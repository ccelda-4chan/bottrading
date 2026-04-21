import requests
import numpy as np
from loguru import logger
from bitget_client import BitgetPublicClient
from strategy import Strategy

# Mock classes to simulate Bitget response
class MockMarketApi:
    def ticker(self, symbol):
        return {"symbol": symbol, "lastPr": "50000"}

class MockAccountApi:
    def account(self, symbol, marginCoin):
        return [{"available": "10000", "marginCoin": "USDT"}]

def test_connectivity():
    logger.info("Starting connectivity and logic test...")
    
    # Test Strategy
    strat = Strategy()
    # Mock candles: [ts, open, high, low, close, vol]
    mock_candles = [[str(i), "100", "110", "90", "105", "1000"] for i in range(50)]
    indicators = strat.calculate_indicators(mock_candles)
    if indicators:
        logger.info(f"Strategy Indicators test: OK (last_close: {indicators['last_close']})")
    else:
        logger.error("Strategy Indicators test: FAILED")
    
    # Test Client Initialization
    try:
        client = BitgetPublicClient()
        logger.info("BitgetPublicClient initialized: OK")
    except Exception as e:
        logger.error(f"BitgetPublicClient initialization: FAILED ({e})")

    logger.info("Test complete.")

if __name__ == "__main__":
    test_connectivity()
