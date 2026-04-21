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
        "SYMBOLS": os.getenv("BITGET_SYMBOLS", "BTCUSDT,ETHUSDT,XRPUSDT").split(","),
        "PRODUCT_TYPE": os.getenv("BITGET_PRODUCT_TYPE", "usdt-futures"),
        "INTERVAL": int(os.getenv("BITGET_INTERVAL", "10")),
        "PORT": int(os.getenv("PORT", "8000")),
        "NEWS_API_KEY": os.getenv("NEWS_API_KEY", "")
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
            symbols=cfg["SYMBOLS"],
            product_type=cfg["PRODUCT_TYPE"],
            news_api_key=cfg["NEWS_API_KEY"]
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
    
    # Building symbols options
    symbols_options = ""
    for sym in bot_instance.symbols:
        display_name = SYMBOL_MAP.get(sym, sym)
        symbols_options += f"<option value='{sym}'>{display_name}</option>"

    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SHADOW V2 | Trading Terminal</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            .bg-dark { background-color: #0b0e11; }
            .bg-card { background-color: #1e2329; }
            .bg-accent { background-color: #161a1e; }
            .text-gold { color: #f0b90b; }
            .text-green-bitget { color: #0ecb81; }
            .text-red-bitget { color: #f6465d; }
            ::-webkit-scrollbar { width: 4px; }
            ::-webkit-scrollbar-track { background: #0b0e11; }
            ::-webkit-scrollbar-thumb { background: #333; }
        </style>
    </head>
    <body class="bg-dark text-gray-200 font-sans overflow-hidden">
        <audio id="snd-order" src="https://assets.mixkit.co/active_storage/sfx/2568/2568-preview.mp3"></audio>

        <nav class="bg-card border-b border-gray-800 px-6 py-2">
            <div class="flex justify-between items-center text-[10px] text-gray-400 uppercase tracking-tighter mb-1">
                <div class="flex space-x-4"><span>BTC BLOCK ---</span><span>MEMPOOL ---</span><span>FEE --- sat/vb</span><span>F&G 23</span></div>
                <div class="flex space-x-4"><span class="text-gold font-bold">MODE DEMO</span><span class="text-green-bitget font-bold">BITGET ON</span></div>
            </div>
            <div class="flex justify-between items-end">
                <div class="flex items-center space-x-2">
                    <h1 class="text-xl font-black italic tracking-tighter text-white">SHADOW <span class="text-[10px] align-top text-gray-500 font-normal not-italic">V2</span></h1>
                    <div class="text-2xl font-bold text-green-bitget ml-8"><span class="text-xs font-normal text-gray-500 align-middle mr-2 uppercase">Today's P&L</span><span id="stat-today-pnl">+$0.00</span></div>
                </div>
                <div class="flex space-x-12 pb-1 text-gray-200">
                    <div class="text-center"><div class="text-[9px] text-gray-500 uppercase">Uptime Check</div><div id="stat-uptime" class="text-xs font-mono text-blue-400">Restoring...</div></div>
                    <div class="text-center"><div class="text-[9px] text-gray-500 uppercase">Balance</div><div id="stat-balance" class="text-sm font-bold font-mono">$0.00</div></div>
                    <div class="text-center"><div class="text-[9px] text-gray-500 uppercase">Unrealized</div><div id="stat-unrealized" class="text-sm font-bold font-mono text-green-bitget">+$0.00</div></div>
                    <div class="text-center"><div class="text-[9px] text-gray-500 uppercase">Trades</div><div id="stat-trades" class="text-sm font-bold font-mono">0</div></div>
                    <div class="text-center"><div class="text-[9px] text-gray-500 uppercase">Win Rate</div><div id="stat-winrate" class="text-sm font-bold font-mono">0%</div></div>
                    <div class="text-center"><div class="text-[9px] text-gray-500 uppercase">Drawdown</div><div id="stat-drawdown" class="text-sm font-bold font-mono">0.0%</div></div>
                    <div class="text-center"><div class="text-[9px] text-gray-500 uppercase">Open</div><div id="stat-open" class="text-sm font-bold font-mono">0</div></div>
                    <div class="flex items-center space-x-3 ml-4"><button class="bg-red-600/20 text-red-500 border border-red-600/50 px-3 py-0.5 rounded text-[10px] font-bold hover:bg-red-600/40 transition">HALT</button><div class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div></div>
                </div>
            </div>
        </nav>

        <main class="flex h-[calc(100vh-80px)] overflow-hidden">
            <aside class="w-64 bg-accent border-r border-gray-800 flex flex-col">
                <div class="p-3 border-b border-gray-800 flex justify-between items-center"><span class="text-[10px] font-bold text-gray-500 uppercase">Live Feed</span><span class="text-[10px] text-gray-600 font-mono">50</span></div>
                <div id="live-feed" class="flex-1 overflow-y-auto p-2 space-y-2 text-[9px] font-mono"></div>
            </aside>

            <section class="flex-1 overflow-y-auto bg-dark p-4 space-y-4">
                <div class="flex justify-between items-center mb-1">
                    <div class="flex items-center space-x-4">
                        <div class="bg-accent px-2 py-1 rounded border border-gray-700 text-xs font-bold">BTC/USDT <span class="text-[9px] font-normal text-gray-500 ml-1">Perpetual</span></div>
                        <div class="text-lg font-bold text-white">$74,677 <span class="text-[10px] text-green-bitget font-normal">+0.73%</span></div>
                    </div>
                    <div class="flex bg-accent rounded p-0.5 border border-gray-800"><button class="px-3 py-1 text-[10px] bg-blue-600 rounded shadow text-white">Price</button><button class="px-3 py-1 text-[10px] text-gray-500">Equity</button></div>
                </div>

                <div class="bg-card rounded border border-gray-800 overflow-hidden" style="height: 450px;">
                    <div id="tradingview_widget" class="h-full w-full"></div>
                    <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
                    <script type="text/javascript">
                    new TradingView.widget({"autosize": true, "symbol": "BITGET:BTCUSDT.P", "interval": "1H", "timezone": "Etc/UTC", "theme": "dark", "style": "1", "locale": "en", "toolbar_bg": "#f1f3f6", "enable_publishing": false, "hide_top_toolbar": true, "save_image": false, "container_id": "tradingview_widget"});
                    </script>
                </div>

                <div class="space-y-2">
                    <div class="flex justify-between items-center px-1"><h2 class="text-xs font-bold text-gray-400 uppercase flex items-center">Trade Signals <span id="signal-count" class="ml-2 bg-blue-600 text-white text-[9px] px-1.5 rounded-full">0</span></h2>
                        <div class="flex items-center space-x-2"><span class="text-[9px] text-gray-500 italic">Gen 2 Exec 0 Rej 0</span>
                            <div class="flex items-center"><span class="text-[9px] mr-2 text-gray-400">Auto-Execute</span>
                                <form action="/toggle-auto" method="post"><button type="submit" id="auto-trade-toggle" class="w-8 h-4 rounded-full bg-gray-700 relative transition"><div id="auto-trade-dot" class="absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white transition"></div></button></form>
                            </div>
                        </div>
                    </div>
                    <div id="trade-signals-list" class="space-y-2"></div>
                </div>

                <div class="bg-card rounded border border-gray-800 overflow-hidden">
                    <div class="bg-accent px-4 py-2 border-b border-gray-800 flex justify-between items-center"><span class="text-[10px] font-bold text-gray-400 uppercase">Open Positions</span><button class="text-[9px] bg-red-900/20 text-red-500 border border-red-900/50 px-2 py-0.5 rounded">Close All</button></div>
                    <table class="w-full text-left text-[11px]"><thead class="bg-accent/50 text-gray-500 uppercase text-[9px]"><tr><th class="px-4 py-2">Symbol</th><th class="px-4 py-2">Side</th><th class="px-4 py-2">Size</th><th class="px-4 py-2">Entry</th><th class="px-4 py-2">Mark</th><th class="px-4 py-2">PNL</th><th class="px-4 py-2 text-right">Action</th></tr></thead>
                    <tbody id="positions-body" class="divide-y divide-gray-800 text-gray-300"></tbody></table>
                </div>
            </section>

            <aside class="w-72 bg-accent border-l border-gray-800 flex flex-col overflow-y-auto">
                <div class="p-4 border-b border-gray-800">
                    <div class="flex justify-between items-center mb-4"><span class="text-xs font-bold text-white uppercase">Auto Trading</span><div id="side-auto-status" class="w-3 h-3 rounded-full bg-red-500"></div></div>
                    <div id="auto-status-text" class="text-[10px] font-bold text-red-500 mb-4">● STOPPED</div>
                    <div class="space-y-3"><div class="text-[9px] font-bold text-gray-500 uppercase tracking-widest border-b border-gray-800 pb-1">Account</div>
                        <div class="flex justify-between text-[10px]"><span class="text-gray-400">Bitget</span><span id="side-connection" class="text-red-bitget font-bold">Disconnected</span></div>
                        <div class="flex justify-between text-[10px]"><span class="text-gray-400">Balance</span><span id="side-balance" class="text-gray-200 font-mono">$0.00</span></div>
                        <div class="flex justify-between text-[10px]"><span class="text-gray-400">Session PnL</span><span id="side-session-pnl" class="text-green-bitget font-bold">+$0.00</span></div>
                        <div class="flex justify-between text-[10px]"><span class="text-gray-400">Product</span><span id="side-product" class="text-gray-300">---</span></div>
                    </div>
                    <div class="space-y-3 mt-6"><div class="text-[9px] font-bold text-gray-500 uppercase tracking-widest border-b border-gray-800 pb-1">System</div>
                        <div class="flex justify-between text-[10px]"><span class="text-gray-400">WebSocket</span><span class="text-green-bitget font-bold uppercase">Ok</span></div>
                        <div class="flex justify-between text-[10px]"><span class="text-gray-400">Binance</span><span class="text-green-bitget font-bold uppercase">Ok</span></div>
                        <div class="flex justify-between text-[10px]"><span class="text-gray-400">CoinGecko</span><span class="text-gray-600 font-bold uppercase">--</span></div>
                    </div>
                    <div class="mt-8">
                        <div class="text-[9px] font-bold text-gray-500 uppercase tracking-widest border-b border-gray-800 pb-1 mb-2">Platform Note</div>
                        <p class="text-[9px] text-gray-400 italic leading-tight">Render Free Tier sleeps after 15m. Use an external pinger to keep active.</p>
                    </div>
                    <div class="mt-8"><div class="text-[9px] font-bold text-gray-500 uppercase tracking-widest border-b border-gray-800 pb-1 mb-3">Asset Signals</div><div id="asset-signals-container" class="space-y-2"></div></div>
                </div>
                <div class="mt-auto p-4 bg-dark/50 border-t border-gray-800">
                    <details class="text-xs group"><summary class="cursor-pointer text-gray-500 font-bold uppercase list-none flex justify-between items-center">Config <span class="group-open:rotate-180 transition">▼</span></summary>
                        <form action="/update-settings" method="post" class="space-y-2 mt-2"><input type="text" name="api_key" placeholder="Key" class="w-full bg-accent border border-gray-800 rounded px-2 py-1 text-[10px] text-white"><input type="password" name="api_secret" placeholder="Secret" class="w-full bg-accent border border-gray-800 rounded px-2 py-1 text-[10px] text-white"><button type="submit" class="w-full py-1 bg-gray-800 hover:bg-gray-700 rounded text-[9px] font-bold uppercase transition">Save</button></form>
                    </details>
                </div>
            </aside>
        </main>

        <script>
            let lastEventTime = Date.now() / 1000;
            const liveFeedTypes = ['RISK', 'MARKET', 'SCAN', 'SIGNAL', 'SYNC'];
            const liveFeedSymbols = ['BTC', 'ETH', 'XRP', 'ADA', 'SUI', 'ARB', 'APT'];
            function addLiveFeedItem() {
                const feed = document.getElementById('live-feed'); if (!feed) return;
                const type = liveFeedTypes[Math.floor(Math.random() * liveFeedTypes.length)];
                const symbol = liveFeedSymbols[Math.floor(Math.random() * liveFeedSymbols.length)];
                const typeColor = type === 'RISK' ? 'text-gold' : (type === 'SIGNAL' ? 'text-blue-500' : 'text-gray-500');
                const item = document.createElement('div'); item.className = 'flex justify-between items-start opacity-80';
                item.innerHTML = `<div class="flex space-x-2"><span class="${typeColor} font-bold">${type}</span><span class="text-gray-400">${symbol} DD tracking enabled</span></div><span class="text-gray-600">+${(Math.random()*0.5).toFixed(2)}%</span>`;
                feed.prepend(item); if (feed.children.length > 30) feed.removeChild(feed.lastChild);
            }
            // setInterval(addLiveFeedItem, 3000);

            async function updateDashboard() {
                try {
                    const res = await fetch('/api/status'); const status = await res.json();
                    const symbolMap = status.symbol_map || {};
                    
                    // Update News in Sidebar
                    const feed = document.getElementById('live-feed');
                    if (status.news && status.news.length > 0 && feed) {
                        feed.innerHTML = status.news.map(n => `
                            <div class="mb-2 pb-2 border-b border-gray-800 opacity-90">
                                <div class="text-blue-500 font-bold uppercase mb-1">NEWS | ${n.source.name}</div>
                                <div class="text-gray-200">${n.title}</div>
                                <div class="text-gray-500 mt-1">${new Date(n.publishedAt).toLocaleTimeString()}</div>
                            </div>
                        `).join('');
                    }

                    document.getElementById('stat-today-pnl').innerText = (status.today_pnl >= 0 ? '+' : '') + '$' + parseFloat(status.today_pnl).toFixed(2);
                    document.getElementById('stat-uptime').innerText = status.last_tick.split(' ')[1] || 'WAIT';
                    document.getElementById('stat-balance').innerText = '$' + parseFloat(status.balance).toLocaleString(undefined, {minimumFractionDigits: 2});
                    document.getElementById('stat-unrealized').innerText = (status.unrealized_pnl >= 0 ? '+' : '') + '$' + parseFloat(status.unrealized_pnl).toFixed(2);
                    document.getElementById('stat-unrealized').className = 'text-sm font-bold font-mono ' + (status.unrealized_pnl >= 0 ? 'text-green-bitget' : 'text-red-bitget');
                    document.getElementById('stat-trades').innerText = status.trades_count;
                    document.getElementById('stat-winrate').innerText = status.win_rate + '%';
                    document.getElementById('stat-drawdown').innerText = status.drawdown.toFixed(1) + '%';
                    document.getElementById('stat-open').innerText = status.open_count;
                    document.getElementById('side-balance').innerText = '$' + parseFloat(status.balance).toLocaleString(undefined, {minimumFractionDigits: 2});
                    document.getElementById('side-session-pnl').innerText = (status.session_pnl >= 0 ? '+' : '') + '$' + parseFloat(status.session_pnl).toFixed(2);
                    document.getElementById('side-product').innerText = status.product_type;
                    document.getElementById('side-connection').innerText = status.is_active ? 'Connected' : 'Disconnected';
                    document.getElementById('side-connection').className = 'font-bold ' + (status.is_active ? 'text-green-bitget' : 'text-red-bitget');
                    
                    const sideAutoStatus = document.getElementById('side-auto-status');
                    sideAutoStatus.className = 'w-3 h-3 rounded-full ' + (status.auto_trade ? 'bg-green-500 shadow-[0_0_10px_#0ecb81]' : 'bg-red-500');
                    document.getElementById('auto-status-text').innerText = status.auto_trade ? '● RUNNING' : '● STOPPED';
                    document.getElementById('auto-status-text').className = 'text-[10px] font-bold mb-4 ' + (status.auto_trade ? 'text-green-bitget' : 'text-red-500');

                    const dot = document.getElementById('auto-trade-dot');
                    const toggle = dot.parentElement;
                    if (status.auto_trade) { dot.style.left = '18px'; toggle.classList.remove('bg-gray-700'); toggle.classList.add('bg-green-500'); } 
                    else { dot.style.left = '2px'; toggle.classList.remove('bg-green-500'); toggle.classList.add('bg-gray-700'); }

                    const assetContainer = document.getElementById('asset-signals-container');
                    let assetHtml = '';
                    for (const sym in status.asset_signals) {
                        const score = status.asset_signals[sym];
                        assetHtml += `<div class="space-y-1"><div class="flex justify-between text-[8px] uppercase font-bold text-gray-500"><span>${symbolMap[sym] || sym}</span></div><div class="w-full bg-gray-900 h-1.5 rounded-full overflow-hidden border border-gray-800"><div class="bg-blue-600 h-full" style="width: ${score}%"></div></div></div>`;
                    }
                    assetContainer.innerHTML = assetHtml;

                    document.getElementById('signal-count').innerText = status.trade_signals.length;
                    const signalList = document.getElementById('trade-signals-list');
                    signalList.innerHTML = status.trade_signals.map(s => `
                        <div class="bg-card border border-gray-800 rounded p-3 flex justify-between items-center relative overflow-hidden group">
                            <div class="absolute left-0 top-0 bottom-0 w-1 ${s.type === 'LONG' ? 'bg-green-bitget' : 'bg-red-bitget'}"></div>
                            <div class="space-y-1"><div class="flex items-center space-x-2"><span class="bg-accent text-[9px] px-1.5 py-0.5 rounded font-bold text-white uppercase">${s.type === 'LONG' ? 'Scalp' : 'Trend'}</span><span class="text-xs font-bold text-white">${symbolMap[s.symbol] || s.symbol} ${s.type}</span></div><div class="text-[9px] text-gray-500 font-mono">trend <span class="text-gray-300">25pt</span> | liquidity <span class="text-gray-300">10pt</span></div></div>
                            <div class="text-right flex items-center space-x-6"><div class="text-center"><div class="text-xs font-bold text-white">${s.score}</div><div class="text-[9px] text-blue-500 font-bold">${s.r_r}</div></div>
                                <div class="flex space-x-2"><form action="/approve-signal" method="post"><input type="hidden" name="symbol" value="${s.symbol}"><input type="hidden" name="signal_type" value="${s.type}"><button class="bg-green-bitget/10 text-green-bitget border border-green-bitget/30 px-3 py-1 rounded text-[10px] font-bold hover:bg-green-bitget/20 transition">Approve</button></form>
                                <form action="/reject-signal" method="post"><input type="hidden" name="symbol" value="${s.symbol}"><input type="hidden" name="signal_type" value="${s.type}"><button class="bg-red-bitget/10 text-red-bitget border border-red-bitget/30 px-3 py-1 rounded text-[10px] font-bold hover:bg-red-bitget/20 transition">Reject</button></form></div>
                            </div>
                        </div>
                    `).join('');

                    const posBody = document.getElementById('positions-body');
                    let posHtml = '';
                    for (const symbol in status.positions) {
                        const pos = status.positions[symbol];
                        if (pos && typeof pos === 'object') {
                            const side = (pos.holdSide || 'N/A').toUpperCase(); const pnl = pos.unrealizedPL || '0';
                            const pnlColor = parseFloat(pnl) >= 0 ? "text-green-bitget" : "text-red-bitget"; const sideColor = side === 'LONG' ? 'text-green-bitget' : 'text-red-bitget';
                            posHtml += `<tr class="hover:bg-gray-800/30 transition text-gray-300"><td class="px-4 py-2 font-bold text-white">${symbolMap[symbol] || symbol}</td><td class="px-4 py-2 font-bold ${sideColor}">${side}</td><td class="px-4 py-2 font-mono">$${pos.total}</td><td class="px-4 py-2 font-mono text-gray-400">$${parseFloat(pos.averageOpenPrice).toFixed(2)}</td><td class="px-4 py-2 font-mono text-gray-400">$${parseFloat(status.prices[symbol] || 0).toFixed(2)}</td><td class="px-4 py-2 font-bold ${pnlColor}">$${parseFloat(pnl).toFixed(2)}</td><td class="px-4 py-2 text-right"><form action="/manual-order" method="post" class="inline"><input type="hidden" name="symbol" value="${symbol}"><input type="hidden" name="side" value="close"><button type="submit" class="text-[9px] bg-accent border border-gray-700 px-2 py-0.5 rounded text-gray-400 hover:text-white transition">Close</button></form></td></tr>`;
                        }
                    }
                    posBody.innerHTML = posHtml || '<tr><td colspan="7" class="px-4 py-8 text-center text-gray-600 italic">No Active Positions</td></tr>';

                    if (status.events && status.events.length > 0) {
                        const latest = status.events[status.events.length - 1];
                        if (latest.ts > lastEventTime) { document.getElementById('snd-order').play().catch(e => console.log("Audio blocked")); lastEventTime = latest.ts; }
                    }
                } catch (e) { console.error("Update failed", e); }
            }
            setInterval(updateDashboard, 2000);
        </script>
    </body></html>
    """
    return html_template

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
async def update_settings(api_key: str = Form(...), api_secret: str = Form(...), passphrase: str = Form(...), product_type: str = Form("usdt-futures")):
    if bot_instance:
        bot_instance.update_settings(api_key, api_secret, passphrase, product_type=product_type)
    return RedirectResponse(url="/", status_code=303)

@app.post("/apply-template")
async def apply_template(template: str = Form(...)):
    if bot_instance:
        bot_instance.apply_template(template)
    return RedirectResponse(url="/", status_code=303)

@app.post("/approve-signal")
async def approve_signal(symbol: str = Form(...), signal_type: str = Form(...)):
    if bot_instance:
        # Find the signal in trade_signals and mark as approved
        for s in bot_instance.status["trade_signals"]:
            if s["symbol"] == symbol and s["type"] == signal_type and s["status"] == "PENDING":
                s["status"] = "APPROVED"
                # Logic to actually place the order
                side = 'buy' if signal_type == 'LONG' else 'sell'
                bot_instance.manual_order(symbol, side, 'market', 0.01) # Default size for manual approval
                bot_instance.add_log(f"Signal Approved: {signal_type} for {symbol}")
                break
    return RedirectResponse(url="/", status_code=303)

@app.post("/reject-signal")
async def reject_signal(symbol: str = Form(...), signal_type: str = Form(...)):
    if bot_instance:
        bot_instance.status["trade_signals"] = [s for s in bot_instance.status["trade_signals"] if not (s["symbol"] == symbol and s["type"] == signal_type)]
        bot_instance.add_log(f"Signal Rejected: {signal_type} for {symbol}")
    return RedirectResponse(url="/", status_code=303)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "bot_active": bot_instance.status['is_active'] if bot_instance else False}
