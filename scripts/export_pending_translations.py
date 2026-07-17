#!/usr/bin/env python3
import json
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZH_PATH = ROOT / 'data' / 'cis_items.zh_hk.json'
OUT_CSV = ROOT / 'data' / 'pending_translations.csv'

def load_zh():
    with ZH_PATH.open('r', encoding='utf-8') as f:
        return json.load(f)

def main():
    zh = load_zh()
    rows = []
    for code, entry in zh.items():
        desc = entry.get('description', '') or ''
        full = entry.get('full_text', '') or ''
        # mark pending if contains the string '待翻譯'
        if '待翻譯' in desc or '待翻譯' in full:
            rows.append({
                'code': code,
                'name_en': entry.get('name', ''),
                'description_en': entry.get('description_en', ''),
                'full_text_en': entry.get('full_text_en', ''),
                'zh_description': desc,
                'zh_full_text': full,
            })
    if not rows:
        print('No pending translations found.')
        return
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open('w', encoding='utf-8-sig', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=['code','name_en','description_en','full_text_en','zh_description','zh_full_text'])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    print(f'Wrote {len(rows)} pending entries to {OUT_CSV}')

if __name__ == '__main__':
    main()
