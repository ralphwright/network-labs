from app.engine.base import BaseSimulator, SimulationResult, ObjectiveResult


class LacpSimulator(BaseSimulator):
    def validate_topology(self, topology_data: dict) -> list[str]:
        errors = []
        devices = topology_data.get("devices", [])
        connections = topology_data.get("connections", [])

        switches = {
            d["name"]
            for d in devices
            if d.get("type", "").lower() in {"switch", "multilayer_switch", "layer3_switch"}
        }

        if len(switches) < 2:
            errors.append("LACP simulation requires at least 2 switches.")
            return errors

        # Check for parallel links
        link_pairs: dict[frozenset, int] = {}
        for conn in connections:
            src = conn.get("source", conn.get("from", ""))
            dst = conn.get("target", conn.get("to", ""))
            if src in switches and dst in switches:
                pair = frozenset({src, dst})
                link_pairs[pair] = link_pairs.get(pair, 0) + 1

        has_parallel = any(count >= 2 for count in link_pairs.values())
        if not has_parallel:
            errors.append(
                "LACP simulation requires at least 2 parallel links between the same pair of switches."
            )
        return errors

    def simulate(self, topology_data: dict, configuration: dict) -> SimulationResult:
        devices = topology_data.get("devices", [])
        connections = topology_data.get("connections", [])
        events = []
        errors = []

        switches = {
            d["name"]
            for d in devices
            if d.get("type", "").lower() in {"switch", "multilayer_switch", "layer3_switch"}
        }

        # Group parallel links by device pair
        parallel_links: dict[frozenset, list[dict]] = {}
        for conn in connections:
            src = conn.get("source", conn.get("from", ""))
            dst = conn.get("target", conn.get("to", ""))
            if src in switches and dst in switches:
                pair = frozenset({src, dst})
                parallel_links.setdefault(pair, []).append(conn)

        port_channels: list[dict] = []
        total_member_ports = 0
        total_bandwidth = 0
        load_balance_method = "src-dst-mac"

        pc_index = 1
        for pair, links in parallel_links.items():
            if len(links) < 2:
                continue

            pair_list = sorted(pair)
            sw1, sw2 = pair_list[0], pair_list[1]

            for link in links:
                src = link.get("source", link.get("from", sw1))
                dst = link.get("target", link.get("to", sw2))
                src_port = link.get("sourcePort", link.get("source_port", "fa0/1"))
                dst_port = link.get("targetPort", link.get("target_port", "fa0/1"))

                # LACP PDU exchange
                events.append({
                    "type": "lacp_pdu",
                    "message": (
                        f"LACP PDU sent {src}:{src_port} -> {dst}:{dst_port} "
                        f"(Actor: ACTIVE, System {src}, Key {pc_index})"
                    ),
                    "from": src,
                    "to": dst,
                })
                events.append({
                    "type": "lacp_pdu",
                    "message": (
                        f"LACP PDU sent {dst}:{dst_port} -> {src}:{src_port} "
                        f"(Partner: ACTIVE, System {dst}, Key {pc_index})"
                    ),
                    "from": dst,
                    "to": src,
                })

            events.append({
                "type": "lacp_negotiation_complete",
                "message": f"LACP negotiation complete between {sw1} and {sw2}",
                "devices": [sw1, sw2],
            })

            member_count = len(links)
            link_speed_mbps = 1000  # default GigabitEthernet
            agg_bandwidth = member_count * link_speed_mbps
            total_bandwidth += agg_bandwidth
            total_member_ports += member_count

            sw1_cfg = configuration.get(sw1, {})
            sw2_cfg = configuration.get(sw2, {})
            lb_method = (
                sw1_cfg.get("lacp_load_balance", sw2_cfg.get("lacp_load_balance", load_balance_method))
            )

            pc_name = f"Port-Channel{pc_index}"
            port_channels.append({
                "name": pc_name,
                "sw1": sw1,
                "sw2": sw2,
                "member_ports": member_count,
                "bandwidth_mbps": agg_bandwidth,
                "load_balance": lb_method,
            })

            events.append({
                "type": "port_channel_formed",
                "message": (
                    f"{pc_name} formed between {sw1} and {sw2} "
                    f"({member_count} member ports, {agg_bandwidth} Mbps aggregated)"
                ),
                "device": sw1,
                "partner": sw2,
                "members": member_count,
            })

            # Load-balancing detail
            events.append({
                "type": "load_balancing",
                "message": (
                    f"Load balancing: {lb_method} on {pc_name} — "
                    f"traffic distributed across {member_count} links"
                ),
            })

            for i, link in enumerate(links):
                src_port = link.get("sourcePort", link.get("source_port", f"fa0/{i + 1}"))
                dst_port = link.get("targetPort", link.get("target_port", f"fa0/{i + 1}"))
                events.append({
                    "type": "member_port",
                    "message": (
                        f"{pc_name} member: {sw1}:{src_port} <-> {sw2}:{dst_port} "
                        f"(bundled, link {i + 1}/{member_count})"
                    ),
                })

            pc_index += 1

        metrics = {
            "port_channels": len(port_channels),
            "member_ports": total_member_ports,
            "aggregated_bandwidth_mbps": total_bandwidth,
            "load_balance_method": load_balance_method,
        }

        return SimulationResult(
            success=len(errors) == 0 and len(port_channels) > 0,
            events=events,
            metrics=metrics,
            errors=errors,
        )

    def verify_objectives(
        self, topology_data: dict, results: SimulationResult, rules: dict
    ) -> list[ObjectiveResult]:
        objectives = []

        # port_channel_formed
        if rules.get("port_channel_formed", False):
            pc_count = results.metrics.get("port_channels", 0)
            passed = pc_count > 0
            objectives.append(ObjectiveResult(
                objective_id="port_channel_formed",
                description="At least one Port-Channel (LAG) has been formed",
                passed=passed,
                message=f"{pc_count} Port-Channel(s) formed." if passed else "No Port-Channels formed.",
            ))

        # member_ports_count
        if "member_ports_count" in rules:
            expected = int(rules["member_ports_count"])
            actual = results.metrics.get("member_ports", 0)
            passed = actual >= expected
            objectives.append(ObjectiveResult(
                objective_id="member_ports_count",
                description=f"Port-Channel has at least {expected} member ports",
                passed=passed,
                message=f"{actual} member port(s) bundled." if passed else f"Only {actual}/{expected} member ports.",
            ))

        # load_balancing
        if "load_balancing" in rules:
            expected_method = rules["load_balancing"]
            actual_method = results.metrics.get("load_balance_method", "")
            passed = expected_method.lower() in actual_method.lower()
            objectives.append(ObjectiveResult(
                objective_id="load_balancing",
                description=f"Load balancing method '{expected_method}' is configured",
                passed=passed,
                message=f"Load balance: {actual_method}." if passed else f"Expected '{expected_method}', got '{actual_method}'.",
            ))

        if not objectives:
            pc_formed = any(e.get("type") == "port_channel_formed" for e in results.events)
            objectives.append(ObjectiveResult(
                objective_id="port_channel_formed",
                description="Port-Channel formed via LACP",
                passed=pc_formed,
                message="Port-Channel established." if pc_formed else "No Port-Channel detected.",
            ))

        return objectives


lacp_simulator = LacpSimulator()
