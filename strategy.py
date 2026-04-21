import numpy as np
from loguru import logger

class Strategy:
    """
    Real-world optimized strategy: EMA Cross with ATR-based volatility sizing.
    """
    def __init__(self, short_window=9, long_window=21, atr_window=14, risk_per_trade=0.01):
        self.short_window = short_window
        self.long_window = long_window
        self.atr_window = atr_window
        self.risk_per_trade = risk_per_trade

    def calculate_indicators(self, candles):
        """
        Expects candles in format: [[ts, open, high, low, close, vol, ...], ...]
        Sorted from oldest to newest.
        """
        # Extract closing prices and high/low for ATR
        closes = np.array([float(c[4]) for c in candles])
        highs = np.array([float(c[2]) for c in candles])
        lows = np.array([float(c[3]) for c in candles])

        if len(closes) < self.long_window:
            return None

        # Calculate EMAs
        ema_short = self._ema(closes, self.short_window)
        ema_long = self._ema(closes, self.long_window)
        
        # Calculate ATR
        atr = self._atr(highs, lows, closes, self.atr_window)

        return {
            "ema_short": ema_short[-1],
            "ema_long": ema_long[-1],
            "prev_ema_short": ema_short[-2],
            "prev_ema_long": ema_long[-2],
            "atr": atr[-1],
            "last_close": closes[-1]
        }

    def _ema(self, data, window):
        alpha = 2 / (window + 1)
        ema = np.zeros_like(data)
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = data[i] * alpha + ema[i-1] * (1 - alpha)
        return ema

    def _atr(self, highs, lows, closes, window):
        tr = np.zeros_like(closes)
        for i in range(1, len(closes)):
            tr[i] = max(highs[i] - lows[i], 
                        abs(highs[i] - closes[i-1]), 
                        abs(lows[i] - closes[i-1]))
        
        atr = np.zeros_like(tr)
        atr[window] = np.mean(tr[1:window+1])
        for i in range(window + 1, len(tr)):
            atr[i] = (atr[i-1] * (window - 1) + tr[i]) / window
        return atr

    def generate_signal(self, indicators, news_sentiment=0):
        if not indicators:
            return None

        # Crossover logic
        signal = "HOLD"
        if indicators["ema_short"] > indicators["ema_long"] and indicators["prev_ema_short"] <= indicators["prev_ema_long"]:
            signal = "LONG"
        elif indicators["ema_short"] < indicators["ema_long"] and indicators["prev_ema_short"] >= indicators["prev_ema_long"]:
            signal = "SHORT"
        
        # News override/boost
        if news_sentiment > 2 and signal == "HOLD":
            return "LONG" # News-driven scalp
        if news_sentiment < -2 and signal == "HOLD":
            return "SHORT" # News-driven dump
            
        return signal

    def calculate_position_size(self, balance, entry_price, atr, stop_loss_mult=2.0):
        """
        Risk-based position sizing: Risk 1% of equity per trade.
        Stop loss = 2 * ATR
        """
        if atr == 0: return 0
        
        risk_amount = balance * self.risk_per_trade
        stop_loss_dist = atr * stop_loss_mult
        
        if stop_loss_dist == 0: return 0
        
        # position_size = risk_amount / stop_loss_dist
        return risk_amount / stop_loss_dist
