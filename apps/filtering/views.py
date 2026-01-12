from __future__ import annotations

from django.http import JsonResponse

from apps.auth.decorators import require_driver
from apps.filtering.services import DictionaryService


"""
GOAL: Provide cities autocomplete endpoint for WebApp filters.

PARAMETERS:
  request: HttpRequest - GET request - Query param: name

RETURNS:
  JsonResponse - {"data": [{id,name,type}, ...]} - HTTP 200

RAISES:
  None

GUARANTEES:
  - Requires a valid driver session (JWT)
  - Returns empty list on upstream failures
"""
@require_driver
def search_cities(request):
    """
    Fetch city suggestions via DictionaryService with caching.
    """
    query = str(request.GET.get("name") or "")
    items = DictionaryService.search_cities(query, limit=10)
    return JsonResponse({"data": items})


"""
GOAL: Provide truck types dictionary endpoint for WebApp filters.

PARAMETERS:
  request: HttpRequest - GET request - No query params required

RETURNS:
  JsonResponse - {"data": [{id,name,short_name}, ...]} - HTTP 200

RAISES:
  None

GUARANTEES:
  - Requires a valid driver session (JWT)
  - Returns empty list on upstream failures
"""
@require_driver
def truck_types(request):
    """
    Fetch truck types dictionary via DictionaryService with caching.
    """
    items = DictionaryService.list_truck_types()
    return JsonResponse({"data": items})


"""
GOAL: Provide load types dictionary endpoint for WebApp filters.

PARAMETERS:
  request: HttpRequest - GET request - No query params required

RETURNS:
  JsonResponse - {"data": [{id,name,short_name}, ...]} - HTTP 200

RAISES:
  None

GUARANTEES:
  - Requires a valid driver session (JWT)
  - Returns empty list on upstream failures
"""
@require_driver
def load_types(request):
    """
    Fetch load types dictionary via DictionaryService with caching.
    """
    items = DictionaryService.list_load_types()
    return JsonResponse({"data": items})
