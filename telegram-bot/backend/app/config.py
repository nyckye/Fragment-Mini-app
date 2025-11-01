from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    
    # API Configuration
    api_ton: str
    
    # Fragment Configuration
    fragment_hash: str
    fragment_publickey: str
    fragment_wallets: str
    fragment_address: str
    
    # Fragment Cookies
    stel_ssid: str
    stel_dt: str
    stel_ton_token: str
    stel_token: str
    
    # TON Wallet Mnemonic
    mnemonic: str  # Comma-separated words
    
    # TON Wallet Address (куда приходят платежи)
    wallet_address: str = "UQB-09E7MDYhYmkuubv0gsOL0Zpll4MwbuKfu5TB4XOG_dn3"

    
    # Telegram Bot (для уведомлений)
    bot_token: str = ""
    admin_telegram_id: int = 0
    admin_token: str = ""  # Токен для доступа к /admin/* endpoints
    
    # Web App URL (для кнопок)
    web_app_url: str = "https://webstorstars.duckdns.org"
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # ТОЛЬКО ваш домен!
    allowed_origins: str = "https://webstorstars.duckdns.org"
    
    # Limits
    min_stars: int = 50
    max_stars: int = 1000000
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    @property
    def mnemonic_list(self) -> List[str]:
        return [word.strip() for word in self.mnemonic.split(",")]
    
    @property
    def fragment_data(self) -> dict:
        return {
            'stel_ssid': self.stel_ssid,
            'stel_dt': self.stel_dt,
            'stel_ton_token': self.stel_ton_token,
            'stel_token': self.stel_token,
        }
    
    @property
    def origins_list(self) -> List[str]:
        if self.allowed_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.allowed_origins.split(",")]
    
    @property
    def has_telegram_notifications(self) -> bool:
        return bool(self.bot_token and self.admin_telegram_id)


# Создаем глобальный экземпляр настроек
settings = Settings()
