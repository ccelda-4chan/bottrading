import time
from loguru import logger
from bitget_client import BitgetDemoClient
from strategy import Strategy

class TradingBot:
    def __init__(self, api_key, api_secret, passphrase, symbols):
        self.client = BitgetDemoClient(api_key, api_secret, passphrase)
        self.strategy = Strategy()
        self.symbols = symbols
        self.is_running = False
        self.auto_trade = False  # Added auto_trade flag
        self.status = {
            "balance": 0.0,
            "last_tick": "Never",
            "positions": {},
            "signals": {},
            "is_active": False,
            "auto_trade": False,
            "logs": [],
            "events": [] # To store sound events
        }

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
        self.add_log("Bot Engine Started")
        
        while self.is_running:
            try:
                self.tick()
                self.status["auto_trade"] = self.auto_trade
            except Exception as e:
                logger.error(f"Error during tick: {e}")
                self.add_log(f"Tick Error: {str(e)}")
            
            # Use small sleeps to allow quicker shutdown
            for _ in range(int(interval)):
                if not self.is_running:
                    break
                time.sleep(1)

    def tick(self):
        # 1. Get account balance
        assets = self.client.get_account_assets()
        if not assets:
            logger.warning("Could not fetch balance, skipping tick.")
            self.status["balance"] = 0.0 # Clear if failed
            return
        
        # USDT-M balance. The API returns a list or a dict.
        # Based on Bitget V2 docs, it's usually a list when calling /accounts
        if isinstance(assets, list) and len(assets) > 0:
            # Try to find USDT specifically if multiple coins returned
            usdt_asset = next((a for a in assets if a.get('marginCoin') == 'USDT'), assets[0])
            usdt_balance = float(usdt_asset.get('available', 0))
        elif isinstance(assets, dict):
            usdt_balance = float(assets.get('available', 0))
        else:
            usdt_balance = 0.0

        self.status["balance"] = usdt_balance
        self.status["last_tick"] = time.strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"Current Balance: {usdt_balance} USDT")

        # 2. Check each symbol
        for symbol in self.symbols:
            self.process_symbol(symbol, usdt_balance)

    def process_symbol(self, symbol, balance):
        logger.info(f"Processing {symbol}...")
        
        # Get candles
        candles = self.client.get_candles(symbol, granularity='1H', limit=50)
        if not candles:
            return

        # Calculate indicators
        indicators = self.strategy.calculate_indicators(candles)
        if not indicators:
            return

        # Generate signal
        signal = self.strategy.generate_signal(indicators)
        self.status["signals"][symbol] = signal
        logger.info(f"Signal for {symbol}: {signal}")

        # Check existing positions
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
                if current_pos and current_pos.get('holdSide') == 'short':
                    logger.info(f"Closing SHORT position for {symbol}")
                    self.add_log(f"Auto-closing SHORT for {symbol}")
                    self.client.place_order(symbol, side='buy', order_type='market', size=current_pos['total'])
                
                if not current_pos or current_pos.get('holdSide') != 'long':
                    size = self.strategy.calculate_position_size(balance, indicators['last_close'], indicators['atr'])
                    if size > 0:
                        logger.info(f"Auto-opening LONG for {symbol} (size {size:.4f})")
                        self.add_log(f"Auto-opening LONG for {symbol} (size {size:.4f})")
                        self.add_event("place_order")
                        self.client.place_order(symbol, side='buy', order_type='market', size=size)

            elif signal == "SHORT":
                if current_pos and current_pos.get('holdSide') == 'long':
                    logger.info(f"Closing LONG position for {symbol}")
                    self.add_log(f"Auto-closing LONG for {symbol}")
                    self.client.place_order(symbol, side='sell', order_type='market', size=current_pos['total'])
                
                if not current_pos or current_pos.get('holdSide') != 'short':
                    size = self.strategy.calculate_position_size(balance, indicators['last_close'], indicators['atr'])
                    if size > 0:
                        logger.info(f"Auto-opening SHORT for {symbol} (size {size:.4f})")
                        self.add_log(f"Auto-opening SHORT for {symbol} (size {size:.4f})")
                        self.add_event("place_order")
                        self.client.place_order(symbol, side='sell', order_type='market', size=size)
            else:
                logger.info(f"Holding {symbol}...")
        else:
            logger.info(f"Auto-trade disabled. Skipping execution for {symbol}")

    def update_settings(self, api_key, api_secret, passphrase):
        self.client.api_key = api_key
        self.client.api_secret = api_secret
        self.client.passphrase = passphrase
        self.add_log("API Settings Updated")
        return True

    def manual_order(self, symbol, side, order_type, size):
        self.add_log(f"Manual {side.upper()} order for {symbol} (size {size})")
        self.add_event("place_order")
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
