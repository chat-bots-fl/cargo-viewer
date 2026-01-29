from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.auth.models import DriverProfile
from apps.auth.services import SessionService

User = get_user_model()


class CargoPricesOOBEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="driver_1", password="testpass")
        DriverProfile.objects.create(
            user=self.user,
            telegram_user_id=123456,
            telegram_username="driver_1",
        )
        self.token = SessionService.create_session(self.user)

    @patch("apps.cargos.views.CargoAPIClient.fetch_cargos")
    def test_prices_endpoint_returns_oob_spans(self, mock_fetch):
        mock_fetch.return_value = {
            "meta": {"size": 1},
            "data": [
                {
                    "id": "6236980507",
                    "points": {
                        "start": {"city": {"name": "Москва"}, "first_date": "2026-01-01"},
                        "finish": {"city": {"name": "Санкт-Петербург"}, "first_date": "2026-01-02"},
                    },
                    "price_carrier": 1350000,
                    "price": 1690000,
                    "weight": 20000,
                    "volume": 86,
                    "distance": 886,
                    "load_types": [{"short_name": "Задняя"}],
                    "truck_types": [{"short_name": "Тент"}],
                }
            ],
        }

        response = self.client.get(
            "/api/cargos/prices/?limit=1&mode=my&seen_ids=6236980507",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn('hx-swap-oob="outerHTML"', html)
        self.assertIn('id="cargo-price-6236980507"', html)

    @patch("apps.cargos.views.CargoAPIClient.fetch_cargos")
    def test_prices_endpoint_deletes_missing_cards(self, mock_fetch):
        mock_fetch.return_value = {
            "meta": {"size": 1},
            "data": [
                {
                    "id": "111",
                    "points": {
                        "start": {"city": {"name": "Москва"}, "first_date": "2026-01-01"},
                        "finish": {"city": {"name": "Санкт-Петербург"}, "first_date": "2026-01-02"},
                    },
                    "price_carrier": 10000,
                }
            ],
        }

        response = self.client.get(
            "/api/cargos/prices/?mode=my&seen_ids=111,222",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn('id="cargo-card-222"', html)
        self.assertIn('hx-swap-oob="delete"', html)

    @patch("apps.cargos.views.CargoAPIClient.fetch_cargos", side_effect=Exception("boom"))
    def test_prices_endpoint_degrades_to_empty_on_upstream_error(self, _mock_fetch):
        response = self.client.get(
            "/api/cargos/prices/?limit=1&mode=my&seen_ids=6236980507",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
