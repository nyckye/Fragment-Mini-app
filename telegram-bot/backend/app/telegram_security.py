import hmac
import hashlib
import json
from urllib.parse import parse_qsl
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


def verify_telegram_webapp_data(init_data: str, bot_token: str) -> Optional[Dict]:
    """
    Проверяет подлинность данных от Telegram WebApp
    
    Args:
        init_data: строка initData от Telegram WebApp
        bot_token: токен бота
        
    Returns:
        Dict с данными пользователя если проверка успешна, иначе None
    """
    try:
        # Парсим initData
        parsed_data = dict(parse_qsl(init_data))
        
        # Проверяем наличие hash
        received_hash = parsed_data.pop('hash', None)
        if not received_hash:
            logger.error("❌ No hash in initData")
            return None
        
        # Создаем data_check_string
        data_check_arr = [f"{k}={v}" for k, v in sorted(parsed_data.items())]
        data_check_string = '\n'.join(data_check_arr)
        
        # Вычисляем secret_key
        secret_key = hmac.new(
            key=b"WebAppData",
            msg=bot_token.encode(),
            digestmod=hashlib.sha256
        ).digest()
        
        # Вычисляем hash
        calculated_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        # Сравниваем хэши
        if calculated_hash != received_hash:
            logger.error("❌ Hash mismatch - possible fake request")
            logger.error(f"   Expected: {calculated_hash}")
            logger.error(f"   Received: {received_hash}")
            return None
        
        # Парсим user данные
        user_data = None
        if 'user' in parsed_data:
            try:
                user_data = json.loads(parsed_data['user'])
            except json.JSONDecodeError:
                logger.error("❌ Failed to parse user data")
                return None
        
        logger.info("✅ Telegram WebApp signature verified")
        return {
            'user': user_data,
            'auth_date': parsed_data.get('auth_date'),
            'query_id': parsed_data.get('query_id')
        }
        
    except Exception as e:
        logger.error(f"❌ Error verifying Telegram data: {e}")
        return None


def extract_user_id(init_data: str, bot_token: str) -> Optional[int]:
    """
    Извлекает и проверяет user_id из initData
    
    Returns:
        user_id если проверка успешна, иначе None
    """
    verified_data = verify_telegram_webapp_data(init_data, bot_token)
    
    if not verified_data or not verified_data.get('user'):
        return None
    
    return verified_data['user'].get('id')
