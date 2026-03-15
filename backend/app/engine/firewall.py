from app.engine.base import BaseSimulator, SimulationResult, ObjectiveResult


class FirewallSimulator(BaseSimulator):
    def validate_topology(self, topology_data: dict) -> list[str]:
        errors = []
        devices = topology_data.get("devices", [])
        firewalls = [
            d for d in devices
            if d.get("type", "").lower() in {
                "firewall", "asa", "ngfw", "palo_alto", "fortinet"
            }
        ]
        if not firewalls:
            errors.append(
                "Firewall simulation requires a firewall device "
                "(type: firewall, asa, ngfw, palo_alto, or fortinet)."
            )
        return errors

    def simulate(self, topology_data: dict, configuration: dict) -> SimulationResult:
        devices = topology_data.get("devices", [])
        events = []
        errors = []

        fw_types = {"firewall", "asa", "ngfw", "palo_alto", "fortinet", "checkpoint"}

        firewalls = [d for d in devices if d.get("type", "").lower() in fw_types]
        if not firewalls:
            firewalls = [d for d in devices if "fw" in d.get("name", "").lower()]
        if not firewalls:
            errors.append("No firewall device found.")
            return SimulationResult(success=False, events=events, errors=errors)

        total_zones = 0
        total_policies = 0
        total_active_sessions = 0
        total_blocked = 0
        total_nat_rules = 0

        for fw_idx, fw in enumerate(firewalls):
            fw_name = fw["name"]
            cfg = configuration.get(fw_name, {})
            fw_cfg = cfg.get("firewall", fw.get("firewall", {}))

            # Zone configuration
            zones = fw_cfg.get("zones", fw.get("zones", [
                {
                    "name": "inside",
                    "interface": f"{fw_name}:eth0",
                    "network": "192.168.1.0/24",
                    "security_level": 100,
                },
                {
                    "name": "outside",
                    "interface": f"{fw_name}:eth1",
                    "network": "203.0.113.0/24",
                    "security_level": 0,
                },
                {
                    "name": "dmz",
                    "interface": f"{fw_name}:eth2",
                    "network": "192.168.100.0/24",
                    "security_level": 50,
                },
            ]))

            zone_names = [z.get("name", f"zone{i}") for i, z in enumerate(zones)]
            total_zones += len(zones)

            events.append({
                "type": "zones_defined",
                "message": (
                    f"Zones defined on {fw_name}: {', '.join(zone_names)}"
                ),
                "device": fw_name,
                "zones": zone_names,
            })

            for zone in zones:
                z_name = zone.get("name", "zone")
                z_iface = zone.get("interface", f"{fw_name}:eth0")
                z_net = zone.get("network", "0.0.0.0/0")
                z_level = zone.get("security_level", 50)
                events.append({
                    "type": "zone_config",
                    "message": (
                        f"Zone {z_name}: interface {z_iface}, network {z_net}, "
                        f"security-level {z_level}"
                    ),
                    "device": fw_name,
                    "zone": z_name,
                    "interface": z_iface,
                    "network": z_net,
                })

            # Zone-based policies
            policies = fw_cfg.get("policies", fw.get("policies", []))
            if not policies:
                # Default policy set: inside->outside permit, outside->inside deny,
                # inside->dmz permit HTTP/HTTPS
                policies = [
                    {
                        "from_zone": "inside",
                        "to_zone": "outside",
                        "action": "permit",
                        "services": ["any"],
                        "stateful": True,
                        "description": "Inside to Internet — stateful permit",
                    },
                    {
                        "from_zone": "outside",
                        "to_zone": "inside",
                        "action": "deny",
                        "services": ["any"],
                        "stateful": False,
                        "description": "Outside to Inside — default deny",
                    },
                    {
                        "from_zone": "inside",
                        "to_zone": "dmz",
                        "action": "permit",
                        "services": ["HTTP", "HTTPS"],
                        "stateful": True,
                        "description": "Inside to DMZ — HTTP/HTTPS only",
                    },
                    {
                        "from_zone": "dmz",
                        "to_zone": "outside",
                        "action": "permit",
                        "services": ["HTTP", "HTTPS", "DNS"],
                        "stateful": True,
                        "description": "DMZ to Internet — web + DNS",
                    },
                    {
                        "from_zone": "outside",
                        "to_zone": "dmz",
                        "action": "permit",
                        "services": ["HTTP", "HTTPS"],
                        "stateful": True,
                        "description": "Internet to DMZ — web services only",
                    },
                ]

            for policy in policies:
                fz = policy.get("from_zone", "inside")
                tz = policy.get("to_zone", "outside")
                action = policy.get("action", "permit").lower()
                services = policy.get("services", ["any"])
                stateful = policy.get("stateful", True)
                desc = policy.get("description", f"{fz}->{tz} {action}")
                svc_str = ", ".join(services)
                stateful_str = " (stateful)" if stateful else ""

                events.append({
                    "type": "firewall_policy",
                    "message": (
                        f"Policy: {fz}->{tz} {action} [{svc_str}]{stateful_str}"
                    ),
                    "device": fw_name,
                    "from_zone": fz,
                    "to_zone": tz,
                    "action": action,
                    "services": services,
                    "stateful": stateful,
                })
                total_policies += 1

            # Stateful inspection simulation
            test_flows = fw_cfg.get("test_flows", fw.get("test_flows", [
                {
                    "src": "192.168.1.5",
                    "dst": "8.8.8.8",
                    "dst_port": 443,
                    "protocol": "tcp",
                    "from_zone": "inside",
                    "to_zone": "outside",
                },
                {
                    "src": "8.8.8.8",
                    "dst": "192.168.1.5",
                    "dst_port": 443,
                    "protocol": "tcp",
                    "from_zone": "outside",
                    "to_zone": "inside",
                    "return_traffic": True,
                },
                {
                    "src": "192.168.1.5",
                    "dst": "192.168.100.10",
                    "dst_port": 80,
                    "protocol": "tcp",
                    "from_zone": "inside",
                    "to_zone": "dmz",
                },
                {
                    "src": "203.0.113.50",
                    "dst": "192.168.1.1",
                    "dst_port": 80,
                    "protocol": "tcp",
                    "from_zone": "outside",
                    "to_zone": "inside",
                    "ips_triggered": True,
                },
            ]))

            connection_table: list[dict] = []

            for flow in test_flows:
                src = flow.get("src", "192.168.1.1")
                dst = flow.get("dst", "8.8.8.8")
                port = flow.get("dst_port", 80)
                proto = flow.get("protocol", "tcp").upper()
                fz = flow.get("from_zone", "inside")
                tz = flow.get("to_zone", "outside")
                is_return = flow.get("return_traffic", False)
                ips_trigger = flow.get("ips_triggered", False)

                # Find matching policy
                matched_policy = None
                for policy in policies:
                    if (
                        policy.get("from_zone") == fz
                        and policy.get("to_zone") == tz
                    ):
                        matched_policy = policy
                        break

                if is_return:
                    # Check connection table for established session
                    existing = any(
                        s.get("src") == dst and s.get("dst") == src
                        for s in connection_table
                    )
                    if existing:
                        events.append({
                            "type": "stateful_return",
                            "message": (
                                f"Return traffic {src}->{dst}: ESTABLISHED (stateful permit)"
                            ),
                            "device": fw_name,
                            "src": src,
                            "dst": dst,
                        })
                        total_active_sessions += 1
                    else:
                        events.append({
                            "type": "stateful_deny",
                            "message": (
                                f"Return traffic {src}->{dst}: "
                                f"NOT in connection table — DROPPED"
                            ),
                            "device": fw_name,
                        })
                        total_blocked += 1
                elif ips_trigger:
                    events.append({
                        "type": "ips_block",
                        "message": (
                            f"IPS: blocked suspicious traffic from {src} "
                            f"(signature match: SQL injection / port scan)"
                        ),
                        "device": fw_name,
                        "src": src,
                    })
                    total_blocked += 1
                elif matched_policy and matched_policy.get("action") == "permit":
                    state = "NEW"
                    connection_table.append({"src": src, "dst": dst, "port": port})
                    events.append({
                        "type": "stateful_new",
                        "message": (
                            f"Stateful: {proto} SYN {src}->{dst}:{port} — {state}"
                        ),
                        "device": fw_name,
                        "src": src,
                        "dst": dst,
                        "state": state,
                    })
                    total_active_sessions += 1
                else:
                    events.append({
                        "type": "policy_deny",
                        "message": (
                            f"Policy deny: {src}->{dst}:{port} "
                            f"({fz}->{tz} default-deny)"
                        ),
                        "device": fw_name,
                        "src": src,
                        "dst": dst,
                    })
                    total_blocked += 1

            # NAT rules (integration)
            nat_rules = fw_cfg.get("nat_rules", fw.get("nat_rules", [
                {
                    "type": "source-nat",
                    "from_zone": "inside",
                    "to_zone": "outside",
                    "src_net": "192.168.1.0/24",
                    "translated_to": "203.0.113.1",
                    "overload": True,
                },
            ]))
            for nat in nat_rules:
                nat_type = nat.get("type", "source-nat")
                events.append({
                    "type": "fw_nat_rule",
                    "message": (
                        f"NAT rule ({nat_type}): "
                        f"{nat.get('from_zone', 'inside')}->{nat.get('to_zone', 'outside')} "
                        f"{nat.get('src_net', 'any')} -> {nat.get('translated_to', 'pool')}"
                        f"{' (overload)' if nat.get('overload') else ''}"
                    ),
                    "device": fw_name,
                    "nat_type": nat_type,
                })
                total_nat_rules += 1

        metrics = {
            "zones": total_zones,
            "policies": total_policies,
            "active_sessions": total_active_sessions,
            "blocked_attempts": total_blocked,
            "nat_rules": total_nat_rules,
        }

        return SimulationResult(
            success=len(errors) == 0 and total_zones > 0,
            events=events,
            metrics=metrics,
            errors=errors,
        )

    def verify_objectives(
        self, topology_data: dict, results: SimulationResult, rules: dict
    ) -> list[ObjectiveResult]:
        objectives = []

        if rules.get("zones_configured", False):
            zones = results.metrics.get("zones", 0)
            passed = zones >= 2
            objectives.append(ObjectiveResult(
                objective_id="zones_configured",
                description="Firewall security zones are configured",
                passed=passed,
                message=(
                    f"{zones} security zone(s) configured." if passed
                    else "Fewer than 2 zones configured."
                ),
            ))

        if rules.get("default_deny", False):
            deny_policy = any(
                e.get("type") == "firewall_policy"
                and e.get("action") == "deny"
                and e.get("from_zone") == "outside"
                for e in results.events
            )
            objectives.append(ObjectiveResult(
                objective_id="default_deny",
                description="Default deny policy on outside zone",
                passed=deny_policy,
                message=(
                    "Default deny policy configured for outside zone." if deny_policy
                    else "No default deny policy found for outside zone."
                ),
            ))

        if rules.get("stateful_inspection", False):
            stateful = any(
                e.get("type") in {"stateful_new", "stateful_return"} for e in results.events
            )
            objectives.append(ObjectiveResult(
                objective_id="stateful_inspection",
                description="Stateful connection tracking is operational",
                passed=stateful,
                message=(
                    "Stateful inspection tracking connections." if stateful
                    else "No stateful inspection detected."
                ),
            ))

        if rules.get("dmz_accessible", False):
            dmz_permit = any(
                e.get("type") == "firewall_policy"
                and e.get("to_zone") == "dmz"
                and e.get("action") == "permit"
                for e in results.events
            )
            objectives.append(ObjectiveResult(
                objective_id="dmz_accessible",
                description="DMZ is accessible from inside (HTTP/HTTPS)",
                passed=dmz_permit,
                message=(
                    "DMZ accessible with permit policy." if dmz_permit
                    else "No permit policy to DMZ found."
                ),
            ))

        if not objectives:
            fw_active = any(e.get("type") == "zones_defined" for e in results.events)
            objectives.append(ObjectiveResult(
                objective_id="firewall_simulation",
                description="Firewall simulation completed",
                passed=fw_active,
                message=(
                    "Firewall zones and policies configured." if fw_active
                    else "Firewall not configured."
                ),
            ))

        return objectives


firewall_simulator = FirewallSimulator()
