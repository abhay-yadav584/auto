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


def build_df_from_parsed(data):
    """Normalize parsed list data into a pandas DataFrame with expected columns."""
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
        cols = [f'col{i}' for i in range(rowlen)]
        df = pd.DataFrame(data, columns=cols)

    for col in ['vrf', 'route', 'source', 'next-hop', 'all-next-hops', 'via-ip', 'all-via-ips']:
        if col in df:
            df[col] = df[col].astype(str).str.strip()
    return df


def compare_pre_post(out_dir: Path):
    """Compare pre_routes.csv and post_routes.csv and write pre_post_compare.csv

    Columns: vrf,count_pre,count_post,delta,missing_routes
    missing_routes: routes present in pre but not in post, joined by ' | '
    """
    pre_csv = out_dir / 'pre_routes.csv'
    post_csv = out_dir / 'post_routes.csv'
    out_csv = out_dir / 'pre_post_compare.csv'

    if not pre_csv.exists() and not post_csv.exists():
        return None

    try:
        pre = pd.read_csv(pre_csv, dtype=str) if pre_csv.exists() else pd.DataFrame(columns=['vrf', 'route'])
    except Exception:
        pre = pd.DataFrame(columns=['vrf', 'route'])
    try:
        post = pd.read_csv(post_csv, dtype=str) if post_csv.exists() else pd.DataFrame(columns=['vrf', 'route'])
    except Exception:
        post = pd.DataFrame(columns=['vrf', 'route'])

    pre = pre.fillna('')
    post = post.fillna('')

    pre_groups = pre.groupby('vrf')['route'].apply(lambda s: set(s[s != ''])) if not pre.empty else pd.Series(dtype=object)
    post_groups = post.groupby('vrf')['route'].apply(lambda s: set(s[s != ''])) if not post.empty else pd.Series(dtype=object)

    all_vrfs = sorted(set(pre_groups.index).union(post_groups.index))

    rows = []
    for vrf in all_vrfs:
        pre_set = pre_groups.get(vrf, set())
        post_set = post_groups.get(vrf, set())
        count_pre = len(pre_set)
        count_post = len(post_set)
        delta = count_post - count_pre
        missing = sorted(pre_set - post_set)
        missing_str = ' | '.join(missing)
        rows.append({
            'vrf': vrf,
            'count_pre': count_pre,
            'count_post': count_post,
            'delta': delta,
            'missing_routes': missing_str,
        })

    out_df = pd.DataFrame(rows)
    out_df = out_df.sort_values(['delta', 'vrf'], ascending=[False, True])
    out_df.to_csv(out_csv, index=False)
    return out_csv


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
    out_csv = out_dir / 'pre_routes.csv'
    out_md = out_dir / 'pre_routes.md'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    wrote_csv = None
    wrote_md = None
    try:
        df.to_csv(out_csv, index=False)
        wrote_csv = out_csv
    except PermissionError:
        fallback = out_dir / f'pre_routes_{timestamp}.csv'
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
                    fallback = out_dir / f'pre_routes_{timestamp}.csv'
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
        fallback_md = out_dir / f'pre_routes_{timestamp}.md'
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
    
    # Also process routes2.txt (same behavior: parse into post_routes.csv and post_routes.md)
    input2 = Path(__file__).resolve().parent / 'routes2.txt'
    if input2.exists():
        print(f"\nFound {input2.name}: parsing to post_routes.csv")
        data2 = None
        if template_file.exists() and textfsm:
            try:
                data2 = parse_with_textfsm(template_file, input2)
            except Exception as exc:
                print(f"TextFSM parsing routes2 failed: {exc}")
        if data2 is None:
            data2 = parse_with_regex(input2)

        df2 = build_df_from_parsed(data2)

        out_csv2 = out_dir / 'post_routes.csv'
        out_md2 = out_dir / 'post_routes.md'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        wrote_csv2 = None
        wrote_md2 = None

        try:
            df2.to_csv(out_csv2, index=False)
            wrote_csv2 = out_csv2
        except PermissionError:
            fallback2 = out_dir / f'post_routes_{timestamp}.csv'
            df2.to_csv(fallback2, index=False)
            wrote_csv2 = fallback2
            print(f'Warning: Could not write {out_csv2}; wrote to {fallback2} instead')

        try:
            with out_md2.open('w', encoding='utf-8') as md:
                md.write('| vrf | route | source | next-hop | all-next-hops | via-ip | all-via-ips |\n')
                md.write('|---|---|---|---|---|---|---|\n')
                for _, r in df2.iterrows():
                    md.write(f"| {r.get('vrf','')} | {r.get('route','')} | {r.get('source','')} | {r.get('next-hop','')} | {r.get('all-next-hops','')} | {r.get('via-ip','')} | {r.get('all-via-ips','')} |\n")
            wrote_md2 = out_md2
        except PermissionError:
            fallback_md2 = out_dir / f'post_routes_{timestamp}.md'
            with fallback_md2.open('w', encoding='utf-8') as md:
                md.write('| vrf | route | source | next-hop | all-next-hops | via-ip | all-via-ips |\n')
                md.write('|---|---|---|---|---|---|---|\n')
                for _, r in df2.iterrows():
                    md.write(f"| {r.get('vrf','')} | {r.get('route','')} | {r.get('source','')} | {r.get('next-hop','')} | {r.get('all-next-hops','')} | {r.get('via-ip','')} | {r.get('all-via-ips','')} |\n")
            wrote_md2 = fallback_md2
            print(f'Warning: Could not write {out_md2}; wrote to {fallback_md2} instead')

        if wrote_csv2 or wrote_md2:
            print('\nWrote (routes2):')
            if wrote_csv2:
                print(f'  {wrote_csv2}')
            if wrote_md2:
                print(f'  {wrote_md2}')

        # After writing both pre and post CSVs, produce a pre/post comparison CSV
        try:
            comp = compare_pre_post(out_dir)
            if comp:
                print(f"\nWrote comparison: {comp}")
        except Exception as exc:
            print(f"Warning: comparison failed: {exc}")


if __name__ == '__main__':
    main()
