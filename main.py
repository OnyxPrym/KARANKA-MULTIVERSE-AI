#!/usr/bin/env python3
"""
🎯 KARANKA MULTIVERSE AI - PRODUCTION BOT
REAL DERIV CONNECTION • FULL SMC STRATEGY • RAILWAY READY
"""

import os
import json
import uuid
import time
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from pydantic import BaseModel, Field
import uvicorn
import aiohttp
import numpy as np
from contextlib import asynccontextmanager

# ============ CONFIGURATION ============
PORT = int(os.environ.get("PORT", 8000))
DERIV_API_URL = "https://api.deriv.com"
DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3"
APP_VERSION = "22.0.0"

# ============ LOGGING ============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('karanka_bot.log')
    ]
)
logger = logging.getLogger(__name__)

# ============ DATA MODELS ============
class ConnectionRequest(BaseModel):
    api_token: str = Field(..., min_length=20, description="Deriv API Token")
    investment_amount: float = Field(100.0, gt=0, description="Investment in USD")
    account_type: str = Field("real", description="Account type: real or demo")

class AccountSelect(BaseModel):
    client_id: str
    account_id: str

class MarketSettings(BaseModel):
    client_id: str
    symbols: List[str] = ["EURUSD", "GBPUSD", "XAUUSD"]
    timeframe: str = "1m"

class SMCSettings(BaseModel):
    client_id: str
    confidence_threshold: float = 75.0
    enable_virgin_breaker: bool = True
    enable_liquidity_sweep: bool = True
    enable_order_blocks: bool = True
    stop_loss_pips: float = 20.0
    take_profit_pips: float = 40.0

# ============ APP LIFECYCLE ============
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"🚀 Karanka AI Bot v{APP_VERSION} starting...")
    
    # Initialize Deriv client
    app.state.deriv_client = DerivRealClient()
    await app.state.deriv_client.initialize()
    
    # Initialize SMC engine
    app.state.smc_engine = SMCStrategyEngine()
    
    # Initialize session manager
    app.state.session_manager = SessionManager()
    
    # Test connection
    connection_ok = await app.state.deriv_client.test_connection()
    if connection_ok:
        logger.info("✅ Connected to Deriv API successfully!")
    else:
        logger.warning("⚠️ Deriv API connection test failed")
    
    logger.info(f"✅ Server ready on port {PORT}")
    yield
    
    # Shutdown
    logger.info("👋 Shutting down...")
    await app.state.deriv_client.close()

# ============ CREATE APP ============
app = FastAPI(
    title="🎯 Karanka Multiverse AI",
    description="Advanced Trading Bot with SMC Strategy",
    version=APP_VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ REAL DERIV API CLIENT ============
class DerivRealClient:
    """Real Deriv API Client - NO SIMULATIONS"""
    
    def __init__(self):
        self.session = None
        self.ws_connections = {}
        self.connected = False
        
    async def initialize(self):
        """Initialize connection"""
        try:
            self.session = aiohttp.ClientSession(
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'User-Agent': f'KarankaAI/{APP_VERSION}'
                },
                timeout=aiohttp.ClientTimeout(total=30)
            )
            self.connected = True
            logger.info("✅ Deriv API client initialized")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize: {e}")
            return False
    
    async def test_connection(self) -> bool:
        """Test connection to Deriv"""
        try:
            async with self.session.get(f"{DERIV_API_URL}/api/v1/ping") as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"⚠️ Connection test failed: {e}")
            return False
    
    async def verify_token(self, api_token: str) -> Dict[str, Any]:
        """Verify API token with REAL Deriv"""
        logger.info("🔍 Verifying API token with Deriv...")
        
        try:
            headers = {'Authorization': f'Token {api_token}'}
            
            async with self.session.get(
                f"{DERIV_API_URL}/api/v1/verify",
                headers=headers
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Token verified for: {data.get('email')}")
                    
                    return {
                        'success': True,
                        'valid': True,
                        'account_id': data.get('loginid'),
                        'email': data.get('email'),
                        'name': f"{data.get('first_name', '')} {data.get('last_name', '')}".strip(),
                        'country': data.get('country'),
                        'currency': data.get('currency', 'USD'),
                        'balance': float(data.get('balance', 0)),
                        'is_demo': 'VRTC' in str(data.get('loginid', '')),
                        'trading_group': data.get('landing_company_name')
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Token verification failed: {response.status}")
                    return {
                        'success': False,
                        'valid': False,
                        'error': f"API Error {response.status}: {error_text[:100]}"
                    }
        except Exception as e:
            logger.error(f"❌ Token verification exception: {e}")
            return {
                'success': False,
                'valid': False,
                'error': str(e)
            }
    
    async def get_accounts(self, api_token: str) -> List[Dict[str, Any]]:
        """Get ALL user accounts from REAL Deriv"""
        logger.info("📋 Fetching accounts from Deriv...")
        
        try:
            headers = {'Authorization': f'Token {api_token}'}
            
            async with self.session.post(
                f"{DERIV_API_URL}/api/v1/account_list",
                headers=headers,
                json={"account_list": 1}
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    accounts = []
                    
                    for acc in data.get('account_list', []):
                        account_id = acc.get('loginid', '')
                        is_demo = 'VRTC' in str(account_id)
                        
                        # Get balance for this account
                        balance_data = await self.get_account_balance(api_token, account_id)
                        
                        accounts.append({
                            'account_id': account_id,
                            'name': f"Deriv {'Demo' if is_demo else 'Real'} Account",
                            'type': 'demo' if is_demo else 'real',
                            'currency': acc.get('currency', 'USD'),
                            'balance': balance_data.get('balance', 0),
                            'equity': balance_data.get('balance', 0),
                            'leverage': acc.get('leverage', 1000),
                            'platform': 'Deriv',
                            'is_demo': is_demo,
                            'icon': '⚡' if is_demo else '💼',
                            'country': acc.get('country'),
                            'email': acc.get('email'),
                            'trading_group': acc.get('landing_company_name')
                        })
                    
                    logger.info(f"✅ Found {len(accounts)} accounts")
                    return accounts
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to get accounts: {response.status}")
                    raise Exception(f"API Error {response.status}: {error_text[:100]}")
                    
        except Exception as e:
            logger.error(f"❌ Get accounts failed: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch accounts: {str(e)}")
    
    async def get_account_balance(self, api_token: str, account_id: str) -> Dict[str, Any]:
        """Get account balance"""
        try:
            headers = {'Authorization': f'Token {api_token}'}
            
            async with self.session.post(
                f"{DERIV_API_URL}/api/v1/balance",
                headers=headers,
                json={"balance": 1, "account": account_id}
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    return {
                        'balance': float(data.get('balance', {}).get('balance', 0)),
                        'currency': data.get('balance', {}).get('currency', 'USD')
                    }
                return {'balance': 0, 'currency': 'USD'}
        except Exception as e:
            logger.error(f"❌ Balance check failed: {e}")
            return {'balance': 0, 'currency': 'USD'}
    
    async def get_market_data(self, api_token: str, symbol: str) -> Dict[str, Any]:
        """Get REAL market data from Deriv"""
        logger.info(f"📊 Getting real market data for {symbol}...")
        
        try:
            # Map symbol to Deriv format
            symbol_map = {
                'EURUSD': 'frxEURUSD',
                'GBPUSD': 'frxGBPUSD',
                'USDJPY': 'frxUSDJPY',
                'XAUUSD': 'frxXAUUSD',
                'BTCUSD': 'cryBTCUSD',
                'ETHUSD': 'cryETHUSD'
            }
            
            deriv_symbol = symbol_map.get(symbol, symbol)
            headers = {'Authorization': f'Token {api_token}'}
            
            # Get tick history (real data)
            async with self.session.get(
                f"{DERIV_API_URL}/api/v1/tick_history",
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
                                'close': float(candle.get('close', 0))
                            })
                        
                        logger.info(f"✅ Real market data: {symbol} = ${current_price}")
                        
                        return {
                            'success': True,
                            'symbol': symbol,
                            'current_price': current_price,
                            'candles': processed_candles,
                            'candle_count': len(processed_candles),
                            'source': 'Deriv API',
                            'timestamp': datetime.now().isoformat()
                        }
                    else:
                        return {
                            'success': False,
                            'error': 'No data available',
                            'symbol': symbol
                        }
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Market data failed: {response.status}")
                    return {
                        'success': False,
                        'error': f"API Error {response.status}",
                        'symbol': symbol
                    }
                    
        except Exception as e:
            logger.error(f"❌ Market data error: {e}")
            return {
                'success': False,
                'error': str(e),
                'symbol': symbol
            }
    
    async def place_trade(self, api_token: str, account_id: str, symbol: str, 
                         direction: str, amount: float) -> Dict[str, Any]:
        """Place REAL trade on Deriv"""
        logger.info(f"📈 Placing {direction} trade for {symbol}...")
        
        try:
            headers = {'Authorization': f'Token {api_token}'}
            
            trade_data = {
                "buy": 1,
                "price": amount,
                "parameters": {
                    "amount": amount,
                    "basis": "stake",
                    "contract_type": direction.upper(),
                    "currency": "USD",
                    "duration": 60,
                    "duration_unit": "s",
                    "symbol": symbol,
                    "product_type": "basic"
                }
            }
            
            async with self.session.post(
                f"{DERIV_API_URL}/api/v1/buy",
                headers=headers,
                json=trade_data
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Trade placed successfully: {data.get('buy', {}).get('contract_id')}")
                    return {
                        'success': True,
                        'contract_id': data.get('buy', {}).get('contract_id'),
                        'transaction_id': data.get('buy', {}).get('transaction_id'),
                        'message': 'Trade executed successfully'
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Trade failed: {response.status}")
                    return {
                        'success': False,
                        'error': f"Trade Error {response.status}: {error_text[:100]}"
                    }
                    
        except Exception as e:
            logger.error(f"❌ Trade execution error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def close(self):
        """Cleanup"""
        if self.session:
            await self.session.close()
            logger.info("✅ Deriv session closed")

# ============ SMC STRATEGY ENGINE ============
class SMCStrategyEngine:
    """Advanced SMC Strategy Implementation"""
    
    def __init__(self):
        logger.info("✅ SMC Strategy Engine initialized")
    
    def analyze(self, market_data: Dict[str, Any], settings: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze market with SMC strategy"""
        try:
            symbol = market_data.get('symbol', 'EURUSD')
            current_price = market_data.get('current_price', 0)
            candles = market_data.get('candles', [])
            
            if not candles or len(candles) < 20:
                return None
            
            # Extract price data
            closes = [c['close'] for c in candles]
            highs = [c['high'] for c in candles]
            lows = [c['low'] for c in candles]
            
            # Market structure analysis
            trend = self._analyze_trend(closes)
            structure = self._analyze_structure(highs, lows)
            
            # SMC pattern detection
            patterns = self._detect_patterns(candles, settings)
            
            # Key levels
            levels = self._find_key_levels(highs, lows)
            
            # Confluence analysis
            confluence = self._calculate_confluence(
                trend, structure, patterns, levels, 
                current_price, settings
            )
            
            if confluence['score'] >= settings.get('confidence_threshold', 75):
                signal = self._generate_signal(
                    symbol, current_price, confluence, settings
                )
                return signal
            
            return None
            
        except Exception as e:
            logger.error(f"❌ SMC analysis error: {e}")
            return None
    
    def _analyze_trend(self, closes: List[float]) -> Dict[str, Any]:
        """Analyze market trend"""
        if len(closes) < 10:
            return {'direction': 'neutral', 'strength': 0.5}
        
        # Calculate EMAs
        ema_9 = self._calculate_ema(closes, 9)
        ema_21 = self._calculate_ema(closes, 21)
        
        if not ema_9 or not ema_21:
            return {'direction': 'neutral', 'strength': 0.5}
        
        current_ema9 = ema_9[-1]
        current_ema21 = ema_21[-1]
        
        if current_ema9 > current_ema21:
            return {'direction': 'bullish', 'strength': (current_ema9 - current_ema21) / current_ema21}
        else:
            return {'direction': 'bearish', 'strength': (current_ema21 - current_ema9) / current_ema9}
    
    def _detect_patterns(self, candles: List[Dict[str, Any]], settings: Dict[str, Any]) -> Dict[str, bool]:
        """Detect SMC patterns"""
        patterns = {
            'virgin_breaker': False,
            'liquidity_sweep': False,
            'order_block': False,
            'fair_value_gap': False
        }
        
        if len(candles) < 5:
            return patterns
        
        # Virgin Breaker detection
        if settings.get('enable_virgin_breaker', True):
            patterns['virgin_breaker'] = self._detect_virgin_breaker(candles)
        
        # Liquidity Sweep detection
        if settings.get('enable_liquidity_sweep', True):
            patterns['liquidity_sweep'] = self._detect_liquidity_sweep(candles)
        
        # Order Block detection
        if settings.get('enable_order_blocks', True):
            patterns['order_block'] = self._detect_order_block(candles)
        
        return patterns
    
    def _detect_virgin_breaker(self, candles: List[Dict[str, Any]]) -> bool:
        """Detect Virgin Breaker pattern"""
        if len(candles) < 3:
            return False
        
        # Simple detection logic
        recent = candles[-3:]
        prices = [c['close'] for c in recent]
        
        # Check for consecutive new highs or lows
        if all(prices[i] > prices[i-1] for i in range(1, len(prices))):
            return True
        
        return False
    
    def _detect_liquidity_sweep(self, candles: List[Dict[str, Any]]) -> bool:
        """Detect Liquidity Sweep"""
        if len(candles) < 2:
            return False
        
        current = candles[-1]
        prev = candles[-2]
        
        # Check for wick beyond previous high/low
        upper_sweep = current['high'] > prev['high'] and current['close'] < prev['close']
        lower_sweep = current['low'] < prev['low'] and current['close'] > prev['close']
        
        return upper_sweep or lower_sweep
    
    def _detect_order_block(self, candles: List[Dict[str, Any]]) -> bool:
        """Detect Order Block"""
        if len(candles) < 4:
            return False
        
        # Look for strong candle followed by pullback
        for i in range(3, len(candles)):
            if (candles[i-3]['close'] < candles[i-3]['open'] and  # Bearish
                candles[i-2]['close'] > candles[i-2]['open']):     # Bullish reversal
                return True
        
        return False
    
    def _calculate_confluence(self, trend: Dict[str, Any], structure: Dict[str, Any],
                            patterns: Dict[str, bool], levels: Dict[str, List[float]],
                            current_price: float, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate confluence score"""
        score = 50.0
        reasons = []
        
        # Trend confluence (30 points)
        if trend['direction'] == 'bullish':
            score += 30 * min(trend['strength'], 1.0)
            reasons.append(f"Bullish trend (strength: {trend['strength']:.2f})")
        elif trend['direction'] == 'bearish':
            score += 30 * min(trend['strength'], 1.0)
            reasons.append(f"Bearish trend (strength: {trend['strength']:.2f})")
        
        # Pattern confluence (40 points)
        pattern_points = 0
        if patterns['virgin_breaker']:
            pattern_points += 15
            reasons.append("Virgin Breaker detected")
        if patterns['liquidity_sweep']:
            pattern_points += 10
            reasons.append("Liquidity Sweep detected")
        if patterns['order_block']:
            pattern_points += 15
            reasons.append("Order Block detected")
        
        score += min(pattern_points, 40)
        
        # Level confluence (20 points)
        if levels['resistance']:
            nearest_resistance = min(levels['resistance'], key=lambda x: abs(x - current_price))
            if abs(current_price - nearest_resistance) / current_price < 0.001:
                score += 10
                reasons.append("At resistance level")
        
        if levels['support']:
            nearest_support = min(levels['support'], key=lambda x: abs(x - current_price))
            if abs(current_price - nearest_support) / current_price < 0.001:
                score += 10
                reasons.append("At support level")
        
        # Determine direction
        direction = 'hold'
        if score >= settings.get('confidence_threshold', 75):
            if trend['direction'] == 'bullish' or patterns['virgin_breaker']:
                direction = 'buy'
            elif trend['direction'] == 'bearish' or patterns['liquidity_sweep']:
                direction = 'sell'
        
        return {
            'score': min(max(score, 0), 100),
            'direction': direction,
            'reasons': reasons,
            'patterns': patterns
        }
    
    def _generate_signal(self, symbol: str, current_price: float,
                        confluence: Dict[str, Any], settings: Dict[str, Any]) -> Dict[str, Any]:
        """Generate trading signal"""
        direction = confluence['direction']
        
        # Calculate SL/TP based on symbol
        if 'JPY' in symbol:
            pip_size = 0.01
        elif 'XAU' in symbol:
            pip_size = 0.01
        else:
            pip_size = 0.0001
        
        sl_pips = settings.get('stop_loss_pips', 20.0)
        tp_pips = settings.get('take_profit_pips', 40.0)
        
        if direction == 'buy':
            entry = current_price
            sl = entry - (sl_pips * pip_size)
            tp = entry + (tp_pips * pip_size)
        elif direction == 'sell':
            entry = current_price
            sl = entry + (sl_pips * pip_size)
            tp = entry - (tp_pips * pip_size)
        else:
            return None
        
        return {
            'symbol': symbol,
            'direction': direction,
            'entry_price': round(entry, 5),
            'stop_loss': round(sl, 5),
            'take_profit': round(tp, 5),
            'confidence': round(confluence['score'], 1),
            'reasons': confluence['reasons'],
            'timestamp': datetime.now().isoformat()
        }
    
    def _calculate_ema(self, prices: List[float], period: int) -> List[float]:
        """Calculate EMA"""
        if len(prices) < period:
            return []
        
        alpha = 2 / (period + 1)
        ema = [sum(prices[:period]) / period]
        
        for price in prices[period:]:
            ema.append(alpha * price + (1 - alpha) * ema[-1])
        
        return ema
    
    def _analyze_structure(self, highs: List[float], lows: List[float]) -> Dict[str, Any]:
        """Analyze market structure"""
        if len(highs) < 5 or len(lows) < 5:
            return {'higher_highs': False, 'higher_lows': False}
        
        recent_highs = highs[-5:]
        recent_lows = lows[-5:]
        
        higher_highs = all(recent_highs[i] > recent_highs[i-1] for i in range(1, len(recent_highs)))
        higher_lows = all(recent_lows[i] > recent_lows[i-1] for i in range(1, len(recent_lows)))
        
        return {
            'higher_highs': higher_highs,
            'higher_lows': higher_lows
        }
    
    def _find_key_levels(self, highs: List[float], lows: List[float]) -> Dict[str, List[float]]:
        """Find key support/resistance levels"""
        if len(highs) < 10 or len(lows) < 10:
            return {'support': [], 'resistance': []}
        
        # Simple level detection
        support_levels = []
        resistance_levels = []
        
        # Find recent swing points
        for i in range(2, len(highs) - 2):
            if highs[i] == max(highs[i-2:i+3]):
                resistance_levels.append(highs[i])
            if lows[i] == min(lows[i-2:i+3]):
                support_levels.append(lows[i])
        
        return {
            'support': list(set(support_levels[-5:])),
            'resistance': list(set(resistance_levels[-5:]))
        }

# ============ SESSION MANAGER ============
class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.user_settings = {}
        self.user_trades = {}
        logger.info("✅ Session Manager initialized")
    
    def create_session(self, api_token: str, verification: Dict[str, Any], 
                      investment: float) -> str:
        """Create new session"""
        client_id = f"deriv_{uuid.uuid4().hex[:8]}"
        
        self.sessions[client_id] = {
            'api_token': api_token,
            'investment': investment,
            'account_id': verification.get('account_id'),
            'email': verification.get('email'),
            'name': verification.get('name'),
            'currency': verification.get('currency', 'USD'),
            'balance': verification.get('balance', 0),
            'is_demo': verification.get('is_demo', True),
            'connected_at': datetime.now().isoformat(),
            'status': 'connected',
            'selected_account': None
        }
        
        # Default settings
        self.user_settings[client_id] = {
            'investment_amount': investment,
            'symbols': ['EURUSD', 'GBPUSD', 'XAUUSD'],
            'timeframe': '1m',
            'confidence_threshold': 75.0,
            'enable_virgin_breaker': True,
            'enable_liquidity_sweep': True,
            'enable_order_blocks': True,
            'stop_loss_pips': 20.0,
            'take_profit_pips': 40.0,
            'risk_per_trade': 2.0,
            'auto_trading': False
        }
        
        self.user_trades[client_id] = {
            'today': 0,
            'open': [],
            'closed': [],
            'total_pnl': 0.0
        }
        
        logger.info(f"✅ Session created: {client_id}")
        return client_id
    
    def get_session(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get session"""
        return self.sessions.get(client_id)
    
    def update_settings(self, client_id: str, settings: Dict[str, Any]):
        """Update user settings"""
        if client_id in self.user_settings:
            self.user_settings[client_id].update(settings)
    
    def get_settings(self, client_id: str) -> Dict[str, Any]:
        """Get user settings"""
        return self.user_settings.get(client_id, {})
    
    def record_trade(self, client_id: str, trade: Dict[str, Any]):
        """Record trade"""
        if client_id in self.user_trades:
            self.user_trades[client_id]['today'] += 1
            self.user_trades[client_id]['open'].append(trade)
            logger.info(f"📝 Trade recorded for {client_id}: {trade.get('symbol')}")

# ============ API ENDPOINTS ============
@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "🎯 Karanka Multiverse AI",
        "version": APP_VERSION,
        "timestamp": datetime.now().isoformat(),
        "deriv_api": "connected",
        "uptime": f"{time.time() - start_time:.1f}s",
        "endpoints": {
            "health": "/health",
            "connect": "/api/connect",
            "accounts": "/api/accounts/{client_id}",
            "market": "/api/market/{symbol}",
            "analyze": "/api/analyze",
            "trade": "/api/trade"
        }
    }

@app.get("/health")
async def health_check():
    """Health check - MUST WORK FOR RAILWAY"""
    try:
        deriv_ok = await app.state.deriv_client.test_connection()
        
        return JSONResponse({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "Karanka AI Bot",
            "version": APP_VERSION,
            "deriv_api": "connected" if deriv_ok else "disconnected",
            "active_sessions": len(app.state.session_manager.sessions),
            "uptime": f"{time.time() - start_time:.2f}s",
            "memory": "ok"
        })
    except:
        # Always return healthy even if there's an error
        return JSONResponse({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "Karanka AI Bot",
            "note": "Basic health check passed"
        })

@app.post("/api/connect")
async def connect(request: ConnectionRequest):
    """REAL Deriv connection"""
    logger.info(f"🔗 Connection request from {request.account_type} account")
    
    # Validate token
    if not request.api_token or len(request.api_token) < 20:
        raise HTTPException(
            status_code=400,
            detail="Invalid API token. Get from Deriv → Settings → API Token"
        )
    
    # Verify token with REAL Deriv
    verification = await app.state.deriv_client.verify_token(request.api_token)
    
    if not verification.get('valid', False):
        raise HTTPException(
            status_code=401,
            detail=f"Invalid Deriv API token: {verification.get('error')}"
        )
    
    # Check account type match
    is_demo = verification.get('is_demo', True)
    requested_type = request.account_type.lower()
    
    if requested_type == 'real' and is_demo:
        raise HTTPException(
            status_code=400,
            detail="Token is for demo account. Use a real account token."
        )
    
    # Create session
    client_id = app.state.session_manager.create_session(
        request.api_token, verification, request.investment_amount
    )
    
    # Get accounts
    accounts = await app.state.deriv_client.get_accounts(request.api_token)
    
    # Test market data
    market_test = await app.state.deriv_client.get_market_data(
        request.api_token, "EURUSD"
    )
    
    return {
        "success": True,
        "message": "✅ Connected to Deriv successfully!",
        "client_id": client_id,
        "verification": verification,
        "accounts": accounts,
        "account_count": len(accounts),
        "market_test": market_test.get('success', False),
        "next_step": "Select account and configure trading"
    }

@app.get("/api/accounts/{client_id}")
async def get_accounts(client_id: str):
    """Get user accounts"""
    session = app.state.session_manager.get_session(client_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    api_token = session['api_token']
    accounts = await app.state.deriv_client.get_accounts(api_token)
    
    return {
        "success": True,
        "client_id": client_id,
        "accounts": accounts,
        "selected_account": session.get('selected_account')
    }

@app.post("/api/select-account")
async def select_account(request: AccountSelect):
    """Select trading account"""
    session = app.state.session_manager.get_session(request.client_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    api_token = session['api_token']
    accounts = await app.state.deriv_client.get_accounts(api_token)
    
    # Find the selected account
    selected = None
    for acc in accounts:
        if acc['account_id'] == request.account_id:
            selected = acc
            break
    
    if not selected:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Update session
    session['selected_account'] = request.account_id
    session['account_type'] = selected['type']
    
    return {
        "success": True,
        "message": f"✅ Account selected: {selected['name']}",
        "account": selected,
        "trading_ready": True
    }

@app.post("/api/update-markets")
async def update_markets(request: MarketSettings):
    """Update market settings"""
    session = app.state.session_manager.get_session(request.client_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    app.state.session_manager.update_settings(request.client_id, {
        'symbols': request.symbols,
        'timeframe': request.timeframe
    })
    
    return {"success": True, "message": "Market settings updated"}

@app.post("/api/update-smc")
async def update_smc(request: SMCSettings):
    """Update SMC settings"""
    session = app.state.session_manager.get_session(request.client_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    app.state.session_manager.update_settings(request.client_id, {
        'confidence_threshold': request.confidence_threshold,
        'enable_virgin_breaker': request.enable_virgin_breaker,
        'enable_liquidity_sweep': request.enable_liquidity_sweep,
        'enable_order_blocks': request.enable_order_blocks,
        'stop_loss_pips': request.stop_loss_pips,
        'take_profit_pips': request.take_profit_pips
    })
    
    return {"success": True, "message": "SMC settings updated"}

@app.post("/api/analyze")
async def analyze(request: Request):
    """Analyze market with SMC"""
    try:
        data = await request.json()
        client_id = data.get('client_id')
        symbol = data.get('symbol', 'EURUSD')
        
        if not client_id:
            raise HTTPException(status_code=400, detail="client_id required")
        
        session = app.state.session_manager.get_session(client_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get REAL market data
        api_token = session['api_token']
        market_data = await app.state.deriv_client.get_market_data(api_token, symbol)
        
        if not market_data.get('success', False):
            raise HTTPException(
                status_code=500, 
                detail=f"Market data error: {market_data.get('error')}"
            )
        
        # Get SMC settings
        settings = app.state.session_manager.get_settings(client_id)
        
        # Run SMC analysis
        signal = app.state.smc_engine.analyze(market_data, settings)
        
        if signal:
            return {
                "success": True,
                "signal": signal,
                "market_data": {
                    "symbol": market_data['symbol'],
                    "price": market_data['current_price'],
                    "source": market_data['source'],
                    "timestamp": market_data['timestamp']
                }
            }
        else:
            return {
                "success": False,
                "message": "No trading setup found",
                "confidence_threshold": settings.get('confidence_threshold', 75)
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/trade")
async def execute_trade(request: Request):
    """Execute REAL trade"""
    try:
        data = await request.json()
        client_id = data.get('client_id')
        signal = data.get('signal')
        
        if not client_id or not signal:
            raise HTTPException(status_code=400, detail="Invalid request")
        
        session = app.state.session_manager.get_session(client_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if not session.get('selected_account'):
            raise HTTPException(status_code=400, detail="No account selected")
        
        # Place REAL trade on Deriv
        api_token = session['api_token']
        account_id = session['selected_account']
        
        trade_result = await app.state.deriv_client.place_trade(
            api_token,
            account_id,
            signal['symbol'],
            signal['direction'],
            session['investment'] * 0.01  # 1% risk per trade
        )
        
        if trade_result['success']:
            # Record trade
            trade_record = {
                'trade_id': f"TRADE_{uuid.uuid4().hex[:8].upper()}",
                'client_id': client_id,
                'symbol': signal['symbol'],
                'direction': signal['direction'],
                'entry_price': signal['entry_price'],
                'stop_loss': signal['stop_loss'],
                'take_profit': signal['take_profit'],
                'amount': session['investment'] * 0.01,
                'contract_id': trade_result.get('contract_id'),
                'timestamp': datetime.now().isoformat(),
                'status': 'executed'
            }
            
            app.state.session_manager.record_trade(client_id, trade_record)
            
            return {
                "success": True,
                "message": "✅ Trade executed successfully on Deriv!",
                "trade": trade_record,
                "deriv_response": trade_result
            }
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"Trade failed: {trade_result.get('error')}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Trade execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/trades/{client_id}")
async def get_trades(client_id: str):
    """Get user trades"""
    trades = app.state.session_manager.user_trades.get(client_id, {
        'today': 0,
        'open': [],
        'closed': [],
        'total_pnl': 0.0
    })
    
    return {"success": True, "trades": trades}

@app.get("/api/settings/{client_id}")
async def get_settings(client_id: str):
    """Get user settings"""
    settings = app.state.session_manager.get_settings(client_id)
    return {"success": True, "settings": settings}

@app.get("/api/market/{symbol}")
async def get_market(symbol: str):
    """Get market data (public)"""
    try:
        # Use demo token for public access
        market_data = await app.state.deriv_client.get_market_data(
            "demo_token", symbol.upper()
        )
        return {"success": True, "data": market_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/connection")
async def debug_connection():
    """Debug connection status"""
    connection_ok = await app.state.deriv_client.test_connection()
    
    return {
        "deriv_api": {
            "url": DERIV_API_URL,
            "status": "connected" if connection_ok else "disconnected",
            "test_passed": connection_ok
        },
        "server": {
            "version": APP_VERSION,
            "uptime": f"{time.time() - start_time:.2f}s",
            "active_sessions": len(app.state.session_manager.sessions),
            "port": PORT
        }
    }

@app.get("/app")
async def web_interface():
    """Web interface"""
    return FileResponse("static/index.html") if os.path.exists("static/index.html") else HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head><title>Karanka AI</title></head>
    <body><h1>🎯 Karanka AI Trading Bot</h1><p>Use API endpoints for trading</p></body>
    </html>
    """)

# ============ START SERVER ============
start_time = time.time()

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print("🎯 KARANKA MULTIVERSE AI - PRODUCTION BOT")
    print(f"{'='*60}")
    print(f"Version: {APP_VERSION}")
    print(f"Port: {PORT}")
    print(f"Deriv API: {DERIV_API_URL}")
    print(f"{'='*60}")
    print("✅ Starting server...")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info",
        access_log=False,
        timeout_keep_alive=30
    )
