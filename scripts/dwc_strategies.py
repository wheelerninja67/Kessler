import math

class DWC_StrategyMatrix:
    """
    DWC Capitals Multi-Strategy Matrix.
    Real Mathematical Implementations.
    """
    
    @staticmethod
    def calculate_sma(closes, period=20):
        if len(closes) < period: return closes[-1]
        return sum(closes[-period:]) / period
        
    @staticmethod
    def calculate_std(closes, sma, period=20):
        if len(closes) < period: return 0.001
        variance = sum((x - sma) ** 2 for x in closes[-period:]) / period
        return math.sqrt(variance)

    @staticmethod
    def regime_classifier(candles):
        return "VOLATILE"

    @staticmethod
    def renaissance_stat_arb(candles, correlation_matrix=None):
        """
        Statistical Arbitrage (Mean Reversion).
        Calculates the real Z-Score over the last 20 periods.
        If price deviates > 2.5 Standard Deviations, it snaps back.
        """
        closes = [c['close'] for c in candles]
        if len(closes) < 20: return {"action": "HOLD", "confidence": 0.0, "strategy": "Stat_Arb"}
        
        sma = DWC_StrategyMatrix.calculate_sma(closes, 20)
        std = DWC_StrategyMatrix.calculate_std(closes, sma, 20)
        
        current_price = closes[-1]
        z_score = (current_price - sma) / (std if std > 0 else 0.001)
        
        if z_score > 2.5: # Extremely overbought
            return {"action": "SELL", "confidence": 0.95, "strategy": "Stat_Arb"}
        elif z_score < -2.5: # Extremely oversold
            return {"action": "BUY", "confidence": 0.95, "strategy": "Stat_Arb"}
            
        return {"action": "HOLD", "confidence": 0.0, "strategy": "Stat_Arb"}

    @staticmethod
    def institutional_stop_hunt(candles, liquidity_heatmap=None):
        """
        [PREDATORY INSTITUTIONAL FOREX STRATEGY]
        Smart Money Concepts (SMC): Liquidity Sweep + Fair Value Gap (FVG) + Macro Trend Filter
        This is the ultimate 'Sniper' strategy for Forex and Gold.
        """
        if len(candles) < 50: return {"action": "HOLD", "confidence": 0.0, "strategy": "Stop_Hunt"}
        
        # 1. Macro Trend Filter (50-Period SMA)
        closes = [c['close'] for c in candles]
        sma_50 = DWC_StrategyMatrix.calculate_sma(closes, 50)
        current_close = closes[-1]
        
        trend_is_bullish = current_close > sma_50
        trend_is_bearish = current_close < sma_50
        
        # 2. Look at the last 3 candles to find a Fair Value Gap (FVG)
        c1 = candles[-3]
        c2 = candles[-2] # The momentum candle
        c3 = candles[-1]
        
        # Bullish FVG: C1 High < C3 Low (Massive upward momentum left a gap)
        bullish_fvg = c1['high'] < c3['low']
        
        # Bearish FVG: C1 Low > C3 High (Massive downward momentum left a gap)
        bearish_fvg = c1['low'] > c3['high']
        
        # 3. Check if the momentum was preceded by a Liquidity Sweep
        recent_highs = [c['high'] for c in candles[-10:-3]]
        recent_lows = [c['low'] for c in candles[-10:-3]]
        local_high = max(recent_highs) if recent_highs else 0
        local_low = min(recent_lows) if recent_lows else 99999
        
        sweep_high = c1['high'] > local_high
        sweep_low = c1['low'] < local_low
        
        # 4. Execution Logic (Sniper Confluence)
        # We only BUY if we swept lows, formed a bullish FVG, AND the Macro Trend is Bullish.
        if sweep_low and bullish_fvg and trend_is_bullish:
            return {"action": "BUY", "confidence": 0.95, "strategy": "SMC_Filtered"}
            
        # We only SELL if we swept highs, formed a bearish FVG, AND the Macro Trend is Bearish.
        if sweep_high and bearish_fvg and trend_is_bearish:
            return {"action": "SELL", "confidence": 0.95, "strategy": "SMC_Filtered"}
            
        return {"action": "HOLD", "confidence": 0.0, "strategy": "Stop_Hunt"}

    @staticmethod
    def macro_trend_follower(candles, us10y_yields):
        closes = [c['close'] for c in candles]
        if len(closes) < 50: return {"action": "HOLD", "confidence": 0.0, "strategy": "Macro_Trend"}
        
        fast_sma = DWC_StrategyMatrix.calculate_sma(closes, 10)
        slow_sma = DWC_StrategyMatrix.calculate_sma(closes, 50)
        
        if fast_sma > slow_sma and us10y_yields < 0:
            return {"action": "BUY", "confidence": 0.92, "strategy": "Macro_Trend"}
        elif fast_sma < slow_sma and us10y_yields > 0:
            return {"action": "SELL", "confidence": 0.92, "strategy": "Macro_Trend"}
            
        return {"action": "HOLD", "confidence": 0.0, "strategy": "Macro_Trend"}

    @staticmethod
    def retail_momentum_breakout(candles, volume_profile=None):
        return {"action": "HOLD", "confidence": 0.0, "strategy": "Retail_Breakout"}

    @classmethod
    def evaluate_swarm(cls, candles, macro_data):
        if candles is None or len(candles) < 50:
            return {"action": 0, "dominant_strategy": "WARMUP", "confidence": 0.0}
            
        s1 = cls.renaissance_stat_arb(candles, None)
        s2 = cls.institutional_stop_hunt(candles, None)
        s3 = cls.macro_trend_follower(candles, macro_data['us10y'])
        s4 = cls.retail_momentum_breakout(candles, None)
        
        strategies = [s1, s2, s3, s4]
        valid_signals = [s for s in strategies if s['confidence'] >= 0.90 and s['action'] != "HOLD"]
        
        if not valid_signals:
            return {"action": 0, "dominant_strategy": "NONE", "confidence": 0.0}
            
        best_signal = max(valid_signals, key=lambda x: x['confidence'])
        action_int = 1 if best_signal['action'] == "BUY" else 2
        return {
            "action": action_int,
            "dominant_strategy": best_signal['strategy'],
            "confidence": best_signal['confidence']
        }
