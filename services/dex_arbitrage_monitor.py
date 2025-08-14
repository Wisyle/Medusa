#!/usr/bin/env python3
"""
DEX Arbitrage Monitor - Monitor and detect arbitrage opportunities across DEXs
"""

import asyncio
import time
import json
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
from sqlalchemy.orm import Session
from telegram import Bot

from app.database import SessionLocal
from models.dex_arbitrage_model import DEXArbitrageInstance, DEXOpportunity
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DEXArbitrageMonitor:
    def __init__(self, instance_id: int):
        self.instance_id = instance_id
        self.db = SessionLocal()
        self.instance = self.db.query(DEXArbitrageInstance).filter(
            DEXArbitrageInstance.id == instance_id
        ).first()
        
        if not self.instance:
            raise ValueError(f"DEX arbitrage instance {instance_id} not found")
        
        self.telegram_bot = self._init_telegram()
        
        self.dex_apis = {
            'pancakeswap': 'https://api.pancakeswap.info/api/v2/tokens/',
            'uniswap': 'https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2',
            'raydium': 'https://api.raydium.io/v2/sdk/liquidity/mainnet.json',
            'jupiter': 'https://price.jup.ag/v4/price',
            'orca': 'https://api.orca.so/v1/whirlpool/list',
            'sushiswap': 'https://api.sushi.com/v1/pools'
        }
        
    def _init_telegram(self) -> Optional[Bot]:
        """Initialize Telegram bot for notifications"""
        token = self.instance.telegram_bot_token or settings.default_telegram_bot_token
        if token:
            try:
                return Bot(token=token)
            except Exception as e:
                logger.error(f"Failed to initialize Telegram bot: {e}")
        return None
    
    def _get_bnb_chain_price(self, token_pair: str, dex: str) -> Optional[Decimal]:
        """Get price from BNB Chain DEXs (PancakeSwap, etc.)"""
        try:
            if dex.lower() == 'pancakeswap':
                base_token, quote_token = token_pair.split('/')
                url = f"https://api.pancakeswap.info/api/v2/tokens/{base_token.lower()}"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data and 'price' in data['data']:
                        return Decimal(str(data['data']['price']))
                        
            elif dex.lower() == 'biswap':
                url = f"https://api.biswap.org/api/v1/market/ticker/{token_pair.replace('/', '_')}"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'last_price' in data:
                        return Decimal(str(data['last_price']))
                        
        except Exception as e:
            logger.error(f"Error fetching BNB price from {dex}: {e}")
        
        return None
    
    def _get_solana_price(self, token_pair: str, dex: str) -> Optional[Decimal]:
        """Get price from Solana DEXs (Raydium, Orca, Jupiter)"""
        try:
            base_token, quote_token = token_pair.split('/')
            
            if dex.lower() == 'jupiter':
                url = f"https://price.jup.ag/v4/price?ids={base_token}&vsToken={quote_token}"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data and base_token in data['data']:
                        return Decimal(str(data['data'][base_token]['price']))
                        
            elif dex.lower() == 'raydium':
                url = "https://api.raydium.io/v2/sdk/liquidity/mainnet.json"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    for pool in data.get('official', []):
                        if (pool.get('baseMint') == base_token and 
                            pool.get('quoteMint') == quote_token):
                            base_reserve = Decimal(str(pool.get('baseReserve', 0)))
                            quote_reserve = Decimal(str(pool.get('quoteReserve', 0)))
                            if base_reserve > 0:
                                return quote_reserve / base_reserve
                                
            elif dex.lower() == 'orca':
                url = "https://api.orca.so/v1/whirlpool/list"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    for pool in data.get('whirlpools', []):
                        if (pool.get('tokenA', {}).get('mint') == base_token and
                            pool.get('tokenB', {}).get('mint') == quote_token):
                            return Decimal(str(pool.get('price', 0)))
                            
        except Exception as e:
            logger.error(f"Error fetching Solana price from {dex}: {e}")
        
        return None
    
    def _get_ethereum_price(self, token_pair: str, dex: str) -> Optional[Decimal]:
        """Get price from Ethereum DEXs (Uniswap, SushiSwap)"""
        try:
            if dex.lower() == 'uniswap':
                base_token, quote_token = token_pair.split('/')
                query = """
                {
                  pairs(where: {token0: "%s", token1: "%s"}) {
                    token0Price
                    token1Price
                    reserveUSD
                  }
                }
                """ % (base_token.lower(), quote_token.lower())
                
                response = requests.post(
                    self.dex_apis['uniswap'],
                    json={'query': query},
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    pairs = data.get('data', {}).get('pairs', [])
                    if pairs:
                        return Decimal(str(pairs[0]['token0Price']))
                        
            elif dex.lower() == 'sushiswap':
                url = f"https://api.sushi.com/v1/pools?chainId=1&tokenA={token_pair.split('/')[0]}&tokenB={token_pair.split('/')[1]}"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if data and len(data) > 0:
                        pool = data[0]
                        return Decimal(str(pool.get('token0Price', 0)))
                        
        except Exception as e:
            logger.error(f"Error fetching Ethereum price from {dex}: {e}")
        
        return None
    
    def _get_price_from_dex(self, token_pair: str, dex: str, chain: str) -> Optional[Decimal]:
        """Get price from specific DEX based on chain"""
        if chain.lower() == 'bnb':
            return self._get_bnb_chain_price(token_pair, dex)
        elif chain.lower() == 'solana':
            return self._get_solana_price(token_pair, dex)
        elif chain.lower() == 'ethereum':
            return self._get_ethereum_price(token_pair, dex)
        else:
            logger.error(f"Unsupported chain: {chain}")
            return None
    
    def _calculate_arbitrage_opportunity(
        self, 
        primary_price: Decimal, 
        secondary_price: Decimal, 
        max_amount: Decimal
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """Calculate arbitrage profit percentage and optimal trade amount"""
        if primary_price <= 0 or secondary_price <= 0:
            return Decimal('0'), Decimal('0'), Decimal('0')
        
        if primary_price < secondary_price:
            profit_pct = ((secondary_price - primary_price) / primary_price) * 100
            buy_price = primary_price
            sell_price = secondary_price
        else:
            profit_pct = ((primary_price - secondary_price) / secondary_price) * 100
            buy_price = secondary_price
            sell_price = primary_price
        
        optimal_amount = min(max_amount, Decimal('1000'))  # Cap at $1000 for safety
        
        potential_profit = optimal_amount * (profit_pct / 100)
        
        return profit_pct, optimal_amount, potential_profit
    
    def _estimate_gas_cost(self, chain: str, trade_amount: Decimal) -> Decimal:
        """Estimate gas cost for the arbitrage transaction"""
        gas_costs = {
            'bnb': Decimal('0.001'),      # ~$0.30 in BNB
            'solana': Decimal('0.00025'),  # ~$0.01 in SOL
            'ethereum': Decimal('0.01'),   # ~$20 in ETH (high gas)
        }
        
        base_cost = gas_costs.get(chain.lower(), Decimal('0.01'))
        
        if trade_amount > 1000:
            base_cost *= Decimal('1.5')
        
        return base_cost
    
    async def _send_opportunity_notification(self, opportunity: DEXOpportunity):
        """Send Telegram notification about arbitrage opportunity"""
        if not self.telegram_bot:
            return
        
        try:
            message = f"""
🚀 **DEX Arbitrage Opportunity Detected!**

💰 **Pair:** {opportunity.pair}
🔗 **Chain:** {opportunity.chain.upper()}
📊 **Profit:** {opportunity.profit_percentage:.2f}%

💹 **Prices:**
• {opportunity.primary_dex}: ${opportunity.primary_price:.6f}
• {opportunity.secondary_dex}: ${opportunity.secondary_price:.6f}

💵 **Trade Details:**
• Optimal Amount: ${opportunity.optimal_amount:.2f}
• Potential Profit: ${opportunity.potential_profit_usd:.2f}
• Est. Gas Cost: ${opportunity.estimated_gas_cost:.4f}
• Net Profit: ${opportunity.net_profit_usd:.2f}

⏰ **Detected:** {opportunity.detected_at.strftime('%H:%M:%S UTC')}

{'🤖 **Auto-execution enabled**' if self.instance.auto_execute else '⚠️ **Manual review required**'}
"""
            
            send_params = {
                'chat_id': self.instance.telegram_chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            
            if self.instance.telegram_topic_id:
                send_params['message_thread_id'] = int(self.instance.telegram_topic_id)
            
            await self.telegram_bot.send_message(**send_params)
            logger.info(f"Arbitrage opportunity notification sent for {opportunity.pair}")
            
        except Exception as e:
            logger.error(f"Failed to send arbitrage notification: {e}")
    
    def _send_webhook_notification(self, opportunity: DEXOpportunity):
        """Send webhook notification about arbitrage opportunity"""
        if not self.instance.webhook_url:
            return
        
        try:
            payload = {
                'event_type': 'arbitrage_opportunity',
                'instance_id': self.instance_id,
                'instance_name': self.instance.name,
                'chain': opportunity.chain,
                'pair': opportunity.pair,
                'primary_dex': opportunity.primary_dex,
                'secondary_dex': opportunity.secondary_dex,
                'primary_price': float(opportunity.primary_price),
                'secondary_price': float(opportunity.secondary_price),
                'profit_percentage': float(opportunity.profit_percentage),
                'potential_profit_usd': float(opportunity.potential_profit_usd),
                'optimal_amount': float(opportunity.optimal_amount),
                'estimated_gas_cost': float(opportunity.estimated_gas_cost),
                'net_profit_usd': float(opportunity.net_profit_usd),
                'detected_at': opportunity.detected_at.isoformat(),
                'auto_execute': self.instance.auto_execute
            }
            
            response = requests.post(
                self.instance.webhook_url,
                json=payload,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                logger.info(f"Webhook notification sent for arbitrage opportunity")
            else:
                logger.warning(f"Webhook returned status {response.status_code}")
                
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")
    
    async def check_arbitrage_opportunity(self) -> Optional[DEXOpportunity]:
        """Check for arbitrage opportunities between configured DEXs"""
        try:
            primary_price = self._get_price_from_dex(
                self.instance.dex_pair,
                self.instance.primary_dex,
                self.instance.chain
            )
            
            secondary_price = self._get_price_from_dex(
                self.instance.dex_pair,
                self.instance.secondary_dex,
                self.instance.chain
            )
            
            if not primary_price or not secondary_price:
                logger.warning(f"Could not fetch prices for {self.instance.dex_pair}")
                return None
            
            profit_pct, optimal_amount, potential_profit = self._calculate_arbitrage_opportunity(
                primary_price, secondary_price, self.instance.max_trade_amount
            )
            
            if profit_pct < self.instance.min_profit_threshold:
                return None
            
            gas_cost = self._estimate_gas_cost(self.instance.chain, optimal_amount)
            net_profit = potential_profit - gas_cost
            
            opportunity = DEXOpportunity(
                instance_id=self.instance_id,
                chain=self.instance.chain,
                pair=self.instance.dex_pair,
                primary_dex=self.instance.primary_dex,
                secondary_dex=self.instance.secondary_dex,
                primary_price=primary_price,
                secondary_price=secondary_price,
                profit_percentage=profit_pct,
                potential_profit_usd=potential_profit,
                optimal_amount=optimal_amount,
                estimated_gas_cost=gas_cost,
                net_profit_usd=net_profit
            )
            
            self.db.add(opportunity)
            self.db.commit()
            self.db.refresh(opportunity)
            
            self.instance.last_check = datetime.utcnow()
            self.instance.last_opportunity = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Arbitrage opportunity detected: {profit_pct:.2f}% profit on {self.instance.dex_pair}")
            
            await self._send_opportunity_notification(opportunity)
            self._send_webhook_notification(opportunity)
            
            return opportunity
            
        except Exception as e:
            logger.error(f"Error checking arbitrage opportunity: {e}")
            return None
    
    async def run_monitoring_loop(self, check_interval: int = 30):
        """Run continuous monitoring loop"""
        logger.info(f"Starting DEX arbitrage monitoring for {self.instance.name}")
        
        while self.instance.is_active:
            try:
                self.db.refresh(self.instance)
                
                if not self.instance.is_active:
                    break
                
                opportunity = await self.check_arbitrage_opportunity()
                
                if opportunity:
                    logger.info(f"Found arbitrage opportunity: {opportunity.profit_percentage:.2f}% profit")
                
                self.instance.last_check = datetime.utcnow()
                self.db.commit()
                
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    def close(self):
        """Clean up resources"""
        if self.db:
            self.db.close()

async def run_dex_arbitrage_monitor(instance_id: int):
    """Run DEX arbitrage monitor for a specific instance"""
    monitor = None
    try:
        monitor = DEXArbitrageMonitor(instance_id)
        await monitor.run_monitoring_loop()
    except Exception as e:
        logger.error(f"DEX arbitrage monitor for instance {instance_id} crashed: {e}")
    finally:
        if monitor:
            monitor.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        instance_id = int(sys.argv[1])
        asyncio.run(run_dex_arbitrage_monitor(instance_id))
    else:
        logger.error("Please provide instance ID as argument")
