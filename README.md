# KARANKA MULTIVERSE AI - DERIV TRADING BOT

## 🌐 Web Version Now Available!

This bot now runs as a **mobile-friendly webapp** that can be deployed on Render.

### 🚀 Quick Deploy on Render

1. Fork this repository
2. Go to [render.com](https://render.com)
3. Click "New +" → "Web Service"
4. Connect your GitHub repository
5. Use these settings:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn -k eventlet -w 1 app:app`
6. Click "Create Web Service"

### 📱 Features
- All 6 original GUI tabs preserved
- Mobile-optimized interface
- Real-time updates via WebSocket
- NEVER sleeps (continuous data fetching)
- Deriv API integration

### 🔧 Local Testing
```bash
pip install -r requirements.txt
python app.py
