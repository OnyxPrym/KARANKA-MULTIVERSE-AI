const express = require('express');
const cors = require('cors');
const path = require('path');
const http = require('http');
const socketIo = require('socket.io');
const DerivClient = require('./deriv-client');
const TradingEngine = require('./trading-engine');
require('dotenv').config();

const app = express();
const server = http.createServer(app);
const io = socketIo(server, {
  cors: {
    origin: "*",
    methods: ["GET", "POST"]
  }
});

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, '../frontend')));

// Store active sessions
const activeSessions = new Map();

// API Routes
app.post('/api/connect', async (req, res) => {
  try {
    const { apiToken, sessionId } = req.body;
    
    // Create new Deriv client
    const derivClient = new DerivClient(apiToken, process.env.DERIV_APP_ID);
    
    // Attempt to connect
    const connected = await derivClient.connect();
    
    if (!connected) {
      return res.status(401).json({ 
        success: false, 
        error: 'Failed to connect to Deriv. Invalid API token.' 
      });
    }
    
    // Get account info
    const accountInfo = await derivClient.getAccountInfo();
    
    // Create session
    const newSessionId = sessionId || Date.now().toString();
    
    activeSessions.set(newSessionId, {
      client: derivClient,
      engine: null,
      trading: false,
      accountInfo
    });
    
    res.json({
      success: true,
      sessionId: newSessionId,
      accountInfo
    });
    
  } catch (error) {
    console.error('Connection error:', error);
    res.status(500).json({ 
      success: false, 
      error: error.message 
    });
  }
});

app.post('/api/disconnect', async (req, res) => {
  const { sessionId } = req.body;
  
  const session = activeSessions.get(sessionId);
  if (session) {
    if (session.trading) {
      session.engine?.stop();
    }
    await session.client.disconnect();
    activeSessions.delete(sessionId);
  }
  
  res.json({ success: true });
});

app.post('/api/start-trading', async (req, res) => {
  const { sessionId, config } = req.body;
  
  const session = activeSessions.get(sessionId);
  if (!session) {
    return res.status(404).json({ 
      success: false, 
      error: 'Session not found' 
    });
  }
  
  if (session.trading) {
    return res.status(400).json({ 
      success: false, 
      error: 'Trading already active' 
    });
  }
  
  // Create trading engine
  const engine = new TradingEngine(session.client, config, io, sessionId);
  
  // Start trading
  await engine.start();
  
  session.engine = engine;
  session.trading = true;
  session.config = config;
  
  res.json({ 
    success: true, 
    message: 'Trading started successfully' 
  });
});

app.post('/api/stop-trading', async (req, res) => {
  const { sessionId } = req.body;
  
  const session = activeSessions.get(sessionId);
  if (session && session.trading) {
    await session.engine.stop();
    session.trading = false;
  }
  
  res.json({ success: true });
});

app.get('/api/status/:sessionId', (req, res) => {
  const session = activeSessions.get(req.params.sessionId);
  
  if (!session) {
    return res.status(404).json({ 
      success: false, 
      error: 'Session not found' 
    });
  }
  
  res.json({
    success: true,
    connected: true,
    trading: session.trading,
    accountInfo: session.accountInfo,
    config: session.config || null,
    stats: session.engine?.getStats() || null
  });
});

// Health check endpoint (keeps Render awake)
app.get('/health', (req, res) => {
  res.status(200).send('OK');
});

// Socket.IO connection for real-time updates
io.on('connection', (socket) => {
  console.log('Client connected:', socket.id);
  
  socket.on('subscribe', (sessionId) => {
    socket.join(`session-${sessionId}`);
  });
  
  socket.on('disconnect', () => {
    console.log('Client disconnected:', socket.id);
  });
});

// Start server
const PORT = process.env.PORT || 10000;
server.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 Karanka Algo Trader running on port ${PORT}`);
  console.log(`📱 Mobile WebApp available at http://localhost:${PORT}`);
});

// Keep-alive mechanism (prevents Render from sleeping)
setInterval(() => {
  // Ping self every 5 minutes
  if (process.env.RENDER) {
    const https = require('https');
    https.get(`https://${process.env.RENDER_EXTERNAL_URL}/health`);
  }
}, 300000);
