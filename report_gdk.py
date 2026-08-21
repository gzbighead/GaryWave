#!/usr/bin/env python3
"""
GDK 报告生成 + 邮件发送
负责：调用engine_gdk扫描watchlist_a -> 组装HTML邮件 -> 通过Resend发送

环境变量:
  RESEND_API_KEY  - Resend API Key (必需，存于GitHub Secrets)
"""

import os
import sys
import datetime
import logging

import requests

from engine_gdk import scan_watchlist, get_signal_list, get_failed_list
from watchlist_a import WATCHLIST_A

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gdk_report")

RESEND_API_URL = "https://api.resend.com/emails"

EMAIL_TO   = ["garyfocus@hotmail.com"]
EMAIL_FROM = "A股启动选股 <messenger@ceic.ca>"


def build_html(signal_list, failed_list, total_count, scan_time_str) -> str:
    style = """
    <style>
        body { font-family: -apple-system, "Microsoft YaHei", sans-serif; background:#f5f5f7; margin:0; padding:16px; }
        .container { max-width:600px; margin:0 auto; background:#fff; border-radius:10px; overflow:hidden; }
        .header { background:#8b3a0f; color:#fff; padding:16px; }
        .header h2 { margin:0; font-size:18px; }
        .header p { margin:4px 0 0; font-size:12px; opacity:0.85; }
        .body { padding:16px; }
        table { width:100%; border-collapse:collapse; font-size:14px; }
        th { background:#fdf0ea; text-align:left; padding:8px 6px; font-size:12px; color:#555; }
        td { padding:8px 6px; border-bottom:1px solid #eee; }
        .symbol { font-weight:600; color:#8b3a0f; }
        .signal-tag { display:inline-block; background:#e05c1a; color:#fff; border-radius:4px; padding:2px 8px; font-size:12px; }
        .empty { color:#888; font-size:14px; padding:24px 0; text-align:center; }
        .footer { padding:12px 16px; font-size:11px; color:#999; border-top:1px solid #eee; }
        .stat { font-size:13px; color:#666; margin-top:4px; }
    </style>
    """

    rows = ""
    if signal_list:
        for r in signal_list:
            rows += f"""
            <tr>
                <td class="symbol">{r.symbol}</td>
                <td>{r.name}</td>
                <td>{r.last_close}</td>
                <td><span class="signal-tag">启动</span></td>
            </tr>"""
        body_content = f"""
        <table>
            <tr><th>代码</th><th>名称</th><th>最新价</th><th>信号</th></tr>
            {rows}
        </table>
        """
    else:
        body_content = '<div class="empty">本轮扫描无启动信号</div>'

    failed_note = ""
    if failed_list:
        failed_note = f'<div class="stat">本轮 {len(failed_list)} 只标的数据拉取失败，已跳过</div>'

    html = f"""
    <html>
    <head><meta charset="utf-8">{style}</head>
    <body>
        <div class="container">
            <div class="header">
                <h2>GDK A股启动选股</h2>
                <p>{scan_time_str}　|　共扫描 {total_count} 只标的，命中 {len(signal_list)} 只</p>
            </div>
            <div class="body">
                {body_content}
                {failed_note}
            </div>
            <div class="footer">
                信号定义：EMA(8)刚突破EMA(EMA(8),20)且幅度&lt;1%，过去60天超过50天处于压制状态
            </div>
        </div>
    </body>
    </html>
    """
    return html


def send_email(html: str, signal_count: int) -> bool:
    resend_api_key = os.environ.get("RESEND_API_KEY")
    if not resend_api_key:
        logger.error("缺少必需的环境变量 RESEND_API_KEY，无法发送邮件")
        return False

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    subject = f"GDK启动选股 {today_str}　命中{signal_count}只" if signal_count > 0 \
        else f"GDK启动选股 {today_str}　无信号"

    payload = {
        "from": EMAIL_FROM,
        "to": EMAIL_TO,
        "subject": subject,
        "html": html,
    }
    headers = {
        "Authorization": f"Bearer {resend_api_key}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(RESEND_API_URL, json=payload, headers=headers, timeout=20)
        if resp.status_code in (200, 201):
            logger.info("邮件发送成功")
            return True
        logger.error(f"邮件发送失败: HTTP {resp.status_code} - {resp.text}")
        return False
    except Exception as e:  # noqa: BLE001
        logger.error(f"邮件发送异常: {e}")
        return False


def main():
    scan_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    logger.info(f"开始GDK扫描，共 {len(WATCHLIST_A)} 只标的")
    # ─── 临时调试：打印159881的H1/H2值 ───────────────────────────────────────
    import yfinance as yf
    from engine_gdk import calc_gdk
    _df = yf.Ticker("159881.SZ").history(period="1y", interval="1d")
    _df["Close"] = _df["Close"].astype(float)
    _r = calc_gdk(_df)
    print("=== 159881调试 ===")
    print(_r[["Close","H1","H2","幅度","GDK"]].tail(5).to_string())
    print("==================")
    # ─── 调试结束 ────────────────────────────────────────────────────────────
    results = scan_watchlist(WATCHLIST_A)
    signal_list = get_signal_list(results)
    failed_list = get_failed_list(results)

    logger.info(f"扫描完成: 命中 {len(signal_list)} 只，失败 {len(failed_list)} 只")

    html = build_html(signal_list, failed_list, len(WATCHLIST_A), scan_time_str)
    ok = send_email(html, len(signal_list))

    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
