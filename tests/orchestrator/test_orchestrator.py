# Tests for the Orchestrator service will go here. 

import pytest
from fastapi.testclient import TestClient
from src.orchestrator import app # Corrected import

@pytest.fixture
def client():
    """Create a TestClient instance for testing the FastAPI app."""
    with TestClient(app) as c:
        yield c

def test_health_check(client: TestClient):
    """Test the /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"} 