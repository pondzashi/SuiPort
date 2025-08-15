from __future__ import annotations
import json
import os
import pathlib
import time
import urllib.parse
import urllib.request

OUT_DIR = pathlib.Path(os.environ.get('OUT_DIR', 'data'))
API_KEY = os.environ.get('BLOCKVISION_API_KEY') or ''
ADDRS_ENV = os.environ.get('SUI_ADDRESSES') or os.environ.get('SUI_ADDRESS') or ''
ADDRESSES = [a.strip() for a in ADDRS_ENV.split(',') if a.strip()]

BASE = 'https://api.blockvision.org/v2/sui/account/defiPortfolio'


def fetch(addr: str) -> dict:
    qs = urllib.parse.urlencode({'address': addr})
    url = f'{BASE}?{qs}'
    headers = {'Accept': 'application/json'}
    if API_KEY:
        headers['X-API-Key'] = API_KEY
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode('utf-8'))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not API_KEY:
        (OUT_DIR / 'defi_bv_error.json').write_text(json.dumps({'error': 'missing BLOCKVISION_API_KEY'}, indent=2))
        return
    for addr in ADDRESSES:
        try:
            data = fetch(addr)
            (OUT_DIR / f'defi_bv_{addr[:10]}.json').write_text(json.dumps(data, indent=2))
        except Exception as e:
            (OUT_DIR / f'defi_bv_{addr[:10]}_error.json').write_text(json.dumps({'error': str(e)}, indent=2))
        time.sleep(0.25)


if __name__ == '__main__':
    main()


