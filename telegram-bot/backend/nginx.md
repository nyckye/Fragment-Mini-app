server {
    listen 443 ssl http2;
    server_name ваш_домен_здесь;

    # SSL сертификаты от acme.sh (ECC)
    ssl_certificate /root/.acme.sh/webstorstars.duckdns.org_ecc/fullchain.cer;
    ssl_certificate_key /root/.acme.sh/webstorstars.duckdns.org_ecc/webstorstars.duckdns.org.key;

    # SSL настройки
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256';

    # 🛡️ Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Блокировка .env (regex)
    location ~ \.env {
        deny all;
        return 404;
    }

    # Блокируем все скрытые файлы
    location ~ /\. {
        deny all;
        return 404;
    }

    # Блокируем backup, логи, конфиги
    location ~ \.(bak|backup|sql|db|log|old|conf|config|ini)$ {
        deny all;
        return 404;
    }
    # Блокируем директории разработки
    location ~ /(node_modules|__pycache__|\.pytest_cache|\.git|\.vscode|\.idea|backup) {
        deny all;
        return 404;
    }

    # 💎 TON Connect manifest - СТАТИЧЕСКИЙ файл с CORS
    location = /tonconnect-manifest.json {
        root /var/www/webstorstars;
        add_header Content-Type application/json;
        add_header Access-Control-Allow-Origin * always;
        add_header Access-Control-Allow-Methods "GET, OPTIONS" always;
        add_header Access-Control-Allow-Headers "*" always;

        # OPTIONS для CORS preflight
        if ($request_method = 'OPTIONS') {
            add_header Access-Control-Allow-Origin * always;
            add_header Access-Control-Allow-Methods "GET, OPTIONS" always;
            add_header Access-Control-Allow-Headers "*" always;
            add_header Content-Length 0;
            add_header Content-Type text/plain;
            return 204;
        }
    }

    # 🖼️ Icon для TON Connect
    location = /icon.png {
        root /var/www/webstorstars;
        add_header Access-Control-Allow-Origin * always;
        add_header Cache-Control "public, max-age=86400";
    }
    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Таймауты
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # Размер запроса
        client_max_body_size 1M;
    }

    # Health check
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        access_log off;
    }

    # Admin endpoints
    location /admin/ {
        proxy_pass http://127.0.0.1:8000/admin/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    # User endpoints
    location /user/ {
        proxy_pass http://127.0.0.1:8000/user/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Frontend HTML (ПОСЛЕДНИМ!)
    location / {
        root /var/www/webstorstars;
        index index.html telegram-stars-shop-integrated.html;
        try_files $uri $uri/ /index.html;

        # Кэширование
        add_header Cache-Control "no-cache, must-revalidate";
    }

    # Логирование
    access_log /var/log/nginx/telegram-stars-access.log;
    error_log /var/log/nginx/telegram-stars-error.log warn;
}

server {
    listen 80;
    server_name webstorstars.duckdns.org;
    return 301 https://$server_name$request_uri;
}
