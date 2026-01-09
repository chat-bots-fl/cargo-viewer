from __future__ import annotations

from django.http import JsonResponse

from apps.integrations.monitoring import CargoTechAuthMonitor


"""
GOAL: Provide a lightweight health endpoint for deployment smoke tests.

PARAMETERS:
  request: HttpRequest - Django request - GET, optional ?deep=1

RETURNS:
  JsonResponse - {"status": "ok", "cargotech": {...}} - HTTP 200

RAISES:
  None

GUARANTEES:
  - Always returns JSON
  - deep check does not raise (returns ok=false on failures)
"""
def healthz(request):
    """
    Return basic status; optionally include CargoTech auth health check when deep=1.
    """
    deep = str(request.GET.get("deep") or "") == "1"
    payload = {"status": "ok"}
    if deep:
        payload["cargotech"] = CargoTechAuthMonitor.check_token_health()
    return JsonResponse(payload)

