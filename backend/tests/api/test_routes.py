import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from firmsignal.api.app import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_analyze_empty_company_returns_422():
    response = client.post("/api/analyze", json={"company": ""})
    assert response.status_code == 422


def test_analyze_whitespace_company_returns_422():
    response = client.post("/api/analyze", json={"company": "   "})
    assert response.status_code == 422


def test_analyze_too_long_returns_422():
    response = client.post("/api/analyze", json={"company": "A" * 101})
    assert response.status_code == 422


def test_analyze_valid_company_returns_run_id():
    with patch("firmsignal.api.routes.run_pipeline"):
        response = client.post("/api/analyze", json={"company": "Nvidia"})
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert data["company"] == "Nvidia"
    assert len(data["run_id"]) == 36  # UUID format


def test_stream_unknown_run_id_returns_404():
    response = client.get("/api/stream/nonexistent-run-id")
    assert response.status_code == 404


def test_resume_unknown_run_id_returns_404():
    response = client.post(
        "/api/resume/nonexistent-run-id",
        json={"approved": True},
    )
    assert response.status_code == 404


def test_status_unknown_run_id_returns_404():
    response = client.get("/api/status/nonexistent-run-id")
    assert response.status_code == 404


def test_resume_requires_approved_field():
    response = client.post("/api/resume/some-id", json={})
    assert response.status_code == 422


def test_resume_edits_optional():
    with patch("firmsignal.api.routes.get_run") as mock_get:
        from firmsignal.api.store import RunRecord, RunStatus
        mock_record        = MagicMock(spec=RunRecord)
        mock_record.status = RunStatus.PAUSED
        mock_record.resume_event = MagicMock()
        mock_get.return_value = mock_record

        response = client.post(
            "/api/resume/some-id",
            json={"approved": True},
        )
        assert response.status_code == 200