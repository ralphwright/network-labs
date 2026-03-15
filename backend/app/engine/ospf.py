from app.engine.base import BaseSimulator, SimulationResult, ObjectiveResult


class OspfSimulator(BaseSimulator):
    def validate_topology(self, topology_data: dict) -> list[str]:
        errors = []
        devices = topology_data.get("devices", [])
        routers = [
            d for d in devices
            if d.get("type", "").lower() in {"router", "multilayer_switch", "layer3_switch"}
        ]
        if len(routers) < 2:
            errors.append("OSPF simulation requires at least 2 routers.")
        return errors

    def simulate(self, topology_data: dict, configuration: dict) -> SimulationResult:
        devices = topology_data.get("devices", [])
        connections = topology_data.get("connections", [])
        events = []
        errors = []

        routers = [
            d for d in devices
            if d.get("type", "").lower() in {"router", "multilayer_switch", "layer3_switch"}
        ]
        router_names = {r["name"] for r in routers}

        # Build per-router OSPF config
        router_configs: dict[str, dict] = {}
        for r in routers:
            name = r["name"]
            cfg = configuration.get(name, {})
            ospf_cfg = cfg.get("ospf", r.get("ospf", {}))
            router_id = ospf_cfg.get("router_id", r.get("router_id", f"10.0.0.{routers.index(r) + 1}"))
            area = ospf_cfg.get("area", "0")
            networks = ospf_cfg.get("networks", r.get("networks", []))
            router_configs[name] = {
                "router_id": router_id,
                "area": str(area),
                "networks": networks,
            }

        # Discover OSPF adjacencies from connections
        adjacencies: list[dict] = []
        link_subnets: dict[tuple, str] = {}

        for conn_idx, conn in enumerate(connections):
            src = conn.get("source", conn.get("from", ""))
            dst = conn.get("target", conn.get("to", ""))
            if src in router_names and dst in router_names:
                subnet = conn.get("subnet", f"10.{conn_idx}.0.0/30")
                src_ip = conn.get("source_ip", f"10.{conn_idx}.0.1")
                dst_ip = conn.get("target_ip", f"10.{conn_idx}.0.2")
                link_subnets[(src, dst)] = subnet
                adjacencies.append({
                    "r1": src,
                    "r2": dst,
                    "subnet": subnet,
                    "r1_ip": src_ip,
                    "r2_ip": dst_ip,
                })

        # Hello packets and adjacency formation
        for adj in adjacencies:
            r1, r2 = adj["r1"], adj["r2"]
            r1_id = router_configs[r1]["router_id"]
            r2_id = router_configs[r2]["router_id"]
            events.append({
                "type": "ospf_hello",
                "message": f"OSPF Hello sent {r1} -> {r2} (src {r1_id}, subnet {adj['subnet']})",
                "from": r1,
                "to": r2,
            })
            events.append({
                "type": "ospf_hello",
                "message": f"OSPF Hello sent {r2} -> {r1} (src {r2_id}, subnet {adj['subnet']})",
                "from": r2,
                "to": r1,
            })
            events.append({
                "type": "ospf_adjacency",
                "message": f"Adjacency formed {r1}-{r2} (Full state) on subnet {adj['subnet']}",
                "routers": [r1, r2],
            })

        # LSA flooding
        for router in routers:
            name = router["name"]
            rid = router_configs[name]["router_id"]
            area = router_configs[name]["area"]
            events.append({
                "type": "lsa_flood",
                "message": f"LSA flood from {name} (Router-ID {rid}, Area {area})",
                "device": name,
            })

        # SPF / Dijkstra route computation
        events.append({
            "type": "spf_start",
            "message": "SPF (Dijkstra) calculation started on all OSPF routers",
        })

        # Build adjacency graph
        graph: dict[str, list[tuple]] = {r["name"]: [] for r in routers}
        for adj in adjacencies:
            cost = 10  # default OSPF cost for 100 Mbps
            graph[adj["r1"]].append((adj["r2"], cost, adj["r2_ip"], adj["subnet"]))
            graph[adj["r2"]].append((adj["r1"], cost, adj["r1_ip"], adj["subnet"]))

        # Collect all networks from configs and link subnets
        all_networks: list[str] = []
        for rcfg in router_configs.values():
            all_networks.extend(rcfg["networks"])
        for adj in adjacencies:
            if adj["subnet"] not in all_networks:
                all_networks.append(adj["subnet"])

        # Compute routes per router with Dijkstra
        routes_computed = 0
        for source in routers:
            src_name = source["name"]
            # Simple Dijkstra
            dist: dict[str, int] = {r["name"]: float("inf") for r in routers}
            dist[src_name] = 0
            next_hop: dict[str, str] = {}
            unvisited = set(r["name"] for r in routers)

            while unvisited:
                # Pick minimum distance unvisited node
                current = min(unvisited, key=lambda n: dist[n])
                if dist[current] == float("inf"):
                    break
                unvisited.remove(current)
                for (neighbor, cost, nh_ip, subnet) in graph.get(current, []):
                    new_dist = dist[current] + cost
                    if new_dist < dist[neighbor]:
                        dist[neighbor] = new_dist
                        # Track next hop from source
                        if current == src_name:
                            next_hop[neighbor] = nh_ip
                        else:
                            next_hop[neighbor] = next_hop.get(current, nh_ip)

            # Emit route events for remote routers
            for dest_name, d in dist.items():
                if dest_name != src_name and d < float("inf"):
                    nh = next_hop.get(dest_name, "direct")
                    # Find a network to advertise from dest
                    dest_nets = router_configs[dest_name]["networks"]
                    advertised = dest_nets[0] if dest_nets else f"10.0.{routers.index(source)}.0/24"
                    events.append({
                        "type": "route_installed",
                        "message": (
                            f"Route {advertised} via {nh} metric {d} added to {src_name}"
                        ),
                        "device": src_name,
                        "prefix": advertised,
                        "next_hop": nh,
                        "metric": d,
                    })
                    routes_computed += 1

        events.append({
            "type": "spf_complete",
            "message": f"SPF calculation complete — {routes_computed} routes computed",
        })

        # Collect unique areas
        areas = list({rc["area"] for rc in router_configs.values()})

        metrics = {
            "routers": len(routers),
            "adjacencies": len(adjacencies),
            "routes_computed": routes_computed,
            "areas": areas,
            "convergence_time_ms": len(routers) * 200,
        }

        return SimulationResult(
            success=len(errors) == 0,
            events=events,
            metrics=metrics,
            errors=errors,
        )

    def verify_objectives(
        self, topology_data: dict, results: SimulationResult, rules: dict
    ) -> list[ObjectiveResult]:
        objectives = []

        # full_adjacency
        if rules.get("full_adjacency", False):
            adj_count = results.metrics.get("adjacencies", 0)
            passed = adj_count > 0
            objectives.append(ObjectiveResult(
                objective_id="full_adjacency",
                description="All OSPF routers have formed Full adjacencies",
                passed=passed,
                message=f"{adj_count} adjacency/adjacencies in Full state." if passed else "No OSPF adjacencies formed.",
            ))

        # routes_learned
        if rules.get("routes_learned", False):
            routes = results.metrics.get("routes_computed", 0)
            passed = routes > 0
            objectives.append(ObjectiveResult(
                objective_id="routes_learned",
                description="Routes have been learned via OSPF",
                passed=passed,
                message=f"{routes} OSPF route(s) installed." if passed else "No OSPF routes computed.",
            ))

        # area_configured
        if "area_configured" in rules:
            expected_area = str(rules["area_configured"])
            actual_areas = results.metrics.get("areas", [])
            passed = expected_area in actual_areas
            objectives.append(ObjectiveResult(
                objective_id="area_configured",
                description=f"OSPF area {expected_area} is configured",
                passed=passed,
                message=f"Area {expected_area} active." if passed else f"Area {expected_area} not found (found: {actual_areas}).",
            ))

        if not objectives:
            adj_formed = any(e.get("type") == "ospf_adjacency" for e in results.events)
            objectives.append(ObjectiveResult(
                objective_id="ospf_adjacency",
                description="OSPF adjacencies have formed",
                passed=adj_formed,
                message="OSPF adjacencies formed." if adj_formed else "No OSPF adjacencies detected.",
            ))

        return objectives


ospf_simulator = OspfSimulator()
