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
        self.status = {
            "balance": 0.0,
            "last_tick": "Never",
            "positions": {},
            "signals": {},
            "is_active": False
        }

    def run(self, interval=60):
        logger.info(f"Starting Trading Bot for symbols: {self.symbols}")
        self.is_running = True
        self.status["is_active"] = True
        
        while self.is_running:
            try:
                self.tick()
            except Exception as e:
                logger.error(f"Error during tick: {e}")
            
            time.sleep(interval)

    def tick(self):
        # 1. Get account balance
        assets = self.client.get_account_assets()
        if not assets:
            logger.warning("Could not fetch balance, skipping tick.")
            return
        
        # USDT-M balance
        usdt_balance = float(assets[0].get('available', 0))
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
        if signal == "LONG":
            if current_pos and current_pos.get('holdSide') == 'short':
                logger.info(f"Closing SHORT position for {symbol}")
                self.client.place_order(symbol, side='buy', order_type='market', size=current_pos['total'])
            
            if not current_pos or current_pos.get('holdSide') != 'long':
                size = self.strategy.calculate_position_size(balance, indicators['last_close'], indicators['atr'])
                if size > 0:
                    logger.info(f"Opening LONG position for {symbol} with size {size}")
                    self.client.place_order(symbol, side='buy', order_type='market', size=size)

        elif signal == "SHORT":
            if current_pos and current_pos.get('holdSide') == 'long':
                logger.info(f"Closing LONG position for {symbol}")
                self.client.place_order(symbol, side='sell', order_type='market', size=current_pos['total'])
            
            if not current_pos or current_pos.get('holdSide') != 'short':
                size = self.strategy.calculate_position_size(balance, indicators['last_close'], indicators['atr'])
                if size > 0:
                    logger.info(f"Opening SHORT position for {symbol} with size {size}")
                    self.client.place_order(symbol, side='sell', order_type='market', size=size)

        else:
            logger.info(f"Holding {symbol}...")
