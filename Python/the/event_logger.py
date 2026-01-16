"""
FILE: event_logger.py
TYPE: Central Data & Audit System (Thinking Logs)
"""
import os
import sys
import json
import time
import sqlite3
import logging
import threading
import queue
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

from the.excel_manager import excel_manager

# Fallback basic logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [EVENT_LOGGER] - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("system_fallback.log"), logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("EventLogger")

SCHEMA_QUERIES = [
    """CREATE TABLE IF NOT EXISTS signals (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, symbol TEXT, signal_type TEXT, confidence REAL, regime TEXT, reason TEXT, raw_payload TEXT);""",
    """CREATE TABLE IF NOT EXISTS trades (trade_id TEXT PRIMARY KEY, symbol TEXT, direction TEXT, quantity INTEGER, entry_price REAL, exit_price REAL, pnl REAL DEFAULT 0.0, status TEXT, entry_time TEXT, exit_time TEXT, mode TEXT, strategy_ref TEXT);""",
    """CREATE TABLE IF NOT EXISTS system_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, level TEXT, module TEXT, message TEXT, payload TEXT);"""
]

class EventLogger:
    _instance = None 

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventLogger, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.db_path = "trading_bot_audit.db"
        self.log_queue = queue.Queue()
        self.running = True
        self.worker_thread = threading.Thread(target=self._db_worker, daemon=True)
        self.worker_thread.start()
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                for query in SCHEMA_QUERIES:
                    conn.execute(query)
        except Exception as e:
            logger.critical(f"DB Initialization Failed: {e}")

    def _db_worker(self):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()
            while self.running:
                try:
                    task = self.log_queue.get(timeout=1)
                except queue.Empty:
                    continue
                if task is None: break
                query, params = task
                try:
                    cursor.execute(query, params)
                    conn.commit()
                except Exception as e:
                    logger.error(f"DB Write Error: {e}")
                finally:
                    self.log_queue.task_done()
        finally:
            if conn: conn.close()

    def log_signal(self, sig: dict):
        readable_msg = f"The intelligence engine identified a potential {sig['signal_type']} opportunity for {sig['symbol']} at {sig['price']:.2f}. Reasoning: {sig['reason']}."
        self.log_system_event("INFO", "SignalEngine", readable_msg)
        query = "INSERT INTO signals (timestamp, symbol, signal_type, confidence, regime, reason, raw_payload) VALUES (?, ?, ?, ?, ?, ?, ?)"
        params = (datetime.now().isoformat(), sig['symbol'], sig['signal_type'], sig['confidence'], sig['regime'], sig['reason'], json.dumps(sig))
        self.log_queue.put((query, params))

        # Log to signal_analysis.xlsx
        excel_manager.append_to_file("signal_analysis.xlsx", "Signal_Analysis", {
            "Timestamp": datetime.now().isoformat(),
            "Symbol": sig['symbol'],
            "Indicator_Values": f"Conf: {sig['confidence']}",
            "Signal_Strength": str(sig['confidence']),
            "Final_Decision": sig['signal_type'],
            "No_Trade_Reason": sig['reason'] if sig['signal_type'] == "HOLD" else "N/A"
        })

    def log_trade_entry(self, trade: dict):
        readable_msg = f"Successfully committed a {trade['direction']} paper position for {trade['symbol']} at {trade['entry_price']:.2f}. Total quantity allocated: {trade['quantity']} units."
        self.log_system_event("INFO", "ExecutionEngine", readable_msg)
        query = "INSERT INTO trades (trade_id, symbol, direction, quantity, entry_price, status, entry_time, mode, strategy_ref) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        params = (trade['trade_id'], trade['symbol'], trade['direction'], trade['quantity'], trade['entry_price'], "OPEN", trade['timestamp'], trade['mode'], trade['signal_id'])
        self.log_queue.put((query, params))

        # Log to paper_trades.xlsx
        excel_manager.append_to_file("paper_trades.xlsx", "Paper_Trades", {
            "Trade_ID": trade['trade_id'],
            "Entry_Price": trade['entry_price'],
            "Fake_Capital": trade['entry_price'] * trade['quantity'],
            "Leverage": 10, # Hardcoded default for now
            "SL": "1%",
            "TP": "N/A",
            "PnL": 0
        })

    def log_trade_exit(self, trade_id: str, exit_price: float, pnl: float, exit_time: str):
        query = "UPDATE trades SET exit_price = ?, pnl = ?, status = 'CLOSED', exit_time = ? WHERE trade_id = ?"
        params = (exit_price, pnl, exit_time, trade_id)
        self.log_queue.put((query, params))

        # Update paper_trades.xlsx (using append for simplicity as per requirement of transparent logging)
        excel_manager.append_to_file("paper_trades.xlsx", "Paper_Trades", {
            "Trade_ID": trade_id,
            "Exit_Price": exit_price,
            "PnL": pnl,
            "Exit_Reason": "System Trigger"
        })

    def log_system_event(self, level: str, module: str, message: str, payload: dict = None):
        query = "INSERT INTO system_logs (timestamp, level, module, message, payload) VALUES (?, ?, ?, ?, ?)"
        params = (datetime.now().isoformat(), level, module, message, json.dumps(payload) if payload else "{}")
        self.log_queue.put((query, params))

    def get_recent_logs(self, limit=10) -> List[dict]:
        query = "SELECT * FROM system_logs ORDER BY id DESC LIMIT ?"
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def shutdown(self):
        self.running = False
        self.log_queue.put(None)
        self.worker_thread.join(timeout=2)
