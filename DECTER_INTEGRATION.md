# Decter 001 Integration for TARC Lighthouse

This integration allows you to control your Decter 001 trading bot directly from the TARC Lighthouse web interface, providing unified management of all your trading systems.

## 🎯 Overview

The Decter 001 integration adds a dedicated **Decter Engine** section to your TARC Lighthouse dashboard, enabling you to:

- **🎮 Control**: Start, stop, and restart Decter 001 from the web interface
- **⚙️ Configure**: Set trading parameters, limits, and strategy options
- **📊 Monitor**: Real-time status, performance metrics, and trade history
- **📱 Command**: Send Telegram-like commands directly through the UI
- **📈 Analyze**: View detailed statistics and system logs

## 🚀 Features

### Control Panel
- **Process Management**: Start/stop/restart Decter 001 with one click
- **Status Monitoring**: Real-time process status and uptime tracking
- **Error Handling**: Graceful shutdown and error recovery

### Trading Configuration
- **Parameter Setup**: Configure stake, growth rate, take profit, trading pairs
- **Risk Management**: Set maximum loss and win limits
- **Exchange Settings**: Select trading indices and currencies
- **Mode Selection**: Switch between continuous and recovery modes

### Real-time Monitoring
- **Live Statistics**: Total trades, win rate, P&L, growth percentage
- **Performance Metrics**: Real-time updates every 5 seconds
- **Trade History**: Recent trades with detailed information
- **System Logs**: Live log streaming with error tracking

### Quick Commands
- Send common commands like "status", "history", "start trading", "stop trading"
- Export trading data and reports
- Reset statistics and engine state

## 📦 Installation

### Prerequisites
- TARC Lighthouse system running
- Decter 001 bot installed at `/mnt/c/users/rober/downloads/001`
- Python 3.8+ with required dependencies

### Setup Steps

1. **Verify Integration Files**
   ```bash
   cd /mnt/c/users/rober/downloads/tarc
   python setup_decter_integration.py
   ```

2. **Start TARC Lighthouse**
   ```bash
   python main.py
   ```

3. **Access Decter Engine**
   - Open your browser to the TARC Lighthouse dashboard
   - Login with your credentials
   - Click "🤖 Decter Engine" in the sidebar navigation

## 🔧 Configuration

### Decter Path Configuration
If your Decter 001 installation is in a different location, update the path in `decter_controller.py`:

```python
# Update this line with your Decter 001 path
def __init__(self, decter_path: str = "/your/custom/path/to/decter001"):
```

### Environment Variables
No additional environment variables are required. The integration uses the existing TARC Lighthouse authentication and database.

## 🎮 Usage Guide

### Starting Decter 001
1. Navigate to **Decter Engine** in the sidebar
2. Click the **▶️ Start Engine** button
3. Monitor the status indicator for successful startup
4. Configure trading parameters if needed
5. Click **▶️ Start Trading** to begin automated trading

### Configuring Parameters
1. Fill out the **Trading Parameters** form:
   - **Stake Amount**: Minimum 0.4 XRP
   - **Growth Rate**: 1-5% (Deriv API requirement)
   - **Take Profit**: Percentage for profit taking
   - **Index**: Select volatility index (R_10, R_25, etc.)
   - **Currency**: Choose trading currency
   - **Max Loss/Win**: Set risk management limits

2. Click **💾 Save Configuration** to apply

### Monitoring Performance
- **Metrics Dashboard**: View key performance indicators
- **Trade History**: Review recent trading activity
- **System Logs**: Monitor bot activity and errors
- **Status Panel**: Real-time process and trading status

### Sending Commands
Use the **Quick Commands** section to:
- Check bot status
- View trading history
- Start/stop trading
- Export data and reports

## 🔌 API Endpoints

The integration adds the following REST API endpoints:

### Control Endpoints
- `POST /api/decter/start` - Start Decter 001 bot
- `POST /api/decter/stop` - Stop Decter 001 bot
- `POST /api/decter/restart` - Restart Decter 001 bot

### Configuration Endpoints
- `GET /api/decter/config` - Get current configuration
- `POST /api/decter/config` - Update configuration
- `GET /api/decter/indices` - Get available trading indices
- `GET /api/decter/currencies` - Get available currencies

### Data Endpoints
- `GET /api/decter/status` - Get comprehensive status
- `GET /api/decter/performance` - Get performance summary
- `GET /api/decter/stats` - Get detailed statistics
- `GET /api/decter/trades` - Get trade history
- `GET /api/decter/logs` - Get system logs

### Command Endpoints
- `POST /api/decter/command` - Send command to bot

## 🛡️ Security

- **Authentication**: All endpoints require TARC Lighthouse login
- **Authorization**: Uses existing user session management
- **Process Isolation**: Decter 001 runs in separate process
- **Safe Operations**: Graceful shutdown and error handling

## 🔧 Troubleshooting

### Common Issues

**1. Decter 001 Not Found**
- Verify the Decter 001 installation path
- Update `decter_controller.py` with correct path
- Ensure all Decter 001 files are present

**2. Cannot Start Decter 001**
- Check system logs for error messages
- Verify Python environment and dependencies
- Ensure no other Decter 001 instance is running

**3. API Endpoints Not Working**
- Verify TARC Lighthouse is running
- Check browser console for JavaScript errors
- Ensure user is properly authenticated

**4. Real-time Updates Not Working**
- Check network connectivity
- Verify JavaScript is enabled
- Refresh the browser page

### Debug Mode
Enable detailed logging by setting log level to DEBUG in `decter_controller.py`:

```python
logging.basicConfig(level=logging.DEBUG)
```

### Health Checks
- **Integration Health**: `GET /api/decter/health`
- **Process Status**: Check if Decter 001 process is running
- **File System**: Verify all required files exist

## 📊 Architecture

### Components

1. **DecterController** (`decter_controller.py`)
   - Manages Decter 001 process lifecycle
   - Handles configuration and parameter management
   - Provides status monitoring and log access

2. **DecterRoutes** (`decter_routes.py`)
   - FastAPI router with REST endpoints
   - Authentication and authorization middleware
   - Request/response validation with Pydantic

3. **DecterEngine UI** (`templates/decter_engine.html`)
   - Responsive web interface with Bootstrap
   - Real-time updates with JavaScript
   - Interactive forms and control panels

### Data Flow
1. **User Interaction**: Web UI sends AJAX requests
2. **API Processing**: FastAPI routes handle requests
3. **Controller Action**: DecterController manages bot operations
4. **Bot Communication**: Subprocess management and file I/O
5. **Response**: Status and data returned to UI

## 🔄 Updates and Maintenance

### Updating the Integration
1. Backup current configuration
2. Update integration files
3. Restart TARC Lighthouse
4. Verify functionality

### Monitoring Health
- Regular status checks via health endpoints
- Monitor system logs for errors
- Track performance metrics over time

## 📝 Development

### Adding Features
1. **New API Endpoints**: Add to `decter_routes.py`
2. **UI Components**: Update `templates/decter_engine.html`
3. **Controller Methods**: Extend `decter_controller.py`

### Testing
```bash
# Test integration setup
python setup_decter_integration.py

# Test API endpoints
curl http://localhost:8000/api/decter/health

# Test web interface
# Visit http://localhost:8000/decter-engine
```

## 🎉 Success!

You now have unified control over both your TARC Lighthouse monitoring system and your Decter 001 trading bot from a single, powerful web interface. 

**Happy Trading!** 🚀