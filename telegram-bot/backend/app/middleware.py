import logging
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
import json

from app.database import log_user_activity, log_suspicious_activity

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    
    async def dispatch(self, request: Request, call_next: Callable):
        # Начало обработки запроса
        start_time = time.time()
        
        # Получаем информацию о запросе
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        method = request.method
        path = request.url.path
        
        # Логируем входящий запрос
        logger.info(f"📥 {method} {path} from {client_ip}")
        logger.info(f"   User-Agent: {user_agent}")
        
        # Проверяем подозрительную активность
        is_suspicious = await self._check_suspicious_activity(request, client_ip, path, user_agent)
        
        # Обрабатываем запрос
        try:
            response = await call_next(request)
            
            # Вычисляем время обработки
            process_time = time.time() - start_time
            
            # Логируем в БД
            log_user_activity(
                action=f"{method} {path}",
                endpoint=path,
                method=method,
                ip_address=client_ip,
                user_agent=user_agent,
                response_status=response.status_code,
                response_time=process_time
            )
            
            # Логируем ответ в консоль
            logger.info(f"✅ {method} {path} → {response.status_code} ({process_time:.3f}s)")
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(f"❌ {method} {path} → Error: {e} ({process_time:.3f}s)")
            
            # Записываем ошибку
            log_user_activity(
                action=f"ERROR: {method} {path}",
                endpoint=path,
                method=method,
                ip_address=client_ip,
                user_agent=user_agent,
                response_status=500,
                response_time=process_time,
                request_data={"error": str(e)}
            )
            
            raise
    
    async def _check_suspicious_activity(
        self, 
        request: Request, 
        client_ip: str, 
        path: str,
        user_agent: str
    ) -> bool:
        
        # Блокируем доступ к чувствительным файлам
        sensitive_files = [
            '/.env', '.env', '/env', '/.git', '.git',
            '/config', '/.ssh', '.ssh', '/backup',
            '/.htaccess', '.htaccess', '/web.config',
            '/.npmrc', '/.dockerenv', '/Dockerfile',
            '/docker-compose', '/.aws', '/.azure'
        ]
        
        # Проверяем путь на чувствительные файлы
        path_lower = path.lower()
        for sensitive in sensitive_files:
            if sensitive in path_lower:
                reason = f"Attempt to access sensitive file: {sensitive}"
                
                # Логируем в БД как заблокированную активность
                log_suspicious_activity(
                    ip_address=client_ip,
                    endpoint=path,
                    reason=reason,
                    user_agent=user_agent,
                    blocked=True
                )
                
                logger.error(f"🚨 BLOCKED: {reason} from {client_ip}")
                
                # Возвращаем 404 чтобы не показывать что файл существует
                from fastapi.responses import JSONResponse
                raise Exception("Not Found")
        
        # Список подозрительных паттернов
        suspicious_patterns = [
            '/admin', '/wp-admin', '/phpMyAdmin', '/phpmyadmin',
            '/shell', '/cmd', '/exec', '/../', '/etc/passwd',
            'SELECT', 'UNION', 'DROP', 'INSERT', '<script>',
            'eval(', 'base64_decode', 'system(', 'exec(',
            '/cgi-bin', '/xmlrpc', '/wp-login', '/administrator'
        ]
        
        # Проверяем путь на подозрительные паттерны
        for pattern in suspicious_patterns:
            if pattern.lower() in path.lower():
                reason = f"Suspicious pattern detected: {pattern}"
                
                # Логируем в БД
                log_suspicious_activity(
                    ip_address=client_ip,
                    endpoint=path,
                    reason=reason,
                    user_agent=user_agent
                )
                
                logger.warning(f"⚠️ SUSPICIOUS: {reason} from {client_ip}")
                return True
        
        return False
