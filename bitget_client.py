import requests
import time
import hmac
import hashlib
import json
from loguru import logger

class BitgetDemoClient:
    """
    A lightweight, production-ready Bitget API client specifically for Demo Trading.
    It manually handles authentication and the required 'paptrading: 1' header.
    """
    def __init__(self, api_key, api_secret, passphrase):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.base_url = "https://api.bitget.com"
        self.session = requests.Session()
        # Crucial for Demo Trading
        self.session.headers.update({"paptrading": "1"})

    def _generate_signature(self, timestamp, method, request_path, body=""):
        message = str(timestamp) + method.upper() + request_path + body
        mac = hmac.new(bytes(self.api_secret, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod=hashlib.sha256)
        return str(mac.digest().hex()) # Note: Bitget uses base64 for real, but some docs say hex for V2. Let's use the standard V1/V2 auth.
        # Actually, Bitget V1/V2 usually uses Base64. Let's re-verify.
        # Correct Bitget V2 signature: base64.b64encode(hmac.new(...).digest()).decode()

    def _get_auth_headers(self, method, request_path, body=""):
        import base64
        timestamp = int(time.time() * 1000)
        message = str(timestamp) + method.upper() + request_path + body
        mac = hmac.new(bytes(self.api_secret, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod=hashlib.sha256)
        sign = base64.b64encode(mac.digest()).decode()
        
        return {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": sign,
            "ACCESS-PASSPHRASE": self.passphrase,
            "ACCESS-TIMESTAMP": str(timestamp),
            "Content-Type": "application/json",
            "paptrading": "1"
        }

    def request(self, method, path, params=None, body=None):
        url = self.base_url + path
        body_str = json.dumps(body) if body else ""
        headers = self._get_auth_headers(method, path, body_str)
        
        try:
            if method.upper() == "GET":
                resp = self.session.get(url, params=params, headers=headers, timeout=10)
            else:
                resp = self.session.request(method, url, data=body_str, headers=headers, timeout=10)
            
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != "00000":
                logger.error(f"Bitget API Error: {data}")
                return None
            return data.get("data")
        except Exception as e:
            logger.error(f"HTTP Request failed: {e}")
            return None

    def get_ticker(self, symbol):
        # USDT-M Futures Ticker V2
        return self.request("GET", "/api/v2/mix/market/ticker", params={"symbol": symbol, "productType": "usdt-futures"})

    def get_candles(self, symbol, granularity='1h', limit=100):
        # V2 Market Candles
        params = {
            "symbol": symbol,
            "productType": "usdt-futures",
            "granularity": granularity,
            "limit": limit
        }
        return self.request("GET", "/api/v2/mix/market/candles", params=params)

    def get_account_assets(self, margin_coin="USDT"):
        return self.request("GET", "/api/v2/mix/account/accounts", params={"productType": "usdt-futures", "marginCoin": margin_coin})

    def place_order(self, symbol, side, order_type, size, margin_coin="USDT", price=None):
        body = {
            "symbol": symbol,
            "productType": "usdt-futures",
            "marginCoin": margin_coin,
            "side": side,  # buy, sell
            "orderType": order_type, # market, limit
            "size": str(size),
            "tradeSide": "open" if "open" in side else "close" # Simplified for V2 if needed, but V2 uses 'buy'/'sell' and 'posSide'
        }
        if price:
            body["price"] = str(price)
        
        # V2 order placement
        return self.request("POST", "/api/v2/mix/order/place-order", body=body)

    def get_open_positions(self, symbol=None):
        params = {"productType": "usdt-futures"}
        if symbol:
            params["symbol"] = symbol
        return self.request("GET", "/api/v2/mix/position/all-position", params=params)

    def set_leverage(self, symbol, leverage, margin_coin="USDT", hold_side="long"):
        body = {
            "symbol": symbol,
            "productType": "usdt-futures",
            "marginCoin": margin_coin,
            "leverage": str(leverage),
            "holdSide": hold_side
        }
        return self.request("POST", "/api/v2/mix/account/set-leverage", body=body)

    def set_margin_mode(self, symbol, margin_mode, margin_coin="USDT"):
        # margin_mode: isolated, crossed
        body = {
            "symbol": symbol,
            "productType": "usdt-futures",
            "marginCoin": margin_coin,
            "marginMode": margin_mode
        }
        return self.request("POST", "/api/v2/mix/account/set-margin-mode", body=body)
