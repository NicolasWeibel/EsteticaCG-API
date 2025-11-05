# apps/catalog/tests/test_api.py
import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_list_treatments_empty():
    c = APIClient()
    resp = c.get("/api/v1/treatments/")
    assert resp.status_code in (200, 401)
