from pathlib import Path

directory = Path(__file__).resolve().parent / "route-map"
input_path = directory / "multicast_route_maps.txt"
input_lines = [line.strip() for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]
output_name = input_lines[0]
route_maps = input_lines[1:]

config_lines = []
for route_map in route_maps:
	config_lines.append(f"route-map {route_map} permit 310")
	config_lines.append("   match ip address prefix-list PL-MKT-CDS-LE245-MCA-SOURCES")
	config_lines.append(f"route-map {route_map} permit 320")
	config_lines.append("   match ip address prefix-list PL-MKT-CDS-LE245-MCB-SOURCES")

output_path = directory / f"{output_name}.txt"
output_path.write_text("\n".join(config_lines) + ("\n" if config_lines else ""), encoding="utf-8")
