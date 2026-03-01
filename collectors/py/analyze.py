#!/usr/bin/env python3
"""keenetic-maxprobe analyzer (no deps)."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

def read_text(p: Path, max_bytes=2_000_000) -> str:
    try:
        b=p.read_bytes()
        if len(b)>max_bytes: b=b[:max_bytes]
        return b.decode('utf-8', errors='replace')
    except Exception:
        return ''

def extract_ports(listen_txt: str):
    ports=set()
    for m in re.finditer(r':(\d+)\b', listen_txt):
        try: ports.add(int(m.group(1)))
        except: pass
    return sorted(ports)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    a=ap.parse_args()
    root=Path(a.root).resolve()
    analysis=root/'analysis'; analysis.mkdir(exist_ok=True)
    meta=root/'meta'
    version=read_text(meta/'version.txt',200).strip()
    mode=read_text(meta/'mode.txt',200).strip()
    profile=read_text(meta/'profile.txt',200).strip()
    listen=read_text(root/'net'/'listen.txt')
    ports=extract_ports(listen)
    web_probe=read_text(root/'web'/'probe.tsv')

    (analysis/'REPORT_RU.md').write_text(
        '# Отчёт keenetic-maxprobe (RU)\n\n'
        f'**Версия:** {version or "?"}  \n'
        f'**Профиль:** {profile or "?"}  \n'
        f'**Режим:** {mode or "?"}\n\n'
        '## Слушающие порты\n\n'
        + ('- ' + ', '.join(map(str, ports)) + '\n\n' if ports else '_Нет данных_\n\n')
        + '## Web probe (кратко)\n\n'
        + ('```\n' + web_probe[:2000] + '\n```\n' if web_probe else '_Нет данных_\n'),
        encoding='utf-8'
    )
    (analysis/'summary.json').write_text(json.dumps({'version':version,'profile':profile,'mode':mode,'ports':ports}, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
