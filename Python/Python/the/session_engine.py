import logging
from datetime import datetime
import pytz
from the.state_manager import state_engine
from the.excel_manager import excel_manager

logger = logging.getLogger("SessionEngine")

class MarketSessionEngine:
    def __init__(self):
        self.tz = pytz.timezone('Asia/Kolkata')
        self.market_open = (9, 15)
        self.market_close = (15, 30)
        self.last_log_time = None

    def get_current_session(self):
        now = datetime.now(self.tz)
        current_time = (now.hour, now.minute)
        
        # Check weekend
        if now.weekday() >= 5:
            return "MARKET_CLOSED"
            
        if current_time < (9, 0):
            return "MARKET_CLOSED"
        elif current_time < self.market_open:
            return "PRE_MARKET"
        elif current_time < self.market_close:
            return "LIVE_MARKET"
        elif current_time < (16, 0):
            return "POST_MARKET"
        else:
            return "MARKET_CLOSED"

    def update_session(self, event_logger):
        session = self.get_current_session()
        state = state_engine.get_state()
        old_session = state.get("session")
        
        if session != old_session:
            state["session"] = session
            state_engine._write_state(state)
            msg = f"Market session changed: {old_session} -> {session}"
            logger.info(msg)
            event_logger.log_system_event("INFO", "SessionEngine", msg)
            
            if session == "POST_MARKET":
                self.run_post_market_analysis(event_logger)
            elif session == "PRE_MARKET":
                self.run_pre_market_reset(event_logger)

        # Log session every 15 minutes
        now = datetime.now()
        if not self.last_log_time or (now - self.last_log_time).total_seconds() >= 900:
            event_logger.log_system_event("INFO", "SessionEngine", f"Heartbeat: Current session is {session}")
            self.last_log_time = now

    def run_pre_market_reset(self, event_logger):
        logger.info("Running PRE_MARKET reset...")
        event_logger.log_system_event("INFO", "SessionEngine", "PRE_MARKET reset initiated.")
        # Variable resets handled by state_manager daily reload, but we can add specific ones here

    def run_post_market_analysis(self, event_logger):
        logger.info("Running POST_MARKET analysis...")
        state = state_engine.get_state()
        
        analysis = {
            "Timestamp": datetime.now().isoformat(),
            "Strategy_Mistake": "N/A",
            "Market_Misread_Reason": "N/A",
            "Confidence_Mismatch": "Low",
            "Suggested_Improvement": "Tighten risk on BTCUSDT"
        }
        excel_manager.append_to_file("post_market_learning.xlsx", "Learning", analysis)
        event_logger.log_system_event("INFO", "SessionEngine", "POST_MARKET analysis complete. Logged to Excel.")

session_manager = MarketSessionEngine()
