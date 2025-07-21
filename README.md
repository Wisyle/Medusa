# ComboLogger - Cryptocurrency Bot Monitoring System

A production-ready Python application for monitoring Bitsgap trading bots across multiple cryptocurrency exchanges with real-time notifications and web-based administration.

## Features

- **Multi-Exchange Support**: Binance Futures, Bybit, OKX, KuCoin, MEXC, Gate.io, Coinbase Pro, Bitfinex
- **Strategy Monitoring**: DCA, Grid, Combo, Loop, BTD, DCA Futures, AIS Assisted
- **Web Admin Panel**: Create, configure, start/stop, and monitor bot instances
- **Real-time Notifications**: Telegram notifications with beautiful Unicode formatting
- **Webhook Integration**: Structured JSON payloads for external systems
- **Change Detection**: SQLite-based state tracking for positions, orders, and trades
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
DATABASE_URL=sqlite:///./combologger.db

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

- `GET /api/health` - System health check
- `GET /api/instances` - List all bot instances
- `POST /api/instances` - Create new instance
- `POST /api/instances/{id}/start` - Start instance
- `POST /api/instances/{id}/stop` - Stop instance
- `DELETE /api/instances/{id}` - Delete instance
- `GET /api/instances/{id}/logs` - Get instance logs

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
sudo cp combologger.service /etc/systemd/system/
sudo systemctl enable combologger
sudo systemctl start combologger
```

### Docker Deployment
```bash
docker build -t combologger .
docker run -d -p 8000:8000 --env-file .env combologger
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
