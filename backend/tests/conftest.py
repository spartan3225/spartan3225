import os
import pytest
import requests

BASE_URL = (os.environ.get("EXPO_BACKEND_URL")
            or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or "https://wave-motion-ai.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
DEMO_TOKEN = "demo_token_active"


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def api_url():
    return API


@pytest.fixture(scope="session")
def auth_headers():
    return {"Authorization": f"Bearer {DEMO_TOKEN}"}


@pytest.fixture
def client():
    s = requests.Session()
    return s
