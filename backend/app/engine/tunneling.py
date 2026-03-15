from app.engine.base import BaseSimulator, SimulationResult, ObjectiveResult

_VALID_ENCAPSULATIONS = {"ip-in-ip", "gre", "ipip", "l2tp", "ipsec", "vxlan", "sit"}


class TunnelingSimulator(BaseSimulator):
    def validate_topology(self, topology_data: dict) -> list[str]:
        errors = []
        devices = topology_data.get("devices", [])

        endpoints = [
            d for d in devices
            if (
                d.get("tunnel_source") or d.get("tunnel_destination")
                or d.get("tunnel", {})
                or "tunnel" in d.get("name", "").lower()
                or d.get("type", "").lower() in {"router", "firewall"}
            )
        ]

        if len(endpoints) < 2:
            errors.append("Tunneling simulation requires at least 2 tunnel endpoint devices.")

        return errors

    def simulate(self, topology_data: dict, configuration: dict) -> SimulationResult:
        devices = topology_data.get("devices", [])
        connections = topology_data.get("connections", [])
        events = []
        errors = []

        routers = [
            d for d in devices
            if d.get("type", "").lower() in {"router", "firewall", "server"}
        ]
        if not routers:
            routers = devices[:2] if len(devices) >= 2 else devices

        # Collect tunnel configurations
        tunnel_defs: list[dict] = []
        for idx, device in enumerate(routers):
            name = device["name"]
            cfg = configuration.get(name, {})
            tunnels = cfg.get("tunnels", device.get("tunnels", []))
            if not tunnels and idx < len(routers) - 1:
                peer = routers[idx + 1]
                peer_cfg = configuration.get(peer["name"], {})
                tunnel_src = cfg.get("public_ip", device.get("public_ip", f"203.0.113.{idx * 2 + 1}"))
                tunnel_dst = peer_cfg.get("public_ip", peer.get("public_ip", f"203.0.113.{idx * 2 + 2}"))
                inner_src = cfg.get("inner_network", device.get("inner_network", f"10.{idx}.0.0/24"))
                inner_dst = peer_cfg.get("inner_network", peer.get("inner_network", f"10.{idx + 1}.0.0/24"))
                tunnel_defs.append({
                    "id": idx,
                    "name": f"Tunnel{idx}",
                    "local_device": name,
                    "remote_device": peer["name"],
                    "source": tunnel_src,
                    "destination": tunnel_dst,
                    "encapsulation": cfg.get("encapsulation", "IP-in-IP"),
                    "inner_src_network": inner_src,
                    "inner_dst_network": inner_dst,
                    "mtu": int(cfg.get("mtu", 1480)),
                })
            else:
                for t in tunnels:
                    tunnel_defs.append({
                        "id": len(tunnel_defs),
                        "name": t.get("name", f"Tunnel{len(tunnel_defs)}"),
                        "local_device": name,
                        "remote_device": t.get("remote_device", ""),
                        "source": t.get("source", f"203.0.113.{idx + 1}"),
                        "destination": t.get("destination", f"203.0.113.{idx + 2}"),
                        "encapsulation": t.get("encapsulation", "IP-in-IP"),
                        "inner_src_network": t.get("inner_src", "10.0.0.0/24"),
                        "inner_dst_network": t.get("inner_dst", "10.1.0.0/24"),
                        "mtu": int(t.get("mtu", 1480)),
                    })

        # Deduplicate symmetric tunnel pairs
        seen_pairs: set[frozenset] = set()
        unique_tunnels: list[dict] = []
        for t in tunnel_defs:
            pair = frozenset({t["local_device"], t["remote_device"]})
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                unique_tunnels.append(t)
        tunnel_defs = unique_tunnels

        total_overhead = 0
        effective_mtu = 1500

        for tunnel in tunnel_defs:
            tname = tunnel["name"]
            encap = tunnel["encapsulation"]
            src = tunnel["source"]
            dst = tunnel["destination"]
            local = tunnel["local_device"]
            remote = tunnel["remote_device"]
            mtu = tunnel["mtu"]

            # Overhead: IP-in-IP = 20 bytes, GRE = 24 bytes, IPSec = 50-60 bytes
            overhead_map = {
                "ip-in-ip": 20, "ipip": 20,
                "gre": 24,
                "ipsec": 58,
                "l2tp": 40,
                "vxlan": 50,
                "sit": 20,
            }
            overhead = overhead_map.get(encap.lower().replace(" ", "-").replace("/", "-"), 20)
            total_overhead = overhead
            effective_mtu = 1500 - overhead

            events.append({
                "type": "tunnel_interface_created",
                "message": f"Tunnel interface {tname} created on {local}",
                "device": local,
                "tunnel": tname,
            })
            events.append({
                "type": "tunnel_encapsulation",
                "message": f"Tunnel encapsulation: {encap} configured on {tname}",
                "tunnel": tname,
                "encapsulation": encap,
            })
            events.append({
                "type": "tunnel_endpoints",
                "message": (
                    f"Tunnel source: {src} (on {local}), "
                    f"destination: {dst} (on {remote})"
                ),
                "source": src,
                "destination": dst,
            })
            events.append({
                "type": "tunnel_mtu",
                "message": (
                    f"MTU consideration: physical MTU 1500B - {encap} overhead {overhead}B "
                    f"= effective MTU {effective_mtu}B on {tname}"
                ),
                "overhead": overhead,
                "effective_mtu": effective_mtu,
            })

            # Simulate packet traversal
            inner_src_net = tunnel["inner_src_network"].split("/")[0]
            inner_dst_net = tunnel["inner_dst_network"].split("/")[0]
            inner_src_ip = inner_src_net[:-1] + "1" if inner_src_net.endswith(".0") else inner_src_net
            inner_dst_ip = inner_dst_net[:-1] + "1" if inner_dst_net.endswith(".0") else inner_dst_net

            events.append({
                "type": "tunnel_packet",
                "message": (
                    f"Inner packet {inner_src_ip} -> {inner_dst_ip} "
                    f"encapsulated in outer {src} -> {dst} ({encap})"
                ),
                "inner_src": inner_src_ip,
                "inner_dst": inner_dst_ip,
                "outer_src": src,
                "outer_dst": dst,
            })

            # Route over tunnel
            events.append({
                "type": "tunnel_route",
                "message": (
                    f"Route {tunnel['inner_dst_network']} via {tname} "
                    f"installed on {local}"
                ),
                "device": local,
                "prefix": tunnel["inner_dst_network"],
            })

            events.append({
                "type": "tunnel_up",
                "message": f"Tunnel {tname} between {local} and {remote} is UP",
                "local": local,
                "remote": remote,
            })

        encap_type = tunnel_defs[0]["encapsulation"] if tunnel_defs else "IP-in-IP"

        metrics = {
            "tunnels": len(tunnel_defs),
            "encapsulation_type": encap_type,
            "overhead_bytes": total_overhead,
            "effective_mtu": effective_mtu,
        }

        return SimulationResult(
            success=len(tunnel_defs) > 0,
            events=events,
            metrics=metrics,
            errors=errors,
        )

    def verify_objectives(
        self, topology_data: dict, results: SimulationResult, rules: dict
    ) -> list[ObjectiveResult]:
        objectives = []

        # tunnel_up
        if rules.get("tunnel_up", False):
            tunnels_up = sum(1 for e in results.events if e.get("type") == "tunnel_up")
            passed = tunnels_up > 0
            objectives.append(ObjectiveResult(
                objective_id="tunnel_up",
                description="At least one tunnel interface is up",
                passed=passed,
                message=f"{tunnels_up} tunnel(s) up." if passed else "No tunnels are up.",
            ))

        # encapsulation_correct
        if "encapsulation_correct" in rules:
            expected_encap = rules["encapsulation_correct"].lower()
            actual_encap = results.metrics.get("encapsulation_type", "").lower()
            passed = expected_encap in actual_encap
            objectives.append(ObjectiveResult(
                objective_id="encapsulation_correct",
                description=f"Tunnel encapsulation is '{rules['encapsulation_correct']}'",
                passed=passed,
                message=f"Encapsulation: {actual_encap}." if passed else f"Expected '{expected_encap}', got '{actual_encap}'.",
            ))

        # routing_over_tunnel
        if rules.get("routing_over_tunnel", False):
            route_installed = any(e.get("type") == "tunnel_route" for e in results.events)
            objectives.append(ObjectiveResult(
                objective_id="routing_over_tunnel",
                description="Routes are installed over the tunnel interface",
                passed=route_installed,
                message="Routes installed via tunnel." if route_installed else "No routes over tunnel.",
            ))

        if not objectives:
            tunnel_up = any(e.get("type") == "tunnel_up" for e in results.events)
            objectives.append(ObjectiveResult(
                objective_id="tunnel_up",
                description="Tunnel is operational",
                passed=tunnel_up,
                message="Tunnel is up." if tunnel_up else "Tunnel is not up.",
            ))

        return objectives


tunneling_simulator = TunnelingSimulator()
