import pytest
from cryptography.fernet import Fernet
from pathlib import Path
from uuid import uuid4
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.database import Database
from app.main import app


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / f".test-provider-{uuid4().hex}.db")
    settings = Settings(database_path=db_path, provider_key_pepper="test-pepper", provider_secret_key=Fernet.generate_key().decode(), admin_token="admin", allowed_models="qwen-test", alibaba_api_key="test-upstream", input_price_per_million=1, output_price_per_million=1)
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client, settings, Database(db_path, "test-pepper")
    app.dependency_overrides.clear()
    try:
        Path(db_path).unlink(missing_ok=True)
    except PermissionError:
        pass
