import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict
from contextlib import contextmanager
import json

logger = logging.getLogger(__name__)

DATABASE_PATH = "telegram_stars.db"


@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Возвращаем результаты как dict
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        conn.close()


def init_database():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Таблица для логов действий пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id INTEGER,
                username TEXT,
                action TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                method TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                user_agent TEXT,
                request_data TEXT,
                response_status INTEGER,
                response_time REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица для истории покупок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                recipient_username TEXT NOT NULL,
                amount INTEGER NOT NULL,
                payment_method TEXT NOT NULL,
                tx_hash TEXT NOT NULL,
                ton_viewer_link TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                timestamp TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица для подозрительной активности
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS suspicious_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                user_agent TEXT,
                endpoint TEXT NOT NULL,
                reason TEXT NOT NULL,
                request_data TEXT,
                blocked BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица для проверок username
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS username_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username_checked TEXT NOT NULL,
                found BOOLEAN NOT NULL,
                ip_address TEXT NOT NULL,
                user_agent TEXT,
                timestamp TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Индексы для быстрого поиска
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON user_activity_logs(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ip ON user_activity_logs(ip_address)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_purchases_user ON purchases(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_suspicious_ip ON suspicious_activity(ip_address)')
        
        conn.commit()
        logger.info("✅ Database initialized successfully")


def log_user_activity(
    action: str,
    endpoint: str,
    method: str,
    ip_address: str,
    user_agent: Optional[str] = None,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    request_data: Optional[Dict] = None,
    response_status: Optional[int] = None,
    response_time: Optional[float] = None
):
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_activity_logs 
                (timestamp, user_id, username, action, endpoint, method, 
                 ip_address, user_agent, request_data, response_status, response_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now().isoformat(),
                user_id,
                username,
                action,
                endpoint,
                method,
                ip_address,
                user_agent,
                json.dumps(request_data) if request_data else None,
                response_status,
                response_time
            ))
            logger.info(f"📝 Logged: {action} from {ip_address}")
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")


def log_purchase(
    user_id: int,
    recipient_username: str,
    amount: int,
    payment_method: str,
    tx_hash: str,
    ton_viewer_link: str,
    ip_address: str,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    user_agent: Optional[str] = None
):
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO purchases 
                (user_id, username, first_name, recipient_username, amount, 
                 payment_method, tx_hash, ton_viewer_link, ip_address, user_agent, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                username,
                first_name,
                recipient_username,
                amount,
                payment_method,
                tx_hash,
                ton_viewer_link,
                ip_address,
                user_agent,
                datetime.now().isoformat()
            ))
            logger.info(f"💾 Purchase saved: {amount} Stars → @{recipient_username} (User {user_id})")
    except Exception as e:
        logger.error(f"Failed to save purchase: {e}")


def log_suspicious_activity(
    ip_address: str,
    endpoint: str,
    reason: str,
    user_agent: Optional[str] = None,
    request_data: Optional[Dict] = None,
    blocked: bool = False
):
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO suspicious_activity 
                (timestamp, ip_address, user_agent, endpoint, reason, request_data, blocked)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now().isoformat(),
                ip_address,
                user_agent,
                endpoint,
                reason,
                json.dumps(request_data) if request_data else None,
                blocked
            ))
            logger.warning(f"⚠️ Suspicious activity logged: {reason} from {ip_address}")
    except Exception as e:
        logger.error(f"Failed to log suspicious activity: {e}")


def log_username_check(
    username_checked: str,
    found: bool,
    ip_address: str,
    user_agent: Optional[str] = None,
    user_id: Optional[int] = None
):
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO username_checks 
                (user_id, username_checked, found, ip_address, user_agent, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                username_checked,
                found,
                ip_address,
                user_agent,
                datetime.now().isoformat()
            ))
    except Exception as e:
        logger.error(f"Failed to log username check: {e}")


def get_user_purchases(user_id: int, limit: int = 50) -> List[Dict]:
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM purchases 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (user_id, limit))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get purchases: {e}")
        return []


def get_user_activity(user_id: int = None, ip_address: str = None, limit: int = 100) -> List[Dict]:
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            if user_id:
                cursor.execute('''
                    SELECT * FROM user_activity_logs 
                    WHERE user_id = ? 
                    ORDER BY created_at DESC 
                    LIMIT ?
                ''', (user_id, limit))
            elif ip_address:
                cursor.execute('''
                    SELECT * FROM user_activity_logs 
                    WHERE ip_address = ? 
                    ORDER BY created_at DESC 
                    LIMIT ?
                ''', (ip_address, limit))
            else:
                cursor.execute('''
                    SELECT * FROM user_activity_logs 
                    ORDER BY created_at DESC 
                    LIMIT ?
                ''', (limit,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get activity: {e}")
        return []


def get_suspicious_activity(limit: int = 100) -> List[Dict]:
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM suspicious_activity 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get suspicious activity: {e}")
        return []


def get_statistics() -> Dict:
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Общее количество покупок
            cursor.execute('SELECT COUNT(*) as total FROM purchases')
            total_purchases = cursor.fetchone()['total']
            
            # Общая сумма Stars
            cursor.execute('SELECT SUM(amount) as total FROM purchases')
            total_stars = cursor.fetchone()['total'] or 0
            
            # Уникальные пользователи
            cursor.execute('SELECT COUNT(DISTINCT user_id) as total FROM purchases')
            unique_users = cursor.fetchone()['total']
            
            # Подозрительная активность
            cursor.execute('SELECT COUNT(*) as total FROM suspicious_activity')
            suspicious_count = cursor.fetchone()['total']
            
            # Проверки username
            cursor.execute('SELECT COUNT(*) as total FROM username_checks')
            username_checks = cursor.fetchone()['total']
            
            return {
                'total_purchases': total_purchases,
                'total_stars_sold': total_stars,
                'unique_users': unique_users,
                'suspicious_activity_count': suspicious_count,
                'username_checks_count': username_checks
            }
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        return {}
