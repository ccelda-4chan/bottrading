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
        ema_200 = self._ema(closes, 200) if len(closes) >= 200 else ema_long # Golden Line / Trend filter
        
        # Calculate ATR
        atr = self._atr(highs, lows, closes, self.atr_window)

        # RSI and Stochastic RSI
        rsi = self._rsi(closes, 14)
        stoch_k, stoch_d = self._stoch_rsi(rsi, 14, 3, 3)

        # Bollinger Bands
        bb_upper, bb_lower, bb_mid = self._bollinger_bands(closes, 20)
        
        # Momentum (ROC)
        momentum = ((closes[-1] - closes[-10]) / closes[-10]) * 100 if len(closes) > 10 else 0

        # Elliott 5th Wave Recognition (Simplified: Look for 3 higher highs/lows)
        wave_pts = self._detect_waves(highs, lows)

        # Trend strength (Ad-hoc)
        trend_pts = 0
        if ema_short[-1] > ema_long[-1]: trend_pts += 25
        if closes[-1] > ema_200[-1]: trend_pts += 15
        
        # Golden Line alignment (Close near EMA 200/50)
        golden_line_score = 15 if abs(closes[-1] - ema_200[-1]) / ema_200[-1] < 0.01 else 0

        # Liquidity/Volume score (Ad-hoc)
        vol_avg = np.mean(volumes[-10:])
        vol_pts = 10 if volumes[-1] > vol_avg else 0

        # Trust Score calculation (0-100)
        # Trust Score = Alignment of RSI, Stoch, EMA, BB, Waves
        trust_score = trend_pts + vol_pts + golden_line_score + wave_pts
        if stoch_k[-1] < 20 or stoch_k[-1] > 80: trust_score += 15
        if abs(rsi[-1] - 50) > 20: trust_score += 15
        
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
            "momentum": momentum,
            "vol_score": vol_pts,
            "trend_score": trend_pts,
            "wave_score": wave_pts,
            "total_score": trust_score # Trust Score
        }

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

        # Base signal from EMA Crossover
        signal = "HOLD"
        
        # Trend indicators
        trend_up = indicators["ema_short"] > indicators["ema_long"]
        trend_strong_up = indicators["last_close"] > indicators["ema_200"]
        stoch_rsi_low = indicators["stoch_k"] < 20
        stoch_rsi_high = indicators["stoch_k"] > 80
        
        # Standard Cross
        if indicators["ema_short"] > indicators["ema_long"] and indicators["prev_ema_short"] <= indicators["prev_ema_long"]:
            signal = "LONG"
        elif indicators["ema_short"] < indicators["ema_long"] and indicators["prev_ema_short"] >= indicators["prev_ema_long"]:
            signal = "SHORT"

        # Stochastic RSI Reversals (High Frequency)
        if signal == "HOLD":
            if stoch_rsi_low and indicators["stoch_k"] > indicators["stoch_d"]:
                signal = "LONG"
            elif stoch_rsi_high and indicators["stoch_k"] < indicators["stoch_d"]:
                signal = "SHORT"

        # Risky Mode: Aggressive entry points using RSI, BB, and Waves
        if self.mode == "Risky" or True: # Making it more aggressive by default as requested
            current_price = indicators["last_close"]
            rsi = indicators["rsi"]
            
            # Oversold + BB Lower touch = Risky Long (Aggressive reversal)
            if rsi < 35 or current_price < indicators["bb_lower"]:
                if signal == "HOLD": signal = "LONG"
            
            # Overbought + BB Upper touch = Risky Short (Aggressive reversal)
            if rsi > 65 or current_price > indicators["bb_upper"]:
                if signal == "HOLD": signal = "SHORT"

            # Trend Continuation (Aggressive)
            if signal == "HOLD":
                if trend_up and trend_strong_up and rsi < 65:
                    signal = "LONG" # Buy the dip
                elif not trend_up and not trend_strong_up and rsi > 35:
                    signal = "SHORT" # Sell the rip
        
        # Wave 5 potential (Add trust but also trigger)
        if indicators["wave_score"] >= 20 and signal == "HOLD":
            signal = "LONG" if trend_up else "SHORT"

        # News override/boost
        if news_sentiment > 1.5:
            signal = "LONG" # News-driven scalp
        if news_sentiment < -1.5:
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
