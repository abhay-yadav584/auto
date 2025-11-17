import os
import re

__all__ = [
    "InterfacesStatusCount",
    "BgpStatus",
    "RouteSummary",
    "IgmpSnoopingQuerier",
    "VlanBrief",
    "VlanDynamic",
    "EvpnRouteTypes",
    "VXLAN",
    "MacAddressTableDynamic",
    "VrfReservedPorts"  # NEW
]

def _fallback_parse_bgp_summary(text: str):
    """
    Fallback parser for 'show bgp summary' when TextFSM templates are unavailable.
    Extracts neighbor lines beginning with an IPv4 address until a non-IP line.
    Returns list of dicts: NEIGHBOR, AS, STATE, NLRI_RCD, NLRI_ACC.
    """
    results = []
    if not text:
        return results
    lines = text.splitlines()
    ip_line_re = re.compile(r'^\s*(\d{1,3}(?:\.\d{1,3}){3})\s+')
    header_re = re.compile(r'^\s*Neighbor\s+.*NLRI\s+Rcd', re.IGNORECASE)
    i = 0
    while i < len(lines):
        if header_re.match(lines[i]):
            i += 1
            while i < len(lines) and re.match(r'^\s*-{4,}', lines[i]):
                i += 1
            while i < len(lines):
                line = lines[i]
                if not ip_line_re.match(line):
                    break
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
                ints = [p for p in parts if p.isdigit()]
                nlri_rcd = nlri_acc = None
                if len(ints) >= 2:
                    nlri_rcd = int(ints[-2]); nlri_acc = int(ints[-1])
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
        i += 1
    return results

def _get_parser():
    """Lazy loader to avoid circular import with cli_parsers. Adds fallback if textfsm unavailable."""
    parser = None
    try:
        from .cli_parsers import NetworkParsers
        parser = NetworkParsers()
    except Exception:
        parser = None
    # Patch parse_bgp_summary if TextFSM missing or raises AttributeError
    if parser:
        need_fallback = False
        try:
            import textfsm  # noqa
            if not (hasattr(textfsm, "TextFSM") and hasattr(textfsm, "TextFSMTemplateError")):
                need_fallback = True
        except Exception:
            need_fallback = True
        orig = getattr(parser, "parse_bgp_summary", None)
        if need_fallback or orig is None:
            parser.parse_bgp_summary = _fallback_parse_bgp_summary
        else:
            def _safe_parse_bgp_summary(txt):
                try:
                    return orig(txt)
                except Exception:
                    return _fallback_parse_bgp_summary(txt)
            parser.parse_bgp_summary = _safe_parse_bgp_summary
    return parser

# --- Ensure InterfacesStatusCount exists (placeholder if already defined) ---
class InterfacesStatusCount:
    # ...existing code...
    def __init__(self, content: str = ""):
        self.content = content or ""
    def read_pre_check_file(self):
        file_path = os.path.join(os.path.dirname(__file__), 'test.txt')
        try:
            with open(file_path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            print(f"Error: The file 'test.txt' was not found in {os.path.dirname(__file__)}")
        except Exception as e:
            print(f"Error reading file: {e}")
        return ""
    def _extract_block(self, markers):
        # ...existing code...
        if not self.content:
            return []
        lines = self.content.splitlines()
        start = None
        for i,l in enumerate(lines):
            low = l.lower()
            if any(m in low for m in markers):
                start = i + 1
                continue
            if start is not None and "#sh " in low and not any(m in low for m in markers):
                return [x for x in lines[start:i] if x.strip()]
        if start is None:
            return []
        return [x for x in lines[start:] if x.strip()]
    def _status_lines(self):
        # ...existing code...
        block = self._extract_block(["#sh interfaces status","show interfaces status"])
        return [l for l in block if l.strip() and not l.lower().startswith("port") and not set(l.strip()) <= {"-"}]
    def _ip_brief_lines(self):
        block = self._extract_block(["#sh ip int br","#sh ip interface brief","show ip interface brief"])
        return [l for l in block if l.strip() and not l.lower().startswith("interface") and not set(l.strip()) <= {"-"}]
    def count_interfaces(self):
        # ...existing code...
        connected=disabled=0
        for line in self._status_lines():
            parts=re.split(r'\s{2,}',line.strip())
            if len(parts)>=3:
                s=parts[2].lower()
                if s=="connected": connected+=1
                elif s=="disabled": disabled+=1
        return connected,disabled
    def count_ip_interfaces(self):
        up=down=0
        for line in self._ip_brief_lines():
            parts=re.split(r'\s{2,}',line.strip())
            if len(parts)>=3:
                s=parts[2].lower()
                if s=="up": up+=1
                elif s=="down": down+=1
        return up,down
    def print_commands(self):
        print("\nCommands executed:")
        print("1. show interfaces status")
        print("2. show ip interface brief")
    def display_results(self):
        if self.content:
            self.print_commands()
            connected,disabled=self.count_interfaces()
            up,down=self.count_ip_interfaces()
            print("\nFrom 'show interfaces status':")
            print(f"Number of interfaces CONNECTED: {connected}")
            print(f"Number of interfaces DISABLED: {disabled}")
            print("\nFrom 'show ip interface brief':")
            print(f"Number of interfaces UP: {up}")
            print(f"Number of interfaces DOWN: {down}")

class BgpStatus:
    # ...existing code...
    def __init__(self, content: str):
        self.content = content or ""

    def _bgp_lines(self):
        if not self.content: return []
        lines=self.content.splitlines()
        start=None
        for i,l in enumerate(lines):
            low=l.lower()
            if "#sh bgp summary" in low or "show bgp summary" in low:
                start=i+1; continue
            if start is not None and "#sh " in low and "bgp summary" not in low:
                return [x for x in lines[start:i] if x.strip()]
        if start is None: return []
        return [x for x in lines[start:] if x.strip()]
    def _bgp_evpn_lines(self):
        if not self.content: return []
        lines=self.content.splitlines()
        start=None
        for i,l in enumerate(lines):
            low=l.lower()
            if "#sh bgp evpn summary" in low or "show bgp evpn summary" in low:
                start=i+1; continue
            if start is not None and "#sh " in low and "bgp evpn summary" not in low:
                return [x for x in lines[start:i] if x.strip()]
        if start is None: return []
        return [x for x in lines[start:] if x.strip()]
    def _records(self):
        recs=[]
        for line in self._bgp_lines():
            low=line.lower()
            if low.startswith("neighbor") or line.startswith("-"): continue
            parts=re.split(r'\s{2,}',line.strip())
            if len(parts)>=7 and parts[0].count('.')==3:
                recs.append(parts)
        return recs
    def get_evpn_prefix_info(self):
        rows=[]
        evpn_lines=self._bgp_evpn_lines()
        if not evpn_lines:
            evpn_lines=[l for l in self._bgp_lines() if "evpn" in l.lower()]
        for line in evpn_lines:
            low=line.lower()
            if low.startswith("neighbor") or line.startswith("-"): continue
            parts=re.split(r'\s{2,}',line.strip())
            if len(parts)<3: parts=line.split()
            if parts and parts[0].count('.')==3 and "evpn" in line.lower():
                nums=[p for p in parts if p.isdigit()]
                if len(nums)>=2:
                    rows.append({"neighbor":parts[0],"pfx_rcd":int(nums[-2]),"pfx_acc":int(nums[-1])})
        return rows
    def count_bgp_neighbors(self): return len(self._records())
    def count_established_sessions(self): return sum(1 for r in self._records() if r[2].lower()=="established")
    def get_nlri_info(self):
        info=[]
        for r in self._records():
            try:
                info.append({"neighbor":r[0],"received":int(r[-2]),"accepted":int(r[-1])})
            except ValueError:
                continue
        return info
    def _print_nlri_table(self,nlri_rows):
        if not nlri_rows:
            print("No NLRI data."); return
        n_w=max(len("Neighbor"),*(len(r["neighbor"]) for r in nlri_rows))
        r_w=max(len("NLRI Rcd"),*(len(str(r["received"])) for r in nlri_rows))
        a_w=max(len("NLRI Acc"),*(len(str(r["accepted"])) for r in nlri_rows))
        header=f"{'Neighbor'.ljust(n_w)}  {'NLRI Rcd'.rjust(r_w)}  {'NLRI Acc'.rjust(a_w)}"
        print("\nNLRI Table:"); print(header); print("-"*len(header))
        for r in nlri_rows:
            print(f"{r['neighbor'].ljust(n_w)}  {str(r['received']).rjust(r_w)}  {str(r['accepted']).rjust(a_w)}")
        total_rcd=sum(r["received"] for r in nlri_rows)
        total_acc=sum(r["accepted"] for r in nlri_rows)
        print("-"*len(header))
        print(f"{'TOTAL'.ljust(n_w)}  {str(total_rcd).rjust(r_w)}  {str(total_acc).rjust(a_w)}")
    def _print_evpn_table(self,rows):
        if not rows:
            print("EVPN Prefix Table: none"); return
        n_w=max(len("Neighbor"),*(len(r["neighbor"]) for r in rows))
        r_w=max(len("PfxRcd"),*(len(str(r["pfx_rcd"])) for r in rows))
        a_w=max(len("PfxAcc"),*(len(str(r["pfx_acc"])) for r in rows))
        header=f"{'Neighbor'.ljust(n_w)}  {'PfxRcd'.rjust(r_w)}  {'PfxAcc'.rjust(a_w)}"
        print("\nEVPN Prefix Table:"); print(header); print("-"*len(header))
        for r in rows:
            print(f"{r['neighbor'].ljust(n_w)}  {str(r['pfx_rcd']).rjust(r_w)}  {str(r['pfx_acc']).rjust(a_w)}")
        print("-"*len(header))
        print(f"{'TOTAL'.ljust(n_w)}  {str(sum(r['pfx_rcd'] for r in rows)).rjust(r_w)}  {str(sum(r['pfx_acc'] for r in rows)).rjust(a_w)}")
    def print_bgp_status(self):
        print("\nCommand executed:\nshow bgp summary")
        print(f"Total BGP Neighbors: {self.count_bgp_neighbors()}")
        print(f"Established Sessions: {self.count_established_sessions()}")
        nlri=self.get_nlri_info()
        self._print_nlri_table(nlri)
        evpn=self.get_evpn_prefix_info()
        self._print_evpn_table(evpn)
    def print_bgp_summary_enhanced(self):
        """
        Enhanced BGP summary output:
        Neighbor count = <total>
        Session state : Established = <established_total>
        <NEIGHBOR>  NLRI Rcd = <NLRI_RCD> NLRI Acc = <NLRI_ACC>
        """
        parser = _get_parser()
        parse_fn = getattr(parser, "parse_bgp_summary", None) if parser else None
        if not parse_fn:
            print("\ncommand executed: show bgp summary (enhanced)")
            print("Neighbor count = 0")
            print("Session state : Established = 0")
            return
        try:
            rows = parse_fn(getattr(self, "content", "") or "")
        except Exception:
            rows = _fallback_parse_bgp_summary(getattr(self, "content", "") or "")
        estab = sum(1 for r in rows if re.sub(r"\d", "", (r.get("STATE") or "")).lower().startswith("estab"))
        print("\ncommand executed: show bgp summary (enhanced)")
        print(f"Neighbor count = {len(rows)}")
        print(f"Session state : Established = {estab}")
        for r in rows:
            nbr = r.get("NEIGHBOR", "?")
            rcd = r.get("NLRI_RCD")
            acc = r.get("NLRI_ACC") if r.get("NLRI_ACC") is not None else rcd
            rcd_s = str(rcd) if rcd is not None else "?"
            acc_s = str(acc) if acc is not None else "?"
            print(f"{nbr}  NLRI Rcd = {rcd_s} NLRI Acc = {acc_s}")

# --- Added simple print helper classes (minimal) ---
class RouteSummary:
    def __init__(self, content: str):
        self.content = content or ""
    def _raw_lines(self):
        if not self.content:
            return []
        # Locate start of "sh ip route summary" command block
        lines = self.content.splitlines()
        start = None
        for i, l in enumerate(lines):
            low = l.lower()
            if "#sh ip route summary" in low or "show ip route summary" in low:
                start = i + 1
                break
        if start is None:
            return []
        block = []
        for l in lines[start:]:
            # Stop at next prompt or another command
            if l.strip().endswith("#") and "#sh" in l:
                break
            block.append(l.rstrip("\n"))
        # Extract only source/count lines plus Total Routes
        out = []
        for l in block:
            if re.match(r'\s*(connected|static|VXLAN Control Service|ospf|ospfv3|bgp|isis|rip|internal|attached|aggregate|dynamic policy|gribi)\b', l) \
               or re.search(r'\bTotal Routes\b', l) \
               or re.match(r'\s*Intra-area:', l) \
               or re.match(r'\s*NSSA External-1:', l) \
               or re.match(r'\s*External:', l) \
               or re.match(r'\s*Level-1:', l):
                out.append(l)
        return out

    def print(self):
        raw = self._raw_lines()
        if raw:
            # NEW: command executed line
            print("\ncommand executed: sh ip route summary")
            print("\nIP Route Summary (raw):")
            for l in raw:
                print(l.lstrip())  # match expected (first line unindented)
            return
        # Fallback to existing parsed summary
        parser = _get_parser()
        rows = parser.parse_ip_route_summary(self.content) if parser else []
        print("\nRoute Summary (class):")
        if not rows:
            print("None"); return
        for r in rows:
            src = r.get("SOURCE")
            cnt = r.get("COUNT")
            if cnt is None:
                print(src)
            else:
                print(f"{src}: {cnt}")

class IgmpSnoopingQuerier:
    def __init__(self, content: str):
        self.content = content or ""
    def print(self):
        parser = _get_parser()
        result = parser.parse_igmp_snooping_querier(self.content) if parser else {"lines": [], "vlan_count": 0}
        print("\nIGMP Snooping Querier (class):")
        lines = result.get("lines", [])
        if not lines:
            print("None"); return
        for l in lines:
            print(l)
        print(f"VLAN count: {result.get('vlan_count')}")

class VlanBrief:
    def __init__(self, content: str):
        self.content = content or ""
    def print(self):
        parser = _get_parser()
        rows = parser.parse_vlan_brief(self.content) if parser else []
        print("\nVLAN Brief (class):")
        if not rows:
            print("None"); return
        for r in rows:
            print(f"{r.get('VLAN')} {r.get('NAME')} {r.get('STATUS')} {r.get('PORTS')}")

class VlanDynamic:
    def __init__(self, content: str):
        self.content = content or ""
    def print(self):
        parser = _get_parser()
        rows = parser.parse_vlan_dynamic(self.content) if parser else []
        print("\nVLAN Dynamic (class):")
        if not rows:
            print("None"); return
        for r in rows:
            print(f"{r.get('VLAN')} {r.get('NAME')} {r.get('STATUS')} {r.get('PORTS')}")

class EvpnRouteTypes:
    def __init__(self, content: str):
        self.content = content or ""
    def print_summary(self):
        parser = _get_parser()
        counts = {}
        if parser:
            for key, fn_name in {
                "auto-discovery": "parse_bgp_evpn_route_type_auto_discovery",
                "mac-ip": "parse_bgp_evpn_route_type_mac_ip",
                "imet": "parse_bgp_evpn_route_type_imet",
                "ethernet-segment": "parse_bgp_evpn_route_type_ethernet_segment",
            }.items():
                fn = getattr(parser, fn_name, None)
                if fn:
                    counts[key] = len(fn(self.content) or [])
        print("\nEVPN Route-Type Summary (class):")
        if not counts:
            print("None"); return
        for k, v in counts.items():
            print(f"{k}: {v} entries")

class VXLAN:
    """Wrapper for 'show vxlan vtep detail' output."""
    def __init__(self, content: str):
        self.content = content or ""
        parser = _get_parser()
        self.vteps = []
        parse_fn = getattr(parser, "parse_vxlan_vtep_detail", None) if parser else None
        if parse_fn:
            try:
                self.vteps = parse_fn(self.content) or []
            except Exception:
                self.vteps = []

    def print_vtep_detail(self):
        print("while parsing command: show vxlan vtep detail")
        print(f"number of VTEP record = {len(self.vteps)}")
        print("\nCommand executed:\nshow vxlan vtep detail")
        print(f"VTEP count: {len(self.vteps)}")
        if not self.vteps:
            print("No VTEP detail data found.")
            return
        for r in self.vteps:
            print(f"  {r['VTEP']}  LearnedVia={r['LEARNED_VIA']}  MACLearning={r['MAC_LEARNING']}  TunnelTypes={r['TUNNEL_TYPES']}")

class MacAddressTableDynamic:
    """Wrapper / printer for 'show mac address-table dynamic'."""
    def __init__(self, content: str):
        self.content = content or ""
        parser = _get_parser()
        parse_fn = getattr(parser, "parse_mac_address_table_dynamic", None) if parser else None
        self.data = parse_fn(self.content) if parse_fn else {"entries": [], "total": None, "per_vlan": {}}

    def print(self):
        print("\nCommand executed:\nshow mac address-table dynamic")
        entries = self.data.get("entries", [])
        total = self.data.get("total")
        if not entries:
            print("No dynamic MAC address entries found.")
            return
        print(f"Total Dynamic MACs: {total if total is not None else len(entries)}")
        # Per-VLAN summary
        per_vlan = self.data.get("per_vlan", {})
        vlan_w = max(len("VLAN"), *(len(v) for v in per_vlan)) if per_vlan else 4
        cnt_w = len("Count")
        header = f"{'VLAN'.ljust(vlan_w)}  {'Count'.rjust(cnt_w)}"
        print("\nPer-VLAN MAC counts:")
        print(header)
        print("-" * len(header))
        for vlan in sorted(per_vlan, key=lambda x: int(x)):
            print(f"{vlan.ljust(vlan_w)}  {str(per_vlan[vlan]).rjust(cnt_w)}")
        print("-" * len(header))

class VrfReservedPorts:
    """Wrapper / printer for 'show vrf reserved-ports'."""
    def __init__(self, content: str):
        self.content = content or ""
        parser = _get_parser()
        parse_fn = getattr(parser, "parse_vrf_reserved_ports", None) if parser else None
        self.data = parse_fn(self.content) if parse_fn else {"entries": [], "total_ports": 0, "total_entries": 0}

    def print(self):
        print("\nCommand executed:\nshow vrf reserved-ports")
        entries = self.data.get("entries", [])
        if not entries:
            print("No reserved ports data found.")
            return
        total_entries = self.data.get("total_entries", len(entries))
        total_ports = self.data.get("total_ports", sum(e.get("COUNT", 0) for e in entries))
        vrf_w = max(len("VRF"), *(len(e.get("VRF","")) for e in entries))
        ports_w = max(len("Ports"), *(len(e.get("PORT_STR","")) for e in entries))
        proto_w = max(len("Protocol"), *(len(e.get("PROTOCOL","")) for e in entries))
        cnt_w = len("Count")
        header = f"{'VRF'.ljust(vrf_w)}  {'Ports'.ljust(ports_w)}  {'Protocol'.ljust(proto_w)}  {'Count'.rjust(cnt_w)}"
        print("Reserved Ports Table:")
        print(header)
        print("-" * len(header))
        for e in entries:
            print(f"{e.get('VRF','').ljust(vrf_w)}  {e.get('PORT_STR','').ljust(ports_w)}  {e.get('PROTOCOL','').ljust(proto_w)}  {str(e.get('COUNT',0)).rjust(cnt_w)}")
        print("-" * len(header))
        print(f"Total Entries: {total_entries}")
        print(f"Total Reserved Ports: {total_ports}")