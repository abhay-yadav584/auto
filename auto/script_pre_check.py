import os
import re
import io
import sys
# --- TextFSM compatibility shim (handles missing attributes) ---
try:
    import textfsm  # type: ignore
    if not (hasattr(textfsm, "TextFSM") and hasattr(textfsm, "TextFSMTemplateError")):
        class _TFSMStub:
            def __init__(self, template_io): pass
            def ParseText(self, txt): return []
            @property
            def header(self): return []
        class _TFSMTemplateErr(Exception): pass
        textfsm.TextFSM = _TFSMStub  # type: ignore
        textfsm.TextFSMTemplateError = _TFSMTemplateErr  # type: ignore
except Exception:
    import types
    textfsm = types.ModuleType("textfsm")
    class _TFSMStub:
        def __init__(self, template_io): pass
        def ParseText(self, txt): return []
        @property
        def header(self): return []
    class _TFSMTemplateErr(Exception): pass
    textfsm.TextFSM = _TFSMStub  # type: ignore
    textfsm.TextFSMTemplateError = _TFSMTemplateErr  # type: ignore

# REPLACED failing absolute imports with hybrid relative/local imports
try:
    from .cli_parsers import NetworkParsers
except Exception:
    from cli_parsers import NetworkParsers

try:
    from .eos_cli import (
        InterfacesStatusCount,
        BgpStatus,
        RouteSummary,
        IgmpSnoopingQuerier,
        VlanBrief,
        VlanDynamic,
        EvpnRouteTypes,
        VXLAN,
        MacAddressTableDynamic,
        VrfReservedPorts
    )
except Exception:
    from eos_cli import (
        InterfacesStatusCount,
        BgpStatus,
        RouteSummary,
        IgmpSnoopingQuerier,
        VlanBrief,
        VlanDynamic,
        EvpnRouteTypes,
        VXLAN,
        MacAddressTableDynamic,
        VrfReservedPorts
    )

# NOTE: Core parsing (all regex/block extraction) resides in network_parsers.py.
# This script mainly orchestrates reading test.txt and printing formatted summaries.

def _print_route_summary_table(raw: str):
    # parser = NetworkParsers()
    # rows = parser.parse_ip_route_summary(raw)
    # if not rows:
    #     print("\nRoute Source Table: none")
    #     return
    # counted_rows = [r for r in rows if r.get("COUNT") is not None]
    # if counted_rows:
    #     name_width = max(len(r["SOURCE"]) for r in counted_rows)
    # else:
    #     name_width = len("SOURCE")
    # target_width = max(name_width, 60)
    # print("\nRoute Source Table:")
    # for r in rows:
    #     cnt = r.get("COUNT")
    #     src = r.get("SOURCE", "")
    #     if cnt is None:
    #         print(src)
    #     else:
    #         print(f"{src.ljust(target_width)}{str(cnt).rjust(4)}")
    # print("")
    # REPLACED: print raw lines (no re-parsing) matching expected format
    lines = raw.splitlines()
    start = None
    for i, l in enumerate(lines):
        low = l.lower()
        if ("#sh ip route summary" in low or
            "show ip route summary" in low or
            "command executed: sh ip route summary" in low):
            start = i + 1
            break
    if start is None:
        print("\nIP Route Summary (raw): none")
        return
    block = []
    for l in lines[start:]:
        if not l.strip():  # stop at first blank line
            break
        if l.strip().endswith("#") and "#sh" in l.lower():
            break
        block.append(l.rstrip())
    wanted = []
    for l in block:
        if re.match(r'\s*(connected|static|VXLAN Control Service|ospf|ospfv3|bgp|isis|rip|internal|attached|aggregate|dynamic policy|gribi)\b', l) \
           or re.search(r'\bTotal Routes\b', l) \
           or re.match(r'\s*Intra-area:', l) \
           or re.match(r'\s*NSSA External-1:', l) \
           or re.match(r'\s*External:', l) \
           or re.match(r'\s*Level-1:', l):
            wanted.append(l)
    print("\nIP Route Summary (raw):")
    for idx, l in enumerate(wanted):
        # First line without leading spaces (as per expected snippet)
        print(l.lstrip() if idx == 0 else l)
    # Added parsed values
    rgx = re.compile(r'^\s*([A-Za-z][A-Za-z0-9 ()/_-]*?)\s+(\d+)\s*$')
    allowed = {
        "connected","static (persistent)","static (non-persistent)","VXLAN Control Service",
        "static nexthop-group","ospf","ospfv3","bgp","isis","rip","internal","attached",
        "aggregate","dynamic policy","gribi","Total Routes"
    }
    parsed = {}
    for l in wanted:
        m = rgx.match(l.strip())
        if m and m.group(1) in allowed:
            parsed[m.group(1)] = int(m.group(2))
    if parsed:
        print("\nIP Route Summary (values):")
        for k in sorted(parsed):
            print(f"{k} {parsed[k]}")

def _print_igmp_snooping_querier(raw: str):
    parser = NetworkParsers()
    result = parser.parse_igmp_snooping_querier(raw)
    print("\nCommand executed:\nshow igmp snooping querier")
    if not result["lines"]:
        print("No IGMP snooping querier output found.")
        return
    for l in result["lines"]:
        print(l)
    print(f"\nVLAN record count: {result['vlan_count']}")

def _print_vlan_brief(raw: str):
    parser = NetworkParsers()
    rows = parser.parse_vlan_brief(raw)
    print("\nCommand executed:\nshow vlan brief")
    if not rows:
        print("No VLAN brief data.")
        return
    v_w = max(len("VLAN"), *(len(r["VLAN"]) for r in rows))
    n_w = max(len("Name"), *(len(r["NAME"]) for r in rows))
    s_w = max(len("Status"), *(len(r["STATUS"]) for r in rows))
    header = f"{'VLAN'.ljust(v_w)}  {'Name'.ljust(n_w)}  {'Status'.ljust(s_w)}  Ports"
    print(header)
    print("-" * len(header))
    for r in rows:
        print(f"{r['VLAN'].ljust(v_w)}  {r['NAME'].ljust(n_w)}  {r['STATUS'].ljust(s_w)}  {r['PORTS']}")
    print("-" * len(header))
    print(f"Total VLANs: {len(rows)}")

def _print_vlan_dynamic(raw: str):
    parser = NetworkParsers()
    rows = parser.parse_vlan_dynamic(raw)
    print("\nCommand executed:\nshow vlan dynamic")
    if not rows:
        print("No dynamic VLAN data.")
        return
    v_w = max(len("VLAN"), *(len(r["VLAN"]) for r in rows))
    n_w = max(len("Name"), *(len(r["NAME"]) for r in rows))
    s_w = max(len("Status"), *(len(r["STATUS"]) for r in rows))
    header = f"{'VLAN'.ljust(v_w)}  {'Name'.ljust(n_w)}  {'Status'.ljust(s_w)}  Ports"
    print(header)
    print("-" * len(header))
    for r in rows:
        print(f"{r['VLAN'].ljust(v_w)}  {r['NAME'].ljust(n_w)}  {r['STATUS'].ljust(s_w)}  {r['PORTS']}")
    print("-" * len(header))
    print(f"Total Dynamic VLANs: {len(rows)}")

def _print_bgp_evpn_route_type_auto_discovery_from_sample():
    """Load test.txt and print EVPN auto-discovery Network entries with counts."""
    sample_path = os.path.join(os.path.dirname(__file__), "test.txt")
    if not os.path.isfile(sample_path):
        print("\n(test) sh bgp evpn route-type auto-discovery: test.txt not found.")
        return
    try:
        raw = open(sample_path, "r", encoding="utf-8", errors="ignore").read()
    except Exception as e:
        print(f"\nError reading test.txt: {e}")
        return
    parser = NetworkParsers()
    rows = parser.parse_bgp_evpn_route_type_auto_discovery(raw)
    print("\nCommand executed (from test.txt):\nsh bgp evpn route-type auto-discovery")
    if not rows:
        print("No auto-discovery route-type data found.")
        return
    print("Entries (all occurrences):")
    for r in rows:
        print(f"  RD {r.get('RD')}")
    counts = {}
    for r in rows:
        rd = r.get("RD")
        if rd:
            counts[rd] = counts.get(rd, 0) + 1
    rd_w = max(len("RD"), *(len(x) for x in counts))
    c_w = len("Count")
    header = f"{'RD'.ljust(rd_w)}  {'Count'.rjust(c_w)}"
    print("\nSummary:")
    print(header)
    print("-" * len(header))
    total = 0
    for rd in sorted(counts):
        v = counts[rd]; total += v
        print(f"{rd.ljust(rd_w)}  {str(v).rjust(c_w)}")
    print("-" * len(header))
    print(f"{'TOTAL DISTINCT'.ljust(rd_w)}  {str(len(counts)).rjust(c_w)}")
    print(f"{'TOTAL OCCURRENCES'.ljust(rd_w)}  {str(total).rjust(c_w)}")

def _print_bgp_evpn_route_type_mac_ip_from_sample():
    """Load test.txt and print EVPN mac-ip Route Distinguisher entries with counts."""
    sample_path = os.path.join(os.path.dirname(__file__), "test.txt")
    if not os.path.isfile(sample_path):
        print("\n(test) sh bgp evpn route-type mac-ip: test.txt not found.")
        return
    try:
        raw = open(sample_path, "r", encoding="utf-8", errors="ignore").read()
    except Exception as e:
        print(f"\nError reading test.txt: {e}")
        return
    parser = NetworkParsers()
    rows = parser.parse_bgp_evpn_route_type_mac_ip(raw)
    print("\nCommand executed (from test.txt):\nsh bgp evpn route-type mac-ip")
    if not rows:
        print("No mac-ip route-type data found.")
        return
    print("Entries (all occurrences):")
    for r in rows:
        print(f"  RD {r.get('RD')}  MAC {r.get('MAC')}  IP {r.get('IP') or ''}")
    rd_counts = {}
    for r in rows:
        rd = r.get("RD")
        if rd:
            rd_counts[rd] = rd_counts.get(rd, 0) + 1
    rd_w = max(len("RD"), *(len(x) for x in rd_counts))
    c_w = len("Count")
    header = f"{'RD'.ljust(rd_w)}  {'Count'.rjust(c_w)}"
    print("\nSummary:")
    print(header)
    print("-" * len(header))
    total = 0
    for rd in sorted(rd_counts):
        v = rd_counts[rd]; total += v
        print(f"{rd.ljust(rd_w)}  {str(v).rjust(c_w)}")
    print("-" * len(header))
    print(f"{'TOTAL DISTINCT'.ljust(rd_w)}  {str(len(rd_counts)).rjust(c_w)}")
    print(f"{'TOTAL OCCURRENCES'.ljust(rd_w)}  {str(total).rjust(c_w)}")

def _print_bgp_evpn_route_type_imet_from_sample():
    """Load test.txt and print EVPN imet RD counts."""
    sample_path = os.path.join(os.path.dirname(__file__), "test.txt")
    if not os.path.isfile(sample_path):
        print("\n(test) sh bgp evpn route-type imet: test.txt not found.")
        return
    try:
        raw = open(sample_path, "r", encoding="utf-8", errors="ignore").read()
    except Exception as e:
        print(f"\nError reading test.txt: {e}")
        return
    parser = NetworkParsers()
    rows = parser.parse_bgp_evpn_route_type_imet(raw)
    print("\nCommand executed (from test.txt):\nsh bgp evpn route-type imet")
    if not rows:
        print("No imet route-type data found.")
        return
    print("Entries (all occurrences):")
    for r in rows:
        print(f"  RD {r.get('RD')}  IP {r.get('IP') or ''}")
    counts = {}
    for r in rows:
        rd = r.get("RD")
        if rd:
            counts[rd] = counts.get(rd, 0) + 1
    rd_w = max(len("RD"), *(len(x) for x in counts))
    c_w = len("Count")
    header = f"{'RD'.ljust(rd_w)}  {'Count'.rjust(c_w)}"
    print("\nSummary:")
    print(header)
    print("-" * len(header))
    total = 0
    for rd in sorted(counts):
        v = counts[rd]; total += v
        print(f"{rd.ljust(rd_w)}  {str(v).rjust(c_w)}")
    print("-" * len(header))
    print(f"{'TOTAL DISTINCT'.ljust(rd_w)}  {str(len(counts)).rjust(c_w)}")
    print(f"{'TOTAL OCCURRENCES'.ljust(rd_w)}  {str(total).rjust(c_w)}")

def _print_bgp_evpn_route_type_ethernet_segment_from_sample():
    """Load test.txt and print EVPN ethernet-segment RD/ESI counts."""
    sample_path = os.path.join(os.path.dirname(__file__), "test.txt")
    if not os.path.isfile(sample_path):
        print("\n(test) sh bgp evpn route-type ethernet-segment: test.txt not found.")
        return
    try:
        raw = open(sample_path, "r", encoding="utf-8", errors="ignore").read()
    except Exception as e:
        print(f"\nError reading test.txt: {e}")
        return
    parser = NetworkParsers()
    fn = getattr(parser, "parse_bgp_evpn_route_type_ethernet_segment", None)
    if not fn:
        print("Parser for ethernet-segment not implemented.")
        return
    rows = fn(raw)
    print("\nCommand executed (from test.txt):\nsh bgp evpn route-type ethernet-segment")
    if not rows:
        print("No ethernet-segment route-type data found.")
        return
    print("Entries (all occurrences):")
    for r in rows:
        print(f"  RD {r.get('RD')}  ESI {r.get('ESI')}")
    counts = {}
    for r in rows:
        rd = r.get("RD")
        if rd:
            counts[rd] = counts.get(rd, 0) + 1
    rd_w = max(len("RD"), *(len(x) for x in counts))
    c_w = len("Count")
    header = f"{'RD'.ljust(rd_w)}  {'Count'.rjust(c_w)}"
    print("\nSummary:")
    print(header)
    print("-" * len(header))
    total = 0
    for rd in sorted(counts):
        v = counts[rd]; total += v
        print(f"{rd.ljust(rd_w)}  {str(v).rjust(c_w)}")
    print("-" * len(header))
    print(f"{'TOTAL DISTINCT'.ljust(rd_w)}  {str(len(counts)).rjust(c_w)}")
    print(f"{'TOTAL OCCURRENCES'.ljust(rd_w)}  {str(total).rjust(c_w)}")

def _write_output_file(content: str, filename: str):
    """Write captured script output to a file in the same directory."""
    out_path = os.path.join(os.path.dirname(__file__), filename)
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        print(f"Failed writing {filename}: {e}")

def _run_parsing(raw: str):
    isc = InterfacesStatusCount()  # reuse object for methods; override content
    isc.content = raw or ""
    buf = io.StringIO()
    # Start capture
    up, down = isc.count_ip_interfaces()
    conn, dis = isc.count_interfaces()
    isc.display_results()
    bgp = BgpStatus(isc.content)
    bgp.print_bgp_status()
    up, down = isc.count_ip_interfaces()
    conn, dis = isc.count_interfaces()
    est = bgp.count_established_sessions()
    print("\n--- Summary ---")
    print(f"UP: {up} DOWN: {down} CONNECTED: {conn} DISABLED: {dis} ESTABLISHED BGP: {est}")
    # Class-based tables
    rs = RouteSummary(isc.content); rs.print()
    ig = IgmpSnoopingQuerier(isc.content); ig.print()
    vb = VlanBrief(isc.content); vb.print()
    vd = VlanDynamic(isc.content); vd.print()
    ev = EvpnRouteTypes(isc.content); ev.print_summary()
    # EVPN detailed
    _print_bgp_evpn_route_type_auto_discovery_from_sample()
    _print_bgp_evpn_route_type_mac_ip_from_sample()
    _print_bgp_evpn_route_type_imet_from_sample()
    _print_bgp_evpn_route_type_ethernet_segment_from_sample()
    # Non-class helpers
    _print_route_summary_table(isc.content)
    _print_igmp_snooping_querier(isc.content)
    _print_vlan_brief(isc.content)
    _print_vlan_dynamic(isc.content)
    return buf.getvalue()

def _print_interface_sections(isc: InterfacesStatusCount):
    # Count interface states once and print in requested format.
    up, down = isc.count_ip_interfaces()
    conn, dis = isc.count_interfaces()
    print("command executed: show interfaces status")
    print(f"Number of interfaces CONNECTED: {conn}")
    print(f"Number of interfaces DISABLED: {dis}")
    print("\ncommand executed: show ip interface brief")
    print(f"Number of interfaces UP: {up}")
    print(f"Number of interfaces DOWN: {down}")
    return up, down, conn, dis

def _print_bgp_evpn_summary(raw: str):
    parser = NetworkParsers()
    rows = parser.parse_bgp_evpn_neighbor_summary(raw)
    print("\nCommand executed:\nsh bgp evpn summary")
    if not rows:
        print("No EVPN summary neighbor data found.")
        return
    estab = sum(1 for r in rows if r["STATE"].lower().startswith("estab"))
    print(f"Neighbor count: {len(rows)}  Established: {estab}")

def _print_bgp_summary(raw: str):
    """Use BgpStatus internal parser (_records) for accurate neighbor / established counts."""
    bs = BgpStatus(raw)
    rows = bs._records()
    estab = sum(1 for r in rows if r[2].lower().startswith("estab"))
    print("\ncommand executed: show bgp summary")
    print(f"Neighbor count: {len(rows)} Established: {estab}")

def _manual_bgp_summary_neighbors(raw: str):
    """
    Direct parser for 'show bgp summary' (no external class).
    Returns list of dicts {ip, asn, state, nlri_rcd, nlri_acc}.
    """
    results = []
    if not raw:
        return results
    lines = [l.rstrip("\r") for l in raw.splitlines()]
    # Find header containing both 'Neighbor' and 'NLRI' Rcd'
    header_idx = None
    for i, l in enumerate(lines):
        if "Neighbor" in l and "NLRI" in l and "Rcd" in l:
            header_idx = i
            break
    if header_idx is None:
        return results
    i = header_idx + 1
    # Skip dashed separator lines
    while i < len(lines) and re.match(r'^\s*-{4,}', lines[i]):
        i += 1
    ip_re = re.compile(r'^\s*(\d{1,3}(?:\.\d{1,3}){3})\s+')
    while i < len(lines):
        line = lines[i]
        # Stop on prompt or blank
        if line.strip().endswith("#"):
            break
        if not ip_re.match(line):
            break
        parts = re.split(r'\s+', line.strip())
        if len(parts) < 4:
            i += 1
            continue
        neighbor = parts[0]
        asn = parts[1]
        state_tok = parts[2]
        state_clean = re.sub(r'\d', '', state_tok).lower()
        if state_clean.startswith("estab"):
            state = "Established"
        elif state_clean.startswith("idle"):
            state = "Idle"
        elif state_clean.startswith("active"):
            state = "Active"
        else:
            state = state_tok
        ints = [p for p in parts if p.isdigit()]
        nlri_rcd = nlri_acc = None
        if len(ints) >= 2:
            nlri_rcd = int(ints[-2])
            nlri_acc = int(ints[-1])
        elif len(ints) == 1:
            nlri_rcd = nlri_acc = int(ints[-1])
        results.append({
            "ip": neighbor,
            "asn": asn,
            "state": state,
            "nlri_rcd": nlri_rcd,
            "nlri_acc": nlri_acc
        })
        i += 1
    return results

def _print_bgp_summary_ipv4(raw: str):
    """
    Same style as _print_bgp_evpn_summary: counts neighbors & established.
    """
    parser = NetworkParsers()
    rows = parser.parse_bgp_summary(raw)
    print("\nCommand executed:\nsh bgp summary")
    if not rows:
        print("No BGP summary neighbor data found.")
        return
    estab = sum(1 for r in rows if (r.get("STATE","").lower().startswith("estab")))
    print(f"Neighbor count: {len(rows)} Established: {estab}")

def main():
    # Run for test.txt (existing behavior)
    test_path = os.path.join(os.path.dirname(__file__), "test.txt")
    test_raw = ""
    if os.path.isfile(test_path):
        test_raw = open(test_path, "r", encoding="utf-8", errors="ignore").read()
    # Fallback: if route summary missing, try script_output.txt
    if "ip route summary" not in test_raw.lower():
        fallback_path = os.path.join(os.path.dirname(__file__), "script_output.txt")
        if os.path.isfile(fallback_path):
            try:
                extra = open(fallback_path, "r", encoding="utf-8", errors="ignore").read()
                if "ip route summary" in extra.lower():
                    test_raw += "\n" + extra
            except Exception:
                pass
    _buf = io.StringIO()
    _real_stdout = sys.stdout
    sys.stdout = _buf
    try:
        isc = InterfacesStatusCount()
        isc.content = test_raw
        up, down, conn, dis = _print_interface_sections(isc)
        bgp = BgpStatus(isc.content)
        _print_bgp_summary_ipv4(isc.content)
        bgp.print_bgp_status()
        # --- ADDED: print IP route summary block ---
        rs = RouteSummary(isc.content)
        rs.print()
    finally:
        sys.stdout = _real_stdout
    output = _buf.getvalue()
    # Write to file (for review, if needed)
    _write_output_file(output, "parsed_output.txt")
    return output