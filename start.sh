#!/bin/bash
echo "🚀 Starting Karanka AI Trading Bot..."
echo "📅 $(date)"
echo "📦 Checking Python installation..."
python --version
echo "📦 Checking dependencies..."
pip list | grep -E "fastapi|uvicorn|aiohttp"
echo "🌐 Testing network connectivity..."
curl -s --connect-timeout 10 https://api.deriv.com/api/v1/ping || echo "⚠️ Deriv API check failed"
echo "🔧 Starting application..."
exec python main.py
