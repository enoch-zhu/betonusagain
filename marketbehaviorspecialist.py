"""
This module analyzes OHLCV market history and returns a MarketSignal
that matches the shared swarm schema.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Dict, Optional
from schemas import MarketSignal


class MarketBehaviorSubagent:
    """
    Produces a MarketSignal aligned to scheme.py:

    MarketSignal(
        trend: float,        # -1.0 to 1.0
        volatility: float,   # 0.0 to 1.0
        momentum: float,     # -1.0 to 1.0
        summary: str,
        confidence: float    # 0.0 to 1.0
    )

    Input DataFrame schema:
        date, open, high, low, close, volume

    Optional benchmark schema:
        date, open, high, low, close, volume

    Notes:
    - trend is directional market structure / trend strength
    - volatility is normalized magnitude (higher = less calm)
    - momentum is directional short/medium-horizon momentum
    - confidence is the agent's confidence in its own market-only read
    """

    def __init__(self) -> None:
        pass

    # ============================================================
    # Public API
    # ============================================================

    def run(
        self,
        price_history: pd.DataFrame,
        benchmark_history: Optional[pd.DataFrame] = None,
        time_horizon: str = "1 week",
        ticker: Optional[str] = None,
    ) -> MarketSignal:
        """
        Main entrypoint.

        Parameters
        ----------
        price_history : pd.DataFrame
            Asset OHLCV history with columns:
            date, open, high, low, close, volume
        benchmark_history : Optional[pd.DataFrame]
            Optional benchmark OHLCV history with same schema
        time_horizon : str
            Examples:
            "1 week", "1 month"
        ticker : Optional[str]
            For summary generation only

        Returns
        -------
        MarketSignal
            Shared schema object from scheme.py
        """
        df = self._prepare_price_history(price_history)
        benchmark_df = (
            self._prepare_price_history(benchmark_history)
            if benchmark_history is not None
            else None
        )

        features = self._compute_features(df, benchmark_df)
        trend = self._compute_trend(features, time_horizon)
        momentum = self._compute_momentum(features, time_horizon)
        volatility = self._compute_volatility(features)
        confidence = self._compute_confidence(
            trend=trend,
            momentum=momentum,
            volatility=volatility,
            features=features,
        )
        summary = self._build_summary(
            ticker=ticker,
            time_horizon=time_horizon,
            trend=trend,
            momentum=momentum,
            volatility=volatility,
            confidence=confidence,
            features=features,
        )

        return MarketSignal(
            trend=float(self._clip(trend, -1.0, 1.0)),
            volatility=float(self._clip(volatility, 0.0, 1.0)),
            momentum=float(self._clip(momentum, -1.0, 1.0)),
            summary=summary,
            confidence=float(self._clip(confidence, 0.0, 1.0)),
        )

    def run_with_diagnostics(
        self,
        price_history: pd.DataFrame,
        benchmark_history: Optional[pd.DataFrame] = None,
        time_horizon: str = "1 week",
        ticker: Optional[str] = None,
    ) -> dict:
        """
        Convenience wrapper if you want MarketSignal plus supporting details.

        This remains compatible with the shared scheme because the nested
        'market_signal' field is a serialized MarketSignal.
        """
        df = self._prepare_price_history(price_history)
        benchmark_df = (
            self._prepare_price_history(benchmark_history)
            if benchmark_history is not None
            else None
        )

        features = self._compute_features(df, benchmark_df)
        signal = self.run(
            price_history=df,
            benchmark_history=benchmark_df,
            time_horizon=time_horizon,
            ticker=ticker,
        )

        return {
            "market_signal": asdict(signal),
            "features": {k: float(v) for k, v in features.items() if pd.notna(v)},
            "ticker": ticker,
            "time_horizon": time_horizon,
            "latest_observation_date": str(df["date"].iloc[-1].date()),
            "rows_used": int(len(df)),
            "has_benchmark": benchmark_df is not None,
        }

    # ============================================================
    # Data preparation
    # ============================================================

    def _prepare_price_history(self, df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
        if df is None:
            return None

        required_cols = {"date", "open", "high", "low", "close", "volume"}
        missing = required_cols.difference(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")

        out = df.copy()
        out["date"] = pd.to_datetime(out["date"])
        out = out.sort_values("date").drop_duplicates("date").reset_index(drop=True)

        for col in ["open", "high", "low", "close", "volume"]:
            out[col] = pd.to_numeric(out[col], errors="coerce")

        out = out.dropna(subset=["close"]).reset_index(drop=True)

        if len(out) < 80:
            raise ValueError(
                "Need at least 80 rows of price history for stable market-behavior analysis."
            )

        return out

    # ============================================================
    # Feature engineering
    # ============================================================

    def _compute_features(
        self,
        df: pd.DataFrame,
        benchmark_df: Optional[pd.DataFrame],
    ) -> Dict[str, float]:
        close = df["close"]
        volume = df["volume"]
        returns = close.pct_change()

        ma20 = close.rolling(20).mean()
        ma50 = close.rolling(50).mean()
        ma200 = close.rolling(200).mean()

        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        macd_signal = macd.ewm(span=9, adjust=False).mean()
        macd_hist = macd - macd_signal

        rsi14 = self._rsi(close, 14)
        atr14 = self._atr(df, 14)

        realized_vol_20d = returns.rolling(20).std(ddof=0) * np.sqrt(252)
        realized_vol_60d = returns.rolling(60).std(ddof=0) * np.sqrt(252)

        rolling_peak = close.rolling(252, min_periods=1).max()
        drawdown = close / rolling_peak - 1.0

        rolling_high_252 = close.rolling(252, min_periods=20).max()
        rolling_low_252 = close.rolling(252, min_periods=20).min()

        vol_ma_20 = volume.rolling(20).mean()
        vol_ratio = volume / vol_ma_20

        features: Dict[str, float] = {
            "ret_5d": self._pct_return(close, 5),
            "ret_10d": self._pct_return(close, 10),
            "ret_20d": self._pct_return(close, 20),
            "ret_60d": self._pct_return(close, 60),
            "close_vs_ma20": (
                float(close.iloc[-1] / ma20.iloc[-1] - 1.0)
                if pd.notna(ma20.iloc[-1])
                else np.nan
            ),
            "close_vs_ma50": (
                float(close.iloc[-1] / ma50.iloc[-1] - 1.0)
                if pd.notna(ma50.iloc[-1])
                else np.nan
            ),
            "ma20_vs_ma50": (
                float(ma20.iloc[-1] / ma50.iloc[-1] - 1.0)
                if pd.notna(ma20.iloc[-1]) and pd.notna(ma50.iloc[-1])
                else np.nan
            ),
            "ma50_vs_ma200": (
                float(ma50.iloc[-1] / ma200.iloc[-1] - 1.0)
                if pd.notna(ma50.iloc[-1]) and pd.notna(ma200.iloc[-1])
                else np.nan
            ),
            "macd_hist": float(macd_hist.iloc[-1]) if pd.notna(macd_hist.iloc[-1]) else np.nan,
            "rsi_14": float(rsi14.iloc[-1]) if pd.notna(rsi14.iloc[-1]) else np.nan,
            "atr_pct": (
                float(atr14.iloc[-1] / close.iloc[-1])
                if pd.notna(atr14.iloc[-1])
                else np.nan
            ),
            "realized_vol_20d": (
                float(realized_vol_20d.iloc[-1])
                if pd.notna(realized_vol_20d.iloc[-1])
                else np.nan
            ),
            "realized_vol_60d": (
                float(realized_vol_60d.iloc[-1])
                if pd.notna(realized_vol_60d.iloc[-1])
                else np.nan
            ),
            "drawdown_252": (
                float(drawdown.iloc[-1]) if pd.notna(drawdown.iloc[-1]) else np.nan
            ),
            "distance_to_52w_high": (
                float(close.iloc[-1] / rolling_high_252.iloc[-1] - 1.0)
                if pd.notna(rolling_high_252.iloc[-1])
                else np.nan
            ),
            "distance_to_52w_low": (
                float(close.iloc[-1] / rolling_low_252.iloc[-1] - 1.0)
                if pd.notna(rolling_low_252.iloc[-1])
                else np.nan
            ),
            "vol_ratio": float(vol_ratio.iloc[-1]) if pd.notna(vol_ratio.iloc[-1]) else np.nan,
        }

        vol_z = self._zscore(realized_vol_20d, 60)
        features["vol_z_20d"] = float(vol_z.iloc[-1]) if pd.notna(vol_z.iloc[-1]) else np.nan

        if benchmark_df is not None:
            merged = pd.merge(
                df[["date", "close"]],
                benchmark_df[["date", "close"]],
                on="date",
                how="inner",
                suffixes=("", "_bench"),
            )

            if len(merged) >= 80:
                asset_rets = merged["close"].pct_change()
                bench_rets = merged["close_bench"].pct_change()

                features["relative_strength_5d"] = (
                    float(
                        (merged["close"].iloc[-1] / merged["close"].iloc[-6] - 1.0)
                        - (merged["close_bench"].iloc[-1] / merged["close_bench"].iloc[-6] - 1.0)
                    )
                    if len(merged) > 5
                    else np.nan
                )

                features["relative_strength_20d"] = (
                    float(
                        (merged["close"].iloc[-1] / merged["close"].iloc[-21] - 1.0)
                        - (merged["close_bench"].iloc[-1] / merged["close_bench"].iloc[-21] - 1.0)
                    )
                    if len(merged) > 20
                    else np.nan
                )

                features["beta_60d"] = self._rolling_beta(asset_rets, bench_rets, 60)
            else:
                features["relative_strength_5d"] = np.nan
                features["relative_strength_20d"] = np.nan
                features["beta_60d"] = np.nan
        else:
            features["relative_strength_5d"] = np.nan
            features["relative_strength_20d"] = np.nan
            features["beta_60d"] = np.nan

        return features

    # ============================================================
    # Signal computation aligned to scheme.py
    # ============================================================

    def _compute_trend(self, features: Dict[str, float], time_horizon: str) -> float:
        """
        Returns trend in [-1, 1].

        Uses mostly moving-average structure and medium-horizon return context.
        """
        horizon = time_horizon.lower()

        if "month" in horizon:
            weights = {
                "close_vs_ma50": 0.25,
                "ma20_vs_ma50": 0.20,
                "ma50_vs_ma200": 0.30,
                "ret_20d": 0.15,
                "ret_60d": 0.10,
            }
        else:
            weights = {
                "close_vs_ma20": 0.25,
                "close_vs_ma50": 0.25,
                "ma20_vs_ma50": 0.20,
                "ret_10d": 0.15,
                "ret_20d": 0.15,
            }

        score = 0.0
        for key, weight in weights.items():
            score += weight * self._bounded_scale(
                features.get(key, np.nan),
                denom=self._trend_denom(key),
            )

        return self._clip(score, -1.0, 1.0)

    def _compute_momentum(self, features: Dict[str, float], time_horizon: str) -> float:
        """
        Returns momentum in [-1, 1].

        Uses recent returns, MACD histogram, RSI, and optional relative strength.
        """
        horizon = time_horizon.lower()

        if "month" in horizon:
            ret_a = self._bounded_scale(features.get("ret_20d", np.nan), 0.15)
            ret_b = self._bounded_scale(features.get("ret_60d", np.nan), 0.25)
            rel = self._bounded_scale(features.get("relative_strength_20d", np.nan), 0.12)
            weights = [0.30, 0.20, 0.25, 0.15, 0.10]
        else:
            ret_a = self._bounded_scale(features.get("ret_5d", np.nan), 0.06)
            ret_b = self._bounded_scale(features.get("ret_10d", np.nan), 0.10)
            rel = self._bounded_scale(features.get("relative_strength_5d", np.nan), 0.05)
            weights = [0.30, 0.20, 0.25, 0.15, 0.10]

        parts = [
            ret_a,
            ret_b,
            self._bounded_scale(features.get("macd_hist", np.nan), 1.5),
            self._rsi_to_score(features.get("rsi_14", np.nan)),
            rel,
        ]

        score = sum(
            w * (0.0 if pd.isna(v) else v)
            for w, v in zip(weights, parts)
        )

        return self._clip(score, -1.0, 1.0)

    def _compute_volatility(self, features: Dict[str, float]) -> float:
        """
        Returns volatility in [0, 1].

        Higher means more turbulent / less calm.
        """
        realized = self._unit_scale(features.get("realized_vol_20d", np.nan), 0.12, 0.60)
        atr_pct = self._unit_scale(features.get("atr_pct", np.nan), 0.01, 0.08)
        vol_z = self._unit_scale(features.get("vol_z_20d", np.nan), -1.0, 2.0)

        score = np.nanmean([realized, atr_pct, vol_z])

        if pd.isna(score):
            return 0.5

        return self._clip(float(score), 0.0, 1.0)

    def _compute_confidence(
        self,
        trend: float,
        momentum: float,
        volatility: float,
        features: Dict[str, float],
    ) -> float:
        """
        Confidence in [0, 1].

        Higher when trend and momentum agree and volatility is not extreme.
        """
        agreement = (
            1.0
            if np.sign(trend) == np.sign(momentum)
            and abs(trend) > 0.15
            and abs(momentum) > 0.15
            else 0.0
        )

        directional_strength = (abs(trend) + abs(momentum)) / 2.0

        drawdown_penalty = 0.0
        drawdown = features.get("drawdown_252", np.nan)
        if pd.notna(drawdown) and drawdown < -0.20:
            drawdown_penalty = 0.08

        confidence = (
            0.35
            + 0.25 * agreement
            + 0.30 * directional_strength
            + 0.20 * (1.0 - volatility)
            - drawdown_penalty
        )

        return self._clip(confidence, 0.05, 0.95)

    def _build_summary(
        self,
        ticker: Optional[str],
        time_horizon: str,
        trend: float,
        momentum: float,
        volatility: float,
        confidence: float,
        features: Dict[str, float],
    ) -> str:
        asset = ticker or "The asset"

        trend_text = (
            "uptrend"
            if trend > 0.20
            else "downtrend"
            if trend < -0.20
            else "mixed trend"
        )

        momentum_text = (
            "positive momentum"
            if momentum > 0.20
            else "negative momentum"
            if momentum < -0.20
            else "mixed momentum"
        )

        vol_text = (
            "calm volatility"
            if volatility < 0.35
            else "elevated volatility"
            if volatility < 0.70
            else "high volatility"
        )

        evidence_parts = []

        close_vs_ma50 = features.get("close_vs_ma50", np.nan)
        if pd.notna(close_vs_ma50):
            if close_vs_ma50 > 0:
                evidence_parts.append("price is above the 50-day moving average")
            else:
                evidence_parts.append("price is below the 50-day moving average")

        rsi = features.get("rsi_14", np.nan)
        if pd.notna(rsi):
            if rsi >= 55:
                evidence_parts.append("RSI is constructive")
            elif rsi <= 45:
                evidence_parts.append("RSI is weak")

        rel = features.get("relative_strength_20d", np.nan)
        if pd.notna(rel):
            if rel > 0:
                evidence_parts.append("the asset has outperformed the benchmark recently")
            else:
                evidence_parts.append("the asset has lagged the benchmark recently")

        if not evidence_parts:
            evidence_parts.append(
                "the signal is based on recent price trend, momentum, and realized volatility"
            )

        evidence_text = "; ".join(evidence_parts[:3])

        return (
            f"{asset} over {time_horizon} shows {trend_text}, {momentum_text}, and {vol_text}. "
            f"Confidence is {confidence:.2f}. Key evidence: {evidence_text}."
        )

    # ============================================================
    # Helpers
    # ============================================================

    def _pct_return(self, close: pd.Series, lookback: int) -> float:
        if len(close) <= lookback:
            return np.nan
        return float(close.iloc[-1] / close.iloc[-(lookback + 1)] - 1.0)

    def _trend_denom(self, key: str) -> float:
        mapping = {
            "close_vs_ma20": 0.05,
            "close_vs_ma50": 0.08,
            "ma20_vs_ma50": 0.05,
            "ma50_vs_ma200": 0.08,
            "ret_10d": 0.10,
            "ret_20d": 0.15,
            "ret_60d": 0.25,
        }
        return mapping.get(key, 0.10)

    def _bounded_scale(self, x: float, denom: float) -> float:
        if pd.isna(x):
            return np.nan
        return float(np.tanh(x / max(denom, 1e-9)))

    def _unit_scale(self, x: float, lo: float, hi: float) -> float:
        if pd.isna(x):
            return np.nan
        if hi <= lo:
            return 0.5
        return float(np.clip((x - lo) / (hi - lo), 0.0, 1.0))

    def _clip(self, x: float, lo: float, hi: float) -> float:
        return float(max(lo, min(hi, x)))

    def _zscore(self, series: pd.Series, window: int) -> pd.Series:
        mean = series.rolling(window).mean()
        std = series.rolling(window).std(ddof=0).replace(0, np.nan)
        return (series - mean) / std

    def _rsi(self, close: pd.Series, window: int = 14) -> pd.Series:
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    def _true_range(self, df: pd.DataFrame) -> pd.Series:
        prev_close = df["close"].shift(1)
        tr1 = df["high"] - df["low"]
        tr2 = (df["high"] - prev_close).abs()
        tr3 = (df["low"] - prev_close).abs()
        return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    def _atr(self, df: pd.DataFrame, window: int = 14) -> pd.Series:
        return self._true_range(df).rolling(window).mean()

    def _rsi_to_score(self, rsi: float) -> float:
        if pd.isna(rsi):
            return np.nan
        if rsi < 30:
            return 0.10
        if 30 <= rsi < 45:
            return -0.35
        if 45 <= rsi < 55:
            return 0.05
        if 55 <= rsi < 65:
            return 0.35
        if 65 <= rsi < 75:
            return 0.20
        return -0.10

    def _rolling_beta(
        self,
        asset_rets: pd.Series,
        bench_rets: pd.Series,
        window: int = 60,
    ) -> float:
        aligned = pd.concat([asset_rets, bench_rets], axis=1).dropna()
        aligned.columns = ["asset", "bench"]

        if len(aligned) < window:
            return np.nan

        cov = aligned["asset"].rolling(window).cov(aligned["bench"])
        var = aligned["bench"].rolling(window).var().replace(0, np.nan)
        beta = cov / var

        return float(beta.iloc[-1]) if pd.notna(beta.iloc[-1]) else np.nan


if __name__ == "__main__":
    # Example usage:
    #
    # import pandas as pd
    # from dataclasses import asdict
    #
    # asset_df = pd.read_csv("MSFT.csv")
    # benchmark_df = pd.read_csv("SPY.csv")
    #
    # agent = MarketBehaviorSubagent()
    #
    # signal = agent.run(
    #     price_history=asset_df,
    #     benchmark_history=benchmark_df,
    #     time_horizon="1 week",
    #     ticker="MSFT",
    # )
    #
    # print(asdict(signal))
    #
    # diagnostics = agent.run_with_diagnostics(
    #     price_history=asset_df,
    #     benchmark_history=benchmark_df,
    #     time_horizon="1 week",
    #     ticker="MSFT",
    # )
    #
    # print(diagnostics)
    pass
