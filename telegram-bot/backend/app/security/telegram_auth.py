import hmac
import hashlib
import json
import logging
from typing import Optional, Dict
from urllib.parse import unquote, parse_qsl

logger = logging.getLogger(__name__)


class TelegramAuth:
    
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        # Создаем secret_key из bot_token по алгоритму Telegram
        self.secret_key = hmac.new(
            key=b"WebAppData",
            msg=bot_token.encode(),
            digestmod=hashlib.sha256
        ).digest()
    
    def verify_init_data(self, init_data: str) -> tuple[bool, Optional[Dict]]:
        """
        Проверяет подпись initData от Telegram WebApp
        
        Returns:
            (is_valid, user_data) - True если подпись валидна + данные пользователя
        """
        try:
            # Парсим init_data
            parsed_data = dict(parse_qsl(init_data))
            
            # Извлекаем hash (это подпись от Telegram)
            received_hash = parsed_data.pop('hash', None)
            if not received_hash:
                logger.error("❌ No hash in initData")
                return False, None
            
            # Сортируем оставшиеся параметры по ключу
            data_check_string = '\n'.join(
                f"{k}={v}" for k, v in sorted(parsed_data.items())
            )
            
            # Вычисляем HMAC-SHA256
            calculated_hash = hmac.new(
                key=self.secret_key,
                msg=data_check_string.encode(),
                digestmod=hashlib.sha256
            ).hexdigest()
            
            # Сравниваем хэши
            if calculated_hash != received_hash:
                logger.error("❌ Invalid hash - possible forgery attempt")
                return False, None
            
            # Извлекаем данные пользователя
            user_json = parsed_data.get('user')
            if not user_json:
                logger.error("❌ No user data in initData")
                return False, None
            
            user_data = json.loads(unquote(user_json))
            
            logger.info(f"✅ Valid initData for user {user_data.get('id')}")
            return True, user_data
            
        except Exception as e:
            logger.error(f"❌ Error verifying initData: {e}")
            return False, None
    
    def extract_user_from_init_data(self, init_data: str) -> Optional[Dict]:
        """
        Упрощенная функция - просто извлекает пользователя
        Используй только ПОСЛЕ verify_init_data!
        """
        try:
            parsed_data = dict(parse_qsl(init_data))
            user_json = parsed_data.get('user')
            if user_json:
                return json.loads(unquote(user_json))
        except Exception as e:
            logger.error(f"Error extracting user: {e}")
        return None
