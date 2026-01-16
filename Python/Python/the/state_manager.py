"""
FILE: state_manager.py
TYPE: Central Authority (Thinking Layer)
"""
import os
import json
import logging
import fcntl
from datetime import date, datetime

logger = logging.getLogger("StateManager")

class StateManager:
    STATE_FILE = "bot_state.json"
    
    DEFAULT_STATE = {
        "system_mode": "PAPER_TRADING_REAL_DATA",
        "session": "MARKET_CLOSED",
        "wallet": {
            "paper_balance": 10000.0,
            "used_margin": 0.0,
            "free_balance": 10000.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "leverage": 10
        },
        "kill_switch": {"stop_new_trades": False, "full_system_freeze": False, "symbol_block": []},
        "daily_loss": {"limit": 150.0, "current": 0.0, "breached": False},
        "active_trades": {},
        "market_data": {},
        "date": str(date.today()),
        "bot_thinking": {
            "current_state": "WAITING",
            "current_market": "NONE",
            "timeframe": "1m",
            "data_source": "TRADINGVIEW_MOCK",
            "indicators_used": [],
            "indicator_explanation": "System initializing...",
            "signal_type": "NO_TRADE",
            "signal_confidence": 0,
            "trade_decision_reason": "Waiting for market scan...",
            "trade_rejection_reason": "None",
            "risk_score": 0,
            "market_mode": "UNKNOWN"
        }
    }

    def __init__(self):
        if not os.path.exists(self.STATE_FILE):
            self._write_state(self.DEFAULT_STATE)
        self.reload_state()

    def reload_state(self):
        state = self._read_state()
        if state.get("date") != str(date.today()):
            new_state = self.DEFAULT_STATE.copy()
            new_state["date"] = str(date.today())
            self._write_state(new_state)

    def _read_state(self):
        try:
            with open(self.STATE_FILE, 'r') as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                data = json.load(f)
                fcntl.flock(f, fcntl.LOCK_UN)
                return data
        except Exception:
            return self.DEFAULT_STATE

    def _write_state(self, data):
        try:
            with open(self.STATE_FILE, 'w') as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                json.dump(data, f, indent=4)
                fcntl.flock(f, fcntl.LOCK_UN)
        except Exception as e:
            logger.error(f"Write failure: {e}")

    def get_state(self):
        return self._read_state()

    def update_thinking(self, updates: dict):
        state = self.get_state()
        
        # Ensure we don't lose existing rich data
        current_thinking = state.get("bot_thinking", {
            "current_state": "INITIALIZING",
            "current_market": "SCANNING...",
            "market_mode": "UNKNOWN",
            "signal_type": "HOLD",
            "signal_confidence": 0,
            "indicator_logic": "N/A",
            "trade_decision": "WAITING",
            "rejection_reason": "NONE",
            "risk_score": 20,
            "narrative_logs": []
        })
        
        current_thinking.update(updates)
        
        # Handle narrative logs as a rolling buffer
        if "log_msg" in updates:
            logs = current_thinking.get("narrative_logs", [])
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {updates['log_msg']}")
            current_thinking["narrative_logs"] = logs[-15:] # Keep last 15
            
        state["bot_thinking"] = current_thinking
        self._write_state(state)

    def can_trade_new(self):
        state = self._read_state()
        if state["system_mode"] == "FREEZE": return False
        if state["kill_switch"]["stop_new_trades"]: return False
        if state["daily_loss"]["breached"]: return False
        return True

    def register_market_data(self, symbol, data):
        state = self._read_state()
        state["market_data"][symbol] = data
        self._write_state(state)

    def register_trade(self, trade_id, trade_data):
        state = self._read_state()
        state["active_trades"][trade_id] = trade_data
        self._write_state(state)

    def close_trade(self, trade_id):
        state = self._read_state()
        if trade_id in state["active_trades"]:
            del state["active_trades"][trade_id]
            self._write_state(state)

    def update_pnl(self, pnl):
        state = self._read_state()
        state["daily_loss"]["current"] += pnl
        if state["daily_loss"]["current"] <= -state["daily_loss"]["limit"]:
            state["daily_loss"]["breached"] = True
            state["kill_switch"]["stop_new_trades"] = True
        self._write_state(state)

state_engine = StateManager()
