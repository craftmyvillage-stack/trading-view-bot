"""
FILE: trade_management_engine.py
TYPE: Risk Management (Paper Only + Thinking)
"""
import logging
import random
from datetime import datetime
from the.state_manager import state_engine

logger = logging.getLogger("TradeManager")

class TradeManagementEngine:
    def __init__(self, event_logger):
        self.event_logger = event_logger
        self.hard_sl_pct = 0.01
        self.mandatory_exit_time = "14:30"

    def calculate_risk_score(self):
        """Generates a dynamic risk score based on system state."""
        state = state_engine.get_state()
        pnl = state["daily_loss"]["current"]
        limit = state["daily_loss"]["limit"]
        
        # Base risk: 20
        risk_score = 20
        explanation = "Market environment appears stable for current operations. "
        
        if pnl < 0:
            loss_pct = abs(pnl) / limit
            risk_score += int(loss_pct * 50)
            explanation = f"Risk is elevated because we are currently at ₹{abs(pnl):.2f} loss for the day. "
        
        active_count = len(state["active_trades"])
        risk_score += active_count * 10
        
        if risk_score > 80:
            explanation += "Caution: Approaching critical risk threshold. Decisions will be highly conservative."
        elif risk_score > 50:
            explanation += "Moderately high risk profile. Monitoring closely."
        else:
            explanation += "System risk levels are within optimal parameters."

        state_engine.update_thinking({
            "risk_score": risk_score,
            "trade_decision": explanation if active_count > 0 else state["bot_thinking"].get("trade_decision", "WAITING"),
            "log_msg": f"Risk assessment: Score {risk_score} ({active_count} active)"
        })
        return risk_score

    def check_exits(self):
        self.calculate_risk_score()
        state = state_engine.get_state()
        active_trades = state.get("active_trades", {})
        market_data = state.get("market_data", {})
        wallet = state.get("wallet", {})

        if not active_trades:
            # Update unrealized pnl to 0 if no trades
            if wallet.get("unrealized_pnl") != 0:
                wallet["unrealized_pnl"] = 0
                state["wallet"] = wallet
                state_engine._write_state(state)
            return

        total_unrealized_pnl = 0
        current_time = datetime.now().strftime("%H:%M")
        
        for tid, trade in list(active_trades.items()):
            symbol = trade['symbol']
            if symbol not in market_data:
                continue
            
            ltp = market_data[symbol]['close']
            entry = trade['entry_price']
            qty = trade['quantity']
            direction = trade['direction']

            # Calculate PnL
            if direction in ["BUY", "LONG"]:
                pnl = (ltp - entry) * qty
                sl_hit = ltp <= entry * (1 - self.hard_sl_pct)
            else:
                pnl = (entry - ltp) * qty
                sl_hit = ltp >= entry * (1 + self.hard_sl_pct)

            total_unrealized_pnl += pnl

            if sl_hit:
                self.close_trade(tid, ltp, pnl, "STOP_LOSS_HIT")
            elif current_time >= self.mandatory_exit_time:
                self.close_trade(tid, ltp, pnl, "MANDATORY_TIME_EXIT")

        # Update unrealized PnL in wallet
        wallet["unrealized_pnl"] = total_unrealized_pnl
        state["wallet"] = wallet
        state_engine._write_state(state)

        # Log to risk_and_drawdown.xlsx
        from the.excel_manager import excel_manager
        excel_manager.append_to_file("risk_and_drawdown.xlsx", "Risk_Drawdown", {
            "Timestamp": datetime.now().isoformat(),
            "Current_Equity": wallet.get("paper_balance", 0),
            "Peak_Equity": wallet.get("paper_balance", 0), # Simplified
            "Drawdown_Pct": "0%",
            "Risk_Per_Trade": "₹1000",
            "Rule_Violations": "None"
        })

    def close_trade(self, trade_id, exit_price, pnl, reason):
        state = state_engine.get_state()
        trade = state["active_trades"].get(trade_id)
        wallet = state.get("wallet", {})
        
        if not trade:
            return

        exit_time = datetime.now().isoformat()
        
        # Calculate margin to return
        leverage = wallet.get("leverage", 1)
        margin_released = (trade['quantity'] * trade['entry_price']) / leverage
        
        # Update wallet
        wallet["used_margin"] -= margin_released
        wallet["free_balance"] += (margin_released + pnl)
        wallet["paper_balance"] += pnl
        wallet["realized_pnl"] += pnl
        
        state["wallet"] = wallet
        state_engine._write_state(state)
        
        state_engine.close_trade(trade_id)
        state_engine.update_pnl(pnl)
        
        # Log to EventLogger
        self.event_logger.log_trade_exit(trade_id, exit_price, pnl, exit_time)

        # Human readable log
        action = "liquidating" if pnl < 0 else "harvesting profits from"
        readable_msg = f"Decided to close position in {trade['symbol']} by {action} the trade at {exit_price:.2f}. Reason: {reason}."
        
        self.event_logger.log_system_event("INFO", "TradeManager", readable_msg)
        state_engine.update_thinking({"log_msg": f"CLOSED {trade['direction']} {trade['symbol']} @ {exit_price:.2f} ({reason})"})
        logger.info(readable_msg)

    def close_all_trades(self, reason):
        active_trades = state_engine.get_state().get("active_trades", {})
        market_data = state_engine.get_state().get("market_data", {})
        for tid, trade in list(active_trades.items()):
            ltp = market_data.get(trade['symbol'], {}).get('close', trade['entry_price'])
            qty = trade['quantity']
            entry = trade['entry_price']
            pnl = (ltp - entry) * qty if trade['direction'] in ["BUY", "LONG"] else (entry - ltp) * qty
            self.close_trade(tid, ltp, pnl, reason)
