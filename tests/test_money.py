from decimal import Decimal

import pytest

from app.money import rate_cost_nano_usd


def test_input_and_output_rates_are_charged_per_million():
    assert rate_cost_nano_usd(
        uncached_input_tokens=1_000_000,
        cached_input_tokens=0,
        output_tokens=500_000,
        input_rate=Decimal("2"),
        output_rate=Decimal("8"),
    ) == 6_000_000_000


def test_cached_tokens_use_cache_rate_only_when_reported_and_configured():
    assert rate_cost_nano_usd(
        uncached_input_tokens=400_000,
        cached_input_tokens=600_000,
        output_tokens=0,
        input_rate=Decimal("2"),
        output_rate=Decimal("0"),
        cached_rate=Decimal("0.5"),
    ) == 1_100_000_000


def test_missing_cache_rate_uses_normal_input_rate():
    assert rate_cost_nano_usd(
        uncached_input_tokens=400_000,
        cached_input_tokens=600_000,
        output_tokens=0,
        input_rate=Decimal("2"),
        output_rate=Decimal("0"),
    ) == 2_000_000_000


def test_fractional_cost_rounds_up_to_nano_usd():
    assert rate_cost_nano_usd(
        uncached_input_tokens=1,
        cached_input_tokens=0,
        output_tokens=1,
        input_rate=Decimal("1E+100"),
        output_rate=Decimal("1E-100"),
    ) == 10**103 + 1


def test_negative_nonfinite_or_boolean_inputs_are_rejected():
    invalid_arguments = (
        {"uncached_input_tokens": -1},
        {"cached_input_tokens": True},
        {"output_tokens": 1.5},
        {"input_rate": Decimal("-0.1")},
        {"output_rate": Decimal("Infinity")},
        {"cached_rate": Decimal("NaN")},
    )
    valid_arguments = {
        "uncached_input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "input_rate": Decimal("0"),
        "output_rate": Decimal("0"),
    }

    for invalid in invalid_arguments:
        with pytest.raises(ValueError):
            rate_cost_nano_usd(**(valid_arguments | invalid))


def test_large_token_counts_keep_exact_integer_cost():
    assert rate_cost_nano_usd(
        uncached_input_tokens=10**30 + 1,
        cached_input_tokens=0,
        output_tokens=0,
        input_rate=Decimal("1E-33"),
        output_rate=Decimal("0"),
    ) == 2
