"""
Unit tests for apps/cargos/.

This module contains tests for cargo service, filtering service,
and dictionary service.
"""

from __future__ import annotations

from unittest.mock import Mock, patch
from django.test import TestCase
from django.core.cache import cache
from django.core.exceptions import ValidationError

from apps.cargos.services import CargoService, _format_rub, _stable_hash
from apps.filtering.services import FilterService, DictionaryService
from apps.filtering.services import FilterService as FilterServiceAlias


class CargoServiceHelperTests(TestCase):
    """Test helper functions for cargo service."""
    
    def test_stable_hash_same_input(self):
        """Test that _stable_hash returns same hash for same input."""
        data = {"a": 1, "b": 2}
        hash1 = _stable_hash(data)
        hash2 = _stable_hash(data)
        
        self.assertEqual(hash1, hash2)
    
    def test_stable_hash_different_order(self):
        """Test that _stable_hash returns same hash regardless of key order."""
        hash1 = _stable_hash({"a": 1, "b": 2})
        hash2 = _stable_hash({"b": 2, "a": 1})
        
        self.assertEqual(hash1, hash2)
    
    def test_stable_hash_different_input(self):
        """Test that _stable_hash returns different hash for different input."""
        hash1 = _stable_hash({"a": 1, "b": 2})
        hash2 = _stable_hash({"a": 1, "b": 3})
        
        self.assertNotEqual(hash1, hash2)
    
    def test_format_rub_valid_price(self):
        """Test that _format_rub formats valid price correctly."""
        result = _format_rub(352500)
        self.assertEqual(result, "3 525 ₽")
    
    def test_format_rub_with_decimals(self):
        """Test that _format_rub handles decimal prices."""
        result = _format_rub(35250)
        self.assertEqual(result, "352,50 ₽")
    
    def test_format_rub_none_price(self):
        """Test that _format_rub returns dash for None price."""
        result = _format_rub(None)
        self.assertEqual(result, "—")
    
    def test_format_rub_zero_price(self):
        """Test that _format_rub returns dash for zero price."""
        result = _format_rub(0)
        self.assertEqual(result, "—")


class CargoServiceTests(TestCase):
    """Test CargoService for cargo operations."""
    
    def setUp(self):
        cache.clear()
    
    def test_format_cargo_card_basic(self):
        """Test that format_cargo_card formats basic cargo data."""
        cargo = {
            "id": "12345",
            "weight": 15000,
            "volume": 65,
            "price": 352500,
            "points": {
                "start": {
                    "city": {"name": "Москва"},
                    "first_date": "2024-01-15"
                },
                "finish": {
                    "city": {"name": "Санкт-Петербург"},
                    "first_date": "2024-01-16"
                }
            },
            "load_types": [{"short_name": "Задняя"}],
            "truck_types": [{"short_name": "Тент"}]
        }
        
        result = CargoService.format_cargo_card(cargo)
        
        self.assertEqual(result["id"], "12345")
        self.assertEqual(result["route"], "Москва → Санкт-Петербург")
        self.assertEqual(result["date"], "2024-01-15")
        self.assertEqual(result["wv"], "15,0 т / 65 м³")
        self.assertEqual(result["price"], "3 525 ₽")
        self.assertEqual(result["pills"], ["Задняя", "Тент"])
    
    def test_format_cargo_card_missing_fields(self):
        """Test that format_cargo_card handles missing fields gracefully."""
        cargo = {"id": "12345"}
        
        result = CargoService.format_cargo_card(cargo)
        
        self.assertEqual(result["id"], "12345")
        self.assertEqual(result["route"], "12345")
        self.assertEqual(result["date"], "")
        self.assertEqual(result["wv"], "")
        self.assertEqual(result["price"], "—")
        self.assertEqual(result["pills"], [])
    
    def test_format_cargo_card_no_load_truck_types(self):
        """Test that format_cargo_card handles empty load/truck types."""
        cargo = {
            "id": "12345",
            "weight": 15000,
            "volume": 65,
            "price": 352500,
            "points": {
                "start": {"city": {"name": "Москва"}},
                "finish": {"city": {"name": "СПБ"}}
            },
            "load_types": [],
            "truck_types": []
        }
        
        result = CargoService.format_cargo_card(cargo)
        
        self.assertEqual(result["pills"], [])
    
    def test_get_cargos_with_cache_hit(self):
        """Test that get_cargos returns cached data when available."""
        cache_key = f"user:1:cargos:{_stable_hash({})}"
        cached_result = {"cards": [], "meta": {}}
        cache.set(cache_key, cached_result, timeout=300)
        
        result = CargoService.get_cargos(user_id=1, api_params={})
        
        self.assertEqual(result, cached_result)
    
    @patch('apps.cargos.services.CargoAPIClient.fetch_cargos')
    def test_get_cargos_cache_miss(self, mock_fetch):
        """Test that get_cargos fetches from API on cache miss."""
        mock_fetch.return_value = {"data": [], "meta": {}}
        
        result = CargoService.get_cargos(user_id=1, api_params={})
        
        self.assertEqual(result["cards"], [])
        self.assertEqual(result["meta"], {})
        mock_fetch.assert_called_once()
    
    @patch('apps.cargos.services.CargoAPIClient.fetch_cargos')
    def test_get_cargos_formats_cards(self, mock_fetch):
        """Test that get_cargos formats cargo cards."""
        mock_fetch.return_value = {
            "data": [
                {
                    "id": "12345",
                    "weight": 15000,
                    "volume": 65,
                    "price": 352500,
                    "points": {
                        "start": {"city": {"name": "Москва"}},
                        "finish": {"city": {"name": "СПБ"}}
                    },
                    "load_types": [{"short_name": "Задняя"}],
                    "truck_types": [{"short_name": "Тент"}]
                }
            ],
            "meta": {}
        }
        
        result = CargoService.get_cargos(user_id=1, api_params={})
        
        self.assertEqual(len(result["cards"]), 1)
        self.assertEqual(result["cards"][0]["id"], "12345")
        self.assertEqual(result["cards"][0]["route"], "Москва → СПБ")
    
    def test_get_cargos_invalid_user_id(self):
        """Test that get_cargos raises ValueError for invalid user_id."""
        with self.assertRaises(ValueError):
            CargoService.get_cargos(user_id=0, api_params={})
        
        with self.assertRaises(ValueError):
            CargoService.get_cargos(user_id=-1, api_params={})
    
    @patch('apps.cargos.services.CargoAPIClient.fetch_cargos')
    def test_get_cargos_api_error_with_cache(self, mock_fetch):
        """Test that get_cargos returns cached data on API error."""
        cache_key = f"user:1:cargos:{_stable_hash({})}"
        cached_result = {"cards": [], "meta": {}}
        cache.set(cache_key, cached_result, timeout=300)
        
        mock_fetch.side_effect = Exception("API Error")
        
        result = CargoService.get_cargos(user_id=1, api_params={})
        
        self.assertEqual(result, cached_result)
    
    @patch('apps.cargos.services.CargoAPIClient.fetch_cargo_detail')
    def test_get_cargo_detail_with_cache_hit(self, mock_fetch):
        """Test that get_cargo_detail returns cached data when available."""
        cache_key = "cargo:12345:detail"
        cached_result = {"id": "12345", "route": "Москва → СПБ"}
        cache.set(cache_key, cached_result, timeout=900)
        
        result = CargoService.get_cargo_detail(cargo_id="12345")
        
        self.assertEqual(result, cached_result)
        mock_fetch.assert_not_called()
    
    @patch('apps.cargos.services.CargoAPIClient.fetch_cargo_detail')
    def test_get_cargo_detail_cache_miss(self, mock_fetch):
        """Test that get_cargo_detail fetches from API on cache miss."""
        mock_fetch.return_value = {
            "data": {
                "id": "12345",
                "weight": 15000,
                "volume": 65,
                "price": 352500,
                "points": {
                    "start": {"city": {"name": "Москва"}},
                    "finish": {"city": {"name": "СПБ"}}
                }
            }
        }
        
        result = CargoService.get_cargo_detail(cargo_id="12345")
        
        self.assertEqual(result["id"], "12345")
        mock_fetch.assert_called_once()
    
    def test_get_cargo_detail_empty_cargo_id(self):
        """Test that get_cargo_detail raises ValueError for empty cargo_id."""
        with self.assertRaises(ValueError):
            CargoService.get_cargo_detail(cargo_id="")
    
    @patch('apps.cargos.services.CargoAPIClient.fetch_cargo_detail')
    def test_get_cargo_detail_formats_detail(self, mock_fetch):
        """Test that get_cargo_detail formats cargo detail."""
        mock_fetch.return_value = {
            "data": {
                "id": "12345",
                "weight": 15000,
                "volume": 65,
                "price": 352500,
                "distance": 700,
                "points": {
                    "start": {
                        "city": {"name": "Москва"},
                        "address": "ул. Тестовая, 1",
                        "first_date": "2024-01-15"
                    },
                    "finish": {
                        "city": {"name": "Санкт-Петербург"},
                        "address": "ул. Тестовая, 2",
                        "first_date": "2024-01-16"
                    }
                },
                "shipper": {
                    "name": "ООО Тестовая Компания",
                    "inn": "1234567890"
                },
                "extra": {
                    "note": "Тестовый комментарий"
                }
            }
        }
        
        result = CargoService.get_cargo_detail(cargo_id="12345")
        
        self.assertEqual(result["id"], "12345")
        self.assertEqual(result["route"], "Москва → Санкт-Петербург")
        self.assertEqual(result["comment"], "Тестовый комментарий")
        self.assertEqual(result["shipper"]["name"], "ООО Тестовая Компания")
        self.assertEqual(result["shipper"]["inn"], "1234567890")


class FilterServiceTests(TestCase):
    """Test FilterService for filter validation and query building."""
    
    def setUp(self):
        cache.clear()
    
    def test_validate_weight_volume_valid(self):
        """Test that validate_weight_volume accepts valid format."""
        result = FilterService.validate_weight_volume("15-65")
        
        self.assertEqual(result, {"filter[wv]": "15-65"})
    
    def test_validate_weight_volume_with_decimals(self):
        """Test that validate_weight_volume accepts decimal values."""
        result = FilterService.validate_weight_volume("1.5-9.5")
        
        self.assertEqual(result, {"filter[wv]": "1.5-9.5"})
    
    def test_validate_weight_volume_empty(self):
        """Test that validate_weight_volume returns empty dict for empty value."""
        result = FilterService.validate_weight_volume("")
        
        self.assertEqual(result, {})
    
    def test_validate_weight_volume_any(self):
        """Test that validate_weight_volume returns empty dict for 'any'."""
        result = FilterService.validate_weight_volume("any")
        
        self.assertEqual(result, {})
    
    def test_validate_weight_volume_invalid_format(self):
        """Test that validate_weight_volume raises ValidationError for invalid format."""
        with self.assertRaises(ValidationError):
            FilterService.validate_weight_volume("15")
        
        with self.assertRaises(ValidationError):
            FilterService.validate_weight_volume("15-")
    
    def test_validate_weight_volume_out_of_range(self):
        """Test that validate_weight_volume raises ValidationError for out of range values."""
        with self.assertRaises(ValidationError):
            FilterService.validate_weight_volume("0.05-10")
        
        with self.assertRaises(ValidationError):
            FilterService.validate_weight_volume("10-0.05")
    
    def test_validate_filters_valid(self):
        """Test that validate_filters accepts valid filters."""
        filters = {
            "start_point_id": 1,
            "finish_point_id": 2,
            "start_date": "2024-01-15",
            "weight_volume": "15-65",
            "load_types": "1,2,3",
            "truck_types": "1,2,3",
            "mode": "my"
        }
        
        result = FilterService.validate_filters(filters)
        
        self.assertEqual(result["start_point_id"], 1)
        self.assertEqual(result["finish_point_id"], 2)
        self.assertEqual(result["mode"], "my")
    
    def test_validate_filters_invalid(self):
        """Test that validate_filters raises ValidationError for invalid filters."""
        filters = {"weight_volume": "invalid"}
        
        with self.assertRaises(ValidationError):
            FilterService.validate_filters(filters)
    
    def test_build_query_defaults(self):
        """Test that build_query includes default parameters."""
        params = FilterService.build_query({})
        
        self.assertIn("include", params)
        self.assertIn("limit", params)
        self.assertIn("offset", params)
        self.assertIn("filter[mode]", params)
        self.assertIn("filter[user_id]", params)
        self.assertEqual(params["filter[mode]"], "my")
    
    def test_build_query_with_filters(self):
        """Test that build_query includes filter parameters."""
        filters = {
            "start_point_id": 1,
            "finish_point_id": 2,
            "start_date": "2024-01-15",
            "weight_volume": "15-65",
            "load_types": "1,2,3",
            "truck_types": "1,2,3"
        }
        
        params = FilterService.build_query(filters)
        
        self.assertEqual(params["filter[start_point_id]"], 1)
        self.assertEqual(params["filter[finish_point_id]"], 2)
        self.assertEqual(params["filter[start_date]"], "2024-01-15")
        self.assertIn("filter[wv]", params)
        self.assertEqual(params["filter[load_types]"], "1,2,3")
        self.assertEqual(params["filter[truck_types]"], "1,2,3")
    
    def test_build_query_with_point_id_includes_radius(self):
        """Test that build_query includes radius for point filters."""
        filters = {"start_point_id": 1}
        
        params = FilterService.build_query(filters)
        
        self.assertEqual(params["filter[start_point_type]"], 2)
        self.assertEqual(params["filter[start_point_radius]"], 50)
    
    def test_build_query_invalid_limit(self):
        """Test that build_query raises ValidationError for invalid limit."""
        with self.assertRaises(ValidationError):
            FilterService.build_query({}, limit=0)
        
        with self.assertRaises(ValidationError):
            FilterService.build_query({}, limit=101)
    
    def test_build_query_invalid_offset(self):
        """Test that build_query raises ValidationError for invalid offset."""
        with self.assertRaises(ValidationError):
            FilterService.build_query({}, offset=-1)


class DictionaryServiceTests(TestCase):
    """Test DictionaryService for city search."""
    
    def setUp(self):
        cache.clear()
    
    @patch('apps.filtering.services.CargoAPIClient.search_cities')
    def test_search_cities_with_cache_hit(self, mock_search):
        """Test that search_cities returns cached data when available."""
        cache_key = "cities:москва:10"
        cached_result = [{"id": 1, "name": "Москва", "type": "city"}]
        cache.set(cache_key, cached_result, timeout=86400)
        
        result = DictionaryService.search_cities("Москва", limit=10)
        
        self.assertEqual(result, cached_result)
        mock_search.assert_not_called()
    
    @patch('apps.filtering.services.CargoAPIClient.search_cities')
    def test_search_cities_cache_miss(self, mock_search):
        """Test that search_cities fetches from API on cache miss."""
        mock_search.return_value = {"data": [{"id": 1, "name": "Москва", "type": "city"}]}
        
        result = DictionaryService.search_cities("Москва", limit=10)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Москва")
        mock_search.assert_called_once()
    
    @patch('apps.filtering.services.CargoAPIClient.search_cities')
    def test_search_cities_normalizes_query(self, mock_search):
        """Test that search_cities normalizes query (lowercase, strip)."""
        mock_search.return_value = {"data": []}
        
        DictionaryService.search_cities("  Москва  ", limit=10)
        
        mock_search.assert_called_once_with("москва", limit=10, offset=0)
    
    @patch('apps.filtering.services.CargoAPIClient.search_cities')
    def test_search_cities_empty_query(self, mock_search):
        """Test that search_cities handles empty query."""
        mock_search.return_value = {"data": []}
        
        result = DictionaryService.search_cities("", limit=10)
        
        self.assertEqual(result, [])
        mock_search.assert_called_once_with("", limit=10, offset=0)
    
    @patch('apps.filtering.services.CargoAPIClient.search_cities')
    def test_search_cities_api_error(self, mock_search):
        """Test that search_cities returns empty list on API error."""
        mock_search.side_effect = Exception("API Error")
        
        result = DictionaryService.search_cities("Москва", limit=10)
        
        self.assertEqual(result, [])
    
    @patch('apps.filtering.services.CargoAPIClient.search_cities')
    def test_search_cities_custom_limit(self, mock_search):
        """Test that search_cities respects custom limit."""
        mock_search.return_value = {"data": []}
        
        DictionaryService.search_cities("Москва", limit=20)
        
        mock_search.assert_called_once_with("москва", limit=20, offset=0)
    
    @patch('apps.filtering.services.CargoAPIClient.search_cities')
    def test_search_cities_caches_result(self, mock_search):
        """Test that search_cities caches API result."""
        mock_search.return_value = {"data": [{"id": 1, "name": "Москва", "type": "city"}]}
        
        DictionaryService.search_cities("Москва", limit=10)
        
        cache_key = "cities:москва:10"
        cached_result = cache.get(cache_key)
        self.assertIsNotNone(cached_result)
        self.assertEqual(cached_result[0]["name"], "Москва")
