import sys
import os
import threading
import time
import logging

# Set base path to the directory containing main.py
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
PYTHON_PATH = BASE_PATH

# Add Python directory to path to allow imports from Python.the
if PYTHON_PATH not in sys.path:
    sys.path.insert(0, PYTHON_PATH)

from the.state_manager import state_engine
from the.market_data_and_signal import MarketSignalEngine
from the.trade_execution_and_mode import ExecutionEngine
from the.trade_management_and_risk import TradeManagementEngine
from the.session_engine import session_manager
from the.event_logger import EventLogger
from the.dashboard_api import start_dashboard_server

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_trading_loop():
    """Main trading bot orchestration loop"""
    event_logger = EventLogger()
    market_engine = MarketSignalEngine()
    execution_engine = ExecutionEngine()
    risk_engine = TradeManagementEngine(event_logger)
    
    # Set initial state
    state_engine.update_thinking({
        "current_state": "BOOTING",
        "trade_decision_reason": "Initializing engines and market scan..."
    })
    
    logger.info("TRADING BOT STARTED")
    
    # First successful scan flag
    first_scan_complete = False
    
    while True:
        try:
            # 1. Update Session and Handle IST transitions
            session_manager.update_session(event_logger)
            state = state_engine.get_state()
            
            # 2. Run Engines Sequentially in the loop
            if state.get("session") == "LIVE_MARKET":
                signals = market_engine.scan_market()
                for signal in signals:
                    execution_engine.execute_trade(signal)
                
                if not first_scan_complete:
                    state_engine.update_thinking({"current_state": "ACTIVE"})
                    first_scan_complete = True
            else:
                # Still allow risk engine to check exits (mandatory time exit)
                # and scan for data updates
                market_engine.scan_market()
            
            risk_engine.check_exits()
            
            # Heartbeat log
            event_logger.log_system_event("INFO", "MainLoop", "Bot heartbeat - system status: " + state_engine.get_state()["bot_thinking"]["current_state"])
            
            time.sleep(2)
        except Exception as e:
            logger.error(f"Loop error: {e}")
            event_logger.log_system_event("ERROR", "MainLoop", f"Critical loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    # Start Trading Bot in a background thread
    trading_thread = threading.Thread(target=run_trading_loop, daemon=True)
    trading_thread.start()
    
    # Start Dashboard Server (Blocks main thread)
    start_dashboard_server()
