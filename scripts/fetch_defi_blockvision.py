""
from __future__ import annotations
import json
import os
import pathlib
import time
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError

OUT_DIR = pathlib.Path(os.environ.get('OUT_DIR', 'data'))
API_KEY = os.environ.get('BLOCKVISION_API_KEY') or ''
ADDRS_ENV = os.environ.get('SUI_ADDRESSES') or os.environ.get('SUI_ADDRESS') or ''
ADDRESSES = [a.strip() for a in ADDRS_ENV.split(',') if a.strip()]

BASE = 'https://api.blockvision.org/v2/sui/account/defiPortfolio'
UA = 'sui-portfolio-bot/1.0 (+github-actions)'


def fetch(addr: str) -> dict:
    qs = urllib.parse.urlencode({'address': addr})
    url = f'{BASE}?{qs}'
    headers = {'Accept': 'application/json', 'User-Agent': UA}
    if API_KEY:
        headers['X-API-Key'] = API_KEY
    req = urllib.request.Request(url, headers=headers, method='GET')
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8'))


def write_json(path: pathlib.Path, obj: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not ADDRESSES:
        write_json(OUT_DIR / 'defi_bv_error.json', {'error': 'no addresses'})
        return
    if not API_KEY:
        write_json(OUT_DIR / 'defi_bv_error.json', {'error': 'missing BLOCKVISION_API_KEY'})
        return

    for addr in ADDRESSES:
        pref = addr[:10]
        try:
            data = fetch(addr)
            write_json(OUT_DIR / f'defi_bv_{pref}.json', data)
        except HTTPError as e:
            body = ''
            try:
                body = e.read().decode('utf-8')
            except Exception:
                body = '<no body>'
            write_json(OUT_DIR / f'defi_bv_{pref}_error.json', {
                'error': f'HTTP {e.code}',
                'reason': e.reason,
                'body': body,
            })
        except URLError as e:
            write_json(OUT_DIR / f'defi_bv_{pref}_error.json', {
                'error': 'URL Error',
                'reason': str(e.reason),
            })
        except Exception as e:
            write_json(OUT_DIR / f'defi_bv_{pref}_error.json', {
                'error': 'Exception',
                'reason': str(e),
            })
        time.sleep(0.25)


if __name__ == '__main__':
    main()
