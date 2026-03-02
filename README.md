# 🤖 Karanka Algo Deriv Matrix AI Trader

Advanced mobile-optimized trading bot for Deriv platform with weighted scoring strategy.

## ✨ Features

- 📱 Mobile-optimized webapp with gold/black theme
- 🔐 Secure Deriv API token authentication
- 📊 Weighted scoring system (65% confidence threshold)
- 🎯 Multiple market selection (R_100, 1HZ50V, etc.)
- ⚙️ Customizable stake, duration, and recovery factor
- 📈 Real-time market data and bot statistics
- 🛑 Stop loss and target profit protection
- 🔄 24/7 operation on Render (never sleeps)
- 📲 Install as PWA on mobile devices

## 🚀 Quick Start

### 1. Get Deriv API Token
- Log in to your Deriv account
- Go to Settings → API Token
- Create new token with "Trade" permissions
- Copy the token

### 2. Deploy on Render
1. Fork this repository
2. Create new Web Service on Render
3. Connect your repository
4. Set environment variables:
   - `DERIV_APP_ID`: Your Deriv app ID (contact Deriv support)
5. Deploy!

### 3. Use the App
- Open the deployed URL on your mobile
- Enter your API token
- Configure trading parameters
- Start trading!

## ⚙️ Configuration Options

| Setting | Description | Recommended |
|---------|-------------|-------------|
| Initial Stake | Amount per trade | $0.50 - $1.00 |
| Max Concurrent Trades | Number of simultaneous trades | 1 |
| Trading Duration | Hours to run (0 = unlimited) | 2-4 hours |
| Confidence Threshold | Minimum score to trade | 65% |
| Recovery Factor | Stake increase on loss | 0.25-0.5 |
| Chosen Digit | Target digit for strategy | 5 |

## 📊 Strategy Logic

The bot uses a weighted scoring system (0-100 points):
- **Statistical (40%)**: Frequency of chosen digit in last 20 ticks
- **Pattern (30%)**: Pre-programmed pattern prediction
- **DIGITDIFF (30%)**: Current digit matches chosen

Trades only when confidence ≥ 65%

## ⚠️ Risk Warning

Trading binary options involves substantial risk. Always:
- Start with small stakes
- Test on demo account first
- Never trade money you can't afford to lose
- Monitor bot performance regularly

## 📞 Support

For issues or questions, contact: [your-email]

## 📜 License

MIT License - Use at your own risk
