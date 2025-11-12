import textfsm
from io import StringIO
import re

class NetworkParsers:
    _templates = {
        "interfaces_status": """
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
        "ip_interface_brief": """
Value INTERFACE (\S+)
Value IPADDR (\S+)
Value STATUS (up|down|\S+)
Value PROTOCOL (up|down|\S+)

Start
  ^${INTERFACE}\s+${IPADDR}\s+${STATUS}\s+${PROTOCOL}\s+ -> Record
""",
        "bgp_summary": """
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
        "bgp_evpn_summary": """
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
        "vxlan_vtep_detail": """
Value VTEP (\d+\.\d+\.\d+\.\d+)
Value LEARNED (\S+(?:\s+\S+)*)
Value MACLEARN (\S+(?:\s+\S+)*)
Value TUNNEL (\S+(?:,\s*\S+)*)

Start
  ^${VTEP}\s+${LEARNED}\s+${MACLEARN}\s+${TUNNEL}\s*$ -> Record
""",
        "mac_table_dynamic": """
Value VLAN (\d+)
Value MAC (\S+)
Value TYPE (DYNAMIC)
Value PORTS (\S+)
Value MOVES (\d+)
Value LASTMOVE (.+)

Start
  ^${VLAN}\s+${MAC}\s+${TYPE}\s+${PORTS}\s+${MOVES}\s+${LASTMOVE}\s*$ -> Record
""",
        "mac_table_static": """
Value VLAN (\d+)
Value MAC (\S+)
Value TYPE (STATIC)
Value PORTS (\S+)

Start
  ^${VLAN}\s+${MAC}\s+${TYPE}\s+${PORTS}\s*$ -> Record
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

__all__ = ["NetworkParsers"]
