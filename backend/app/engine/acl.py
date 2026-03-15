from app.engine.base import BaseSimulator, SimulationResult, ObjectiveResult


class AclSimulator(BaseSimulator):
    def validate_topology(self, topology_data: dict) -> list[str]:
        errors = []
        devices = topology_data.get("devices", [])
        acl_devices = [
            d for d in devices
            if d.get("acl") or d.get("access_lists") or
            d.get("type", "").lower() in {"router", "firewall", "multilayer_switch", "layer3_switch"}
        ]
        if not acl_devices:
            errors.append(
                "ACL simulation requires routers or firewalls with ACL configuration "
                "(set acl or access_lists on device, or use type: router/firewall)."
            )
        return errors

    def _parse_acl_rules(self, raw_rules: list) -> list[dict]:
        """Normalize ACL rule entries into a consistent format."""
        parsed = []
        for idx, rule in enumerate(raw_rules):
            if isinstance(rule, str):
                rule = {"raw": rule}
            action = rule.get("action", "permit").lower()
            protocol = rule.get("protocol", "ip").lower()
            src = rule.get("src", rule.get("source", "any"))
            dst = rule.get("dst", rule.get("destination", "any"))
            dst_port = rule.get("dst_port", rule.get("port", rule.get("eq", None)))
            seq = rule.get("seq", (idx + 1) * 10)
            parsed.append({
                "seq": seq,
                "action": action,
                "protocol": protocol,
                "src": src,
                "dst": dst,
                "dst_port": dst_port,
            })
        return parsed

    def _match_packet(self, packet: dict, rules: list[dict]) -> dict:
        """Match a test packet against ACL rules; returns matched rule or implicit deny."""
        p_src = packet.get("src", "any")
        p_dst = packet.get("dst", "any")
        p_proto = packet.get("protocol", "tcp").lower()
        p_port = packet.get("dst_port", packet.get("port"))

        for rule in rules:
            src_match = rule["src"] in {"any", p_src} or (
                rule["src"].startswith("host ") and rule["src"].split()[1] == p_src
            )
            dst_match = rule["dst"] in {"any", p_dst} or (
                rule["dst"].startswith("host ") and rule["dst"].split()[1] == p_dst
            )
            proto_match = rule["protocol"] in {"ip", p_proto}
            port_match = (
                rule["dst_port"] is None
                or str(rule["dst_port"]) == str(p_port)
                or (rule["dst_port"] in {"http", "www", 80} and p_port in {80, "http", "www"})
                or (rule["dst_port"] in {"telnet", 23} and p_port in {23, "telnet"})
                or (rule["dst_port"] in {"https", 443} and p_port in {443, "https"})
                or (rule["dst_port"] in {"dns", 53} and p_port in {53, "dns"})
                or (rule["dst_port"] in {"ssh", 22} and p_port in {22, "ssh"})
                or (rule["dst_port"] in {"smtp", 25} and p_port in {25, "smtp"})
            )
            if src_match and dst_match and proto_match and port_match:
                return rule
        # Implicit deny
        return {"seq": 9999, "action": "deny", "implicit": True}

    def simulate(self, topology_data: dict, configuration: dict) -> SimulationResult:
        devices = topology_data.get("devices", [])
        events = []
        errors = []

        acl_device_types = {
            "router", "firewall", "multilayer_switch", "layer3_switch"
        }

        # Collect ACL-capable devices
        acl_devices = [
            d for d in devices
            if d.get("type", "").lower() in acl_device_types
            or d.get("acl") or d.get("access_lists")
        ]

        if not acl_devices:
            acl_devices = devices  # fallback

        total_acl_entries = 0
        total_permitted = 0
        total_denied = 0
        interfaces_protected = 0

        for device in acl_devices:
            dname = device["name"]
            cfg = configuration.get(dname, {})
            acl_list = cfg.get("acl", device.get("acl", []))
            if not isinstance(acl_list, list):
                acl_list = [acl_list]
            if not acl_list:
                # Inject a default demo ACL
                acl_list = [{
                    "name": "ACL_100",
                    "type": "extended",
                    "interface": f"{dname}:eth0",
                    "direction": "inbound",
                    "rules": [
                        {"seq": 10, "action": "permit", "protocol": "tcp",
                         "src": "any", "dst": "host 10.0.0.1", "dst_port": 80},
                        {"seq": 20, "action": "permit", "protocol": "tcp",
                         "src": "any", "dst": "host 10.0.0.1", "dst_port": 443},
                        {"seq": 30, "action": "deny", "protocol": "tcp",
                         "src": "any", "dst": "any", "dst_port": 23},
                        {"seq": 40, "action": "deny", "protocol": "tcp",
                         "src": "any", "dst": "any", "dst_port": 22, "comment": "block-ssh"},
                        {"seq": 50, "action": "permit", "protocol": "ip",
                         "src": "192.168.1.0/24", "dst": "any"},
                    ],
                    "test_packets": [
                        {"src": "192.168.1.5", "dst": "10.0.0.1",
                         "protocol": "tcp", "dst_port": 80},
                        {"src": "192.168.1.5", "dst": "10.0.0.1",
                         "protocol": "tcp", "dst_port": 23},
                        {"src": "10.0.0.5", "dst": "172.16.0.1",
                         "protocol": "tcp", "dst_port": 443},
                    ],
                }]

            for acl in acl_list:
                acl_name = acl.get("name", acl.get("id", "ACL_100"))
                acl_type = acl.get("type", "extended").lower()
                interface = acl.get("interface", f"{dname}:eth0")
                direction = acl.get("direction", "inbound")
                raw_rules = acl.get("rules", [])
                test_packets = acl.get("test_packets", [])

                parsed_rules = self._parse_acl_rules(raw_rules)
                total_acl_entries += len(parsed_rules)
                interfaces_protected += 1

                events.append({
                    "type": "acl_applied",
                    "message": (
                        f"ACL {acl_name} ({acl_type}) applied to {interface} {direction} "
                        f"({len(parsed_rules)} rules)"
                    ),
                    "device": dname,
                    "acl": acl_name,
                    "interface": interface,
                    "direction": direction,
                })

                # Process each rule as an event
                for rule in parsed_rules:
                    port_str = f" eq {rule['dst_port']}" if rule["dst_port"] else ""
                    events.append({
                        "type": "acl_rule",
                        "message": (
                            f"ACL {acl_name} seq {rule['seq']}: "
                            f"{rule['action']} {rule['protocol']} "
                            f"{rule['src']} {rule['dst']}{port_str}"
                        ),
                        "device": dname,
                        "acl": acl_name,
                        "rule": rule,
                    })

                # Process test packets
                for pkt in test_packets:
                    matched = self._match_packet(pkt, parsed_rules)
                    action = matched["action"]
                    src = pkt.get("src", "?")
                    dst = pkt.get("dst", "?")
                    port = pkt.get("dst_port", "")
                    proto = pkt.get("protocol", "ip")
                    port_str = f":{port}" if port else ""
                    port_display = f" eq {port}" if port else ""

                    if matched.get("implicit"):
                        events.append({
                            "type": "acl_implicit_deny",
                            "message": (
                                f"Implicit deny: {src}->{dst}{port_str} dropped "
                                f"(no ACL match, default deny)"
                            ),
                            "device": dname,
                            "packet": pkt,
                        })
                        total_denied += 1
                    elif action == "permit":
                        events.append({
                            "type": "acl_permit",
                            "message": (
                                f"Packet {src}->{dst}{port_str}: match permit "
                                f"{proto} {matched['src']} {matched['dst']}{port_display}"
                            ),
                            "device": dname,
                            "packet": pkt,
                            "matched_rule": matched,
                        })
                        total_permitted += 1
                    else:
                        events.append({
                            "type": "acl_deny",
                            "message": (
                                f"Packet {src}->{dst}{port_str}: match deny "
                                f"{proto} {matched['src']} {matched['dst']}{port_display}"
                            ),
                            "device": dname,
                            "packet": pkt,
                            "matched_rule": matched,
                        })
                        total_denied += 1

        metrics = {
            "acl_entries": total_acl_entries,
            "packets_permitted": total_permitted,
            "packets_denied": total_denied,
            "interfaces_protected": interfaces_protected,
        }

        return SimulationResult(
            success=len(errors) == 0 and total_acl_entries > 0,
            events=events,
            metrics=metrics,
            errors=errors,
        )

    def verify_objectives(
        self, topology_data: dict, results: SimulationResult, rules: dict
    ) -> list[ObjectiveResult]:
        objectives = []

        if rules.get("acl_applied", False):
            ifaces = results.metrics.get("interfaces_protected", 0)
            passed = ifaces > 0
            objectives.append(ObjectiveResult(
                objective_id="acl_applied",
                description="ACLs are applied to interfaces",
                passed=passed,
                message=(
                    f"ACLs applied to {ifaces} interface(s)." if passed
                    else "No ACLs applied to any interface."
                ),
            ))

        if rules.get("telnet_blocked", False):
            telnet_denied = any(
                e.get("type") in {"acl_deny", "acl_implicit_deny"}
                and (
                    e.get("packet", {}).get("dst_port") in {23, "telnet"}
                    or "23" in e.get("message", "")
                    or "telnet" in e.get("message", "").lower()
                )
                for e in results.events
            )
            objectives.append(ObjectiveResult(
                objective_id="telnet_blocked",
                description="Telnet (TCP/23) is blocked by ACL",
                passed=telnet_denied,
                message=(
                    "Telnet traffic is blocked by ACL." if telnet_denied
                    else "Telnet traffic is not blocked."
                ),
            ))

        if rules.get("http_permitted", False):
            http_permitted = any(
                e.get("type") == "acl_permit"
                and e.get("packet", {}).get("dst_port") in {80, "http", "www"}
                for e in results.events
            )
            objectives.append(ObjectiveResult(
                objective_id="http_permitted",
                description="HTTP (TCP/80) traffic is permitted by ACL",
                passed=http_permitted,
                message=(
                    "HTTP traffic is permitted." if http_permitted
                    else "HTTP traffic is not explicitly permitted."
                ),
            ))

        if not objectives:
            acl_active = any(e.get("type") == "acl_applied" for e in results.events)
            objectives.append(ObjectiveResult(
                objective_id="acl_simulation",
                description="ACL simulation completed",
                passed=acl_active,
                message=(
                    "ACLs configured and processing packets." if acl_active
                    else "No ACLs detected."
                ),
            ))

        return objectives


acl_simulator = AclSimulator()
