# replit.md - Trading Bot System

## Overview

This is an intraday paper trading bot system designed for simulating trades on Indian indices (NIFTY, BANKNIFTY) and cryptocurrency (BTCUSDT). The system operates entirely in paper trading mode without requiring real broker connections or API credentials.

**Core Purpose:** Simulate trading strategies using TradingView-style market data, execute paper trades, manage risk with stop-losses and time-based exits, and display real-time performance on a web dashboard.

**Key Characteristics:**
- Paper trading only (no real money or live broker integration)
- Simulated market data (no external API keys needed)
- Self-contained system with file-based state persistence
- FastAPI-powered dashboard for monitoring
- SQLite for audit logging
- Excel workbook for detailed trade analytics

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Core Pipeline Architecture

The system follows a continuous loop architecture with four distinct stages:

```
Market Data → Signal Generation → Trade Execution → Risk Management
     ↓              ↓                   ↓                  ↓
  (OHLC)        (BUY/SELL)          (Paper Fill)      (SL/Time Exit)
```

**Main Orchestrator** (`Python/main.py`):
- Runs an infinite loop with 2-second intervals
- Coordinates all engines in sequence
- Handles errors gracefully with automatic recovery

### Module Responsibilities

| File | Purpose |
|------|---------|
| `Python/main.py` | Central orchestrator - runs the trading loop |
| `Python/the/market_data_and_signal.py` | Generates simulated OHLC data and trading signals |
| `Python/the/trade_execution_and_mode.py` | Executes paper trades based on signals |
| `Python/the/trade_management_and_risk.py` | Monitors positions, handles stop-losses and exits |
| `Python/the/state_manager.py` | Single source of truth for all system state |
| `Python/the/event_logger.py` | Audit logging with SQLite persistence |
| `Python/the/excel_manager.py` | Excel workbook management for trade analytics |
| `Python/the/dashboard_api.py` | FastAPI server for web dashboard |
| `Python/index.html` | Simple trading terminal UI |

### State Management Design

**File-Based State** (`bot_state.json`):
- Persists system mode, kill switches, daily loss tracking
- Stores active trades and market data
- Includes "bot_thinking" object for UI transparency
- Resets daily counters automatically

**Design Rationale:** File-based state was chosen over database for simplicity and portability. The state file uses file locking (fcntl) for thread safety.

### Signal Generation Logic

The `MarketSignalEngine` generates simulated price data and produces BUY/SELL/HOLD signals based on:
- Price momentum (difference between open and close)
- Confidence scoring (0-100%)
- Human-readable explanations for each decision

### Risk Management

- **Daily Loss Limit:** ₹150 default, triggers kill switch when breached
- **Hard Stop-Loss:** 1% per trade
- **Mandatory Exit Time:** 14:30 IST
- **Max Active Trades:** 2 concurrent positions
- **Dynamic Risk Scoring:** 0-100 scale based on current P&L and position count

## External Dependencies

### Python Packages
- **FastAPI** - Web framework for dashboard API
- **Uvicorn** - ASGI server for FastAPI
- **openpyxl** - Excel file creation and manipulation
- **pandas** - Data manipulation for market analysis
- **sqlite3** - Built-in database for audit logging

### Data Storage
- **SQLite** (`trading_bot_audit.db`) - Audit logs for signals, trades, and system events
- **JSON** (`bot_state.json`) - Live system state persistence
- **Excel** (`Trading_Analytics.xlsx`) - Detailed trade analytics with multiple sheets

### No External APIs Required
- Market data is simulated internally (TradingView-style mock data)
- No broker integration (paper trading only)
- No authentication tokens needed