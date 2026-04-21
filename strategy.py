import numpy as np
from loguru import logger

class Strategy:
    """
    Real-world optimized strategy: EMA Cross with ATR-based volatility sizing.
    Supports multiple modes: Default, Scalp, Swing, and Risky.
    """
    def __init__(self, short_window=9, long_window=21, atr_window=14, risk_per_trade=0.01):
        self.short_window = short_window
        self.long_window = long_window
        self.atr_window = atr_window
        self.risk_per_trade = risk_per_trade
        # Strategy State
        self.mode = "Default" # Default, Scalp, Swing, Risky
        self.timeframe = "1h"
        self.risk_per_trade = 0.01

    def calculate_indicators(self, candles, symbol="BTCUSDT"):
        """
        Expects candles in format: [[ts, open, high, low, close, vol, ...], ...]
        Sorted from oldest to newest.
        """
        # Extract prices
        closes = np.array([float(c[4]) for c in candles])
        highs = np.array([float(c[2]) for c in candles])
        lows = np.array([float(c[3]) for c in candles])
        volumes = np.array([float(c[5]) for c in candles])

        if len(closes) < max(self.long_window, 50):
            return None

        # Calculate EMAs
        ema_short = self._ema(closes, self.short_window)
        ema_long = self._ema(closes, self.long_window)
        ema_200 = self._ema(closes, 200) if len(closes) >= 200 else ema_long # Filter for trend
        
        # Calculate ATR
        atr = self._atr(highs, lows, closes, self.atr_window)

        # RSI
        rsi = self._rsi(closes, 14)

        # Bollinger Bands
        bb_upper, bb_lower, bb_mid = self._bollinger_bands(closes, 20)
        
        # Momentum (ROC)
        momentum = ((closes[-1] - closes[-10]) / closes[-10]) * 100 if len(closes) > 10 else 0

        # Trend strength (Ad-hoc)
        trend_pts = 0
        if ema_short[-1] > ema_long[-1]: trend_pts += 25
        if closes[-1] > ema_200[-1]: trend_pts += 15
        
        # Liquidity/Volume score (Ad-hoc)
        vol_avg = np.mean(volumes[-10:])
        vol_pts = 10 if volumes[-1] > vol_avg else 0

        # Score calculation (0-100)
        score = trend_pts + vol_pts + (20 if rsi < 30 or rsi > 70 else 0) + 15
        score = min(100, score)

        return {
            "symbol": symbol,
            "ema_short": ema_short[-1],
            "ema_long": ema_long[-1],
            "ema_200": ema_200[-1],
            "prev_ema_short": ema_short[-2],
            "prev_ema_long": ema_long[-2],
            "atr": atr[-1],
            "last_close": closes[-1],
            "rsi": rsi[-1],
            "bb_upper": bb_upper[-1],
            "bb_lower": bb_lower[-1],
            "bb_mid": bb_mid[-1],
            "momentum": momentum,
            "vol_score": vol_pts,
            "trend_score": trend_pts,
            "total_score": score
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

    def _rsi(self, data, window):
        delta = np.diff(data)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        
        avg_gain = np.zeros_like(data)
        avg_loss = np.zeros_like(data)
        
        avg_gain[window] = np.mean(gain[:window])
        avg_loss[window] = np.mean(loss[:window])
        
        for i in range(window + 1, len(data)):
            avg_gain[i] = (avg_gain[i-1] * (window - 1) + gain[i-1]) / window
            avg_loss[i] = (avg_loss[i-1] * (window - 1) + loss[i-1]) / window
            
        rs = np.divide(avg_gain, avg_loss, out=np.zeros_like(avg_gain), where=avg_loss!=0)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _bollinger_bands(self, data, window):
        sma = np.convolve(data, np.ones(window)/window, mode='same')
        std = np.zeros_like(data)
        for i in range(window, len(data)):
            std[i] = np.std(data[i-window:i])
        upper = sma + (std * 2)
        lower = sma - (std * 2)
        return upper, lower, sma

    def generate_signal(self, indicators, news_sentiment=0):
        if not indicators:
            return None

        # Base signal from EMA Crossover
        signal = "HOLD"
        
        # Trend check
        trend_up = indicators["ema_short"] > indicators["ema_long"]
        trend_strong_up = indicators["last_close"] > indicators["ema_200"]
        
        # Standard Cross
        if indicators["ema_short"] > indicators["ema_long"] and indicators["prev_ema_short"] <= indicators["prev_ema_long"]:
            signal = "LONG"
        elif indicators["ema_short"] < indicators["ema_long"] and indicators["prev_ema_short"] >= indicators["prev_ema_long"]:
            signal = "SHORT"

        # Risky Mode: Aggressive entry points using RSI and BB
        if self.mode == "Risky":
            current_price = indicators["last_close"]
            rsi = indicators["rsi"]
            
            # Oversold + BB Lower touch = Risky Long (Aggressive reversal)
            if rsi < 30 or current_price < indicators["bb_lower"]:
                if signal == "HOLD": signal = "LONG"
            
            # Overbought + BB Upper touch = Risky Short (Aggressive reversal)
            if rsi > 70 or current_price > indicators["bb_upper"]:
                if signal == "HOLD": signal = "SHORT"

            # Trend Continuation (Aggressive)
            if signal == "HOLD":
                if trend_up and trend_strong_up and rsi < 60:
                    signal = "LONG" # Buy the dip in strong uptrend
                elif not trend_up and not trend_strong_up and rsi > 40:
                    signal = "SHORT" # Sell the rip in strong downtrend
        
        # News override/boost
        if news_sentiment > 2:
            signal = "LONG" # News-driven scalp
        if news_sentiment < -2:
            signal = "SHORT" # News-driven dump
            
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

    def apply_template(self, template_name):
        self.mode = template_name
        if template_name == "Risky":
            self.short_window = 3
            self.long_window = 7
            self.risk_per_trade = 0.05
        elif template_name == "Scalp":
            self.short_window = 5
            self.long_window = 13
            self.risk_per_trade = 0.02
        elif template_name == "Swing":
            self.short_window = 12
            self.long_window = 26
            self.risk_per_trade = 0.01
        else:
            self.short_window = 9
            self.long_window = 21
            self.risk_per_trade = 0.01
        logger.info(f"Strategy Template Applied: {template_name}")
