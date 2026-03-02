const WebSocket = require('ws');

class DerivClient {
  constructor(apiToken, appId) {
    this.apiToken = apiToken;
    this.appId = appId;
    this.ws = null;
    this.connected = false;
    this.accountInfo = null;
    this.reqId = 1;
    this.pendingRequests = new Map();
  }

  async connect() {
    return new Promise((resolve, reject) => {
      try {
        const wsUrl = `wss://ws.binaryws.com/websockets/v3?app_id=${this.appId}&l=EN&brand=deriv`;
        
        this.ws = new WebSocket(wsUrl);
        
        // Set timeout for connection
        const timeout = setTimeout(() => {
          reject(new Error('Connection timeout'));
        }, 10000);
        
        this.ws.on('open', async () => {
          console.log('WebSocket connected');
          
          // Authorize with API token
          try {
            const authResponse = await this.sendRequest({
              authorize: this.apiToken,
              req_id: this.reqId++
            });
            
            if (authResponse.error) {
              reject(new Error(authResponse.error.message));
              return;
            }
            
            this.connected = true;
            this.accountInfo = authResponse.authorize;
            
            // Get available markets
            await this.getActiveSymbols();
            
            clearTimeout(timeout);
            resolve(true);
            
          } catch (error) {
            clearTimeout(timeout);
            reject(error);
          }
        });
        
        this.ws.on('error', (error) => {
          console.error('WebSocket error:', error);
          reject(error);
        });
        
        this.ws.on('message', (data) => {
          const response = JSON.parse(data);
          
          // Handle subscription responses
          if (response.subscription) {
            // Handle tick data
            if (response.tick) {
              this.handleTick(response);
            }
          }
          
          // Handle request responses
          if (response.req_id && this.pendingRequests.has(response.req_id)) {
            const { resolve, reject } = this.pendingRequests.get(response.req_id);
            this.pendingRequests.delete(response.req_id);
            
            if (response.error) {
              reject(response.error);
            } else {
              resolve(response);
            }
          }
        });
        
      } catch (error) {
        reject(error);
      }
    });
  }

  sendRequest(request) {
    return new Promise((resolve, reject) => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        reject(new Error('WebSocket not connected'));
        return;
      }
      
      const reqId = request.req_id || this.reqId++;
      request.req_id = reqId;
      
      this.pendingRequests.set(reqId, { resolve, reject });
      this.ws.send(JSON.stringify(request));
      
      // Timeout for request
      setTimeout(() => {
        if (this.pendingRequests.has(reqId)) {
          this.pendingRequests.delete(reqId);
          reject(new Error('Request timeout'));
        }
      }, 5000);
    });
  }

  async getAccountInfo() {
    try {
      const response = await this.sendRequest({
        balance: 1,
        subscribe: 1,
        req_id: this.reqId++
      });
      
      return {
        balance: response.balance.balance,
        currency: response.balance.currency,
        loginid: this.accountInfo?.loginid,
        email: this.accountInfo?.email,
        name: this.accountInfo?.fullname
      };
    } catch (error) {
      console.error('Error getting account info:', error);
      return null;
    }
  }

  async getActiveSymbols() {
    try {
      const response = await this.sendRequest({
        active_symbols: 'brief',
        product_type: 'basic',
        req_id: this.reqId++
      });
      
      return response.active_symbols.filter(s => 
        s.market_display_name.includes('Synthetic') ||
        s.symbol.includes('R_') ||
        s.symbol.includes('1HZ')
      );
    } catch (error) {
      console.error('Error getting symbols:', error);
      return [];
    }
  }

  async subscribeTicks(symbol, callback) {
    this.tickCallback = callback;
    
    return this.sendRequest({
      ticks: symbol,
      subscribe: 1,
      req_id: this.reqId++
    });
  }

  handleTick(response) {
    if (this.tickCallback) {
      this.tickCallback({
        symbol: response.tick.symbol,
        price: response.tick.quote,
        epoch: response.tick.epoch,
        digit: parseInt(response.tick.quote.toString().slice(-1))
      });
    }
  }

  async buyContract(proposal) {
    try {
      const response = await this.sendRequest({
        buy: proposal.id,
        price: proposal.amount,
        req_id: this.reqId++
      });
      
      return {
        success: true,
        contractId: response.buy.contract_id,
        transactionId: response.buy.transaction_id,
        buyPrice: response.buy.buy_price,
        balanceAfter: response.buy.balance_after
      };
    } catch (error) {
      console.error('Error buying contract:', error);
      return {
        success: false,
        error: error.message
      };
    }
  }

  async proposeContract(amount, symbol, duration, durationType, contractType, barrier, prediction) {
    try {
      const proposal = {
        proposal: 1,
        amount: amount,
        basis: 'stake',
        contract_type: contractType,
        currency: 'USD',
        duration: duration,
        duration_unit: durationType,
        symbol: symbol,
        req_id: this.reqId++
      };
      
      // Add barrier/prediction for digit contracts
      if (contractType.includes('DIGIT')) {
        proposal.barrier = barrier;
        if (prediction !== undefined) {
          proposal.prediction = prediction;
        }
      }
      
      const response = await this.sendRequest(proposal);
      
      if (response.error) {
        return {
          success: false,
          error: response.error.message
        };
      }
      
      return {
        success: true,
        id: response.proposal.id,
        longCode: response.proposal.longcode,
        payout: response.proposal.payout,
        spot: response.proposal.spot,
        spotTime: response.proposal.spot_time
      };
      
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }

  async getLastDigitList(symbol, ticks) {
    try {
      const response = await this.sendRequest({
        ticks_history: symbol,
        end: 'latest',
        start: 1,
        style: 'ticks',
        count: ticks,
        req_id: this.reqId++
      });
      
      if (response.error) {
        return [];
      }
      
      return response.history.times.map((time, index) => ({
        time,
        price: response.history.prices[index],
        digit: parseInt(response.history.prices[index].toString().slice(-1))
      }));
      
    } catch (error) {
      console.error('Error getting tick history:', error);
      return [];
    }
  }

  async disconnect() {
    if (this.ws) {
      this.ws.close();
      this.connected = false;
    }
  }
}

module.exports = DerivClient;
