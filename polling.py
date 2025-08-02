import ccxt
import hashlib
import json
import time
import requests
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, DisconnectionError
from telegram import Bot
import logging

from database import SessionLocal, BotInstance, PollState, ActivityLog, ErrorLog, BalanceHistory
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ExchangePoller:
    def __init__(self, instance_id: int):
        self.instance_id = instance_id
        self.db = SessionLocal()
        self.instance = self.db.query(BotInstance).filter(BotInstance.id == instance_id).first()
        self.last_telegram_send = 0  # Rate limiting for Telegram
        
        if not self.instance:
            raise ValueError(f"Bot instance {instance_id} not found")
        
        # Get API credentials (either from library or direct)
        self.api_credentials = self.instance.get_api_credentials()
        if not self.api_credentials or not self.api_credentials.get('api_key') or not self.api_credentials.get('api_secret'):
            error_msg = f"Bot instance {instance_id} (user_id: {self.instance.user_id}) has no valid or accessible API credentials"
            logger.error(error_msg)
            # Log this error to the instance's error log
            self._log_error("api_credentials", error_msg)
            raise ValueError(error_msg)
        
        self.exchange = self._init_exchange()
        self.telegram_bot = self._init_telegram()
        
        # Initialize Bitget REST client for futures instances to bypass CCXT issues
        self.bitget_rest_client = None
        
        # Debug: Log the API credentials structure
        logger.info(f"🔍 [DEBUG] API credentials for instance {instance_id}: {dict(self.api_credentials) if self.api_credentials else None}")
        
        # Check for both 'passphrase' and 'api_passphrase' to support both direct and library credentials
        passphrase = self.api_credentials.get('passphrase') or self.api_credentials.get('api_passphrase')
        logger.info(f"🔍 [DEBUG] Passphrase found: {bool(passphrase)} (length: {len(passphrase) if passphrase else 0})")
        
        if (self.instance.exchange.lower() == 'bitget' and 
            self.instance.market_type == 'futures' and 
            passphrase):
            try:
                from rest_client import BitgetRESTClient
                self.bitget_rest_client = BitgetRESTClient(
                    self.api_credentials['api_key'],
                    self.api_credentials['api_secret'],
                    passphrase
                )
                logger.info("✅ [BITGET REST CLIENT] Initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Bitget REST client: {e}")
                self.bitget_rest_client = None
        else:
            # Debug: Log why the condition failed
            if self.instance.exchange.lower() != 'bitget':
                logger.info(f"🔍 [DEBUG] Exchange is {self.instance.exchange.lower()}, not 'bitget'")
            elif self.instance.market_type != 'futures':
                logger.info(f"🔍 [DEBUG] Market type is {self.instance.market_type}, not 'futures'")
            elif not self.api_credentials.get('passphrase'):
                passphrase_value = self.api_credentials.get('passphrase') if self.api_credentials else 'N/A'
                logger.info(f"🔍 [DEBUG] No passphrase found. Value: '{passphrase_value}'")
            
            logger.warning("Bitget REST client not initialized, falling back to CCXT")
        
    def _init_exchange(self) -> ccxt.Exchange:
        """Initialize exchange connection with advanced CloudFront bypass"""
        import os
        import random
        
        # Check if running on cloud hosting (Render, Heroku, etc.)
        is_cloud_hosting = any(env in os.environ for env in ['RENDER', 'HEROKU', 'RAILWAY', 'VERCEL'])
        if is_cloud_hosting:
            logger.info("🌐 Cloud hosting detected - using enhanced bypass methods")
        
        exchange_name = self.instance.exchange.lower()
        
        # For non-Bybit exchanges, use simpler generic configurations
        if exchange_name != 'bybit':
            return self._init_generic_exchange()
        
        # Bybit-specific CloudFront bypass logic continues below...
        # Alternative DNS servers for bypass
        dns_alternatives = [
            '8.8.8.8',      # Google DNS
            '1.1.1.1',      # Cloudflare DNS
            '208.67.222.222', # OpenDNS
            '9.9.9.9'       # Quad9 DNS
        ]
        
        # Updated IP pools for better CloudFront bypass (2025)
        singapore_ips = os.getenv('SINGAPORE_IP_POOL', '103.28.248.100,119.81.28.200,18.141.147.50,52.220.100.50,13.228.104.25,54.169.1.100,175.41.128.50,202.54.1.100').split(',')
        uae_ips = ['5.62.60.100', '5.62.61.200', '185.3.124.50', '185.3.125.100', '37.44.238.50', '109.123.116.200']
        hk_ips = ['103.10.197.100', '202.45.84.50', '210.6.4.100', '119.28.0.50', '103.254.155.100', '202.67.10.50']
        jp_ips = ['133.106.32.100', '210.173.160.50', '103.79.141.100', '202.32.115.50', '118.27.0.100', '210.148.59.50']
        us_ips = ['173.252.66.100', '69.171.224.50', '31.13.64.100', '157.240.1.50', '204.15.20.100']
        uk_ips = ['31.13.72.100', '157.240.15.50', '185.60.216.100', '173.252.88.50']
        
        selected_sg_ip = random.choice(singapore_ips)
        selected_uae_ip = random.choice(uae_ips)
        selected_hk_ip = random.choice(hk_ips)
        selected_jp_ip = random.choice(jp_ips)
        selected_us_ip = random.choice(us_ips)
        selected_uk_ip = random.choice(uk_ips)
        
        configs_to_try = [
            {
                'apiKey': self.api_credentials['api_key'],
                'secret': self.api_credentials['api_secret'],
                'sandbox': False,
                'enableRateLimit': True,
                'urls': {
                    'api': {
                        'public': 'https://api.bybit.com',
                        'private': 'https://api.bybit.com',
                    }
                },
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/json, text/plain, */*',
                    'Accept-Language': 'en-SG,zh-SG;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Origin': 'https://www.bybit.com',
                    'Referer': 'https://www.bybit.com/',
                    'Sec-Fetch-Site': 'same-site',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Dest': 'empty',
                    'X-Forwarded-For': selected_sg_ip,
                    'X-Real-IP': selected_sg_ip,
                    'CF-Connecting-IP': selected_sg_ip,
                    'X-Originating-IP': selected_sg_ip,
                    'X-Client-IP': selected_sg_ip,
                    'True-Client-IP': selected_sg_ip,
                    'X-Cluster-Client-IP': selected_sg_ip,
                    'X-Country-Code': 'SG',
                    'CloudFront-Viewer-Country': 'SG',
                    'CloudFront-Is-Desktop-Viewer': 'true',
                    'CloudFront-Is-Mobile-Viewer': 'false',
                    'CloudFront-Is-Tablet-Viewer': 'false',
                    'CloudFront-Is-SmartTV-Viewer': 'false',
                    'Connection': 'keep-alive',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                    'Upgrade-Insecure-Requests': '1'
                },
                'timeout': 60000,
                'rateLimit': 800
            },
            {
                'apiKey': self.api_credentials['api_key'],
                'secret': self.api_credentials['api_secret'],
                'sandbox': False,
                'enableRateLimit': True,
                'urls': {
                    'api': {
                        'public': 'https://api.bybit.com',
                        'private': 'https://api.bybit.com',
                    }
                },
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/json, text/plain, */*',
                    'Accept-Language': 'en-AE,ar;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Origin': 'https://www.bybit.com',
                    'Referer': 'https://www.bybit.com/',
                    'Sec-Fetch-Site': 'same-site',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Dest': 'empty',
                    'X-Forwarded-For': '5.62.60.1',        # UAE Dubai IP
                    'X-Real-IP': '5.62.60.1',
                    'CF-Connecting-IP': '5.62.60.1',
                    'X-Originating-IP': '5.62.60.1',
                    'X-Client-IP': '5.62.60.1',
                    'X-Country-Code': 'AE',
                    'CloudFront-Viewer-Country': 'AE',
                    'CloudFront-Is-Desktop-Viewer': 'true',
                    'CloudFront-Is-Mobile-Viewer': 'false',
                    'CloudFront-Is-Tablet-Viewer': 'false',
                    'Connection': 'keep-alive',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                    'Via': '1.1 proxy.ae.example.com',
                    'X-VPN-Country': 'AE'
                },
                'timeout': 60000,
                'rateLimit': 800
            },
            {
                'apiKey': self.api_credentials['api_key'],
                'secret': self.api_credentials['api_secret'],
                'sandbox': False,
                'enableRateLimit': True,
                'urls': {
                    'api': {
                        'public': 'https://api-testnet.bybit.com',
                        'private': 'https://api-testnet.bybit.com',
                    }
                },
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/json',
                    'Accept-Language': 'en-AE,ar;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Origin': 'https://www.bybit.com',
                    'Referer': 'https://www.bybit.com/',
                    'Sec-Fetch-Site': 'same-site',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Dest': 'empty',
                    'X-Forwarded-For': '5.62.60.1',        # UAE Dubai IP
                    'X-Real-IP': '5.62.60.1',
                    'CF-Connecting-IP': '5.62.60.1',
                    'X-Originating-IP': '5.62.60.1',
                    'X-Client-IP': '5.62.60.1',
                    'X-Country-Code': 'AE',                # UAE country code
                    'CloudFront-Viewer-Country': 'AE',
                    'CloudFront-Is-Desktop-Viewer': 'true',
                    'CloudFront-Is-Mobile-Viewer': 'false',
                    'CloudFront-Is-Tablet-Viewer': 'false',
                    'Connection': 'keep-alive',
                    'Cache-Control': 'no-cache',
                    'Upgrade-Insecure-Requests': '1'
                },
                'timeout': 60000,
                'rateLimit': 800
            },
            {
                'apiKey': self.api_credentials['api_key'],
                'secret': self.api_credentials['api_secret'],
                'sandbox': False,
                'enableRateLimit': True,
                'urls': {
                    'api': {
                        'public': 'https://api.bybit.com',
                        'private': 'https://api.bybit.com',
                    }
                },
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/json',
                    'Accept-Language': 'en-HK,zh;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'X-Forwarded-For': selected_hk_ip,
                    'X-Real-IP': selected_hk_ip,
                    'CF-Connecting-IP': selected_hk_ip,
                    'True-Client-IP': selected_hk_ip,
                    'X-Country-Code': 'HK',
                    'CloudFront-Viewer-Country': 'HK',
                    'CloudFront-Is-Desktop-Viewer': 'true',
                    'CloudFront-Is-Mobile-Viewer': 'false',
                    'CloudFront-Is-Tablet-Viewer': 'false',
                    'Via': '1.1 103.10.197.1:8080',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                },
                'timeout': 60000,
                'rateLimit': 800
            },
            {
                'apiKey': self.api_credentials['api_key'],
                'secret': self.api_credentials['api_secret'],
                'sandbox': False,
                'enableRateLimit': True,
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                    'Accept': 'application/json',
                    'X-Forwarded-For': selected_jp_ip,
                    'X-Real-IP': selected_jp_ip,
                    'CF-Connecting-IP': selected_jp_ip,
                    'True-Client-IP': selected_jp_ip,
                    'X-Country-Code': 'JP',
                    'CloudFront-Viewer-Country': 'JP',
                    'Connection': 'keep-alive'
                },
                'timeout': 60000,
                'rateLimit': 800
            },
            {
                'apiKey': self.api_credentials['api_key'],
                'secret': self.api_credentials['api_secret'],
                'sandbox': False,
                'enableRateLimit': True,
                'urls': {
                    'api': {
                        'public': 'https://api-testnet.bybit.com',
                        'private': 'https://api-testnet.bybit.com',
                    }
                },
                'headers': {
                    'User-Agent': 'okhttp/4.9.0',
                    'Accept': 'application/json',
                    'Accept-Language': 'en-SG,en;q=0.9',
                    'X-Forwarded-For': f'{selected_sg_ip}, {selected_uae_ip}',
                    'X-Real-IP': selected_sg_ip,
                    'CF-Connecting-IP': selected_sg_ip,
                    'X-Originating-IP': selected_sg_ip,
                    'X-Client-IP': selected_sg_ip,
                    'True-Client-IP': selected_sg_ip,
                    'X-Country-Code': 'SG',
                    'CloudFront-Viewer-Country': 'SG',
                    'X-Forwarded-Proto': 'https',
                    'Connection': 'keep-alive'
                },
                'timeout': 60000,
                'rateLimit': 800
            },
            {
                'apiKey': self.api_credentials['api_key'],
                'secret': self.api_credentials['api_secret'],
                'sandbox': False,
                'enableRateLimit': True,
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15',
                    'Accept': 'application/json',
                    'Accept-Language': 'en-SG,en;q=0.9',
                    'X-Forwarded-For': selected_sg_ip,
                    'X-Real-IP': selected_sg_ip,
                    'CF-Connecting-IP': selected_sg_ip,
                    'X-Country-Code': 'SG',
                    'CloudFront-Viewer-Country': 'SG',
                    'Connection': 'keep-alive'
                },
                'timeout': 30000,
                'rateLimit': 1200
            },
            # Additional bypass methods
            {
                'apiKey': self.api_credentials['api_key'],
                'secret': self.api_credentials['api_secret'],
                'sandbox': False,
                'enableRateLimit': True,
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/json',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'X-Forwarded-For': selected_us_ip,
                    'X-Real-IP': selected_us_ip,
                    'CF-Connecting-IP': selected_us_ip,
                    'X-Country-Code': 'US',
                    'CloudFront-Viewer-Country': 'US',
                    'CloudFront-Viewer-ASN': '16509',
                    'CloudFront-Forwarded-Proto': 'https',
                    'Connection': 'keep-alive'
                },
                'timeout': 45000,
                'rateLimit': 1000
            },
            {
                'apiKey': self.api_credentials['api_key'],
                'secret': self.api_credentials['api_secret'],
                'sandbox': False,
                'enableRateLimit': True,
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
                    'Accept': 'application/json',
                    'Accept-Language': 'en-GB,en;q=0.9',
                    'X-Forwarded-For': selected_uk_ip,
                    'X-Real-IP': selected_uk_ip,
                    'CF-Connecting-IP': selected_uk_ip,
                    'X-Country-Code': 'GB',
                    'CloudFront-Viewer-Country': 'GB',
                    'CloudFront-Viewer-Time-Zone': 'Europe/London',
                    'Connection': 'keep-alive'
                },
                'timeout': 45000,
                'rateLimit': 1000
            },
            # Fallback with no custom headers
            {
                'apiKey': self.api_credentials['api_key'],
                'secret': self.api_credentials['api_secret'],
                'sandbox': False,
                'enableRateLimit': True,
                'timeout': 30000,
                'rateLimit': 1500
            },
            # DNS bypass using alternative resolver
            {
                'apiKey': self.api_credentials['api_key'],
                'secret': self.api_credentials['api_secret'],
                'sandbox': False,
                'enableRateLimit': True,
                'urls': {
                    'api': {
                        'public': 'https://api.bybit.com',
                        'private': 'https://api.bybit.com',
                    }
                },
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/json',
                    'Host': 'api.bybit.com',
                    'X-Forwarded-For': selected_sg_ip,
                    'X-Real-IP': selected_sg_ip,
                    'CF-Connecting-IP': selected_sg_ip,
                    'X-Country-Code': 'SG',
                    'CloudFront-Viewer-Country': 'SG'
                },
                'timeout': 45000,
                'rateLimit': 1000,
                'proxies': os.getenv('HTTPS_PROXY', None)  # Support for proxy if configured
            }
        ]
        
        method_names = [
            "Singapore IP Spoofing (Primary)",
            "UAE/Dubai IP Spoofing (Fallback)",
            "Testnet API with UAE headers",
            "Hong Kong IP with VPN headers", 
            "Japan/Tokyo endpoint routing",
            "Singapore testnet with multi-IP",
            "Minimal headers mobile fallback",
            "US datacenter IP spoofing",
            "UK/London IP spoofing",
            "Clean headers fallback (no geo-spoofing)",
            "DNS bypass with proxy support"
        ]
        
        for i, config in enumerate(configs_to_try):
            if self.api_credentials.get('api_passphrase'):
                config['passphrase'] = self.api_credentials.get('api_passphrase')
                
            try:
                exchange_class = getattr(ccxt, self.instance.exchange.lower())
                test_exchange = exchange_class(config)
                
                # Set market type for unified trading (Bybit feature)
                market_type = getattr(self.instance, 'market_type', 'unified')
                if self.instance.exchange.lower() == 'bybit' and hasattr(test_exchange, 'options'):
                    if market_type == 'unified':
                        test_exchange.options['defaultType'] = 'unified'
                    elif market_type == 'spot':
                        test_exchange.options['defaultType'] = 'spot'
                    elif market_type == 'futures':
                        test_exchange.options['defaultType'] = 'future'
                
                test_exchange.load_markets()
                if self.instance.exchange.lower() == 'bybit':
                    test_exchange.fetch_ticker('BTC/USDT')
                
                logger.info(f"✅ [BYBIT SUCCESS] Method {i+1} WORKED: {method_names[i]}")
                logger.info(f"✅ [BYBIT SUCCESS] Successfully bypassed CloudFront restrictions!")
                logger.info(f"✅ [BYBIT SUCCESS] Market type set to: {market_type}")
                return test_exchange
                
            except Exception as e:
                import time
                error_msg = str(e).lower()
                method_name = method_names[i] if i < len(method_names) else f"Method {i+1}"
                
                # Enhanced CloudFront detection
                cloudfront_indicators = [
                    'cloudfront', '403', 'forbidden', 'request could not be satisfied',
                    'configured to block access', 'country', 'region blocked',
                    'access denied', 'geo-restriction', 'location restricted'
                ]
                
                is_cloudfront_block = any(indicator in error_msg for indicator in cloudfront_indicators)
                
                if is_cloudfront_block:
                    logger.warning(f"⚠️ Method {i+1}/{len(configs_to_try)} failed - CloudFront/Geo blocking: {method_name}")
                    logger.debug(f"Error details: {str(e)[:200]}")
                    
                    if i < len(configs_to_try) - 1:
                        logger.info(f"🔄 Waiting 2 seconds before next bypass attempt...")
                        time.sleep(2)  # Brief delay to avoid rate limiting
                        continue
                    else:
                        logger.error(f"❌ All {len(configs_to_try)} CloudFront bypass methods failed!")
                        self._log_error("cloudfront_bypass_failed", f"All {len(configs_to_try)} bypass methods failed. Last error: {e}")
                        
                        # Suggest user action
                        logger.error("💡 Suggestions:")
                        logger.error("   1. Try using a VPN from Singapore, UAE, or Hong Kong")
                        logger.error("   2. Check if your server IP is in a restricted region")
                        logger.error("   3. Verify your API credentials are correct")
                        
                        raise Exception(f"CloudFront bypass failed after {len(configs_to_try)} attempts. Geographic restrictions detected.")
                else:
                    logger.error(f"Failed to initialize exchange {self.instance.exchange} (Method {i+1}): {e}")
                    if i < len(configs_to_try) - 1:
                        time.sleep(1)  # Brief delay before retry
                        continue
                    else:
                        self._log_error("exchange_init", str(e))
                        raise
    
    def _init_generic_exchange(self) -> ccxt.Exchange:
        """Initialize non-Bybit exchanges with generic configurations"""
        exchange_name = self.instance.exchange.lower()
        
        # Exchange-specific configurations
        configs_to_try = []
        
        if exchange_name == 'bitget':
            # Bitget-specific configurations
            configs_to_try = [
                {
                    'apiKey': self.api_credentials['api_key'],
                    'secret': self.api_credentials['api_secret'],
                    'password': self.api_credentials.get('api_passphrase', ''),  # Bitget uses 'password' field
                    'sandbox': False,
                    'enableRateLimit': True,
                    'headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'application/json',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Connection': 'keep-alive'
                    },
                    'timeout': 30000,
                    'rateLimit': 100
                },
                {
                    'apiKey': self.api_credentials['api_key'],
                    'secret': self.api_credentials['api_secret'],
                    'password': self.api_credentials.get('api_passphrase', ''),  # Bitget uses 'password' field
                    'sandbox': False,
                    'enableRateLimit': True,
                    'timeout': 30000,
                    'rateLimit': 200
                }
            ]
        else:
            # Generic configurations for other exchanges
            configs_to_try = [
                {
                    'apiKey': self.api_credentials['api_key'],
                    'secret': self.api_credentials['api_secret'],
                    'sandbox': False,
                    'enableRateLimit': True,
                    'headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'application/json',
                    },
                    'timeout': 30000,
                    'rateLimit': 100
                },
                {
                    'apiKey': self.api_credentials['api_key'],
                    'secret': self.api_credentials['api_secret'],
                    'sandbox': False,
                    'enableRateLimit': True,
                    'timeout': 30000,
                    'rateLimit': 200
                }
            ]
        
        # Add passphrase if provided (for exchanges like OKX, KuCoin)
        for config in configs_to_try:
            if self.api_credentials.get('api_passphrase'):
                config['passphrase'] = self.api_credentials.get('api_passphrase')
        
        # Try each configuration
        for i, config in enumerate(configs_to_try):
            try:
                exchange_class = getattr(ccxt, exchange_name)
                test_exchange = exchange_class(config)
                
                # Load markets to test connection
                test_exchange.load_markets()
                
                # Test with a common ticker (most exchanges support BTC/USDT)
                try:
                    test_exchange.fetch_ticker('BTC/USDT')
                except Exception as ticker_error:
                    # If BTC/USDT fails, try ETH/USDT
                    try:
                        test_exchange.fetch_ticker('ETH/USDT')
                    except Exception:
                        # If both fail, still continue if load_markets worked
                        logger.warning(f"Ticker test failed for {exchange_name}, but connection established: {ticker_error}")
                
                logger.info(f"✅ [{exchange_name.upper()} SUCCESS] Connection established successfully (Method {i+1})")
                return test_exchange
                
            except Exception as e:
                logger.warning(f"⚠️ [{exchange_name.upper()}] Method {i+1} failed: {str(e)[:200]}")
                if i < len(configs_to_try) - 1:
                    continue
                else:
                    logger.error(f"❌ [{exchange_name.upper()}] All connection methods failed")
                    self._log_error("exchange_init", f"Failed to initialize {exchange_name}: {e}")
                    
                    # Provide helpful error message
                    error_msg = str(e).lower()
                    if 'invalid api' in error_msg or 'authentication' in error_msg or 'signature' in error_msg:
                        raise Exception(f"Invalid API credentials for {exchange_name.title()}. Please check your API key, secret, and passphrase (if required).")
                    elif 'permission' in error_msg or 'not allowed' in error_msg:
                        raise Exception(f"API key permissions insufficient for {exchange_name.title()}. Please ensure your API key has trading permissions enabled.")
                    else:
                        raise Exception(f"Failed to connect to {exchange_name.title()}: {e}")
    
    def _init_telegram(self) -> Optional[Bot]:
        """Initialize Telegram bot"""
        token = self.instance.telegram_bot_token or settings.default_telegram_bot_token
        if token:
            return Bot(token=token)
        return None
    
    def _recreate_db_session(self):
        """Recreate database session after connection failure"""
        try:
            if self.db:
                self.db.close()
        except Exception:
            pass
        
        self.db = SessionLocal()
        self.instance = self.db.query(BotInstance).filter(BotInstance.id == self.instance_id).first()
        if not self.instance:
            raise ValueError(f"Bot instance {self.instance_id} not found after session recreation")
    
    def _execute_db_operation(self, operation_func, operation_name: str, max_retries: int = 3):
        """Execute database operation with retry logic and session recovery"""
        for attempt in range(max_retries):
            try:
                operation_func()
                return
            except (OperationalError, DisconnectionError) as e:
                error_msg = str(e).lower()
                if 'ssl syscall error' in error_msg or 'eof detected' in error_msg or 'connection' in error_msg:
                    logger.warning(f"Database connection error during {operation_name} (attempt {attempt + 1}/{max_retries}): {e}")
                    
                    try:
                        self.db.rollback()
                    except Exception:
                        pass
                    
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) * 0.5
                        logger.info(f"Retrying {operation_name} in {wait_time} seconds...")
                        time.sleep(wait_time)
                        
                        try:
                            self._recreate_db_session()
                        except Exception as recreate_error:
                            logger.error(f"Failed to recreate session: {recreate_error}")
                            if attempt == max_retries - 1:
                                raise
                    else:
                        logger.error(f"Failed to execute {operation_name} after {max_retries} attempts")
                        raise
                else:
                    raise
            except Exception as e:
                if 'rolled back' in str(e).lower():
                    logger.warning(f"Session rollback error during {operation_name}: {e}")
                    try:
                        self.db.rollback()
                    except Exception:
                        pass
                    
                    if attempt < max_retries - 1:
                        try:
                            self._recreate_db_session()
                        except Exception as recreate_error:
                            logger.error(f"Failed to recreate session: {recreate_error}")
                            if attempt == max_retries - 1:
                                raise
                    else:
                        logger.error(f"Failed to execute {operation_name} after {max_retries} attempts")
                        raise
                else:
                    logger.error(f"Failed to execute {operation_name}: {e}")
                    raise

    def _execute_db_operation_with_return(self, operation_func, operation_name: str, max_retries: int = 3):
        """Execute database operation with retry logic and return value"""
        for attempt in range(max_retries):
            try:
                return operation_func()
            except (OperationalError, DisconnectionError) as e:
                error_msg = str(e).lower()
                if 'ssl syscall error' in error_msg or 'eof detected' in error_msg or 'connection' in error_msg:
                    logger.warning(f"Database connection error during {operation_name} (attempt {attempt + 1}/{max_retries}): {e}")
                    
                    try:
                        self.db.rollback()
                    except Exception:
                        pass
                    
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) * 0.5
                        logger.info(f"Retrying {operation_name} in {wait_time} seconds...")
                        time.sleep(wait_time)
                        
                        try:
                            self._recreate_db_session()
                        except Exception as recreate_error:
                            logger.error(f"Failed to recreate session: {recreate_error}")
                            if attempt == max_retries - 1:
                                raise
                    else:
                        logger.error(f"Failed to execute {operation_name} after {max_retries} attempts")
                        raise
                else:
                    raise
            except Exception as e:
                if 'rolled back' in str(e).lower():
                    logger.warning(f"Session rollback error during {operation_name}: {e}")
                    try:
                        self.db.rollback()
                    except Exception:
                        pass
                    
                    if attempt < max_retries - 1:
                        try:
                            self._recreate_db_session()
                        except Exception as recreate_error:
                            logger.error(f"Failed to recreate session: {recreate_error}")
                            if attempt == max_retries - 1:
                                raise
                    else:
                        logger.error(f"Failed to execute {operation_name} after {max_retries} attempts")
                        raise
                else:
                    logger.error(f"Failed to execute {operation_name}: {e}")
                    raise

    def _log_activity(self, event_type: str, symbol: Optional[str] = None, message: str = "", data: Optional[Dict] = None):
        """Log activity to database with connection error recovery"""
        def _log_operation():
            log_db = SessionLocal()
            try:
                log = ActivityLog(
                    instance_id=self.instance_id,
                    event_type=event_type,
                    symbol=symbol,
                    message=message,
                    data=data
                )
                log_db.add(log)
                log_db.commit()
            finally:
                log_db.close()
        
        try:
            self._execute_db_operation(_log_operation, "log_activity")
        except Exception as e:
            logger.error(f"Failed to log activity after all retries: {e}")
    
    def _log_error(self, error_type: str, error_message: str, traceback_str: Optional[str] = None):
        """Log error to database with connection error recovery"""
        def _error_operation():
            log_db = SessionLocal()
            try:
                error_log = ErrorLog(
                    instance_id=self.instance_id,
                    error_type=error_type,
                    error_message=error_message,
                    traceback=traceback_str
                )
                log_db.add(error_log)
                log_db.commit()
            finally:
                log_db.close()
        
        try:
            self._execute_db_operation(_error_operation, "log_error")
        except Exception as e:
            logger.error(f"Failed to log error after all retries: {e}")
    
    def _get_data_hash(self, data: Any) -> str:
        """Generate hash for change detection"""
        return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
    
    def _detect_strategy_type(self, symbol: str, data: Dict) -> str:
        """Get strategy type from instance configuration, not from symbol detection"""
        
        # Use configured strategies if available
        if self.instance.strategies:
            # If multiple strategies configured, return the first one
            # In practice, most instances will have one primary strategy
            return self.instance.strategies[0]
        
        # Fallback: try to infer from symbol name (legacy behavior)
        symbol_lower = symbol.lower()
        
        if 'dca' in symbol_lower:
            return 'DCA' if 'futures' not in symbol_lower else 'DCA Futures'
        elif 'grid' in symbol_lower:
            return 'Grid'
        elif 'combo' in symbol_lower:
            return 'Combo'
        elif 'loop' in symbol_lower:
            return 'Loop'
        elif 'btd' in symbol_lower:
            return 'BTD'
        elif 'ais' in symbol_lower:
            return 'AIS Assisted'
        
        return 'Unknown'
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol format for comparison (remove slashes, colons, convert to uppercase)"""
        # Remove common separators and suffixes used in different exchanges
        normalized = symbol.replace('/', '').replace('-', '').replace(':', '').upper()
        
        # Handle Bybit futures format: XRP/USDT:USDT -> XRPUSDT
        # Remove duplicate USDT if it appears due to :USDT suffix
        if normalized.endswith('USDTUSDT'):
            normalized = normalized[:-4]  # Remove the extra USDT
        elif normalized.endswith('BUSDBUSD'):
            normalized = normalized[:-4]  # Remove the extra BUSD
        elif normalized.endswith('BTCBTC'):
            normalized = normalized[:-3]  # Remove the extra BTC
        elif normalized.endswith('ETHETH'):
            normalized = normalized[:-3]  # Remove the extra ETH
            
        return normalized

    def _should_process_symbol(self, symbol: str) -> bool:
        """Check if symbol should be processed based on configured trading pair and strategies"""
        logger.info(f"[SYMBOL_CHECK] Checking symbol: {symbol}")
        logger.info(f"[SYMBOL_CHECK] Configured trading_pair: {self.instance.trading_pair}")
        logger.info(f"[SYMBOL_CHECK] Configured strategies: {self.instance.strategies}")
        
        if self.instance.trading_pair:
            normalized_symbol = self._normalize_symbol(symbol)
            normalized_trading_pair = self._normalize_symbol(self.instance.trading_pair)
            logger.info(f"[SYMBOL_CHECK] Normalized symbol: {normalized_symbol}")
            logger.info(f"[SYMBOL_CHECK] Normalized trading_pair: {normalized_trading_pair}")
            
            if normalized_symbol != normalized_trading_pair:
                logger.info(f"[SYMBOL_CHECK] ❌ {symbol} filtered out - doesn't match trading pair {self.instance.trading_pair}")
                return False
            else:
                logger.info(f"[SYMBOL_CHECK] ✅ {symbol} matches trading pair {self.instance.trading_pair}")
        
        # Strategy filtering: if strategies are configured, all matching symbols use those strategies
        if not self.instance.strategies:
            logger.info(f"[SYMBOL_CHECK] ✅ {symbol} will be processed - no strategy filter")
            return True
        
        # If strategies are configured, the symbol passes (since trading pair already matched)
        # The configured strategies will be used for this symbol
        configured_strategies = ', '.join(self.instance.strategies)
        logger.info(f"[SYMBOL_CHECK] ✅ {symbol} will be processed - using configured strategies: {configured_strategies}")
        return True
    
    async def fetch_positions(self) -> List[Dict]:
        """Fetch current positions"""
        try:
            exchange_name = self.instance.exchange.lower()
            
            # Handle Bitget isolated futures specifically using REST client
            if exchange_name == 'bitget' and self.instance.market_type == 'futures' and self.bitget_rest_client:
                try:
                    positions_response = self.bitget_rest_client.get_positions(
                        product_type='USDT-FUTURES',
                        margin_coin='USDT'
                    )
                    
                    if positions_response and positions_response.get('code') == '00000':
                        positions_data = positions_response.get('data', [])
                        logger.info(f"REST client fetched {len(positions_data)} positions")
                        return self._parse_bitget_positions(positions_data)
                    else:
                        logger.warning(f"REST client positions failed: {positions_response}")
                        
                except Exception as rest_error:
                    logger.warning(f"REST client positions failed, falling back to CCXT: {rest_error}")
            
            # Fallback to standard CCXT method
            positions = self.exchange.fetch_positions()
            return [pos for pos in positions if pos['contracts'] > 0]  # Only open positions
        except Exception as e:
            self._log_error("fetch_positions", str(e))
            return []
    
    async def fetch_open_orders(self) -> List[Dict]:
        """Fetch open orders"""
        try:
            exchange_name = self.instance.exchange.lower()
            
            # Handle Bitget isolated futures specifically using REST client
            if exchange_name == 'bitget' and self.instance.market_type == 'futures' and self.bitget_rest_client:
                try:
                    # Get trading pair for symbol filtering if specified
                    symbol = None
                    if self.instance.trading_pair:
                        symbol = self.instance.trading_pair
                        if '/' in symbol:
                            symbol = symbol.replace('/', '')
                    
                    orders_response = self.bitget_rest_client.get_pending_orders(
                        product_type='USDT-FUTURES',
                        symbol=symbol.lower() if symbol else None
                    )
                    
                    if orders_response and orders_response.get('code') == '00000':
                        orders_data = orders_response.get('data', {}).get('entrustedList', [])
                        logger.info(f"REST client fetched {len(orders_data)} pending orders")
                        return self._parse_bitget_orders(orders_data)
                    else:
                        logger.warning(f"REST client orders failed: {orders_response}")
                        
                except Exception as rest_error:
                    logger.warning(f"REST client orders failed, falling back to CCXT: {rest_error}")
            
            # Fallback to standard CCXT method
            return self.exchange.fetch_open_orders()
        except Exception as e:
            self._log_error("fetch_open_orders", str(e))
            return []
    
    async def fetch_balance(self) -> Dict:
        """Fetch account balance"""
        if not self.instance.balance_enabled:
            return {}
            
        try:
            exchange_name = self.instance.exchange.lower()
            
            # Handle Bitget isolated futures specifically
            if exchange_name == 'bitget' and self.instance.market_type == 'futures':
                balance = await self._fetch_bitget_futures_balance()
            else:
                # Use standard CCXT method for other exchanges
                balance = self.exchange.fetch_balance()
            
            # Filter out zero balances and format for notification
            filtered_balance = {}
            for currency, amount_data in balance.items():
                if currency in ['info', 'free', 'used', 'total']:
                    continue
                
                if isinstance(amount_data, dict):
                    total = amount_data.get('total', 0)
                    if total and total > 0:
                        filtered_balance[currency] = {
                            'free': amount_data.get('free', 0),
                            'used': amount_data.get('used', 0),
                            'total': total
                        }
                        
            return filtered_balance
        except Exception as e:
            self._log_error("fetch_balance", str(e))
            return {}

    async def _fetch_bitget_futures_balance(self) -> Dict:
        """Fetch Bitget futures balance using custom REST client to bypass CCXT issues"""
        try:
            if not self.bitget_rest_client:
                logger.warning("Bitget REST client not initialized, falling back to CCXT")
                return {}
            
            # Get the trading pair, default to BTCUSDT if not specified
            symbol = self.instance.trading_pair or 'BTCUSDT'
            # Convert BTC/USDT format to BTCUSDT format expected by Bitget
            if '/' in symbol:
                symbol = symbol.replace('/', '')
            
            logger.info(f"Using custom REST client to fetch Bitget balance for symbol: {symbol}")
            
            # Use synchronous call to get account data
            try:
                account_response = self.bitget_rest_client.get_account(
                    symbol=symbol.lower(),
                    product_type='USDT-FUTURES',
                    margin_coin='USDT'
                )
                
                logger.info(f"REST client account response: {account_response}")
                
                if account_response and account_response.get('code') == '00000':
                    # Parse the successful response
                    bitget_balance = self._parse_bitget_balance_response(account_response)
                    if bitget_balance:
                        logger.info("Successfully fetched balance using custom REST client")
                        return bitget_balance
                    else:
                        logger.warning("REST client returned successful response but parsing failed")
                else:
                    logger.warning(f"REST client returned error: {account_response}")
                    
            except Exception as rest_error:
                logger.error(f"REST client get_account failed: {rest_error}")
            
            # Fallback to CCXT if REST client fails
            logger.warning("REST client failed, falling back to CCXT methods")
            
            # Try CCXT with specific parameters
            try:
                params = {
                    'symbol': symbol,
                    'productType': 'USDT-FUTURES',
                    'marginCoin': 'USDT'
                }
                logger.info(f"Fallback: Trying CCXT fetch_balance with params: {params}")
                balance = self.exchange.fetch_balance(params)
                
                if balance and any(isinstance(v, dict) and v.get('total', 0) > 0 for v in balance.values()):
                    logger.info("CCXT fallback succeeded")
                    return balance
                else:
                    logger.warning("CCXT returned empty balance")
                    
            except Exception as ccxt_error:
                logger.warning(f"CCXT fallback failed: {ccxt_error}")
            
            # Final fallback: Use standard CCXT fetch_balance
            try:
                logger.info("Using final fallback: standard CCXT fetch_balance")
                return self.exchange.fetch_balance()
            except Exception as fallback_error:
                logger.error(f"Final fallback also failed: {fallback_error}")
                return {}
            
        except Exception as e:
            logger.error(f"Failed to fetch Bitget futures balance: {e}")
            return {}

    def _parse_bitget_balance_response(self, response: Dict) -> Dict:
        """Parse Bitget API response into CCXT balance format"""
        try:
            balance = {}
            logger.info(f"Parsing Bitget response: {response}")
            
            # Handle the exact Bitget response format from the user's working API call
            if 'data' in response and response['data'] and response.get('code') == '00000':
                account_data = response['data']
                
                # Parse margin coin balance (usually USDT for USDT futures)
                margin_coin = account_data.get('marginCoin', 'USDT')
                
                # Extract balance values using the exact field names from Bitget API
                available = float(account_data.get('available', 0))
                locked = float(account_data.get('locked', 0))
                total = available + locked
                
                if total > 0:
                    balance[margin_coin] = {
                        'free': available,
                        'used': locked, 
                        'total': total
                    }
                    logger.info(f"Added {margin_coin} balance: free={available}, used={locked}, total={total}")
                
                # Include account equity as a separate entry
                account_equity = account_data.get('accountEquity')
                if account_equity:
                    equity_value = float(account_equity)
                    balance[f"{margin_coin}_Equity"] = {
                        'free': equity_value,
                        'used': 0,
                        'total': equity_value
                    }
                    logger.info(f"Added {margin_coin}_Equity: {equity_value}")
                
                # Include unrealized P&L
                unrealized_pl = account_data.get('unrealizedPL')
                if unrealized_pl:
                    pl_value = float(unrealized_pl)
                    if pl_value != 0:  # Only show if non-zero
                        balance[f"{margin_coin}_UnrealizedPL"] = {
                            'free': pl_value,
                            'used': 0,
                            'total': pl_value
                        }
                        logger.info(f"Added {margin_coin}_UnrealizedPL: {pl_value}")
                
                logger.info(f"Final parsed Bitget balance: {balance}")
            else:
                logger.warning(f"Unexpected Bitget response format: {response}")
            
            return balance
            
        except Exception as e:
            logger.error(f"Error parsing Bitget balance response: {e}")
            logger.error(f"Response was: {response}")
            return {}

    def _parse_bitget_positions(self, positions_data: List[Dict]) -> List[Dict]:
        """Parse Bitget positions response into CCXT format"""
        try:
            ccxt_positions = []
            
            for position in positions_data:
                # Only include positions with actual size > 0
                if float(position.get('total', 0)) > 0:
                    ccxt_position = {
                        'symbol': position.get('symbol', ''),
                        'side': position.get('holdSide', ''),
                        'contracts': float(position.get('total', 0)),
                        'contractSize': float(position.get('contractSize', 1)),
                        'unrealizedPnl': float(position.get('unrealizedPL', 0)),
                        'percentage': float(position.get('unrealizedPLR', 0)) * 100,
                        'notional': float(position.get('margin', 0)),
                        'markPrice': float(position.get('markPrice', 0)),
                        'entryPrice': float(position.get('averageOpenPrice', 0)),
                        'timestamp': None,
                        'datetime': None,
                        'info': position
                    }
                    ccxt_positions.append(ccxt_position)
                    logger.info(f"Parsed position: {ccxt_position['symbol']} {ccxt_position['side']} {ccxt_position['contracts']}")
            
            return ccxt_positions
            
        except Exception as e:
            logger.error(f"Error parsing Bitget positions: {e}")
            logger.error(f"Positions data was: {positions_data}")
            return []

    def _parse_bitget_orders(self, orders_data: List[Dict]) -> List[Dict]:
        """Parse Bitget orders response into CCXT format"""
        try:
            ccxt_orders = []
            
            for order in orders_data:
                ccxt_order = {
                    'id': order.get('orderId', ''),
                    'clientOrderId': order.get('clientOid', ''),
                    'symbol': order.get('symbol', ''),
                    'side': order.get('side', ''),
                    'amount': float(order.get('size', 0)),
                    'price': float(order.get('price', 0)) if order.get('price') else None,
                    'type': order.get('orderType', '').lower(),
                    'status': self._map_bitget_order_status(order.get('state', '')),
                    'filled': float(order.get('filledQty', 0)),
                    'remaining': float(order.get('size', 0)) - float(order.get('filledQty', 0)),
                    'timestamp': int(order.get('cTime', 0)),
                    'datetime': None,
                    'fee': None,
                    'trades': None,
                    'info': order
                }
                ccxt_orders.append(ccxt_order)
                logger.info(f"Parsed order: {ccxt_order['symbol']} {ccxt_order['side']} {ccxt_order['amount']} @ {ccxt_order['price']}")
            
            return ccxt_orders
            
        except Exception as e:
            logger.error(f"Error parsing Bitget orders: {e}")
            logger.error(f"Orders data was: {orders_data}")
            return []

    def _map_bitget_order_status(self, bitget_status: str) -> str:
        """Map Bitget order status to CCXT status"""
        status_mapping = {
            'new': 'open',
            'partial-fill': 'open',
            'full-fill': 'closed',
            'cancelled': 'canceled',
            'live': 'open'
        }
        return status_mapping.get(bitget_status.lower(), 'open')

    def _save_balance_history(self, balance: Dict):
        """Save balance snapshot to history"""
        if not balance or not self.instance.balance_enabled:
            return
            
        def _save_operation():
            # Save balance history entry
            history_entry = BalanceHistory(
                instance_id=self.instance_id,
                balance_data=balance,
                timestamp=datetime.utcnow()
            )
            
            self.db.add(history_entry)
            self.db.commit()
            
            # Clean up old history entries (keep last 90 days)
            cutoff_date = datetime.utcnow() - timedelta(days=90)
            old_entries = self.db.query(BalanceHistory).filter(
                BalanceHistory.instance_id == self.instance_id,
                BalanceHistory.timestamp < cutoff_date
            ).all()
            
            for entry in old_entries:
                self.db.delete(entry)
            
            if old_entries:
                self.db.commit()
                logger.info(f"Cleaned up {len(old_entries)} old balance history entries")
        
        try:
            self._execute_db_operation(_save_operation, "save_balance_history")
        except Exception as e:
            logger.error(f"Failed to save balance history: {e}")
            # Don't re-raise - balance history is not critical enough to stop polling

    async def fetch_recent_trades(self) -> List[Dict]:
        """Fetch recent trades since last poll"""
        try:
            since = None
            if self.instance.last_poll:
                since = int(self.instance.last_poll.timestamp() * 1000)
            
            # Handle exchanges that require symbol parameter (like Bitget)
            exchange_name = self.instance.exchange.lower()
            if exchange_name == 'bitget':
                # Bitget requires symbol parameter, so we need to get trades for specific symbols
                all_trades = []
                
                # If trading_pair is specified, use it
                if self.instance.trading_pair:
                    try:
                        trades = self.exchange.fetch_my_trades(symbol=self.instance.trading_pair, since=since)
                        all_trades.extend(trades)
                    except Exception as e:
                        logger.warning(f"Failed to fetch trades for {self.instance.trading_pair}: {e}")
                else:
                    # Get trades for common pairs if no specific pair is set
                    common_symbols = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT']
                    for symbol in common_symbols:
                        try:
                            trades = self.exchange.fetch_my_trades(symbol=symbol, since=since)
                            all_trades.extend(trades)
                        except Exception as e:
                            # Ignore errors for symbols that don't exist or aren't traded
                            continue
                
                return all_trades
            else:
                # For other exchanges, use the standard method
                return self.exchange.fetch_my_trades(since=since)
                
        except Exception as e:
            self._log_error("fetch_recent_trades", str(e))
            return []
    
    def _get_previous_state(self, symbol: str, data_type: str) -> Optional[Dict]:
        """Get previous state for comparison with connection error recovery"""
        def _get_operation():
            state = self.db.query(PollState).filter(
                PollState.instance_id == self.instance_id,
                PollState.symbol == symbol,
                PollState.data_type == data_type
            ).order_by(PollState.timestamp.desc()).first()
            
            return state.data if state else None
        
        try:
            return self._execute_db_operation_with_return(_get_operation, "get_previous_state")
        except Exception as e:
            logger.error(f"Failed to get previous state for {symbol} {data_type}: {e}")
            return None
    
    def _save_state(self, symbol: str, data_type: str, data: Dict):
        """Save current state with connection error recovery"""
        def _save_operation():
            data_hash = self._get_data_hash(data)
            
            state = PollState(
                instance_id=self.instance_id,
                symbol=symbol,
                data_type=data_type,
                data_hash=data_hash,
                data=data
            )
            
            self.db.add(state)
            self.db.commit()
        
        try:
            self._execute_db_operation(_save_operation, "save_state")
        except Exception as e:
            logger.error(f"Failed to save state after all retries: {e}")
    
    def _create_event_payload(self, event_type: str, symbol: str, data: Dict, balance: Dict = None) -> Dict:
        """Create structured event payload"""
        strategy_type = self._detect_strategy_type(symbol, data)
        
        payload = {
            "event_type": event_type,
            "symbol": symbol,
            "bot_type": strategy_type,
            "timestamp": datetime.utcnow().isoformat(),
            "instance_id": self.instance_id,
            "exchange": self.instance.exchange
        }
        
        # Add balance information if provided and enabled
        if balance and self.instance.balance_enabled:
            payload["balance"] = balance
        
        if event_type in ["order_filled", "order_cancelled", "new_order"]:
            if event_type == "order_filled" and 'order' in data:
                payload.update({
                    "order_id": data.get('order'),
                    "side": data.get('side'),
                    "entry_price": data.get('price'),
                    "quantity": data.get('amount'),
                    "status": "filled",
                    "trade_id": data.get('id')
                })
            else:
                payload.update({
                    "order_id": data.get('id'),
                    "side": data.get('side'),
                    "entry_price": data.get('price'),
                    "quantity": data.get('amount'),
                    "status": data.get('status')
                })
        
        elif event_type == "position_update":
            payload.update({
                "side": data.get('side'),
                "entry_price": data.get('entryPrice'),
                "quantity": data.get('contracts'),
                "unrealized_pnl": data.get('unrealizedPnl')
            })
        
        return payload
    
    async def _send_webhook(self, payload: Dict):
        """Send webhook notification"""
        if not self.instance.webhook_url:
            return
        
        try:
            headers = {
                'Content-Type': 'application/json',
                'X-Webhook-Secret': settings.webhook_secret
            }
            
            response = requests.post(
                self.instance.webhook_url,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                self._log_activity("webhook_sent", payload.get('symbol'), "Webhook sent successfully")
                logger.info(f"Webhook sent successfully for instance {self.instance_id}")
            else:
                self._log_error("webhook_failed", f"Webhook failed with status {response.status_code}")
                logger.error(f"Webhook failed for instance {self.instance_id}: status {response.status_code}")
                
        except Exception as e:
            self._log_error("webhook_error", str(e))
    
    async def _send_telegram_notification(self, payload: Dict):
        """Send Telegram notification with beautiful formatting and rate limiting"""
        if not self.telegram_bot:
            logger.debug(f"No Telegram bot configured for instance {self.instance_id}")
            return
        
        chat_id = self.instance.telegram_chat_id or settings.default_telegram_chat_id
        if not chat_id:
            logger.debug(f"No Telegram chat ID configured for instance {self.instance_id}")
            return
        
        try:
            # Rate limiting: minimum 5 seconds between messages
            current_time = time.time()
            time_since_last = current_time - self.last_telegram_send
            if time_since_last < 5.0:
                wait_time = 5.0 - time_since_last
                logger.info(f"Rate limiting: waiting {wait_time:.1f}s before sending Telegram message")
                await asyncio.sleep(wait_time)
            
            message = self._format_telegram_message(payload)
            
            topic_id = self.instance.telegram_topic_id or settings.default_telegram_topic_id
            
            send_params = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            
            if topic_id:
                send_params['message_thread_id'] = int(topic_id)
            
            await self.telegram_bot.send_message(**send_params)
            self.last_telegram_send = time.time()  # Update last send time
            
            self._log_activity("telegram_sent", payload.get('symbol'), "Telegram notification sent")
            logger.info(f"Telegram notification sent for instance {self.instance_id}")
            
        except Exception as e:
            error_msg = f"Failed to send Telegram notification: {e}"
            logger.error(error_msg)
            self._log_error("telegram_error", error_msg)
    
    def _format_telegram_message(self, payload: Dict) -> str:
        """Format beautiful Telegram message with enhanced Markdown formatting"""
        timestamp = datetime.now().strftime("%Y-%m-%d %I:%M %p")
        event_type = payload.get('event_type')
        symbol = payload.get('symbol', 'N/A')
        bot_type = payload.get('bot_type', 'Unknown')
        balance = payload.get('balance', {})
        
        # Safe formatting functions to handle None values
        def safe_float(value, decimals=2, default='0'):
            if value is None:
                return default
            try:
                return f"{float(value):.{decimals}f}"
            except (ValueError, TypeError):
                return default
        
        def safe_side(value):
            if value is None:
                return 'N/A'
            return str(value).upper()
        
        def safe_string(value, default='N/A'):
            return str(value) if value is not None else default
        
        def format_balance_section(balance_data):
            """Format balance data for display"""
            if not balance_data:
                return ""
            
            balance_lines = []
            balance_lines.append("\n💰 **Account Balance:**")
            balance_lines.append("```")
            
            # Extract active coin from trading pair (if available)
            active_coin = self._get_active_coin_from_trading_pair()
            
            # Show active coin and USDT first (if they exist)
            priority_currencies = []
            if active_coin:
                priority_currencies.append(active_coin)
            priority_currencies.append('USDT')
            
            # Show priority currencies first
            shown_currencies = set()
            for currency in priority_currencies:
                if currency in balance_data:
                    amounts = balance_data[currency]
                    if isinstance(amounts, dict) and amounts.get('total', 0) > 0:
                        total = amounts.get('total', 0)
                        free = amounts.get('free', 0)
                        used = amounts.get('used', 0)
                        balance_lines.append(f"• {currency}: {safe_float(total, 6)} (Free: {safe_float(free, 6)}, Used: {safe_float(used, 6)})")
                        shown_currencies.add(currency)
            
            # Show any other currencies with balances > $0.01
            for currency, amounts in balance_data.items():
                if currency not in shown_currencies and isinstance(amounts, dict):
                    total = amounts.get('total', 0)
                    if total > 0.01:  # Show balances > 1 cent
                        free = amounts.get('free', 0)
                        used = amounts.get('used', 0)
                        balance_lines.append(f"• {currency}: {safe_float(total, 6)} (Free: {safe_float(free, 6)}, Used: {safe_float(used, 6)})")
            
            balance_lines.append("```")
            # Return balance even if we don't have active coin
            return "\n".join(balance_lines) if len(balance_lines) > 2 else ""

        if event_type == "order_filled":
            message = f"""🎯 **Order Filled** - {timestamp}

**🤖 Bot:** `{self.instance.name}`
**💱 Pair:** `{symbol}`
**📊 Exchange:** `{self.instance.exchange}`

**📈 Details:**
• **Side:** {safe_side(payload.get('side'))}
• **Amount:** `{safe_float(payload.get('quantity'), 6)}`
• **Price:** `${safe_float(payload.get('entry_price'), 4)}`
• **Status:** ✅ FILLED
• **PnL:** `${safe_float(payload.get('unrealized_pnl'), 2)}`{format_balance_section(balance)}

✅ **Transaction Complete**"""

        elif event_type == "position_update":
            message = f"""🔄 **Position Update** - {timestamp}

**🤖 Bot:** `{self.instance.name}`
**💱 Pair:** `{symbol}`
**📊 Exchange:** `{self.instance.exchange}`

**📈 Details:**
• **Side:** {safe_side(payload.get('side'))}
• **Size:** `{safe_float(payload.get('quantity'), 6)}`
• **Entry:** `${safe_float(payload.get('entry_price'), 4)}`
• **PnL:** `${safe_float(payload.get('unrealized_pnl'), 2)}`
• **Strategy:** {bot_type}{format_balance_section(balance)}

📊 **Monitoring Continues**"""

        elif event_type == "order_cancelled":
            message = f"""❌ **Order Cancelled** - {timestamp}

**🤖 Bot:** `{self.instance.name}`
**💱 Pair:** `{symbol}`
**📊 Exchange:** `{self.instance.exchange}`

**📈 Details:**
• **Order ID:** `{safe_string(payload.get('order_id'))}`
• **Side:** {safe_side(payload.get('side'))}
• **Amount:** `{safe_float(payload.get('quantity'), 6)}`
• **Status:** ❌ CANCELLED
• **Strategy:** {bot_type}{format_balance_section(balance)}

⚠️ **Action Logged**"""

        elif event_type == "new_order":
            message = f"""🆕 **New Order** - {timestamp}

**🤖 Bot:** `{self.instance.name}`
**💱 Pair:** `{symbol}`
**📊 Exchange:** `{self.instance.exchange}`

**📈 Details:**
• **Order ID:** `{safe_string(payload.get('order_id'))}`
• **Side:** {safe_side(payload.get('side'))}
• **Amount:** `{safe_float(payload.get('quantity'), 6)}`
• **Price:** `${safe_float(payload.get('entry_price'), 4)}`
• **Status:** ⏳ PENDING
• **Strategy:** {bot_type}{format_balance_section(balance)}

⏳ **Awaiting Fill**"""

        else:
            message = f"""📊 **Bot Update** - {timestamp}

**🤖 Bot:** `{self.instance.name}`
**💱 Pair:** `{symbol}`
**📊 Exchange:** `{self.instance.exchange}`
**🛡️ Event:** {event_type}
**Strategy:** {bot_type}{format_balance_section(balance)}

📱 **Monitoring Active**"""

        return message
    
    async def poll_once(self):
        """Perform one polling cycle"""
        cycle_id = f"poll_{int(time.time())}"
        try:
            logger.info(f"[{cycle_id}] Starting poll cycle for instance {self.instance_id} - {self.instance.name}")
            self._log_activity("poll_start", None, f"Starting poll cycle {cycle_id}")
            
            if self.instance.trading_pair:
                logger.info(f"[{cycle_id}] Filtering for trading pair: {self.instance.trading_pair}")
            
            positions = await self.fetch_positions()
            orders = await self.fetch_open_orders()
            trades = await self.fetch_recent_trades()
            balance = await self.fetch_balance() if self.instance.balance_enabled else {}
            
            # Save balance history if enabled and balance was fetched
            if balance and self.instance.balance_enabled:
                logger.info(f"[{cycle_id}] Saving balance history for {self.instance.name} - {len(balance)} currencies")
                self._save_balance_history(balance)
            elif self.instance.balance_enabled:
                logger.warning(f"[{cycle_id}] No balance data to save for {self.instance.name} (balance_enabled=True but balance empty)")
            else:
                logger.info(f"[{cycle_id}] Balance tracking disabled for {self.instance.name}")
            
            logger.info(f"[{cycle_id}] API responses - Positions: {len(positions)}, Orders: {len(orders)}, Trades: {len(trades)}, Balance: {len(balance)} currencies")
            
            # Log the actual symbols returned from the API
            if positions:
                position_symbols = [pos['symbol'] for pos in positions]
                logger.info(f"[{cycle_id}] Position symbols: {position_symbols}")
            
            if orders:
                order_symbols = [order['symbol'] for order in orders]
                logger.info(f"[{cycle_id}] Order symbols: {order_symbols}")
                
            if trades:
                trade_symbols = [trade['symbol'] for trade in trades]
                logger.info(f"[{cycle_id}] Trade symbols: {trade_symbols}")
            
            processed_positions = 0
            for position in positions:
                symbol = position['symbol']
                if not self._should_process_symbol(symbol):
                    continue
                
                processed_positions += 1
                side = position.get('side', 'unknown')
                position_state_key = f"position_{side}"  # Include side in state key
                previous_position = self._get_previous_state(symbol, position_state_key)
                current_hash = self._get_data_hash(position)
                previous_hash = self._get_data_hash(previous_position) if previous_position else None
                
                if current_hash != previous_hash:
                    payload = self._create_event_payload('position_update', symbol, position, balance)
                    await self._send_webhook(payload)
                    await self._send_telegram_notification(payload)
                    self._log_activity("position_update", symbol, "Position updated", payload)
                    self._save_state(symbol, position_state_key, position)
                    logger.info(f"[{cycle_id}] Position change detected for {symbol} {side}")
            
            processed_orders = 0
            for order in orders:
                symbol = order['symbol']
                if not self._should_process_symbol(symbol):
                    continue
                
                processed_orders += 1
                previous_order = self._get_previous_state(symbol, f"order_{order['id']}")
                
                if not previous_order:
                    payload = self._create_event_payload('new_order', symbol, order, balance)
                    await self._send_webhook(payload)
                    await self._send_telegram_notification(payload)
                    self._log_activity("new_order", symbol, "New order detected", payload)
                    self._save_state(symbol, f"order_{order['id']}", order)
                    logger.info(f"[{cycle_id}] New order detected for {symbol}: {order['id']}")
                
                elif order['status'] != previous_order.get('status'):
                    if order['status'] == 'closed':
                        event_type = 'order_filled'
                    elif order['status'] == 'canceled':
                        event_type = 'order_cancelled'
                    else:
                        event_type = 'order_update'
                    
                    payload = self._create_event_payload(event_type, symbol, order, balance)
                    await self._send_webhook(payload)
                    await self._send_telegram_notification(payload)
                    self._log_activity(event_type, symbol, f"Order status changed to {order['status']}", payload)
                    self._save_state(symbol, f"order_{order['id']}", order)
                    logger.info(f"[{cycle_id}] Order status change for {symbol}: {order['id']} -> {order['status']}")
            
            processed_trades = 0
            for trade in trades:
                symbol = trade['symbol']
                if not self._should_process_symbol(symbol):
                    continue
                
                processed_trades += 1
                previous_trade = self._get_previous_state(symbol, f"trade_{trade['id']}")
                
                if not previous_trade:
                    payload = self._create_event_payload('order_filled', symbol, trade, balance)
                    await self._send_webhook(payload)
                    await self._send_telegram_notification(payload)
                    self._log_activity("order_filled", symbol, f"Trade executed: {trade['id']}", payload)
                    self._save_state(symbol, f"trade_{trade['id']}", trade)
                    logger.info(f"[{cycle_id}] Trade executed for {symbol}: {trade['id']}")
            
            def _update_instance():
                self.instance.last_poll = datetime.utcnow()
                self.instance.last_error = None
                self.db.commit()
            
            try:
                self._execute_db_operation(_update_instance, "update_instance")
            except Exception as e:
                logger.error(f"Failed to update instance after poll completion: {e}")
            
            logger.info(f"[{cycle_id}] Poll completed for instance {self.instance_id} - Processed {processed_positions} positions, {processed_orders} orders, {processed_trades} trades")
            self._log_activity("poll_complete", None, f"Poll cycle {cycle_id} completed - {processed_positions} positions, {processed_orders} orders, {processed_trades} trades processed")
            
        except Exception as e:
            error_msg = str(e)
            
            # Check if this is a database connection error
            if isinstance(e, (OperationalError, DisconnectionError)) or 'ssl syscall error' in error_msg.lower() or 'eof detected' in error_msg.lower():
                logger.warning(f"[{cycle_id}] Database connection error for instance {self.instance_id}: {error_msg}")
                
                # Try to recover the database connection
                try:
                    logger.info(f"[{cycle_id}] Attempting to recover database connection...")
                    self._recreate_db_session()
                    logger.info(f"[{cycle_id}] Database connection recovered successfully")
                    # Don't update error status for connection issues as they're recoverable
                    return
                except Exception as recovery_error:
                    logger.error(f"[{cycle_id}] Failed to recover database connection: {recovery_error}")
                    error_msg = f"Database connection recovery failed: {recovery_error}"
            else:
                logger.error(f"[{cycle_id}] Poll failed for instance {self.instance_id}: {error_msg}")
            
            def _update_error():
                self.instance.last_error = error_msg
                self.db.commit()
            
            try:
                self._execute_db_operation(_update_error, "update_error")
            except Exception as update_error:
                logger.error(f"Failed to update instance error status: {update_error}")
            
            self._log_error("poll_failed", error_msg)
            self._log_activity("poll_error", None, f"Poll cycle {cycle_id} failed: {error_msg}")
    
    def close(self):
        """Clean up resources"""
        if self.db:
            self.db.close()

    def _get_active_coin_from_trading_pair(self) -> str:
        """Extract active trading coin from instance trading pair"""
        if not self.instance.trading_pair:
            return ""
        
        trading_pair = self.instance.trading_pair.upper()
        
        # Handle formats like 'LTC/USDT:USDT', 'LTC/USDT', 'LTCUSDT'
        if '/' in trading_pair:
            base_currency = trading_pair.split('/')[0]
        elif ':' in trading_pair:
            base_currency = trading_pair.split(':')[0].split('/')[0] if '/' in trading_pair else trading_pair.split(':')[0]
        else:
            # Handle LTCUSDT format
            if trading_pair.endswith('USDT'):
                base_currency = trading_pair[:-4]
            elif trading_pair.endswith('BTC'):
                base_currency = trading_pair[:-3]
            elif trading_pair.endswith('ETH'):
                base_currency = trading_pair[:-3]
            else:
                base_currency = trading_pair
        
        return base_currency

async def run_poller(instance_id: int):
    """Run poller for a specific instance"""
    poller = None
    try:
        poller = ExchangePoller(instance_id)
        
        while True:
            db = SessionLocal()
            instance = db.query(BotInstance).filter(BotInstance.id == instance_id).first()
            db.close()
            
            if not instance or not instance.is_active:
                logger.info(f"Instance {instance_id} is no longer active, stopping poller")
                break
            
            await poller.poll_once()
            await asyncio.sleep(instance.polling_interval)
            
    except Exception as e:
        logger.error(f"Poller for instance {instance_id} crashed: {e}")
    finally:
        if poller:
            poller.close()
