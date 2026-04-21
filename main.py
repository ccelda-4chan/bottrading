import os
import threading
import uvicorn
from loguru import logger
from bot import TradingBot
import web_app
from dotenv import load_dotenv

load_dotenv() # Load from .env if present

def load_config():
    config = {
        "API_KEY": os.getenv("BITGET_API_KEY", "your_api_key"),
        "API_SECRET": os.getenv("BITGET_API_SECRET", "your_api_secret"),
        "API_PASSPHRASE": os.getenv("BITGET_API_PASSPHRASE", "your_passphrase"),
        "SYMBOLS": os.getenv("BITGET_SYMBOLS", "SBTCSUSDT,SETHSUSDT,SXRPSUSDT").split(","),
        "INTERVAL": int(os.getenv("BITGET_INTERVAL", "60")),
        "PORT": int(os.getenv("PORT", "8000"))
    }
    return config

if __name__ == "__main__":
    logger.add("bot.log", rotation="10 MB")
    logger.info("Initializing Bitget Demo Trading Bot with Web UI...")
    
    cfg = load_config()
    
    bot = TradingBot(
        api_key=cfg["bg_0890dd661ffd67da87e32a8e07c42f0a"],
        api_secret=cfg["bg_0890dd661ffd67da87e32a8e07c42f0a"],
        passphrase=cfg["127642371"],
        symbols=cfg["SYMBOLS"]
    )
    
    # Register bot instance with web app
    web_app.bot_instance = bot
    
    # Run bot in a separate thread
    bot_thread = threading.Thread(target=bot.run, kwargs={"interval": cfg["INTERVAL"]}, daemon=True)
    bot_thread.start()
    
    # Run Web Server
    logger.info(f"Starting Web UI on port {cfg['PORT']}...")
    uvicorn.run(web_app.app, host="0.0.0.0", port=cfg["PORT"])
