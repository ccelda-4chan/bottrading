from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from contextlib import asynccontextmanager
import os
import threading
from loguru import logger
from bot import TradingBot
from dotenv import load_dotenv
import time

load_dotenv()

# Symbol Mapping for UI
SYMBOL_MAP = {
    "SBTCSUSDT": "BTCUSDT",
    "SETHSUSDT": "ETHUSDT",
    "SXRPSUSDT": "XRPUSDT"
}

def load_config():
    config = {
        "API_KEY": os.getenv("BITGET_API_KEY", ""),
        "API_SECRET": os.getenv("BITGET_API_SECRET", ""),
        "API_PASSPHRASE": os.getenv("BITGET_API_PASSPHRASE", ""),
        "SYMBOLS": os.getenv("BITGET_SYMBOLS", "SBTCSUSDT,SETHSUSDT,SXRPSUSDT").split(","),
        "INTERVAL": int(os.getenv("BITGET_INTERVAL", "10")),
        "PORT": int(os.getenv("PORT", "8000"))
    }
    return config

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_instance
    try:
        try:
            logger.add("bot.log", rotation="10 MB")
        except Exception as e:
            logger.warning(f"Could not initialize file logging: {e}")

        logger.info("Initializing Bitget Trading Bot from Web App...")
        cfg = load_config()
        
        bot_instance = TradingBot(
            api_key=cfg["API_KEY"],
            api_secret=cfg["API_SECRET"],
            passphrase=cfg["API_PASSPHRASE"],
            symbols=cfg["SYMBOLS"]
        )
        
        bot_thread = threading.Thread(target=bot_instance.run, kwargs={"interval": cfg["INTERVAL"]}, daemon=True)
        bot_thread.start()
        logger.info("Trading Bot started in background thread.")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
    
    yield
    
    if bot_instance:
        logger.info("Shutting down bot...")
        bot_instance.is_running = False

app = FastAPI(lifespan=lifespan)
bot_instance = None

@app.get("/api/status")
async def get_status():
    if not bot_instance:
        return {"error": "Bot not initialized"}
    # Include symbol map for frontend
    data = bot_instance.status.copy()
    data["symbol_map"] = SYMBOL_MAP
    return data

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    if not bot_instance:
        return "Bot not initialized."
    
    status = bot_instance.status
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Bitget Pro Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            .bg-dark {{ background-color: #0b0e11; }}
            .bg-card {{ background-color: #1e2329; }}
            .text-gold {{ color: #f0b90b; }}
            .border-gold {{ border-color: #f0b90b; }}
            .fade-in {{ animation: fadeIn 0.5s ease-in; }}
            @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
        </style>
    </head>
    <body class="bg-dark text-gray-200 font-sans">
        <audio id="snd-order" src="https://assets.mixkit.co/active_storage/sfx/2568/2568-preview.mp3"></audio>

        <nav class="bg-card border-b border-gray-700 p-4">
            <div class="container mx-auto flex justify-between items-center">
                <h1 class="text-2xl font-bold text-gold">Bitget <span class="text-white">Pro Bot</span></h1>
                <div class="flex items-center space-x-6">
                    <div class="flex flex-col items-end">
                        <span class="text-xs text-gray-400 uppercase tracking-wider">Total Balance</span>
                        <span id="top-balance" class="text-xl font-mono text-green-400 font-bold">{status['balance']:.2f} USDT</span>
                    </div>
                    <div id="engine-status" class="px-3 py-1 rounded-full text-xs font-bold { 'bg-green-900 text-green-300' if status['is_active'] else 'bg-red-900 text-red-300' }">
                        { "ENGINE ONLINE" if status['is_active'] else "ENGINE OFFLINE" }
                    </div>
                </div>
            </div>
        </nav>

        <main class="container mx-auto p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div class="lg:col-span-2 space-y-6">
                <div class="bg-card rounded-lg p-6 shadow-lg border border-gray-800">
                    <div class="flex justify-between items-center mb-4">
                        <h2 class="text-xl font-semibold text-gold">Portfolio Tracker</h2>
                        <span id="last-tick" class="text-xs text-gray-500 font-mono">Last Update: {status['last_tick']}</span>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left">
                            <thead class="text-gray-500 text-xs uppercase border-b border-gray-700">
                                <tr>
                                    <th class="pb-3">Asset</th>
                                    <th class="pb-3">Signal</th>
                                    <th class="pb-3">Active Position</th>
                                    <th class="pb-3 text-right">Action</th>
                                </tr>
                            </thead>
                            <tbody id="market-body" class="divide-y divide-gray-800">
    """
    
    for symbol in bot_instance.symbols:
        display_name = SYMBOL_MAP.get(symbol, symbol)
        signal = status['signals'].get(symbol, "WAITING")
        pos = status['positions'].get(symbol, "None")
        signal_color = "text-green-400" if signal == "LONG" else "text-red-400" if signal == "SHORT" else "text-gray-400"
        
        pos_str = "No Position"
        if isinstance(pos, dict):
            side = pos.get('holdSide', 'N/A').upper()
            size = pos.get('total', 0)
            pnl = pos.get('unrealizedPL', '0')
            pnl_color = "text-green-400" if float(pnl) >= 0 else "text-red-400"
            pos_str = f"<span class='font-bold'>{side}</span> {size} (<span class='{pnl_color}'>{pnl}</span>)"
        
        html_content += f"""
                                <tr class="hover:bg-gray-800/50 transition">
                                    <td class="py-4 font-bold">{display_name}</td>
                                    <td class="py-4 {signal_color} font-mono">{signal}</td>
                                    <td class="py-4 text-sm">{pos_str}</td>
                                    <td class="py-4 text-right">
                                        <form action="/manual-order" method="post" class="inline">
                                            <input type="hidden" name="symbol" value="{symbol}">
                                            <input type="hidden" name="side" value="close">
                                            <button type="submit" class="text-xs bg-red-900/30 text-red-400 border border-red-900/50 px-3 py-1 rounded hover:bg-red-900/50 transition">
                                                Close
                                            </button>
                                        </form>
                                    </td>
                                </tr>
        """
        
    html_content += """
                            </tbody>
                        </table>
                    </div>
                </div>

                <div class="bg-card rounded-lg p-6 shadow-lg border border-gray-800">
                    <h2 class="text-xl font-semibold mb-4">Activity Logs</h2>
                    <div id="log-container" class="bg-black rounded p-4 font-mono text-xs h-48 overflow-y-auto space-y-1 text-gray-400">
    """
    for log in reversed(status.get('logs', [])):
        html_content += f"<div>{log}</div>"
    
    html_content += """
                    </div>
                </div>
            </div>

            <div class="space-y-6">
                <div class="bg-card rounded-lg p-6 shadow-lg border border-gray-800">
                    <h2 class="text-xl font-semibold mb-4 text-gold">API Configuration</h2>
                    <form action="/update-settings" method="post" class="space-y-3">
                        <div>
                            <label class="block text-xs text-gray-400 mb-1">API Key</label>
                            <input type="text" name="api_key" value="***" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm text-white">
                        </div>
                        <div>
                            <label class="block text-xs text-gray-400 mb-1">API Secret</label>
                            <input type="password" name="api_secret" value="***" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm text-white">
                        </div>
                        <div>
                            <label class="block text-xs text-gray-400 mb-1">Passphrase</label>
                            <input type="password" name="passphrase" value="***" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm text-white">
                        </div>
                        <button type="submit" class="w-full py-2 bg-gray-700 hover:bg-gray-600 rounded text-xs font-bold transition">Update Credentials</button>
                    </form>
                </div>

                <div class="bg-card rounded-lg p-6 shadow-lg border border-gray-800">
                    <h2 class="text-xl font-semibold mb-4">Trading Mode</h2>
                    <div class="flex items-center justify-between p-4 bg-gray-800 rounded-lg">
                        <div>
                            <span class="block font-bold">Auto-Trade</span>
                            <span class="text-xs text-gray-400">AI executes signals</span>
                        </div>
                        <form action="/toggle-auto" method="post">
    """
    
    btn_color = "bg-green-600 hover:bg-green-700" if not bot_instance.auto_trade else "bg-red-600 hover:bg-red-700"
    btn_text = "Enable" if not bot_instance.auto_trade else "Disable"
    
    html_content += f"""
                            <button type="submit" class="{btn_color} text-white px-4 py-2 rounded-lg font-bold transition">
                                {btn_text}
                            </button>
                        </form>
                    </div>
                    
                    <div class="mt-6">
                        <span class="block text-sm font-semibold mb-3 text-gray-400 uppercase">Quick Strategy Templates</span>
                        <div class="grid grid-cols-3 gap-2">
                            <form action="/apply-template" method="post"><input type="hidden" name="template" value="Scalp"><button class="w-full py-2 bg-gray-700 hover:bg-gray-600 rounded text-xs">Scalp</button></form>
                            <form action="/apply-template" method="post"><input type="hidden" name="template" value="Swing"><button class="w-full py-2 bg-gray-700 hover:bg-gray-600 rounded text-xs">Swing</button></form>
                            <form action="/apply-template" method="post"><input type="hidden" name="template" value="Default"><button class="w-full py-2 bg-gray-700 hover:bg-gray-600 rounded text-xs">Default</button></form>
                        </div>
                    </div>
                </div>

                <div class="bg-card rounded-lg p-6 shadow-lg border border-gray-800">
                    <h2 class="text-xl font-semibold mb-4 text-gold">Manual Order</h2>
                    <form action="/manual-order" method="post" class="space-y-4">
                        <div>
                            <label class="block text-xs text-gray-400 mb-1">Symbol</label>
                            <select name="symbol" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm text-white">
    """
    for sym in bot_instance.symbols:
        display_name = SYMBOL_MAP.get(sym, sym)
        html_content += f"<option value='{sym}'>{display_name}</option>"
    
    html_content += """
                            </select>
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="block text-xs text-gray-400 mb-1">Side</label>
                                <select name="side" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm text-white">
                                    <option value="buy">BUY / LONG</option>
                                    <option value="sell">SELL / SHORT</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-xs text-gray-400 mb-1">Type</label>
                                <select name="order_type" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm text-white">
                                    <option value="market">Market</option>
                                </select>
                            </div>
                        </div>
                        <div>
                            <label class="block text-xs text-gray-400 mb-1">Size (Contracts)</label>
                            <input type="number" name="size" step="0.001" value="0.01" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm text-white">
                        </div>
                        <button type="submit" class="w-full py-3 bg-gold hover:bg-yellow-600 text-black font-bold rounded transition mt-2">
                            Execute Order
                        </button>
                    </form>
                </div>
            </div>
        </main>
        
        <footer class="container mx-auto p-6 text-center text-gray-600 text-xs">
            Bitget Trading Terminal | Production Ready | 2026
        </footer>

        <script>
            let lastEventTime = Date.now() / 1000;
            
            async function updateDashboard() {
                try {
                    const res = await fetch('/api/status');
                    const status = await res.json();
                    const symbolMap = status.symbol_map || {};
                    
                    const balEl = document.getElementById('top-balance');
                    const newBal = parseFloat(status.balance).toFixed(2);
                    if (balEl.innerText !== newBal + ' USDT') {
                        balEl.innerText = newBal + ' USDT';
                        balEl.classList.add('fade-in');
                        setTimeout(() => balEl.classList.remove('fade-in'), 500);
                    }
                    
                    document.getElementById('last-tick').innerText = 'Last Update: ' + status.last_tick;
                    
                    const logContainer = document.getElementById('log-container');
                    const logHtml = status.logs.slice().reverse().map(l => `<div>${l}</div>`).join('');
                    logContainer.innerHTML = logHtml;
                    
                    const engineEl = document.getElementById('engine-status');
                    if (status.is_active) {
                        engineEl.className = 'px-3 py-1 rounded-full text-xs font-bold bg-green-900 text-green-300';
                        engineEl.innerText = 'ENGINE ONLINE';
                    } else {
                        engineEl.className = 'px-3 py-1 rounded-full text-xs font-bold bg-red-900 text-red-300';
                        engineEl.innerText = 'ENGINE OFFLINE';
                    }

                    // Update Market Table
                    const marketBody = document.getElementById('market-body');
                    let marketHtml = '';
                    for (const symbol in status.signals) {
                        const displayName = symbolMap[symbol] || symbol;
                        const signal = status.signals[symbol];
                        const pos = status.positions[symbol];
                        const signalColor = signal === "LONG" ? "text-green-400" : (signal === "SHORT" ? "text-red-400" : "text-gray-400");
                        
                        let posStr = "No Position";
                        if (pos && typeof pos === 'object') {
                            const side = (pos.holdSide || 'N/A').toUpperCase();
                            const pnl = pos.unrealizedPL || '0';
                            const pnlColor = parseFloat(pnl) >= 0 ? "text-green-400" : "text-red-400";
                            posStr = `<span class='font-bold'>${side}</span> ${pos.total} (<span class='${pnlColor}'>${pnl}</span>)`;
                        }

                        marketHtml += `
                            <tr class="hover:bg-gray-800/50 transition">
                                <td class="py-4 font-bold">${displayName}</td>
                                <td class="py-4 ${signalColor} font-mono">${signal}</td>
                                <td class="py-4 text-sm">${posStr}</td>
                                <td class="py-4 text-right">
                                    <form action="/manual-order" method="post" class="inline">
                                        <input type="hidden" name="symbol" value="${symbol}">
                                        <input type="hidden" name="side" value="close">
                                        <button type="submit" class="text-xs bg-red-900/30 text-red-400 border border-red-900/50 px-3 py-1 rounded hover:bg-red-900/50 transition">
                                            Close
                                        </button>
                                    </form>
                                </td>
                            </tr>
                        `;
                    }
                    marketBody.innerHTML = marketHtml;

                    if (status.events && status.events.length > 0) {
                        const latest = status.events[status.events.length - 1];
                        if (latest.ts > lastEventTime) {
                            document.getElementById('snd-order').play().catch(e => console.log("Audio play blocked"));
                            lastEventTime = latest.ts;
                        }
                    }
                    
                } catch (e) {
                    console.error("Failed to fetch status", e);
                }
            }

            setInterval(updateDashboard, 2000);
        </script>
    </body>
    </html>
    """
    return html_content

@app.post("/toggle-auto")
async def toggle_auto():
    if bot_instance:
        bot_instance.auto_trade = not bot_instance.auto_trade
        bot_instance.add_log(f"Auto-trade set to {bot_instance.auto_trade}")
    return RedirectResponse(url="/", status_code=303)

@app.post("/manual-order")
async def manual_order(symbol: str = Form(...), side: str = Form(...), order_type: str = Form("market"), size: float = Form(...)):
    if bot_instance:
        if side == "close":
            pos = bot_instance.status["positions"].get(symbol)
            if isinstance(pos, dict):
                close_side = "buy" if pos['holdSide'] == "short" else "sell"
                bot_instance.manual_order(symbol, close_side, "market", pos['total'])
            else:
                bot_instance.add_log(f"No active position to close for {symbol}")
        else:
            bot_instance.manual_order(symbol, side, order_type, size)
    return RedirectResponse(url="/", status_code=303)

@app.post("/update-settings")
async def update_settings(api_key: str = Form(...), api_secret: str = Form(...), passphrase: str = Form(...)):
    if bot_instance:
        bot_instance.update_settings(api_key, api_secret, passphrase)
    return RedirectResponse(url="/", status_code=303)

@app.post("/apply-template")
async def apply_template(template: str = Form(...)):
    if bot_instance:
        bot_instance.apply_template(template)
    return RedirectResponse(url="/", status_code=303)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "bot_active": bot_instance.status['is_active'] if bot_instance else False}
