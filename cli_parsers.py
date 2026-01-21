import re
from typing import List, Dict, Optional

class NetworkParsers:
    # Central EVPN patterns
    _EVPN_PATTERNS = {
        "auto_discovery": re.compile(r'RD:\s*(\d{1,3}(?:\.\d{1,3}){3}:\d+)\s+auto-discovery', re.IGNORECASE),
        "mac_ip": re.compile(
            r'RD:\s*(?P<rd>\d{1,3}(?:\.\d{1,3}){3}:\d+)\s+mac-ip\s+(?P<mac>[0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4})(?:\s+(?P<ip>\d{1,3}(?:\.\d{1,3}){3}))?',
            re.IGNORECASE
        ),
        "imet": re.compile(
            r'RD:\s*(?P<rd>\d{1,3}(?:\.\d{1,3}){3}:\d+)\s+imet(?:\s+(?P<ip>\d{1,3}(?:\.\d{1,3}){3}))?',
            re.IGNORECASE
        ),
        "ethernet_segment": re.compile(
            r'RD:\s*(?P<rd>\d{1,3}(?:\.\d{1,3}){3}:\d+)\s+ethernet-segment\s+(?P<esi>\S+)',
            re.IGNORECASE
        ),
    }

    def parse_ip_route_summary(self, raw: str):
        if not raw: return []
        lines = [l for l in raw.splitlines() if l.strip()]
        out = []
        in_block = False
        for l in lines:
            low = l.lower()
            if "show ip route summary" in low or "#sh ip route summary" in low:
                in_block = True; continue
            if in_block and "#sh " in low and "ip route summary" not in low:
                break
            if in_block:
                m = re.match(r'\s*([A-Za-z0-9\*\+\- ]+?)\s+(\d+)\s*$', l)
                if m:
                    out.append({"SOURCE": m.group(1).rstrip(), "COUNT": int(m.group(2))})
                else:
                    out.append({"SOURCE": l, "COUNT": None})
        return out

    def parse_igmp_snooping_querier(self, raw: str):
        if not raw: return {"lines": [], "vlan_count": 0}
        lines = []
        in_block = False
        for l in raw.splitlines():
            low = l.lower()
            if "show igmp snooping querier" in low or "#sh igmp snooping querier" in low:
                in_block = True; continue
            if in_block and "#sh " in low and "igmp snooping querier" not in low:
                break
            if in_block and l.strip():
                lines.append(l.rstrip())
        vlan_cnt = sum(1 for l in lines if re.search(r'\bvlan\b', l, re.IGNORECASE))
        return {"lines": lines, "vlan_count": vlan_cnt}

    def parse_vlan_brief(self, raw: str):
        if not raw: return []
        rows = []; in_block = False
        for l in raw.splitlines():
            low = l.lower()
            if "show vlan brief" in low or "#sh vlan brief" in low:
                in_block = True; continue
            if in_block and "#sh " in low and "vlan brief" not in low:
                break
            if in_block and l.strip() and not l.lower().startswith("vlan") and not set(l.strip()) <= {"-"}:
                parts = re.split(r'\s{2,}', l.strip())
                if len(parts) >= 3:
                    vlan, name, status = parts[:3]
                    ports = parts[3] if len(parts) > 3 else ""
                    rows.append({"VLAN": vlan, "NAME": name, "STATUS": status, "PORTS": ports})
        return rows

    def parse_vlan_dynamic(self, raw: str):
        if not raw: return []
        rows = []; in_block = False
        for l in raw.splitlines():
            low = l.lower()
            if "show vlan dynamic" in low or "#sh vlan dynamic" in low:
                in_block = True; continue
            if in_block and "#sh " in low and "vlan dynamic" not in low:
                break
            if in_block and l.strip() and not l.lower().startswith("vlan") and not set(l.strip()) <= {"-"}:
                parts = re.split(r'\s{2,}', l.strip())
                if len(parts) >= 3:
                    vlan, name, status = parts[:3]
                    ports = parts[3] if len(parts) > 3 else ""
                    rows.append({"VLAN": vlan, "NAME": name, "STATUS": status, "PORTS": ports})
        return rows

    def parse_bgp_evpn_route_type_auto_discovery(self, raw: str):
        if not raw: return []
        results = []
        for line in raw.splitlines():
            if "auto-discovery" in line.lower() and "rd:" in line.lower():
                m = self._EVPN_PATTERNS["auto_discovery"].search(line)
                if m:
                    results.append({"RD": m.group(1)})
        return results

    def parse_bgp_evpn_route_type_mac_ip(self, raw: str):
        if not raw: return []
        results = []
        pat = self._EVPN_PATTERNS["mac_ip"]
        for line in raw.splitlines():
            if "mac-ip" in line.lower() and "rd:" in line.lower():
                m = pat.search(line)
                if m:
                    results.append({"RD": m.group("rd"), "MAC": m.group("mac"), "IP": m.group("ip")})
        return results

    def parse_bgp_evpn_route_type_imet(self, raw: str):
        if not raw: return []
        results = []
        pat = self._EVPN_PATTERNS["imet"]
        for line in raw.splitlines():
            if "imet" in line.lower() and "rd:" in line.lower():
                m = pat.search(line)
                if m:
                    results.append({"RD": m.group("rd"), "IP": m.group("ip")})
        return results

    def parse_bgp_evpn_route_type_ethernet_segment(self, raw: str):
        if not raw: return []
        results = []
        pat = self._EVPN_PATTERNS["ethernet_segment"]
        for line in raw.splitlines():
            low = line.lower()
            if "ethernet-segment" in low and "rd:" in low:
                m = pat.search(line)
                if m:
                    results.append({"RD": m.group("rd"), "ESI": m.group("esi").rstrip(",;")})
        return results