"""
FILE: market_data_and_signal.py
RESPONSIBILITY: Intelligence Layer (Simulated TradingView Data + Thinking)
"""
import logging
import random
import time
import pandas as pd
from datetime import datetime, timedelta
from the.state_manager import state_engine

logger = logging.getLogger("SignalEngine")

class MarketSignalEngine:
    def __init__(self, config=None):
        self.config = config
        self.symbols = ["NIFTY", "BANKNIFTY", "BTCUSDT"]
        self.last_prices = {s: random.uniform(20000, 25000) if "NIFTY" in s else random.uniform(40000, 60000) for s in self.symbols}

    def fetch_simulated_ohlc(self, symbol):
        """Simulates TradingView-style candle data with gap/delay handling."""
        # Simulated delay or skip
        if random.random() < 0.02: # 2% chance of "data delay/gap"
            logger.warning(f"Market gap/delay detected for {symbol}. Skipping candle.")
            return None

        base_price = self.last_prices[symbol]
        change = random.uniform(-0.002, 0.002) * base_price
        new_price = base_price + change
        self.last_prices[symbol] = new_price
        
        return {
            "symbol": symbol,
            "open": base_price,
            "high": max(base_price, new_price) + random.uniform(0, 5),
            "low": min(base_price, new_price) - random.uniform(0, 5),
            "close": new_price,
            "volume": random.randint(1000, 5000),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def generate_signal(self, data):
        """Generates BUY/SELL/HOLD signals with explanations."""
        diff = data['close'] - data['open']
        momentum = abs(diff) / (data['open'] * 0.001)
        confidence = min(momentum, 1.0)
        
        signal_type = "HOLD"
        reason = "Market is currently moving sideways with no clear direction."
        explanation = f"Price moved from {data['open']:.2f} to {data['close']:.2f} ({diff:.2f} pts). "
        
        if diff > 0.5 and confidence > 0.6:
            signal_type = "BUY"
            reason = f"Bullish momentum detected. Price is climbing with a confidence of {confidence*100:.0f}%."
            explanation += "The recent candle closed significantly higher than its open, suggesting strong buying interest."
        elif diff < -0.5 and confidence > 0.6:
            signal_type = "SELL"
            reason = f"Bearish momentum detected. Price is falling with a confidence of {confidence*100:.0f}%."
            explanation += "The recent candle closed significantly lower than its open, indicating aggressive selling pressure."
        else:
            explanation += "The price movement is too small to constitute a reliable signal."

        market_mode = "TRENDING" if confidence > 0.7 else "CHOPPY"
        if momentum < 0.2:
            market_mode = "SIDEWAYS"

        state_engine.update_thinking({
            "current_state": "ANALYZING",
            "current_market": data['symbol'],
            "indicator_logic": explanation,
            "signal_type": signal_type,
            "signal_confidence": int(confidence * 100),
            "trade_decision": reason,
            "market_mode": market_mode,
            "indicators_used": ["Price Momentum", "Candle Analysis"],
            "log_msg": f"Analyzed {data['symbol']}: {signal_type} at {data['close']:.2f} ({market_mode})"
        })

        return {
            "symbol": data['symbol'],
            "signal_type": signal_type,
            "confidence": round(confidence, 2),
            "regime": market_mode,
            "reason": reason,
            "price": data['close'],
            "timestamp": data['timestamp'],
            "expiry": (datetime.now() + timedelta(minutes=5)).isoformat()
        }

    def scan_market(self):
        """Main logic loop: returns a list of actionable signals."""
        state_engine.update_thinking({"current_state": "SCANNING"})
        
        session = state_engine.get_state().get("session", "MARKET_CLOSED")
        if session != "LIVE_MARKET":
            state_engine.update_thinking({
                "rejection_reason": f"Trading blocked: Current session is {session}",
                "log_msg": f"Scan skipped: {session}"
            })
            return []

        if not state_engine.can_trade_new():
            state_engine.update_thinking({
                "rejection_reason": "Trading restricted by state manager (Daily limit or Kill switch)",
                "log_msg": "Scan skipped: Risk limit reached"
            })
            return []

        actionable_signals = []
        for symbol in self.symbols:
            data = self.fetch_simulated_ohlc(symbol)
            if not data:
                continue
            state_engine.register_market_data(symbol, data)
            
            sig = self.generate_signal(data)
            
            # Log to market_state.xlsx
            from the.excel_manager import excel_manager
            excel_manager.append_to_file("market_state.xlsx", "Market_State", {
                "Timestamp": datetime.now().isoformat(),
                "Market_Status": state_engine.get_state().get("session", "UNKNOWN"),
                "Symbol": symbol,
                "Candle_Freshness": "LIVE",
                "Regime": sig.get('regime', 'UNKNOWN')
            })

            # Log signal to EventLogger
            from the.event_logger import EventLogger
            sig_copy = sig.copy()
            sig_copy['trade_id'] = f"SIG_{int(time.time())}_{symbol}"
            EventLogger().log_signal(sig_copy)

            if sig['signal_type'] != "HOLD":
                actionable_signals.append(sig)
                
        if not actionable_signals:
            state_engine.update_thinking({
                "current_state": "WAITING", 
                "trade_decision": "No actionable signals found in current scan.",
                "log_msg": "Scan complete: No signals"
            })
        
        return actionable_signals
