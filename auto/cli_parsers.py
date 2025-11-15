import os
import re
from eos_cli import (
    InterfacesStatusCount,
    BgpStatus,
    RouteSummary,
    IgmpSnoopingQuerier,
    VlanBrief,
    VlanDynamic,
    EvpnRouteTypes
)
from cli_parsers import NetworkParsers  # renamed from network_parsers
import io
import sys
# NOTE: Core parsing (all regex/block extraction) resides in network_parsers.py.
# This script mainly orchestrates reading test.txt and printing formatted summaries.

def _print_route_summary_table(raw: str):
    parser = NetworkParsers()
    rows = parser.parse_ip_route_summary(raw)
    if not rows:
        print("\nRoute Source Table: none")
        return
    counted_rows = [r for r in rows if r.get("COUNT") is not None]
    if counted_rows:
        name_width = max(len(r["SOURCE"]) for r in counted_rows)
    else:
        name_width = len("SOURCE")
    target_width = max(name_width, 60)
    print("\nRoute Source Table:")
    for r in rows:
        cnt = r.get("COUNT")
        src = r.get("SOURCE", "")
        if cnt is None:
            print(src)
        else:
            print(f"{src.ljust(target_width)}{str(cnt).rjust(4)}")
    print("")

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

def _write_output_file(content: str, filename: str = "script_output.txt"):
    """Write captured script output to a file in the same directory."""
    out_path = os.path.join(os.path.dirname(__file__), filename)
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        print(f"Failed writing {filename}: {e}")

def main():
    _buf = io.StringIO()
    _real_stdout = sys.stdout
    sys.stdout = _buf
    try:
        isc = InterfacesStatusCount()
        isc.display_results()
        bgp = BgpStatus(isc.content)
        bgp.print_bgp_status()
        up, down = isc.count_ip_interfaces()
        conn, dis = isc.count_interfaces()
        est = bgp.count_established_sessions()
        print("\n--- Summary ---")
        print(f"UP: {up} DOWN: {down} CONNECTED: {conn} DISABLED: {dis} ESTABLISHED BGP: {est}")
        # Optional class-based usage (non-breaking)
        rs = RouteSummary(isc.content); rs.print()
        ig = IgmpSnoopingQuerier(isc.content); ig.print()
        vb = VlanBrief(isc.content); vb.print()
        vd = VlanDynamic(isc.content); vd.print()
        ev = EvpnRouteTypes(isc.content); ev.print_summary()
        _print_bgp_evpn_route_type_auto_discovery_from_sample()
        _print_bgp_evpn_route_type_mac_ip_from_sample()
        _print_bgp_evpn_route_type_imet_from_sample()
        _print_bgp_evpn_route_type_ethernet_segment_from_sample()
    finally:
        sys.stdout = _real_stdout
    _out = _buf.getvalue()
    print(_out)  # echo to console once
    _write_output_file(_out, "script_output.txt")

if __name__ == "__main__":
    main()