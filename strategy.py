import numpy as np
from loguru import logger

class Strategy:
    """
    Elite Pro Trading Strategy: Combines Trend, SMC, Mean Reversion, and Wave analysis.
    Supports modes: Elite, SMC, Quant, Scalp, Swing, and Risky.
    """
    def __init__(self, short_window=9, long_window=21, atr_window=14, risk_per_trade=0.01):
        self.short_window = short_window
        self.long_window = long_window
        self.atr_window = atr_window
        self.risk_per_trade = risk_per_trade
        # Strategy State
        self.mode = "Elite" 
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

        if len(closes) < 20:
            return None

        # Calculate EMAs
        ema_short = self._ema(closes, self.short_window)
        ema_long = self._ema(closes, self.long_window)
        ema_200 = self._ema(closes, 200) if len(closes) >= 200 else ema_long # Golden Line / Trend filter
        
        # Calculate ATR
        atr = self._atr(highs, lows, closes, self.atr_window)

        # RSI and Stochastic RSI
        rsi = self._rsi(closes, 14)
        stoch_k, stoch_d = self._stoch_rsi(rsi, 14, 3, 3)

        # Bollinger Bands
        bb_upper, bb_lower, bb_mid = self._bollinger_bands(closes, 20)
        
        # MACD
        macd_line, signal_line, macd_hist = self._macd(closes)

        # ADX
        adx = self._adx(highs, lows, closes, 14)

        # Momentum (ROC)
        momentum = ((closes[-1] - closes[-10]) / closes[-10]) * 100 if len(closes) > 10 else 0

        # Elliott 5th Wave Recognition
        wave_pts = self._detect_waves(highs, lows)

        # Trend strength
        trend_pts = 0
        if ema_short[-1] > ema_long[-1]: trend_pts += 25
        if closes[-1] > ema_200[-1]: trend_pts += 15
        if adx[-1] > 25: trend_pts += 10
        
        # Golden Line alignment
        golden_line_score = 15 if abs(closes[-1] - ema_200[-1]) / ema_200[-1] < 0.01 else 0

        # Liquidity/Volume score
        vol_avg = np.mean(volumes[-20:])
        vol_pts = 10 if volumes[-1] > vol_avg else 0

        # SMC Detection
        smc_score = self._detect_smc(highs, lows, closes)

        # Trust Score calculation (0-100)
        trust_score = trend_pts + vol_pts + golden_line_score + wave_pts + smc_score
        if stoch_k[-1] < 20 or stoch_k[-1] > 80: trust_score += 10
        if abs(rsi[-1] - 50) > 20: trust_score += 10
        
        trust_score = min(100, trust_score)

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
            "stoch_k": stoch_k[-1],
            "stoch_d": stoch_d[-1],
            "bb_upper": bb_upper[-1],
            "bb_lower": bb_lower[-1],
            "bb_mid": bb_mid[-1],
            "macd": macd_line[-1],
            "macd_signal": signal_line[-1],
            "macd_hist": macd_hist[-1],
            "adx": adx[-1],
            "momentum": momentum,
            "vol_score": vol_pts,
            "trend_score": trend_pts,
            "wave_score": wave_pts,
            "smc_score": smc_score,
            "total_score": trust_score
        }

    def _macd(self, data, fast=12, slow=26, signal=9):
        ema_fast = self._ema(data, fast)
        ema_slow = self._ema(data, slow)
        macd_line = ema_fast - ema_slow
        signal_line = self._ema(macd_line, signal)
        macd_hist = macd_line - signal_line
        return macd_line, signal_line, macd_hist

    def _adx(self, highs, lows, closes, window):
        plus_dm = np.zeros_like(highs)
        minus_dm = np.zeros_like(lows)
        for i in range(1, len(highs)):
            up_move = highs[i] - highs[i-1]
            down_move = lows[i-1] - lows[i]
            if up_move > down_move and up_move > 0: plus_dm[i] = up_move
            if down_move > up_move and down_move > 0: minus_dm[i] = down_move
        
        tr = np.zeros_like(closes)
        for i in range(1, len(closes)):
            tr[i] = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
        
        tr_smooth = self._ema(tr, window)
        plus_di = 100 * self._ema(plus_dm, window) / tr_smooth
        minus_di = 100 * self._ema(minus_dm, window) / tr_smooth
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = self._ema(dx, window)
        return adx

    def _detect_smc(self, highs, lows, closes):
        """Simple SMC detection: Fair Value Gaps (FVG)"""
        score = 0
        if len(closes) < 5: return 0
        if highs[-3] < lows[-1]: score += 15 # Bullish FVG
        if lows[-3] > highs[-1]: score += 15 # Bearish FVG
        return score

    def _stoch_rsi(self, rsi, window, k_period, d_period):
        rsi_min = np.zeros_like(rsi)
        rsi_max = np.zeros_like(rsi)
        for i in range(window, len(rsi)):
            rsi_min[i] = np.min(rsi[i-window+1:i+1])
            rsi_max[i] = np.max(rsi[i-window+1:i+1])
        
        stoch_rsi = np.zeros_like(rsi)
        denom = rsi_max - rsi_min
        stoch_rsi = np.divide(rsi - rsi_min, denom, out=np.zeros_like(rsi), where=denom!=0) * 100
        
        # Smoothing
        stoch_k = np.convolve(stoch_rsi, np.ones(k_period)/k_period, mode='same')
        stoch_d = np.convolve(stoch_k, np.ones(d_period)/d_period, mode='same')
        return stoch_k, stoch_d

    def _detect_waves(self, highs, lows):
        """
        Simplified Elliott Wave 5th Wave Detection:
        Looks for series of higher highs and higher lows in the last 50 bars.
        """
        if len(highs) < 20: return 0
        
        # Find local peaks/troughs
        last_20_highs = highs[-20:]
        last_20_lows = lows[-20:]
        
        # Very crude check: are we in a general uptrend but showing signs of exhaustion?
        # Or are we starting a 5th wave after a correction?
        # For now, let's use a point system for 'Wave Potential'
        pts = 0
        if highs[-1] > np.mean(last_20_highs): pts += 10
        if lows[-1] > np.mean(last_20_lows): pts += 10
        return pts

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

        signal = "HOLD"
        current_price = indicators["last_close"]
        rsi = indicators["rsi"]
        stoch_k = indicators["stoch_k"]
        stoch_d = indicators["stoch_d"]
        
        # Trend / Momentum filters
        trend_up = indicators["ema_short"] > indicators["ema_long"]
        trend_strong_up = current_price > indicators["ema_200"]
        adx_strong = indicators.get("adx", 0) > 25
        macd_bullish = indicators.get("macd_hist", 0) > 0
        
        # ELITE STRATEGY SELECTOR
        if self.mode in ["Elite", "Risky"]:
            if trend_up and trend_strong_up and macd_bullish and adx_strong:
                signal = "LONG"
            elif not trend_up and not trend_strong_up and not macd_bullish and adx_strong:
                signal = "SHORT"
            
            if signal == "HOLD":
                if (rsi < 30 or stoch_k < 15) and current_price < indicators["bb_lower"]:
                    signal = "LONG"
                elif (rsi > 70 or stoch_k > 85) and current_price > indicators["bb_upper"]:
                    signal = "SHORT"
            
            if signal == "HOLD":
                if indicators.get("smc_score", 0) > 0 and trend_strong_up:
                    signal = "LONG"
                if indicators.get("wave_score", 0) > 15:
                    signal = "LONG" if trend_up else "SHORT"

        elif self.mode == "SMC":
            if indicators.get("smc_score", 0) > 0:
                signal = "LONG" if trend_strong_up else "SHORT"
            elif indicators.get("wave_score", 0) > 10:
                signal = "LONG" if trend_up else "SHORT"

        elif self.mode == "Quant":
            score = indicators["total_score"]
            if score > 80: signal = "LONG"
            elif score < 30: signal = "SHORT"

        elif self.mode == "Scalp":
            if stoch_k < 20 and stoch_k > stoch_d: signal = "LONG"
            elif stoch_k > 80 and stoch_k < stoch_d: signal = "SHORT"
            
        else: # Default
            if indicators["ema_short"] > indicators["ema_long"] and indicators["prev_ema_short"] <= indicators["prev_ema_long"]:
                signal = "LONG"
            elif indicators["ema_short"] < indicators["ema_long"] and indicators["prev_ema_short"] >= indicators["prev_ema_long"]:
                signal = "SHORT"

        if news_sentiment > 1.8: signal = "LONG"
        elif news_sentiment < -1.8: signal = "SHORT"
            
        return signal

    def calculate_position_size(self, balance, entry_price, atr, stop_loss_mult=1.5):
        if atr == 0 or balance <= 0: return 0
        effective_balance = min(balance, 1000000) 
        risk_amount = effective_balance * self.risk_per_trade
        stop_loss_dist = atr * stop_loss_mult
        if stop_loss_dist == 0: return 0
        return risk_amount / stop_loss_dist

    def apply_template(self, template_name):
        self.mode = template_name
        if template_name == "Elite":
            self.short_window = 7; self.long_window = 25; self.risk_per_trade = 0.03
        elif template_name == "Risky":
            self.short_window = 3; self.long_window = 7; self.risk_per_trade = 0.05
        elif template_name == "SMC":
            self.short_window = 10; self.long_window = 50; self.risk_per_trade = 0.02
        elif template_name == "Quant":
            self.short_window = 20; self.long_window = 100; self.risk_per_trade = 0.02
        elif template_name == "Scalp":
            self.short_window = 5; self.long_window = 13; self.risk_per_trade = 0.02
        elif template_name == "Swing":
            self.short_window = 12; self.long_window = 26; self.risk_per_trade = 0.01
        else:
            self.short_window = 9; self.long_window = 21; self.risk_per_trade = 0.01
        logger.info(f"Elite Strategy Template Applied: {template_name}")
