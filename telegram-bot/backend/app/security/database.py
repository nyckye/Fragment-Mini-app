import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path

logger = logging.getLogger(__name__)


class Database:
    
    def __init__(self, db_path: str = "data/transactions.db"):
        self.db_path = db_path
        # Создаем директорию если не существует
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._create_tables()
    
    def _get_connection(self):
        """Создает подключение к БД"""
        return sqlite3.connect(self.db_path)
    
    def _create_tables(self):
        """Создает таблицы если их нет"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Таблица транзакций
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idempotency_key TEXT UNIQUE NOT NULL,
                buyer_telegram_id INTEGER,
                buyer_username TEXT,
                buyer_first_name TEXT,
                recipient_username TEXT NOT NULL,
                amount_stars INTEGER NOT NULL,
                payment_method TEXT NOT NULL,
                tx_hash TEXT,
                ton_viewer_link TEXT,
                status TEXT NOT NULL,
                error_message TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица действий пользователей (логи)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                username TEXT,
                action_type TEXT NOT NULL,
                endpoint TEXT,
                request_data TEXT,
                ip_address TEXT,
                user_agent TEXT,
                status_code INTEGER,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица для rate limiting
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                ip_address TEXT NOT NULL,
                action_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Индексы для быстрого поиска
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_buyer ON transactions(buyer_telegram_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_idempotency ON transactions(idempotency_key)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_actions_telegram_id ON user_actions(telegram_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rate_limits_telegram_id ON rate_limits(telegram_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rate_limits_ip ON rate_limits(ip_address)")
        
        conn.commit()
        conn.close()
        logger.info("✅ Database tables created/verified")
    
    def log_transaction(
        self,
        idempotency_key: str,
        buyer_telegram_id: Optional[int],
        buyer_username: Optional[str],
        buyer_first_name: Optional[str],
        recipient_username: str,
        amount_stars: int,
        payment_method: str,
        tx_hash: Optional[str],
        ton_viewer_link: Optional[str],
        status: str,
        error_message: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO transactions (
                    idempotency_key, buyer_telegram_id, buyer_username, buyer_first_name,
                    recipient_username, amount_stars, payment_method, tx_hash,
                    ton_viewer_link, status, error_message, ip_address, user_agent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                idempotency_key, buyer_telegram_id, buyer_username, buyer_first_name,
                recipient_username, amount_stars, payment_method, tx_hash,
                ton_viewer_link, status, error_message, ip_address, user_agent
            ))
            
            transaction_id = cursor.lastrowid
            conn.commit()
            logger.info(f"✅ Transaction logged: ID={transaction_id}")
            return transaction_id
            
        except sqlite3.IntegrityError:
            # Idempotency key уже существует
            logger.warning(f"⚠️ Duplicate idempotency_key: {idempotency_key}")
            return -1
        finally:
            conn.close()
    
    def get_transaction_by_idempotency_key(self, key: str) -> Optional[Dict]:
        """Получает транзакцию по idempotency ключу"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM transactions WHERE idempotency_key = ?
        """, (key,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))
    
    def log_user_action(
        self,
        telegram_id: Optional[int],
        username: Optional[str],
        action_type: str,
        endpoint: str,
        request_data: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status_code: Optional[int] = None,
        error_message: Optional[str] = None
    ):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO user_actions (
                telegram_id, username, action_type, endpoint, request_data,
                ip_address, user_agent, status_code, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            telegram_id, username, action_type, endpoint, request_data,
            ip_address, user_agent, status_code, error_message
        ))
        
        conn.commit()
        conn.close()
    
    def check_rate_limit(
        self,
        telegram_id: Optional[int],
        ip_address: str,
        action_type: str,
        limit: int = 10,
        window_minutes: int = 1
    ) -> tuple[bool, int]:
        """
        Проверяет rate limit
        
        Returns:
            (is_allowed, current_count)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Очищаем старые записи
        cursor.execute("""
            DELETE FROM rate_limits 
            WHERE datetime(created_at) < datetime('now', '-' || ? || ' minutes')
        """, (window_minutes,))
        
        # Считаем текущие запросы
        if telegram_id:
            cursor.execute("""
                SELECT COUNT(*) FROM rate_limits
                WHERE telegram_id = ? AND action_type = ?
                AND datetime(created_at) >= datetime('now', '-' || ? || ' minutes')
            """, (telegram_id, action_type, window_minutes))
        else:
            cursor.execute("""
                SELECT COUNT(*) FROM rate_limits
                WHERE ip_address = ? AND action_type = ?
                AND datetime(created_at) >= datetime('now', '-' || ? || ' minutes')
            """, (ip_address, action_type, window_minutes))
        
        count = cursor.fetchone()[0]
        
        if count >= limit:
            conn.close()
            return False, count
        
        # Добавляем новую запись
        cursor.execute("""
            INSERT INTO rate_limits (telegram_id, ip_address, action_type)
            VALUES (?, ?, ?)
        """, (telegram_id or 0, ip_address, action_type))
        
        conn.commit()
        conn.close()
        
        return True, count + 1
    
    def get_user_transactions(self, telegram_id: int, limit: int = 10) -> List[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM transactions 
            WHERE buyer_telegram_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (telegram_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    
    def get_statistics(self) -> Dict:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # Всего транзакций
        cursor.execute("SELECT COUNT(*) FROM transactions")
        stats['total_transactions'] = cursor.fetchone()[0]
        
        # Успешных транзакций
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'success'")
        stats['successful_transactions'] = cursor.fetchone()[0]
        
        # Сумма Stars
        cursor.execute("SELECT SUM(amount_stars) FROM transactions WHERE status = 'success'")
        stats['total_stars'] = cursor.fetchone()[0] or 0
        
        # Уникальных пользователей
        cursor.execute("SELECT COUNT(DISTINCT buyer_telegram_id) FROM transactions")
        stats['unique_users'] = cursor.fetchone()[0]
        
        conn.close()
        return stats
