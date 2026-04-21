import json
import os
import time
from loguru import logger
from bitget_client import BitgetDemoClient
from strategy import Strategy
from news_client import NewsClient

class TradingBot:
    def __init__(self, api_key, api_secret, passphrase, symbols, product_type="usdt-futures", news_api_key=None):
        self.client = BitgetDemoClient(api_key, api_secret, passphrase, product_type=product_type)
        self.strategy = Strategy()
        self.news_client = NewsClient(news_api_key) if news_api_key else None
        self.symbols = symbols
        self.product_type = product_type
        self.is_running = False
        self.auto_trade = False
        self.news_sentiment = 0
        self.persistence_file = "bot_state.json"
        
        # Simulation Mode state
        self.simulation_mode = not (api_key and api_secret)
        self.virtual_balance = 10000.0  # Starting virtual balance
        self.virtual_positions = {}  # {symbol: {holdSide: 'long'/'short', total: float, averageOpenPrice: float, tp: float, sl: float}}
        
        self.status = {
            "balance": 0.0,
            "today_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "trades_count": 0,
            "win_rate": 0,
            "drawdown": 0.0,
            "open_count": 0,
            "session_pnl": 0.0,
            "prices": {s: "0.00" for s in symbols}, # Initialized with 0.00
            "last_tick": "Never",
            "next_tick_in": 0,
            "positions": {s: "None" for s in symbols}, # Initialized with None
            "signals": {s: "WAITING" for s in symbols}, # Initialized with WAITING
            "is_active": False,
            "auto_trade": False,
            "simulation_mode": self.simulation_mode,
            "logs": [],
            "events": [], # To store sound events
            "asset_signals": {s: 50 for s in symbols}, # Mock score for bar chart
            "trade_signals": [], # List of pending/recent signals for approval
            "news": [], # Latest news
            "chart_timeframe": "1H"
        }
        self.initial_balance = None
        self.load_state()

    def save_state(self):
        try:
            state = {
                "initial_balance": self.initial_balance,
                "auto_trade": self.auto_trade,
                "logs": self.status["logs"],
                "trades_count": self.status["trades_count"],
                "virtual_balance": self.virtual_balance,
                "virtual_positions": self.virtual_positions,
                "simulation_mode": self.simulation_mode
            }
            with open(self.persistence_file, "w") as f:
                json.dump(state, f)
        except Exception as e:
            logger.warning(f"Failed to save state: {e}")

    def load_state(self):
        if os.path.exists(self.persistence_file):
            try:
                with open(self.persistence_file, "r") as f:
                    state = json.load(f)
                    self.initial_balance = state.get("initial_balance")
                    self.auto_trade = state.get("auto_trade", False)
                    self.status["logs"] = state.get("logs", [])
                    self.status["trades_count"] = state.get("trades_count", 0)
                    self.status["auto_trade"] = self.auto_trade
                    self.virtual_balance = state.get("virtual_balance", 10000.0)
                    self.virtual_positions = state.get("virtual_positions", {})
                    # Only override simulation mode if it was explicitly saved as true
                    # and we don't have API keys
                    if not (self.client.api_key and self.client.api_secret):
                         self.simulation_mode = True
                    else:
                         self.simulation_mode = state.get("simulation_mode", self.simulation_mode)
                    
                    self.status["simulation_mode"] = self.simulation_mode
                logger.info("Bot state restored from local storage")
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")

    def add_event(self, event_type):
        # event_type can be 'place_order', 'tp', 'sl'
        self.status["events"].append({"type": event_type, "ts": time.time()})
        if len(self.status["events"]) > 5:
            self.status["events"].pop(0)

    def add_log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.status["logs"].append(f"[{timestamp}] {message}")
        if len(self.status["logs"]) > 20:
            self.status["logs"].pop(0)

    def run(self, interval=10):
        logger.info(f"Starting Trading Bot for symbols: {self.symbols}")
        self.is_running = True
        self.status["is_active"] = True
        self.add_log("Bot Engine Active (Simulation Mode Available)")
        
        while self.is_running:
            try:
                self.tick()
                self.status["auto_trade"] = self.auto_trade
                self.status["simulation_mode"] = self.simulation_mode
            except Exception as e:
                logger.error(f"Error during tick: {e}")
                self.add_log(f"Tick Error: {str(e)}")
            
            # Use small sleeps for countdown precision
            interval_int = max(1, int(interval))
            for i in range(interval_int, 0, -1):
                self.status["next_tick_in"] = i
                if not self.is_running:
                    break
                time.sleep(1)

    def tick(self):
        # 0. Save State periodically
        self.save_state()

        # 0. Update News
        if self.news_client:
            news = self.news_client.get_crypto_news()
            if news:
                self.status["news"] = news
                # Calculate aggregate sentiment
                total_sentiment = 0
                for article in news:
                    total_sentiment += self.news_client.get_sentiment(article.get('title', '') + " " + article.get('description', ''))
                self.news_sentiment = total_sentiment
                logger.info(f"News Sentiment: {self.news_sentiment}")
                if self.news_sentiment > 2:
                    self.add_log(f"Bullish News Detected ({self.news_sentiment})")
                elif self.news_sentiment < -2:
                    self.add_log(f"Bearish News Detected ({self.news_sentiment})")

        # 1. Update real-time prices for all symbols
        for symbol in self.symbols:
            ticker = self.client.get_ticker(symbol)
            if ticker:
                # Bitget V2 ticker returns last price in 'lastPr'
                self.status["prices"][symbol] = ticker.get('lastPr', '0')
            elif self.simulation_mode:
                # If in simulation and API fails, use mock price if none exist
                if self.status["prices"].get(symbol) == "0.00":
                    self.status["prices"][symbol] = "60000.00" if "BTC" in symbol else "3000.00"

        # 2. Get account balance
        if self.simulation_mode:
            usdt_balance = self.virtual_balance
            logger.info(f"Simulation Mode: Balance {usdt_balance} USDT")
        else:
            usdt_balance = self.status.get("balance", 0.0)
            
            # Try primary product type (usually usdt-futures)
            assets = self.client.get_account_assets(margin_coin="USDT")
            
            # Fallback: If no assets found, try 'susdt-futures' which is common for demo
            if not assets and self.product_type == "usdt-futures":
                logger.info("No assets found for usdt-futures, trying susdt-futures fallback...")
                assets = self.client.get_account_assets(product_type="susdt-futures", margin_coin="USDT")
                
            # Fallback: Fetch all assets for primary product type if USDT-specific fetch returns nothing
            if not assets:
                logger.debug(f"USDT-specific asset fetch failed for {self.product_type}, trying all assets...")
                assets = self.client.get_account_assets()

            if assets:
                # USDT-M balance. The API returns a list or a dict.
                if isinstance(assets, list):
                    usdt_asset = next((a for a in assets if a.get('marginCoin') == 'USDT'), None)
                    if usdt_asset:
                        usdt_balance = float(usdt_asset.get('available', 0))
                    elif len(assets) > 0:
                        usdt_balance = float(assets[0].get('available', 0))
                elif isinstance(assets, dict):
                    if assets.get('marginCoin') == 'USDT' or 'available' in assets:
                        usdt_balance = float(assets.get('available', 0))
                
                logger.info(f"Updated Balance: {usdt_balance} USDT")
            else:
                logger.warning("Could not fetch balance from API, using last known value.")

        self.status["balance"] = usdt_balance
        if self.initial_balance is None and usdt_balance > 0:
            self.initial_balance = usdt_balance
        
        if self.initial_balance:
            self.status["session_pnl"] = usdt_balance - self.initial_balance
            self.status["today_pnl"] = self.status["session_pnl"]

        self.status["last_tick"] = time.strftime("%Y-%m-%d %H:%M:%S")

        # 3. Check each symbol
        total_unrealized = 0.0
        open_count = 0
        for symbol in self.symbols:
            self.process_symbol(symbol, usdt_balance)
            pos = self.status["positions"].get(symbol)
            if pos and isinstance(pos, dict):
                total_unrealized += float(pos.get('unrealizedPL', 0))
                open_count += 1
        
        self.status["unrealized_pnl"] = total_unrealized
        self.status["open_count"] = open_count

    def process_symbol(self, symbol, balance):
        logger.info(f"Processing {symbol}...")
        
        # Get candles
        candles = self.client.get_candles(symbol, granularity=self.status.get("chart_timeframe", "1H"), limit=50)
        if not candles:
            return

        # Calculate indicators
        indicators = self.strategy.calculate_indicators(candles)
        if not indicators:
            return

        # Generate signal
        signal = self.strategy.generate_signal(indicators, news_sentiment=self.news_sentiment)
        self.status["signals"][symbol] = signal
        logger.info(f"Signal for {symbol}: {signal}")
        
        # Update asset signal score
        score = 50
        if signal == "LONG": score = 80
        elif signal == "SHORT": score = 20
        self.status["asset_signals"][symbol] = score

        # Add to trade signals list if it's a new actionable signal
        if signal in ["LONG", "SHORT"]:
            exists = any(ts['symbol'] == symbol and ts['type'] == signal for ts in self.status["trade_signals"])
            if not exists:
                self.status["trade_signals"].insert(0, {
                    "symbol": symbol,
                    "type": signal,
                    "status": "PENDING",
                    "score": f"{score}/100",
                    "r_r": "2.0R",
                    "ts": time.time()
                })
                if len(self.status["trade_signals"]) > 5:
                    self.status["trade_signals"].pop()

        # Check existing positions
        if self.simulation_mode:
            current_pos = self.virtual_positions.get(symbol)
            if current_pos:
                # Update unrealized PNL for simulation
                current_price = float(self.status["prices"].get(symbol, 0))
                entry_price = current_pos['averageOpenPrice']
                size = current_pos['total']
                if current_pos['holdSide'] == 'long':
                    current_pos['unrealizedPL'] = (current_price - entry_price) * size
                else:
                    current_pos['unrealizedPL'] = (entry_price - current_price) * size
                
                # Check TP/SL
                tp_hit = (current_pos['holdSide'] == 'long' and current_price >= current_pos['tp']) or \
                         (current_pos['holdSide'] == 'short' and current_price <= current_pos['tp'])
                sl_hit = (current_pos['holdSide'] == 'long' and current_price <= current_pos['sl']) or \
                         (current_pos['holdSide'] == 'short' and current_price >= current_pos['sl'])
                
                if tp_hit or sl_hit:
                    event = "tp" if tp_hit else "sl"
                    logger.info(f"Simulation: {event.upper()} hit for {symbol}")
                    self.add_log(f"Simulation: {event.upper()} hit for {symbol} at {current_price}")
                    self.add_event(event)
                    self.virtual_balance += current_pos['unrealizedPL']
                    self.status["trades_count"] += 1
                    del self.virtual_positions[symbol]
                    current_pos = None
        else:
            positions = self.client.get_open_positions(symbol)
            current_pos = None
            if positions:
                for p in positions:
                    if float(p.get('total', 0)) != 0:
                        current_pos = p
                        break
        
        self.status["positions"][symbol] = current_pos if current_pos else "None"

        # Execution Logic
        if self.auto_trade:
            if signal == "LONG":
                self.execute_trade(symbol, "buy", balance, indicators)
            elif signal == "SHORT":
                self.execute_trade(symbol, "sell", balance, indicators)
            else:
                logger.info(f"Holding {symbol}...")
        else:
            logger.info(f"Auto-trade disabled. Skipping execution for {symbol}")

    def execute_trade(self, symbol, side, balance, indicators):
        current_pos = self.status["positions"].get(symbol)
        if current_pos == "None": current_pos = None
        
        target_side = "long" if side == "buy" else "short"
        opposite_side = "short" if side == "buy" else "long"
        close_side = "sell" if side == "buy" else "buy"

        # 1. Close opposite position
        if current_pos and current_pos.get('holdSide') == opposite_side:
            logger.info(f"Closing {opposite_side.upper()} position for {symbol}")
            self.add_log(f"Auto-closing {opposite_side.upper()} for {symbol}")
            if self.simulation_mode:
                self.virtual_balance += current_pos.get('unrealizedPL', 0)
                self.status["trades_count"] += 1
                del self.virtual_positions[symbol]
                self.status["positions"][symbol] = "None"
                current_pos = None
            else:
                self.client.place_order(symbol, side=close_side, order_type='market', size=current_pos['total'])

        # 2. Open new position
        if not current_pos or current_pos.get('holdSide') != target_side:
            size = self.strategy.calculate_position_size(balance, indicators['last_close'], indicators['atr'])
            if size > 0:
                logger.info(f"Auto-opening {target_side.upper()} for {symbol} (size {size:.4f})")
                self.add_log(f"Auto-opening {target_side.upper()} for {symbol} (size {size:.4f})")
                self.add_event("place_order")
                
                entry_price = indicators['last_close']
                tp_dist = indicators['atr'] * 3
                sl_dist = indicators['atr'] * 2
                tp = entry_price + tp_dist if target_side == "long" else entry_price - tp_dist
                sl = entry_price - sl_dist if target_side == "long" else entry_price + sl_dist

                if self.simulation_mode:
                    self.virtual_positions[symbol] = {
                        "holdSide": target_side,
                        "total": size,
                        "averageOpenPrice": entry_price,
                        "unrealizedPL": 0.0,
                        "tp": tp,
                        "sl": sl
                    }
                else:
                    self.client.place_order(symbol, side=side, order_type='market', size=size)

    def update_settings(self, api_key, api_secret, passphrase, product_type=None):
        self.client.api_key = api_key
        self.client.api_secret = api_secret
        self.client.passphrase = passphrase
        
        # Disable simulation if keys are provided
        if api_key and api_secret:
            self.simulation_mode = False
            self.status["simulation_mode"] = False
            self.add_log("API Keys Detected: Live Mode Enabled")
        
        if product_type:
            self.client.product_type = product_type
            self.product_type = product_type
        self.add_log("API Settings Updated")
        return True

    def manual_order(self, symbol, side, order_type, size):
        self.add_log(f"Manual {side.upper()} order for {symbol} (size {size})")
        self.add_event("place_order")
        
        if self.simulation_mode:
            entry_price = float(self.status["prices"].get(symbol, 0))
            if side in ["buy", "sell"]:
                target_side = "long" if side == "buy" else "short"
                # TP 5%, SL 2% for manual simulation
                tp_dist = entry_price * 0.05
                sl_dist = entry_price * 0.02
                self.virtual_positions[symbol] = {
                    "holdSide": target_side,
                    "total": float(size),
                    "averageOpenPrice": entry_price,
                    "unrealizedPL": 0.0,
                    "tp": entry_price + tp_dist if side == "buy" else entry_price - tp_dist,
                    "sl": entry_price - sl_dist if side == "buy" else entry_price + sl_dist
                }
            elif side == "close":
                 if symbol in self.virtual_positions:
                     self.virtual_balance += float(self.virtual_positions[symbol].get('unrealizedPL', 0))
                     self.status["trades_count"] += 1
                     del self.virtual_positions[symbol]
            return {"code": "00000", "data": {"orderId": "sim_123"}}
            
        return self.client.place_order(symbol, side=side, order_type=order_type, size=size)

    def apply_template(self, template_name):
        self.add_log(f"Applying template: {template_name}")
        if template_name == "Scalp":
            self.strategy.short_window = 5
            self.strategy.long_window = 13
            self.strategy.risk_per_trade = 0.005
            for sym in self.symbols:
                self.client.set_leverage(sym, 20)
                self.client.set_margin_mode(sym, "isolated")
        elif template_name == "Swing":
            self.strategy.short_window = 20
            self.strategy.long_window = 50
            self.strategy.risk_per_trade = 0.02
            for sym in self.symbols:
                self.client.set_leverage(sym, 5)
                self.client.set_margin_mode(sym, "crossed")
        elif template_name == "Default":
            self.strategy.short_window = 9
            self.strategy.long_window = 21
            self.strategy.risk_per_trade = 0.01
            for sym in self.symbols:
                self.client.set_leverage(sym, 10)
        return True
