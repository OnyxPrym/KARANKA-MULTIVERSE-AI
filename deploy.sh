#!/bin/bash
echo "🚀 Deploying Karanka Multiverse AI..."

# Create files
cat > fly.toml << 'EOF'
app = "karanka-multiverse-ai"
primary_region = "iad"

[env]
  PORT = "8080"

[build]
  builder = "paketobuildpacks/builder:base"

[http_service]
  internal_port = 8080
  force_https = true
  
  [[http_service.checks]]
    interval = "10s"
    timeout = "2s"
    method = "GET"
    path = "/health"
EOF

cat > requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
EOF

cat > main.py << 'EOF'
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn
import os

app = FastAPI()

@app.get("/")
def root():
    return {"app": "Karanka AI", "status": "online"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/app")
def webapp():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🎯 Karanka AI</title>
        <style>
            body { background: #000; color: #FFD700; font-family: Arial; padding: 50px; text-align: center; }
            h1 { color: #FFD700; }
            .btn { background: #FFD700; color: #000; padding: 15px 30px; border-radius: 10px; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>🎯 KARANKA MULTIVERSE AI</h1>
        <p>Trading Bot - Deployed Successfully!</p>
        <button class="btn" onclick="alert('Bot is working!')">TEST BOT</button>
    </body>
    </html>
    """)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
EOF

echo "📁 Files created. Deploying to Fly.io..."

# Deploy
flyctl deploy

echo "✅ Done! Your bot: https://karanka-multiverse-ai.fly.dev"
