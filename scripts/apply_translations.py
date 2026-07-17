#!/usr/bin/env python3
import json
import csv
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
ZH_PATH = ROOT / 'data' / 'cis_items.zh_hk.json'
IN_CSV = ROOT / 'data' / 'pending_translations_translated.csv'

def load_zh():
    with ZH_PATH.open('r', encoding='utf-8') as f:
        return json.load(f)

def backup_zh():
    bak = ZH_PATH.with_suffix('.json.bak.' + datetime.now().strftime('%Y%m%d%H%M%S'))
    bak.write_text(ZH_PATH.read_text(encoding='utf-8'), encoding='utf-8')
    print('Backup written to', bak)

def main():
    if not IN_CSV.exists():
        print('Expected translated CSV at', IN_CSV)
        print('Please create or upload the translated CSV (same columns as pending_translations.csv) and re-run this script.')
        return
    zh = load_zh()
    updates = 0
    with IN_CSV.open('r', encoding='utf-8-sig', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            code = row.get('code')
            if not code or code not in zh:
                continue
            # prefer provided translated fields; if empty skip
            new_desc = row.get('zh_description', '').strip()
            new_full = row.get('zh_full_text', '').strip()
            if new_desc:
                zh[code]['description'] = new_desc
                updates += 1
            if new_full:
                zh[code]['full_text'] = new_full
    if updates == 0:
        print('No updates found in CSV. Make sure zh_description or zh_full_text columns are filled.')
        return
    backup_zh()
    with ZH_PATH.open('w', encoding='utf-8') as f:
        json.dump(zh, f, ensure_ascii=False, indent=2)
    print(f'Applied translations for {updates} fields to {ZH_PATH}')

if __name__ == '__main__':
    main()
