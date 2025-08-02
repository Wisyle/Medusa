import asyncio
import json
import ssl
import time
import traceback
from collections import deque
from datetime import datetime
from typing import List, Optional, Dict, Deque

import websockets

import config
import utils

# Initialize the logger from the utils module
logger = utils.setup_logging()

# A set to track contract IDs for which a close notification has already been sent.
# This helps prevent duplicate processing in a distributed or concurrent environment.
closed_trades = set()


class Trade:
    """A data class to represent a single trade and its state."""
    def __init__(self, contract_id: str, symbol: str, stake: float, growth_rate: float, currency: str,
                 entry_price: float, take_profit: Optional[float] = None):
        self.contract_id = contract_id
        self.symbol = symbol
        self.stake = stake
        self.growth_rate = growth_rate  # In decimal form (e.g., 0.01 for 1%)
        self.currency = currency
        self.entry_price = entry_price
        self.take_profit = take_profit  # In percentage form (e.g., 15 for 15%)
        
        self.open_time = datetime.now()
        self.close_time: Optional[datetime] = None
        self.status: str = "open"  # Can be "open", "closing", "closed", "error"
        
        self.profit_loss: float = 0.0
        self.pre_trade_balance: float = 0.0
        self.post_trade_balance: float = 0.0
        
        self.close_attempts: int = 0
        
        # Calculate the estimated time to reach take-profit
        if take_profit and growth_rate > 0:
            take_profit_decimal = take_profit / 100.0
            # Time (seconds) = Target Profit / Growth Rate per second
            raw_time = take_profit_decimal / growth_rate
            self.estimated_tp_time = raw_time + 1  # Add a 1-second buffer
            self.contract_duration = int(self.estimated_tp_time)
        else:
            self.estimated_tp_time = None
            self.contract_duration = 2  # A default minimum duration


class DerivAPI:
    """
    Handles WebSocket connection and communication with the Deriv API.
    This class is responsible for low-level API interactions.
    """
    def __init__(self):
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.session_active = False
        self.connected = False
        self.current_api_token = config.CURRENCY_API_TOKENS.get('XRP')
        if not self.current_api_token:
            raise ValueError("XRP API token is required in config.")
            
        self.message_queue: Deque[str] = deque(maxlen=100)
        self.req_id_counter = 0
        self.connection_attempts = 0
        self.max_connection_attempts = 5
        self.keepalive_task = None

    async def _send_request(self, payload: dict) -> None:
        """Sends a JSON payload to the WebSocket server."""
        if not self.websocket or not self.connected:
            raise ConnectionError("WebSocket is not connected.")
        await self.websocket.send(json.dumps(payload))

    async def _receive_message(self, timeout: int = 10) -> Dict:
        """Receives a message from the WebSocket server."""
        if not self.websocket or not self.connected:
            raise ConnectionError("WebSocket is not connected.")
        try:
            message = await asyncio.wait_for(self.websocket.recv(), timeout=timeout)
            data = json.loads(message)
            # Log non-ping messages for debugging
            if data.get("msg_type") not in ["ping", "pong"]:
                logger.debug(f"Received: {data}")
            return data
        except asyncio.TimeoutError:
            logger.error("WebSocket receive timeout.")
            raise
        except websockets.exceptions.ConnectionClosed:
            logger.error("WebSocket connection closed unexpectedly.")
            self.connected = False
            self.session_active = False
            raise

    async def _send_keepalive(self):
        """Sends a ping every 30 seconds to keep the connection alive."""
        while self.connected and self.websocket:
            try:
                await self._send_request({"ping": 1})
                logger.debug("Sent keepalive ping.")
                await asyncio.sleep(30)
            except (ConnectionError, websockets.exceptions.ConnectionClosed):
                logger.warning("Keepalive failed. Connection lost.")
                break

    async def connect(self) -> bool:
        """Establishes and authorizes a connection to the Deriv WebSocket API."""
        if self.session_active:
            return True
            
        if self.connection_attempts >= self.max_connection_attempts:
            logger.error(f"Maximum connection attempts ({self.max_connection_attempts}) reached.")
            return False
            
        self.connection_attempts += 1
        logger.info(f"Attempting Deriv WebSocket connection (Attempt {self.connection_attempts}).")

        try:
            ws_url = f"wss://ws.derivws.com/websockets/v3?app_id={config.DERIV_APP_ID}"
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            self.websocket = await websockets.connect(
                ws_url, ping_interval=None, ssl=ssl_context
            )
            self.connected = True
            
            await self._send_request({"authorize": self.current_api_token})
            response = await self._receive_message()

            if "error" in response:
                error_msg = response['error'].get('message', 'Unknown authorization error')
                logger.error(f"Authorization failed: {error_msg}")
                await self.disconnect()
                return False
                
            self.session_active = True
            self.connection_attempts = 0  # Reset on success
            logger.info("Deriv WebSocket connected and authorized successfully.")
            
            if self.keepalive_task is None or self.keepalive_task.done():
                self.keepalive_task = asyncio.create_task(self._send_keepalive())
            
            return True

        except Exception as e:
            logger.error(f"Connection attempt failed: {e}")
            await self.disconnect()
            return False

    async def disconnect(self):
        """Closes the WebSocket connection."""
        self.session_active = False
        self.connected = False
        if self.keepalive_task and not self.keepalive_task.done():
            self.keepalive_task.cancel()
        if self.websocket:
            try:
                await self.websocket.close()
            except websockets.exceptions.ConnectionClosed:
                pass  # Already closed
            self.websocket = None
        logger.info("WebSocket connection closed.")

    async def fetch_balance(self) -> Optional[Dict]:
        """Fetches the current account balance."""
        try:
            logger.debug("Attempting to fetch balance")
            
            if not await self.connect():
                logger.error("Cannot fetch balance - API connection failed")
                return None
                
            self.req_id_counter += 1
            balance_req = {"balance": 1, "req_id": self.req_id_counter}
            
            logger.debug(f"Sending balance request: {balance_req}")
            await self._send_request(balance_req)
            
            # Look for the response with the matching request ID
            timeout_count = 0
            max_timeout = 15  # 15 second timeout for balance
            
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    logger.debug(f"Received balance response: {data}")
                    
                    if "error" in data:
                        error_msg = data['error'].get('message', 'Unknown error')
                        logger.error(f"Balance request failed: {error_msg}")
                        return None
                    
                    if data.get("req_id") == self.req_id_counter and data.get("msg_type") == "balance":
                        balance_data = data.get('balance')
                        if balance_data:
                            logger.info(f"Fetched balance: {balance_data}")
                            return balance_data
                        else:
                            logger.error("Balance response missing balance data")
                            return None
                            
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error in balance response: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing balance response: {e}")
                    continue
                    
                # Timeout check
                timeout_count += 1
                if timeout_count > max_timeout:
                    logger.error("Timeout waiting for balance response")
                    return None
                    
            logger.error("Failed to get balance response")
            return None
            
        except Exception as e:
            logger.error(f"Fetch balance failed with exception: {e}")
            return None

    async def place_trade(self, symbol: str, amount: float, growth_rate: float, currency: str, take_profit: float) -> Optional[Trade]:
        """Places a trade and returns a Trade object if successful."""
        try:
            logger.info(f"Attempting to place trade: {symbol}, {amount}, {growth_rate}%, {currency}, {take_profit}%")
            
            if not await self.connect():
                logger.error("Cannot place trade - API connection failed")
                return None
            
            # Validate input parameters
            if not all([symbol, amount > 0, growth_rate > 0, currency, take_profit > 0]):
                logger.error(f"Invalid trade parameters: symbol={symbol}, amount={amount}, growth_rate={growth_rate}, currency={currency}, take_profit={take_profit}")
                return None
            
            # Calculate and log take profit amount for debugging
            take_profit_amount = amount * take_profit / 100.0
            logger.info(f"Calculated take profit amount: {take_profit_amount:.4f} {currency} ({take_profit}% of {amount} {currency})")
        
            # Step 1: Get a proposal
            proposal_req = {
                "proposal": 1,
                "symbol": symbol,
                "contract_type": "ACCU",
                "currency": currency,
                "amount": amount,
                "basis": "stake",
                "growth_rate": growth_rate / 100.0, # Convert percentage to decimal
                "limit_order": {"take_profit": take_profit_amount}
            }
            
            logger.info(f"Proposal details: symbol={symbol}, stake={amount}, growth_rate={growth_rate / 100.0:.4f}, take_profit_amount={take_profit_amount:.4f}")
            
            logger.debug(f"Sending proposal request: {proposal_req}")
            await self._send_request(proposal_req)

            # Look for the proposal response
            timeout_count = 0
            max_timeout = 30  # 30 second timeout
            
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    logger.debug(f"Received proposal response: {data}")
                    
                    if "error" in data:
                        error_msg = data['error'].get('message', 'Unknown error')
                        error_code = data['error'].get('code', 'Unknown code')
                        error_details = data['error'].get('details', {})
                        logger.error(f"Proposal failed: {error_msg} (Code: {error_code})")
                        logger.error(f"Full error details: {data['error']}")
                        logger.error(f"Failed proposal was: symbol={symbol}, stake={amount}, growth_rate={growth_rate}%, take_profit={take_profit}%, calculated_tp_amount={take_profit_amount:.4f}")
                        return None
                        
                    if data.get("msg_type") == "proposal":
                        proposal_id = data["proposal"]["id"]
                        ask_price = float(data["proposal"]["ask_price"])
                        
                        logger.info(f"Proposal accepted: {proposal_id}, price: {ask_price}")
                        
                        # Step 2: Buy the contract
                        buy_req = {"buy": proposal_id, "price": ask_price}
                        logger.debug(f"Sending buy request: {buy_req}")
                        await self._send_request(buy_req)
                        
                        # Look for the buy confirmation
                        async for buy_message in self.websocket:
                            try:
                                buy_data = json.loads(buy_message)
                                logger.debug(f"Received buy response: {buy_data}")
                                
                                if "error" in buy_data:
                                    error_msg = buy_data['error'].get('message', 'Unknown error')
                                    logger.error(f"Buy failed: {error_msg}")
                                    return None
                                    
                                if buy_data.get("msg_type") == "buy":
                                    contract_id = str(buy_data["buy"]["contract_id"])
                                    entry_price = buy_data["buy"].get("entry_spot", 0.0)
                                    
                                    logger.info(f"Trade placed successfully: {contract_id}")
                                    
                                    # Create and return a Trade object
                                    trade = Trade(
                                        contract_id=contract_id,
                                        symbol=symbol,
                                        stake=amount,
                                        growth_rate=growth_rate / 100.0,
                                        currency=currency,
                                        entry_price=entry_price,
                                        take_profit=take_profit
                                    )
                                    logger.info(f"Created Trade object: {trade.__dict__}")
                                    return trade
                                    
                            except json.JSONDecodeError as e:
                                logger.error(f"JSON decode error in buy response: {e}")
                                continue
                            except Exception as e:
                                logger.error(f"Error processing buy response: {e}")
                                continue
                                
                        logger.error("Failed to get buy confirmation")
                        return None
                        
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error in proposal response: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing proposal response: {e}")
                    continue
                    
                # Timeout check
                timeout_count += 1
                if timeout_count > max_timeout:
                    logger.error("Timeout waiting for proposal response")
                    return None
                    
            logger.error("Failed to get proposal response")
            return None
            
        except Exception as e:
            logger.error(f"Place trade failed with exception: {e}\n{traceback.format_exc()}")
            return None

    async def sell_contract(self, contract_id: str) -> Optional[Dict]:
        """Sells an open contract."""
        if not await self.connect():
            return None
        try:
            await self._send_request({"sell": int(contract_id), "price": 0}) # Price 0 to sell at market
            
            async for message in self.websocket:
                data = json.loads(message)
                if "error" in data:
                    logger.error(f"Sell failed for {contract_id}: {data['error'].get('message')}")
                    return None
                if data.get("msg_type") == "sell":
                    logger.info(f"Contract {contract_id} sold successfully.")
                    return data['sell']
            return None
        except Exception as e:
            logger.error(f"Sell contract failed: {e}")
            return None

    async def get_trade_outcome(self, contract_id: str) -> Optional[Dict]:
        """Get the outcome of a completed trade. Robust polling until contract is closed or timeout."""
        try:
            await self._send_request({
                "proposal_open_contract": 1,
                "contract_id": contract_id,
                "subscribe": 1
            })

            contract = None
            start_time = time.time()
            timeout = 60  # seconds
            while time.time() - start_time < timeout:
                response = await self._receive_message()
                if not response or "error" in response:
                    logger.error(f"Error getting trade outcome: {response.get('error', 'Unknown error') if response else 'No response'}")
                    return None
                contract = response.get("proposal_open_contract", {})
                if contract and contract.get("is_sold", 0) == 1:
                    break
                await asyncio.sleep(1)

            if not contract or contract.get("is_sold", 0) != 1:
                logger.error(f"Timeout or contract not closed for {contract_id}")
                return None

            return {
                "profit": float(contract.get("profit", 0)),
                "buy_price": float(contract.get("buy_price", 0)),
                "sell_price": float(contract.get("sell_price", 0)),
                "status": contract.get("status", "unknown")
            }
        except Exception as e:
            logger.error(f"Error in get_trade_outcome: {e}\n{traceback.format_exc()}")
            return None
