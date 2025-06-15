from fastapi.testclient import TestClient
from .main import app
from unittest.mock import ANY
from unittest import TestCase

client = TestClient(app)

class UrlPostTests(TestCase):
    def test_post_url_happy_path(self):
        body = {
            "long_url": "https://www.google.com"
        }
        response = client.post("/urls", json=body)

        assert response.status_code == 200

        expected = {
            "short_id": ANY
        }

        assert response.json() == expected

    def test_post_duplicate_urls(self):
        body = {
            "long_url": "https://www.realpython.com"
        }

        response = client.post("/urls", json=body)

        assert response.status_code == 200

        previous_short_id = response.json()["short_id"]

        res2 = client.post("/urls", json=body)

        assert previous_short_id == res2.json()["short_id"]

    def test_post_custom_alias(self):
        body = {
            "long_url": "https://www.fastapi.tiangolo.com",
            "custom_alias": "fastapisite"
        }

        response = client.post("/urls", json=body)

        assert response.status_code == 200

        expected = {
            "short_id": ANY,
            "custom_alias": "fastapisite"
        }

        assert response.json() == expected
