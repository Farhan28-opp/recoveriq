"""
Tests for the RecoverIQ FastAPI health endpoints.

These tests exercise the existing FastAPI application in-process via
TestClient. They do not start uvicorn and do not require PostgreSQL
to be running, since the health endpoints do not query the database.

Run with:
    pytest tests/test_api.py -v
"""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


# ==================================================
# TEST 1 — ROOT ENDPOINT
# ==================================================

def test_root_endpoint_returns_expected_response():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "RecoverIQ",
        "status": "ok",
    }


# ==================================================
# TEST 2 — HEALTH ENDPOINT
# ==================================================

def test_health_endpoint_returns_expected_response():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "recoveriq-api",
    }


# ==================================================
# TEST 3 — APPLICATION METADATA
# ==================================================

def test_application_metadata():
    assert app.title == "RecoverIQ"
    assert "AI-powered revenue recovery platform" in app.description
