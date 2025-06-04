import datetime as dt
import importlib
import sys
import types

# Stub heavy optional dependencies before importing the target module
for name in [
    'keyring',
    'requests',
    'dotenv',
    'rich',
    'rich.console',
    'rich.table',
    'playwright',
    'playwright.async_api',
]:
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)

# Provide minimal attributes used during import
sys.modules['dotenv'].load_dotenv = lambda *a, **kw: None

class DummyConsole:
    def __init__(self, *a, **kw):
        pass
sys.modules['rich'].print = lambda *a, **kw: None
sys.modules['rich.console'].Console = DummyConsole
sys.modules['rich.table'].Table = type('Table', (), {})
sys.modules['playwright.async_api'].async_playwright = lambda *a, **kw: None
sys.modules['playwright.async_api'].BrowserContext = type('BrowserContext', (), {})

module = importlib.import_module('letus_checker_secure')
parse_due_date = module.parse_due_date
JST = module.JST


def test_parse_japanese_date():
    text = "2024\u5e747\u67085\u65e5 15:30 \u307e\u3067"
    expected = dt.datetime(2024, 7, 5, 15, 30, tzinfo=JST)
    assert parse_due_date(text) == expected


def test_parse_english_date_with_ampm():
    text = "5 August 2025 at 9:15 PM"
    expected = dt.datetime(2025, 8, 5, 21, 15, tzinfo=JST)
    assert parse_due_date(text) == expected


def test_unmatched_returns_none():
    assert parse_due_date("no date here") is None
