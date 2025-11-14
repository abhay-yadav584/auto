import textfsm
from io import StringIO
import re

class NetworkParsers:
    _templates = {
        "interfaces_status": r"""
Value PORT (\S+)
Value NAME (.+?)
Value STATUS (\S+)
Value VLAN (.+?)
Value DUPLEX (\S+)
Value SPEED (\S+)
Value TYPE (\S+)

Start
  ^${PORT}\s+${NAME}\s{2,}${STATUS}\s{2,}${VLAN}\s{2,}${DUPLEX}\s+${SPEED}\s+${TYPE} -> Record
""",
        "ip_interface_brief": r"""
Value INTERFACE (\S+)
Value IPADDR (\S+)
Value STATUS (up|down|\S+)
Value PROTOCOL (up|down|\S+)

Start
  ^${INTERFACE}\s+${IPADDR}\s+${STATUS}\s+${PROTOCOL}\s+ -> Record
""",
        "bgp_summary": r"""
Value NEIGHBOR (\d+\.\d+\.\d+\.\d+)
Value AS (\S+)
Value STATE (Established|Idle|Active|\S+)
Value AFI (\S+)
Value SAFI (\S+)
Value AFI_STATE (\S+)
Value RCD (\d+)
Value ACC (\d+)

Start
  ^${NEIGHBOR}\s+${AS}\s+${STATE}\s+${AFI}\s+${SAFI}\s+${AFI_STATE}\s+${RCD}\s+${ACC} -> Record
""",
        "bgp_evpn_summary": r"""
Value NEIGHBOR (\d+\.\d+\.\d+\.\d+)
Value V (\d+)
Value AS (\S+)
Value MSGRCVD (\d+)
Value MSGSENT (\d+)
Value INQ (\d+)
Value OUTQ (\d+)
Value UPTIME (\S+)
Value STATE (Estab|Established|Idle|Active|\S+)
Value PFXRCD (\d+)
Value PFXACC (\d+)

Start
  ^\s*${NEIGHBOR}\s+${V}\s+${AS}\s+${MSGRCVD}\s+${MSGSENT}\s+${INQ}\s+${OUTQ}\s+${UPTIME}\s+${STATE}\s+${PFXRCD}\s+${PFXACC}\s*$ -> Record
""",
        "vxlan_vtep_detail": r"""
Value VTEP (\d+\.\d+\.\d+\.\d+)
Value LEARNED (\S+(?:\s+\S+)*)
Value MACLEARN (\S+(?:\s+\S+)*)
Value TUNNEL (\S+(?:,\s*\S+)*)

Start
  ^${VTEP}\s+${LEARNED}\s+${MACLEARN}\s+${TUNNEL}\s*$ -> Record
""",
        "mac_table_dynamic": r"""
Value VLAN (\d+)
Value MAC (\S+)
Value TYPE (DYNAMIC)
Value PORTS (\S+)
Value MOVES (\d+)
Value LASTMOVE (.+)

Start
  ^${VLAN}\s+${MAC}\s+${TYPE}\s+${PORTS}\s+${MOVES}\s+${LASTMOVE}\s*$ -> Record
""",
        "mac_table_static": r"""
Value VLAN (\d+)
Value MAC (\S+)
Value TYPE (STATIC)
Value PORTS (\S+)

Start
  ^${VLAN}\s+${MAC}\s+${TYPE}\s+${PORTS}\s*$ -> Record
""",
        "vrf_reserved_ports": r"""
Value VRF (\S.+?)
Value RESERVED (\S+)
Value COMMENT (.*)

Start
  ^\s*${VRF}\s+${RESERVED}\s+${COMMENT}\s*$ -> Record
"""
    }

    def _parse(self, key: str, text: str):
        if not text.strip():
            return []
        try:
            fsm = textfsm.TextFSM(StringIO(self._templates[key].strip()))
            rows = fsm.ParseText(text)
            return [dict(zip(fsm.header, r)) for r in rows]
        except textfsm.TextFSMTemplateError:
            return []

    def parse_interfaces_status(self, text: str):
        return self._parse("interfaces_status", text)

    def parse_ip_interface_brief(self, text: str):
        return self._parse("ip_interface_brief", text)

    def parse_bgp_summary(self, text: str):
        return self._parse("bgp_summary", text)

    def parse_bgp_evpn_summary(self, text: str):
        return self._parse("bgp_evpn_summary", text)

    def parse_vxlan_vtep_detail(self, text: str):
        return self._parse("vxlan_vtep_detail", text)

    def parse_mac_table_dynamic(self, text: str):
        return self._parse("mac_table_dynamic", text)

    def parse_mac_table_static(self, text: str):
        return self._parse("mac_table_static", text)

    def extract_block(self, raw: str, markers: list[str], prompt_regex=r'^.+#sh\s') -> list[str]:
        """Return lines for the first matched command block (without the command line)."""
        if not raw:
            return []
        lines = raw.splitlines()
        start = None
        out = []
        prompt_pat = re.compile(prompt_regex, re.IGNORECASE)
        for i, line in enumerate(lines):
            low = line.lower()
            if any(m in low for m in markers):
                start = i + 1
                continue
            if start is not None:
                if prompt_pat.match(line) and not any(m in low for m in markers):
                    break
                if line.strip():
                    out.append(line.rstrip())
        return out

    def _count_mac_entries(self, lines: list[str], entry_type: str) -> int:
        """Manual fallback counting when TextFSM fails."""
        if entry_type.lower() == "dynamic":
            pattern = re.compile(r'^\s*\d+\s+[0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}\s+DYNAMIC\s+\S+', re.IGNORECASE)
        else:
            pattern = re.compile(r'^\s*\d+\s+[0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}\s+STATIC\s+\S+', re.IGNORECASE)
        count = 0
        for line in lines:
            low = line.lower()
            if "total mac addresses for this criterion" in low:
                break
            if pattern.match(line):
                count += 1
        return count

    def parse_vrf_summary(self, raw: str):
        # Extract lines after the command until next prompt
        lines = raw.splitlines()
        start = None
        block = []
        for i, line in enumerate(lines):
            low = line.lower()
            if "#show  vrf summary" in low or "#show vrf summary" in low or "#sh vrf summary" in low:
                start = i + 1
                continue
            if start is not None:
                if re.search(r'#sh\s|#show\s', line.lower()) and "vrf summary" not in low:
                    break
                if line.strip():
                    block.append(line.strip())
        # Parse counts
        counts = {"vrf_count": None, "vrf_up": None, "vrf_ipv4": None, "vrf_ipv6": None}
        for l in block:
            m = re.match(r'VRF count:\s+(\d+)', l)
            if m: counts["vrf_count"] = int(m.group(1)); continue
            m = re.match(r'VRF up count:\s+(\d+)', l)
            if m: counts["vrf_up"] = int(m.group(1)); continue
            m = re.match(r'VRF IPv4 routing count:\s+(\d+)', l)
            if m: counts["vrf_ipv4"] = int(m.group(1)); continue
            m = re.match(r'VRF IPv6 routing count:\s+(\d+)', l)
            if m: counts["vrf_ipv6"] = int(m.group(1)); continue
        return counts

    def count_mac_dynamic(self, raw: str) -> int:
        block = self.extract_block(raw, ["#show mac address-table dynamic", "#sh mac address-table dynamic"])
        data = [l for l in block
                if l and not l.lower().startswith("vlan") and not l.startswith("-")
                and "total mac addresses" not in l.lower()
                and "multicast mac address table" not in l.lower()]
        rows = self._parse("mac_table_dynamic", "\n".join(data))
        if rows:
            return len(rows)
        return self._count_mac_entries(data, "dynamic")

    def count_mac_static(self, raw: str) -> int:
        block = self.extract_block(raw, ["#show mac address-table static", "#sh mac address-table static"])
        data = [l for l in block
                if l and not l.lower().startswith("vlan") and not l.startswith("-")
                and "total mac addresses" not in l.lower()
                and "multicast mac address table" not in l.lower()]
        rows = self._parse("mac_table_static", "\n".join(data))
        if rows:
            return len(rows)
        return self._count_mac_entries(data, "static")

    def parse_vrf_reserved_ports(self, raw: str):
        lines = raw.splitlines()
        start_idx = None
        for i, line in enumerate(lines):
            low = line.lower()
            if "#show vrf reserved-ports" in low or "#sh vrf reserved-ports" in low:
                start_idx = i + 1
                break
        if start_idx is None:
            return []
        block = []
        prompt_re = re.compile(r'^[A-Za-z0-9._-]+#')
        for line in lines[start_idx:]:
            low = line.lower()
            if (prompt_re.match(line) and "vrf reserved-ports" not in low):
                break
            if line.strip():
                block.append(line.rstrip())
        if not block:
            return []
        # Updated filtering: drop header and any separator lines (dashes/spaces)
        sep_re = re.compile(r'^[\s-]+$')  # only dashes and spaces
        data = [
            l for l in block
            if l.strip()
            and not l.lstrip().lower().startswith("vrf")
            and not re.fullmatch(r'[-\s]+', l)
        ]
        if not data:
            return []
        parsed = self._parse("vrf_reserved_ports", "\n".join(data))
        if parsed:
            return parsed
        rows = []
        row_re = re.compile(r'^\s*(?P<vrf>\S.+?)\s{2,}(?P<reserved>\S+)(?:\s{2,}(?P<comment>.*))?$')
        for l in data:
            m = row_re.match(l)
            if m:
                rows.append({
                    "VRF": m.group("vrf").strip(),
                    "RESERVED": m.group("reserved").strip(),
                    "COMMENT": (m.group("comment") or "").strip()
                })
        return rows

    def parse_vrf_reserved_ports_names(self, raw: str):
        return [r["VRF"] for r in self.parse_vrf_reserved_ports(raw)]

__all__ = ["NetworkParsers"]
