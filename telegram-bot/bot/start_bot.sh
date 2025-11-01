#!/bin/bash

echo "🤖 Starting Telegram Stars Shop Bot..."
echo ""

# Проверка .env файла
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found!"
    echo ""
    echo "📝 Please create .env file:"
    echo "   cp .env.example .env"
    echo "   nano .env"
    echo ""
    exit 1
fi

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed!"
    exit 1
fi

python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "🐍 Python version: $python_version"
echo ""

# Установка зависимостей
echo "📦 Installing dependencies..."
pip install -r requirements.txt
echo ""

# Запуск бота
echo "✅ Starting bot..."
echo "Press Ctrl+C to stop"
echo ""

python3 bot.py
