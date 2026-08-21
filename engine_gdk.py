#!/usr/bin/env python3
"""
GDK 引擎 - A股/美股启动信号扫描

通达信公式:
  H1 := EMA(CLOSE, 8)
  H2 := EMA(H1, 20)
  幅度 := (H1 - H2) / H2 * 100
  GDK := 幅度 > 0 AND 幅度 < 1 AND COUNT(幅度 < 0, 60) > 50 AND 幅度 > 昨日幅度

通达信EMA实现细节：
  EMA(X, N) 的初始值 = 前N期的简单平均(SMA)，之后每期用
  EMA = (2*X + (N-1)*EMA_prev) / (N+1) 递推。
  这与pandas ewm(adjust=False)的"第一个点直接作为初始值"不同，
  必须手动实现才能与通达信结果对齐。
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gdk")

# ─── 参数 ──────────────────────────────────────────────────────────────────
HISTORY_PERIOD  = "5y"
MIN_BARS        = 80
MAX_RETRIES     = 1
RETRY_SLEEP     = 1.5

COUNT_PERIOD    = 60
COUNT_THRESHOLD = 50
RANGE_UPPER     = 1.0
RANGE_LOWER     = 0.0


# ─── TDX EMA（初始值用前N期SMA，与通达信对齐）────────────────────────────
def _tdx_ema(series: pd.Series, n: int) -> pd.Series:
    """
    通达信EMA实现：
    - 前N-1期：NaN（数据不足）
    - 第N期起始值：前N期的简单平均
    - 之后每期：(2*X + (N-1)*EMA_prev) / (N+1)
    """
    values = series.values.astype(float)
    length = len(values)
    result = np.full(length, np.nan)

    # 找到第一个有效的起始点（前N期需要都是有效数字）
    start = n - 1
    while start < length:
        window = values[start - n + 1: start + 1]
        if not np.any(np.isnan(window)):
            result[start] = np.mean(window)
            break
        start += 1

    if start >= length:
        return pd.Series(result, index=series.index)

    k = 2.0 / (n + 1)
    for i in range(start + 1, length):
        if np.isnan(values[i]):
            result[i] = np.nan
        else:
            result[i] = values[i] * k + result[i - 1] * (1 - k)

    return pd.Series(result, index=series.index)


# ─── GDK核心计算 ──────────────────────────────────────────────────────────
def calc_gdk(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    h1 = _tdx_ema(out["Close"], 8)
    h2 = _tdx_ema(h1, 20)
    amplitude = (h1 - h2) / h2 * 100.0

    below_zero = (amplitude < 0).astype(int)
    count_below = below_zero.rolling(window=COUNT_PERIOD, min_periods=COUNT_PERIOD).sum()

    amplitude_expanding = amplitude > amplitude.shift(1)

    gdk = (
        (amplitude > RANGE_LOWER) &
        (amplitude < RANGE_UPPER) &
        (count_below > COUNT_THRESHOLD) &
        amplitude_expanding
    )

    out["H1"]  = h1
    out["H2"]  = h2
    out["幅度"] = amplitude
    out["GDK"] = gdk
    return out


# ─── 数据拉取 ──────────────────────────────────────────────────────────────
def _fetch_with_retry(symbol: str) -> Optional[pd.DataFrame]:
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            df = yf.Ticker(symbol).history(period=HISTORY_PERIOD, interval="1d")
            if df is None or df.empty:
                last_err = "empty dataframe"
                continue
            for col in ["Open", "High", "Low", "Close", "Volume"]:
                if col in df.columns:
                    df[col] = df[col].astype(float)
            return df
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_SLEEP)
    logger.warning(f"{symbol} 拉取失败: {last_err}")
    return None


# ─── 单标的扫描结果 ────────────────────────────────────────────────────────
@dataclass
class GDKResult:
    symbol: str
    name: str
    ok: bool = False
    error: Optional[str] = None
    is_signal: bool = False
    last_close: Optional[float] = None
    last_amplitude: Optional[float] = None
    last_date: Optional[str] = None


def scan_symbol(symbol: str, name: str) -> GDKResult:
    df = _fetch_with_retry(symbol)
    if df is None or len(df) < MIN_BARS:
        return GDKResult(symbol=symbol, name=name, ok=False,
                         error="数据不足或拉取失败")
    try:
        result = calc_gdk(df)
    except Exception as e:  # noqa: BLE001
        return GDKResult(symbol=symbol, name=name, ok=False,
                         error=f"计算异常: {e}")

    last = result.iloc[-1]
    gdk_val = last["GDK"]
    is_signal = bool(gdk_val) if pd.notna(gdk_val) else False

    return GDKResult(
        symbol=symbol,
        name=name,
        ok=True,
        is_signal=is_signal,
        last_close=round(float(last["Close"]), 3),
        last_amplitude=round(float(last["幅度"]), 4) if pd.notna(last["幅度"]) else None,
        last_date=result.index[-1].strftime("%Y-%m-%d"),
    )


def scan_watchlist(watchlist: list[tuple[str, str]]) -> list[GDKResult]:
    results: list[GDKResult] = []
    total = len(watchlist)
    for idx, (symbol, name) in enumerate(watchlist, start=1):
        logger.info(f"[{idx}/{total}] 扫描 {symbol} ({name})")
        res = scan_symbol(symbol, name)
        if not res.ok:
            logger.warning(f"  -> 跳过 {symbol}: {res.error}")
        elif res.is_signal:
            logger.info(f"  -> ✓ GDK启动信号! 幅度={res.last_amplitude:.4f}%")
        results.append(res)
    return results


def get_signal_list(results: list[GDKResult]) -> list[GDKResult]:
    return [r for r in results if r.ok and r.is_signal]


def get_failed_list(results: list[GDKResult]) -> list[GDKResult]:
    return [r for r in results if not r.ok]
