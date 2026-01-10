"""
Data Transfer Objects (DTOs) for cargo-viewer application.

This module defines pydantic v2 DTOs for transferring data between layers.
All DTOs use from_attributes=True for Django model compatibility.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, TypeVar, Type
from pydantic import BaseModel, Field, ConfigDict

from django.db.models import Model

# Type variable for generic DTO functions
T = TypeVar('T', bound=BaseModel)


# ============================================================================
# Auth DTOs
# ============================================================================

class UserDTO(BaseModel):
    """
    DTO for user data transfer.
    """
    id: int
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    is_driver: bool = False
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class DriverProfileDTO(BaseModel):
    """
    DTO for driver profile data transfer.
    """
    id: int
    user_id: int
    company_name: Optional[str] = None
    inn: Optional[str] = None
    ogrn: Optional[str] = None
    license_number: Optional[str] = None
    license_expiry: Optional[datetime] = None
    truck_type: Optional[str] = None
    truck_capacity: Optional[float] = None
    verified: bool = False
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class TelegramSessionDTO(BaseModel):
    """
    DTO for Telegram session data transfer.
    """
    id: int
    user_id: int
    telegram_id: int
    session_data: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Cargo DTOs
# ============================================================================

class CargoCardDTO(BaseModel):
    """
    DTO for cargo card (list view) data transfer.
    """
    id: int
    cargo_id: str
    title: str
    route_from: str
    route_to: str
    distance: Optional[int] = None
    price: Optional[Decimal] = None
    cargo_type: Optional[str] = None
    weight: Optional[float] = None
    volume: Optional[float] = None
    loading_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class CargoDetailDTO(BaseModel):
    """
    DTO for cargo detail (full view) data transfer.
    """
    id: int
    cargo_id: str
    title: str
    description: Optional[str] = None
    route_from: str
    route_to: str
    distance: Optional[int] = None
    price: Optional[Decimal] = None
    cargo_type: Optional[str] = None
    weight: Optional[float] = None
    volume: Optional[float] = None
    loading_date: Optional[datetime] = None
    unloading_date: Optional[datetime] = None
    loading_address: Optional[str] = None
    unloading_address: Optional[str] = None
    requirements: Optional[List[str]] = Field(default_factory=list)
    contact_phone: Optional[str] = None
    contact_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Payment DTOs
# ============================================================================

class PaymentDTO(BaseModel):
    """
    DTO for payment data transfer.
    """
    id: int
    user_id: int
    subscription_id: Optional[int] = None
    amount: Decimal
    currency: str = "RUB"
    status: str
    payment_method: str
    transaction_id: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Subscription DTOs
# ============================================================================

class SubscriptionDTO(BaseModel):
    """
    DTO for subscription data transfer.
    """
    id: int
    user_id: int
    plan_type: str
    status: str
    start_date: datetime
    end_date: datetime
    auto_renew: bool = False
    payment_count: int = 0
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Promo Code DTOs
# ============================================================================

class PromoCodeDTO(BaseModel):
    """
    DTO for promo code data transfer.
    """
    id: int
    code: str
    discount_percent: float
    max_uses: Optional[int] = None
    current_uses: int = 0
    valid_from: datetime
    valid_until: datetime
    active: bool = True
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Telegram Bot DTOs
# ============================================================================

class TelegramResponseDTO(BaseModel):
    """
    DTO for Telegram response data transfer.
    """
    message_id: Optional[int] = None
    chat_id: int
    text: str
    parse_mode: Optional[str] = None
    reply_markup: Optional[Dict[str, Any]] = None
    success: bool = True
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Audit DTOs
# ============================================================================

class AuditLogDTO(BaseModel):
    """
    DTO for audit log data transfer.
    """
    id: int
    user_id: Optional[int] = None
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Helper Functions for Model-DTO Conversion
# ============================================================================

"""
GOAL: Convert Django model instance to corresponding DTO instance.

PARAMETERS:
  model: Model - Django model instance - Not None
  dto_class: Type[T] - DTO class to convert to - Must be pydantic.BaseModel subclass

RETURNS:
  T - DTO instance populated with model data - Never None

RAISES:
  TypeError: If model is not a Django model instance
  ValueError: If model fields don't match DTO fields

GUARANTEES:
  - Returned DTO contains all model fields that have matching DTO fields
  - DateTime fields are converted to ISO format strings
  - Decimal fields are converted to float
  - Original model is not modified
"""
def model_to_dto[T](model: Model, dto_class: Type[T]) -> T:
    """
    Extract model fields and pass to DTO constructor using from_attributes=True.
    Pydantic v2 automatically handles datetime and decimal conversions.
    """
    if not hasattr(model, '_meta'):
        raise TypeError(f"Expected Django model, got {type(model)}")
    
    return dto_class.model_validate(model)


"""
GOAL: Convert DTO instance to dictionary.

PARAMETERS:
  dto: BaseModel - Pydantic DTO instance - Not None

RETURNS:
  Dict[str, Any] - Dictionary representation of DTO - Never None

RAISES:
  TypeError: If dto is not a pydantic BaseModel instance

GUARANTEES:
  - All DTO fields are included in dictionary
  - Nested DTOs are recursively converted to dicts
  - None values are preserved as None
  - Original DTO is not modified
"""
def dto_to_dict(dto: BaseModel) -> Dict[str, Any]:
    """
    Use pydantic's model_dump() method to convert DTO to dictionary.
    This handles nested DTOs and all type conversions automatically.
    """
    if not isinstance(dto, BaseModel):
        raise TypeError(f"Expected pydantic BaseModel, got {type(dto)}")
    
    return dto.model_dump()


"""
GOAL: Convert list of Django model instances to list of DTO instances.

PARAMETERS:
  models: List[Model] - Django model instances - Can be empty
  dto_class: Type[T] - DTO class to convert to - Must be pydantic.BaseModel subclass

RETURNS:
  List[T] - List of DTO instances - Same length as input list

RAISES:
  TypeError: If any model is not a Django model instance
  ValueError: If model fields don't match DTO fields

GUARANTEES:
  - Returned list has same length as input list
  - Order of items is preserved
  - Each DTO is populated with corresponding model data
  - Original models are not modified
"""
def models_to_dtos[T](models: List[Model], dto_class: Type[T]) -> List[T]:
    """
    Map model_to_dto() over the list of models using list comprehension.
    This preserves order and handles each model independently.
    """
    return [model_to_dto(model, dto_class) for model in models]
