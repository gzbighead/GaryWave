#!/usr/bin/env python3
"""
GWAVE 引擎 - 双周期(日线+周线)共振扫描
负责：拉取日线/周线数据 -> 计算TNUM -> 判断共振 -> 返回结果列表

信号定义：日线TNUM=1 且 周线TNUM=1 (双周期同时刚金叉)

数据时点说明：
  - 本引擎设计为"收盘前约30分钟"运行，此时yfinance返回的最新一根K线
    (无论日线还是周线)是"接近完成但未必100%最终"的状态。
  - 这是有意为之的权衡：牺牲一点点理论确定性，换取在收盘前仍有交易执行窗口。
  - 若想要100%确定性版本，只需在收盘后再跑一次即可，计算逻辑完全相同。
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gwave")

# ─── 参数 ──────────────────────────────────────────────────────────────────
HISTORY_PERIOD_DAILY  = "1y"   # 日线拉取长度
HISTORY_PERIOD_WEEKLY = "1y"   # 周线拉取长度 (约52根周K，足够EMA(4)*3层稳定)
MIN_BARS_REQUIRED     = 30     # 单周期最少需要多少根K线才能可靠计算(三层EMA4+缓冲)
MAX_RETRIES           = 1      # 单只股票数据拉取重试次数 (0=不重试，1=失败后再试一次)
RETRY_SLEEP_SEC       = 1.5

TARGET_TNUM = 1  # 只关心金叉信号(TNUM=1)，死叉(TNUM=-1)本系统不处理


# ─── TDX 公式核心 (与tnum_core.py一致，内嵌避免额外文件依赖) ────────────────
def _tdx_ema(series: pd.Series, n: int) -> pd.Series:
    alpha = 2.0 / (n + 1)
    return series.ewm(alpha=alpha, adjust=False).mean()


def _tdx_ma(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(window=n, min_periods=n).mean()


def _tdx_cross(a: pd.Series, b: pd.Series) -> pd.Series:
    a_prev = a.shift(1)
    b_prev = b.shift(1)
    return (a >= b) & (a_prev < b_prev)


def _tdx_barslast(cond: pd.Series) -> pd.Series:
    n = len(cond)
    out = np.full(n, np.nan)
    last_true_idx = None
    cond_vals = cond.values
    for i in range(n):
        if bool(cond_vals[i]):
            last_true_idx = i
        if last_true_idx is not None:
            out[i] = i - last_true_idx
    return pd.Series(out, index=cond.index)


def calc_tnum(df: pd.DataFrame) -> pd.DataFrame:
    """
    输入: df 包含 Close, High, Low 列(按时间升序)
    输出: 附加 J, D, K, TNUM 列的新df
    """
    out = df.copy()
    var1 = (2 * out["Close"] + out["High"] + out["Low"]) / 4.0
    var2 = _tdx_ema(_tdx_ema(_tdx_ema(var1, 4), 4), 4)
    var2_ref1 = var2.shift(1)
    j = (var2 - var2_ref1) / var2_ref1 * 100.0

    d = _tdx_ma(j, 1)
    k = _tdx_ma(j, 3)

    tu = _tdx_cross(d, k)
    td = _tdx_cross(k, d)

    bars_tu = _tdx_barslast(tu)
    bars_td = _tdx_barslast(td)

    d_gt_k = d > k
    tnum = np.where(d_gt_k, bars_tu + 1, (bars_td + 1) * -1)
    tnum = pd.Series(tnum, index=out.index)
    tnum[d_gt_k & bars_tu.isna()] = np.nan
    tnum[(~d_gt_k) & bars_td.isna()] = np.nan

    out["J"] = j
    out["D"] = d
    out["K"] = k
    out["TNUM"] = tnum
    return out


# ─── 数据拉取 ──────────────────────────────────────────────────────────────
def _fetch_with_retry(symbol: str, interval: str, period: str) -> Optional[pd.DataFrame]:
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            df = yf.Ticker(symbol).history(period=period, interval=interval)
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
                time.sleep(RETRY_SLEEP_SEC)
    logger.warning(f"{symbol} [{interval}] 拉取失败: {last_err}")
    return None


def fetch_daily(symbol: str) -> Optional[pd.DataFrame]:
    return _fetch_with_retry(symbol, "1d", HISTORY_PERIOD_DAILY)


def fetch_weekly(symbol: str) -> Optional[pd.DataFrame]:
    """
    直接用yfinance的周线interval拉取，而不是用日线resample，
    避免本周未完成这一周的resample边界处理出现偏差。
    yfinance "1wk" 的最新一根，对应的就是"本周至今"的进行中K线，
    这正是我们想要的(收盘前/收盘后均可直接使用)。
    """
    return _fetch_with_retry(symbol, "1wk", HISTORY_PERIOD_WEEKLY)


# ─── 单标的扫描结果 ────────────────────────────────────────────────────────
@dataclass
class ScanResult:
    symbol: str
    name: str
    ok: bool = False
    error: Optional[str] = None
    daily_tnum: Optional[float] = None
    weekly_tnum: Optional[float] = None
    last_close: Optional[float] = None
    last_daily_date: Optional[str] = None
    last_weekly_date: Optional[str] = None
    is_resonance: bool = False


def scan_symbol(symbol: str, name: str) -> ScanResult:
    """对单只股票执行完整流程：拉日线 -> 拉周线 -> 算TNUM -> 判断共振"""
    daily_df = fetch_daily(symbol)
    if daily_df is None or len(daily_df) < MIN_BARS_REQUIRED:
        return ScanResult(symbol=symbol, name=name, ok=False,
                           error="日线数据不足或拉取失败")

    weekly_df = fetch_weekly(symbol)
    if weekly_df is None or len(weekly_df) < MIN_BARS_REQUIRED:
        return ScanResult(symbol=symbol, name=name, ok=False,
                           error="周线数据不足或拉取失败")

    try:
        daily_calc = calc_tnum(daily_df)
        weekly_calc = calc_tnum(weekly_df)
    except Exception as e:  # noqa: BLE001
        return ScanResult(symbol=symbol, name=name, ok=False,
                           error=f"计算异常: {e}")

    daily_last = daily_calc.iloc[-1]
    weekly_last = weekly_calc.iloc[-1]

    d_tnum = daily_last["TNUM"]
    w_tnum = weekly_last["TNUM"]

    d_tnum_val = float(d_tnum) if pd.notna(d_tnum) else None
    w_tnum_val = float(w_tnum) if pd.notna(w_tnum) else None

    is_resonance = (
        d_tnum_val is not None and w_tnum_val is not None
        and d_tnum_val == TARGET_TNUM and w_tnum_val == TARGET_TNUM
    )

    last_daily_date = daily_calc.index[-1]
    last_weekly_date = weekly_calc.index[-1]

    return ScanResult(
        symbol=symbol,
        name=name,
        ok=True,
        daily_tnum=d_tnum_val,
        weekly_tnum=w_tnum_val,
        last_close=round(float(daily_last["Close"]), 3),
        last_daily_date=last_daily_date.strftime("%Y-%m-%d"),
        last_weekly_date=last_weekly_date.strftime("%Y-%m-%d"),
        is_resonance=is_resonance,
    )


def scan_watchlist(watchlist: list[tuple[str, str]]) -> list[ScanResult]:
    """
    批量扫描整个watchlist。
    watchlist: [("NVDA","英伟达"), ...] 形式，与现有watchlist_us.py格式一致。
    返回所有结果(包括失败的)，由上层(report)决定如何呈现。
    """
    results: list[ScanResult] = []
    total = len(watchlist)
    for idx, (symbol, name) in enumerate(watchlist, start=1):
        logger.info(f"[{idx}/{total}] 扫描 {symbol} ({name})")
        res = scan_symbol(symbol, name)
        if not res.ok:
            logger.warning(f"  -> 跳过 {symbol}: {res.error}")
        elif res.is_resonance:
            logger.info(f"  -> ✓ 共振信号! 日TNUM={res.daily_tnum} 周TNUM={res.weekly_tnum}")
        results.append(res)
    return results


def get_resonance_list(results: list[ScanResult]) -> list[ScanResult]:
    return [r for r in results if r.ok and r.is_resonance]


def get_failed_list(results: list[ScanResult]) -> list[ScanResult]:
    return [r for r in results if not r.ok]


if __name__ == "__main__":
    # 简单自测：用几个常见标的跑一遍流程(需要可访问yahoo finance的网络环境)
    test_watchlist = [("NVDA", "英伟达"), ("PLTR", "Palantir"), ("AAPL", "苹果")]
    results = scan_watchlist(test_watchlist)
    for r in results:
        print(r)
    print("\n共振信号:", [r.symbol for r in get_resonance_list(results)])
    print("失败:", [(r.symbol, r.error) for r in get_failed_list(results)])
