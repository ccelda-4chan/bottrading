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
    def __init__(self, api_key, api_secret, passphrase, product_type="usdt-futures"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.product_type = product_type
        self.base_url = "https://api.bitget.com"
        self.session = requests.Session()
        # Crucial for Demo Trading
        self.session.headers.update({"paptrading": "1"})

    def _get_auth_headers(self, method, request_path, body=""):
        import base64
        timestamp = int(time.time() * 1000)
        
        # Ensure request_path includes query params if they exist for signature
        # But requests handles this. Bitget V2 signature: timestamp + method + path + body
        # request_path should be the raw path including ?params=val
        
        message = str(timestamp) + method.upper() + request_path + body
        mac = hmac.new(bytes(self.api_secret, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod=hashlib.sha256)
        sign = base64.b64encode(mac.digest()).decode()
        
        return {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": sign,
            "ACCESS-PASSPHRASE": self.passphrase,
            "ACCESS-TIMESTAMP": str(timestamp),
            "Content-Type": "application/json",
            "locale": "en-US",
            "paptrading": "1"
        }

    def request(self, method, path, params=None, body=None):
        # Bitget V2 requires query parameters in the signature for GET requests
        signed_path = path
        if params:
            # Sort params to ensure consistent signature if needed, though Bitget usually wants raw order
            query_str = "&".join([f"{k}={v}" for k, v in params.items()])
            signed_path = f"{path}?{query_str}"

        url = self.base_url + path
        body_str = json.dumps(body) if body else ""
        headers = self._get_auth_headers(method, signed_path, body_str)
        
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
        return self.request("GET", "/api/v2/mix/market/ticker", params={"symbol": symbol, "productType": self.product_type})

    def get_candles(self, symbol, granularity='1h', limit=100):
        # V2 Market Candles
        params = {
            "symbol": symbol,
            "productType": self.product_type,
            "granularity": granularity,
            "limit": limit
        }
        return self.request("GET", "/api/v2/mix/market/candles", params=params)

    def get_account_assets(self, product_type=None, margin_coin=None):
        # The API might return a list or a single object depending on if marginCoin is specified
        # V2 Get Account List: /api/v2/mix/account/accounts
        p_type = product_type if product_type else self.product_type
        params = {"productType": p_type}
        if margin_coin:
            params["marginCoin"] = margin_coin
        return self.request("GET", "/api/v2/mix/account/accounts", params=params)

    def place_order(self, symbol, side, order_type, size, margin_coin="USDT", price=None):
        body = {
            "symbol": symbol,
            "productType": self.product_type,
            "marginCoin": margin_coin,
            "side": side,  # buy, sell
            "orderType": order_type, # market, limit
            "size": str(size),
            "tradeSide": "open" if "open" in side else "close"
        }
        if price:
            body["price"] = str(price)
        
        return self.request("POST", "/api/v2/mix/order/place-order", body=body)

    def get_open_positions(self, symbol=None):
        params = {"productType": self.product_type}
        if symbol:
            params["symbol"] = symbol
        return self.request("GET", "/api/v2/mix/position/all-position", params=params)

    def set_leverage(self, symbol, leverage, margin_coin="USDT", hold_side="long"):
        body = {
            "symbol": symbol,
            "productType": self.product_type,
            "marginCoin": margin_coin,
            "leverage": str(leverage),
            "holdSide": hold_side
        }
        return self.request("POST", "/api/v2/mix/account/set-leverage", body=body)

    def set_margin_mode(self, symbol, margin_mode, margin_coin="USDT"):
        body = {
            "symbol": symbol,
            "productType": self.product_type,
            "marginCoin": margin_coin,
            "marginMode": margin_mode
        }
        return self.request("POST", "/api/v2/mix/account/set-margin-mode", body=body)
