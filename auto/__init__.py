# Minimal package initializer for 'auto'
# Ensures relative imports (eos_cli, cli_parsers) work when running top-level scripts.

from .cli_parsers import NetworkParsers
from .eos_cli import (
    InterfacesStatusCount,
    BgpStatus,
    RouteSummary,
    IgmpSnoopingQuerier,
    VlanBrief,
    VlanDynamic,
    EvpnRouteTypes
)

__all__ = [
    "NetworkParsers",
    "InterfacesStatusCount",
    "BgpStatus",
    "RouteSummary",
    "IgmpSnoopingQuerier",
    "VlanBrief",
    "VlanDynamic",
    "EvpnRouteTypes",
]
