# letus-watcher

This script monitors the LETUS learning management system for upcoming
assignment deadlines and optionally sends notifications via LINE Notify.

## Installation

Install the Python dependencies listed in `requirements.txt` and download the
Chromium browser used by Playwright:

```bash
pip install -r requirements.txt
playwright install chromium
```

## Usage

Run once with `--configure` to store your LETUS credentials in the system
keyring:

```bash
python letus_checker_secure.py --configure --due-within 24
```

Stored credentials can be removed later with `--clear`:

```bash
python letus_checker_secure.py --clear
```

After configuration you can simply run the checker:

```bash
python letus_checker_secure.py --due-within 24 --quiet
```

Use `--watch` to continuously poll LETUS every _n_ minutes:

```bash
python letus_checker_secure.py --watch 30 --due-within 6
```

## Development

Run the unit tests with `pytest`:

```bash
pytest
```
