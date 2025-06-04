import datetime as dt
from zoneinfo import ZoneInfo
from unittest.mock import AsyncMock
import pytest
import sys
import types
from pathlib import Path
import asyncio

# stub external dependencies so we can import the module without installing them
keyring = types.ModuleType('keyring')
keyring.set_password = lambda *a, **k: None
keyring.get_password = lambda *a, **k: None
sys.modules['keyring'] = keyring

requests = types.ModuleType('requests')
requests.post = lambda *a, **k: types.SimpleNamespace(status_code=200, text='')
sys.modules['requests'] = requests

dotenv = types.ModuleType('dotenv')
dotenv.load_dotenv = lambda *a, **k: None
sys.modules['dotenv'] = dotenv

rich = types.ModuleType('rich')
rich.print = lambda *a, **k: None
console_mod = types.ModuleType('rich.console')
class DummyConsole:
    def print(self, *a, **k):
        pass
console_mod.Console = DummyConsole
sys.modules['rich.console'] = console_mod
table_mod = types.ModuleType('rich.table')
table_mod.Table = object
sys.modules['rich.table'] = table_mod
sys.modules['rich'] = rich

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

playwright = types.ModuleType('playwright')
async_api = types.ModuleType('playwright.async_api')
async_api.async_playwright = None
async_api.BrowserContext = object
playwright.async_api = async_api
sys.modules['playwright'] = playwright
sys.modules['playwright.async_api'] = async_api

import letus_checker_secure as lcs

JST = ZoneInfo("Asia/Tokyo")

def test_run_closes_page(monkeypatch):
    page = AsyncMock()
    closed = False

    async def close():
        nonlocal closed
        closed = True
    page.close.side_effect = close

    checker = lcs.LetusChecker(None)

    async def fake_login():
        return page

    async def fake_fetch(_):
        return [{
            "label": "dummy",
            "link": "dummy",
            "due": dt.datetime.now(JST) + dt.timedelta(hours=1)
        }]

    async def fake_is_submitted(_, __):
        return False

    monkeypatch.setattr(checker, "login", fake_login)
    monkeypatch.setattr(checker, "fetch_upcoming", fake_fetch)
    monkeypatch.setattr(checker, "is_submitted", fake_is_submitted)
    monkeypatch.setattr(lcs, "notify", lambda alerts: None)

    count = asyncio.run(checker.run(2))

    assert count == 1
    assert closed
