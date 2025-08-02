import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from a .env file if it exists
load_dotenv()

# --- Placeholder for later configuration loading ---
# Will be loaded after DATA_DIR is set up

# --- Server & Socket Configuration ---
SOCKET_HOST: str = '0.0.0.0'
SOCKET_PORT: int = int(os.environ.get("PORT", 5556))

# --- Trading Parameters & Constants ---
MESSAGE_RETENTION_LIMIT: int = 5  # Example value, adjust as needed
STARTING_SIZE: float = 10000.0
DAILY_LOSS_LIMIT: float = 0.05
MINIMUM_STAKE: float = 0.4

# --- Decision Engine Configuration ---
# Core Strategy Parameters
BASE_GROWTH_RATE: float = 1.0  # The foundational growth rate (%)
BASE_TAKE_PROFIT: float = 1.5  # The foundational take-profit level (%)
N_PERIODS: int = 1800  # Lookback period for calculating volatility and mean return
LOSS_THRESHOLD: int = 10  # Number of consecutive losses that triggers Drawdown Response Protocol
LIQUIDITY_MIN_VOLUME: float = 1000.0  # Minimum trade volume over the last M hours
SANITY_FACTOR: int = 5  # Value by which LOSS_THRESHOLD is temporarily increased if no better index found
CONFIRM_TIMEOUT: int = 15  # Timeout in seconds for admin confirmation
DRAW_LIMIT: float = 10.0  # Maximum tolerable loss for a single trade as multiple of take_profit
LEARNING_INTERVAL: int = 5000  # Number of trades between meta-optimization cycles

# --- Trading Modes Configuration ---
# Continuous Mode Settings
CONSECUTIVE_WIN_THRESHOLD: int = 10  # Wins needed to trigger risk reduction
DAILY_PROFIT_TARGET_MIN: float = 3.0  # Minimum daily profit target (%)
DAILY_PROFIT_TARGET_MAX: float = 5.0  # Maximum daily profit target (%)
ADDITIONAL_PROFIT_BUFFER: float = 2.0  # Additional profit before final stop (%)
CONTINUOUS_RISK_REDUCTION: float = 0.7  # Risk reduction factor after win streak

# Recovery Mode Settings  
RECOVERY_RISK_MULTIPLIER: float = 1.8  # Risk multiplier for recovery mode
RECOVERY_FREQUENCY: str = "medium"  # Frequency for recovery trades
RECOVERY_MIN_TRADES: int = 3  # Minimum trades to attempt recovery
RECOVERY_MAX_TRADES: int = 15  # Maximum trades before reassessment
RECOVERY_SAFETY_MARGIN: float = 1.2  # Safety margin for recovery calculations

# Volatility Scaling Parameters
G_EXPONENT: float = 0.5  # Exponent for growth rate scaling
P_EXPONENT: float = 0.5  # Exponent for take profit scaling
G_MIN: float = 0.1  # Minimum growth scaling factor
G_MAX: float = 5.0  # Maximum growth scaling factor  
P_MIN: float = 0.1  # Minimum profit scaling factor
P_MAX: float = 5.0  # Maximum profit scaling factor

# Universe of tradeable indices (expanded from VALID_INDICES for decision engine)
UNIVERSE_INDICES = [
    "R_10", "R_25", "R_50", "R_75", "R_100",
    "1HZ10V", "1HZ25V", "1HZ50V", "1HZ75V", "1HZ100V"
]

# Return calculation method
RETURN_DEFINITION = "simple"  # "simple" for (price_t - price_{t-1}) / price_{t-1}

# --- File & Directory Paths ---
# Use appropriate data directory based on environment with robust error handling
import tempfile

def setup_data_directory():
    """Set up data directory with comprehensive error handling"""
    # Try different directory options in order of preference
    directory_options = [
        ("relative_data", Path("data")),
        ("home_data", Path.home() / ".decter_data"),
        ("tmp_data", Path("/tmp/decter_data")),
        ("temp_data", Path(tempfile.gettempdir()) / "decter_data")
    ]
    
    for option_name, data_path in directory_options:
        try:
            data_path.mkdir(parents=True, exist_ok=True)
            # Test write permissions
            test_file = data_path / "test_write.tmp"
            test_file.write_text("test")
            test_file.unlink()
            print(f"✅ Using data directory ({option_name}): {data_path}")
            return data_path
        except (PermissionError, OSError) as e:
            print(f"⚠️ Cannot use {option_name} ({data_path}): {e}")
            continue
    
    # Final fallback: use temporary directory
    temp_dir = Path(tempfile.mkdtemp(prefix="decter_data_"))
    print(f"🔄 Fallback: Using temporary data directory: {temp_dir}")
    return temp_dir

# Set up data directory
DATA_DIR = setup_data_directory()

# --- Configuration Loading Functions ---
import json

def load_web_config():
    """Load configuration from web interface settings"""
    try:
        # Try to load from telegram_config.json (set via web interface)
        config_file = DATA_DIR / "telegram_config.json"
        if config_file.exists():
            with open(config_file, 'r') as f:
                web_config = json.load(f)
            return web_config
    except Exception:
        pass
    return {}

def load_deriv_config():
    """Load Deriv API configuration from web interface"""
    try:
        # Try to load from deriv_config.json (set via web interface)
        config_file = DATA_DIR / "deriv_config.json"
        if config_file.exists():
            with open(config_file, 'r') as f:
                deriv_config = json.load(f)
            return deriv_config
    except Exception:
        pass
    return {}

# Load configurations from web interface
web_config = load_web_config()
deriv_config = load_deriv_config()

# --- Core Configuration ---
# Priority: Web interface > Environment variables > Default values
BOT_TOKEN: str = web_config.get("telegram_bot_token") or os.getenv("BOT_TOKEN") or ""
GROUP_ID: str = web_config.get("telegram_group_id") or os.getenv("GROUP_ID") or ""
TOPIC_ID: str = web_config.get("telegram_topic_id") or os.getenv("TOPIC_ID") or ""

DERIV_APP_ID: str = deriv_config.get("deriv_app_id") or os.getenv("DERIV_APP_ID") or ""

# --- API Tokens for different currencies ---
# Load from web interface or environment variables
def get_currency_token(currency: str) -> str:
    """Get currency token from web interface or environment"""
    return deriv_config.get(f"{currency.lower()}_api_token") or os.getenv(f"{currency}_API_TOKEN") or ""

CURRENCY_API_TOKENS: dict[str, str] = {
    'XRP': get_currency_token('XRP'),
    'BTC': get_currency_token('BTC'),
    'ETH': get_currency_token('ETH'),
    'LTC': get_currency_token('LTC'),
    'USDT': get_currency_token('USDT'),
    'USD': get_currency_token('USD')
}

TRADING_STATS_FILE = DATA_DIR / 'trading_stats.json'
TRADE_RECORDS_FILE = DATA_DIR / 'trade_records.json'
SAVED_PARAMS_FILE = DATA_DIR / 'saved_params.json'
LOG_FILE = DATA_DIR / 'trading_bot.log'
VERSION_FILE = DATA_DIR / 'version.json'

# --- Decision Engine Files ---
DECISION_ENGINE_STATE_FILE = DATA_DIR / 'decision_engine_state.json'
META_LEARNING_DATA_FILE = DATA_DIR / 'meta_learning_data.json'
MARKET_DATA_CACHE_FILE = DATA_DIR / 'market_data_cache.json'
VOLATILITY_REFERENCE_FILE = DATA_DIR / 'volatility_reference.json'

# --- Predefined Lists & Dictionaries ---
VALID_INDICES = {
    "R_10", "R_25", "R_50", "R_75", "R_100",
    "1HZ10V", "1HZ25V", "1HZ50V", "1HZ75V", "1HZ100V"
}

_SNARKY_REMARKS = [
    "Trading requires discipline.",
    "Markets are not casinos.",
    "Focus on strategy, not luck.",
    "Risk management is essential.",
    "Stay objective, stay profitable."
]

_STARTUP_LINES = [
    "Decter-001 online",
    "Decter-001 operational",
    "Decter-001 active",
    "Decter-001 initialized",
    "Decter-001 ready"
]

def validate_env_vars():
    """
    Validates that all required configuration is set.
    Returns True if valid, False if missing config.
    """
    required_vars = {
        "BOT_TOKEN": BOT_TOKEN,
        "DERIV_APP_ID": DERIV_APP_ID,
        "XRP_API_TOKEN": CURRENCY_API_TOKENS.get('XRP'),
        "GROUP_ID": GROUP_ID,
        "TOPIC_ID": TOPIC_ID
    }

    missing_vars = [var for var, value in required_vars.items() if not value]
    if missing_vars:
        error_msg = f"Missing required configuration: {', '.join(missing_vars)}"
        print(f"⚠️ WARNING: {error_msg}")
        print("📝 Please configure these settings through the TARC Lighthouse web interface:")
        print("   1. Navigate to Decter Engine in the sidebar")
        print("   2. Set up Telegram configuration (Bot Token, Group ID, Topic ID)")
        print("   3. Set up Deriv configuration (App ID and API tokens)")
        print("   4. Restart the Decter Engine service")
        print("🔄 Engine will retry every 30 seconds until configured...")
        return False

    print("INFO: All required environment variables are set.")

# You can run this validation at the start of your main application
if __name__ == '__main__':
    try:
        validate_env_vars()
        print("\nConfiguration check passed.")
        print(f"Data directory: {DATA_DIR.resolve()}")
    except EnvironmentError as e:
        print(f"\nConfiguration check failed: {e}")