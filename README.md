# TGL MEDUSA - Cryptocurrency Bot Monitoring System

A production-ready Python application for monitoring Tar Global trading bots across multiple cryptocurrency exchanges with real-time notifications, web-based administration, and advanced strategy-level aggregation.

## Features

- **Multi-Exchange Support**: Binance Futures, Bybit, OKX, KuCoin, MEXC, Gate.io, Coinbase Pro, Bitfinex
- **Strategy Monitoring**: DCA, Grid, Combo, Loop, BTD, DCA Futures, AIS Assisted
- **Strategy Monitor System**: Aggregate performance data across multiple instances by strategy
- **Web Admin Panel**: Create, configure, start/stop, and monitor bot instances
- **Real-time Notifications**: Telegram notifications with beautiful Unicode formatting
- **Advanced Reporting**: Strategy-level PnL tracking, position summaries, trade analytics
- **Webhook Integration**: Structured JSON payloads for external systems
- **Change Detection**: PostgreSQL/SQLite-based state tracking for positions, orders, and trades
- **Multi-Instance Management**: Run multiple bot instances simultaneously
- **Health Monitoring**: System health checks and error logging

## Installation

### Prerequisites

- Python 3.8+
- pip or poetry for package management

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd combologger
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Initialize database**
   ```bash
   python -c "from database import init_db; init_db()"
   ```

## Configuration

### Environment Variables (.env)

```env
# Database Configuration
DATABASE_URL=sqlite:///./tgl_medusa.db

# Admin Panel Authentication
ADMIN_USERNAME=admin
ADMIN_PASSWORD=changeme123

# Default Telegram Configuration
DEFAULT_TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
DEFAULT_TELEGRAM_CHAT_ID=your_chat_id_here

# Security
SECRET_KEY=your-secret-key-here

# Application Settings
DEBUG=True
HOST=0.0.0.0
PORT=8000

# Webhook Settings
WEBHOOK_SECRET=your-webhook-secret
```

### Exchange API Keys

For each bot instance, you'll need:
- **API Key**: Read-only API key from your exchange
- **API Secret**: Corresponding secret
- **API Passphrase**: Required for OKX and KuCoin only

⚠️ **Security Note**: Only use read-only API keys. Never use keys with trading permissions.

## Usage

### Starting the Application

```bash
python main.py
```

The application will start on `http://localhost:8000` (or your configured host/port).

### Web Admin Panel

1. **Access the dashboard**: Navigate to `http://localhost:8000`
2. **Login**: Use the credentials from your `.env` file
3. **Create instances**: Go to "New Instance" to configure bot monitoring
4. **Monitor activity**: View real-time status, logs, and health metrics

### API Endpoints

#### Core System
- `GET /api/health` - System health check
- `GET /api/strategy-monitor-health` - Strategy monitor health check

#### Bot Instances
- `GET /api/instances` - List all bot instances
- `POST /api/instances` - Create new instance
- `POST /api/instances/{id}/start` - Start instance
- `POST /api/instances/{id}/stop` - Stop instance
- `DELETE /api/instances/{id}` - Delete instance
- `GET /api/instances/{id}/logs` - Get instance logs

#### Strategy Monitors
- `GET /strategy-monitors` - Strategy monitor management page
- `GET /api/strategy-monitors` - List all strategy monitors
- `POST /strategy-monitors` - Create new strategy monitor
- `PUT /strategy-monitors/{id}` - Update strategy monitor
- `DELETE /strategy-monitors/{id}` - Delete strategy monitor
- `POST /strategy-monitors/{id}/toggle` - Toggle monitor active status
- `POST /strategy-monitors/{id}/test-report` - Send test report

## Strategy Monitor System

The Strategy Monitor System provides high-level aggregation and reporting across multiple bot instances running the same strategy.

### Features
- **Strategy-Level Aggregation**: Combines data from all instances running the same strategy
- **Comprehensive Reporting**: PnL tracking, position summaries, order/trade analytics
- **Beautiful Telegram Reports**: Professional formatting with Unicode emojis and code blocks
- **Configurable Intervals**: Reports every 30 minutes to 24 hours
- **No API Keys Required**: Uses existing instance data
- **Error Tracking**: Monitors and reports system health

### Sample Strategy Report
```
🎯 **Scalping Strategy Monitor** - 2024-12-19 15:30:00 UTC

📈 **Overview**
• Active Instances: 3
• Total PnL (24h): $+1,247.50
• Active Positions: 8
• Active Orders: 12
• Trades (24h): 156
• Volume (24h): $89,450.25

🏢 **Instances**
  1. `BTC-Scalper-1` - bybit
  2. `ETH-Scalper-2` - bybit
  3. `SOL-Scalper-3` - bybit

💰 **PnL by Symbol (24h)**
```
🟢 BTC/USDT:USDT    $+487.25
🟢 ETH/USDT:USDT    $+325.80
🔴 SOL/USDT:USDT     $-45.30
```

🎯 **Active Positions** (8)
```
🟢 BTC/USDT     long    0.0045 @$97,245.50
🔴 ETH/USDT     short   0.1250 @$3,845.20
```

📊 **Monitoring Active** | Next Report: 16:30:00
```

### Setup Strategy Monitor
1. Navigate to **Strategy Monitors** in the web interface
2. Select a strategy from your active instances
3. Configure Telegram bot token and chat ID
4. Set reporting interval and features
5. Save and monitor will start automatically

## Bot Instance Configuration

### Basic Settings
- **Name**: Descriptive name for the instance
- **Exchange**: Target cryptocurrency exchange
- **Polling Interval**: How often to check for changes (30-300 seconds)

### Strategy Selection
Choose which strategies to monitor:
- DCA (Dollar Cost Average)
- Grid Trading
- Combo Strategy
- Loop Strategy
- BTD (Buy The Dip)
- DCA Futures
- AIS Assisted

Leave all unchecked to monitor all strategies.

### Notifications

#### Telegram Setup
1. Create a bot with [@BotFather](https://t.me/BotFather)
2. Get your chat ID from [@userinfobot](https://t.me/userinfobot)
3. Add the bot to your group/channel
4. Configure bot token and chat ID in the instance

#### Webhook Configuration
- Set webhook URL to receive JSON payloads
- Payloads include event type, symbol, prices, quantities, and timestamps

## Notification Templates

The system sends beautifully formatted Telegram notifications:

### Order Filled
```
TARCXXX, [2024-01-15 02:30 PM]
📈 Order Filled - 2024-01-15 02:30 PM

🤖 Bot: BTC-Grid-Bot
💱 Pair: BTC/USDT
🛡️ Event: Order Filled

Side: Buy
Quantity: 0.0015 @ $42,500.00
Status: Filled
Unrealized PnL: $12.50
Bot Type: Grid

✅ Transaction complete.
```

### Position Update
```
TARCXXX, [2024-01-15 02:30 PM]
🔄 Position Change Detected - 2024-01-15 02:30 PM

🤖 Bot: BTC-Grid-Bot
💱 Pair: BTC/USDT
🛡️ Event: Position Update

New Size: 0.0025
Entry Price: $42,500.00
Unrealized PnL: $25.75
Side: Long
Bot Type: Grid

📊 Monitoring continues.
```

## Architecture

### Core Components

1. **Main Application** (`main.py`)
   - FastAPI web server
   - Admin panel routes
   - API endpoints
   - Process management

2. **Polling Engine** (`polling.py`)
   - Exchange integration via ccxt
   - Change detection logic
   - Notification delivery
   - Error handling

3. **Database Layer** (`database.py`)
   - SQLAlchemy models
   - State management
   - Activity logging

4. **Web Interface** (`templates/`)
   - Bootstrap-based admin panel
   - Real-time dashboard
   - Instance management

### Data Flow

1. **Configuration**: Admin creates bot instances via web panel
2. **Polling**: Background processes monitor exchange APIs
3. **Detection**: Changes in positions/orders trigger events
4. **Notification**: Telegram messages and webhooks sent
5. **Logging**: All activity stored in database

## Deployment

### Local Development
```bash
python main.py
```

### Production Deployment
```bash
# Using systemd service
sudo cp tgl_medusa.service /etc/systemd/system/
sudo systemctl enable tgl_medusa
sudo systemctl start tgl_medusa
```

### Docker Deployment
```bash
docker build -t tgl-medusa-loggers .
docker run -d -p 8000:8000 --env-file .env tgl-medusa-loggers
```

## Troubleshooting

### Common Issues

1. **API Rate Limits**
   - Increase polling intervals
   - Use read-only API keys
   - Monitor exchange rate limit headers

2. **Telegram Notifications Not Working**
   - Verify bot token and chat ID
   - Check bot permissions in group/channel
   - Review error logs in admin panel

3. **Database Connection Issues**
   - Check DATABASE_URL in .env
   - Ensure SQLite file permissions
   - Initialize database if needed

4. **Process Management**
   - Monitor system resources
   - Check for zombie processes
   - Review application logs

### Logs and Monitoring

- **Activity Logs**: Track all bot events and notifications
- **Error Logs**: Capture exceptions and API failures
- **Health Endpoint**: `/api/health` for monitoring systems
- **Admin Dashboard**: Real-time status and metrics

## Security Considerations

- Use read-only API keys only
- Secure admin credentials
- Enable HTTPS in production
- Rotate webhook secrets regularly
- Monitor for unauthorized access

## Contributing

1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Submit pull request

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
- Check the troubleshooting section
- Review application logs
- Open GitHub issue with details
