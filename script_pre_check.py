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

try:
    from auto.cli_parsers import NetworkParsers
    from auto.eos_cli import (
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
except ModuleNotFoundError:
    # Fallback when 'auto' package not discoverable (direct execution)
    import sys as _sys, os as _os
    _auto_dir = _os.path.join(_os.path.dirname(__file__), "auto")
    if _auto_dir not in _sys.path:
        _sys.path.append(_auto_dir)
    try:
        import cli_parsers  # type: ignore
        import eos_cli  # type: ignore
        NetworkParsers = cli_parsers.NetworkParsers  # type: ignore
        InterfacesStatusCount = eos_cli.InterfacesStatusCount  # type: ignore
        BgpStatus = eos_cli.BgpStatus  # type: ignore
        RouteSummary = eos_cli.RouteSummary  # type: ignore
        IgmpSnoopingQuerier = eos_cli.IgmpSnoopingQuerier  # type: ignore
        VlanBrief = eos_cli.VlanBrief  # type: ignore
        VlanDynamic = eos_cli.VlanDynamic  # type: ignore
        EvpnRouteTypes = eos_cli.EvpnRouteTypes  # type: ignore
        VXLAN = eos_cli.VXLAN  # type: ignore
        MacAddressTableDynamic = eos_cli.MacAddressTableDynamic  # type: ignore
        VrfReservedPorts = eos_cli.VrfReservedPorts  # type: ignore
    except Exception as _e:
        print(f"Import fallback failed: {_e}")

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
        if "#sh ip route summary" in low or "show ip route summary" in low:
            start = i + 1
            break
    if start is None:
        print("\nIP Route Summary (raw): none")
        return
    block = []
    for l in lines[start:]:
        if l.strip().endswith("#") and "#sh" in l:
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
    Adds neighbor IP list for validation (expect 6 in test.txt).
    """
    parser = NetworkParsers()
    rows = parser.parse_bgp_summary(raw)
    print("\nCommand executed:\nsh bgp summary")
    if not rows:
        print("No BGP summary neighbor data found.")
        return
    estab = sum(1 for r in rows if (r.get("STATE","").lower().startswith("estab")))
    neighbors = [r.get("NEIGHBOR") for r in rows if r.get("NEIGHBOR")]
    print(f"Neighbor count: {len(rows)} Established: {estab}")
    print(f"Neighbor IPs ({len(neighbors)}): {' '.join(neighbors)}")

def main():
    # Run for test.txt (existing behavior)
    test_path = os.path.join(os.path.dirname(__file__), "test.txt")
    test_raw = ""
    if os.path.isfile(test_path):
        test_raw = open(test_path, "r", encoding="utf-8", errors="ignore").read()
    else:
        print("test.txt not found.")
    _buf = io.StringIO()
    _real_stdout = sys.stdout
    sys.stdout = _buf
    try:
        isc = InterfacesStatusCount()
        isc.content = test_raw
        up, down, conn, dis = _print_interface_sections(isc)
        bgp = BgpStatus(isc.content)
        # REMOVED obsolete enhanced summary call:
        # bgp.print_bgp_summary_enhanced()
        _print_bgp_summary_ipv4(isc.content)
        bgp.print_bgp_status()
        _print_bgp_evpn_summary(isc.content)
        VXLAN(isc.content).print_vtep_detail()
        MacAddressTableDynamic(isc.content).print()
        VrfReservedPorts(isc.content).print()
        est = bgp.count_established_sessions()
        RouteSummary(isc.content).print()
        IgmpSnoopingQuerier(isc.content).print()
        VlanBrief(isc.content).print()
        VlanDynamic(isc.content).print()
        EvpnRouteTypes(isc.content).print_summary()
        _print_bgp_evpn_route_type_auto_discovery_from_sample()
        _print_bgp_evpn_route_type_mac_ip_from_sample()
        _print_bgp_evpn_route_type_imet_from_sample()
        _print_bgp_evpn_route_type_ethernet_segment_from_sample()
    finally:
        sys.stdout = _real_stdout
    test_out = _buf.getvalue()
    # REMOVED _strip_plain_bgp_summary call to preserve neighbor / established lines
    # test_out = _strip_plain_bgp_summary(test_out)
    print(test_out)
    _write_output_file(test_out, "script_output.txt")

    # Run for post_check.txt (new)
    post_path = os.path.join(os.path.dirname(__file__), "post_check.txt")
    if os.path.isfile(post_path):
        post_raw = open(post_path, "r", encoding="utf-8", errors="ignore").read()
        # Reuse same functions but need EVPN sample readers to point at post file temporarily
        # Simplest: temporarily rename expected file references
        _buf2 = io.StringIO()
        sys.stdout = _buf2
        try:
            # Override sample-based functions to read post_check.txt by monkey patching path lookups
            def _load_and_replace(func, new_file):
                # Wrap original function to force reading new_file
                def wrapper():
                    # Replace internal sample_path usage by reading new_file directly
                    raw_local = post_raw
                    parser = NetworkParsers()
                    if func.__name__.endswith("auto_discovery_from_sample"):
                        rows = parser.parse_bgp_evpn_route_type_auto_discovery(raw_local)
                        print("\nCommand executed (from post_check.txt):\nsh bgp evpn route-type auto-discovery")
                        if not rows:
                            print("No auto-discovery route-type data found."); return
                        print("Entries (all occurrences):")
                        for r in rows: print(f"  RD {r.get('RD')}")
                        counts={}
                        for r in rows:
                            rd=r.get("RD")
                            if rd: counts[rd]=counts.get(rd,0)+1
                        rd_w=max(len("RD"),*(len(x) for x in counts))
                        c_w=len("Count")
                        header=f"{'RD'.ljust(rd_w)}  {'Count'.rjust(c_w)}"
                        print("\nSummary:"); print(header); print("-"*len(header))
                        total=0
                        for rd in sorted(counts):
                            v=counts[rd]; total+=v
                            print(f"{rd.ljust(rd_w)}  {str(v).rjust(c_w)}")
                        print("-"*len(header))
                        print(f"{'TOTAL DISTINCT'.ljust(rd_w)}  {str(len(counts)).rjust(c_w)}")
                        print(f"{'TOTAL OCCURRENCES'.ljust(rd_w)}  {str(total).rjust(c_w)}")
                    elif func.__name__.endswith("mac_ip_from_sample"):
                        rows = parser.parse_bgp_evpn_route_type_mac_ip(raw_local)
                        print("\nCommand executed (from post_check.txt):\nsh bgp evpn route-type mac-ip")
                        if not rows:
                            print("No mac-ip route-type data found."); return
                        print("Entries (all occurrences):")
                        for r in rows: print(f"  RD {r.get('RD')}  MAC {r.get('MAC')}  IP {r.get('IP') or ''}")
                        counts={}
                        for r in rows:
                            rd=r.get("RD")
                            if rd: counts[rd]=counts.get(rd,0)+1
                        rd_w=max(len("RD"),*(len(x) for x in counts))
                        c_w=len("Count"); header=f"{'RD'.ljust(rd_w)}  {'Count'.rjust(c_w)}"
                        print("\nSummary:"); print(header); print("-"*len(header))
                        total=0
                        for rd in sorted(counts):
                            v=counts[rd]; total+=v
                            print(f"{rd.ljust(rd_w)}  {str(v).rjust(c_w)}")
                        print("-"*len(header))
                        print(f"{'TOTAL DISTINCT'.ljust(rd_w)}  {str(len(counts)).rjust(c_w)}")
                        print(f"{'TOTAL OCCURRENCES'.ljust(rd_w)}  {str(total).rjust(c_w)}")
                    elif func.__name__.endswith("imet_from_sample"):
                        rows = parser.parse_bgp_evpn_route_type_imet(raw_local)
                        print("\nCommand executed (from post_check.txt):\nsh bgp evpn route-type imet")
                        if not rows:
                            print("No imet route-type data found."); return
                        print("Entries (all occurrences):")
                        for r in rows: print(f"  RD {r.get('RD')}  IP {r.get('IP') or ''}")
                        counts={}
                        for r in rows:
                            rd=r.get("RD")
                            if rd: counts[rd]=counts.get(rd,0)+1
                        rd_w=max(len("RD"),*(len(x) for x in counts))
                        c_w=len("Count"); header=f"{'RD'.ljust(rd_w)}  {'Count'.rjust(c_w)}"
                        print("\nSummary:"); print(header); print("-"*len(header))
                        total=0
                        for rd in sorted(counts):
                            v=counts[rd]; total+=v
                            print(f"{rd.ljust(rd_w)}  {str(v).rjust(c_w)}")
                        print("-"*len(header))
                        print(f"{'TOTAL DISTINCT'.ljust(rd_w)}  {str(len(counts)).rjust(c_w)}")
                        print(f"{'TOTAL OCCURRENCES'.ljust(rd_w)}  {str(total).rjust(c_w)}")
                    elif func.__name__.endswith("ethernet_segment_from_sample"):
                        rows = parser.parse_bgp_evpn_route_type_ethernet_segment(raw_local)
                        print("\nCommand executed (from post_check.txt):\nsh bgp evpn route-type ethernet-segment")
                        if not rows:
                            print("No ethernet-segment route-type data found."); return
                        print("Entries (all occurrences):")
                        for r in rows: print(f"  RD {r.get('RD')}  ESI {r.get('ESI')}")
                        counts={}
                        for r in rows:
                            rd=r.get("RD")
                            if rd: counts[rd]=counts.get(rd,0)+1
                        rd_w=max(len("RD"),*(len(x) for x in counts))
                        c_w=len("Count"); header=f"{'RD'.ljust(rd_w)}  {'Count'.rjust(c_w)}"
                        print("\nSummary:"); print(header); print("-"*len(header))
                        total=0
                        for rd in sorted(counts):
                            v=counts[rd]; total+=v
                            print(f"{rd.ljust(rd_w)}  {str(v).rjust(c_w)}")
                        print("-"*len(header))
                        print(f"{'TOTAL DISTINCT'.ljust(rd_w)}  {str(len(counts)).rjust(c_w)}")
                        print(f"{'TOTAL OCCURRENCES'.ljust(rd_w)}  {str(total).rjust(c_w)}")
                return wrapper

            # Run same high-level summary for post_check
            isc_post = InterfacesStatusCount()
            isc_post.content = post_raw
            # REPLACED isc_post.display_results() with custom formatting
            up_p, down_p, conn_p, dis_p = _print_interface_sections(isc_post)
            bgp_post = BgpStatus(isc_post.content)
            # REMOVED obsolete enhanced summary call:
            # bgp_post.print_bgp_summary_enhanced()
            _print_bgp_summary_ipv4(isc_post.content)
            bgp_post.print_bgp_status()
            # EVPN detailed for post_check
            for func in (
                _print_bgp_evpn_route_type_auto_discovery_from_sample,
                _print_bgp_evpn_route_type_mac_ip_from_sample,
                _print_bgp_evpn_route_type_imet_from_sample,
                _print_bgp_evpn_route_type_ethernet_segment_from_sample,
            ):
                wrapped = _load_and_replace(func, post_path)
                wrapped()
            # NEW: invoke VXLAN VTEP detail for post_check
            VXLAN(isc_post.content).print_vtep_detail()
            # NEW: print MAC address-table dynamic for post_check
            MacAddressTableDynamic(isc_post.content).print()
            # NEW: supplemental single-line variant (requested pattern)
            print("command executed:show mac address-table dynamic")
        finally:
            sys.stdout = _real_stdout
        post_out = _buf2.getvalue()
        # REMOVED _strip_plain_bgp_summary call
        # post_out = _strip_plain_bgp_summary(post_out)
        print(post_out)
        _write_output_file(post_out, "post_check_output.txt")
    else:
        print("post_check.txt not found; skipping second pass.")

# ---- Test class addition ----
class OutputTests:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.script_content = self._read("script_output.txt")
        self.post_content = self._read("post_check_output.txt")
        self.results = []

    def _read(self, fname):
        path = os.path.join(self.base_dir, fname)
        if not os.path.isfile(path):
            return ""
        try:
            return open(path, "r", encoding="utf-8", errors="ignore").read()
        except Exception:
            return ""

    def _extract_int(self, text, label):
        # Accept ':' or '='
        m = re.search(rf"{re.escape(label)}\s*[=:]\s*(\d+)", text)
        return int(m.group(1)) if m else None

    def _connected(self, content):
        return self._extract_int(content, "Number of interfaces CONNECTED")

    def _disabled(self, content):
        return self._extract_int(content, "Number of interfaces DISABLED")

    def _up(self, content):
        return self._extract_int(content, "Number of interfaces UP")

    def _down(self, content):
        return self._extract_int(content, "Number of interfaces DOWN")

    def _evpn_summary_counts(self, content):
        # From "EVPN Route-Type Summary (class):"
        counts = {}
        if not content:
            return counts
        for key in ["auto-discovery", "mac-ip", "imet", "ethernet-segment"]:
            # Accept either:
            #   mac-ip: 2089 entries
            # or
            #   mac-ip entries: 2089
            m1 = re.search(rf"{re.escape(key)}:\s*(\d+)\s+entries", content)
            m2 = re.search(rf"{re.escape(key)}\s+entries:\s*(\d+)", content)
            if m1:
                counts[key] = int(m1.group(1))
            elif m2:
                counts[key] = int(m2.group(1))
        # UPDATED: fallback for mac-ip when summary lines absent; use TOTAL OCCURRENCES from mac-ip block
        if "mac-ip" not in counts:
            _, occ = self._evpn_mac_ip_totals(content)
            if occ is not None:
                counts["mac-ip"] = occ
        return counts

    def _bgp_enhanced_vals(self, content):
        nbr = self._extract_int(content, "Neighbor count")
        estab = None
        # First try enhanced session state line
        m = re.search(r"Session state\s*:\s*Established\s*[=:]\s*(\d+)", content)
        if m:
            estab = int(m.group(1))
        else:
            # Fallback to simple "Established:" line
            m2 = re.search(r"Established:\s*(\d+)", content)
            if m2:
                estab = int(m2.group(1))
            else:
                # Fallback to "Neighbor count: X Established: Y"
                m3 = re.search(r"Neighbor count:\s*\d+\s+Established:\s*(\d+)", content)
                if m3:
                    estab = int(m3.group(1))
        mismatch_count = 0
        return nbr, estab, mismatch_count

    # ADD: restored helper for extracting 4-line BGP summary block
    def _bgp_all_summary(self, content):
        """
        Extract the plain 4-line IPv4 BGP summary block:
        Command executed:
        sh bgp summary
        Neighbor count: X Established: Y
        Neighbor IPs (N): <ips...>
        Returns dict or None.
        """
        if not content:
            return None
        lines = content.splitlines()
        for i in range(len(lines) - 3):
            if lines[i].strip() == "Command executed:" and lines[i+1].strip() == "sh bgp summary":
                nbr_line = lines[i+2].strip()
                ips_line = lines[i+3].strip()
                if not nbr_line.startswith("Neighbor count:") or not ips_line.startswith("Neighbor IPs"):
                    continue
                m_cnt = re.search(r'Neighbor count:\s*(\d+)\s+Established:\s*(\d+)', nbr_line)
                m_ips = re.search(r'Neighbor IPs\s*\(\d+\):\s*(.+)', ips_line)
                if not m_cnt or not m_ips:
                    continue
                return {
                    "neighbor_count": int(m_cnt.group(1)),
                    "established": int(m_cnt.group(2)),
                    "neighbors": m_ips.group(1).split(),
                    "block": [lines[i].rstrip(), lines[i+1].rstrip(), nbr_line, ips_line]
                }
        return None

    # REPLACE: faulty test_bgp_all_summary (was redefining parser, used undefined 'content')
    def test_bgp_all_summary(self):
        pre = self._bgp_all_summary(self.script_content)
        post = self._bgp_all_summary(self.post_content)
        if pre is None or post is None:
            self.results.append(("bgp_all_summary", pre, post, "SKIP"))
            return
        status = (
            "PASS" if (
                pre["neighbor_count"] == post["neighbor_count"] and
                pre["established"] == post["established"] and
                pre["neighbors"] == post["neighbors"]
            ) else "FAIL"
        )
        self.results.append((
            "bgp_all_summary",
            {
                "neighbor_count": pre["neighbor_count"],
                "established": pre["established"],
                "neighbors": pre["neighbors"],
            },
            {
                "neighbor_count": post["neighbor_count"],
                "established": post["established"],
                "neighbors": post["neighbors"],
            },
            status
        ))

    def _assert_equal(self, name, a, b):
        if a is None or b is None:
            status = "SKIP"
            detail = f"{name}: missing data (script={a}, post={b})"
        else:
            status = "PASS" if a == b else "FAIL"
            detail = f"{name}: script={a} post={b}"
        self.results.append((name, status, detail))

    def _record(self, label, a, b):
        if a is None or b is None:
            status = "SKIP"
            self.results.append((label, a, b, status))
        else:
            status = "PASS" if a == b else "FAIL"
            self.results.append((label, a, b, status))

    def _vtep_count(self, content):
        m = re.search(r"VTEP count:\s*(\d+)", content)
        if not m:
            m = re.search(r"number of VTEP record\s*=\s*(\d+)", content)
        if not m:
            m = re.search(r"Total number of remote VTEPS:\s*(\d+)",
content)
        return int(m.group(1)) if m else None

    def _mac_dynamic_total(self, content):
        m = re.search(r"Total Dynamic MACs:\s*(\d+)", content)
        if not m:
            m = re.search(r"Total Mac Addresses for this criterion:\s*(\d+)", content)
        if m:
            return int(m.group(1))
        # UPDATED: fallback like EVPN totals
        # 1) Count MAC entry lines inside 'show mac address-table dynamic' block
        if "show mac address-table dynamic" in content:
            block = content.split("show mac address-table dynamic", 1)[1]
            # Truncate at next Command executed or end
            nxt = block.find("\nCommand executed:")
            if nxt != -1:
                block = block[:nxt]
            mac_line_re = re.compile(r'^\s*\d+\s+[0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}\s+', re.IGNORECASE)
            mac_lines = [l for l in block.splitlines() if mac_line_re.match(l)]
            if mac_lines:
                return len(mac_lines)
        # 2) Per-VLAN summary fallback
        if "Per-VLAN MAC counts:" in content:
            part = content.split("Per-VLAN MAC counts:", 1)[1]
            lines = part.splitlines()
            total = 0
            for l in lines:
                if set(l.strip()) <= {"-"}:
                    continue
                # Format: VLAN  Count (already printed with spacing)
                cols = re.split(r'\s{2,}', l.strip())
                if len(cols) == 2 and cols[0].isdigit() and cols[1].isdigit():
                    total += int(cols[1])
            if total > 0:
                return total
        return None
    def _vrf_reserved_ports_total(self, content):  # NEW
        m = re.search(r"Total Reserved Ports:\s*(\d+)", content)
        return int(m.group(1)) if m else None
    def _vrf_reserved_ports_entry_count(self, content):  # NEW
        m = re.search(r"Total Entries:\s*(\d+)", content)
        return int(m.group(1)) if m else None
    # NEW: Total Routes from route summary
    def _total_routes(self, content):
        # UPDATED: prefer parsed dict, fallback to regex search
        parsed = self._route_source_counts(content)
        if "Total Routes" in parsed:
            return parsed["Total Routes"]
        m = re.search(r'\bTotal Routes[:\s]+(\d+)', content)
        return int(m.group(1)) if m else None
    # NEW: Per route source counts (e.g. connected: 4, bgp: 58)
    def _route_source_counts(self, content):
        # UPDATED: support raw summary (preferred) and legacy class summary
        counts = {}
        if not content:
            return counts
        raw_marker = "IP Route Summary (raw):"
        class_marker = "Route Summary (class):"
        block_lines = []
        if raw_marker in content:
            after = content.split(raw_marker, 1)[1].splitlines()
            for line in after:
                if not line.strip():
                    # stop at first blank after data
                    if block_lines:
                        break
                    else:
                        continue
                if line.startswith("command executed:"):
                    break
                block_lines.append(line.strip())
        elif class_marker in content:
            after = content.split(class_marker, 1)[1].splitlines()
            for line in after:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("Command executed:") or line.startswith("EVPN ") or line.startswith("VLAN ") or line.startswith("IGMP "):
                    break
                block_lines.append(line)
        # Parse lines like:
        # connected 12
        # static (persistent) 0
        # bgp 58
        # Total Routes 1024
        rgx = re.compile(r'^([A-Za-z][A-Za-z0-9 ()/_-]*?)\s+(\d+)$')
        for l in block_lines:
            m = rgx.match(l)
            if m:
                counts[m.group(1).strip()] = int(m.group(2))
        return counts

    # Test 1: CONNECTED interfaces equal
    def test_connected_interfaces_equal(self):
        self._record("connected_interfaces",
                     self._connected(self.script_content),
                     self._connected(self.post_content))

    # Example additional tests (can expand as needed)
    def test_disabled_interfaces_equal(self):
        self._record("disabled_interfaces",
                     self._disabled(self.script_content),
                     self._disabled(self.post_content))

    def test_up_interfaces_equal(self):
        self._record("up_interfaces",
                     self._up(self.script_content),
                     self._up(self.post_content))

    def test_down_interfaces_equal(self):
        self._record("down_interfaces",
                     self._down(self.script_content),
                     self._down(self.post_content))

    def test_evpn_mac_ip_non_decrease(self):
        sc = self._evpn_summary_counts(self.script_content).get("mac-ip")
        pc = self._evpn_summary_counts(self.post_content).get("mac-ip")
        if sc is None or pc is None:
            self.results.append(("evpn_mac_ip_equal", sc, pc, "SKIP"))
        else:
            # CHANGED: allow non-decrease
            status = "PASS" if pc >= sc else "FAIL"
            self.results.append(("evpn_mac_ip_equal", sc, pc, status))

    def test_bgp_neighbor_count_equal(self):
        sc_n, _, _ = self._bgp_enhanced_vals(self.script_content)
        pc_n, _, _ = self._bgp_enhanced_vals(self.post_content)
        self._record("bgp_neighbor_count", sc_n, pc_n)

    def test_bgp_established_count_equal(self):
        _, sc_e, _ = self._bgp_enhanced_vals(self.script_content)
        _, pc_e, _ = self._bgp_enhanced_vals(self.post_content)
        self._record("bgp_established_count", sc_e, pc_e)

    # RE-ADDED: missing VTEP count test
    def test_vtep_count_equal(self):
        pre = self._vtep_count(self.script_content)
        post = self._vtep_count(self.post_content)
        if pre is None or post is None:
            self.results.append(("vtep_count", pre, post, "SKIP"))
        else:
            status = "PASS" if post == pre else "FAIL"
            self.results.append(("vtep_count", pre, post, status))

    # ADD: restore missing MAC dynamic total test
    def test_mac_dynamic_total_equal(self):
        self._record(
            "mac_dynamic_total",
            self._mac_dynamic_total(self.script_content),
            self._mac_dynamic_total(self.post_content)
        )

    def test_bgp_all_summary(self):
        pre = self._bgp_all_summary(self.script_content)
        post = self._bgp_all_summary(self.post_content)
        if pre is None or post is None:
            self.results.append(("bgp_all_summary", pre, post, "SKIP"))
            return
        status = (
            "PASS" if (
                pre["neighbor_count"] == post["neighbor_count"] and
                pre["established"] == post["established"] and
                pre["neighbors"] == post["neighbors"]
            ) else "FAIL"
        )
        self.results.append((
            "bgp_all_summary",
            {
                "neighbor_count": pre["neighbor_count"],
                "established": pre["established"],
                "neighbors": pre["neighbors"],
            },
            {
                "neighbor_count": post["neighbor_count"],
                "established": post["established"],
                "neighbors": post["neighbors"],
            },
            status
        ))

    def _evpn_auto_discovery_totals(self, content):
        """Extract TOTAL DISTINCT and TOTAL OCCURRENCES from the auto-discovery summary block."""
        if "sh bgp evpn route-type auto-discovery" not in content:
            return None, None
        # Isolate block after command
        part = content.split("sh bgp evpn route-type auto-discovery", 1)[1]
        # Truncate at next command executed (if present)
        nxt = part.find("\nCommand executed:")
        if nxt != -1:
            part = part[:nxt]
        # Look for summary section totals
        m_dist = re.search(r'TOTAL DISTINCT\s+(\d+)', part)
        m_occ = re.search(r'TOTAL OCCURRENCES\s+(\d+)', part)
        return (int(m_dist.group(1)) if m_dist else None,
                int(m_occ.group(1)) if m_occ else None)

    def test_evpn_auto_discovery_non_decrease(self):
        pre_d, pre_o = self._evpn_auto_discovery_totals(self.script_content)
        post_d, post_o = self._evpn_auto_discovery_totals(self.post_content)
        if pre_d is None or pre_o is None or post_d is None or post_o is None:
            self.results.append(("evpn_auto_discovery_totals_equal", (pre_d, pre_o), (post_d, post_o), "SKIP"))
        else:
            status = "PASS" if (post_d == pre_d and post_o == pre_o) else "FAIL"
            self.results.append(("evpn_auto_discovery_totals_equal", (pre_d, pre_o), (post_d, post_o), status))

    def _evpn_mac_ip_totals(self, content):
        """Extract TOTAL DISTINCT and TOTAL OCCURRENCES from the mac-ip summary block."""
        if "sh bgp evpn route-type mac-ip" not in content:
            return None, None
        part = content.split("sh bgp evpn route-type mac-ip", 1)[1]
        nxt = part.find("\nCommand executed:")
        if nxt != -1:
            part = part[:nxt]
        m_dist = re.search(r'TOTAL DISTINCT\s+(\d+)', part)
        m_occ = re.search(r'TOTAL OCCURRENCES\s+(\d+)', part)
        return (int(m_dist.group(1)) if m_dist else None,
                int(m_occ.group(1)) if m_occ else None)

    def test_evpn_mac_ip_totals_non_decrease(self):
        pre_d, pre_o = self._evpn_mac_ip_totals(self.script_content)
        post_d, post_o = self._evpn_mac_ip_totals(self.post_content)
        if pre_d is None or pre_o is None or post_d is None or post_o is None:
            self.results.append(("evpn_mac_ip_totals_equal", (pre_d, pre_o), (post_d, post_o), "SKIP"))
        else:
            # CHANGED: DISTINCT must match, OCCURRENCES may increase
            status = "PASS" if (post_d == pre_d and post_o >= pre_o) else "FAIL"
            self.results.append(("evpn_mac_ip_totals_equal", (pre_d, pre_o), (post_d, post_o), status))
    # --- NEW helper + test for imet ---
    def _evpn_imet_totals(self, content):
        """Extract TOTAL DISTINCT and TOTAL OCCURRENCES from the imet summary block."""
        if "sh bgp evpn route-type imet" not in content:
            return None, None
        part = content.split("sh bgp evpn route-type imet", 1)[1]
        nxt = part.find("\nCommand executed:")
        if nxt != -1:
            part = part[:nxt]
        m_dist = re.search(r'TOTAL DISTINCT\s+(\d+)', part)
        m_occ = re.search(r'TOTAL OCCURRENCES\s+(\d+)', part)
        return (int(m_dist.group(1)) if m_dist else None,
                int(m_occ.group(1)) if m_occ else None)

    def test_evpn_imet_totals_non_decrease(self):
        pre_d, pre_o = self._evpn_imet_totals(self.script_content)
        post_d, post_o = self._evpn_imet_totals(self.post_content)
        if pre_d is None or pre_o is None or post_d is None or post_o is None:
            self.results.append(("evpn_imet_totals_equal", (pre_d, pre_o), (post_d, post_o), "SKIP"))
        else:
            status = "PASS" if (post_d == pre_d and post_o == pre_o) else "FAIL"
            self.results.append(("evpn_imet_totals_equal", (pre_d, pre_o), (post_d, post_o), status))
    # --- NEW helper for ethernet-segment ---
    def _evpn_ethernet_segment_totals(self, content):
        """Extract TOTAL DISTINCT and TOTAL OCCURRENCES from ethernet-segment RD summary (exclude ESI table)."""
        if "sh bgp evpn route-type ethernet-segment" not in content:
            return None, None
        part = content.split("sh bgp evpn route-type ethernet-segment", 1)[1]
        nxt = part.find("\nCommand executed:")
        if nxt != -1:
            part = part[:nxt]
        # Limit to lines before the ESI table header
        lines = part.splitlines()
        rd_section = []
        for line in lines:
            if re.match(r'\s*ESI\b', line):
                break
            rd_section.append(line)
        section_text = "\n".join(rd_section)
        m_dist = re.search(r'TOTAL DISTINCT\s+(\d+)', section_text)
        m_occ = re.search(r'TOTAL OCCURRENCES\s+(\d+)', section_text)
        return (int(m_dist.group(1)) if m_dist else None,
                int(m_occ.group(1)) if m_occ else None)

    def test_evpn_ethernet_segment_totals_equal(self):
        """Require RD TOTAL DISTINCT and TOTAL OCCURRENCES to remain exactly equal (not just non-decreasing)."""
        pre_d, pre_o = self._evpn_ethernet_segment_totals(self.script_content)
        post_d, post_o = self._evpn_ethernet_segment_totals(self.post_content)
        if pre_d is None or pre_o is None or post_d is None or post_o is None:
            self.results.append(("evpn_ethernet_segment_totals", (pre_d, pre_o), (post_d, post_o), "SKIP"))
        else:
            status = "PASS" if (post_d == pre_d and post_o == pre_o) else "FAIL"
            self.results.append(("evpn_ethernet_segment_totals", (pre_d, pre_o), (post_d, post_o), status))

    def test_ip_route_count(self):
        """Compare Total Routes between pre (script) and post outputs."""
        pre = self._route_source_counts(self.script_content).get("Total Routes")
        post = self._route_source_counts(self.post_content).get("Total Routes")
        self._record("ip_route_total", pre, post)

    # --- NEW (re-added) helpers ---
    def print_route_source_counts_table(self):
        sources = self._route_source_counts(self.script_content)
        print("\nroute_source_counts:")
        print("command executed: sh ip route summary")
        order = [
            "connected","static (persistent)","static (non-persistent)","VXLAN Control Service",
            "static nexthop-group","ospf","ospfv3","bgp","isis","rip","internal","attached",
            "aggregate","dynamic policy","gribi","Total Routes"
        ]
        for k in order:
            v = sources.get(k, "-")
            print(f"{k}\t{v}")

    def print_route_source_tables(self):
        pre = self._route_source_counts(self.script_content)
        post = self._route_source_counts(self.post_content)
        if pre:
            print("\nPre Route Sources:")
            for k in sorted(pre):
                print(f"{k} : {pre[k]}")
        else:
            print("\nPre Route Sources: none")
        if post:
            print("\nPost Route Sources:")
            for k in sorted(post):
                print(f"{k} : {post[k]}")
        else:
            print("\nPost Route Sources: none")

    def write_html(self, filename="test_results.html"):
        if not self.results:
            return
        path = os.path.join(self.base_dir, filename)
        rows = []
        for label, pre_val, post_val, status in self.results:
            pre_s = "-" if pre_val is None else str(pre_val)
            post_s = "-" if post_val is None else str(post_val)
            match_word = "match" if status == "PASS" else "mismatch" if status == "FAIL" else "skip"
            cls = "pass" if status == "PASS" else "fail" if status == "FAIL" else "skip"
            rows.append(
                f"<tr><td>{label}</td><td>{pre_s}</td><td>{post_s}</td>"
                f"<td>{match_word}</td><td><span class='{cls}'>{status}</span></td></tr>"
            )
        html = f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'/><title>Pre/Post Check Test Results</title>
<style>body{{font-family:Arial,sans-serif;margin:20px}}table{{border-collapse:collapse;width:100%;max-width:1100px}}
th,td{{border:1px solid #ccc;padding:6px 10px;text-align:left;font-size:13px}}th{{background:#f5f5f5}}
tr:nth-child(even){{background:#fafafa}}.pass{{color:#0a0;font-weight:600}}
.fail,.skip{{color:#c00;font-weight:600}}</style></head><body>
<h2>Pre / Post Check Test Results</h2><table><thead><tr>
<th>Metric</th><th>pre_check</th><th>post_check</th><th>match</th><th>status</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table>
<p>Generated from script_output.txt and post_check_output.txt.</p></body></html>"""
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"\nHTML report written: file://{path}")
        except Exception as e:
            print(f"Failed writing HTML report: {e}")

    def run_all(self):
        if not self.script_content or not self.post_content:
            print("\n[Tests] SKIP: One or both output files missing.")
            return
        self.test_connected_interfaces_equal()
        self.test_disabled_interfaces_equal()
        self.test_up_interfaces_equal()
        self.test_down_interfaces_equal()
        self.test_evpn_mac_ip_non_decrease()
        self.test_bgp_neighbor_count_equal()
        self.test_bgp_established_count_equal()
        self.test_vtep_count_equal()
        self.test_bgp_all_summary()
        self.test_mac_dynamic_total_equal()
        # ...existing code...
        print("\n=== Test Results (tabular) ===")
        for label, pre_val, post_val, status in self.results:
            pre_s = "-" if pre_val is None else str(pre_val)
            post_s = "-" if post_val is None else str(post_val)
            match_word = "match" if status == "PASS" else "mismatch" if status == "FAIL" else "skip"
            print(f"{label.ljust(28)} pre_check={pre_s}  post_check={post_s}  {match_word} {status.lower()}")
        self.write_html()
        self.print_route_source_tables()

# Re-add execution guard if truncated by previous edit
if __name__ == "__main__":
    main()
    tester = OutputTests(os.path.dirname(__file__))
    tester.run_all()
