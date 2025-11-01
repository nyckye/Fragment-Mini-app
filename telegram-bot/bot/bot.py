import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, List

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, 
    CallbackQuery,
    WebAppInfo, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)
from aiogram.filters import Command
from aiogram.enums import ParseMode

import config

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# Хранилище покупок пользователей (в продакшене используй БД)
user_purchases: Dict[int, List[Dict]] = {}


# KEYBOARDS

def get_main_keyboard(user_id: int, has_purchases: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text="🛍️ Открыть магазин",
                web_app=WebAppInfo(url=config.WEB_APP_URL)
            )
        ],
        [
            InlineKeyboardButton(
                text="📢 Наш канал",
                url="https://t.me/your_channel"
            ),
            InlineKeyboardButton(
                text="📖 Инструкция",
                url="https://t.me/your_instruction"
            )
        ]
    ]
    
    # Добавляем кнопку истории если есть покупки
    if has_purchases:
        buttons.append([
            InlineKeyboardButton(
                text="📋 Последние покупки",
                callback_data="show_history"
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_after_purchase_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛍️ Открыть магазин",
                    web_app=WebAppInfo(url=config.WEB_APP_URL)
                )
            ],
            [
                InlineKeyboardButton(
                    text="💬 Поддержка",
                    url="https://t.me/your_support"  # Замени на аккаунт поддержки
                )
            ]
        ]
    )
    return keyboard


def get_history_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data="back_to_main"
                )
            ]
        ]
    )
    return keyboard


# HANDLERS 

@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    has_purchases = user_id in user_purchases and len(user_purchases[user_id]) > 0
    
    welcome_text = (
        f"👋 <b>Привет, {message.from_user.first_name}!</b>\n\n"
        "🌟 <b>Telegram Stars Shop</b> — быстрая и безопасная покупка Telegram Stars!\n\n"
        "💎 <b>Что можно сделать:</b>\n"
        "• Купить Stars для любого пользователя Telegram\n"
        "• Оплатить через TON, криптовалюту или RUB\n"
        "• Получить Stars моментально после оплаты\n\n"
        "🔒 <b>Безопасность:</b>\n"
        "Все транзакции проходят через TON блокчейн\n\n"
        "⭐ <b>Минимум:</b> 50 Stars\n"
        "💰 <b>Максимум:</b> 1,000,000 Stars\n\n"
        "Нажмите кнопку ниже чтобы начать! 👇"
    )
    
    sent_message = await message.answer(
        welcome_text,
        reply_markup=get_main_keyboard(user_id, has_purchases),
        parse_mode=ParseMode.HTML
    )
    
    # Закрепляем первое сообщение
    try:
        await bot.pin_chat_message(
            chat_id=message.chat.id,
            message_id=sent_message.message_id,
            disable_notification=True
        )
        logger.info(f"✅ Message pinned for user {user_id}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to pin message: {e}")


@dp.message(F.web_app_data)
async def handle_web_app_data(message: Message):
    try:
        data = json.loads(message.web_app_data.data)
        
        if data.get('action') == 'purchase_completed':
            username = data.get('username')
            amount = data.get('amount')
            tx_hash = data.get('tx_hash')
            ton_viewer_link = data.get('ton_viewer_link')
            
            user_id = message.from_user.id
            
            # Сохраняем покупку в историю
            if user_id not in user_purchases:
                user_purchases[user_id] = []
            
            purchase_record = {
                'username': username,
                'amount': amount,
                'tx_hash': tx_hash,
                'ton_viewer_link': ton_viewer_link,
                'timestamp': datetime.now().isoformat(),
                'buyer': {
                    'id': user_id,
                    'username': message.from_user.username,
                    'first_name': message.from_user.first_name
                }
            }
            user_purchases[user_id].append(purchase_record)
            
            # Уведомление пользователю
            success_text = (
                "✅ <b>Покупка успешно завершена!</b>\n\n"
                f"👤 Получатель: <code>@{username}</code>\n"
                f"⭐ Количество: <b>{amount} Stars</b>\n"
                f"🔗 TX Hash: <code>{tx_hash[:16]}...</code>\n\n"
                f"<a href='{ton_viewer_link}'>📊 Посмотреть транзакцию</a>\n\n"
                "Спасибо за покупку! 🎉"
            )
            
            await message.answer(
                success_text,
                reply_markup=get_after_purchase_keyboard(),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            
            # Уведомление админу
            if config.ADMIN_ID:
                admin_text = (
                    "🔔 <b>НОВАЯ ПОКУПКА STARS</b>\n\n"
                    f"👤 От: {message.from_user.mention_html()}\n"
                    f"🆔 ID: <code>{user_id}</code>\n"
                    f"📧 Username: @{message.from_user.username or 'нет'}\n\n"
                    f"🎯 Получатель: <code>@{username}</code>\n"
                    f"⭐ Количество: <b>{amount} Stars</b>\n\n"
                    f"🔗 TX Hash:\n<code>{tx_hash}</code>\n\n"
                    f"<a href='{ton_viewer_link}'>📊 TON Viewer</a>\n\n"
                    f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                
                try:
                    await bot.send_message(
                        chat_id=config.ADMIN_ID,
                        text=admin_text,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.error(f"Failed to notify admin: {e}")
            
            logger.info(f"✅ Purchase recorded for user {user_id}: {amount} Stars → @{username}")
            
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON from web app: {message.web_app_data.data}")
        await message.answer("❌ Ошибка обработки данных")
    except Exception as e:
        logger.error(f"Error handling web app data: {e}")
        await message.answer("❌ Произошла ошибка")


@dp.callback_query(F.data == "show_history")
async def show_purchase_history(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in user_purchases or not user_purchases[user_id]:
        await callback.answer("У вас пока нет покупок", show_alert=True)
        return
    
    # Берем последние 10 покупок
    purchases = user_purchases[user_id][-10:]
    purchases.reverse()  # Показываем сначала самые новые
    
    history_text = "📋 <b>Последние покупки:</b>\n\n"
    
    for i, purchase in enumerate(purchases, 1):
        timestamp = datetime.fromisoformat(purchase['timestamp'])
        date_str = timestamp.strftime('%d.%m.%Y %H:%M')
        
        history_text += (
            f"<b>{i}.</b> {date_str}\n"
            f"├ 👤 Получатель: <code>@{purchase['username']}</code>\n"
            f"├ ⭐ Количество: <b>{purchase['amount']} Stars</b>\n"
            f"└ 🔗 <a href='{purchase['ton_viewer_link']}'>Посмотреть транзакцию</a>\n\n"
        )
    
    history_text += f"<i>Всего покупок: {len(user_purchases[user_id])}</i>"
    
    # Редактируем сообщение
    await callback.message.edit_text(
        history_text,
        reply_markup=get_history_keyboard(),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )
    await callback.answer()


@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    """Вернуться в главное меню"""
    user_id = callback.from_user.id
    has_purchases = user_id in user_purchases and len(user_purchases[user_id]) > 0
    
    welcome_text = (
        f"👋 <b>Привет, {callback.from_user.first_name}!</b>\n\n"
        "🌟 <b>Telegram Stars Shop</b> — быстрая и безопасная покупка Telegram Stars!\n\n"
        "💎 <b>Что можно сделать:</b>\n"
        "• Купить Stars для любого пользователя Telegram\n"
        "• Оплатить через TON, криптовалюту или RUB\n"
        "• Получить Stars моментально после оплаты\n\n"
        "🔒 <b>Безопасность:</b>\n"
        "Все транзакции проходят через TON блокчейн\n\n"
        "⭐ <b>Минимум:</b> 50 Stars\n"
        "💰 <b>Максимум:</b> 1,000,000 Stars\n\n"
        "Нажмите кнопку ниже чтобы начать! 👇"
    )
    
    # Редактируем сообщение
    await callback.message.edit_text(
        welcome_text,
        reply_markup=get_main_keyboard(user_id, has_purchases),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


# MAIN 

async def main():
    logger.info("🚀 Starting bot...")
    
    try:
        # Удаляем вебхук если есть
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook deleted")
        
        # Запускаем polling
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Error: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
