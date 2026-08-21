#!/usr/bin/env python3
"""
GDK 引擎 - A股/美股启动信号扫描

通达信公式:
  H1 := EMA(CLOSE, 8)
  H2 := EMA(H1, 20)
  幅度 := (H1 - H2) / H2 * 100
  GDK := 幅度 > 0 AND 幅度 < 1 AND COUNT(幅度 < 0, 60) > 50 AND 幅度 > 昨日幅度

实现说明：
  拉取2年数据，前1年作为EMA预热期（让H2充分收敛），
  后1年用于实际信号判断，只取最后一根K线的GDK值。
  这样既避免ETF成立年限不足5年导致数据拉取失败，
  又让H2有足够的历史建立正确的基准水平。
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
HISTORY_PERIOD  = "2y"    # 拉2年，前1年预热H2，后1年用于信号判断
MIN_BARS        = 160     # 2年约500根，至少要有160根（约8个月）才够用
MAX_RETRIES     = 1
RETRY_SLEEP     = 1.5

COUNT_PERIOD    = 60
COUNT_THRESHOLD = 50
RANGE_UPPER     = 1.0
RANGE_LOWER     = 0.0


# ─── TDX EMA（初始值用前N期SMA，与通达信对齐）────────────────────────────
def _tdx_ema(series: pd.Series, n: int) -> pd.Series:
    values = series.values.astype(float)
    length = len(values)
    result = np.full(length, np.nan)

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
    if df is None or df.empty:
        return GDKResult(symbol=symbol, name=name, ok=False,
                         error="数据拉取失败")

    # 数据不足时降级用全部可用数据（兼容成立时间较短的ETF）
    if len(df) < MIN_BARS:
        if len(df) < 80:
            return GDKResult(symbol=symbol, name=name, ok=False,
                             error=f"数据不足({len(df)}根)")
        # 数据在80~160之间，降级使用
        logger.debug(f"{symbol} 数据仅{len(df)}根，降级计算")

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
