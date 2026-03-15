from app.engine.base import BaseSimulator, SimulationResult, ObjectiveResult


class BgpSimulator(BaseSimulator):
    def validate_topology(self, topology_data: dict) -> list[str]:
        errors = []
        devices = topology_data.get("devices", [])
        routers = [
            d for d in devices
            if d.get("type", "").lower() in {"router", "multilayer_switch", "layer3_switch"}
        ]
        if len(routers) < 2:
            errors.append("BGP simulation requires at least 2 routers.")
            return errors

        bgp_routers = [
            r for r in routers
            if (
                r.get("bgp_as") is not None
                or r.get("bgp", {}).get("as_number") is not None
                or configuration_has_bgp(r)
            )
        ]
        # Allow topology-only BGP (AS may be in configuration dict)
        if len(bgp_routers) < 1 and len(routers) >= 2:
            pass  # AS numbers will come from configuration at simulate time

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

        # Build BGP config per router
        bgp_configs: dict[str, dict] = {}
        for idx, r in enumerate(routers):
            name = r["name"]
            cfg = configuration.get(name, {})
            bgp_cfg = cfg.get("bgp", r.get("bgp", {}))
            as_number = int(
                bgp_cfg.get("as_number", r.get("bgp_as", 65000 + idx + 1))
            )
            bgp_id = bgp_cfg.get("bgp_id", r.get("router_id", f"{idx + 1}.{idx + 1}.{idx + 1}.{idx + 1}"))
            networks = bgp_cfg.get("networks", r.get("networks", [f"10.{idx}.0.0/24"]))
            local_pref = int(bgp_cfg.get("local_pref", 100))
            bgp_configs[name] = {
                "as_number": as_number,
                "bgp_id": bgp_id,
                "networks": networks,
                "local_pref": local_pref,
            }

        router_names = set(bgp_configs.keys())

        # Find BGP sessions from connections
        sessions: list[dict] = []
        for conn_idx, conn in enumerate(connections):
            src = conn.get("source", conn.get("from", ""))
            dst = conn.get("target", conn.get("to", ""))
            if src in router_names and dst in router_names:
                src_ip = conn.get("source_ip", f"10.{conn_idx}.0.1")
                dst_ip = conn.get("target_ip", f"10.{conn_idx}.0.2")
                src_as = bgp_configs[src]["as_number"]
                dst_as = bgp_configs[dst]["as_number"]
                session_type = "iBGP" if src_as == dst_as else "eBGP"
                sessions.append({
                    "r1": src, "r2": dst,
                    "r1_ip": src_ip, "r2_ip": dst_ip,
                    "r1_as": src_as, "r2_as": dst_as,
                    "type": session_type,
                })

        if not sessions and len(routers) >= 2:
            # Auto-create sessions between adjacent routers
            for i in range(len(routers) - 1):
                r1 = routers[i]["name"]
                r2 = routers[i + 1]["name"]
                src_as = bgp_configs[r1]["as_number"]
                dst_as = bgp_configs[r2]["as_number"]
                session_type = "iBGP" if src_as == dst_as else "eBGP"
                sessions.append({
                    "r1": r1, "r2": r2,
                    "r1_ip": f"10.{i}.0.1", "r2_ip": f"10.{i}.0.2",
                    "r1_as": src_as, "r2_as": dst_as,
                    "type": session_type,
                })

        # TCP session establishment + BGP OPEN
        for sess in sessions:
            r1, r2 = sess["r1"], sess["r2"]
            r1_cfg, r2_cfg = bgp_configs[r1], bgp_configs[r2]

            events.append({
                "type": "bgp_tcp",
                "message": (
                    f"BGP TCP session {r1} ({sess['r1_ip']}) -> {r2} ({sess['r2_ip']}) "
                    f"established (port 179) [{sess['type']}]"
                ),
                "from": r1,
                "to": r2,
            })
            events.append({
                "type": "bgp_open",
                "message": (
                    f"BGP OPEN from {r1}: AS {r1_cfg['as_number']}, "
                    f"BGP-ID {r1_cfg['bgp_id']}, Hold-Time 90s"
                ),
                "device": r1,
                "as_number": r1_cfg["as_number"],
            })
            events.append({
                "type": "bgp_open",
                "message": (
                    f"BGP OPEN from {r2}: AS {r2_cfg['as_number']}, "
                    f"BGP-ID {r2_cfg['bgp_id']}, Hold-Time 90s"
                ),
                "device": r2,
                "as_number": r2_cfg["as_number"],
            })
            events.append({
                "type": "bgp_keepalive",
                "message": f"BGP KEEPALIVE exchanged {r1} <-> {r2} — session Established",
                "devices": [r1, r2],
            })

        # BGP UPDATE — advertise networks
        advertised: list[dict] = []
        for router_name, rcfg in bgp_configs.items():
            for prefix in rcfg["networks"]:
                for sess in sessions:
                    if sess["r1"] == router_name or sess["r2"] == router_name:
                        peer = sess["r2"] if sess["r1"] == router_name else sess["r1"]
                        peer_as = sess["r2_as"] if sess["r1"] == router_name else sess["r1_as"]
                        # eBGP: prepend own AS, iBGP: reflect as-is
                        as_path = (
                            str(rcfg["as_number"])
                            if sess["type"] == "eBGP"
                            else f"{rcfg['as_number']}"
                        )
                        next_hop = (
                            sess["r1_ip"] if sess["r1"] == router_name else sess["r2_ip"]
                        )
                        events.append({
                            "type": "bgp_update",
                            "message": (
                                f"BGP UPDATE from {router_name} to {peer}: "
                                f"prefix {prefix}, AS_PATH {as_path}, "
                                f"NEXT_HOP {next_hop}, LOCAL_PREF {rcfg['local_pref']}"
                            ),
                            "device": router_name,
                            "prefix": prefix,
                            "as_path": as_path,
                        })
                        advertised.append({
                            "prefix": prefix,
                            "from": router_name,
                            "to": peer,
                            "as_path": as_path,
                            "next_hop": next_hop,
                            "local_pref": rcfg["local_pref"],
                            "med": 0,
                        })

        # Best path selection
        prefix_candidates: dict[str, list[dict]] = {}
        for adv in advertised:
            prefix_candidates.setdefault(adv["prefix"], []).append(adv)

        for prefix, candidates in prefix_candidates.items():
            if len(candidates) > 1:
                # Sort by: highest LOCAL_PREF, shortest AS_PATH, lowest MED
                best = min(
                    candidates,
                    key=lambda c: (
                        -c["local_pref"],
                        len(c["as_path"].split()),
                        c["med"],
                    ),
                )
                events.append({
                    "type": "bgp_best_path",
                    "message": (
                        f"Best path selected for {prefix} via {best['from']} "
                        f"(AS_PATH {best['as_path']}, "
                        f"LOCAL_PREF {best['local_pref']}, NEXT_HOP {best['next_hop']})"
                    ),
                    "prefix": prefix,
                })

        unique_as = {rcfg["as_number"] for rcfg in bgp_configs.values()}
        prefixes_advertised = sum(len(rcfg["networks"]) for rcfg in bgp_configs.values())

        metrics = {
            "sessions": len(sessions),
            "prefixes_advertised": prefixes_advertised,
            "prefixes_received": len(advertised),
            "as_count": len(unique_as),
        }

        return SimulationResult(
            success=len(sessions) > 0,
            events=events,
            metrics=metrics,
            errors=errors,
        )

    def verify_objectives(
        self, topology_data: dict, results: SimulationResult, rules: dict
    ) -> list[ObjectiveResult]:
        objectives = []

        # bgp_sessions
        if rules.get("bgp_sessions", False):
            sessions = results.metrics.get("sessions", 0)
            passed = sessions > 0
            objectives.append(ObjectiveResult(
                objective_id="bgp_sessions",
                description="BGP sessions are established",
                passed=passed,
                message=f"{sessions} BGP session(s) established." if passed else "No BGP sessions established.",
            ))

        # prefixes_exchanged
        if rules.get("prefixes_exchanged", False):
            prefixes = results.metrics.get("prefixes_received", 0)
            passed = prefixes > 0
            objectives.append(ObjectiveResult(
                objective_id="prefixes_exchanged",
                description="BGP prefixes have been exchanged",
                passed=passed,
                message=f"{prefixes} prefix advertisement(s) sent." if passed else "No BGP prefixes exchanged.",
            ))

        # path_selection
        if rules.get("path_selection", False):
            best_path_set = any(e.get("type") == "bgp_best_path" for e in results.events)
            objectives.append(ObjectiveResult(
                objective_id="path_selection",
                description="BGP best-path selection has been performed",
                passed=best_path_set,
                message="BGP best-path selected." if best_path_set else "No best-path selection triggered.",
            ))

        if not objectives:
            established = any(e.get("type") == "bgp_keepalive" for e in results.events)
            objectives.append(ObjectiveResult(
                objective_id="bgp_established",
                description="BGP session reached Established state",
                passed=established,
                message="BGP sessions in Established state." if established else "BGP sessions not established.",
            ))

        return objectives


def configuration_has_bgp(device: dict) -> bool:
    return bool(device.get("bgp") or device.get("bgp_as"))


bgp_simulator = BgpSimulator()
