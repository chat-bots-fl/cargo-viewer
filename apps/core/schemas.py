"""
Pydantic schemas for request validation.

This module defines Pydantic v2 models for validating incoming request data
across all API endpoints. All schemas follow AGENTS.md contract conventions.
"""

from __future__ import annotations

from datetime import date
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict


class TelegramAuthRequest(BaseModel):
    """
    GOAL: Validate Telegram WebApp initData for authentication.

    PARAMETERS:
      init_data: str - Telegram WebApp initData string - Must be non-empty

    RETURNS:
      TelegramAuthRequest - Validated auth request - Never None

    RAISES:
      ValueError: If init_data is missing or empty

    GUARANTEES:
      - init_data is a non-empty string
      - Data is ready for TelegramAuthService.validate_init_data()
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    init_data: str = Field(..., min_length=1, description="Telegram WebApp initData string")


class CargoListRequest(BaseModel):
    """
    GOAL: Validate query parameters for cargo list endpoint.

    PARAMETERS:
      limit: int - Number of items per page - 1 to 100, default 20
      offset: int - Pagination offset - >= 0, default 0
      start_point_id: Optional[int] - Starting location filter - Must be positive
      finish_point_id: Optional[int] - Ending location filter - Must be positive
      start_date: Optional[date] - Filter by start date - ISO format YYYY-MM-DD
      weight_volume: Optional[str] - Weight-volume filter "{weight}-{volume}"
      load_types: Optional[str] - CSV of load type IDs - Format "1,2,3"
      truck_types: Optional[str] - CSV of truck type IDs - Format "1,2,3"
      mode: Literal["my", "all"] - Filter mode - Default "my"

    RETURNS:
      CargoListRequest - Validated cargo list request - Never None

    RAISES:
      ValueError: If any parameter is invalid

    GUARANTEES:
      - limit is within [1, 100]
      - offset is >= 0
      - start_date is valid ISO date if provided
      - weight_volume matches pattern "X-Y" if provided
      - load_types and truck_types are valid CSV if provided
      - mode is either "my" or "all"
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    limit: int = Field(default=20, ge=1, le=100, description="Number of items per page (1-100)")
    offset: int = Field(default=0, ge=0, description="Pagination offset (>= 0)")
    start_point_id: Optional[int] = Field(default=None, gt=0, description="Starting location ID")
    finish_point_id: Optional[int] = Field(default=None, gt=0, description="Ending location ID")
    start_date: Optional[date] = Field(default=None, description="Start date (YYYY-MM-DD)")
    weight_volume: Optional[str] = Field(default=None, description="Weight-volume filter (e.g. '15-65')")
    load_types: Optional[str] = Field(default=None, description="CSV of load type IDs")
    truck_types: Optional[str] = Field(default=None, description="CSV of truck type IDs")
    mode: Literal["my", "all"] = Field(default="my", description="Filter mode")

    @field_validator("weight_volume")
    @classmethod
    def validate_weight_volume(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate weight_volume format: must match "X-Y" pattern with decimals.
        """
        if v is None:
            return None
        import re
        pattern = re.compile(r"^\d+(\.\d+)?-\d+(\.\d+)?$")
        if not pattern.match(v):
            raise ValueError(f"Invalid weight_volume format: '{v}'. Expected '{{weight}}-{{volume}}', e.g. '15-65' or '1.5-9'")
        weight_s, volume_s = v.split("-", 1)
        weight_val = float(weight_s)
        volume_val = float(volume_s)
        if not (0.1 <= weight_val <= 1000):
            raise ValueError(f"Weight {weight_val} out of range (0.1-1000)")
        if not (0.1 <= volume_val <= 200):
            raise ValueError(f"Volume {volume_val} out of range (0.1-200)")
        return v

    @field_validator("load_types", "truck_types")
    @classmethod
    def validate_csv_ids(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate CSV format for IDs: must be "1,2,3" pattern.
        """
        if v is None:
            return None
        import re
        if not re.match(r"^\d+(,\d+)*$", v):
            raise ValueError(f"Expected CSV of ids, got '{v}'")
        return v


class CargoDetailRequest(BaseModel):
    """
    GOAL: Validate cargo_id parameter for cargo detail endpoint.

    PARAMETERS:
      cargo_id: str - CargoTech cargo ID - Must be non-empty

    RETURNS:
      CargoDetailRequest - Validated cargo detail request - Never None

    RAISES:
      ValueError: If cargo_id is missing or empty

    GUARANTEES:
      - cargo_id is a non-empty string
      - cargo_id is stripped of whitespace
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    cargo_id: str = Field(..., min_length=1, description="CargoTech cargo ID")


class PaymentCreateRequest(BaseModel):
    """
    GOAL: Validate payment creation request parameters.

    PARAMETERS:
      tariff_name: str - Name of tariff to purchase - Must be non-empty
      return_url: Optional[str] - URL to redirect after payment - Defaults to WEBAPP_URL

    RETURNS:
      PaymentCreateRequest - Validated payment creation request - Never None

    RAISES:
      ValueError: If tariff_name is missing or empty

    GUARANTEES:
      - tariff_name is a non-empty string
      - return_url is a valid URL if provided
      - All strings are stripped of whitespace
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    tariff_name: str = Field(..., min_length=1, description="Name of tariff to purchase")
    return_url: Optional[str] = Field(default=None, description="URL to redirect after payment")

    @field_validator("return_url")
    @classmethod
    def validate_return_url(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate return_url is a valid URL if provided.
        """
        if v is None or v == "":
            return None
        # Basic URL validation
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError(f"Invalid URL: '{v}'. Must start with http:// or https://")
        return v


class FilterRequest(BaseModel):
    """
    GOAL: Validate filter parameters for cargo filtering.

    PARAMETERS:
      start_point_id: Optional[int] - Starting location filter - Must be positive
      finish_point_id: Optional[int] - Ending location filter - Must be positive
      start_date: Optional[date] - Filter by start date - ISO format YYYY-MM-DD
      weight_volume: Optional[str] - Weight-volume filter "{weight}-{volume}"
      load_types: Optional[str] - CSV of load type IDs - Format "1,2,3"
      truck_types: Optional[str] - CSV of truck type IDs - Format "1,2,3"
      mode: Literal["my", "all"] - Filter mode - Default "my"

    RETURNS:
      FilterRequest - Validated filter request - Never None

    RAISES:
      ValueError: If any filter parameter is invalid

    GUARANTEES:
      - All integer IDs are positive if provided
      - start_date is valid ISO date if provided
      - weight_volume matches pattern "X-Y" if provided
      - load_types and truck_types are valid CSV if provided
      - mode is either "my" or "all"
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    start_point_id: Optional[int] = Field(default=None, gt=0, description="Starting location ID")
    finish_point_id: Optional[int] = Field(default=None, gt=0, description="Ending location ID")
    start_date: Optional[date] = Field(default=None, description="Start date (YYYY-MM-DD)")
    weight_volume: Optional[str] = Field(default=None, description="Weight-volume filter (e.g. '15-65')")
    load_types: Optional[str] = Field(default=None, description="CSV of load type IDs")
    truck_types: Optional[str] = Field(default=None, description="CSV of truck type IDs")
    mode: Literal["my", "all"] = Field(default="my", description="Filter mode")

    @field_validator("weight_volume")
    @classmethod
    def validate_weight_volume(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate weight_volume format: must match "X-Y" pattern with decimals.
        """
        if v is None:
            return None
        import re
        pattern = re.compile(r"^\d+(\.\d+)?-\d+(\.\d+)?$")
        if not pattern.match(v):
            raise ValueError(f"Invalid weight_volume format: '{v}'. Expected '{{weight}}-{{volume}}', e.g. '15-65' or '1.5-9'")
        weight_s, volume_s = v.split("-", 1)
        weight_val = float(weight_s)
        volume_val = float(volume_s)
        if not (0.1 <= weight_val <= 1000):
            raise ValueError(f"Weight {weight_val} out of range (0.1-1000)")
        if not (0.1 <= volume_val <= 200):
            raise ValueError(f"Volume {volume_val} out of range (0.1-200)")
        return v

    @field_validator("load_types", "truck_types")
    @classmethod
    def validate_csv_ids(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate CSV format for IDs: must be "1,2,3" pattern.
        """
        if v is None:
            return None
        import re
        if not re.match(r"^\d+(,\d+)*$", v):
            raise ValueError(f"Expected CSV of ids, got '{v}'")
        return v


class TelegramResponseRequest(BaseModel):
    """
    GOAL: Validate Telegram response request from WebApp.

    PARAMETERS:
      cargo_id: str - CargoTech cargo ID - Must be non-empty
      phone: str - Driver phone number - Can be empty
      name: str - Driver name - Can be empty, defaults to user.first_name

    RETURNS:
      TelegramResponseRequest - Validated response request - Never None

    RAISES:
      ValueError: If cargo_id is missing or empty

    GUARANTEES:
      - cargo_id is a non-empty string
      - All strings are stripped of whitespace
      - phone and name can be empty (will use defaults)
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    cargo_id: str = Field(..., min_length=1, description="CargoTech cargo ID")
    phone: str = Field(default="", description="Driver phone number")
    name: str = Field(default="", description="Driver name")
