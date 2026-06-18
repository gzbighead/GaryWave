#!/usr/bin/env python3
"""
GWAVE 报告生成 + 邮件发送
负责：调用engine_gwave扫描watchlist -> 组装HTML邮件 -> 通过Resend发送

环境变量:
  RESEND_API_KEY  - Resend API Key (必需，存于GitHub Secrets)

发件/收件地址直接写在本文件中(非敏感信息，与RESEND_API_KEY区分对待)。
"""

import sys
import os
import datetime
import logging

import requests

from engine_gwave import scan_watchlist, get_resonance_list, get_failed_list
from watchlist_us import WATCHLIST_US

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gwave_report")

RESEND_API_URL = "https://api.resend.com/emails"

EMAIL_TO   = ["garyfocus@hotmail.com"]
EMAIL_FROM = "美股波动选股 <messenger@ceic.ca>"


def build_html(resonance_list, failed_list, total_count, scan_time_str) -> str:
    """组装HTML邮件正文，手机端友好的表格样式"""

    style = """
    <style>
        body { font-family: -apple-system, "Microsoft YaHei", sans-serif; background:#f5f5f7; margin:0; padding:16px; }
        .container { max-width:600px; margin:0 auto; background:#fff; border-radius:10px; overflow:hidden; }
        .header { background:#1a3c6e; color:#fff; padding:16px; }
        .header h2 { margin:0; font-size:18px; }
        .header p { margin:4px 0 0; font-size:12px; opacity:0.85; }
        .body { padding:16px; }
        table { width:100%; border-collapse:collapse; font-size:14px; }
        th { background:#eef2f8; text-align:left; padding:8px 6px; font-size:12px; color:#555; }
        td { padding:8px 6px; border-bottom:1px solid #eee; }
        .symbol { font-weight:600; color:#1a3c6e; }
        .tnum-tag { display:inline-block; background:#1a9e5c; color:#fff; border-radius:4px; padding:2px 6px; font-size:12px; }
        .empty { color:#888; font-size:14px; padding:24px 0; text-align:center; }
        .footer { padding:12px 16px; font-size:11px; color:#999; border-top:1px solid #eee; }
        .stat { font-size:13px; color:#666; margin-top:4px; }
    </style>
    """

    rows = ""
    if resonance_list:
        for r in resonance_list:
            rows += f"""
            <tr>
                <td class="symbol">{r.symbol}</td>
                <td>{r.name}</td>
                <td>{r.last_close}</td>
                <td><span class="tnum-tag">命中</span></td>
            </tr>"""
        body_content = f"""
        <table>
            <tr><th>代码</th><th>名称</th><th>最新价</th><th>波动状态</th></tr>
            {rows}
        </table>
        """
    else:
        body_content = '<div class="empty">本轮扫描无波动信号股票</div>'

    failed_note = ""
    if failed_list:
        failed_note = f'<div class="stat">本轮 {len(failed_list)} 只标的数据拉取失败，已跳过</div>'

    html = f"""
    <html>
    <head><meta charset="utf-8">{style}</head>
    <body>
        <div class="container">
            <div class="header">
                <h2>美股波动选股</h2>
                <p>{scan_time_str}　|　共扫描 {total_count} 只标的，命中 {len(resonance_list)} 只</p>
            </div>
            <div class="body">
                {body_content}
                {failed_note}
            </div>
        </div>
    </body>
    </html>
    """
    return html


def send_email(html: str, resonance_count: int) -> bool:
    resend_api_key = os.environ.get("RESEND_API_KEY")

    if not resend_api_key:
        logger.error("缺少必需的环境变量 RESEND_API_KEY，无法发送邮件")
        return False

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    subject = f"美股波动选股 {today_str}　命中{resonance_count}只" if resonance_count > 0 \
        else f"美股波动选股 {today_str}　无符合条件个股"

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
    logger.info(f"开始扫描，共 {len(WATCHLIST_US)} 只标的")

    results = scan_watchlist(WATCHLIST_US)
    resonance_list = get_resonance_list(results)
    failed_list = get_failed_list(results)

    logger.info(f"扫描完成: 共振 {len(resonance_list)} 只，失败 {len(failed_list)} 只")

    html = build_html(resonance_list, failed_list, len(WATCHLIST_US), scan_time_str)
    ok = send_email(html, len(resonance_list))

    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
