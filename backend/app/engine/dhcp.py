from app.engine.base import BaseSimulator, SimulationResult, ObjectiveResult


class DhcpSimulator(BaseSimulator):
    def validate_topology(self, topology_data: dict) -> list[str]:
        errors = []
        devices = topology_data.get("devices", [])
        servers = [
            d for d in devices
            if d.get("type", "").lower() in {"server", "dhcp_server"}
            or d.get("role", "").lower() in {"dhcp_server", "dhcp"}
        ]
        clients = [
            d for d in devices
            if d.get("type", "").lower() in {"pc", "host", "workstation"}
        ]
        if not servers:
            errors.append("DHCP simulation requires at least one DHCP server.")
        if not clients:
            errors.append("DHCP simulation requires at least one DHCP client.")
        return errors

    def simulate(self, topology_data: dict, configuration: dict) -> SimulationResult:
        devices = topology_data.get("devices", [])
        connections = topology_data.get("connections", [])
        events = []
        errors = []

        servers = [
            d for d in devices
            if d.get("type", "").lower() in {"server", "dhcp_server"}
            or d.get("role", "").lower() in {"dhcp_server", "dhcp"}
        ]
        clients = [
            d for d in devices
            if d.get("type", "").lower() in {"pc", "host", "workstation"}
        ]
        routers = [
            d for d in devices
            if d.get("type", "").lower() == "router"
        ]

        if not servers:
            # Fall back to any server-ish device
            servers = [d for d in devices if "server" in d.get("name", "").lower()]
        if not clients:
            clients = [d for d in devices if d.get("type", "").lower() in {"pc", "host"}]

        server = servers[0]
        server_name = server["name"]
        server_cfg = configuration.get(server_name, {})
        dhcp_pools = server_cfg.get("dhcp_pools", server.get("dhcp_pools", [
            {
                "name": "LAN_POOL",
                "network": "192.168.1.0/24",
                "start": "192.168.1.100",
                "end": "192.168.1.200",
                "gateway": "192.168.1.1",
                "dns": "8.8.8.8",
                "lease": 86400,
            }
        ]))

        events.append({
            "type": "dhcp_server_start",
            "message": f"DHCP server {server_name} started — serving {len(dhcp_pools)} pool(s)",
            "device": server_name,
        })

        for pool in dhcp_pools:
            events.append({
                "type": "dhcp_pool",
                "message": (
                    f"DHCP pool '{pool.get('name', 'default')}': "
                    f"network {pool.get('network', '192.168.1.0/24')}, "
                    f"range {pool.get('start', '192.168.1.100')}-{pool.get('end', '192.168.1.200')}, "
                    f"GW {pool.get('gateway', '192.168.1.1')}, "
                    f"DNS {pool.get('dns', '8.8.8.8')}"
                ),
                "device": server_name,
            })

        # Check if relay is needed (router between client and server)
        relay_agents = []
        if routers:
            for router in routers:
                router_cfg = configuration.get(router["name"], {})
                if router_cfg.get("dhcp_relay") or router.get("dhcp_relay"):
                    relay_agents.append(router["name"])
            if not relay_agents and len(routers) > 0:
                # Heuristic: if there are subnets in config, relay likely needed
                all_subnets = {
                    conn.get("subnet", "")
                    for conn in connections
                }
                if len({s for s in all_subnets if s}) > 1:
                    relay_agents.append(routers[0]["name"])
                    events.append({
                        "type": "dhcp_relay",
                        "message": (
                            f"DHCP Relay Agent configured on {routers[0]['name']} — "
                            f"forwarding broadcasts to {server_name}"
                        ),
                        "device": routers[0]["name"],
                    })

        # Simulate DORA for each client
        leases_issued = 0
        pool = dhcp_pools[0] if dhcp_pools else {}
        start_ip_parts = pool.get("start", "192.168.1.100").split(".")
        base_host = int(start_ip_parts[-1]) if start_ip_parts else 100

        for idx, client in enumerate(clients):
            client_name = client["name"]
            offered_ip = ".".join(start_ip_parts[:-1] + [str(base_host + idx)])
            gateway = pool.get("gateway", "192.168.1.1")
            dns = pool.get("dns", "8.8.8.8")
            lease = pool.get("lease", 86400)
            subnet_mask = "255.255.255.0"

            events.append({
                "type": "dhcp_discover",
                "message": f"DHCP Discover broadcast from {client_name} (src 0.0.0.0, dst 255.255.255.255)",
                "device": client_name,
            })

            if relay_agents:
                events.append({
                    "type": "dhcp_relay_forward",
                    "message": (
                        f"DHCP Relay on {relay_agents[0]} forwards Discover from "
                        f"{client_name} to {server_name}"
                    ),
                })

            events.append({
                "type": "dhcp_offer",
                "message": (
                    f"DHCP Offer: {offered_ip}/{subnet_mask} "
                    f"GW {gateway} DNS {dns} from {server_name} to {client_name}"
                ),
                "device": server_name,
                "ip_offered": offered_ip,
            })
            events.append({
                "type": "dhcp_request",
                "message": f"DHCP Request from {client_name} for {offered_ip}",
                "device": client_name,
                "ip_requested": offered_ip,
            })
            events.append({
                "type": "dhcp_ack",
                "message": (
                    f"DHCP Ack: {offered_ip}/{subnet_mask} GW {gateway} "
                    f"DNS {dns} lease {lease}s — {client_name} configured"
                ),
                "device": server_name,
                "ip_assigned": offered_ip,
                "lease_seconds": lease,
            })
            leases_issued += 1

        # Pool utilization
        pool_size = 101  # default 100-200 range
        try:
            start_parts = pool.get("start", "192.168.1.100").split(".")
            end_parts = pool.get("end", "192.168.1.200").split(".")
            pool_size = int(end_parts[-1]) - int(start_parts[-1]) + 1
        except (ValueError, IndexError):
            pass

        utilization = round((leases_issued / pool_size * 100), 2) if pool_size else 0

        metrics = {
            "clients_configured": leases_issued,
            "leases_issued": leases_issued,
            "relay_agents": len(relay_agents),
            "pool_utilization_pct": utilization,
        }

        return SimulationResult(
            success=leases_issued > 0,
            events=events,
            metrics=metrics,
            errors=errors,
        )

    def verify_objectives(
        self, topology_data: dict, results: SimulationResult, rules: dict
    ) -> list[ObjectiveResult]:
        objectives = []

        # dhcp_server_configured
        if rules.get("dhcp_server_configured", False):
            server_started = any(e.get("type") == "dhcp_server_start" for e in results.events)
            objectives.append(ObjectiveResult(
                objective_id="dhcp_server_configured",
                description="DHCP server is configured and active",
                passed=server_started,
                message="DHCP server configured." if server_started else "DHCP server not found.",
            ))

        # clients_received_ip
        if rules.get("clients_received_ip", False):
            leases = results.metrics.get("leases_issued", 0)
            passed = leases > 0
            objectives.append(ObjectiveResult(
                objective_id="clients_received_ip",
                description="DHCP clients have received IP addresses",
                passed=passed,
                message=f"{leases} client(s) received IP via DHCP." if passed else "No DHCP leases issued.",
            ))

        # relay_configured
        if rules.get("relay_configured", False):
            relays = results.metrics.get("relay_agents", 0)
            passed = relays > 0
            objectives.append(ObjectiveResult(
                objective_id="relay_configured",
                description="DHCP relay agent is configured",
                passed=passed,
                message=f"{relays} relay agent(s) active." if passed else "No DHCP relay agents configured.",
            ))

        if not objectives:
            dora_complete = any(e.get("type") == "dhcp_ack" for e in results.events)
            objectives.append(ObjectiveResult(
                objective_id="dora_complete",
                description="DHCP DORA process completed for at least one client",
                passed=dora_complete,
                message="DHCP DORA completed." if dora_complete else "DHCP DORA not completed.",
            ))

        return objectives


dhcp_simulator = DhcpSimulator()
