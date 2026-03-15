from app.engine.base import BaseSimulator, SimulationResult, ObjectiveResult

_GRE_OVERHEAD_BYTES = 24  # 20-byte outer IP + 4-byte GRE header


class GreSimulator(BaseSimulator):
    def validate_topology(self, topology_data: dict) -> list[str]:
        errors = []
        devices = topology_data.get("devices", [])

        endpoints = [
            d for d in devices
            if (
                d.get("gre_tunnel")
                or d.get("tunnel", {}).get("mode", "").lower() == "gre"
                or d.get("type", "").lower() in {"router", "firewall"}
            )
        ]

        if len(endpoints) < 2:
            errors.append("GRE simulation requires at least 2 GRE-capable endpoint devices (routers/firewalls).")

        return errors

    def simulate(self, topology_data: dict, configuration: dict) -> SimulationResult:
        devices = topology_data.get("devices", [])
        connections = topology_data.get("connections", [])
        events = []
        errors = []

        routers = [
            d for d in devices
            if d.get("type", "").lower() in {"router", "firewall"}
        ]
        if not routers:
            routers = [d for d in devices if d.get("type", "").lower() != "pc"][:2]
        if len(routers) < 2:
            routers = devices[:2]

        # Build GRE tunnel configs
        gre_tunnels: list[dict] = []
        processed_pairs: set[frozenset] = set()

        for idx in range(len(routers) - 1):
            r1 = routers[idx]
            r2 = routers[idx + 1]

            pair = frozenset({r1["name"], r2["name"]})
            if pair in processed_pairs:
                continue
            processed_pairs.add(pair)

            r1_cfg = configuration.get(r1["name"], {})
            r2_cfg = configuration.get(r2["name"], {})
            gre1 = r1_cfg.get("gre", r1.get("gre_tunnel", {}))
            gre2 = r2_cfg.get("gre", r2.get("gre_tunnel", {}))

            r1_public = gre1.get("source", r1_cfg.get("public_ip", r1.get("public_ip", f"203.0.113.{idx * 2 + 1}")))
            r2_public = gre2.get("source", r2_cfg.get("public_ip", r2.get("public_ip", f"203.0.113.{idx * 2 + 2}")))

            tunnel_ip_r1 = gre1.get("tunnel_ip", f"172.16.{idx}.1/30")
            tunnel_ip_r2 = gre2.get("tunnel_ip", f"172.16.{idx}.2/30")

            keepalive_interval = int(gre1.get("keepalive", r1_cfg.get("keepalive", 10)))
            keepalive_retries = int(gre1.get("keepalive_retries", 3))

            gre_key = gre1.get("key", None)
            checksum = bool(gre1.get("checksum", False))
            multicast = bool(gre1.get("multicast", r1_cfg.get("multicast", False)))

            routing_protocol = gre1.get("routing_protocol", r1_cfg.get("routing_protocol", "ospf"))

            gre_tunnels.append({
                "id": idx,
                "name": f"Tunnel{idx}",
                "r1": r1["name"],
                "r2": r2["name"],
                "r1_public": r1_public,
                "r2_public": r2_public,
                "tunnel_ip_r1": tunnel_ip_r1,
                "tunnel_ip_r2": tunnel_ip_r2,
                "keepalive_interval": keepalive_interval,
                "keepalive_retries": keepalive_retries,
                "gre_key": gre_key,
                "checksum": checksum,
                "multicast": multicast,
                "routing_protocol": routing_protocol,
            })

        multicast_enabled = any(t["multicast"] for t in gre_tunnels)
        first_keepalive = gre_tunnels[0]["keepalive_interval"] if gre_tunnels else 10

        for tunnel in gre_tunnels:
            tname = tunnel["name"]
            r1 = tunnel["r1"]
            r2 = tunnel["r2"]

            # Tunnel establishment
            events.append({
                "type": "gre_tunnel_established",
                "message": (
                    f"GRE tunnel {tname} established {r1} ({tunnel['r1_public']}) "
                    f"<-> {r2} ({tunnel['r2_public']})"
                ),
                "r1": r1,
                "r2": r2,
            })

            # GRE header detail
            gre_flags = []
            if tunnel["checksum"]:
                gre_flags.append("Checksum=1")
            if tunnel["gre_key"] is not None:
                gre_flags.append(f"Key={tunnel['gre_key']}")
            flags_str = " ".join(gre_flags) if gre_flags else "Flags=0x0000"
            events.append({
                "type": "gre_header",
                "message": (
                    f"GRE header on {tname}: Protocol Type 0x0800 (IPv4), "
                    f"{flags_str}, overhead {_GRE_OVERHEAD_BYTES}B"
                ),
                "tunnel": tname,
            })

            # Tunnel interface IPs
            events.append({
                "type": "tunnel_ip_assigned",
                "message": (
                    f"Tunnel IPs: {r1} {tunnel['tunnel_ip_r1']}, "
                    f"{r2} {tunnel['tunnel_ip_r2']}"
                ),
            })

            # MTU consideration
            effective_mtu = 1500 - _GRE_OVERHEAD_BYTES
            events.append({
                "type": "gre_mtu",
                "message": (
                    f"MTU: physical 1500B - GRE overhead {_GRE_OVERHEAD_BYTES}B "
                    f"= effective {effective_mtu}B on {tname}"
                ),
            })

            # Keepalive simulation
            events.append({
                "type": "gre_keepalive",
                "message": (
                    f"GRE keepalive sent on {tname}: "
                    f"interval {tunnel['keepalive_interval']}s, "
                    f"retries {tunnel['keepalive_retries']}"
                ),
                "tunnel": tname,
                "interval": tunnel["keepalive_interval"],
            })
            events.append({
                "type": "gre_keepalive_ack",
                "message": f"GRE keepalive ACK received from {r2} on {tname} — tunnel UP",
                "tunnel": tname,
            })

            # Multicast / routing protocol over GRE
            if tunnel["multicast"]:
                events.append({
                    "type": "gre_multicast",
                    "message": (
                        f"Multicast enabled on {tname} — "
                        f"{tunnel['routing_protocol'].upper()} hellos will traverse GRE tunnel"
                    ),
                    "tunnel": tname,
                })

            proto = tunnel["routing_protocol"].upper()
            events.append({
                "type": "routing_over_gre",
                "message": (
                    f"{proto} running over GRE tunnel {tname} — "
                    f"adjacency forming between {r1} and {r2}"
                ),
                "tunnel": tname,
                "protocol": proto,
            })

            # Sample encapsulated packet
            r1_inner = tunnel["tunnel_ip_r1"].split("/")[0]
            r2_inner = tunnel["tunnel_ip_r2"].split("/")[0]
            events.append({
                "type": "gre_packet",
                "message": (
                    f"GRE encapsulated packet: inner {r1_inner} -> {r2_inner}, "
                    f"outer src {tunnel['r1_public']} dst {tunnel['r2_public']}, "
                    f"protocol 0x2F (GRE)"
                ),
                "inner_src": r1_inner,
                "inner_dst": r2_inner,
            })

        metrics = {
            "gre_tunnels": len(gre_tunnels),
            "keepalive_interval": first_keepalive,
            "multicast_enabled": multicast_enabled,
            "overhead_bytes": _GRE_OVERHEAD_BYTES,
        }

        return SimulationResult(
            success=len(gre_tunnels) > 0,
            events=events,
            metrics=metrics,
            errors=errors,
        )

    def verify_objectives(
        self, topology_data: dict, results: SimulationResult, rules: dict
    ) -> list[ObjectiveResult]:
        objectives = []

        # gre_tunnel_up
        if rules.get("gre_tunnel_up", False):
            tunnels = results.metrics.get("gre_tunnels", 0)
            passed = tunnels > 0
            objectives.append(ObjectiveResult(
                objective_id="gre_tunnel_up",
                description="GRE tunnel is established and UP",
                passed=passed,
                message=f"{tunnels} GRE tunnel(s) up." if passed else "No GRE tunnels established.",
            ))

        # keepalives
        if rules.get("keepalives", False):
            ka_ok = any(e.get("type") == "gre_keepalive_ack" for e in results.events)
            objectives.append(ObjectiveResult(
                objective_id="keepalives",
                description="GRE keepalives are exchanged successfully",
                passed=ka_ok,
                message="GRE keepalives acknowledged." if ka_ok else "No GRE keepalive ACKs received.",
            ))

        # routing_protocol_over_tunnel
        if rules.get("routing_protocol_over_tunnel", False):
            routing_up = any(e.get("type") == "routing_over_gre" for e in results.events)
            proto = next(
                (e.get("protocol", "") for e in results.events if e.get("type") == "routing_over_gre"),
                "unknown",
            )
            objectives.append(ObjectiveResult(
                objective_id="routing_protocol_over_tunnel",
                description="A routing protocol is running over the GRE tunnel",
                passed=routing_up,
                message=f"{proto} running over GRE." if routing_up else "No routing protocol over GRE tunnel.",
            ))

        if not objectives:
            tunnel_up = any(e.get("type") == "gre_tunnel_established" for e in results.events)
            objectives.append(ObjectiveResult(
                objective_id="gre_tunnel_up",
                description="GRE tunnel is established",
                passed=tunnel_up,
                message="GRE tunnel established." if tunnel_up else "GRE tunnel not established.",
            ))

        return objectives


gre_simulator = GreSimulator()
