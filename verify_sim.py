
from bot import TradingBot
import time
from loguru import logger

def verify_sim():
    logger.info("Starting simulation verification...")
    symbols = ["BTCUSDT", "ETHUSDT"]
    bot = TradingBot(symbols=symbols)
    
    # Enable auto trade
    bot.auto_trade = True
    
    # Run a few ticks manually
    for i in range(3):
        logger.info(f"Tick {i+1}...")
        bot.tick()
        time.sleep(1)
    
    logger.info(f"Balance after 3 ticks: {bot.status['balance']}")
    logger.info(f"Positions: {bot.status['positions']}")
    logger.info(f"Trades Count: {bot.status['trades_count']}")
    
    if bot.status['balance'] > 0:
        logger.info("VERIFICATION SUCCESSFUL: Simulation is running.")
    else:
        logger.error("VERIFICATION FAILED: Balance is 0.")

if __name__ == "__main__":
    verify_sim()
