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
        "SYMBOLS": os.getenv("BITGET_SYMBOLS", "BTCUSDT,ETHUSDT,XRPUSDT").split(","),
        "PRODUCT_TYPE": os.getenv("BITGET_PRODUCT_TYPE", "usdt-futures"),
        "INTERVAL": int(os.getenv("BITGET_INTERVAL", "10")),
        "PORT": int(os.getenv("PORT", "8000")),
        "NEWS_API_KEY": os.getenv("NEWS_API_KEY", "")
    }
    return config

if __name__ == "__main__":
    logger.info("Initializing Pro Trading Platform with Web UI...")
    
    cfg = load_config()
    
    # Expanded list of symbols for Alts/Shitcoins/New Coins
    default_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "PEPEUSDT", "SHIBUSDT", "LINKUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT", "UNIUSDT", "LTCUSDT", "BCHUSDT", "ARBUSDT", "OPUSDT", "SUIUSDT", "SEIUSDT"]
    symbols = os.getenv("BITGET_SYMBOLS")
    if symbols:
        symbols = symbols.split(",")
    else:
        symbols = default_symbols
    
    try:
        logger.add("bot.log", rotation="10 MB")
    except Exception as e:
        logger.warning(f"Could not initialize file logging: {e}")

    bot = TradingBot(
        symbols=symbols,
        product_type=cfg["PRODUCT_TYPE"],
        news_api_key=cfg["NEWS_API_KEY"]
    )
    
    # Register bot instance with web app
    web_app.bot_instance = bot
    
    # Run bot in a separate thread
    bot_thread = threading.Thread(target=bot.run, kwargs={"interval": cfg["INTERVAL"]}, daemon=True)
    bot_thread.start()
    
    # Run Web Server
    logger.info(f"Starting Web UI on port {cfg['PORT']}...")
    uvicorn.run(web_app.app, host="0.0.0.0", port=cfg["PORT"])
