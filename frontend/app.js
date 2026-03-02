// Global variables
let socket = null;
let sessionId = localStorage.getItem('karanka_session');
let connected = false;
let trading = false;
let botInterval = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    loadSavedSettings();
    checkExistingSession();
    initWebSocket();
});

// Tab switching
function initTabs() {
    const tabs = document.querySelectorAll('.tab-btn');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active class from all tabs and panes
            document.querySelectorAll('.tab-btn').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
            
            // Add active class to clicked tab
            tab.classList.add('active');
            
            // Show corresponding pane
            const tabId = tab.getAttribute('data-tab');
            document.getElementById(`${tabId}-tab`).classList.add('active');
        });
    });
}

// Load saved settings from localStorage
function loadSavedSettings() {
    const savedToken = localStorage.getItem('deriv_api_token');
    if (savedToken) {
        document.getElementById('apiToken').value = savedToken;
    }
    
    const savedSymbol = localStorage.getItem('selected_symbol');
    if (savedSymbol) {
        document.getElementById('symbolSelect').value = savedSymbol;
    }
    
    const savedDigit = localStorage.getItem('chosen_digit');
    if (savedDigit) {
        document.getElementById('chosenDigit').value = savedDigit;
    }
    
    const savedStake = localStorage.getItem('initial_stake');
    if (savedStake) {
        document.getElementById('initialStake').value = savedStake;
    }
}

// WebSocket connection for real-time updates
function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}`;
    
    socket = io(wsUrl);
    
    socket.on('connect', () => {
        console.log('Connected to server');
        if (sessionId) {
            socket.emit('subscribe', sessionId);
        }
    });
    
    socket.on('tick', (data) => {
        updateLiveData(data);
    });
    
    socket.on('scores', (data) => {
        updateScores(data);
    });
    
    socket.on('trade_result', (data) => {
        updateStats(data);
        showNotification('Trade Result', `${data.result.toUpperCase()}: $${data.profit || data.loss}`, data.result);
    });
    
    socket.on('error', (data) => {
        showNotification('Error', data.error, 'error');
    });
}

// Check if there's an existing session
async function checkExistingSession() {
    if (!sessionId) return;
    
    try {
        const response = await fetch('/api/status/' + sessionId);
        const data = await response.json();
        
        if (data.success && data.connected) {
            connected = true;
            updateConnectionStatus(true, data.accountInfo);
            
            if (data.trading) {
                trading = true;
                updateBotStatus(true);
                document.getElementById('startBotBtn').disabled = true;
                document.getElementById('stopBotBtn').disabled = false;
            }
            
            document.getElementById('connectBtn').disabled = true;
        }
    } catch (error) {
        console.error('Session check failed:', error);
    }
}

// Connect to Deriv
async function connectToDeriv() {
    const apiToken = document.getElementById('apiToken').value.trim();
    
    if (!apiToken) {
        showNotification('Error', 'Please enter your API token', 'error');
        return;
    }
    
    // Show loading
    const connectBtn = document.getElementById('connectBtn');
    const btnText = connectBtn.querySelector('.btn-text');
    const btnLoader = connectBtn.querySelector('.btn-loader');
    
    btnText.style.display = 'none';
    btnLoader.style.display = 'inline';
    connectBtn.disabled = true;
    
    try {
        const response = await fetch('/api/connect', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                apiToken: apiToken,
                sessionId: sessionId
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Save session
            sessionId = data.sessionId;
            localStorage.setItem('karanka_session', sessionId);
            localStorage.setItem('deriv_api_token', apiToken);
            
            // Update UI
            connected = true;
            updateConnectionStatus(true, data.accountInfo);
            
            // Show account info
            document.getElementById('accountInfo').style.display = 'block';
            document.getElementById('accountId').textContent = data.accountInfo.loginid || '-';
            document.getElementById('accountBalance').textContent = data.accountInfo.balance || '-';
            document.getElementById('accountCurrency').textContent = data.accountInfo.currency || '-';
            document.getElementById('accountName').textContent = data.accountInfo.name || '-';
            
            // Enable start button
            document.getElementById('startBotBtn').disabled = false;
            
            showNotification('Success', 'Connected to Deriv successfully!', 'success');
            
            // Subscribe to socket room
            if (socket) {
                socket.emit('subscribe', sessionId);
            }
            
        } else {
            showNotification('Connection Failed', data.error || 'Invalid API token', 'error');
            connectBtn.disabled = false;
        }
        
    } catch (error) {
        console.error('Connection error:', error);
        showNotification('Error', 'Failed to connect to server', 'error');
        connectBtn.disabled = false;
    } finally {
        // Hide loader
        btnText.style.display = 'inline';
        btnLoader.style.display = 'none';
    }
}

// Start trading bot
async function startBot() {
    if (!connected) {
        showNotification('Error', 'Please connect to Deriv first', 'error');
        return;
    }
    
    // Get settings
    const config = {
        symbol: document.getElementById('symbolSelect').value,
        chosenDigit: parseInt(document.getElementById('chosenDigit').value),
        duration: parseInt(document.getElementById('duration').value),
        initialStake: parseFloat(document.getElementById('initialStake').value),
        maxTrades: parseInt(document.getElementById('maxTrades').value),
        tradeHours: parseFloat(document.getElementById('tradeHours').value),
        confidenceThreshold: parseInt(document.getElementById('confidenceThreshold').value),
        recoveryFactor: parseFloat(document.getElementById('recoveryFactor').value)
    };
    
    // Validate
    if (config.initialStake < 0.35) {
        showNotification('Error', 'Minimum stake is $0.35', 'error');
        return;
    }
    
    // Save settings
    localStorage.setItem('selected_symbol', config.symbol);
    localStorage.setItem('chosen_digit', config.chosenDigit);
    localStorage.setItem('initial_stake', config.initialStake);
    
    // Show loading on button
    const startBtn = document.getElementById('startBotBtn');
    startBtn.disabled = true;
    startBtn.textContent = '▶ STARTING...';
    
    try {
        const response = await fetch('/api/start-trading', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                sessionId: sessionId,
                config: config
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            trading = true;
            updateBotStatus(true);
            document.getElementById('stopBotBtn').disabled = false;
            
            // Set timeout if trade hours > 0
            if (config.tradeHours > 0) {
                setTimeout(() => {
                    if (trading) {
                        stopBot();
                        showNotification('Info', `Trading stopped after ${config.tradeHours} hours`, 'info');
                    }
                }, config.tradeHours * 60 * 60 * 1000);
            }
            
            showNotification('Success', 'Bot started successfully!', 'success');
            
            // Show live stats
            document.getElementById('liveStats').style.display = 'grid';
            document.getElementById('marketData').innerHTML = '';
            
        } else {
            showNotification('Error', data.error || 'Failed to start bot', 'error');
            startBtn.disabled = false;
        }
        
    } catch (error) {
        console.error('Start bot error:', error);
        showNotification('Error', 'Failed to start bot', 'error');
        startBtn.disabled = false;
    } finally {
        startBtn.textContent = '▶ START';
    }
}

// Stop trading bot
async function stopBot() {
    if (!trading) return;
    
    const stopBtn = document.getElementById('stopBotBtn');
    stopBtn.disabled = true;
    stopBtn.textContent = '⏹ STOPPING...';
    
    try {
        const response = await fetch('/api/stop-trading', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                sessionId: sessionId
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            trading = false;
            updateBotStatus(false);
            document.getElementById('startBotBtn').disabled = false;
            showNotification('Info', 'Bot stopped', 'info');
        }
        
    } catch (error) {
        console.error('Stop bot error:', error);
        showNotification('Error', 'Failed to stop bot', 'error');
    } finally {
        stopBtn.textContent = '⏹ STOP';
    }
}

// Update connection status UI
function updateConnectionStatus(isConnected, accountInfo = null) {
    const statusEl = document.querySelector('.connection-status');
    const statusText = statusEl.querySelector('.status-text');
    const connectBtn = document.getElementById('connectBtn');
    
    if (isConnected) {
        statusEl.classList.add('connected');
        statusText.textContent = accountInfo ? `Connected: $${accountInfo.balance}` : 'Connected';
        connectBtn.disabled = true;
        connectBtn.textContent = '✓ CONNECTED';
    } else {
        statusEl.classList.remove('connected');
        statusText.textContent = 'Disconnected';
        connectBtn.disabled = false;
        connectBtn.textContent = 'CONNECT TO DERIV';
    }
}

// Update bot status UI
function updateBotStatus(isRunning) {
    const statusEl = document.querySelector('.bot-status');
    
    if (isRunning) {
        statusEl.classList.add('running');
        statusEl.innerHTML = '<span class="status-indicator"></span><span>Bot Running</span>';
    } else {
        statusEl.classList.remove('running');
        statusEl.innerHTML = '<span class="status-indicator"></span><span>Bot Stopped</span>';
    }
}

// Update live data display
function updateLiveData(data) {
    document.getElementById('lastDigit').textContent = data.tick.digit;
    document.getElementById('confidenceScore').textContent = data.confidence + '%';
}

// Update scores display
function updateScores(data) {
    // Could show individual scores in a tooltip or small display
}

// Update statistics
function updateStats(data) {
    document.getElementById('statTrades').textContent = data.wins + data.losses;
    document.getElementById('statWins').textContent = data.wins;
    document.getElementById('statLosses').textContent = data.losses;
    
    const winRate = data.wins + data.losses > 0 
        ? ((data.wins / (data.wins + data.losses)) * 100).toFixed(1)
        : 0;
    document.getElementById('statWinRate').textContent = winRate + '%';
    
    document.getElementById('statProfit').textContent = '$' + data.totalProfit.toFixed(2);
    document.getElementById('statCurrentStake').textContent = '$' + data.newStake.toFixed(2);
    document.getElementById('patternPos').textContent = data.consecutiveLosses || 0;
}

// Show notification (mobile-friendly)
function showNotification(title, message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <strong>${title}</strong>
        <p>${message}</p>
    `;
    
    // Add to body
    document.body.appendChild(notification);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.remove();
    }, 3000);
}

// Add notification styles (dynamic)
const style = document.createElement('style');
style.textContent = `
    .notification {
        position: fixed;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        background: var(--black-tertiary);
        border: 2px solid var(--gold-primary);
        color: var(--text-primary);
        padding: 15px;
        border-radius: 10px;
        z-index: 1000;
        max-width: 300px;
        animation: slideDown 0.3s ease;
    }
    
    .notification.success {
        border-color: var(--success);
    }
    
    .notification.error {
        border-color: var(--error);
    }
    
    .notification.warning {
        border-color: var(--warning);
    }
    
    @keyframes slideDown {
        from {
            top: -100px;
            opacity: 0;
        }
        to {
            top: 20px;
            opacity: 1;
        }
    }
`;
document.head.appendChild(style);
