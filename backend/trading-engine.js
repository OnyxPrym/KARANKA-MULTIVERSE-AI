class TradingEngine {
  constructor(derivClient, config, io, sessionId) {
    this.client = derivClient;
    this.config = config;
    this.io = io;
    this.sessionId = sessionId;
    
    // Trading state
    this.active = false;
    this.currentStake = config.initialStake;
    this.baseStake = config.initialStake;
    this.consecutiveLosses = 0;
    this.totalProfit = 0;
    this.tradesExecuted = 0;
    this.wins = 0;
    this.losses = 0;
    this.startTime = null;
    this.endTime = null;
    
    // Strategy data
    this.lastDigits = [];
    this.patternPosition = 1;
    this.patternList = [5,6,7,8,9,4,3,2,1,0,5,6,7,8,9,4,3,2,1,0];
    this.chosenDigit = config.chosenDigit || 5;
    
    // Score weights
    this.statsWeight = 2;      // 0-40 points
    this.patternWeight = 5;    // 0-30 points
    this.diffWeight = 30;      // 0-30 points
    this.threshold = 65;       // Minimum score to trade
    
    this.tickHandler = this.handleTick.bind(this);
  }

  async start() {
    if (this.active) return;
    
    this.active = true;
    this.startTime = Date.now();
    
    // Subscribe to ticks for selected symbol
    await this.client.subscribeTicks(this.config.symbol, this.tickHandler);
    
    // Get initial digit history
    const history = await this.client.getLastDigitList(this.config.symbol, 20);
    this.lastDigits = history.map(h => h.digit);
    
    this.emitUpdate('started', {
      message: 'Trading started',
      startTime: this.startTime
    });
    
    console.log('Trading engine started');
  }

  async stop() {
    this.active = false;
    await this.client.disconnect();
    this.emitUpdate('stopped', {
      message: 'Trading stopped',
      stats: this.getStats()
    });
    console.log('Trading engine stopped');
  }

  async handleTick(tick) {
    if (!this.active) return;
    
    // Update last digits
    this.lastDigits.push(tick.digit);
    if (this.lastDigits.length > 20) {
      this.lastDigits.shift();
    }
    
    // Calculate confidence score
    const score = this.calculateConfidence(tick.digit);
    
    // Emit tick update
    this.emitUpdate('tick', {
      tick,
      confidence: score,
      currentStake: this.currentStake,
      totalProfit: this.totalProfit
    });
    
    // Check if we should trade (score >= threshold)
    if (score >= this.threshold) {
      await this.executeTrade(tick, score);
    }
  }

  calculateConfidence(currentDigit) {
    // STRATEGY 1: Statistical Score (0-40)
    const frequency = this.lastDigits.filter(d => d === this.chosenDigit).length;
    const statsScore = frequency * this.statsWeight;
    
    // STRATEGY 2: Pattern Score (0-30)
    const patternPrediction = this.patternList[this.patternPosition - 1];
    const patternDiff = Math.abs(patternPrediction - this.chosenDigit);
    const patternScore = patternDiff * this.patternWeight;
    
    // STRATEGY 3: DIGITDIFF Score (0-30)
    const diffScore = (currentDigit === this.chosenDigit) ? this.diffWeight : 0;
    
    // Total score
    const totalScore = statsScore + patternScore + diffScore;
    
    // Emit scores
    this.emitUpdate('scores', {
      statsScore,
      patternScore,
      diffScore,
      totalScore,
      threshold: this.threshold
    });
    
    return totalScore;
  }

  async executeTrade(tick, confidence) {
    // Determine trade direction based on pattern
    const patternPrediction = this.patternList[this.patternPosition - 1];
    const direction = patternPrediction > this.chosenDigit ? 'DIGITOVER' : 'DIGITUNDER';
    
    // Prepare proposal
    const proposal = await this.client.proposeContract(
      this.currentStake,
      this.config.symbol,
      this.config.duration || 1,
      't',
      direction,
      this.chosenDigit,
      this.chosenDigit
    );
    
    if (!proposal.success) {
      this.emitUpdate('error', {
        error: 'Failed to create proposal',
        details: proposal.error
      });
      return;
    }
    
    // Execute buy
    const result = await this.client.buyContract(proposal);
    
    if (!result.success) {
      this.emitUpdate('error', {
        error: 'Failed to execute trade',
        details: result.error
      });
      return;
    }
    
    this.tradesExecuted++;
    
    // Wait for contract result (simplified - in production, you'd subscribe to contract updates)
    setTimeout(() => {
      // Simulate result (in production, check actual contract result)
      const win = Math.random() < 0.7; // 70% win rate for demo
      
      if (win) {
        this.handleWin(result.buyPrice);
      } else {
        this.handleLoss(result.buyPrice);
      }
      
      // Update pattern position
      this.patternPosition++;
      if (this.patternPosition > this.patternList.length) {
        this.patternPosition = 1;
      }
      
    }, 2000);
    
    this.emitUpdate('trade', {
      type: 'executed',
      direction,
      stake: this.currentStake,
      confidence,
      proposal,
      result
    });
  }

  handleWin(profit) {
    this.wins++;
    this.totalProfit += profit;
    this.consecutiveLosses = 0;
    this.currentStake = this.baseStake;
    
    this.emitUpdate('trade_result', {
      result: 'win',
      profit,
      totalProfit: this.totalProfit,
      newStake: this.currentStake,
      wins: this.wins,
      losses: this.losses
    });
  }

  handleLoss(loss) {
    this.losses++;
    this.totalProfit -= loss;
    this.consecutiveLosses++;
    
    // Conservative stake increase (0.25 × loss)
    this.currentStake += loss * 0.25;
    
    this.emitUpdate('trade_result', {
      result: 'loss',
      loss,
      totalProfit: this.totalProfit,
      newStake: this.currentStake,
      wins: this.wins,
      losses: this.losses,
      consecutiveLosses: this.consecutiveLosses
    });
  }

  getStats() {
    return {
      active: this.active,
      totalProfit: this.totalProfit,
      tradesExecuted: this.tradesExecuted,
      wins: this.wins,
      losses: this.losses,
      winRate: this.tradesExecuted > 0 ? (this.wins / this.tradesExecuted * 100).toFixed(1) : 0,
      currentStake: this.currentStake,
      consecutiveLosses: this.consecutiveLosses,
      uptime: this.startTime ? Date.now() - this.startTime : 0
    };
  }

  emitUpdate(event, data) {
    if (this.io) {
      this.io.to(`session-${this.sessionId}`).emit(event, {
        ...data,
        timestamp: Date.now()
      });
    }
  }
}

module.exports = TradingEngine;
