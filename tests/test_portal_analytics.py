from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import app.periods as periods
from app.portal_api import PortalService, create_portal_router
from app.portal_db import PortalDatabase


class NoLoginIdentity:
    async def begin_login(self, *_args, **_kwargs):
        raise AssertionError("not used")


def _portal_client(tmp_path):
    repository = PortalDatabase(str(tmp_path / "portal-api.db"), key_pepper="c" * 40)
    app = FastAPI()
    app.include_router(create_portal_router(PortalService(repository, NoLoginIdentity(), cookie_secure=False)))
    client = TestClient(app)
    return client, repository


def _sign_in(client, repository, username, role="developer"):
    user = repository.upsert_user(subject=username, email=None, name=username, role=role)
    session = repository.create_session(user["id"], ttl_seconds=3600)
    client.cookies.set("portal_session", session.raw_token)
    client.cookies.set("portal_csrf", session.csrf_token)
    return user


def _insert_legacy_usage(repository, owner, key, *, model, provider, cost, occurred_at, brand_id):
    with repository.connect() as connection:
        connection.execute(
            """INSERT INTO portal_usage_events(
                id,owner_user_id,owner_name_snapshot,owner_email_snapshot,key_id,key_label_snapshot,
                provider_id,provider_name_snapshot,model_id,occurred_at,status,estimated_cost_usd,
                amount_nano_usd,brand_id,canonical_model_id,brand_snapshot
            ) VALUES(?,?,?,?,?,?,?,?,?,?,'success',?,NULL,?,?,?)""",
            (f"legacy-{model}-{occurred_at}-{cost}", owner["id"], owner["display_name"], owner["email"],
             key["id"], key["label"], None, provider, model, occurred_at, cost, brand_id, model, provider),
        )


def test_dashboard_window_uses_berlin_calendar_month_and_captured_now():
    now = datetime(2026, 9, 28, 10, 15, tzinfo=timezone.utc)

    window = periods.dashboard_window("current_month", now)

    assert window.start_utc == datetime(2026, 8, 31, 22, tzinfo=timezone.utc)
    assert window.end_utc == now
    assert window.timezone_name == "Europe/Berlin"


def test_dashboard_window_day_ranges_cover_local_dates_including_today():
    now = datetime(2026, 3, 29, 12, tzinfo=timezone.utc)

    window = periods.dashboard_window("7d", now)

    assert window.start_utc == datetime(2026, 3, 22, 23, tzinfo=timezone.utc)
    assert window.end_utc == now


def test_dashboard_window_supports_all_range_lengths_and_rejects_naive_now():
    now = datetime(2026, 9, 28, 10, 15, tzinfo=timezone.utc)

    assert periods.dashboard_window("30d", now).start_utc == datetime(2026, 8, 29, 22, tzinfo=timezone.utc)
    assert periods.dashboard_window("90d", now).start_utc == datetime(2026, 6, 30, 22, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="timezone-aware"):
        periods.dashboard_window("7d", datetime(2026, 9, 28, 10, 15))


def test_dashboard_window_handles_leap_february_and_berlin_year_rollover():
    february = periods.dashboard_window("current_month", datetime(2024, 2, 29, 12, tzinfo=timezone.utc))
    december = periods.dashboard_window("current_month", datetime(2026, 12, 31, 22, 30, tzinfo=timezone.utc))
    january = periods.dashboard_window("current_month", datetime(2026, 12, 31, 23, 30, tzinfo=timezone.utc))

    assert february.start_utc == datetime(2024, 1, 31, 23, tzinfo=timezone.utc)
    assert december.start_utc == datetime(2026, 11, 30, 23, tzinfo=timezone.utc)
    assert january.start_utc == datetime(2026, 12, 31, 23, tzinfo=timezone.utc)


def test_dashboard_analytics_uses_event_snapshots_and_exact_known_cost(tmp_path):
    repository = PortalDatabase(str(tmp_path / "analytics.db"), key_pepper="a" * 40)
    owner = repository.upsert_user(subject="analytics-owner", email=None, name="Owner")
    key = repository.create_user_key(owner["id"], "Historical key", allowed_models_mode="all_approved")
    start = "2026-09-01T00:00:00+02:00"
    repository.record_usage(
        owner["id"], key["id"], model="brand::deleted-model", provider_name="Deleted Brand",
        input_tokens=4, output_tokens=3, total_tokens=7, latency_ms=10, status="success",
        estimated_cost_usd=None, amount_nano_usd=123_456_789, occurred_at=start,
        brand_id="brand", canonical_model_id="deleted-model",
    )
    repository.record_usage(
        owner["id"], key["id"], model="brand::unpriced-model", provider_name="Deleted Brand",
        input_tokens=None, output_tokens=2, total_tokens=None, latency_ms=20, status="error",
        estimated_cost_usd=None, occurred_at="2026-09-02T12:00:00+02:00",
        brand_id="brand", canonical_model_id="unpriced-model",
    )

    analytics = repository.dashboard_analytics(owner["id"], periods.dashboard_window(
        "current_month", datetime(2026, 9, 3, 12, tzinfo=timezone.utc),
    ))

    assert analytics["summary"] == {
        "requests": 2, "successfulRequests": 1, "rejectedRequests": 0,
        "inputTokens": 4, "outputTokens": 5, "totalTokens": 7,
        "knownSpendUsd": "0.123456789", "unpricedRequests": 1,
    }
    assert analytics["modelSpend"] == [
        {"id": analytics["modelSpend"][0]["id"], "modelId": "deleted-model", "providerName": "Deleted Brand", "requests": 1,
         "totalTokens": 7, "spendUsd": "0.123456789"},
        {"id": analytics["modelSpend"][1]["id"], "modelId": "unpriced-model", "providerName": "Deleted Brand", "requests": 1,
         "totalTokens": None, "spendUsd": None},
    ]
    assert [point["day"] for point in analytics["series"]] == ["2026-09-01", "2026-09-02", "2026-09-03"]
    assert analytics["series"][0]["estimatedSpendUsd"] == "0.123456789"
    assert analytics["series"][1]["estimatedSpendUsd"] is None
    assert [point["unpricedRequests"] for point in analytics["series"]] == [0, 1, 0]
    assert analytics["series"][2]["requests"] == 0
    assert analytics["series"][2]["totalTokens"] == 0
    assert analytics["series"][2]["estimatedSpendUsd"] == "0"


def test_dashboard_analytics_applies_owner_and_exclusive_utc_end(tmp_path):
    repository = PortalDatabase(str(tmp_path / "scoped-analytics.db"), key_pepper="b" * 40)
    owner = repository.upsert_user(subject="scope-a", email=None, name="A")
    outsider = repository.upsert_user(subject="scope-b", email=None, name="B")
    owner_key = repository.create_user_key(owner["id"], "A", allowed_models_mode="all_approved")
    outsider_key = repository.create_user_key(outsider["id"], "B", allowed_models_mode="all_approved")
    window = periods.dashboard_window("7d", datetime(2026, 9, 8, 10, tzinfo=timezone.utc))
    for user, key, model, occurred in (
        (owner, owner_key, "inside", window.start_utc.isoformat()),
        (owner, owner_key, "exclusive-end", window.end_utc.isoformat()),
        (outsider, outsider_key, "outsider", window.start_utc.isoformat()),
    ):
        repository.record_usage(user["id"], key["id"], model=model, provider_name="Snapshot",
                                input_tokens=1, output_tokens=1, total_tokens=2, latency_ms=1,
                                status="success", estimated_cost_usd=0.000000001,
                                occurred_at=occurred,
                                brand_id="brand" if model == "inside" else None,
                                canonical_model_id=model)

    analytics = repository.dashboard_analytics(owner["id"], window)

    assert analytics["summary"]["requests"] == 1
    assert [model["modelId"] for model in analytics["modelSpend"]] == ["inside"]
    assert analytics["summary"]["knownSpendUsd"] == "0.000000001"


def test_daily_unpriced_coverage_is_reported_even_when_known_spend_is_zero(tmp_path):
    repository = PortalDatabase(str(tmp_path / "daily-coverage.db"), key_pepper="g" * 40)
    owner = repository.upsert_user(subject="daily-coverage", email=None, name="Owner")
    key = repository.create_user_key(owner["id"], "Key", allowed_models_mode="all_approved")
    for model, cost, nano_cost in (("free-model", 0, 0), ("unknown-price-model", None, None)):
        repository.record_usage(
            owner["id"], key["id"], model=model, provider_name="Brand",
            input_tokens=1, output_tokens=1, total_tokens=2, latency_ms=1, status="success",
            estimated_cost_usd=cost, amount_nano_usd=nano_cost, brand_id="brand",
            canonical_model_id=model, occurred_at="2026-09-02T12:00:00+02:00",
        )

    analytics = repository.dashboard_analytics(
        owner["id"], periods.dashboard_window("current_month", datetime(2026, 9, 3, 12, tzinfo=timezone.utc)),
    )
    day = next(point for point in analytics["series"] if point["day"] == "2026-09-02")

    assert analytics["summary"]["unpricedRequests"] == 1
    assert day["estimatedSpendUsd"] == "0"
    assert day["unpricedRequests"] == 1


def test_dashboard_analytics_keeps_same_model_separate_by_brand_snapshot(tmp_path):
    repository = PortalDatabase(str(tmp_path / "brand-scope.db"), key_pepper="d" * 40)
    owner = repository.upsert_user(subject="brand-scope", email=None, name="Owner")
    key = repository.create_user_key(owner["id"], "Key", allowed_models_mode="all_approved")
    for brand_id, provider_name, cost in (("brand:one", "Provider One", 0.25), ("brand:two", "Provider Two", 0.75)):
        repository.record_usage(
            owner["id"], key["id"], model="same-model", provider_name=provider_name,
            input_tokens=2, output_tokens=3, total_tokens=5, latency_ms=10, status="success",
            estimated_cost_usd=cost, brand_id=brand_id, canonical_model_id="same-model",
            occurred_at="2026-09-02T12:00:00+02:00",
        )

    analytics = repository.dashboard_analytics(
        owner["id"], periods.dashboard_window("current_month", datetime(2026, 9, 3, 12, tzinfo=timezone.utc)),
    )

    assert [row["modelId"] for row in analytics["modelSpend"]] == ["same-model", "same-model"]
    assert len({row["id"] for row in analytics["modelSpend"]}) == 2
    assert {row["providerName"] for row in analytics["modelSpend"]} == {"Provider One", "Provider Two"}
    assert "brand:one" not in str(analytics) and "brand:two" not in str(analytics)
    assert analytics["summary"]["knownSpendUsd"] == "1"


def test_dashboard_analytics_preserves_repeated_subnano_legacy_estimates(tmp_path):
    repository = PortalDatabase(str(tmp_path / "subnano.db"), key_pepper="e" * 40)
    owner = repository.upsert_user(subject="subnano", email=None, name="Owner")
    key = repository.create_user_key(owner["id"], "Legacy key", allowed_models_mode="all_approved")
    for index in range(2):
        _insert_legacy_usage(
            repository, owner, key, model="legacy-model", provider="Legacy provider",
            cost=0.0000000004, occurred_at=f"2026-09-02T12:00:0{index}+02:00", brand_id="legacy-brand",
        )
    analytics = repository.dashboard_analytics(
        owner["id"], periods.dashboard_window("current_month", datetime(2026, 9, 3, 12, tzinfo=timezone.utc)),
    )

    assert analytics["summary"]["knownSpendUsd"] == "0.0000000008"
    assert analytics["modelSpend"][0]["spendUsd"] == "0.0000000008"
    assert repository.usage_cost_nano_usd(owner["id"]) == 2


def test_dashboard_analytics_prefers_settled_nano_charge_over_fractional_estimate(tmp_path):
    repository = PortalDatabase(str(tmp_path / "settled-cost.db"), key_pepper="f" * 40)
    owner = repository.upsert_user(subject="settled-cost", email=None, name="Owner")
    key = repository.create_user_key(owner["id"], "Key", allowed_models_mode="all_approved")
    repository.record_usage(
        owner["id"], key["id"], model="model", provider_name="Brand",
        input_tokens=1, output_tokens=1, total_tokens=2, latency_ms=1, status="success",
        estimated_cost_usd=0.0000000004, amount_nano_usd=1,
        brand_id="brand", canonical_model_id="model",
        occurred_at="2026-09-02T12:00:00+02:00",
    )

    analytics = repository.dashboard_analytics(
        owner["id"], periods.dashboard_window("current_month", datetime(2026, 9, 3, 12, tzinfo=timezone.utc)),
    )

    assert analytics["summary"]["knownSpendUsd"] == "0.000000001"
    assert analytics["modelSpend"][0]["spendUsd"] == "0.000000001"


def test_developer_dashboard_returns_default_period_analytics_and_rejects_bad_range(tmp_path):
    client, repository = _portal_client(tmp_path)
    user = _sign_in(client, repository, "api-developer")
    key = repository.create_user_key(user["id"], "test", allowed_models_mode="all_approved")
    repository.record_usage(user["id"], key["id"], model="brand::model", provider_name="Brand",
                            input_tokens=1, output_tokens=2, total_tokens=3, latency_ms=10,
                            status="success", estimated_cost_usd=0.000000001,
                            occurred_at="2026-09-10T12:00:00+02:00",
                            brand_id="brand", canonical_model_id="model")

    response = client.get("/api/developer/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["analytics"]["period"]["key"] == "current_month"
    assert body["analytics"]["period"]["timezone"] == "Europe/Berlin"
    assert body["analytics"]["summary"]["knownSpendUsd"] == "0.000000001"
    assert body["analytics"]["modelSpend"][0]["modelId"] == "model"
    assert client.get("/api/developer/dashboard?range=year").status_code == 422


def test_operator_dashboard_analytics_is_global_and_range_scoped(tmp_path):
    client, repository = _portal_client(tmp_path)
    for subject, model in (("a", "model-a"), ("b", "model-b")):
        user = repository.upsert_user(subject=subject, email=None, name=subject)
        key = repository.create_user_key(user["id"], model, allowed_models_mode="all_approved")
        repository.record_usage(user["id"], key["id"], model=model, provider_name="Brand",
                                input_tokens=1, output_tokens=1, total_tokens=2, latency_ms=10,
                                status="success", estimated_cost_usd=0.000000001,
                                occurred_at="2026-09-10T12:00:00+02:00",
                                brand_id=f"brand-{subject}", canonical_model_id=model)
    _sign_in(client, repository, "api-operator", role="operator")

    response = client.get("/api/operator/dashboard?range=30d")

    assert response.status_code == 200
    assert response.json()["analytics"]["period"]["key"] == "30d"
    assert response.json()["analytics"]["summary"]["requests"] == 2
    assert {row["modelId"] for row in response.json()["analytics"]["modelSpend"]} == {"model-a", "model-b"}
