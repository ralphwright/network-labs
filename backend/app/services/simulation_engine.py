import logging
from typing import Any
from app.engine.vlan import vlan_simulator
from app.engine.stp import stp_simulator
from app.engine.ospf import ospf_simulator
from app.engine.lacp import lacp_simulator
from app.engine.dhcp import dhcp_simulator
from app.engine.dns import dns_simulator
from app.engine.bgp import bgp_simulator
from app.engine.mpls import mpls_simulator
from app.engine.tunneling import tunneling_simulator
from app.engine.gre import gre_simulator
from app.engine.autonomous_systems import autonomous_systems_simulator
from app.engine.ipv6 import ipv6_simulator
from app.engine.remote_access import remote_access_simulator
from app.engine.ssh import ssh_simulator
from app.engine.acl import acl_simulator
from app.engine.nat import nat_simulator
from app.engine.pat import pat_simulator
from app.engine.wireless_ap import wireless_ap_simulator
from app.engine.wireless_controller import wireless_controller_simulator
from app.engine.wireless_security import wireless_security_simulator
from app.engine.wireless_topology import wireless_topology_simulator
from app.engine.firewall import firewall_simulator
from app.engine.comprehensive import comprehensive_simulator

logger = logging.getLogger(__name__)

SIMULATOR_MAP = {
    "vlans": vlan_simulator,
    "stp": stp_simulator,
    "ospf": ospf_simulator,
    "lacp": lacp_simulator,
    "dhcp": dhcp_simulator,
    "dns": dns_simulator,
    "bgp": bgp_simulator,
    "mpls": mpls_simulator,
    "tunneling": tunneling_simulator,
    "gre": gre_simulator,
    "autonomous-systems": autonomous_systems_simulator,
    "ipv6": ipv6_simulator,
    "remote-access": remote_access_simulator,
    "ssh": ssh_simulator,
    "acls": acl_simulator,
    "nat": nat_simulator,
    "pat": pat_simulator,
    "wireless-ap": wireless_ap_simulator,
    "wireless-controller": wireless_controller_simulator,
    "wireless-security": wireless_security_simulator,
    "wireless-topology": wireless_topology_simulator,
    "firewalls": firewall_simulator,
    "comprehensive": comprehensive_simulator,
}


class SimulationEngine:
    def run_simulation(self, lab: Any, topology_data: dict, configuration: dict) -> dict:
        simulator = SIMULATOR_MAP.get(lab.slug)
        if not simulator:
            return {
                "success": False,
                "packet_traces": [],
                "events": [{"type": "error", "message": f"No simulator for lab: {lab.slug}"}],
                "metrics": {},
                "errors": [f"Unknown lab type: {lab.slug}"],
                "objectives": [],
            }

        try:
            errors = simulator.validate_topology(topology_data)
            if errors:
                return {
                    "success": False,
                    "packet_traces": [],
                    "events": [{"type": "validation_error", "message": e} for e in errors],
                    "metrics": {},
                    "errors": errors,
                    "objectives": [],
                }

            result = simulator.simulate(topology_data, configuration)
            objective_results = simulator.verify_objectives(
                topology_data, result, lab.verification_rules or {}
            )

            passed = sum(1 for o in objective_results if o.passed)
            total = len(objective_results)

            return {
                "success": result.success,
                "packet_traces": result.packet_traces,
                "events": result.events,
                "metrics": result.metrics,
                "errors": result.errors,
                "objectives": [
                    {
                        "objective_id": o.objective_id,
                        "description": o.description,
                        "passed": o.passed,
                        "message": o.message,
                    }
                    for o in objective_results
                ],
                "score": int((passed / total * 100)) if total > 0 else 0,
            }
        except Exception as e:
            logger.exception(f"Simulation error for lab {lab.slug}: {e}")
            return {
                "success": False,
                "packet_traces": [],
                "events": [],
                "metrics": {},
                "errors": [str(e)],
                "objectives": [],
                "score": 0,
            }
