from pathlib import Path

input_path = Path(__file__).resolve().parent / "route-map" / "unicast_route_maps.txt"
input_lines = input_path.read_text(encoding="utf-8-sig").splitlines()
header = input_lines[0].strip() if input_lines else ""
header_label, separator, device_name = header.partition("-")
device_name = device_name.strip()
if header_label.strip().casefold() != "unicast route maps" or not separator or not device_name:
	raise ValueError("First line must be 'Unicast route maps-<device name>'.")
route_maps = [line.strip() for line in input_lines[1:] if line.strip()]

config_lines = []
for route_map in route_maps:
	config_lines.append(f"route-map {route_map} permit 150")
	config_lines.append("   match ip address prefix-list PL-MKT-CDS-LE245-OE-VIPS")

output_path = Path(__file__).resolve().parent / "route-map" / f"{device_name}_unicast.txt"
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text("\n".join(config_lines) + "\n", encoding="utf-8")