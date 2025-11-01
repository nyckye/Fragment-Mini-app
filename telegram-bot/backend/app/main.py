import logging
import base64
from datetime import datetime
import hashlib
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request, Header, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.models import (
    CheckUsernameRequest, 
    UserProfileResponse,
    PurchaseRequest,
    PurchaseResponse,
    PriceCalculation,
    CalculatePriceRequest
)
from app.fragment.client import FragmentClient
from app.fragment.transaction import TonTransaction
from app.telegram_notifier import TelegramNotifier
from app.telegram_security import verify_telegram_webapp_data, extract_user_id
from app.middleware import SecurityMiddleware
from app.database import (
    init_database,
    log_purchase,
    log_username_check,
    get_user_purchases,
    get_statistics
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Глобальные клиенты
fragment_client: FragmentClient = None
ton_transaction: TonTransaction = None
telegram_notifier: TelegramNotifier = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager для инициализации клиентов"""
    global fragment_client, ton_transaction, telegram_notifier
    
    logger.info("🚀 Starting application...")
    
    # Инициализация базы данных
    init_database()
    logger.info("✅ Database initialized")
    
    # Инициализация Fragment клиента
    fragment_client = FragmentClient(
        fragment_hash=settings.fragment_hash,
        fragment_data=settings.fragment_data,
        fragment_address=settings.fragment_address,
        fragment_publickey=settings.fragment_publickey,
        fragment_wallets=settings.fragment_wallets
    )
    logger.info("✅ Fragment client initialized")
    
    # Инициализация TON транзакций
    ton_transaction = TonTransaction(
        api_key=settings.api_ton,
        mnemonic=settings.mnemonic_list
    )
    
    # Инициализируем кошелек
    wallet_initialized = await ton_transaction.initialize_wallet()
    if wallet_initialized:
        logger.info("✅ TON Wallet initialized")
        balance = await ton_transaction.get_balance()
        if balance:
            logger.info(f"💰 Wallet balance: {balance:.4f} TON")
    else:
        logger.error("❌ Failed to initialize TON wallet")
    
    # Инициализация Telegram уведомлений
    if settings.has_telegram_notifications:
        telegram_notifier = TelegramNotifier(
            bot_token=settings.bot_token,
            admin_id=settings.admin_telegram_id
        )
        logger.info(f"✅ Telegram notifications enabled (Admin ID: {settings.admin_telegram_id})")
    else:
        logger.warning("⚠️  Telegram notifications disabled (BOT_TOKEN or ADMIN_TELEGRAM_ID not set)")
    
    yield
    
    logger.info("👋 Shutting down application...")


# Создание FastAPI приложения
app = FastAPI(
    title="Telegram Stars Shop API",
    description="Backend API для покупки Telegram Stars",
    version="1.0.0",
    lifespan=lifespan
)

# Security middleware (добавляем ПЕРВЫМ)
app.add_middleware(SecurityMiddleware)

# CORS middleware - БЕЗОПАСНЫЙ
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)


# ============= UTILITY FUNCTIONS =============

# Хранилище обработанных транзакций
processed_transactions = set()

def calculate_price(amount: int, payment_method: str) -> PriceCalculation:
    """Рассчитывает цену в зависимости от способа оплаты"""
    if payment_method == 'rub':
        price = round(amount * 1.5, 2)
        currency = 'RUB'
    elif payment_method == 'ton':
        price = round(amount * 0.007, 4)
        currency = 'TON'
    elif payment_method == 'crypto':
        price = round(amount * 0.019, 3)
        currency = 'USDT'
    else:
        raise ValueError(f"Unknown payment method: {payment_method}")
    
    return PriceCalculation(
        amount_stars=amount,
        price=price,
        total_ton=price,  # Для совместимости с frontend
        currency=currency,
        payment_method=payment_method
    )




class TransactionVerifier:
    """Проверка TON транзакций"""
    
    @staticmethod
    def verify_transaction(tx_boc: str, expected_amount: int, username: str) -> dict:
        """Проверяет TON транзакцию"""
        try:
            if not tx_boc:
                return {"verified": False, "error": "BOC is empty"}
            
            tx_hash = hashlib.sha256(tx_boc.encode()).hexdigest()
            
            if tx_hash in processed_transactions:
                return {"verified": False, "error": "Already processed"}
            
            logger.info(f"✅ Transaction verified: {tx_hash[:16]}... for {username}")
            processed_transactions.add(tx_hash)
            
            return {"verified": True, "tx_hash": tx_hash, "amount": expected_amount}
        except Exception as e:
            logger.error(f"Transaction verification error: {e}")
            return {"verified": False, "error": str(e)}

# ============= API ENDPOINTS =============

@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {
        "message": "Telegram Stars Shop API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Публичная проверка здоровья API (без конфиденциальных данных)"""
    return {
        "status": "ok",
        "service": "Telegram Stars Shop API",
        "version": "1.0.0"
    }


@app.get("/tonconnect-manifest.json")
async def get_tonconnect_manifest():
    """TON Connect manifest для подключения кошелька"""
    return JSONResponse(
        content={
            "url": "https://webstorstars.duckdns.org",
            "name": "Telegram Stars Shop",
            "iconUrl": "https://webstorstars.duckdns.org/icon.png",
            "termsOfUseUrl": "https://webstorstars.duckdns.org/",
            "privacyPolicyUrl": "https://webstorstars.duckdns.org/"
        },
        headers={
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        }
    )


@app.get("/admin/health")
async def admin_health_check(admin_token: str = Header(None, alias="X-Admin-Token")):
    """Админская проверка здоровья с балансом (требует токен)"""
    # Проверяем админский токен
    if not admin_token or admin_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    
    wallet_balance = None
    if ton_transaction and ton_transaction.wallet:
        wallet_balance = await ton_transaction.get_balance()
    
    return {
        "status": "healthy",
        "fragment_client": fragment_client is not None,
        "ton_wallet": ton_transaction is not None and ton_transaction.wallet is not None,
        "wallet_balance": wallet_balance,
        "telegram_notifier": telegram_notifier is not None
    }


@app.post("/api/check_user", response_model=UserProfileResponse)
async def check_user(request: CheckUsernameRequest, http_request: Request):
    """Проверяет существование пользователя через Fragment API"""
    try:
        client_ip = http_request.client.host if http_request.client else "unknown"
        user_agent = http_request.headers.get("user-agent", "unknown")
        
        logger.info(f"🔍 Checking user: {request.username} from {client_ip}")
        
        user_profile = await fragment_client.fetch_user_profile(request.username)
        
        # Логируем в БД
        log_username_check(
            username_checked=request.username,
            found=user_profile is not None,
            ip_address=client_ip,
            user_agent=user_agent
        )
        
        if user_profile:
            return UserProfileResponse(
                success=True,
                username=user_profile.get("username"),
                user_id=user_profile.get("user_id"),
                first_name=user_profile.get("first_name"),
                last_name=user_profile.get("last_name"),
                photo_url=user_profile.get("photo_url"),
                is_premium=user_profile.get("is_premium", False)
            )
        else:
            return UserProfileResponse(
                success=False,
                username=request.username,
                error="User not found in Fragment"
            )
    
    except Exception as e:
        logger.error(f"Error checking user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/calculate_price", response_model=PriceCalculation)
async def calculate_price_endpoint(request: CalculatePriceRequest):
    """Рассчитывает цену для покупки Stars"""
    try:
        if request.amount < settings.min_stars or request.amount > settings.max_stars:
            raise HTTPException(
                status_code=400,
                detail=f"Amount must be between {settings.min_stars} and {settings.max_stars}"
            )
        
        price_calc = calculate_price(request.amount, request.payment_method)
        return price_calc
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculating price: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/purchase", response_model=PurchaseResponse)
async def purchase_stars(request: PurchaseRequest, http_request: Request):
    """Обрабатывает покупку Telegram Stars"""
    try:
        client_ip = http_request.client.host if http_request.client else "unknown"
        user_agent = http_request.headers.get("user-agent", "unknown")
        
        logger.info(f"🛒 Purchase request: {request.amount} Stars → @{request.username} from {client_ip}")
        
        # БЕЗОПАСНОСТЬ: Проверяем подпись Telegram WebApp
        if request.init_data and settings.bot_token:
            verified_data = verify_telegram_webapp_data(request.init_data, settings.bot_token)
            
            if not verified_data:
                logger.error("❌ Invalid Telegram WebApp signature - possible fake request!")
                raise HTTPException(
                    status_code=403,
                    detail="Invalid Telegram WebApp signature"
                )
            
            # Проверяем что buyer.id совпадает с verified user_id
            if request.buyer and request.buyer.id:
                verified_user_id = verified_data.get('user', {}).get('id')
                if verified_user_id != request.buyer.id:
                    logger.error(f"❌ User ID mismatch: {request.buyer.id} != {verified_user_id}")
                    raise HTTPException(
                        status_code=403,
                        detail="User ID mismatch"
                    )
                logger.info(f"✅ Telegram signature verified for user {verified_user_id}")
        else:
            # Если нет init_data - логируем предупреждение
            if request.buyer:
                logger.warning("⚠️ Purchase without init_data verification - opened directly from web")
        
        # Валидация
        if request.amount < settings.min_stars or request.amount > settings.max_stars:
            raise HTTPException(
                status_code=400,
                detail=f"Amount must be between {settings.min_stars} and {settings.max_stars}"
            )
        
        # Проверяем пользователя
        logger.info("1️⃣ Checking recipient in Fragment...")
        recipient = await fragment_client.fetch_recipient(request.username)
        
        if not recipient:
            return PurchaseResponse(
                success=False,
                error=f"User @{request.username} not found in Fragment"
            )
        
        logger.info(f"✅ Recipient found: {recipient}")
        
        # Получаем request ID
        logger.info("2️⃣ Getting request ID from Fragment...")
        req_id = await fragment_client.fetch_req_id(recipient, request.amount)
        
        if not req_id:
            return PurchaseResponse(
                success=False,
                error="Failed to initialize purchase request"
            )
        
        logger.info(f"✅ Request ID: {req_id}")
        
        # Получаем параметры транзакции
        logger.info("3️⃣ Fetching transaction parameters...")
        address, amount_nano, payload = await fragment_client.fetch_buy_link(
            recipient, req_id, request.amount
        )
        
        if not address or not amount_nano or not payload:
            return PurchaseResponse(
                success=False,
                error="Failed to get transaction parameters"
            )
        
        # Конвертируем amount из nano в TON
        amount_ton = float(amount_nano) / 1_000_000_000
        logger.info(f"✅ Transaction params: {amount_ton:.4f} TON → {address}")
        
        # Отправляем транзакцию
        logger.info("4️⃣ Sending TON transaction...")
        success, tx_hash, error = await ton_transaction.send_ton_transaction(
            recipient=address,
            amount_ton=amount_ton,
            payload=payload,
            stars=request.amount
        )
        
        if not success or not tx_hash:
            return PurchaseResponse(
                success=False,
                error=error or "Transaction failed"
            )
        
        logger.info(f"✅ Transaction sent successfully!")
        
        # tx_hash может быть bytes или str
        if isinstance(tx_hash, str):
            tx_hash_hex = tx_hash
        else:
            tx_hash_hex = tx_hash.hex()
        
        # TON Viewer принимает просто hex, без base64
        ton_viewer_link = f"https://tonviewer.com/transaction/{tx_hash_hex}"
        
        logger.info(f"📊 TX Hash (hex): {tx_hash_hex}")
        logger.info(f"🔗 TON Viewer: {ton_viewer_link}")
        
        # Отправляем уведомления в Telegram (если настроено)
        if telegram_notifier:
            try:
                buyer_id = request.buyer.id if request.buyer else None
                buyer_username = request.buyer.username if request.buyer else None
                buyer_first_name = request.buyer.first_name if request.buyer else "User"
                
                logger.info(f"📬 Preparing notifications - Buyer ID: {buyer_id}, Username: {buyer_username}")
                
                # Уведомление админу
                await telegram_notifier.notify_purchase_success(
                    buyer_id=buyer_id,
                    buyer_username=buyer_username,
                    buyer_first_name=buyer_first_name,
                    recipient_username=request.username,
                    amount=request.amount,
                    tx_hash=tx_hash_hex,
                    ton_viewer_link=ton_viewer_link
                )
                
                # Уведомление покупателю
                if buyer_id:
                    await telegram_notifier.notify_user_purchase(
                        user_id=buyer_id,
                        recipient_username=request.username,
                        amount=request.amount,
                        tx_hash=tx_hash_hex,
                        ton_viewer_link=ton_viewer_link,
                        web_app_url=settings.web_app_url if hasattr(settings, 'web_app_url') else None
                    )
                    
                    # Сохраняем покупку в БД
                    log_purchase(
                        user_id=buyer_id,
                        recipient_username=request.username,
                        amount=request.amount,
                        payment_method=request.payment_method,
                        tx_hash=tx_hash_hex,
                        ton_viewer_link=ton_viewer_link,
                        ip_address=client_ip,
                        username=request.buyer.username if request.buyer else None,
                        first_name=request.buyer.first_name if request.buyer else None,
                        user_agent=user_agent
                    )
                    logger.info(f"💾 Purchase saved to database for user {buyer_id}")
                    
                else:
                    logger.warning("⚠️ Buyer ID not provided - user notification skipped. Make sure to open Mini-App through Telegram bot.")
                    
            except Exception as e:
                logger.error(f"Failed to send Telegram notification: {e}")
                # Продолжаем даже если уведомление не отправилось
        
        return PurchaseResponse(
            success=True,
            tx_hash=tx_hash_hex,
            amount=request.amount,
            recipient=request.username,
            ton_viewer_link=ton_viewer_link
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Purchase error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/wallet/balance")
async def get_wallet_balance():
    """Получает баланс TON кошелька"""
    try:
        if not ton_transaction or not ton_transaction.wallet:
            raise HTTPException(status_code=503, detail="Wallet not initialized")
        
        balance = await ton_transaction.get_balance()
        
        if balance is None:
            raise HTTPException(status_code=500, detail="Failed to get balance")
        
        return {
            "success": True,
            "balance": balance,
            "currency": "TON"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/user/purchases/{user_id}")
async def get_user_purchases_endpoint(user_id: int):
    """Получить историю покупок пользователя из БД"""
    try:
        purchases = get_user_purchases(user_id, limit=50)
        
        logger.info(f"📋 Fetching purchase history for user {user_id}: {len(purchases)} purchases")
        
        # Преобразуем формат для фронтенда
        formatted_purchases = []
        for p in purchases:
            formatted_purchases.append({
                "recipient_username": p['recipient_username'],
                "amount": p['amount'],
                "tx_hash": p['tx_hash'],
                "ton_viewer_link": p['ton_viewer_link'],
                "timestamp": p['timestamp']
            })
        
        return {
            "success": True,
            "user_id": user_id,
            "purchases": formatted_purchases,
            "total": len(formatted_purchases)
        }
    
    except Exception as e:
        logger.error(f"Error fetching purchases for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/statistics")
async def get_statistics_endpoint(admin_token: str = Header(None, alias="X-Admin-Token")):
    """Получить статистику (требует админский токен)"""
    # Проверяем админский токен
    if not admin_token or admin_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    
    try:
        stats = get_statistics()
        logger.info("📊 Admin accessed statistics")
        return {
            "success": True,
            "statistics": stats
        }
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
