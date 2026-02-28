#!/usr/bin/env python3
"""
KARANKA MULTIVERSE ALGO AI TRADER - RENDER DEPLOYMENT VERSION
"""

import sys
import os
import threading
import time
import json
import traceback
import queue
from datetime import datetime
import numpy as np
import pandas as pd
import requests
import websocket
from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)

# ============ DERIV CONNECTOR (SIMPLIFIED) ============
class DerivConnector:
    def __init__(self):
        self.api_token = ""
        self.app_id = "1089"
        self.ws_url = f"wss://ws.binaryws.com/websockets/v3?app_id={self.app_id}"
        self.ws = None
        self.connected = False
        self.authorized = False
        self.balance = 0.0
        self.currency = "USD"
        self.loginid = ""
        self.active_symbols = []
        self.last_tick = {}
        self.response_queues = {}
        self.message_id = 1
        
    def connect(self, api_token):
        self.api_token = api_token.strip()
        try:
            self.ws = websocket.WebSocket()
            self.ws.connect(self.ws_url)
            self.connected = True
            return self.authorize()
        except Exception as e:
            return False, str(e)
    
    def authorize(self):
        req_id = self._get_req_id()
        auth_request = {
            "authorize": self.api_token,
            "req_id": req_id
        }
        self.ws.send(json.dumps(auth_request))
        response = json.loads(self.ws.recv())
        
        if "error" in response:
            return False, response['error']['message']
        
        self.authorized = True
        auth_data = response.get("authorize", {})
        self.balance = float(auth_data.get('balance', 0))
        self.currency = auth_data.get('currency', 'USD')
        self.loginid = auth_data.get('loginid', '')
        return True, "Connected"
    
    def get_active_symbols(self):
        if not self.connected or not self.authorized:
            return False, []
        
        req_id = self._get_req_id()
        symbols_request = {
            "active_symbols": "brief",
            "product_type": "basic",
            "req_id": req_id
        }
        self.ws.send(json.dumps(symbols_request))
        response = json.loads(self.ws.recv())
        
        if "error" in response:
            return False, []
        
        self.active_symbols = response.get("active_symbols", [])
        return True, self.active_symbols
    
    def get_tick_price(self, symbol):
        if not self.connected or not self.authorized:
            return None
        
        req_id = self._get_req_id()
        tick_request = {
            "ticks": symbol,
            "req_id": req_id
        }
        self.ws.send(json.dumps(tick_request))
        response = json.loads(self.ws.recv())
        tick = response.get("tick", {})
        return float(tick.get('quote', 0)) if tick else None
    
    def _get_req_id(self):
        self.message_id += 1
        return self.message_id
    
    def get_account_info(self):
        return {
            'balance': self.balance,
            'currency': self.currency,
            'loginid': self.loginid,
            'connected': self.connected,
            'authorized': self.authorized
        }
    
    def disconnect(self):
        if self.ws:
            self.ws.close()
        self.connected = False
        self.authorized = False

# ============ TRADING ENGINE (MINIMAL) ============
class TradingEngine:
    def __init__(self):
        self.deriv = DerivConnector()
        self.connected = False
        self.authorized = False
        self.running = False
        self.market_data = {}
        self.trades_today = 0
        
    def connect_deriv(self, api_token):
        success, message = self.deriv.connect(api_token)
        if success:
            self.connected = True
            self.authorized = True
            self.deriv.get_active_symbols()
        return success, message
    
    def get_status(self):
        account = self.deriv.get_account_info()
        return {
            'connected': self.connected,
            'authorized': self.authorized,
            'running': self.running,
            'balance': account['balance'],
            'currency': account['currency'],
            'loginid': account['loginid'],
            'daily_trades': self.trades_today
        }
    
    def disconnect(self):
        self.deriv.disconnect()
        self.connected = False
        self.authorized = False

# Initialize trading engine
trader = TradingEngine()

# ============ HTML TEMPLATE (SELF-CONTAINED) ============
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KARANKA ALGO AI TRADER</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: #000000;
            color: #FFD700;
            font-family: -apple-system, system-ui, sans-serif;
            padding: 10px;
        }
        .container { max-width: 600px; margin: 0 auto; }
        h1 {
            font-size: 1.2rem;
            text-align: center;
            border-bottom: 2px solid #D4AF37;
            padding-bottom: 10px;
            margin-bottom: 15px;
        }
        .status-bar {
            background: #0a0a0a;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 10px;
            margin-bottom: 15px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .status-item { text-align: center; }
        .status-label { font-size: 0.7rem; color: #B8860B; }
        .status-value { font-size: 1rem; font-weight: bold; }
        .connected { color: #00FF00; }
        .disconnected { color: #FF4444; }
        .tab-bar {
            display: flex;
            background: #0a0a0a;
            border-radius: 8px;
            margin-bottom: 15px;
            border: 1px solid #333;
        }
        .tab {
            flex: 1;
            text-align: center;
            padding: 12px 0;
            cursor: pointer;
            color: #B8860B;
            font-size: 0.8rem;
        }
        .tab.active {
            background: #D4AF37;
            color: #000;
            font-weight: bold;
        }
        .panel {
            display: none;
            background: #0a0a0a;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
        }
        .panel.active { display: block; }
        .btn {
            background: #8B7500;
            color: #FFD700;
            border: none;
            padding: 12px;
            border-radius: 6px;
            font-size: 0.9rem;
            font-weight: bold;
            width: 100%;
            margin: 5px 0;
            cursor: pointer;
        }
        .btn:active { background: #D4AF37; color: #000; }
        .btn-group { display: flex; gap: 8px; }
        .input-group {
            margin-bottom: 15px;
        }
        .input-group label {
            display: block;
            color: #B8860B;
            font-size: 0.8rem;
            margin-bottom: 3px;
        }
        .input-group input {
            width: 100%;
            padding: 10px;
            background: #000;
            border: 1px solid #333;
            color: #FFD700;
            border-radius: 4px;
        }
        .info-text {
            background: #000;
            border: 1px solid #333;
            border-radius: 6px;
            padding: 10px;
            font-size: 0.8rem;
            color: #B8860B;
            margin: 10px 0;
        }
        .last-update {
            text-align: center;
            font-size: 0.7rem;
            color: #B8860B;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚡ KARANKA ALGO AI - DERIV</h1>
        
        <div class="status-bar">
            <div class="status-item">
                <div class="status-label">Connection</div>
                <div class="status-value" id="conn-status">❌</div>
            </div>
            <div class="status-item">
                <div class="status-label">Balance</div>
                <div class="status-value" id="balance">0.00</div>
            </div>
        </div>
        
        <div class="tab-bar">
            <div class="tab active" onclick="switchTab('dashboard')">📊 Dashboard</div>
            <div class="tab" onclick="switchTab('connection')">🔗 Connection</div>
            <div class="tab" onclick="switchTab('settings')">⚙️ Settings</div>
        </div>
        
        <!-- Dashboard Panel -->
        <div id="dashboard-panel" class="panel active">
            <h2>Quick Controls</h2>
            <div class="btn-group">
                <button class="btn" onclick="startTrading()">🚀 Start</button>
                <button class="btn" onclick="stopTrading()">🛑 Stop</button>
            </div>
            <div class="info-text" id="dashboard-info">
                Connect to Deriv first in the Connection tab
            </div>
        </div>
        
        <!-- Connection Panel -->
        <div id="connection-panel" class="panel">
            <h2>Deriv Connection</h2>
            <div class="input-group">
                <label>API Token</label>
                <input type="password" id="api-token" placeholder="Enter your Deriv API token">
            </div>
            <button class="btn" onclick="connectDeriv()">🔗 Connect</button>
            <button class="btn" onclick="disconnectDeriv()">🔌 Disconnect</button>
            <div class="info-text" id="connection-info">
                Status: Not Connected
            </div>
        </div>
        
        <!-- Settings Panel -->
        <div id="settings-panel" class="panel">
            <h2>Settings</h2>
            <div class="input-group">
                <label>Update Interval (seconds)</label>
                <input type="number" id="update-interval" value="2" min="1" max="10">
            </div>
            <button class="btn" onclick="saveSettings()">💾 Save</button>
        </div>
        
        <div class="last-update" id="last-update">
            Last Update: --
        </div>
    </div>

    <script>
        let currentTab = 'dashboard';
        
        function switchTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
            document.querySelector(`[onclick="switchTab('${tab}')"]`).classList.add('active');
            document.getElementById(`${tab}-panel`).classList.add('active');
            currentTab = tab;
        }
        
        function updateStatus() {
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('conn-status').innerHTML = data.connected ? '✅' : '❌';
                    document.getElementById('conn-status').className = 'status-value ' + (data.connected ? 'connected' : 'disconnected');
                    document.getElementById('balance').innerHTML = data.balance.toFixed(2) + ' ' + data.currency;
                    
                    let info = data.connected ? 
                        `✅ Connected to Deriv<br>Account: ${data.loginid}<br>Balance: ${data.balance.toFixed(2)} ${data.currency}` :
                        '❌ Not Connected to Deriv';
                    document.getElementById('connection-info').innerHTML = info;
                    document.getElementById('dashboard-info').innerHTML = info;
                    
                    document.getElementById('last-update').innerHTML = 'Last Update: ' + new Date().toLocaleTimeString();
                });
        }
        
        function connectDeriv() {
            const token = document.getElementById('api-token').value;
            fetch('/api/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({api_token: token})
            })
            .then(r => r.json())
            .then(data => {
                alert(data.message);
                updateStatus();
            });
        }
        
        function disconnectDeriv() {
            fetch('/api/disconnect', {method: 'POST'})
            .then(r => r.json())
            .then(() => updateStatus());
        }
        
        function startTrading() {
            fetch('/api/start_trading', {method: 'POST'})
            .then(r => r.json())
            .then(data => alert(data.message));
        }
        
        function stopTrading() {
            fetch('/api/stop_trading', {method: 'POST'})
            .then(r => r.json())
            .then(data => alert(data.message));
        }
        
        function saveSettings() {
            const interval = document.getElementById('update-interval').value;
            localStorage.setItem('updateInterval', interval);
            alert('Settings saved!');
        }
        
        // Auto-refresh
        updateStatus();
        setInterval(updateStatus, 2000);
    </script>
</body>
</html>
'''

# ============ FLASK ROUTES ============
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/status')
def api_status():
    return jsonify(trader.get_status())

@app.route('/api/connect', methods=['POST'])
def api_connect():
    data = request.json
    success, message = trader.connect_deriv(data.get('api_token', ''))
    return jsonify({'success': success, 'message': message})

@app.route('/api/disconnect', methods=['POST'])
def api_disconnect():
    trader.disconnect()
    return jsonify({'success': True})

@app.route('/api/start_trading', methods=['POST'])
def api_start_trading():
    if not trader.connected or not trader.authorized:
        return jsonify({'success': False, 'message': 'Not connected'})
    trader.running = True
    return jsonify({'success': True, 'message': 'Trading started'})

@app.route('/api/stop_trading', methods=['POST'])
def api_stop_trading():
    trader.running = False
    return jsonify({'success': True, 'message': 'Trading stopped'})

@app.route('/ping')
def ping():
    return jsonify({'status': 'alive', 'time': datetime.now().isoformat()})

# ============ MAIN ============
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
