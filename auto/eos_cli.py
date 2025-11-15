import os
import re
from .cli_parsers import NetworkParsers  # fixed: removed self-import that caused circular import

class InterfacesStatusCount:
    # ...existing code...
    def __init__(self):
        self.content = self.read_pre_check_file()
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
    def __init__(self,content):
        self.content=content
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

class RouteSummary:
    # ...existing code...
    def __init__(self,raw:str):
        self.raw=raw; self.parser=NetworkParsers()
    def rows(self): return self.parser.parse_ip_route_summary(self.raw)
    def print(self):
        rows=self.rows()
        if not rows:
            print("\nRoute Source Table: none"); return
        counted=[r for r in rows if r.get("COUNT") is not None]
        name_width=max(len(r["SOURCE"]) for r in counted) if counted else len("SOURCE")
        target_width=max(name_width,60)
        print("\nRoute Source Table (class):")
        for r in rows:
            cnt=r.get("COUNT")
            if cnt is None: print(r.get("SOURCE",""))
            else: print(f"{r.get('SOURCE','').ljust(target_width)}{str(cnt).rjust(4)}")
        print("")

class IgmpSnoopingQuerier:
    # ...existing code...
    def __init__(self,raw:str):
        self.raw=raw; self.parser=NetworkParsers()
    def data(self): return self.parser.parse_igmp_snooping_querier(self.raw)
    def print(self):
        d=self.data()
        print("\nshow igmp snooping querier (class):")
        if not d["lines"]:
            print("No output."); return
        for l in d["lines"]: print(l)
        print(f"VLAN record count: {d['vlan_count']}")

class VlanBrief:
    # ...existing code...
    def __init__(self,raw:str):
        self.raw=raw; self.parser=NetworkParsers()
    def rows(self): return self.parser.parse_vlan_brief(self.raw)
    def print(self):
        rows=self.rows()
        print("\nshow vlan brief (class):")
        if not rows: print("No data."); return
        v_w=max(len("VLAN"),*(len(r["VLAN"]) for r in rows))
        n_w=max(len("Name"),*(len(r["NAME"]) for r in rows))
        s_w=max(len("Status"),*(len(r["STATUS"]) for r in rows))
        header=f"{'VLAN'.ljust(v_w)}  {'Name'.ljust(n_w)}  {'Status'.ljust(s_w)}  Ports"
        print(header); print("-"*len(header))
        for r in rows:
            print(f"{r['VLAN'].ljust(v_w)}  {r['NAME'].ljust(n_w)}  {r['STATUS'].ljust(s_w)}  {r['PORTS']}")
        print("-"*len(header)); print(f"Total VLANs: {len(rows)}")

class VlanDynamic:
    # ...existing code...
    def __init__(self,raw:str):
        self.raw=raw; self.parser=NetworkParsers()
    def rows(self): return self.parser.parse_vlan_dynamic(self.raw)
    def print(self):
        rows=self.rows()
        print("\nshow vlan dynamic (class):")
        if not rows: print("No data."); return
        v_w=max(len("VLAN"),*(len(r["VLAN"]) for r in rows))
        n_w=max(len("Name"),*(len(r["NAME"]) for r in rows))
        s_w=max(len("Status"),*(len(r["STATUS"]) for r in rows))
        header=f"{'VLAN'.ljust(v_w)}  {'Name'.ljust(n_w)}  {'Status'.ljust(s_w)}  Ports"
        print(header); print("-"*len(header))
        for r in rows:
            print(f"{r['VLAN'].ljust(v_w)}  {r['NAME'].ljust(n_w)}  {r['STATUS'].ljust(s_w)}  {r['PORTS']}")
        print("-"*len(header)); print(f"Total Dynamic VLANs: {len(rows)}")

class EvpnRouteTypes:
    # ...existing code...
    def __init__(self,raw:str):
        self.raw=raw; self.parser=NetworkParsers()
    def auto_discovery(self): return self.parser.parse_bgp_evpn_route_type_auto_discovery(self.raw)
    def mac_ip(self): return self.parser.parse_bgp_evpn_route_type_mac_ip(self.raw)
    def imet(self): return self.parser.parse_bgp_evpn_route_type_imet(self.raw)
    def ethernet_segment(self):
        fn=getattr(self.parser,"parse_bgp_evpn_route_type_ethernet_segment",None)
        return fn(self.raw) if fn else []
    def _count(self,rows,key):
        c={}
        for r in rows:
            v=r.get(key)
            if v: c[v]=c.get(v,0)+1
        return c
    def print_summary(self):
        print("\nEVPN Route-Type Summary (class):")
        ad=self.auto_discovery(); mac=self.mac_ip(); im=self.imet(); eth=self.ethernet_segment()
        print(f"auto-discovery: {len(ad)} entries")
        print(f"mac-ip: {len(mac)} entries")
        print(f"imet: {len(im)} entries")
        if eth: print(f"ethernet-segment: {len(eth)} entries")