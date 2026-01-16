"""
FILE: execution_engine.py
TYPE: Execution (Paper Only + Thinking)
"""
import logging
import time
import math
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, Dict
from the.state_manager import state_engine

logger = logging.getLogger("ExecutionEngine")

@dataclass
class TradeObject:
    trade_id: str
    symbol: str
    direction: str
    quantity: int
    entry_price: float
    order_type: str
    timestamp: str
    mode: str
    status: str
    signal_id: str

    def to_dict(self):
        return asdict(self)

class ExecutionEngine:
    def __init__(self):
        self.max_risk_per_trade = 1000.0
        self.min_confidence = 0.70

    def execute_trade(self, signal: Dict) -> Optional[TradeObject]:
        symbol = signal['symbol']
        direction = signal['signal_type']
        
        state = state_engine.get_state()
        session = state.get("session", "MARKET_CLOSED")
        
        if session != "LIVE_MARKET":
            rej_reason = f"Execution blocked: Cannot trade in {session} session."
            state_engine.update_thinking({
                "rejection_reason": rej_reason,
                "log_msg": f"Trade rejected: {rej_reason}"
            })
            return None

        wallet = state.get("wallet", {})
        
        state_engine.update_thinking({"current_state": "TRADING"})

        if not state_engine.can_trade_new():
            rej_reason = "Trading is blocked due to risk limits or kill switch."
            state_engine.update_thinking({
                "rejection_reason": rej_reason,
                "log_msg": f"Trade rejected: {rej_reason}"
            })
            return None

        # Check for sufficient free balance
        ltp = signal['price']
        leverage = wallet.get("leverage", 1)
        
        # Quantity based on max risk or capital available
        # Risking 1000 INR per trade, but limited by free balance * leverage
        max_position_value = min(self.max_risk_per_trade * leverage, wallet.get("free_balance", 0) * leverage)
        
        qty = math.floor(max_position_value / ltp)
        if qty < 1:
            rej_reason = f"Insufficient free balance to open trade for {symbol}."
            state_engine.update_thinking({
                "rejection_reason": rej_reason,
                "log_msg": f"Trade rejected: {rej_reason}"
            })
            return None

        required_margin = (qty * ltp) / leverage
        if required_margin > wallet.get("free_balance", 0):
            rej_reason = f"Margin required ({required_margin:.2f}) exceeds free balance."
            state_engine.update_thinking({
                "rejection_reason": rej_reason,
                "log_msg": f"Trade rejected: {rej_reason}"
            })
            return None

        trade = TradeObject(
            trade_id=f"TRD_{int(time.time())}_{symbol}",
            symbol=symbol,
            direction=direction,
            quantity=qty,
            entry_price=ltp,
            order_type="MARKET",
            timestamp=datetime.now().isoformat(),
            mode=state["system_mode"],
            status="OPEN",
            signal_id=signal.get('reason', 'algo')
        )
        
        # Update wallet margin
        new_wallet = wallet.copy()
        new_wallet["used_margin"] += required_margin
        new_wallet["free_balance"] -= required_margin
        
        state_engine.register_trade(trade.trade_id, trade.to_dict())
        
        # Update state with new wallet
        current_state = state_engine.get_state()
        current_state["wallet"] = new_wallet
        state_engine._write_state(current_state)
        
        # Log to EventLogger (which now logs to Excel)
        from the.event_logger import EventLogger
        EventLogger().log_trade_entry(trade.to_dict())

        state_engine.update_thinking({
            "trade_decision": f"Executing {direction} trade for {symbol} at {ltp:.2f} as momentum looks strong.",
            "rejection_reason": "None",
            "log_msg": f"OPENED {direction} {symbol} @ {ltp:.2f}"
        })
        logger.info(f"[PAPER] Trade Executed: {trade.trade_id} @ {ltp}")
        return trade
