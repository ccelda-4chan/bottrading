from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import os
import threading
from loguru import logger
from bot import TradingBot
from dotenv import load_dotenv

load_dotenv()

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

app = FastAPI()
bot_instance = None

@app.on_event("startup")
async def startup_event():
    global bot_instance
    logger.add("bot.log", rotation="10 MB")
    logger.info("Initializing Bitget Demo Trading Bot from Web App...")
    
    cfg = load_config()
    
    bot_instance = TradingBot(
        api_key=cfg["API_KEY"],
        api_secret=cfg["API_SECRET"],
        passphrase=cfg["API_PASSPHRASE"],
        symbols=cfg["SYMBOLS"]
    )
    
    # Run bot in a separate thread
    bot_thread = threading.Thread(target=bot_instance.run, kwargs={"interval": cfg["INTERVAL"]}, daemon=True)
    bot_thread.start()
    logger.info("Trading Bot started in background thread.")

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    if not bot_instance:
        return "Bot not initialized."
    
    status = bot_instance.status
    
    html_content = f"""
    <html>
        <head>
            <title>Bitget Trading Bot Dashboard</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f9; }}
                .container {{ max-width: 800px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                h1 {{ color: #333; }}
                .status-item {{ margin-bottom: 10px; padding: 10px; border-bottom: 1px solid #eee; }}
                .label {{ font-weight: bold; color: #555; }}
                .value {{ color: #000; }}
                .active {{ color: green; font-weight: bold; }}
                .inactive {{ color: red; font-weight: bold; }}
            </style>
            <meta http-equiv="refresh" content="30">
        </head>
        <body>
            <div class="container">
                <h1>Bitget Trading Bot Status</h1>
                <div class="status-item">
                    <span class="label">Bot Status:</span> 
                    <span class="{ "active" if status['is_active'] else "inactive" }">
                        { "RUNNING" if status['is_active'] else "STOPPED" }
                    </span>
                </div>
                <div class="status-item">
                    <span class="label">Current Balance:</span> 
                    <span class="value">{status['balance']} USDT</span>
                </div>
                <div class="status-item">
                    <span class="label">Last Tick:</span> 
                    <span class="value">{status['last_tick']}</span>
                </div>
                <h2>Signals & Positions</h2>
                <table border="1" cellpadding="10" style="border-collapse: collapse; width: 100%;">
                    <thead>
                        <tr style="background-color: #eee;">
                            <th>Symbol</th>
                            <th>Signal</th>
                            <th>Position</th>
                        </tr>
                    </thead>
                    <tbody>
    """
    
    for symbol in bot_instance.symbols:
        signal = status['signals'].get(symbol, "N/A")
        pos = status['positions'].get(symbol, "None")
        pos_str = f"{pos.get('holdSide', 'N/A')} ({pos.get('total', 0)})" if isinstance(pos, dict) else "None"
        
        html_content += f"""
                        <tr>
                            <td>{symbol}</td>
                            <td>{signal}</td>
                            <td>{pos_str}</td>
                        </tr>
        """
        
    html_content += """
                    </tbody>
                </table>
                <p><small>Auto-refreshes every 30 seconds.</small></p>
            </div>
        </body>
    </html>
    """
    return html_content

@app.get("/health")
async def health_check():
    return {"status": "healthy", "bot_active": bot_instance.status['is_active'] if bot_instance else False}
