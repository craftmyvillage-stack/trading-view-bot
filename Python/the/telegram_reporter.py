import os
import asyncio
import logging
import shutil
from datetime import datetime
from telegram import Bot
from the.state_manager import state_engine

logger = logging.getLogger("TelegramReporter")

class TelegramReporter:
    def __init__(self, event_logger=None):
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        self.event_logger = event_logger
        self.is_valid = bool(self.token and self.chat_id)
        
        if not self.is_valid:
            logger.warning("Telegram credentials missing. Reporting disabled.")

    async def send_report(self, excel_path="market_state.xlsx"):
        if not self.is_valid:
            return False

        # Create daily copy
        date_str = datetime.now().strftime("%Y-%m-%d")
        report_name = f"Daily_Report_{date_str}.xlsx"
        try:
            shutil.copy(excel_path, report_name)
        except:
            pass

        # Prepare Summary
        state = state_engine.get_state()
        summary = (
            f"📊 MyAlgoBot Daily Report\n"
            f"Date: {date_str}\n"
            f"Net PnL: ₹{state['daily_loss']['current']:.2f}\n"
            f"Status: {'BREACHED' if state['daily_loss']['breached'] else 'HEALTHY'}\n"
        )

        retries = 3
        for i in range(retries):
            try:
                bot = Bot(token=self.token)
                async with bot:
                    if os.path.exists(report_name):
                        with open(report_name, 'rb') as f:
                            await bot.send_document(
                                chat_id=self.chat_id,
                                document=f,
                                caption=summary
                            )
                    else:
                        await bot.send_message(chat_id=self.chat_id, text=summary)
                logger.info("Telegram report sent successfully.")
                if self.event_logger:
                    self.event_logger.log_system_event("INFO", "TelegramReporter", "Report sent successfully")
                return True
            except Exception as e:
                logger.error(f"Telegram failure (attempt {i+1}): {e}")
                if i == retries - 1 and self.event_logger:
                    self.event_logger.log_system_event("ERROR", "TelegramReporter", f"Failed to send report: {e}")
                await asyncio.sleep(2)
        return False

    def send_report_sync(self):
        """Wrapper for sync calls"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.send_report())
            else:
                loop.run_until_complete(self.send_report())
        except Exception as e:
            logger.error(f"Sync report error: {e}")

    async def send_15min_report(self):
        if not self.is_valid:
            return False

        state = state_engine.get_state()
        wallet = state.get("wallet", {})
        thinking = state.get("bot_thinking", {})
        
        summary = (
            f"🕒 15-Minute Bot Update\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🌍 Market: {thinking.get('current_market', 'NONE')}\n"
            f"📊 Status: {state.get('session', 'UNKNOWN')}\n"
            f"💡 Signal: {thinking.get('signal_type', 'HOLD')}\n"
            f"💰 Balance: ₹{wallet.get('paper_balance', 0):.2f}\n"
            f"📈 UnPnL: ₹{wallet.get('unrealized_pnl', 0):.2f}\n"
            f"🛡️ Risk: {thinking.get('risk_score', 0)}/100\n"
            f"🧠 Learning: {thinking.get('indicator_explanation', 'Normal operations')[:100]}...\n"
        )

        files = [
            "market_state.xlsx",
            "signal_analysis.xlsx",
            "paper_trades.xlsx",
            "risk_and_drawdown.xlsx"
        ]
        
        retries = 3
        for i in range(retries):
            try:
                bot = Bot(token=self.token)
                async with bot:
                    # Send text summary
                    await bot.send_message(chat_id=self.chat_id, text=summary)
                    
                    # Send files
                    for file_path in files:
                        if os.path.exists(file_path):
                            with open(file_path, 'rb') as f:
                                await bot.send_document(chat_id=self.chat_id, document=f)
                
                logger.info("15-minute Telegram report sent.")
                return True
            except Exception as e:
                logger.error(f"15min Telegram failure (attempt {i+1}): {e}")
                await asyncio.sleep(2)
        return False

telegram_reporter = TelegramReporter()
