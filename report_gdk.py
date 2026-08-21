#!/usr/bin/env python3
"""
GDK 报告生成 + 邮件发送（调试版：显示所有标的的幅度值）
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


def build_html(all_results, signal_list, failed_list, total_count, scan_time_str) -> str:
    style = """
    <style>
        body { font-family: -apple-system, "Microsoft YaHei", sans-serif; background:#f5f5f7; margin:0; padding:16px; }
        .container { max-width:600px; margin:0 auto; background:#fff; border-radius:10px; overflow:hidden; }
        .header { background:#8b3a0f; color:#fff; padding:16px; }
        .header h2 { margin:0; font-size:18px; }
        .header p { margin:4px 0 0; font-size:12px; opacity:0.85; }
        .body { padding:16px; }
        table { width:100%; border-collapse:collapse; font-size:13px; }
        th { background:#fdf0ea; text-align:left; padding:6px 4px; font-size:12px; color:#555; }
        td { padding:6px 4px; border-bottom:1px solid #eee; }
        .symbol { font-weight:600; color:#8b3a0f; }
        .signal-row { background:#fff8f5; }
        .signal-tag { display:inline-block; background:#e05c1a; color:#fff; border-radius:4px; padding:1px 6px; font-size:11px; }
        .amp-val { font-family: monospace; }
        .footer { padding:12px 16px; font-size:11px; color:#999; border-top:1px solid #eee; }
        .stat { font-size:13px; color:#666; margin-top:8px; }
    </style>
    """

    rows = ""
    ok_results = [r for r in all_results if r.ok]
    # 按幅度升序排列，方便查看分布
    ok_results.sort(key=lambda r: r.last_amplitude if r.last_amplitude is not None else 9999)

    for r in ok_results:
        amp_str = f"{r.last_amplitude:.4f}%" if r.last_amplitude is not None else "N/A"
        if r.is_signal:
            rows += f"""
            <tr class="signal-row">
                <td class="symbol">{r.symbol}</td>
                <td>{r.name}</td>
                <td>{r.last_close}</td>
                <td class="amp-val">{amp_str}</td>
                <td><span class="signal-tag">启动</span></td>
            </tr>"""
        else:
            rows += f"""
            <tr>
                <td class="symbol">{r.symbol}</td>
                <td>{r.name}</td>
                <td>{r.last_close}</td>
                <td class="amp-val">{amp_str}</td>
                <td></td>
            </tr>"""

    body_content = f"""
    <table>
        <tr><th>代码</th><th>名称</th><th>最新价</th><th>幅度</th><th>信号</th></tr>
        {rows}
    </table>
    """

    failed_note = ""
    if failed_list:
        failed_note = f'<div class="stat">本轮 {len(failed_list)} 只标的数据拉取失败，已跳过</div>'

    html = f"""
    <html>
    <head><meta charset="utf-8">{style}</head>
    <body>
        <div class="container">
            <div class="header">
                <h2>GDK A股启动选股（调试版）</h2>
                <p>{scan_time_str}　|　共扫描 {total_count} 只，命中 {len(signal_list)} 只</p>
            </div>
            <div class="body">
                {body_content}
                {failed_note}
            </div>
            <div class="footer">
                幅度 = (EMA8 - EMA(EMA8,20)) / EMA(EMA8,20) × 100%，按幅度升序排列<br>
                信号条件：0% &lt; 幅度 &lt; 1% 且 过去60天超50天压制 且 幅度扩大
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
    subject = f"GDK启动选股(调试) {today_str}　命中{signal_count}只" if signal_count > 0 \
        else f"GDK启动选股(调试) {today_str}　无信号"

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

    results = scan_watchlist(WATCHLIST_A)
    signal_list = get_signal_list(results)
    failed_list = get_failed_list(results)

    logger.info(f"扫描完成: 命中 {len(signal_list)} 只，失败 {len(failed_list)} 只")

    html = build_html(results, signal_list, failed_list, len(WATCHLIST_A), scan_time_str)
    ok = send_email(html, len(signal_list))

    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
