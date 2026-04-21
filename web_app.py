from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import os

app = FastAPI()
bot_instance = None

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
