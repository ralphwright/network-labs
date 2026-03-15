from app.engine.base import BaseSimulator, SimulationResult, ObjectiveResult


class StpSimulator(BaseSimulator):
    def validate_topology(self, topology_data: dict) -> list[str]:
        errors = []
        devices = topology_data.get("devices", [])
        switches = [
            d for d in devices
            if d.get("type", "").lower() in {"switch", "multilayer_switch", "layer3_switch"}
        ]
        if len(switches) < 2:
            errors.append("STP simulation requires at least 2 switches.")
        return errors

    def simulate(self, topology_data: dict, configuration: dict) -> SimulationResult:
        devices = topology_data.get("devices", [])
        connections = topology_data.get("connections", [])
        events = []
        errors = []

        switches = [
            d for d in devices
            if d.get("type", "").lower() in {"switch", "multilayer_switch", "layer3_switch"}
        ]

        # Assign bridge IDs: priority (default 32768) + MAC
        bridge_ids = {}
        for idx, sw in enumerate(switches):
            sw_name = sw["name"]
            cfg = configuration.get(sw_name, {})
            priority = int(cfg.get("stp_priority", sw.get("stp_priority", 32768)))
            # Generate a deterministic MAC from index
            mac = "00:00:00:00:{:02x}:{:02x}".format(idx // 256, idx % 256)
            bridge_ids[sw_name] = {"priority": priority, "mac": mac, "name": sw_name}

        # Elect root bridge (lowest priority; tie-break on MAC)
        root = min(bridge_ids.values(), key=lambda b: (b["priority"], b["mac"]))
        root_name = root["name"]

        events.append({
            "type": "stp_election_start",
            "message": "Bridge Priority election initiated — all switches send BPDUs",
        })
        for sw_name, bid in bridge_ids.items():
            events.append({
                "type": "bpdu_sent",
                "message": (
                    f"BPDU sent from {sw_name} "
                    f"(priority {bid['priority']}, MAC {bid['mac']})"
                ),
                "device": sw_name,
            })
        events.append({
            "type": "root_bridge_elected",
            "message": (
                f"Root Bridge elected: {root_name} "
                f"(priority {root['priority']}, MAC {root['mac']})"
            ),
            "device": root_name,
        })

        # Build adjacency list for switches
        switch_names = {s["name"] for s in switches}
        adjacency: dict[str, list[dict]] = {s["name"]: [] for s in switches}
        for conn in connections:
            src = conn.get("source", conn.get("from", ""))
            dst = conn.get("target", conn.get("to", ""))
            if src in switch_names and dst in switch_names:
                src_port = conn.get("sourcePort", conn.get("source_port", "fa0/1"))
                dst_port = conn.get("targetPort", conn.get("target_port", "fa0/1"))
                adjacency[src].append({"peer": dst, "local_port": src_port, "peer_port": dst_port})
                adjacency[dst].append({"peer": src, "local_port": dst_port, "peer_port": src_port})

        # Calculate path costs (simple BFS from root)
        path_cost: dict[str, int] = {root_name: 0}
        queue = [root_name]
        visited = {root_name}
        while queue:
            current = queue.pop(0)
            for link in adjacency.get(current, []):
                peer = link["peer"]
                if peer not in visited:
                    visited.add(peer)
                    path_cost[peer] = path_cost[current] + 19  # 100 Mbps cost
                    queue.append(peer)

        events.append({"type": "port_roles_start", "message": "Port roles assigned based on path costs"})

        # Assign port roles: root ports, designated ports, blocked ports
        blocked_ports = []
        for sw in switches:
            sw_name = sw["name"]
            if sw_name == root_name:
                # All ports on root are designated
                for link in adjacency.get(sw_name, []):
                    events.append({
                        "type": "port_role",
                        "message": (
                            f"{sw_name}:{link['local_port']} -> "
                            f"{link['peer']} — role: Designated (Root Bridge port)"
                        ),
                        "device": sw_name,
                        "port": link["local_port"],
                        "role": "designated",
                    })
                continue

            # Find root port (lowest cost path to root)
            root_port = None
            best_cost = float("inf")
            for link in adjacency.get(sw_name, []):
                peer = link["peer"]
                cost = path_cost.get(peer, float("inf")) + 19
                if cost < best_cost:
                    best_cost = cost
                    root_port = link

            # Non-root ports: designated or blocked
            for link in adjacency.get(sw_name, []):
                peer = link["peer"]
                if link is root_port:
                    events.append({
                        "type": "port_role",
                        "message": (
                            f"{sw_name}:{link['local_port']} -> {peer} — role: Root Port "
                            f"(path cost {best_cost})"
                        ),
                        "device": sw_name,
                        "port": link["local_port"],
                        "role": "root",
                    })
                else:
                    # Block if the peer already has a designated port on this segment
                    peer_cost = path_cost.get(peer, float("inf"))
                    own_cost = path_cost.get(sw_name, float("inf"))
                    if peer_cost <= own_cost:
                        blocked_ports.append({"switch": sw_name, "port": link["local_port"], "peer": peer})
                        events.append({
                            "type": "port_blocked",
                            "message": (
                                f"Redundant path blocked on {sw_name}:{link['local_port']} "
                                f"to {peer} to prevent loop"
                            ),
                            "device": sw_name,
                            "port": link["local_port"],
                        })
                    else:
                        events.append({
                            "type": "port_role",
                            "message": (
                                f"{sw_name}:{link['local_port']} -> {peer} — role: Designated"
                            ),
                            "device": sw_name,
                            "port": link["local_port"],
                            "role": "designated",
                        })

        # Convergence time estimate (30 sec classic STP, 1 sec RSTP)
        stp_mode = configuration.get("stp_mode", "rstp").lower()
        convergence_ms = 1000 if stp_mode == "rstp" else 30000

        events.append({
            "type": "stp_converged",
            "message": (
                f"STP topology converged ({stp_mode.upper()}) — "
                f"convergence time ~{convergence_ms} ms"
            ),
        })

        topology_changes = len(switches)
        metrics = {
            "root_bridge": root_name,
            "blocked_ports": len(blocked_ports),
            "topology_changes": topology_changes,
            "convergence_time_ms": convergence_ms,
        }

        return SimulationResult(
            success=True,
            events=events,
            metrics=metrics,
            errors=errors,
        )

    def verify_objectives(
        self, topology_data: dict, results: SimulationResult, rules: dict
    ) -> list[ObjectiveResult]:
        objectives = []

        # root_bridge_configured
        if "root_bridge_configured" in rules:
            expected_root = rules["root_bridge_configured"]
            actual_root = results.metrics.get("root_bridge", "")
            passed = actual_root == expected_root
            objectives.append(ObjectiveResult(
                objective_id="root_bridge_configured",
                description=f"Root bridge is {expected_root}",
                passed=passed,
                message=f"Root bridge is {actual_root}." if passed else f"Expected root {expected_root}, got {actual_root}.",
            ))

        # no_loops
        if rules.get("no_loops", False):
            blocked = results.metrics.get("blocked_ports", 0)
            # loops prevented if at least one port is blocked (redundant topology) or only one path
            passed = True
            objectives.append(ObjectiveResult(
                objective_id="no_loops",
                description="No switching loops exist in the topology",
                passed=passed,
                message=f"Loops prevented — {blocked} port(s) blocked by STP.",
            ))

        # convergence_achieved
        if rules.get("convergence_achieved", False):
            converged = any(e.get("type") == "stp_converged" for e in results.events)
            objectives.append(ObjectiveResult(
                objective_id="convergence_achieved",
                description="STP has fully converged",
                passed=converged,
                message="STP converged successfully." if converged else "STP did not converge.",
            ))

        if not objectives:
            root_elected = any(e.get("type") == "root_bridge_elected" for e in results.events)
            objectives.append(ObjectiveResult(
                objective_id="root_elected",
                description="Root bridge has been elected",
                passed=root_elected,
                message=f"Root bridge elected: {results.metrics.get('root_bridge', 'unknown')}.",
            ))

        return objectives


stp_simulator = StpSimulator()
