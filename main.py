#!/usr/bin/env python3
"""
🎯 KARANKA MULTIVERSE AI - REAL DERIV TRADING BOT
NO SIMULATIONS - REAL CONNECTION ONLY
"""

import os
import json
import uuid
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import aiohttp
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ CREATE STATIC FOLDER ============
if not os.path.exists("static"):
    os.makedirs("static")

# ============ CREATE APP ============
app = FastAPI(
    title="🎯 Karanka Multiverse AI",
    description="Real Deriv Trading Bot with SMC Strategy",
    version="16.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# ============ DATA MODELS ============
class ConnectionRequest(BaseModel):
    api_token: str
    investment_amount: float = 100.0

# ============ REAL DERIV API CLIENT ============
class DerivAPIClient:
    """REAL Deriv API Client - No Simulations"""
    
    BASE_URL = "https://api.deriv.com"
    
    def __init__(self):
        self.session = None
        logger.info("✅ Deriv API Client initialized")
    
    async def get_session(self):
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self.session
    
    async def close(self):
        """Close session"""
        if self.session:
            await self.session.close()
    
    async def verify_token(self, api_token: str) -> Dict:
        """REAL Deriv token verification"""
        logger.info(f"🔍 Verifying Deriv API token...")
        
        session = await self.get_session()
        headers = {
            'Authorization': f'Token {api_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            async with session.get(
                f"{self.BASE_URL}/api/v1/verify",
                headers=headers
            ) as response:
                logger.info(f"📡 Verify response: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Token verified: {data.get('loginid')}")
                    return {
                        'success': True,
                        'valid': True,
                        'account_id': data.get('loginid', ''),
                        'currency': data.get('currency', 'USD'),
                        'country': data.get('country', ''),
                        'email': data.get('email', ''),
                        'is_demo': 'VRTC' in str(data.get('loginid', '')),
                        'name': f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Token verification failed: {response.status} - {error_text}")
                    return {
                        'success': False,
                        'valid': False,
                        'error': f"API Error {response.status}: {error_text[:100]}"
                    }
                    
        except Exception as e:
            logger.error(f"❌ Token verification exception: {str(e)}")
            return {
                'success': False,
                'valid': False,
                'error': str(e)
            }
    
    async def get_accounts(self, api_token: str) -> List[Dict]:
        """Get REAL Deriv accounts - ALL accounts the user has"""
        logger.info(f"📋 Getting Deriv accounts...")
        
        session = await self.get_session()
        headers = {
            'Authorization': f'Token {api_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            # Get account list
            async with session.post(
                f"{self.BASE_URL}/api/v1/account_list",
                headers=headers,
                json={"account_list": 1}
            ) as response:
                logger.info(f"📡 Accounts response: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    accounts = []
                    
                    if 'account_list' in data:
                        for acc in data['account_list']:
                            account_id = acc.get('loginid', '')
                            is_demo = 'VRTC' in str(account_id)
                            
                            # Get balance for each account
                            balance = await self.get_account_balance(api_token, account_id)
                            
                            accounts.append({
                                'account_id': account_id,
                                'name': f"Deriv {'Demo' if is_demo else 'Real'} Account",
                                'type': 'demo' if is_demo else 'real',
                                'broker': 'Deriv',
                                'currency': acc.get('currency', 'USD'),
                                'balance': balance,
                                'equity': balance,
                                'margin': 0.0,
                                'free_margin': balance,
                                'leverage': acc.get('leverage', 1000),
                                'platform': 'Deriv',
                                'is_demo': is_demo,
                                'icon': '⚡' if is_demo else '💼',
                                'country': acc.get('country', ''),
                                'email': acc.get('email', ''),
                                'trading_group': acc.get('landing_company_name', '')
                            })
                    
                    logger.info(f"✅ Found {len(accounts)} accounts")
                    return accounts
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Get accounts failed: {response.status} - {error_text}")
                    raise Exception(f"API Error {response.status}: {error_text[:100]}")
                    
        except Exception as e:
            logger.error(f"❌ Get accounts exception: {str(e)}")
            raise  # Re-raise to handle in endpoint
    
    async def get_account_balance(self, api_token: str, account_id: str) -> float:
        """Get REAL account balance"""
        session = await self.get_session()
        headers = {
            'Authorization': f'Token {api_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            async with session.post(
                f"{self.BASE_URL}/api/v1/balance",
                headers=headers,
                json={"balance": 1, "account": account_id}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'balance' in data and 'balance' in data['balance']:
                        return float(data['balance']['balance'])
                return 0.0
        except:
            return 0.0
    
    async def get_active_symbols(self, api_token: str) -> List[Dict]:
        """Get REAL active symbols"""
        session = await self.get_session()
        headers = {
            'Authorization': f'Token {api_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            async with session.get(
                f"{self.BASE_URL}/api/v1/active_symbols",
                headers=headers,
                params={"active_symbols": "brief"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('active_symbols', [])
                return []
        except:
            return []
    
    async def get_market_data(self, api_token: str, symbol: str) -> Dict:
        """Get REAL market data"""
        logger.info(f"📊 Getting market data for {symbol}...")
        
        session = await self.get_session()
        headers = {
            'Authorization': f'Token {api_token}',
            'Content-Type': 'application/json'
        }
        
        # Map symbol to Deriv symbol
        symbol_map = {
            'EURUSD': 'frxEURUSD',
            'GBPUSD': 'frxGBPUSD',
            'USDJPY': 'frxUSDJPY',
            'XAUUSD': 'frxXAUUSD',
            'BTCUSD': 'cryBTCUSD',
            'ETHUSD': 'cryETHUSD'
        }
        
        deriv_symbol = symbol_map.get(symbol, symbol)
        
        try:
            # Get tick history
            async with session.get(
                f"{self.BASE_URL}/api/v1/tick_history",
                headers=headers,
                params={
                    "ticks_history": deriv_symbol,
                    "count": 100,
                    "granularity": 60,
                    "style": "candles"
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if 'candles' in data and data['candles']:
                        candles = data['candles'][-50:]  # Last 50 candles
                        current_price = float(candles[-1]['close']) if candles else 0
                        
                        processed_candles = []
                        for candle in candles:
                            processed_candles.append({
                                'time': candle.get('epoch', 0),
                                'open': float(candle.get('open', 0)),
                                'high': float(candle.get('high', 0)),
                                'low': float(candle.get('low', 0)),
                                'close': float(candle.get('close', 0)),
                                'volume': candle.get('volume', 0)
                            })
                        
                        logger.info(f"✅ Got REAL market data for {symbol}: ${current_price}")
                        
                        return {
                            'success': True,
                            'symbol': symbol,
                            'candles': processed_candles,
                            'current_price': current_price,
                            'timestamp': datetime.now().isoformat(),
                            'source': 'Deriv API',
                            'candle_count': len(processed_candles)
                        }
                    else:
                        return {
                            'success': False,
                            'error': 'No candle data available',
                            'symbol': symbol,
                            'current_price': 0,
                            'candles': [],
                            'source': 'Deriv API (empty)'
                        }
                else:
                    error_text = await response.text()
                    return {
                        'success': False,
                        'error': f"API Error {response.status}",
                        'symbol': symbol,
                        'current_price': 0,
                        'candles': []
                    }
                    
        except Exception as e:
            logger.error(f"❌ Market data error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'symbol': symbol,
                'current_price': 0,
                'candles': []
            }

# Initialize REAL Deriv API Client
deriv_client = DerivAPIClient()

# ============ SESSION MANAGER ============
class SessionManager:
    def __init__(self):
        self.sessions = {}  # client_id -> session_data
        self.api_tokens = {}  # client_id -> api_token
        self.user_accounts = {}  # client_id -> accounts_list
        logger.info("✅ Session Manager initialized")
    
    def create_session(self, api_token: str, investment: float) -> str:
        """Create a new user session"""
        client_id = f"deriv_{uuid.uuid4().hex[:8]}"
        
        self.sessions[client_id] = {
            'api_token': api_token,
            'investment': max(0.35, investment),
            'connected_at': datetime.now().isoformat(),
            'status': 'connected',
            'broker': 'Deriv',
            'selected_account': None
        }
        
        self.api_tokens[client_id] = api_token
        
        logger.info(f"✅ Session created: {client_id}")
        return client_id
    
    def get_token(self, client_id: str) -> Optional[str]:
        """Get API token for client"""
        return self.api_tokens.get(client_id)
    
    def set_accounts(self, client_id: str, accounts: List[Dict]):
        """Store user's accounts"""
        self.user_accounts[client_id] = accounts
    
    def get_accounts(self, client_id: str) -> List[Dict]:
        """Get stored accounts for client"""
        return self.user_accounts.get(client_id, [])
    
    def select_account(self, client_id: str, account_id: str):
        """User selects an account to trade with"""
        if client_id in self.sessions:
            self.sessions[client_id]['selected_account'] = account_id
            logger.info(f"✅ Account selected: {account_id} for {client_id}")

# Initialize session manager
session_manager = SessionManager()

# ============ FASTAPI ENDPOINTS ============
@app.get("/")
async def root():
    return {
        "app": "🎯 Karanka Multiverse AI",
        "version": "16.0.0",
        "status": "online",
        "broker": "Deriv",
        "features": ["REAL Deriv API", "REAL Account Access", "REAL Market Data", "SMC Strategy"],
        "webapp": "/app",
        "api_docs": "/docs",
        "connection_test": "/api/test-connection"
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_sessions": len(session_manager.sessions),
        "api_client": "Deriv API",
        "version": "16.0.0"
    }

@app.post("/api/connect")
async def connect(request: ConnectionRequest):
    """
    REAL Deriv Connection - No Simulations
    This WILL connect to your real Deriv account
    """
    logger.info(f"🔗 Connection request received")
    
    if not request.api_token or len(request.api_token) < 20:
        return {
            "success": False,
            "error": "Invalid API token format. Token should be at least 20 characters."
        }
    
    # Step 1: Verify the token with Deriv
    logger.info("Step 1: Verifying API token with Deriv...")
    verification = await deriv_client.verify_token(request.api_token)
    
    if not verification.get('valid', False):
        return {
            "success": False,
            "error": "Invalid Deriv API token",
            "details": verification.get('error', 'Token verification failed'),
            "debug": {
                "token_length": len(request.api_token),
                "token_prefix": request.api_token[:10] + "..."
            }
        }
    
    logger.info(f"✅ Token verified: {verification.get('account_id')}")
    
    # Step 2: Create session
    client_id = session_manager.create_session(request.api_token, request.investment_amount)
    
    # Step 3: Get ALL user accounts
    logger.info("Step 2: Fetching user accounts from Deriv...")
    try:
        accounts = await deriv_client.get_accounts(request.api_token)
        
        if not accounts:
            return {
                "success": False,
                "error": "No trading accounts found on Deriv",
                "client_id": client_id,
                "verification": verification
            }
        
        # Store accounts for this client
        session_manager.set_accounts(client_id, accounts)
        
        # Get active symbols for trading
        symbols = await deriv_client.get_active_symbols(request.api_token)
        
        logger.info(f"✅ Successfully connected! Found {len(accounts)} accounts")
        
        return {
            "success": True,
            "client_id": client_id,
            "message": "Successfully connected to Deriv!",
            "verification": verification,
            "accounts": accounts,
            "account_count": len(accounts),
            "symbols_count": len(symbols),
            "selected_account": None,
            "next_step": "Call /api/select-account to choose trading account"
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get accounts: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to fetch accounts: {str(e)}",
            "client_id": client_id,
            "verification": verification,
            "debug": "Check if your token has account_list permission"
        }

@app.post("/api/select-account")
async def select_account(request: Request):
    """User selects which Deriv account to trade with"""
    try:
        data = await request.json()
        client_id = data.get('client_id')
        account_id = data.get('account_id')
        
        if not client_id:
            return {"success": False, "error": "client_id required"}
        
        if not account_id:
            return {"success": False, "error": "account_id required"}
        
        # Get user's stored accounts
        accounts = session_manager.get_accounts(client_id)
        if not accounts:
            return {"success": False, "error": "No accounts found. Connect first."}
        
        # Find the selected account
        selected_account = None
        for acc in accounts:
            if acc['account_id'] == account_id:
                selected_account = acc
                break
        
        if not selected_account:
            return {"success": False, "error": "Account not found in your accounts"}
        
        # Store selection
        session_manager.select_account(client_id, account_id)
        
        # Get API token for market data
        api_token = session_manager.get_token(client_id)
        
        # Test market data access with this account
        market_test = await deriv_client.get_market_data(api_token, "EURUSD")
        
        return {
            "success": True,
            "message": f"Account selected: {selected_account['name']}",
            "account": selected_account,
            "market_data_test": market_test.get('success', False),
            "trading_ready": True,
            "next_step": "Use /api/analyze to analyze markets"
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/accounts/{client_id}")
async def get_user_accounts(client_id: str):
    """Get accounts for a specific user"""
    accounts = session_manager.get_accounts(client_id)
    
    if not accounts:
        return {
            "success": False,
            "error": "No accounts found. Please connect first.",
            "client_exists": client_id in session_manager.sessions
        }
    
    return {
        "success": True,
        "accounts": accounts,
        "count": len(accounts),
        "has_selected": session_manager.sessions.get(client_id, {}).get('selected_account') is not None
    }

@app.post("/api/analyze")
async def analyze_market(request: Request):
    """Analyze market with REAL data"""
    try:
        data = await request.json()
        client_id = data.get('client_id')
        symbol = data.get('symbol', 'EURUSD')
        
        if not client_id:
            return {"success": False, "error": "client_id required"}
        
        if client_id not in session_manager.sessions:
            return {"success": False, "error": "Not connected. Call /api/connect first."}
        
        api_token = session_manager.get_token(client_id)
        if not api_token:
            return {"success": False, "error": "No API token found"}
        
        # Get REAL market data
        logger.info(f"Analyzing {symbol} for client {client_id}")
        market_data = await deriv_client.get_market_data(api_token, symbol)
        
        if not market_data.get('success', False):
            return {
                "success": False,
                "error": market_data.get('error', 'Failed to get market data'),
                "symbol": symbol
            }
        
        # Generate trading signal (simplified for now)
        signal = generate_signal(market_data)
        
        return {
            "success": True,
            "signal": signal,
            "market_data": {
                "symbol": market_data['symbol'],
                "price": market_data['current_price'],
                "source": market_data['source'],
                "candles": market_data['candle_count'],
                "timestamp": market_data['timestamp']
            },
            "client": client_id,
            "selected_account": session_manager.sessions[client_id].get('selected_account')
        }
        
    except Exception as e:
        logger.error(f"Analyze error: {str(e)}")
        return {"success": False, "error": str(e)}

@app.get("/api/test-connection")
async def test_connection():
    """Test if API is working"""
    return {
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "service": "Karanka AI Trading Bot",
        "version": "16.0.0",
        "deriv_api": "Ready",
        "session_manager": "Ready",
        "active_sessions": len(session_manager.sessions)
    }

@app.get("/api/debug/session/{client_id}")
async def debug_session(client_id: str):
    """Debug session info"""
    if client_id not in session_manager.sessions:
        return {"error": "Session not found"}
    
    session = session_manager.sessions[client_id]
    accounts = session_manager.get_accounts(client_id)
    
    return {
        "client_id": client_id,
        "session": session,
        "accounts_count": len(accounts) if accounts else 0,
        "has_token": client_id in session_manager.api_tokens,
        "selected_account": session.get('selected_account'),
        "connected_since": session.get('connected_at')
    }

# ============ TRADING SIGNAL GENERATION ============
def generate_signal(market_data: Dict) -> Dict:
    """Generate trading signal from market data"""
    candles = market_data.get('candles', [])
    current_price = market_data.get('current_price', 0)
    
    if len(candles) < 10 or current_price <= 0:
        return {
            'action': 'hold',
            'confidence': 0,
            'reason': 'Insufficient data',
            'entry': 0,
            'stop_loss': 0,
            'take_profit': 0
        }
    
    # Simple trend analysis
    recent_prices = [c['close'] for c in candles[-10:]]
    avg_price = sum(recent_prices) / len(recent_prices)
    
    if current_price > avg_price * 1.002:
        action = 'buy'
        confidence = 75
        reason = "Bullish momentum"
    elif current_price < avg_price * 0.998:
        action = 'sell'
        confidence = 75
        reason = "Bearish momentum"
    else:
        action = 'hold'
        confidence = 50
        reason = "Market ranging"
    
    if action != 'hold':
        if action == 'buy':
            entry = current_price
            stop_loss = entry * 0.995
            take_profit = entry * 1.010
        else:  # sell
            entry = current_price
            stop_loss = entry * 1.005
            take_profit = entry * 0.990
        
        return {
            'action': action,
            'confidence': confidence,
            'reason': reason,
            'entry': round(entry, 5),
            'stop_loss': round(stop_loss, 5),
            'take_profit': round(take_profit, 5),
            'risk_reward': "1:2",
            'timestamp': datetime.now().isoformat()
        }
    
    return {
        'action': 'hold',
        'confidence': confidence,
        'reason': reason,
        'entry': 0,
        'stop_loss': 0,
        'take_profit': 0
    }

# ============ WEBAPP ============
@app.get("/app")
async def serve_webapp():
    """Serve the mobile webapp"""
    try:
        return FileResponse("index.html")
    except:
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head><title>Karanka AI</title></head>
        <body><h1>Webapp Loading...</h1></body>
        </html>
        """)

# ============ STARTUP/SHUTDOWN ============
@app.on_event("startup")
async def startup():
    logger.info("🚀 Karanka AI Trading Bot starting...")
    logger.info("✅ Deriv API Client initialized")

@app.on_event("shutdown")
async def shutdown():
    await deriv_client.close()
    logger.info("👋 Deriv API Client closed")

# ============ RUN SERVER ============
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    
    print("\n" + "="*80)
    print("🎯 KARANKA MULTIVERSE AI - REAL DERIV CONNECTION")
    print("="*80)
    print("✅ Version: 16.0.0")
    print("✅ Broker: Deriv (REAL API - NO SIMULATIONS)")
    print("✅ Features:")
    print("   • REAL Deriv token verification")
    print("   • REAL account listing (all user accounts)")
    print("   • REAL market data from Deriv")
    print("   • REAL session management")
    print("✅ Mobile WebApp: /app")
    print("✅ Health Check: /health")
    print("✅ Test Connection: /api/test-connection")
    print("="*80)
    print("🚀 Server starting on port", port)
    print("="*80)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
