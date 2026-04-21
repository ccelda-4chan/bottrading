import requests
import time
import json
import urllib3
from loguru import logger

# Disable SSL warnings for environments with certificate issues
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class BitgetPublicClient:
    """
    A public Bitget API client for market data (no auth required).
    """
    def __init__(self, product_type="usdt-futures"):
        self.product_type = product_type
        self.base_url = "https://api.bitget.com"
        self.session = requests.Session()

    def request(self, method, path, params=None):
        url = self.base_url + path
        try:
            resp = self.session.get(url, params=params, timeout=10, verify=False)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != "00000":
                logger.error(f"Bitget Public API Error: {data}")
                return None
            return data.get("data")
        except Exception as e:
            logger.error(f"Public HTTP Request failed: {e}")
            return None

    def get_ticker(self, symbol):
        # USDT-M Futures Ticker V2 Public
        return self.request("GET", "/api/v2/mix/market/ticker", params={"symbol": symbol, "productType": self.product_type})

    def get_candles(self, symbol, granularity='1h', limit=100):
        # V2 Market Candles Public
        params = {
            "symbol": symbol,
            "productType": self.product_type,
            "granularity": granularity,
            "limit": limit
        }
        return self.request("GET", "/api/v2/mix/market/candles", params=params)
