import re
from pathlib import Path
import textfsm
from io import StringIO
from network_parsers import NetworkParsers

PROMPT_LINE = re.compile(r'^.+#sh\s', re.IGNORECASE)
IF_STATUS_LINE = re.compile(
    r'^(?P<port>Et\d+\S*)\s+(?P<name>.+?)\s{2,}(?P<status>connected|disabled)\s{2,}(?P<vlan>.+?)\s{2,}(?P<duplex>full|auto|half)\s+(?P<speed>\S+)\s+(?P<type>\S+)',
    re.IGNORECASE
)
IP_BRIEF_LINE = re.compile(
    r'^(?P<intf>Ethernet\d+(?:/\d+)*)\s+(?P<ipaddr>\S+)\s+(?P<status>up|down)\s+(?P<protocol>up|down)\b',
    re.IGNORECASE
)
BGP_LINE = re.compile(
    r'^(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\s+(?P<asn>\S+)\s+(?P<state>Established|Idle|Active)\s+(?P<afi>.+?)\s+(?:Negotiated|Idle|Active)\s+(?P<rcd>\d+)\s+(?P<acc>\d+)$',
    re.IGNORECASE
)
EVPN_REGEX = re.compile(
    r'^\s*(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\s+\d+\s+\S+\s+\d+\s+\d+\s+\d+\s+\d+\s+\S+\s+\S+\s+(?P<pfxrcd>\d+)\s+(?P<pfxacc>\d+)$',
    re.IGNORECASE
)
VTEP_IP_REGEX = re.compile(r'^(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\s+control plane', re.IGNORECASE)
PARSER = NetworkParsers()

def load_raw():
    p = Path("test.txt")
    if not p.is_file():
        raise FileNotFoundError("test.txt not found.")
    return p.read_text(encoding="utf-8")

def print_nlri_table(rows):
    if not rows:
        print("NLRI Table: none")
        return
    n_w = max(len("Neighbor"), *(len(r["neighbor"]) for r in rows))
    r_w = max(len("NLRI Rcd"), *(len(str(r["received"])) for r in rows))
    a_w = max(len("NLRI Acc"), *(len(str(r["accepted"])) for r in rows))
    header = f"{'Neighbor'.ljust(n_w)}  {'NLRI Rcd'.rjust(r_w)}  {'NLRI Acc'.rjust(a_w)}"
    print("\nNLRI Table:")
    print(header)
    print("-" * len(header))
    for r in rows:
        print(f"{r['neighbor'].ljust(n_w)}  {str(r['received']).rjust(r_w)}  {str(r['accepted']).rjust(a_w)}")
    print("-" * len(header))
    print(f"{'TOTAL'.ljust(n_w)}  {str(sum(r['received'] for r in rows)).rjust(r_w)}  {str(sum(r['accepted'] for r in rows)).rjust(a_w)}")

class Interfaces:
    def __init__(self, raw: str):
        self.raw = raw

    def _extract_block(self, marker: str) -> list[str]:
        lines = self.raw.splitlines()
        start = None
        out = []
        for i, line in enumerate(lines):
            if marker in line.lower():
                start = i + 1
                continue
            if start is not None:
                if PROMPT_LINE.match(line) and marker not in line.lower():
                    break
                if line.strip():
                    out.append(line.rstrip())
        return out

    def parse_interfaces_status(self):
        block = self._extract_block("#sh interfaces status")
        data = [l for l in block if l and not l.lower().startswith("port") and not set(l.strip()) <= {"-"}]
        rows = PARSER.parse_interfaces_status("\n".join(data))
        if rows:
            connected = sum(1 for r in rows if r["STATUS"].lower() == "connected")
            disabled = sum(1 for r in rows if r["STATUS"].lower() == "disabled")
            return connected, disabled
        # fallback
        connected = disabled = 0
        for line in data:
            parts = re.split(r'\s{2,}', line.strip())
            if len(parts) >= 2:
                s = parts[1].lower()
                if s == "connected": connected += 1
                elif s == "disabled": disabled += 1
        return connected, disabled

    def parse_ip_brief(self):
        block = self._extract_block("#sh ip int br")
        data = [l for l in block if l and not l.lower().startswith("interface") and not set(l.strip()) <= {"-"}]
        rows = PARSER.parse_ip_interface_brief("\n".join(data))
        if rows:
            up = sum(1 for r in rows if r["STATUS"].lower() == "up")
            down = sum(1 for r in rows if r["STATUS"].lower() == "down")
            return up, down
        up = down = 0
        for line in data:
            parts = re.split(r'\s{2,}', line.strip())
            if len(parts) >= 3:
                s = parts[2].lower()
                if s == "up": up += 1
                elif s == "down": down += 1
        return up, down

class BGP:
    def __init__(self, raw: str):
        self.raw = raw

    def _extract_block(self, marker: str) -> list[str]:
        lines = self.raw.splitlines()
        start = None
        out = []
        for i, line in enumerate(lines):
            if marker in line.lower():
                start = i + 1
                continue
            if start is not None:
                if PROMPT_LINE.match(line) and marker not in line.lower():
                    break
                if line.strip():
                    out.append(line.rstrip())
        return out

    def parse_bgp_summary(self):
        block = self._extract_block("#sh bgp summary")
        data = [l for l in block if l and not l.lower().startswith("neighbor") and not l.startswith("-")]
        rows = PARSER.parse_bgp_summary("\n".join(data))
        if rows:
            neighbors = len(rows)
            established = sum(1 for r in rows if r["STATE"].lower().startswith("estab"))
            nlri_rows = []
            for r in rows:
                try:
                    nlri_rows.append({
                        "neighbor": r["NEIGHBOR"],
                        "received": int(r["RCD"]),
                        "accepted": int(r["ACC"])
                    })
                except (KeyError, ValueError):
                    pass
            return neighbors, established, nlri_rows
        # Fallback manual parsing
        neighbors = established = 0
        nlri_rows = []
        for line in data:
            parts = re.split(r'\s{2,}', line.strip())
            if len(parts) < 7:
                continue
            if parts[0].count(".") != 3:
                continue
            neighbors += 1
            if parts[2].lower() == "established":
                established += 1
            # Last two numeric tokens as NLRI Rcd / Acc
            nums = [p for p in parts if p.isdigit()]
            if len(nums) >= 2:
                try:
                    nlri_rows.append({
                        "neighbor": parts[0],
                        "received": int(nums[-2]),
                        "accepted": int(nums[-1])
                    })
                except ValueError:
                    pass
        return neighbors, established, nlri_rows

    def _extract_block_evpn(self):
        lines = self.raw.splitlines()
        start = None
        out = []
        for i, line in enumerate(lines):
            low = line.lower()
            if "#sh bgp evpn summary" in low or "show bgp evpn summary" in low:
                start = i + 1
                continue
            if start is not None:
                if PROMPT_LINE.match(line) and "bgp evpn summary" not in low:
                    break
                if line.strip():
                    out.append(line.rstrip())
        return out

    def parse_bgp_evpn_summary(self):
        block = self._extract_block_evpn()
        if not block:
            block = self._extract_block("#sh bgp evpn summary") or self._extract_block("#sh bgp summary")
        data = [l for l in block if l and not l.lower().startswith("neighbor") and not l.startswith("-")]
        rows = PARSER.parse_bgp_evpn_summary("\n".join(data))
        if rows:
            return [
                {
                    "neighbor": r["NEIGHBOR"],
                    "pfx_rcd": int(r["PFXRCD"]),
                    "pfx_acc": int(r["PFXACC"])
                }
                for r in rows
                if r.get("NEIGHBOR")
            ]
        # Fallback: use EVPN_REGEX
        evpn_rows = []
        for line in data:
            m = EVPN_REGEX.match(line.strip())
            if not m:
                continue
            try:
                evpn_rows.append({
                    "neighbor": m.group("ip"),
                    "pfx_rcd": int(m.group("pfxrcd")),
                    "pfx_acc": int(m.group("pfxacc"))
                })
            except ValueError:
                continue
        return evpn_rows

def print_evpn_table(rows):
    if not rows:
        print("EVPN Prefix Table: none")
        return
    n_w = max(len("Neighbor"), *(len(r["neighbor"]) for r in rows))
    r_w = max(len("PfxRcd"), *(len(str(r["pfx_rcd"])) for r in rows))
    a_w = max(len("PfxAcc"), *(len(str(r["pfx_acc"])) for r in rows))
    header = f"{'Neighbor'.ljust(n_w)}  {'PfxRcd'.rjust(r_w)}  {'PfxAcc'.rjust(a_w)}"
    print("\nEVPN Prefix Table:")
    print(header)
    print("-" * len(header))
    for r in rows:
        print(f"{r['neighbor'].ljust(n_w)}  {str(r['pfx_rcd']).rjust(r_w)}  {str(r['pfx_acc']).rjust(a_w)}")
    print("-" * len(header))
    print(f"{'TOTAL'.ljust(n_w)}  {str(sum(r['pfx_rcd'] for r in rows)).rjust(r_w)}  {str(sum(r['pfx_acc'] for r in rows)).rjust(a_w)}")

def parse_vxlan_vtep_detail(raw: str):
    lines = raw.splitlines()
    start = None
    collected = []
    for i, line in enumerate(lines):
        low = line.lower()
        if "#show vxlan vtep detail" in low or "#sh vxlan vtep detail" in low:
            start = i + 1
            continue
        if start is not None:
            if PROMPT_LINE.match(line) and "vxlan vtep detail" not in low:
                break
            if line.strip():
                collected.append(line.rstrip())
    rows = PARSER.parse_vxlan_vtep_detail("\n".join(collected))
    if rows:
        return [r["VTEP"] for r in rows if r.get("VTEP")]
    # Fallback to regex / total line
    vteps = []
    for line in collected:
        m = VTEP_IP_REGEX.match(line.strip())
        if m:
            vteps.append(m.group("ip"))
    if not vteps:
        for line in collected:
            if "total number of remote vteps" in line.lower():
                try:
                    count = int(re.findall(r'\d+', line)[-1])
                    vteps = ["<unknown>"] * count
                except:
                    pass
    return vteps

def _extract_mac_block(raw: str, markers: list[str]) -> list[str]:
    lines = raw.splitlines()
    start = None
    out = []
    for i, line in enumerate(lines):
        low = line.lower()
        if any(m in low for m in markers):
            start = i + 1
            continue
        if start is not None:
            if PROMPT_LINE.match(line) and not any(m in low for m in markers):
                break
            if line.strip():
                out.append(line.rstrip())
    return out

def _extract_section(raw: str, markers: list[str]) -> list[str]:
    lines = raw.splitlines()
    start = None
    collected = []
    for i, line in enumerate(lines):
        low = line.lower()
        if any(m in low for m in markers):
            start = i + 1
            continue
        if start is not None:
            if PROMPT_LINE.match(line):
                break
            collected.append(line.rstrip())
    return collected

# Add regex patterns for MAC entries (dynamic / static)
MAC_DYNAMIC_LINE = re.compile(r'^\s*(\d+)\s+[0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}\s+DYNAMIC\s+\S+', re.IGNORECASE)
MAC_STATIC_LINE  = re.compile(r'^\s*(\d+)\s+[0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}\s+STATIC\s+\S+', re.IGNORECASE)

def parse_mac_address_tables(raw: str):
    # Extract full sections
    dyn_section = _extract_section(raw, ["#show mac address-table dynamic", "#sh mac address-table dynamic"])
    stat_section = _extract_section(raw, ["#show mac address-table static", "#sh mac address-table static"])

    def count_entries(section_lines, pattern):
        count = 0
        for line in section_lines:
            low = line.lower()
            if "total mac addresses for this criterion" in low:
                # Stop before the summary line (we rely on counted entries)
                break
            if pattern.match(line):
                count += 1
        return count

    dynamic_count = count_entries(dyn_section, MAC_DYNAMIC_LINE)
    static_count  = count_entries(stat_section, MAC_STATIC_LINE)

    # Fallback: if regex somehow failed but a total line exists, use it
    if dynamic_count == 0:
        for l in dyn_section:
            if "total mac addresses for this criterion" in l.lower():
                nums = re.findall(r'\d+', l)
                if nums:
                    dynamic_count = int(nums[-1])
                break
    if static_count == 0:
        for l in stat_section:
            if "total mac addresses for this criterion" in l.lower():
                nums = re.findall(r'\d+', l)
                if nums:
                    static_count = int(nums[-1])
                break
    return dynamic_count, static_count

def main():
    raw = load_raw()
    iface = Interfaces(raw)
    bgp = BGP(raw)

    # Interfaces status
    print("Command: sh interfaces status")
    connected, disabled = iface.parse_interfaces_status()
    print(f"Connected interfaces: {connected}")
    print(f"Disabled interfaces: {disabled}")

    # IP brief
    print("\nCommand: sh ip int br")
    ip_up, ip_down = iface.parse_ip_brief()
    print(f"IP interfaces UP: {ip_up}")
    print(f"IP interfaces DOWN: {ip_down}")

    # BGP summary
    print("\nCommand: sh bgp summary")
    bgp_total, bgp_est, nlri_rows = bgp.parse_bgp_summary()
    print(f"BGP neighbors total: {bgp_total}")
    print(f"BGP neighbors established: {bgp_est}")
    print_nlri_table(nlri_rows)

    # BGP EVPN summary
    print("\nCommand: sh bgp evpn summary")
    evpn_rows = bgp.parse_bgp_evpn_summary()
    print_evpn_table(evpn_rows)
    print("\nEVPN Neighbor Prefix Detail:")
    for r in evpn_rows:
        print(f"{r['neighbor']}: PfxRcd={r['pfx_rcd']} PfxAcc={r['pfx_acc']}")

    # VXLAN VTEP detail
    print("\nCommand: show vxlan vtep detail")
    vteps = parse_vxlan_vtep_detail(raw)
    print(f"Remote VTEP count: {len(vteps)}")
    for ip in vteps:
        print(f"VTEP: {ip}")

    # MAC address-table dynamic/static via NetworkParsers
    print("\nCommand: show mac address-table dynamic")
    dyn_count = PARSER.count_mac_dynamic(raw)
    print(f"Dynamic MAC entries: {dyn_count}")

    print("\nCommand: show mac address-table static")
    stat_count = PARSER.count_mac_static(raw)
    print(f"Static MAC entries: {stat_count}")

if __name__ == "__main__":
    main()
