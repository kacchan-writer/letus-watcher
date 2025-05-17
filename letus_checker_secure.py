#!/usr/bin/env python3
"""
LETUS Assignment Checker — Secure Edition
========================================

*   Prompts once for credentials if they are not in the environment and stores them **encrypted**
    with the OS key‑ring (via `keyring` package).
*   Offers an **opt‑in interactive** mode (`--configure`) where you enter username, password and
    LINE token; thereafter runs fully unattended.
*   Uses **async Playwright** for faster page fetches and cleaner shutdown.
*   Built‑in **`--watch`** flag starts an infinite loop that polls LETUS every *n* minutes (default
    60) — replaces the need for cron if you prefer a single long‑running process.

Dependencies
------------
```bash
pip install playwright asyncio‑run‑in‑process keyring python‑dotenv rich requests
playwright install chromium
```

Quick start
-----------
```bash
# first‑time setup – store creds in keyring and test a 24 h window
python letus_checker_secure.py --configure --due-within 24

# thereafter – just run it
python letus_checker_secure.py --due-within 24 --quiet

# GUI‑less daemon that checks every 30 min
python letus_checker_secure.py --watch 30 --due-within 6
```

NOTE ✱ Never commit your credentials; this script uses the OS credential vault (macOS Keychain,
Windows Credential Manager, or Secret Service on Linux) so they stay off‑disk.  You may still set
`LINE_NOTIFY_TOKEN` in `.env` or during `--configure`.
"""
from __future__ import annotations
import argparse, asyncio, datetime as dt, os, re, textwrap
from pathlib import Path
from typing import List, Optional
from zoneinfo import ZoneInfo
import keyring, requests
from dotenv import load_dotenv
from rich import print
from rich.console import Console
from rich.table import Table
from playwright.async_api import async_playwright, BrowserContext

SERVICE = "LETUS_CHECKER"
JST = ZoneInfo("Asia/Tokyo")
DASHBOARD_URL = "https://letus.ed.tus.ac.jp/my/"

console = Console()

# --------------------------- Helpers -----------------------------------------------------------

def save_secret(key: str, value: str):
    keyring.set_password(SERVICE, key, value)


def get_secret(key: str) -> Optional[str]:
    return keyring.get_password(SERVICE, key)


def parse_due_date(text: str) -> Optional[dt.datetime]:
    jp = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})", text)
    if jp:
        y, m, d, hh, mm = map(int, jp.groups())
        return dt.datetime(y, m, d, hh, mm, tzinfo=JST)
    en = re.search(r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4}).*?(\d{1,2}):(\d{2})\s*(AM|PM)", text, re.I)
    if en:
        d, mon, y, hh, mm, ampm = en.groups()
        month_idx = dt.datetime.strptime(mon[:3], "%b").month
        hh = int(hh) % 12 + (12 if ampm.lower() == "pm" else 0)
        return dt.datetime(int(y), month_idx, int(d), hh, int(mm), tzinfo=JST)
    return None


def notify(alerts: List[dict]):
    token = os.getenv("LINE_NOTIFY_TOKEN") or get_secret("LINE_TOKEN")
    messages = [f"\u26A0 LETUS: 未提出課題 {len(alerts)} 件\n"]
    now = dt.datetime.now(JST)
    for t in alerts:
        hrs = int((t["due"] - now).total_seconds() // 3600)
        messages.append(f"• {t['label']} (あと {hrs}h)")
    msg = "\n".join(messages)

    if token:
        resp = requests.post("https://notify-api.line.me/api/notify",
                             headers={"Authorization": f"Bearer {token}"},
                             data={"message": msg})
        if resp.status_code != 200:
            console.print(f"[bold red]LINE Notify failed:[/bold red] {resp.text}")
    else:
        console.print(msg)

# --------------------------- Core --------------------------------------------------------------

class LetusChecker:
    def __init__(self, context: BrowserContext):
        self.ctx = context

    async def login(self):
        page = await self.ctx.new_page()
        await page.goto(DASHBOARD_URL)
        if await page.locator('[data-region="timeline"]').count():
            return page  # cached session

        await page.locator("text=Log in").first.click()
        await page.wait_for_load_state("networkidle")
        u = get_secret("USERNAME")
        p = get_secret("PASSWORD")
        if not u or not p:
            raise RuntimeError("Credentials not stored; run with --configure first.")
        await page.fill('input[name="j_username"], input[name="username"]', u)
        await page.fill('input[name="j_password"], input[name="password"]', p)
        await page.keyboard.press("Enter")
        await page.wait_for_load_state("networkidle")
        if "ログインエラー" in await page.content():
            raise RuntimeError("Login failed – check credentials/MFA.")
        return page

    async def fetch_upcoming(self, page) -> List[dict]:
        await page.goto(DASHBOARD_URL)
        await page.wait_for_selector('[data-region="timeline"]')
        items = []
        for itm in await page.locator('[data-region="timeline-item"]').all():
            label = (await itm.inner_text()).strip()
            link = await itm.locator('a').get_attribute('href')
            due = parse_due_date(label)
            items.append({"label": label, "link": link, "due": due})
        return items

    async def is_submitted(self, page, link: str) -> bool:
        await page.goto(link)
        await page.wait_for_load_state("domcontentloaded")
        html = await page.content()
        return ("提出済" in html) or ("Submitted for grading" in html)

    async def run(self, due_within_h: int) -> int:
        page = await self.login()
        upcoming = await self.fetch_upcoming(page)
        now = dt.datetime.now(JST)
        threshold = now + dt.timedelta(hours=due_within_h)
        alerts: List[dict] = []
        for task in upcoming:
            if task["due"] and task["due"] <= threshold:
                if not await self.is_submitted(page, task["link"]):
                    alerts.append(task)
        if alerts:
            notify(alerts)
        return len(alerts)

# --------------------------- CLI ---------------------------------------------------------------

def configure():
    console.print("[bold]LETUS Checker: 初期設定[/bold]")
    u = input("学籍番号 (LETUS_USERNAME):")
    p = input("パスワード (非表示ではありませんので注意): ")
    token = input("LINE Notify トークン (任意): ")
    save_secret("USERNAME", u)
    save_secret("PASSWORD", p)
    if token:
        save_secret("LINE_TOKEN", token)
    console.print("[green]保存しました。[/green]")

async def main_async(args):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        checker = LetusChecker(context)
        if args.watch:
            interval = args.watch * 60
            console.print(f"Watching LETUS every {args.watch} min… (Ctrl+C で停止)")
            try:
                while True:
                    count = await checker.run(args.due_within)
                    if not args.quiet and count == 0:
                        console.print("[dim]No deadlines soon.[/dim]")
                    await asyncio.sleep(interval)
            except KeyboardInterrupt:
                console.print("Stopped.")
        else:
            await checker.run(args.due_within)
        await browser.close()

# --------------------------- Entry -------------------------------------------------------------

def build_parser():
    ap = argparse.ArgumentParser(description="Secure LETUS assignment watcher")
    ap.add_argument("--configure", action="store_true", help="Store credentials in keyring and exit")
    ap.add_argument("--due-within", type=int, default=48, help="Deadline window in hours")
    ap.add_argument("--watch", type=int, metavar="MIN", help="Continuous mode: check every MIN minutes")
    ap.add_argument("--quiet", action="store_true", help="Suppress output when no alerts")
    return ap

if __name__ == "__main__":
    load_dotenv()
    args = build_parser().parse_args()
    if args.configure:
        configure()
        raise SystemExit(0)
    asyncio.run(main_async(args))
