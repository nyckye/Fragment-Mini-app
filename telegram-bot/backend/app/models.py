from pydantic import BaseModel, Field, validator
from typing import Optional, Literal


#  REQUEST MODELS

class BuyerInfo(BaseModel):
    """Информация о покупателе"""
    id: Optional[int] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class CheckUsernameRequest(BaseModel):
    """Запрос на проверку username"""
    username: str = Field(..., min_length=1, max_length=100)
    
    @validator('username')
    def validate_username(cls, v):
        # Убираем @ если есть
        v = v.lstrip('@')
        if not v:
            raise ValueError('Username cannot be empty')
        return v


class CalculatePriceRequest(BaseModel):
    """Запрос на расчет цены"""
    amount: int = Field(..., ge=50, le=1000000, description="Количество Stars")
    payment_method: Literal['ton', 'crypto', 'rub'] = Field(default='ton', description="Способ оплаты")


class PurchaseRequest(BaseModel):
    """Запрос на покупку Stars"""
    username: str = Field(..., description="Username получателя (без @)")
    amount: int = Field(..., ge=50, le=1000000, description="Количество Stars")
    payment_method: Literal['ton', 'crypto', 'rub'] = Field(..., description="Способ оплаты")
    tx_boc: Optional[str] = Field(None, description="BOC транзакции для TON оплаты")
    buyer: Optional[BuyerInfo] = Field(None, description="Информация о покупателе из Telegram WebApp")
    init_data: Optional[str] = Field(None, description="Telegram WebApp initData для проверки подписи")
    
    @validator('username')
    def validate_username(cls, v):
        v = v.lstrip('@')
        if not v:
            raise ValueError('Username cannot be empty')
        return v


# ============= RESPONSE MODELS =============

class UserProfileResponse(BaseModel):
    """Ответ с профилем пользователя"""
    success: bool
    username: str
    user_id: Optional[int] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    photo_url: Optional[str] = None
    is_premium: Optional[bool] = None
    error: Optional[str] = None


class PriceCalculation(BaseModel):
    """Расчет цены"""
    amount_stars: int
    price: float
    total_ton: float  # Добавлено для совместимости с frontend
    currency: str
    payment_method: str


class PurchaseResponse(BaseModel):
    """Ответ при покупке"""
    success: bool
    tx_hash: Optional[str] = None
    amount: Optional[int] = None
    recipient: Optional[str] = None
    ton_viewer_link: Optional[str] = None
    error: Optional[str] = None
