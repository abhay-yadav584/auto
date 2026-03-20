import sys
from pathlib import Path
import re

try:
    import textfsm
except Exception:
    textfsm = None

from datetime import datetime
import pandas as pd


def clean_text(s: str) -> str:
    # remove common control sequences
    s = re.sub(r'\x1b\].*?\x07', '', s, flags=re.DOTALL)
    s = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', s)
    s = ''.join(ch for ch in s if ch in '\n\r\t' or ord(ch) >= 32)
    return s


def parse_with_textfsm(template_path: Path, input_path: Path):
    with template_path.open('r', encoding='utf-8') as tf:
        fsm = textfsm.TextFSM(tf)
    with input_path.open('r', encoding='utf-8') as rf:
        raw = clean_text(rf.read())
    rows = fsm.ParseText(raw)
    # Convert rows to list of lists (ensure consistent format)
    return [list(r) for r in rows]


def parse_with_regex(input_path: Path):
    raw = clean_text(input_path.read_text(encoding='utf-8'))
    routes = []
    current_vrf = None
    lines = raw.splitlines()
    vrf_re = re.compile(r'^VRF:\s*(\S+)')
    route_re = re.compile(r'^\s*(?P<source>[A-Z0-9 ]+)\s+(?P<prefix>\d+\.\d+\.\d+\.\d+/\d+)')
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = vrf_re.match(ln)
        if m:
            current_vrf = m.group(1)
            i += 1
            continue
        m = route_re.match(ln)
        if m and current_vrf:
            source = m.group('source').strip()
            prefix = m.group('prefix')
            # collect subsequent next-hop lines until next route/vrf
            next_hops = []
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if nxt == '':
                    j += 1
                    continue
                if route_re.match(lines[j]) or vrf_re.match(lines[j]):
                    break
                # collect lines that look like nexthop info
                if nxt.startswith('directly connected') or nxt.startswith('via ') or 'VTEP' in nxt or nxt.startswith('via VTEP'):
                    next_hops.append(nxt)
                j += 1

            # normalizer
            def normalize_nexthop(s: str) -> str:
                s = s.strip()
                s = re.sub(r'^directly connected,?\s*', '', s, flags=re.I)
                s = re.sub(r'^via\s+', '', s, flags=re.I)
                # treat VTEP specially (format as "VTEP (ip)")
                if 'VTEP' in s.upper():
                    ip_m_v = re.search(r'(\d+\.\d+\.\d+\.\d+)', s)
                    if ip_m_v:
                        return f"VTEP ({ip_m_v.group(1)})"
                    return 'VTEP'
                # extract interface (Ethernet49/1, Vlan1304, Loopback0, Null0, Port-Channel1)
                int_m = re.search(r'([A-Za-z-]+\d+[A-Za-z0-9/\-]*)', s)
                ip_m = re.search(r'(\d+\.\d+\.\d+\.\d+)', s)
                interface = int_m.group(1) if int_m else None
                ip = ip_m.group(1) if ip_m else None
                if interface and ip:
                    return f"{interface} ({ip})"
                if interface:
                    return interface
                if ip:
                    return ip
                return re.sub(r'\[.*?\]', '', s).strip()

            normalized = [normalize_nexthop(x) for x in next_hops]
            first_nh = normalized[0] if normalized else ''
            # keep order but deduplicate
            seen = set()
            dedup = []
            for v in normalized:
                if v and v not in seen:
                    dedup.append(v)
                    seen.add(v)
            all_nh = ', '.join(dedup)

            # extract via IPs separately
            ips = []
            for raw in next_hops:
                ip_m = re.search(r'(\d+\.\d+\.\d+\.\d+)', raw)
                if ip_m:
                    ip = ip_m.group(1)
                    if ip not in ips:
                        ips.append(ip)
            first_ip = ips[0] if ips else ''
            all_ips = ', '.join(ips)

            routes.append([current_vrf, prefix, source, first_nh, all_nh, first_ip, all_ips])
            i = j
            continue
        i += 1
    return routes


def main():
    template_file = Path(__file__).resolve().parent / 'nxos_routes.template'
    input_file = Path(__file__).resolve().parent / 'routes.txt'

    if not input_file.exists():
        print(f"Input file not found: {input_file.resolve()}")
        sys.exit(2)

    data = None
    # Try TextFSM if template present and textfsm module available
    if template_file.exists() and textfsm:
        try:
            data = parse_with_textfsm(template_file, input_file)
        except Exception as exc:
            print(f"TextFSM parsing failed: {exc}")

    if data is None:
        data = parse_with_regex(input_file)

    # Normalize rows into DataFrame
    rowlen = len(data[0]) if data else 0
    if rowlen == 4:
        df = pd.DataFrame(data, columns=['vrf', 'route', 'source', 'next-hop'])
        df['all-next-hops'] = df['next-hop']
        df['via-ip'] = ''
        df['all-via-ips'] = ''
    elif rowlen == 5:
        df = pd.DataFrame(data, columns=['vrf', 'route', 'source', 'next-hop', 'all-next-hops'])
        df['via-ip'] = ''
        df['all-via-ips'] = ''
    elif rowlen >= 7:
        df = pd.DataFrame(data, columns=['vrf', 'route', 'source', 'next-hop', 'all-next-hops', 'via-ip', 'all-via-ips'])
    else:
        # fallback: try to create with generic column names
        cols = [f'col{i}' for i in range(rowlen)]
        df = pd.DataFrame(data, columns=cols)

    for col in ['vrf', 'route', 'source', 'next-hop', 'all-next-hops', 'via-ip', 'all-via-ips']:
        if col in df:
            df[col] = df[col].astype(str).str.strip()

    # Summary
    total = len(df)
    print(f"Total routes: {total}\n")
    vrf_counts = df['vrf'].value_counts()
    print("Routes per VRF:")
    print(vrf_counts.to_string())
    print('\nParsed routes:')
    # pretty-print all parsed columns to console
    print(df.to_string(index=False))

    out_dir = Path(__file__).resolve().parent
    out_csv = out_dir / 'parsed_routes.csv'
    out_md = out_dir / 'parsed_routes.md'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    wrote_csv = None
    wrote_md = None
    try:
        df.to_csv(out_csv, index=False)
        wrote_csv = out_csv
    except PermissionError:
        fallback = out_dir / f'parsed_routes_{timestamp}.csv'
        df.to_csv(fallback, index=False)
        wrote_csv = fallback
        print(f'Warning: Could not write {out_csv}; wrote to {fallback} instead')

    # If an existing parsed_routes.csv exists, merge/appent deduplicating rows
    # This ensures newly parsed VRFs (e.g., CMN-PROD-LE) are added to the same CSV
    try:
        if out_csv.exists():
            # read existing and combine
            try:
                existing = pd.read_csv(out_csv, dtype=str)
            except Exception:
                existing = None
            if existing is not None:
                # ensure same columns
                cols = list(df.columns)
                existing = existing.reindex(columns=cols)
                combined = pd.concat([existing, df], ignore_index=True)
                # drop exact duplicate rows
                combined = combined.drop_duplicates()
                # write combined back
                try:
                    combined.to_csv(out_csv, index=False)
                    wrote_csv = out_csv
                except PermissionError:
                    fallback = out_dir / f'parsed_routes_{timestamp}.csv'
                    combined.to_csv(fallback, index=False)
                    wrote_csv = fallback
                    print(f'Warning: Could not write merged {out_csv}; wrote to {fallback} instead')
    except Exception:
        # non-fatal, we already wrote df above or to a fallback
        pass

    try:
        with out_md.open('w', encoding='utf-8') as md:
            md.write('| vrf | route | source | next-hop | all-next-hops | via-ip | all-via-ips |\n')
            md.write('|---|---|---|---|---|---|---|\n')
            for _, r in df.iterrows():
                md.write(f"| {r.get('vrf','')} | {r.get('route','')} | {r.get('source','')} | {r.get('next-hop','')} | {r.get('all-next-hops','')} | {r.get('via-ip','')} | {r.get('all-via-ips','')} |\n")
        wrote_md = out_md
    except PermissionError:
        fallback_md = out_dir / f'parsed_routes_{timestamp}.md'
        with fallback_md.open('w', encoding='utf-8') as md:
            md.write('| vrf | route | source | next-hop | all-next-hops | via-ip | all-via-ips |\n')
            md.write('|---|---|---|---|---|---|---|\n')
            for _, r in df.iterrows():
                md.write(f"| {r.get('vrf','')} | {r.get('route','')} | {r.get('source','')} | {r.get('next-hop','')} | {r.get('all-next-hops','')} | {r.get('via-ip','')} | {r.get('all-via-ips','')} |\n")
        wrote_md = fallback_md
        print(f'Warning: Could not write {out_md}; wrote to {fallback_md} instead')

    print('\nWrote:')
    if wrote_csv:
        print(f'  {wrote_csv}')
    if wrote_md:
        print(f'  {wrote_md}')


if __name__ == '__main__':
    main()
