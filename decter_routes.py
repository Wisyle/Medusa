"""
Decter 001 API Routes for TARC Lighthouse Integration
FastAPI routes for controlling Decter 001 trading bot
"""

from fastapi import APIRouter, HTTPException, Depends, Form
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from decter_controller import decter_controller, DecterConfig, DecterStatus
from auth import get_current_active_user
from database import User

logger = logging.getLogger(__name__)

# Create router for Decter 001 endpoints
decter_router = APIRouter(prefix="/api/decter", tags=["Decter 001"])


# Pydantic models for request/response
class DecterConfigRequest(BaseModel):
    stake: float = Field(..., gt=0, description="Stake amount (minimum 0.4)")
    growth_rate: float = Field(..., gt=0, le=5, description="Growth rate percentage (1-5%)")
    take_profit: float = Field(..., gt=0, description="Take profit percentage")
    index: str = Field(..., description="Trading index (e.g., R_10, R_25)")
    currency: str = Field(..., description="Currency (XRP, BTC, ETH, etc.)")
    max_loss_amount: float = Field(..., gt=0, description="Maximum loss amount")
    max_win_amount: float = Field(..., gt=0, description="Maximum win amount")


class DecterCommandRequest(BaseModel):
    command: str = Field(..., description="Telegram command to send")


class TelegramConfigRequest(BaseModel):
    bot_token: str = Field(..., description="Telegram bot token")
    group_id: str = Field(..., description="Telegram group/chat ID")
    topic_id: Optional[str] = Field(None, description="Telegram topic ID (optional)")


class TransactionLogRequest(BaseModel):
    message: str = Field(..., description="Notification message")
    transaction_type: Optional[str] = Field(None, description="Transaction type")
    amount: Optional[float] = Field(None, description="Transaction amount")
    result: Optional[str] = Field(None, description="Transaction result")


class DerivConfigRequest(BaseModel):
    deriv_app_id: str = Field(..., description="Deriv application ID")
    xrp_api_token: Optional[str] = Field(None, description="XRP API token")
    btc_api_token: Optional[str] = Field(None, description="BTC API token")
    eth_api_token: Optional[str] = Field(None, description="ETH API token")
    ltc_api_token: Optional[str] = Field(None, description="LTC API token")
    usdt_api_token: Optional[str] = Field(None, description="USDT API token")
    usd_api_token: Optional[str] = Field(None, description="USD API token")


class EngineConfigRequest(BaseModel):
    # Multi-currency settings
    selected_currency: Optional[str] = Field("XRP", description="Currently selected trading currency")
    supported_currencies: Optional[List[str]] = Field(["XRP", "BTC", "ETH", "LTC", "USDT", "USD"], description="Supported currencies")
    
    # Continuous Engine parameters
    consecutive_wins_threshold: Optional[int] = Field(10, description="Consecutive wins before risk reduction")
    max_profit_cap: Optional[float] = Field(1000.0, description="Maximum profit before stopping")
    risk_reduction_factor: Optional[float] = Field(0.7, description="Risk reduction factor after win streak")
    
    # Decision Engine parameters
    max_loss_threshold: Optional[float] = Field(100.0, description="Maximum loss before recovery mode")
    drawdown_threshold: Optional[float] = Field(0.15, description="Drawdown percentage threshold")
    volatility_lookback_periods: Optional[int] = Field(1800, description="Periods for volatility analysis")
    recovery_risk_multiplier: Optional[float] = Field(1.8, description="Risk multiplier for recovery trades")
    
    # Engine control
    enable_continuous_engine: Optional[bool] = Field(True, description="Enable continuous monitoring engine")
    enable_decision_engine: Optional[bool] = Field(True, description="Enable decision/recovery engine")
    diagnostic_logging: Optional[bool] = Field(True, description="Enable detailed diagnostic logging")


class CurrencySwitchRequest(BaseModel):
    currency: str = Field(..., description="Currency to switch to")


class TradeHistoryRequest(BaseModel):
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")
    currency: Optional[str] = Field(None, description="Filter by currency")
    engine: Optional[str] = Field(None, description="Filter by engine (continuous/decision)")
    result: Optional[str] = Field(None, description="Filter by result (win/loss/breakeven)")
    asset_pair: Optional[str] = Field(None, description="Filter by asset pair")
    limit: Optional[int] = Field(50, description="Number of records to return")
    offset: Optional[int] = Field(0, description="Number of records to skip")


class ExportRequest(BaseModel):
    format: str = Field("csv", description="Export format (csv, json, pdf)")
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")
    currency: Optional[str] = Field(None, description="Filter by currency")
    engine: Optional[str] = Field(None, description="Filter by engine")


class DecterStatusResponse(BaseModel):
    status: str
    is_running: bool
    process_id: Optional[int] = None
    uptime_seconds: Optional[int] = None
    stats: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None


# Health check endpoint
@decter_router.get("/health")
async def decter_health():
    """Health check for Decter 001 integration"""
    return {
        "service": "decter-001-integration",
        "status": "healthy",
        "controller_initialized": decter_controller is not None
    }


# Status endpoints
@decter_router.get("/status", response_model=DecterStatusResponse)
async def get_decter_status(current_user: User = Depends(get_current_active_user)):
    """Get comprehensive Decter 001 status"""
    try:
        status = decter_controller.get_status()
        return JSONResponse(content=status)
    except Exception as e:
        logger.error(f"❌ Error getting Decter status: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")


@decter_router.get("/performance")
async def get_decter_performance(current_user: User = Depends(get_current_active_user)):
    """Get Decter 001 performance summary"""
    try:
        performance = decter_controller.get_performance_summary()
        return JSONResponse(content=performance)
    except Exception as e:
        logger.error(f"❌ Error getting Decter performance: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting performance: {str(e)}")


# Control endpoints
@decter_router.post("/start")
async def start_decter(current_user: User = Depends(get_current_active_user)):
    """Start Decter 001 bot"""
    try:
        result = decter_controller.start()
        if result["success"]:
            logger.info(f"✅ Decter 001 started by user: {getattr(current_user, 'email', 'unknown')}")
            return JSONResponse(content=result)
        else:
            logger.warning(f"⚠️ Failed to start Decter 001: {result['message']}")
            # Return 400 with specific error details
            raise HTTPException(status_code=400, detail=f"Error starting Decter 001: {result['message']}")
    except HTTPException:
        raise  # Re-raise HTTPExceptions as-is
    except Exception as e:
        logger.error(f"❌ Error starting Decter: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error starting Decter: {str(e)}")


@decter_router.post("/stop")
async def stop_decter(current_user: User = Depends(get_current_active_user)):
    """Stop Decter 001 bot"""
    try:
        result = decter_controller.stop()
        if result["success"]:
            logger.info(f"✅ Decter 001 stopped by user: {getattr(current_user, 'email', 'unknown')}")
            return JSONResponse(content=result)
        else:
            logger.warning(f"⚠️ Failed to stop Decter 001: {result['message']}")
            raise HTTPException(status_code=400, detail=result["message"])
    except Exception as e:
        logger.error(f"❌ Error stopping Decter: {e}")
        raise HTTPException(status_code=500, detail=f"Error stopping Decter: {str(e)}")


@decter_router.post("/restart")
async def restart_decter(current_user: User = Depends(get_current_active_user)):
    """Restart Decter 001 bot"""
    try:
        result = decter_controller.restart()
        if result["success"]:
            logger.info(f"✅ Decter 001 restarted by user: {getattr(current_user, 'email', 'unknown')}")
            return JSONResponse(content=result)
        else:
            logger.warning(f"⚠️ Failed to restart Decter 001: {result['message']}")
            raise HTTPException(status_code=400, detail=result["message"])
    except Exception as e:
        logger.error(f"❌ Error restarting Decter: {e}")
        raise HTTPException(status_code=500, detail=f"Error restarting Decter: {str(e)}")


# Configuration endpoints
@decter_router.post("/config")
async def set_decter_config(
    config: DecterConfigRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Set Decter 001 trading parameters"""
    try:
        decter_config = DecterConfig(
            stake=config.stake,
            growth_rate=config.growth_rate,
            take_profit=config.take_profit,
            index=config.index,
            currency=config.currency,
            max_loss_amount=config.max_loss_amount,
            max_win_amount=config.max_win_amount
        )
        
        result = decter_controller.set_parameters(decter_config)
        if result["success"]:
            logger.info(f"✅ Decter 001 config updated by user: {getattr(current_user, 'email', 'unknown')}")
            return JSONResponse(content=result)
        else:
            logger.warning(f"⚠️ Failed to update Decter config: {result['message']}")
            raise HTTPException(status_code=400, detail=result["message"])
    except Exception as e:
        logger.error(f"❌ Error setting Decter config: {e}")
        raise HTTPException(status_code=500, detail=f"Error setting config: {str(e)}")


@decter_router.get("/config")
async def get_decter_config(current_user: User = Depends(get_current_active_user)):
    """Get current Decter 001 configuration"""
    try:
        config = decter_controller._get_current_config()
        return JSONResponse(content=config or {})
    except Exception as e:
        logger.error(f"❌ Error getting Decter config: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting config: {str(e)}")


# Trading data endpoints
@decter_router.get("/trades")
async def get_decter_trades(
    limit: int = 50,
    current_user: User = Depends(get_current_active_user)
):
    """Get Decter 001 trade history"""
    try:
        trades = decter_controller.get_trade_history(limit)
        return JSONResponse(content={"trades": trades, "count": len(trades)})
    except Exception as e:
        logger.error(f"❌ Error getting Decter trades: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting trades: {str(e)}")


@decter_router.get("/stats")
async def get_decter_stats(current_user: User = Depends(get_current_active_user)):
    """Get detailed Decter 001 statistics"""
    try:
        stats = decter_controller.get_stats()
        if stats:
            return JSONResponse(content=stats.__dict__)
        else:
            return JSONResponse(content={})
    except Exception as e:
        logger.error(f"❌ Error getting Decter stats: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")


# Command endpoints
@decter_router.post("/command")
async def send_decter_command(
    command_req: DecterCommandRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Send command to Decter 001"""
    try:
        result = decter_controller.send_telegram_command(command_req.command)
        if result["success"]:
            logger.info(f"✅ Command sent to Decter by user: {getattr(current_user, 'email', 'unknown')}: {command_req.command}")
            return JSONResponse(content=result)
        else:
            logger.warning(f"⚠️ Failed to send command: {result['message']}")
            raise HTTPException(status_code=400, detail=result["message"])
    except Exception as e:
        logger.error(f"❌ Error sending command: {e}")
        raise HTTPException(status_code=500, detail=f"Error sending command: {str(e)}")


# Information endpoints
@decter_router.get("/indices")
async def get_available_indices(current_user: User = Depends(get_current_active_user)):
    """Get available trading indices"""
    try:
        indices = decter_controller._get_available_indices()
        return JSONResponse(content={"indices": indices})
    except Exception as e:
        logger.error(f"❌ Error getting indices: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting indices: {str(e)}")


@decter_router.get("/currencies")
async def get_available_currencies(current_user: User = Depends(get_current_active_user)):
    """Get available currencies"""
    try:
        currencies = decter_controller._get_available_currencies()
        return JSONResponse(content={"currencies": currencies})
    except Exception as e:
        logger.error(f"❌ Error getting currencies: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting currencies: {str(e)}")


@decter_router.get("/logs")
async def get_decter_logs(
    lines: int = 50,
    current_user: User = Depends(get_current_active_user)
):
    """Get recent Decter 001 logs"""
    try:
        logs = decter_controller._get_recent_logs(lines)
        return JSONResponse(content={"logs": logs, "count": len(logs)})
    except Exception as e:
        logger.error(f"❌ Error getting Decter logs: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting logs: {str(e)}")


@decter_router.post("/logs/clear")
async def clear_decter_logs(current_user: User = Depends(get_current_active_user)):
    """Clear Decter 001 JSON log files"""
    try:
        result = decter_controller.clear_json_logs()
        if result["success"]:
            logger.info(f"✅ Decter logs cleared by user: {getattr(current_user, 'email', 'unknown')}")
            return JSONResponse(content=result)
        else:
            raise HTTPException(status_code=400, detail=result["message"])
    except Exception as e:
        logger.error(f"❌ Error clearing Decter logs: {e}")
        raise HTTPException(status_code=500, detail=f"Error clearing logs: {str(e)}")


# Form-based endpoints for web interface
@decter_router.post("/config/form")
async def set_decter_config_form(
    stake: float = Form(...),
    growth_rate: float = Form(...),
    take_profit: float = Form(...),
    index: str = Form(...),
    currency: str = Form(...),
    max_loss_amount: float = Form(...),
    max_win_amount: float = Form(...),
    current_user: User = Depends(get_current_active_user)
):
    """Set Decter 001 config via form submission"""
    try:
        config = DecterConfigRequest(
            stake=stake,
            growth_rate=growth_rate,
            take_profit=take_profit,
            index=index,
            currency=currency,
            max_loss_amount=max_loss_amount,
            max_win_amount=max_win_amount
        )
        return await set_decter_config(config, current_user)
    except Exception as e:
        logger.error(f"❌ Error in form config submission: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid form data: {str(e)}")


@decter_router.post("/command/form")
async def send_decter_command_form(
    command: str = Form(...),
    current_user: User = Depends(get_current_active_user)
):
    """Send command via form submission"""
    try:
        command_req = DecterCommandRequest(command=command)
        return await send_decter_command(command_req, current_user)
    except Exception as e:
        logger.error(f"❌ Error in form command submission: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid command: {str(e)}")


# Telegram configuration endpoints
@decter_router.post("/telegram/config")
async def set_telegram_config(
    config_req: TelegramConfigRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Set Telegram bot configuration"""
    try:
        result = decter_controller.set_telegram_config(
            config_req.bot_token,
            config_req.group_id,
            config_req.topic_id
        )
        if result["success"]:
            logger.info(f"✅ Telegram config updated by user: {getattr(current_user, 'email', 'unknown')}")
            return JSONResponse(content=result)
        else:
            raise HTTPException(status_code=400, detail=result["message"])
    except Exception as e:
        logger.error(f"❌ Error setting Telegram config: {e}")
        raise HTTPException(status_code=500, detail=f"Error setting Telegram config: {str(e)}")


@decter_router.get("/telegram/config")
async def get_telegram_config(current_user: User = Depends(get_current_active_user)):
    """Get current Telegram configuration"""
    try:
        config = decter_controller.get_telegram_config()
        # Mask bot token for security
        if 'telegram_bot_token' in config:
            config['telegram_bot_token'] = '***MASKED***'
        return JSONResponse(content=config)
    except Exception as e:
        logger.error(f"❌ Error getting Telegram config: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting Telegram config: {str(e)}")


@decter_router.post("/telegram/notify")
async def send_telegram_notification(
    notify_req: TransactionLogRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Send Telegram notification with transaction logging"""
    try:
        transaction_data = None
        if notify_req.transaction_type or notify_req.amount or notify_req.result:
            transaction_data = {
                "type": notify_req.transaction_type,
                "amount": notify_req.amount,
                "result": notify_req.result,
                "timestamp": datetime.now().isoformat()
            }
        
        result = decter_controller.send_telegram_notification(
            notify_req.message,
            transaction_data
        )
        
        if result["success"]:
            logger.info(f"✅ Telegram notification sent by user: {getattr(current_user, 'email', 'unknown')}")
            return JSONResponse(content=result)
        else:
            raise HTTPException(status_code=400, detail=result["message"])
    except Exception as e:
        logger.error(f"❌ Error sending Telegram notification: {e}")
        raise HTTPException(status_code=500, detail=f"Error sending notification: {str(e)}")


@decter_router.post("/telegram/daily-summary")
async def send_daily_summary(current_user: User = Depends(get_current_active_user)):
    """Send daily trading summary via Telegram"""
    try:
        result = decter_controller.send_daily_summary()
        
        if result["success"]:
            logger.info(f"✅ Daily summary sent by user: {getattr(current_user, 'email', 'unknown')}")
            return JSONResponse(content=result)
        else:
            raise HTTPException(status_code=400, detail=result["message"])
    except Exception as e:
        logger.error(f"❌ Error sending daily summary: {e}")
        raise HTTPException(status_code=500, detail=f"Error sending daily summary: {str(e)}")


@decter_router.post("/telegram/config/form")
async def set_telegram_config_form(
    bot_token: str = Form(...),
    group_id: str = Form(...),
    topic_id: str = Form(None),
    current_user: User = Depends(get_current_active_user)
):
    """Set Telegram config via form submission"""
    try:
        config_req = TelegramConfigRequest(
            bot_token=bot_token,
            group_id=group_id,
            topic_id=topic_id if topic_id else None
        )
        return await set_telegram_config(config_req, current_user)
    except Exception as e:
        logger.error(f"❌ Error in form Telegram config submission: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid form data: {str(e)}")


# Deriv configuration endpoints
@decter_router.post("/deriv/config")
async def set_deriv_config(
    config_req: DerivConfigRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Set Deriv API configuration"""
    try:
        currency_tokens = {}
        if config_req.xrp_api_token: currency_tokens['XRP'] = config_req.xrp_api_token
        if config_req.btc_api_token: currency_tokens['BTC'] = config_req.btc_api_token
        if config_req.eth_api_token: currency_tokens['ETH'] = config_req.eth_api_token
        if config_req.ltc_api_token: currency_tokens['LTC'] = config_req.ltc_api_token
        if config_req.usdt_api_token: currency_tokens['USDT'] = config_req.usdt_api_token
        if config_req.usd_api_token: currency_tokens['USD'] = config_req.usd_api_token
        
        result = decter_controller.set_deriv_config(
            config_req.deriv_app_id,
            currency_tokens
        )
        if result["success"]:
            logger.info(f"✅ Deriv config updated by user: {getattr(current_user, 'email', 'unknown')}")
            return JSONResponse(content=result)
        else:
            raise HTTPException(status_code=400, detail=result["message"])
    except Exception as e:
        logger.error(f"❌ Error setting Deriv config: {e}")
        raise HTTPException(status_code=500, detail=f"Error setting Deriv config: {str(e)}")


@decter_router.get("/deriv/config")
async def get_deriv_config(current_user: User = Depends(get_current_active_user)):
    """Get current Deriv configuration"""
    try:
        config = decter_controller.get_deriv_config()
        return JSONResponse(content=config)
    except Exception as e:
        logger.error(f"❌ Error getting Deriv config: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting Deriv config: {str(e)}")


@decter_router.post("/deriv/config/form")
async def set_deriv_config_form(
    deriv_app_id: str = Form(...),
    xrp_api_token: str = Form(""),
    btc_api_token: str = Form(""),
    eth_api_token: str = Form(""),
    ltc_api_token: str = Form(""),
    usdt_api_token: str = Form(""),
    usd_api_token: str = Form(""),
    current_user: User = Depends(get_current_active_user)
):
    """Set Deriv config via form submission"""
    try:
        config_req = DerivConfigRequest(
            deriv_app_id=deriv_app_id,
            xrp_api_token=xrp_api_token if xrp_api_token else None,
            btc_api_token=btc_api_token if btc_api_token else None,
            eth_api_token=eth_api_token if eth_api_token else None,
            ltc_api_token=ltc_api_token if ltc_api_token else None,
            usdt_api_token=usdt_api_token if usdt_api_token else None,
            usd_api_token=usd_api_token if usd_api_token else None
        )
        return await set_deriv_config(config_req, current_user)
    except Exception as e:
        logger.error(f"❌ Error in form Deriv config submission: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid form data: {str(e)}")


# Engine configuration and control endpoints
@decter_router.post("/engine/config")
async def set_engine_config(
    config_req: EngineConfigRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Set engine behavior and risk parameters"""
    try:
        config_dict = config_req.dict(exclude_unset=True)
        result = decter_controller.set_engine_config(config_dict)
        
        if result["success"]:
            logger.info(f"✅ Engine config updated by user: {getattr(current_user, 'email', 'unknown')}")
            return JSONResponse(content=result)
        else:
            raise HTTPException(status_code=400, detail=result["message"])
    except Exception as e:
        logger.error(f"❌ Error setting engine config: {e}")
        raise HTTPException(status_code=500, detail=f"Error setting engine config: {str(e)}")


@decter_router.get("/engine/config")
async def get_engine_config(current_user: User = Depends(get_current_active_user)):
    """Get current engine configuration"""
    try:
        config = decter_controller.get_engine_config()
        return JSONResponse(content=config)
    except Exception as e:
        logger.error(f"❌ Error getting engine config: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting engine config: {str(e)}")


@decter_router.get("/engine/diagnostics")
async def get_engine_diagnostics(current_user: User = Depends(get_current_active_user)):
    """Get comprehensive engine diagnostics and state"""
    try:
        diagnostics = decter_controller.get_engine_diagnostics()
        return JSONResponse(content=diagnostics)
    except Exception as e:
        logger.error(f"❌ Error getting engine diagnostics: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting diagnostics: {str(e)}")


@decter_router.post("/currency/switch")
async def switch_currency(
    switch_req: CurrencySwitchRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Switch active trading currency"""
    try:
        result = decter_controller.switch_currency(switch_req.currency)
        
        if result["success"]:
            logger.info(f"✅ Currency switched by user: {getattr(current_user, 'email', 'unknown')} to {switch_req.currency}")
            return JSONResponse(content=result)
        else:
            raise HTTPException(status_code=400, detail=result["message"])
    except Exception as e:
        logger.error(f"❌ Error switching currency: {e}")
        raise HTTPException(status_code=500, detail=f"Error switching currency: {str(e)}")


@decter_router.get("/currencies")
async def get_supported_currencies(current_user: User = Depends(get_current_active_user)):
    """Get list of supported currencies"""
    try:
        engine_config = decter_controller.get_engine_config()
        currencies = engine_config.get("supported_currencies", ["XRP", "BTC", "ETH", "LTC", "USDT", "USD"])
        active_currency = engine_config.get("selected_currency", "XRP")
        
        return JSONResponse(content={
            "supported_currencies": currencies,
            "active_currency": active_currency,
            "total_count": len(currencies)
        })
    except Exception as e:
        logger.error(f"❌ Error getting currencies: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting currencies: {str(e)}")


# Engine control endpoints
@decter_router.post("/engine/continuous/start")
async def start_continuous_engine(current_user: User = Depends(get_current_active_user)):
    """Start the continuous monitoring engine"""
    try:
        # Update engine config to enable continuous engine
        config = decter_controller.get_engine_config()
        config["enable_continuous_engine"] = True
        result = decter_controller.set_engine_config(config)
        
        if result["success"]:
            logger.info(f"✅ Continuous engine started by user: {getattr(current_user, 'email', 'unknown')}")
            return JSONResponse(content={"success": True, "message": "Continuous engine started"})
        else:
            raise HTTPException(status_code=400, detail=result["message"])
    except Exception as e:
        logger.error(f"❌ Error starting continuous engine: {e}")
        raise HTTPException(status_code=500, detail=f"Error starting continuous engine: {str(e)}")


@decter_router.post("/engine/continuous/stop")
async def stop_continuous_engine(current_user: User = Depends(get_current_active_user)):
    """Stop the continuous monitoring engine"""
    try:
        # Update engine config to disable continuous engine
        config = decter_controller.get_engine_config()
        config["enable_continuous_engine"] = False
        result = decter_controller.set_engine_config(config)
        
        if result["success"]:
            logger.info(f"✅ Continuous engine stopped by user: {getattr(current_user, 'email', 'unknown')}")
            return JSONResponse(content={"success": True, "message": "Continuous engine stopped"})
        else:
            raise HTTPException(status_code=400, detail=result["message"])
    except Exception as e:
        logger.error(f"❌ Error stopping continuous engine: {e}")
        raise HTTPException(status_code=500, detail=f"Error stopping continuous engine: {str(e)}")


@decter_router.post("/engine/decision/start")
async def start_decision_engine(current_user: User = Depends(get_current_active_user)):
    """Start the decision/recovery engine"""
    try:
        # Update engine config to enable decision engine
        config = decter_controller.get_engine_config()
        config["enable_decision_engine"] = True
        result = decter_controller.set_engine_config(config)
        
        if result["success"]:
            logger.info(f"✅ Decision engine started by user: {getattr(current_user, 'email', 'unknown')}")
            return JSONResponse(content={"success": True, "message": "Decision engine started"})
        else:
            raise HTTPException(status_code=400, detail=result["message"])
    except Exception as e:
        logger.error(f"❌ Error starting decision engine: {e}")
        raise HTTPException(status_code=500, detail=f"Error starting decision engine: {str(e)}")


@decter_router.post("/engine/decision/stop")
async def stop_decision_engine(current_user: User = Depends(get_current_active_user)):
    """Stop the decision/recovery engine"""
    try:
        # Update engine config to disable decision engine
        config = decter_controller.get_engine_config()
        config["enable_decision_engine"] = False
        result = decter_controller.set_engine_config(config)
        
        if result["success"]:
            logger.info(f"✅ Decision engine stopped by user: {getattr(current_user, 'email', 'unknown')}")
            return JSONResponse(content={"success": True, "message": "Decision engine stopped"})
        else:
            raise HTTPException(status_code=400, detail=result["message"])
    except Exception as e:
        logger.error(f"❌ Error stopping decision engine: {e}")
        raise HTTPException(status_code=500, detail=f"Error stopping decision engine: {str(e)}")


# Trade History and Export endpoints
@decter_router.post("/trades/history")
async def get_trade_history(
    history_req: TradeHistoryRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Get filtered trade history with pagination"""
    try:
        result = decter_controller.get_filtered_trade_history(
            start_date=history_req.start_date,
            end_date=history_req.end_date,
            currency=history_req.currency,
            engine=history_req.engine,
            result=history_req.result,
            asset_pair=history_req.asset_pair,
            limit=history_req.limit,
            offset=history_req.offset
        )
        
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"❌ Error getting trade history: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting trade history: {str(e)}")


@decter_router.get("/trades/summary")
async def get_trade_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    currency: Optional[str] = None,
    engine: Optional[str] = None,
    current_user: User = Depends(get_current_active_user)
):
    """Get trade summary statistics"""
    try:
        result = decter_controller.get_trade_summary_stats(
            start_date=start_date,
            end_date=end_date,
            currency=currency,
            engine=engine
        )
        
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"❌ Error getting trade summary: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting trade summary: {str(e)}")


@decter_router.post("/trades/export")
async def export_trades(
    export_req: ExportRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Export filtered trades to specified format"""
    try:
        result = decter_controller.export_trade_history(
            export_format=export_req.format,
            start_date=export_req.start_date,
            end_date=export_req.end_date,
            currency=export_req.currency,
            engine=export_req.engine
        )
        
        if result["success"]:
            logger.info(f"✅ Trades exported by user: {getattr(current_user, 'email', 'unknown')} - Format: {export_req.format}")
            return JSONResponse(content=result)
        else:
            raise HTTPException(status_code=400, detail=result["message"])
    except Exception as e:
        logger.error(f"❌ Error exporting trades: {e}")
        raise HTTPException(status_code=500, detail=f"Error exporting trades: {str(e)}")


@decter_router.get("/trades/daily-breakdown")
async def get_daily_breakdown(
    days: int = 30,
    current_user: User = Depends(get_current_active_user)
):
    """Get daily trading performance breakdown"""
    try:
        result = decter_controller.get_daily_trading_breakdown(days)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"❌ Error getting daily breakdown: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting daily breakdown: {str(e)}")


def add_decter_routes(app):
    """Add Decter routes to the main FastAPI app"""
    app.include_router(decter_router)
    logger.info("🤖 Decter 001 routes added to TARC Lighthouse")