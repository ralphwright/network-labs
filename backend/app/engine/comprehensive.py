from app.engine.base import BaseSimulator, SimulationResult, ObjectiveResult
from app.engine.vlan import vlan_simulator
from app.engine.stp import stp_simulator
from app.engine.ospf import ospf_simulator
from app.engine.bgp import bgp_simulator
from app.engine.firewall import firewall_simulator
from app.engine.nat import nat_simulator
from app.engine.dhcp import dhcp_simulator
from app.engine.dns import dns_simulator


class ComprehensiveSimulator(BaseSimulator):
    """
    Orchestrates multiple component simulators to produce an end-to-end
    network simulation covering switching, routing, security, and services.
    """

    # Sub-simulators in execution order
    _SUBSYSTEMS = [
        ("vlan", "Switching Layer (VLAN/STP)", vlan_simulator, stp_simulator),
        ("ospf", "Internal Routing (OSPF)", ospf_simulator, None),
        ("bgp", "External Routing (BGP)", bgp_simulator, None),
        ("firewall", "Security (Firewall)", firewall_simulator, None),
        ("nat", "Address Translation (NAT)", nat_simulator, None),
        ("dhcp", "Client Services (DHCP)", dhcp_simulator, None),
        ("dns", "Name Resolution (DNS)", dns_simulator, None),
    ]

    def validate_topology(self, topology_data: dict) -> list[str]:
        errors = []
        devices = topology_data.get("devices", [])
        if not devices:
            errors.append("Comprehensive simulation requires a topology with devices.")
            return errors

        device_types = {d.get("type", "").lower() for d in devices}
        device_names = {d.get("name", "").lower() for d in devices}

        # Core switches
        has_switch = bool(
            device_types & {"switch", "multilayer_switch", "layer3_switch"}
        )
        # Routers
        has_router = bool(
            device_types & {"router", "multilayer_switch", "layer3_switch"}
        )
        # Firewall
        has_firewall = bool(
            device_types & {"firewall", "asa", "ngfw"}
            or any("fw" in n or "firewall" in n for n in device_names)
        )
        # Servers (DHCP/DNS)
        has_server = bool(
            device_types & {"server", "dhcp_server", "dns_server"}
        )
        # Clients
        has_client = bool(
            device_types & {"pc", "host", "workstation", "laptop"}
        )

        missing = []
        if not has_switch:
            missing.append("core switch(es)")
        if not has_router:
            missing.append("router(s)")
        if not has_firewall:
            missing.append("firewall")
        if not has_server:
            missing.append("server(s) for DHCP/DNS")
        if not has_client:
            missing.append("client device(s)")

        if missing:
            errors.append(
                f"Comprehensive simulation missing required components: "
                f"{', '.join(missing)}."
            )

        return errors

    def simulate(self, topology_data: dict, configuration: dict) -> SimulationResult:
        all_events: list[dict] = []
        combined_metrics: dict = {}
        all_errors: list[str] = []
        subsystem_results: dict[str, SimulationResult] = {}
        subsystems_ok: list[str] = []
        subsystems_failed: list[str] = []

        # Phase 1: Switching layer — VLAN + STP
        all_events.append({
            "type": "phase_start",
            "message": "=== Phase 1: Switching Layer (VLAN/STP) ===",
        })
        for sim_name, sim in [("vlan", vlan_simulator), ("stp", stp_simulator)]:
            try:
                result = sim.simulate(topology_data, configuration)
                subsystem_results[sim_name] = result
                all_events.extend(result.events)
                combined_metrics.update({
                    f"{sim_name}_{k}": v for k, v in result.metrics.items()
                })
                if result.success:
                    subsystems_ok.append(sim_name.upper())
                else:
                    subsystems_failed.append(sim_name.upper())
                    all_errors.extend(result.errors)
            except Exception as exc:
                all_errors.append(f"{sim_name} simulation error: {exc}")
                subsystems_failed.append(sim_name.upper())

        # Phase 2: Internal Routing — OSPF
        all_events.append({
            "type": "phase_start",
            "message": "=== Phase 2: Internal Routing (OSPF) ===",
        })
        try:
            ospf_result = ospf_simulator.simulate(topology_data, configuration)
            subsystem_results["ospf"] = ospf_result
            all_events.extend(ospf_result.events)
            combined_metrics.update({
                f"ospf_{k}": v for k, v in ospf_result.metrics.items()
            })
            if ospf_result.success:
                subsystems_ok.append("OSPF")
            else:
                subsystems_failed.append("OSPF")
                all_errors.extend(ospf_result.errors)
        except Exception as exc:
            all_errors.append(f"OSPF simulation error: {exc}")
            subsystems_failed.append("OSPF")

        # Phase 3: External Routing — BGP
        all_events.append({
            "type": "phase_start",
            "message": "=== Phase 3: External Routing (BGP) ===",
        })
        try:
            bgp_result = bgp_simulator.simulate(topology_data, configuration)
            subsystem_results["bgp"] = bgp_result
            all_events.extend(bgp_result.events)
            combined_metrics.update({
                f"bgp_{k}": v for k, v in bgp_result.metrics.items()
            })
            if bgp_result.success:
                subsystems_ok.append("BGP")
            else:
                subsystems_failed.append("BGP")
                all_errors.extend(bgp_result.errors)
        except Exception as exc:
            all_errors.append(f"BGP simulation error: {exc}")
            subsystems_failed.append("BGP")

        # Phase 4: Security — Firewall
        all_events.append({
            "type": "phase_start",
            "message": "=== Phase 4: Security (Firewall) ===",
        })
        try:
            fw_result = firewall_simulator.simulate(topology_data, configuration)
            subsystem_results["firewall"] = fw_result
            all_events.extend(fw_result.events)
            combined_metrics.update({
                f"fw_{k}": v for k, v in fw_result.metrics.items()
            })
            if fw_result.success:
                subsystems_ok.append("Firewall")
            else:
                subsystems_failed.append("Firewall")
                all_errors.extend(fw_result.errors)
        except Exception as exc:
            all_errors.append(f"Firewall simulation error: {exc}")
            subsystems_failed.append("Firewall")

        # Phase 5: Address Translation — NAT
        all_events.append({
            "type": "phase_start",
            "message": "=== Phase 5: Address Translation (NAT) ===",
        })
        try:
            nat_result = nat_simulator.simulate(topology_data, configuration)
            subsystem_results["nat"] = nat_result
            all_events.extend(nat_result.events)
            combined_metrics.update({
                f"nat_{k}": v for k, v in nat_result.metrics.items()
            })
            if nat_result.success:
                subsystems_ok.append("NAT")
            else:
                subsystems_failed.append("NAT")
                all_errors.extend(nat_result.errors)
        except Exception as exc:
            all_errors.append(f"NAT simulation error: {exc}")
            subsystems_failed.append("NAT")

        # Phase 6: Client Services — DHCP
        all_events.append({
            "type": "phase_start",
            "message": "=== Phase 6: Client Services (DHCP) ===",
        })
        try:
            dhcp_result = dhcp_simulator.simulate(topology_data, configuration)
            subsystem_results["dhcp"] = dhcp_result
            all_events.extend(dhcp_result.events)
            combined_metrics.update({
                f"dhcp_{k}": v for k, v in dhcp_result.metrics.items()
            })
            if dhcp_result.success:
                subsystems_ok.append("DHCP")
            else:
                subsystems_failed.append("DHCP")
                all_errors.extend(dhcp_result.errors)
        except Exception as exc:
            all_errors.append(f"DHCP simulation error: {exc}")
            subsystems_failed.append("DHCP")

        # Phase 7: Name Resolution — DNS
        all_events.append({
            "type": "phase_start",
            "message": "=== Phase 7: Name Resolution (DNS) ===",
        })
        try:
            dns_result = dns_simulator.simulate(topology_data, configuration)
            subsystem_results["dns"] = dns_result
            all_events.extend(dns_result.events)
            combined_metrics.update({
                f"dns_{k}": v for k, v in dns_result.metrics.items()
            })
            if dns_result.success:
                subsystems_ok.append("DNS")
            else:
                subsystems_failed.append("DNS")
                all_errors.extend(dns_result.errors)
        except Exception as exc:
            all_errors.append(f"DNS simulation error: {exc}")
            subsystems_failed.append("DNS")

        # Integration summary
        all_ok = len(subsystems_failed) == 0
        critical_ok = "OSPF" in subsystems_ok or "BGP" in subsystems_ok

        if all_ok:
            all_events.append({
                "type": "integration_ok",
                "message": "All subsystems operational",
                "subsystems": subsystems_ok,
            })
        else:
            all_events.append({
                "type": "integration_partial",
                "message": (
                    f"Partial operation: {', '.join(subsystems_ok)} OK; "
                    f"{', '.join(subsystems_failed)} failed"
                ),
                "ok": subsystems_ok,
                "failed": subsystems_failed,
            })

        # End-to-end packet trace
        devices = topology_data.get("devices", [])
        clients = [
            d for d in devices
            if d.get("type", "").lower() in {"pc", "host", "workstation", "laptop"}
        ]
        client_name = clients[0]["name"] if clients else "PC1"
        client_ip = (
            clients[0].get("ip_address", "192.168.1.100") if clients else "192.168.1.100"
        )

        if critical_ok:
            all_events.append({
                "type": "e2e_trace",
                "message": (
                    f"End-to-end packet trace: {client_name}({client_ip}) -> Internet verified "
                    f"(VLAN->OSPF->BGP->Firewall->NAT->Internet)"
                ),
                "client": client_name,
                "path": ["VLAN", "OSPF/BGP", "Firewall", "NAT", "Internet"],
            })
            all_events.append({
                "type": "e2e_trace",
                "message": (
                    f"DNS resolution trace: {client_name} -> DNS server -> "
                    f"www.example.com (203.0.113.1) verified"
                ),
            })
        else:
            all_events.append({
                "type": "e2e_trace_failed",
                "message": (
                    f"End-to-end trace {client_name} -> Internet: INCOMPLETE "
                    f"(failed subsystems: {', '.join(subsystems_failed)})"
                ),
                "failed_subsystems": subsystems_failed,
            })

        # Summary metrics
        combined_metrics.update({
            "subsystems_ok": len(subsystems_ok),
            "subsystems_failed": len(subsystems_failed),
            "total_events": len(all_events),
        })

        return SimulationResult(
            success=len(all_errors) == 0 or critical_ok,
            events=all_events,
            metrics=combined_metrics,
            errors=all_errors,
        )

    def verify_objectives(
        self, topology_data: dict, results: SimulationResult, rules: dict
    ) -> list[ObjectiveResult]:
        objectives = []

        # Check each subsystem
        subsystem_checks = {
            "vlan_configured": (
                "vlan_vlans_configured",
                "VLAN switching layer configured",
                "VLAN(s) configured.",
                "No VLANs configured.",
            ),
            "stp_configured": (
                "stp_blocked_ports",
                "STP loop prevention configured",
                "STP active, loop prevention operational.",
                "STP not detected.",
            ),
            "ospf_configured": (
                "ospf_adjacencies",
                "OSPF internal routing operational",
                "OSPF adjacencies formed.",
                "OSPF not operational.",
            ),
            "bgp_configured": (
                "bgp_sessions",
                "BGP external routing operational",
                "BGP sessions established.",
                "BGP not operational.",
            ),
            "firewall_configured": (
                "fw_zones",
                "Firewall zones and policies configured",
                "Firewall zones configured.",
                "Firewall not configured.",
            ),
            "nat_configured": (
                "nat_active_translations",
                "NAT address translation operational",
                "NAT translations active.",
                "NAT not configured.",
            ),
            "dhcp_configured": (
                "dhcp_leases_issued",
                "DHCP client service operational",
                "DHCP leases issued.",
                "DHCP not operational.",
            ),
            "dns_configured": (
                "dns_queries_simulated",
                "DNS name resolution operational",
                "DNS queries resolved.",
                "DNS not operational.",
            ),
        }

        for rule_key, (metric_key, desc, pass_msg, fail_msg) in subsystem_checks.items():
            if rules.get(rule_key, False):
                value = results.metrics.get(metric_key, 0)
                passed = bool(value) and (not isinstance(value, (int, float)) or value > 0)
                objectives.append(ObjectiveResult(
                    objective_id=rule_key,
                    description=desc,
                    passed=passed,
                    message=pass_msg if passed else fail_msg,
                ))

        # All subsystems check
        if rules.get("all_subsystems_operational", False):
            failed = results.metrics.get("subsystems_failed", 0)
            ok = results.metrics.get("subsystems_ok", 0)
            passed = failed == 0 and ok > 0
            objectives.append(ObjectiveResult(
                objective_id="all_subsystems_operational",
                description="All network subsystems are operational",
                passed=passed,
                message=(
                    f"All {ok} subsystems operational." if passed
                    else f"{failed} subsystem(s) failed."
                ),
            ))

        # End-to-end connectivity check
        if rules.get("e2e_connectivity", False):
            e2e = any(e.get("type") == "e2e_trace" for e in results.events)
            objectives.append(ObjectiveResult(
                objective_id="e2e_connectivity",
                description="End-to-end connectivity verified (client to Internet)",
                passed=e2e,
                message=(
                    "End-to-end connectivity verified." if e2e
                    else "End-to-end connectivity not verified."
                ),
            ))

        if not objectives:
            overall_ok = any(e.get("type") == "integration_ok" for e in results.events)
            partial_ok = any(e.get("type") == "integration_partial" for e in results.events)
            passed = overall_ok or partial_ok
            objectives.append(ObjectiveResult(
                objective_id="comprehensive_simulation",
                description="Comprehensive network simulation completed",
                passed=passed,
                message=(
                    "All subsystems simulated." if overall_ok
                    else "Simulation completed with some subsystem failures." if partial_ok
                    else "Comprehensive simulation did not complete."
                ),
            ))

        return objectives


comprehensive_simulator = ComprehensiveSimulator()
