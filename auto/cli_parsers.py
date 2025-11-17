import os
import re
from .eos_cli import (
    InterfacesStatusCount,
    BgpStatus,
    RouteSummary,
    IgmpSnoopingQuerier,
    VlanBrief,
    VlanDynamic,
    EvpnRouteTypes,
    VXLAN,
    MacAddressTableDynamic
)
# REMOVED: from cli_parsers import NetworkParsers  # circular / self-import

# NEW: safe loader / stub for NetworkParsers to avoid NameError before patching
try:
    from .network_parsers import NetworkParsers  # if a dedicated module exists
except ImportError:
    try:
        # If running outside package context, fallback absolute
        from network_parsers import NetworkParsers
    except Exception:
        class NetworkParsers:
            pass

import io
import sys
# NOTE: Core parsing (all regex/block extraction) resides in network_parsers.py.
# This script mainly orchestrates reading test.txt and printing formatted summaries.

def _print_route_summary_table(raw: str):
    # REPLACED with raw printer (no parsing)
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

def _write_output_file(content: str, filename: str = "script_output.txt"):
    """Write captured script output to a file in the same directory."""
    out_path = os.path.join(os.path.dirname(__file__), filename)
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        print(f"Failed writing {filename}: {e}")

def _print_bgp_evpn_summary(raw: str):
    parser = NetworkParsers()
    rows = parser.parse_bgp_evpn_neighbor_summary(raw)
    print("\nCommand executed:\nsh bgp evpn summary")
    if not rows:
        print("No EVPN summary neighbor data found.")
        return
    estab = sum(1 for r in rows if r["STATE"].lower().startswith("estab"))
    print(f"Neighbor count: {len(rows)}  Established: {estab}")

def _strip_plain_bgp_summary(text: str) -> str:
    """
    Remove the plain 'Command executed:\\nshow bgp summary' block from output.
    Keeps enhanced summary and other sections.
    """
    if not text:
        return text
    lines = text.splitlines()
    out = []
    skip = False
    for i, line in enumerate(lines):
        if not skip and line.strip() == "Command executed:" and i + 1 < len(lines) and lines[i+1].strip() == "show bgp summary":
            skip = True
            continue
        if skip:
            # End block when we hit a blank line or next 'Command executed:' (other command) or 'sh bgp evpn summary'
            if line.strip() == "" or line.startswith("Command executed:") or line.strip().startswith("sh bgp evpn summary"):
                skip = False
                # If this line is start of next section we keep it
                if line.strip():
                    out.append(line)
            continue
        out.append(line)
    return "\n".join(out)

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
        rs = RouteSummary(isc.content); rs.print()
        ig = IgmpSnoopingQuerier(isc.content); ig.print()
        vb = VlanBrief(isc.content); vb.print()
        vd = VlanDynamic(isc.content); vd.print()
        ev = EvpnRouteTypes(isc.content); ev.print_summary()
        _print_bgp_evpn_summary(isc.content)
        VXLAN(isc.content).print_vtep_detail()
        _print_bgp_evpn_route_type_auto_discovery_from_sample()
    finally:
        sys.stdout = _real_stdout
    _out = _buf.getvalue()
    _out = _strip_plain_bgp_summary(_out)
    print(_out)
    _write_output_file(_out, "script_output.txt")

if __name__ == "__main__":
    main()

# Add / patch parse_bgp_summary inside NetworkParsers
try:
    NetworkParsers
except NameError:
    class NetworkParsers:
        # Placeholder; real file should already contain other parse_* methods.
        pass

if not hasattr(NetworkParsers, "parse_bgp_summary"):
    class NetworkParsers(NetworkParsers):
        # ...existing code...

        def parse_bgp_summary(self, text: str):
            """
            Parse only the 'show bgp summary' neighbor table.
            Neighbor lines are taken ONLY from the block that begins with the header
            starting 'Neighbor' (containing NLRI columns) and the following dashed
            separator line. Parsing stops at the first line that does not start with
            an IPv4 address.
            Returns list of dicts with NEIGHBOR, AS, STATE, NLRI_RCD, NLRI_ACC.
            """
            results = []
            if not text:
                return results

            lines = text.splitlines()
            ip_line_re = re.compile(r'^\s*(\d{1,3}(?:\.\d{1,3}){3})\s+')
            header_re = re.compile(r'^\s*Neighbor\s+.*NLRI\s+Rcd', re.IGNORECASE)

            i = 0
            while i < len(lines):
                # Locate header line that marks start of the table
                if header_re.match(lines[i]):
                    i += 1
                    # Skip dashed/separator lines
                    while i < len(lines) and re.match(r'^\s*-{4,}', lines[i]):
                        i += 1
                    # Consume neighbor rows
                    while i < len(lines):
                        line = lines[i]
                        if not ip_line_re.match(line):
                            break  # end of neighbor block
                        parts = re.split(r'\s+', line.strip())
                        if len(parts) < 4:
                            i += 1
                            continue
                        neighbor = parts[0]
                        asn = parts[1]
                        raw_state = parts[2]
                        norm_state = re.sub(r'\d', '', raw_state)
                        ls = norm_state.lower()
                        if ls.startswith("estab"):
                            state = "Established"
                        elif ls.startswith("idle"):
                            state = "Idle"
                        elif ls.startswith("active"):
                            state = "Active"
                        else:
                            state = norm_state
                        # Last two integer tokens = NLRI Rcd / Acc (if present)
                        ints = [p for p in parts if p.isdigit()]
                        nlri_rcd = nlri_acc = None
                        if len(ints) >= 2:
                            nlri_rcd = int(ints[-2])
                            nlri_acc = int(ints[-1])
                        elif len(ints) == 1:
                            nlri_rcd = nlri_acc = int(ints[-1])
                        results.append({
                            "NEIGHBOR": neighbor,
                            "AS": asn,
                            "STATE": state,
                            "NLRI_RCD": nlri_rcd,
                            "NLRI_ACC": nlri_acc
                        })
                        i += 1
                    # Continue scanning (support multiple VRF blocks)
                i += 1
            return results

def parse_show_bgp_summary(output: str) -> dict:
    """
    Wrapper: count unique neighbor IPs from the parsed BGP summary table.
    """
    parser = NetworkParsers()
    rows = parser.parse_bgp_summary(output) or []
    neighbors = sorted({r["NEIGHBOR"] for r in rows if r.get("NEIGHBOR")})
    return {
        "neighbor_count": len(neighbors),
        "neighbors": neighbors
    }

# ---- REPLACE wrapper: show bgp evpn summary now parses neighbor table ----
def parse_show_bgp_evpn_summary(output: str) -> dict:
    """
    Parse 'show bgp evpn summary' neighbor table (not route-type counts).
    Returns dict:
      {
        'neighbor_count': <int>,
        'established_count': <int>,
        'neighbors': [ip,...],
        'entries': [ {NEIGHBOR, VERSION, AS, MSG_RCV, MSG_SNT, INQ, OUTQ,
                      UP_DOWN, STATE, PFX_RCD, PFX_ACC}, ... ],
        'total_pfx_rcd': <int>,
        'total_pfx_acc': <int>
      }
    """
    parser = NetworkParsers()
    rows = parser.parse_bgp_evpn_neighbor_summary(output) or []
    neighbors = [r["NEIGHBOR"] for r in rows]
    estab = sum(1 for r in rows if r["STATE"].lower().startswith("estab"))
    total_rcd = sum(r["PFX_RCD"] for r in rows if r["PFX_RCD"] is not None)
    total_acc = sum(r["PFX_ACC"] for r in rows if r["PFX_ACC"] is not None)
    return {
        "neighbor_count": len(neighbors),
        "established_count": estab,
        "neighbors": neighbors,
        "entries": rows,
        "total_pfx_rcd": total_rcd,
        "total_pfx_acc": total_acc
    }

try:
    PARSERS["show bgp evpn summary"] = parse_show_bgp_evpn_summary
except NameError:
    pass

# ---- Add neighbor-style EVPN summary parser if missing ----
if not hasattr(NetworkParsers, "parse_bgp_evpn_neighbor_summary"):
    class NetworkParsers(NetworkParsers):
        # ...existing code...

        def parse_bgp_evpn_neighbor_summary(self, text: str):
            """
            Parse neighbor lines from 'show bgp evpn summary'.
            Expected header then lines like:
              10.4.228.1 4 64100.21001  10817487  12924096    0    0  191d18h Estab   3839   3839
            Returns list of dicts with keys:
              NEIGHBOR, VERSION, AS, MSG_RCV, MSG_SNT, INQ, OUTQ, UP_DOWN, STATE, PFX_RCD, PFX_ACC
            """
            results = []
            if not text:
                return results
            ip_re = re.compile(r'^\s*(\d{1,3}(?:\.\d{1,3}){3})\s+')
            # Strip leading spaces, collapse multiple spaces
            for line in text.splitlines():
                if not ip_re.match(line):
                    continue
                # Skip if this is part of a different context (sanity: must contain MsgRcvd-style numeric columns)
                parts = re.split(r'\s+', line.strip())
                if len(parts) < 11:
                    continue
                try:
                    neighbor = parts[0]
                    version = parts[1]
                    asn = parts[2]
                    msg_rcv = int(parts[3])
                    msg_snt = int(parts[4])
                    inq = int(parts[5])
                    outq = int(parts[6])
                    up_down = parts[7]
                    state = parts[8]
                    # Remaining two columns could be pref received/accepted
                    # Sometimes state might be split (e.g. Estab vs Established); we handle simple forms.
                    # If state token is not alpha (rare), skip line.
                    if not re.match(r'[A-Za-z]', state):
                        continue
                    pfx_rcd = None
                    pfx_acc = None
                    # Last two numeric tokens
                    tail_nums = [p for p in parts[9:] if p.isdigit()]
                    if len(tail_nums) >= 2:
                        pfx_rcd = int(tail_nums[-2])
                        pfx_acc = int(tail_nums[-1])
                    elif len(tail_nums) == 1:
                        pfx_rcd = pfx_acc = int(tail_nums[-1])
                    results.append({
                        "NEIGHBOR": neighbor,
                        "VERSION": version,
                        "AS": asn,
                        "MSG_RCV": msg_rcv,
                        "MSG_SNT": msg_snt,
                        "INQ": inq,
                        "OUTQ": outq,
                        "UP_DOWN": up_down,
                        "STATE": state,
                        "PFX_RCD": pfx_rcd,
                        "PFX_ACC": pfx_acc
                    })
                except Exception:
                    # Ignore malformed line
                    continue
            return results

# Patch NetworkParsers with parse_bgp_evpn_summary if missing.
if not hasattr(NetworkParsers, "parse_bgp_evpn_summary"):
    class NetworkParsers(NetworkParsers):
        # ...existing code...

        def parse_bgp_evpn_summary(self, text: str):
            """
            Parse 'show bgp evpn summary' route-type table.
            Expected lines (examples):
              1 - Ethernet Auto-Discovery          10          10
              2 - MAC/IP Advertisement            500         500
              3 - Inclusive Multicast Ethernet Tag  4           4
              4 - Ethernet Segment                  2           2
              5 - IP Prefix                        20          20
              Total                               536         536
            Returns list of dicts:
              {
                'ROUTE_TYPE_NUM': <int|None>,  # None for Total line
                'ROUTE_TYPE_NAME': <str>,
                'PATHS': <int|None>,
                'ADVERTISED': <int|None>
              }
            """
            results = []
            if not text:
                return results
            # Accept hyphen or ' - ' after number; capture name until two numeric columns.
            line_re = re.compile(
                r'^\s*(?:(?P<num>[1-5])\s*-\s*)?(?P<name>[A-Za-z ].*?)\s+(?P<paths>\d+)\s+(?P<adv>\d+)\s*$'
            )
            total_re = re.compile(r'^\s*Total\s+(?P<paths>\d+)\s+(?P<adv>\d+)\s*$')
            for line in text.splitlines():
                if not line.strip():
                    continue
                m_total = total_re.match(line)
                if m_total:
                    results.append({
                        "ROUTE_TYPE_NUM": None,
                        "ROUTE_TYPE_NAME": "Total",
                        "PATHS": int(m_total.group("paths")),
                        "ADVERTISED": int(m_total.group("adv"))
                    })
                    continue
                m = line_re.match(line)
                if not m:
                    continue
                num = m.group("num")
                name = m.group("name").strip()
                paths = m.group("paths")
                adv = m.group("adv")
                # Filter out header/separator lines
                if name.lower().startswith("route type") or set(name) == set("-"):
                    continue
                results.append({
                    "ROUTE_TYPE_NUM": int(num) if num is not None else None,
                    "ROUTE_TYPE_NAME": name,
                    "PATHS": int(paths) if paths is not None else None,
                    "ADVERTISED": int(adv) if adv is not None else None
                })
            return results

# ---- Override: robust 'show vxlan vtep detail' parser (always replace) ----
class NetworkParsers(NetworkParsers):
    # ...existing code...

    def parse_vxlan_vtep_detail(self, text: str):
        """
        Parse 'show vxlan vtep detail' output.
        Returns list of dicts:
          { VTEP, LEARNED_VIA, MAC_LEARNING, TUNNEL_TYPES }
        """
        results = []
        if not text:
            return results
        lines = text.splitlines()

        # Locate header line
        header_idx = None
        for i, line in enumerate(lines):
            if re.search(r'\bVTEP\s+Learned Via\s+MAC Address Learning', line):
                header_idx = i
                break
        if header_idx is None:
            return results

        # Advance past header and any dashed separator lines
        i = header_idx + 1
        while i < len(lines) and re.match(r'\s*-{5,}', lines[i]):
            i += 1

        ip_re = re.compile(r'^\d{1,3}(?:\.\d{1,3}){3}$')

        while i < len(lines):
            raw = lines[i].rstrip()
            if not raw:
                break
            low = raw.lower()
            if low.startswith("total number of remote vteps"):
                break
            if raw.strip().endswith("#"):  # prompt / next command
                break
            # Split into columns by 2+ spaces
            parts = re.split(r'\s{2,}', raw.strip())
            if len(parts) < 4:
                i += 1
                continue
            vtep, learned_via, mac_learning, tunnel_types = parts[0:4]
            if not ip_re.match(vtep):
                i += 1
                continue
            results.append({
                "VTEP": vtep,
                "LEARNED_VIA": learned_via.strip(),
                "MAC_LEARNING": mac_learning.strip(),
                "TUNNEL_TYPES": tunnel_types.strip()
            })
            i += 1
        return results

# ---- Add parser for 'show mac address-table dynamic' if missing ----
if not hasattr(NetworkParsers, "parse_mac_address_table_dynamic"):
    class NetworkParsers(NetworkParsers):
        # ...existing code...

        def parse_mac_address_table_dynamic(self, text: str):
            """
            Parse 'show mac address-table dynamic' section.
            Returns dict:
              {
                'entries': [ {VLAN, MAC, TYPE, PORTS, MOVES, LAST_MOVE}, ... ],
                'total': <int|None>,
                'per_vlan': { vlan: count, ... }
              }
            """
            if not text:
                return {"entries": [], "total": None, "per_vlan": {}}
            lines = text.splitlines()
            # Find start marker line containing 'Mac Address Table' followed by header with 'Vlan'
            start = None
            for i, l in enumerate(lines):
                if l.strip().startswith("Mac Address Table"):
                    # scan ahead for header
                    for j in range(i+1, min(i+10, len(lines))):
                        if re.match(r'\s*Vlan\s+Mac Address\s+Type\s+Ports', lines[j]):
                            start = j + 1
                            break
                if start:
                    break
            if start is None:
                return {"entries": [], "total": None, "per_vlan": {}}
            entries = []
            total = None
            data_re = re.compile(
                r'^\s*(\d+)\s+([0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4})\s+(\S+)\s+(\S+)\s+(\d+)\s+(.+?)\s*$',
                re.IGNORECASE
            )
            for k in range(start, len(lines)):
                line = lines[k].rstrip()
                if not line:
                    continue
                m_total = re.search(r'Total Mac Addresses for this criterion:\s*(\d+)', line)
                if m_total:
                    total = int(m_total.group(1))
                    break
                m = data_re.match(line)
                if m:
                    vlan, mac, typ, ports, moves, last_move = m.groups()
                    entries.append({
                        "VLAN": vlan,
                        "MAC": mac.lower(),
                        "TYPE": typ,
                        "PORTS": ports,
                        "MOVES": int(moves),
                        "LAST_MOVE": last_move
                    })
            per_vlan = {}
            for e in entries:
                per_vlan[e["VLAN"]] = per_vlan.get(e["VLAN"], 0) + 1
            return {"entries": entries, "total": total, "per_vlan": per_vlan}

# ---- Force override: regex-based 'show vrf reserved-ports' parser (TextFSM-free) ----
class NetworkParsers(NetworkParsers):
    # ...existing code...

    def parse_vrf_reserved_ports(self, text: str):
        """
        Parse 'show vrf reserved-ports' output.
        Counts every VRF line even if Reserved ports is 'None'.
        Returns:
          {
            'entries': [ {VRF, PORT_STR, PORT_START, PORT_END, PROTOCOL, COUNT}, ... ],
            'total_ports': <int>,        # sum of COUNT (only numeric/range ports)
            'total_entries': <int>       # number of VRF rows
          }
        """
        if not text:
            return {"entries": [], "total_ports": 0, "total_entries": 0}

        lines = text.splitlines()
        # Locate block start
        start = None
        for i, l in enumerate(lines):
            low = l.lower()
            if "show vrf reserved-ports" in low or "#show vrf reserved-ports" in low or "#sh vrf reserved-ports" in low:
                start = i + 1
                break
        if start is None:
            return {"entries": [], "total_ports": 0, "total_entries": 0}

        # Collect until blank line or next prompt
        block = []
        for l in lines[start:]:
            if l.strip().startswith("EMEA-") and "#sh" in l:
                break
            if l.strip().startswith("EMEA-") and l.strip().endswith("#"):
                break
            if l.strip() == "":
                # allow trailing blank; stop
                break
            block.append(l.rstrip())

        entries = []
        # Skip header/separator lines
        sep_re = re.compile(r'^-+')
        header_detected = False
        row_re = re.compile(r'^\s*(?P<vrf>\S[^\s]*)\s+(?P<ports>(None|none|\d+(?:-\d+)?))(?:\s+|$)', re.IGNORECASE)

        for l in block:
            ls = l.strip()
            if not ls:
                continue
            if "VRF" in ls and "Reserved" in ls:
                header_detected = True
                continue
            if sep_re.match(ls):
                continue
            m = row_re.match(l)
            if not m:
                # tolerate lines with extra spacing; attempt manual split
                parts = [p for p in re.split(r'\s{2,}', ls) if p]
                if len(parts) >= 2:
                    vrf = parts[0]
                    ports_field = parts[1]
                else:
                    continue
            else:
                vrf = m.group("vrf")
                ports_field = m.group("ports")

            ports_field_clean = ports_field.strip()
            count = 0
            p_start = p_end = None
            proto = ""  # protocol not shown in this variant; leave blank
            if ports_field_clean.lower() != "none":
                # Single number or range
                if "-" in ports_field_clean:
                    a, b = ports_field_clean.split("-", 1)
                    try:
                        p_start = int(a); p_end = int(b)
                        if p_end >= p_start:
                            count = p_end - p_start + 1
                    except ValueError:
                        p_start = p_end = None
                else:
                    try:
                        p_start = p_end = int(ports_field_clean)
                        count = 1
                    except ValueError:
                        p_start = p_end = None
            entries.append({
                "VRF": vrf,
                "PORT_STR": ports_field_clean,
                "PORT_START": p_start,
                "PORT_END": p_end,
                "PROTOCOL": proto,
                "COUNT": count
            })

        total_ports = sum(e["COUNT"] for e in entries)
        return {
            "entries": entries,
            "total_ports": total_ports,
            "total_entries": len(entries)
        }