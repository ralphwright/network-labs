from app.engine.base import BaseSimulator, SimulationResult, ObjectiveResult


class AutonomousSystemsSimulator(BaseSimulator):
    def validate_topology(self, topology_data: dict) -> list[str]:
        errors = []
        devices = topology_data.get("devices", [])
        routers = [
            d for d in devices
            if d.get("type", "").lower() in {"router", "multilayer_switch", "layer3_switch"}
        ]
        if len(routers) < 2:
            errors.append("Autonomous Systems simulation requires at least 2 routers.")

        # Check that multiple AS domains are represented
        as_numbers = set()
        for d in routers:
            as_num = d.get("bgp_as") or d.get("as_number") or d.get("bgp", {}).get("as_number")
            if as_num:
                as_numbers.add(int(as_num))

        if len(as_numbers) < 2:
            errors.append(
                "Multiple AS domains required. Configure bgp_as or bgp.as_number on routers."
            )
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

        # Build per-router AS/BGP/OSPF config
        router_configs: dict[str, dict] = {}
        for idx, r in enumerate(routers):
            name = r["name"]
            cfg = configuration.get(name, {})
            bgp_cfg = cfg.get("bgp", r.get("bgp", {}))
            ospf_cfg = cfg.get("ospf", r.get("ospf", {}))
            as_num = int(
                bgp_cfg.get("as_number", r.get("bgp_as", r.get("as_number", 65001 + idx)))
            )
            router_id = bgp_cfg.get(
                "router_id", ospf_cfg.get("router_id", r.get("router_id", f"10.0.0.{idx + 1}"))
            )
            networks = bgp_cfg.get("networks", r.get("networks", [f"10.{idx}.0.0/24"]))
            intra_protocol = ospf_cfg.get("protocol", cfg.get("intra_protocol", "OSPF"))
            route_maps = cfg.get("route_maps", r.get("route_maps", []))
            prefix_lists = cfg.get("prefix_lists", r.get("prefix_lists", []))
            router_configs[name] = {
                "as_number": as_num,
                "router_id": router_id,
                "networks": networks,
                "intra_protocol": intra_protocol,
                "route_maps": route_maps,
                "prefix_lists": prefix_lists,
            }

        router_names = set(router_configs.keys())

        # Group routers by AS
        as_domains: dict[int, list[str]] = {}
        for name, cfg in router_configs.items():
            as_domains.setdefault(cfg["as_number"], []).append(name)

        # Identify ASBR (routers with connections to a different AS)
        asbr_set: set[str] = set()
        inter_as_links: list[dict] = []
        intra_as_links: list[dict] = []

        for conn_idx, conn in enumerate(connections):
            src = conn.get("source", conn.get("from", ""))
            dst = conn.get("target", conn.get("to", ""))
            if src not in router_names or dst not in router_names:
                continue
            src_as = router_configs[src]["as_number"]
            dst_as = router_configs[dst]["as_number"]
            src_ip = conn.get("source_ip", f"10.{conn_idx}.0.1")
            dst_ip = conn.get("target_ip", f"10.{conn_idx}.0.2")
            link = {
                "r1": src, "r2": dst,
                "r1_ip": src_ip, "r2_ip": dst_ip,
                "r1_as": src_as, "r2_as": dst_as,
            }
            if src_as != dst_as:
                asbr_set.add(src)
                asbr_set.add(dst)
                inter_as_links.append(link)
            else:
                intra_as_links.append(link)

        # Auto-assign ASBRs if no explicit cross-AS connections found
        if not inter_as_links and len(as_domains) >= 2:
            as_list = sorted(as_domains.keys())
            for i in range(len(as_list) - 1):
                r1_list = as_domains[as_list[i]]
                r2_list = as_domains[as_list[i + 1]]
                r1 = r1_list[0]
                r2 = r2_list[0]
                asbr_set.add(r1)
                asbr_set.add(r2)
                inter_as_links.append({
                    "r1": r1, "r2": r2,
                    "r1_ip": f"203.0.113.{i * 4 + 1}",
                    "r2_ip": f"203.0.113.{i * 4 + 2}",
                    "r1_as": as_list[i],
                    "r2_as": as_list[i + 1],
                })

        # AS boundary identification events
        for as_num, members in sorted(as_domains.items()):
            boundary = [r for r in members if r in asbr_set]
            internal = [r for r in members if r not in asbr_set]
            boundary_str = ", ".join(boundary) if boundary else "none"
            internal_str = ", ".join(internal) if internal else "none"
            events.append({
                "type": "as_boundary",
                "message": f"AS {as_num} boundary routers: {boundary_str}",
                "as_number": as_num,
                "boundary_routers": boundary,
            })
            events.append({
                "type": "as_internal",
                "message": (
                    f"AS {as_num} internal routers: {internal_str} "
                    f"(intra-AS: {router_configs[members[0]]['intra_protocol']})"
                ),
                "as_number": as_num,
                "internal_routers": internal,
            })

        # Intra-AS routing (OSPF/IS-IS)
        for link in intra_as_links:
            proto = router_configs[link["r1"]]["intra_protocol"]
            events.append({
                "type": "intra_as_routing",
                "message": (
                    f"{proto} adjacency {link['r1']}-{link['r2']} "
                    f"(AS {link['r1_as']}, subnet {link['r1_ip']}/30)"
                ),
                "protocol": proto,
                "routers": [link["r1"], link["r2"]],
            })

        # eBGP session establishment
        ebgp_sessions = 0
        ibgp_sessions = 0
        for link in inter_as_links:
            events.append({
                "type": "ebgp_session",
                "message": (
                    f"eBGP session AS{link['r1_as']}<->AS{link['r2_as']}: "
                    f"{link['r1']}({link['r1_ip']}) <-> {link['r2']}({link['r2_ip']})"
                ),
                "r1": link["r1"], "r2": link["r2"],
                "r1_as": link["r1_as"], "r2_as": link["r2_as"],
            })
            events.append({
                "type": "ebgp_established",
                "message": (
                    f"eBGP session AS{link['r1_as']}<->AS{link['r2_as']} Established "
                    f"(Hold-Time 90s, Keepalive 30s)"
                ),
            })
            ebgp_sessions += 1

        # iBGP within each AS (full mesh between internal routers)
        for as_num, members in sorted(as_domains.items()):
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    r1, r2 = members[i], members[j]
                    events.append({
                        "type": "ibgp_session",
                        "message": (
                            f"iBGP session {r1}<->{r2} (AS {as_num}) Established "
                            f"(loopback peering)"
                        ),
                        "r1": r1, "r2": r2, "as_number": as_num,
                    })
                    ibgp_sessions += 1

        # BGP UPDATE / route advertisement
        redistributed_routes = 0
        for link in inter_as_links:
            for router_name in [link["r1"], link["r2"]]:
                rcfg = router_configs[router_name]
                for prefix in rcfg["networks"]:
                    peer = link["r2"] if link["r1"] == router_name else link["r1"]
                    peer_as = link["r2_as"] if link["r1"] == router_name else link["r1_as"]
                    events.append({
                        "type": "bgp_update",
                        "message": (
                            f"BGP UPDATE {router_name}->AS{peer_as}: "
                            f"prefix {prefix}, AS_PATH {rcfg['as_number']}, "
                            f"NEXT_HOP {link['r1_ip'] if link['r1'] == router_name else link['r2_ip']}"
                        ),
                        "device": router_name,
                        "prefix": prefix,
                    })

        # Route redistribution (OSPF->BGP at ASBRs)
        for asbr in sorted(asbr_set):
            rcfg = router_configs[asbr]
            events.append({
                "type": "redistribution",
                "message": (
                    f"Route redistribution: {rcfg['intra_protocol']}->BGP on ASBR {asbr} "
                    f"(AS {rcfg['as_number']})"
                ),
                "device": asbr,
                "from_protocol": rcfg["intra_protocol"],
                "to_protocol": "BGP",
            })
            redistributed_routes += len(rcfg["networks"])

        # Policy application (route-maps, prefix-lists)
        policy_filters = 0
        for name, rcfg in router_configs.items():
            for rm in rcfg["route_maps"]:
                action = rm.get("action", "permit")
                match = rm.get("match", "any")
                events.append({
                    "type": "policy_applied",
                    "message": f"Policy applied on {name}: route-map {action} {match}",
                    "device": name,
                    "policy": rm,
                })
                policy_filters += 1
            for pl in rcfg["prefix_lists"]:
                seq = pl.get("seq", 10)
                action = pl.get("action", "permit")
                prefix = pl.get("prefix", "0.0.0.0/0")
                events.append({
                    "type": "prefix_list",
                    "message": (
                        f"Prefix-list on {name}: seq {seq} {action} {prefix}"
                    ),
                    "device": name,
                    "prefix_list": pl,
                })
                policy_filters += 1

        # Example AS_PATH filter (deny paths containing a transit AS)
        all_as = sorted(as_domains.keys())
        if len(all_as) >= 3:
            blocked_as = all_as[1]
            events.append({
                "type": "as_path_filter",
                "message": (
                    f"Policy applied: deny AS_PATH containing {blocked_as} "
                    f"(transit AS filtering)"
                ),
                "blocked_as": blocked_as,
            })
            policy_filters += 1

        metrics = {
            "autonomous_systems": len(as_domains),
            "asbr_count": len(asbr_set),
            "redistributed_routes": redistributed_routes,
            "policy_filters": policy_filters,
            "ebgp_sessions": ebgp_sessions,
            "ibgp_sessions": ibgp_sessions,
        }

        return SimulationResult(
            success=len(errors) == 0 and len(as_domains) >= 1,
            events=events,
            metrics=metrics,
            errors=errors,
        )

    def verify_objectives(
        self, topology_data: dict, results: SimulationResult, rules: dict
    ) -> list[ObjectiveResult]:
        objectives = []

        if rules.get("as_separation", False):
            as_count = results.metrics.get("autonomous_systems", 0)
            passed = as_count >= 2
            objectives.append(ObjectiveResult(
                objective_id="as_separation",
                description="Multiple autonomous systems are defined and separated",
                passed=passed,
                message=(
                    f"{as_count} autonomous systems configured." if passed
                    else "Less than 2 autonomous systems found."
                ),
            ))

        if rules.get("ebgp_peering", False):
            ebgp = results.metrics.get("ebgp_sessions", 0)
            passed = ebgp > 0
            objectives.append(ObjectiveResult(
                objective_id="ebgp_peering",
                description="eBGP peering sessions established between AS domains",
                passed=passed,
                message=(
                    f"{ebgp} eBGP session(s) established." if passed
                    else "No eBGP sessions established."
                ),
            ))

        if rules.get("redistribution_correct", False):
            redist = results.metrics.get("redistributed_routes", 0)
            passed = redist > 0
            objectives.append(ObjectiveResult(
                objective_id="redistribution_correct",
                description="Routes redistributed between intra-AS and inter-AS protocols",
                passed=passed,
                message=(
                    f"{redist} routes redistributed at ASBR(s)." if passed
                    else "No route redistribution configured."
                ),
            ))

        if not objectives:
            ebgp_formed = any(e.get("type") == "ebgp_established" for e in results.events)
            objectives.append(ObjectiveResult(
                objective_id="as_simulation",
                description="Autonomous systems simulation completed",
                passed=ebgp_formed,
                message=(
                    "eBGP sessions established between autonomous systems." if ebgp_formed
                    else "eBGP sessions not established."
                ),
            ))

        return objectives


autonomous_systems_simulator = AutonomousSystemsSimulator()
