from __future__ import annotations

from typing import Any, Mapping


"""
GOAL: Safely read nested keys from a dict-like mapping.

PARAMETERS:
  mapping: Mapping[str, Any] - Root mapping - Must be dict-like
  *keys: str - Nested keys path - Can be empty
  default: Any - Default value when path missing - Optional

RETURNS:
  Any - Nested value or default - Never raises KeyError

RAISES:
  None

GUARANTEES:
  - Returns default if any level is missing or not a Mapping
"""
def safe_get(mapping: Mapping[str, Any], *keys: str, default: Any = "") -> Any:
    """
    Safely walk nested dict-like values without KeyError.
    """
    cur: Any = mapping
    for key in keys:
        if not isinstance(cur, Mapping) or key not in cur:
            return default
        cur = cur[key]
    return cur
