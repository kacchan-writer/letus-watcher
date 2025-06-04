import sys, types, importlib

# Stub heavy dependencies
for name in [
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

sys.modules['dotenv'].load_dotenv = lambda *a, **kw: None

class DummyConsole:
    def __init__(self, *a, **kw):
        pass
    def print(self, *a, **kw):
        pass
sys.modules['rich'].print = lambda *a, **kw: None
sys.modules['rich.console'].Console = DummyConsole
sys.modules['rich.table'].Table = type('Table', (), {})

sys.modules['playwright.async_api'].async_playwright = lambda *a, **kw: None
sys.modules['playwright.async_api'].BrowserContext = type('BrowserContext', (), {})

# Prepare fake keyring module
calls = []
keyring = types.ModuleType('keyring')
keyring.set_password = lambda *a, **k: None
keyring.get_password = lambda *a, **k: None

def delete_password(service, key):
    calls.append((service, key))
keyring.delete_password = delete_password
sys.modules['keyring'] = keyring

module = importlib.import_module('letus_checker_secure')


def test_clear_credentials_calls_delete():
    module.clear_credentials()
    expected_keys = {'USERNAME', 'PASSWORD', 'LINE_TOKEN'}
    assert {k for _, k in calls} == expected_keys
