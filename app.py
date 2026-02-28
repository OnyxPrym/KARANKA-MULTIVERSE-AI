#!/usr/bin/env python3
"""
KARANKA ALGO AI TRADER - ULTRA SIMPLE VERSION
"""

import os
import time
import json
from datetime import datetime
from flask import Flask, jsonify, request, render_template_string
import requests

app = Flask(__name__)

# Simple in-memory storage
class SimpleTrader:
    def __init__(self):
        self.connected = False
        self.authorized = False
        self.balance = 0.0
        self.currency = "USD"
        self.loginid = ""
        self.api_token = ""
        
    def connect(self, token):
        self.api_token = token
        # Simulate connection for demo
        self.connected = True
        self.authorized = True
        self.balance = 1000.00
        self.currency = "USD"
        self.loginid = "DEMO123"
        return True, "Connected to Deriv (Demo Mode)"
    
    def disconnect(self):
        self.connected = False
        self.authorized = False
        
    def get_status(self):
        return {
            'connected': self.connected,
            'authorized': self.authorized,
            'balance': self.balance,
            'currency': self.currency,
            'loginid': self.loginid
        }

trader = SimpleTrader()

# HTML Template - ULTRA SIMPLE
HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KARANKA AI TRADER</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: black;
            color: gold;
            font-family: Arial, sans-serif;
            padding: 10px;
        }
        .container { max-width: 500px; margin: 0 auto; }
        h1 {
            text-align: center;
            border-bottom: 2px solid gold;
            padding: 10px;
            margin-bottom: 20px;
            font-size: 1.2rem;
        }
        .status-box {
            background: #111;
            border: 1px solid #333;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
        }
        .status-row {
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            font-size: 1rem;
        }
        .connected { color: #0f0; }
        .disconnected { color: #f00; }
        button {
            width: 100%;
            padding: 15px;
            margin: 5px 0;
            background: #gold;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: bold;
            cursor: pointer;
        }
        .connect-btn { background: #006400; color: white; }
        .disconnect-btn { background: #8b0000; color: white; }
        input {
            width: 100%;
            padding: 12px;
            margin: 10px 0;
            background: black;
            border: 1px solid gold;
            color: gold;
            border-radius: 5px;
        }
        .last-update {
            text-align: center;
            margin-top: 20px;
            color: #886;
            font-size: 0.8rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚡ KARANKA AI TRADER</h1>
        
        <div class="status-box" id="status">
            <div class="status-row">
                <span>Connection:</span>
                <span id="conn-status" class="disconnected">Disconnected</span>
            </div>
            <div class="status-row">
                <span>Balance:</span>
                <span id="balance">0.00 USD</span>
            </div>
            <div class="status-row">
                <span>Account:</span>
                <span id="account">-</span>
            </div>
        </div>

        <h2>Deriv Connection</h2>
        <input type="password" id="token" placeholder="Enter your Deriv API token">
        <button class="connect-btn" onclick="connect()">🔗 Connect to Deriv</button>
        <button class="disconnect-btn" onclick="disconnect()">🔌 Disconnect</button>
        
        <div class="last-update" id="last-update">Loading...</div>
    </div>

    <script>
        function updateStatus() {
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('conn-status').innerHTML = 
                        data.connected ? '✅ Connected' : '❌ Disconnected';
                    document.getElementById('conn-status').className = 
                        data.connected ? 'connected' : 'disconnected';
                    document.getElementById('balance').innerHTML = 
                        data.balance.toFixed(2) + ' ' + data.currency;
                    document.getElementById('account').innerHTML = 
                        data.loginid || '-';
                    document.getElementById('last-update').innerHTML = 
                        'Last Update: ' + new Date().toLocaleTimeString();
                });
        }

        function connect() {
            const token = document.getElementById('token').value;
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

        function disconnect() {
            fetch('/api/disconnect', {method: 'POST'})
            .then(r => r.json())
            .then(() => updateStatus());
        }

        // Update every 2 seconds
        updateStatus();
        setInterval(updateStatus, 2000);
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/status')
def api_status():
    return jsonify(trader.get_status())

@app.route('/api/connect', methods=['POST'])
def api_connect():
    data = request.json
    success, message = trader.connect(data.get('api_token', ''))
    return jsonify({'success': success, 'message': message})

@app.route('/api/disconnect', methods=['POST'])
def api_disconnect():
    trader.disconnect()
    return jsonify({'success': True})

@app.route('/ping')
def ping():
    return jsonify({'status': 'alive', 'time': datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
