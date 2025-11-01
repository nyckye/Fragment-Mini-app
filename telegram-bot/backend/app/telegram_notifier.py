import httpx
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TelegramNotifier:
    
    def __init__(self, bot_token: str, admin_id: int):
        self.bot_token = bot_token
        self.admin_id = admin_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    async def send_message(self, chat_id: int, text: str, parse_mode: str = "HTML", reply_markup: dict = None):
        try:
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }
            
            if reply_markup:
                payload["reply_markup"] = reply_markup
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/sendMessage",
                    json=payload
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Message sent to {chat_id}")
                    return True
                else:
                    logger.error(f"❌ Failed to send message: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error sending message: {e}")
            return False
    
    async def notify_purchase_success(
        self,
        buyer_id: Optional[int],
        buyer_username: Optional[str],
        buyer_first_name: Optional[str],
        recipient_username: str,
        amount: int,
        tx_hash: str,
        ton_viewer_link: str
    ):
        
        # Формируем информацию о покупателе
        if buyer_first_name:
            buyer_info = buyer_first_name
        elif buyer_username:
            buyer_info = f"@{buyer_username}"
        else:
            buyer_info = "Неизвестный пользователь"
        
        # Уведомление админу
        admin_message = (
            "🔔 <b>НОВАЯ ПОКУПКА STARS</b>\n\n"
            f"👤 Покупатель: {buyer_info}\n"
        )
        
        if buyer_id:
            admin_message += f"🆔 ID: <code>{buyer_id}</code>\n"
        
        if buyer_username:
            admin_message += f"📧 Username: @{buyer_username}\n"
        
        admin_message += (
            f"\n🎯 Получатель: <code>@{recipient_username}</code>\n"
            f"⭐ Количество: <b>{amount} Stars</b>\n\n"
            f"🔗 TX Hash:\n<code>{tx_hash}</code>\n\n"
            f"<a href='{ton_viewer_link}'>📊 Посмотреть в TON Viewer</a>\n\n"
            f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # Отправляем админу
        success = await self.send_message(self.admin_id, admin_message)
        
        if success:
            logger.info(f"✅ Admin notified about purchase: {amount} Stars → @{recipient_username}")
        else:
            logger.error(f"❌ Failed to notify admin")
        
        return success
    
    async def notify_user_purchase(
        self,
        user_id: int,
        recipient_username: str,
        amount: int,
        tx_hash: str,
        ton_viewer_link: str,
        web_app_url: str = None
    ):
        
        user_message = (
            "✅ <b>Покупка успешно завершена!</b>\n\n"
            f"👤 Получатель: <code>@{recipient_username}</code>\n"
            f"⭐ Количество: <b>{amount} Stars</b>\n"
            f"🔗 TX Hash: <code>{tx_hash[:16]}...</code>\n\n"
            f"<a href='{ton_viewer_link}'>📊 Посмотреть транзакцию</a>\n\n"
            "Спасибо за покупку! 🎉"
        )
        
        # Создаем кнопки
        reply_markup = None
        if web_app_url:
            reply_markup = {
                "inline_keyboard": [
                    [
                        {
                            "text": "🛍️ Открыть магазин",
                            "web_app": {"url": web_app_url}
                        }
                    ],
                    [
                        {
                            "text": "💬 Поддержка",
                            "url": "https://t.me/your_support"  # Замени на свой
                        }
                    ]
                ]
            }
        
        # Отправляем пользователю
        success = await self.send_message(user_id, user_message, reply_markup=reply_markup)
        
        if success:
            logger.info(f"✅ User {user_id} notified about purchase")
        else:
            logger.error(f"❌ Failed to notify user {user_id}")
        
        return success
