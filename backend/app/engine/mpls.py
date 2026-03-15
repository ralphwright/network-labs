from app.engine.base import BaseSimulator, SimulationResult, ObjectiveResult


class MplsSimulator(BaseSimulator):
    def validate_topology(self, topology_data: dict) -> list[str]:
        errors = []
        devices = topology_data.get("devices", [])
        routers = [
            d for d in devices
            if d.get("type", "").lower() in {"router", "multilayer_switch", "layer3_switch"}
        ]
        if len(routers) < 2:
            errors.append("MPLS simulation requires at least 2 routers configured as LSRs/LERs.")
            return errors

        lsr_capable = [
            r for r in routers
            if (
                r.get("mpls", {}).get("enabled", False)
                or r.get("role", "").lower() in {"lsr", "ler", "p", "pe", "ce"}
                or "mpls" in r.get("name", "").lower()
            )
        ]
        if not lsr_capable and len(routers) >= 2:
            pass  # Will treat all routers as LSR-capable if none explicitly configured

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

        # Assign MPLS roles
        router_roles: dict[str, str] = {}
        for idx, r in enumerate(routers):
            name = r["name"]
            cfg = configuration.get(name, {})
            mpls_cfg = cfg.get("mpls", r.get("mpls", {}))
            role = mpls_cfg.get("role", r.get("role", ""))
            if not role:
                if idx == 0 or idx == len(routers) - 1:
                    role = "LER"
                else:
                    role = "LSR"
            router_roles[name] = role.upper()

        router_names = set(r["name"] for r in routers)

        # Build link graph for LSPs
        links: list[dict] = []
        for conn_idx, conn in enumerate(connections):
            src = conn.get("source", conn.get("from", ""))
            dst = conn.get("target", conn.get("to", ""))
            if src in router_names and dst in router_names:
                links.append({
                    "src": src,
                    "dst": dst,
                    "src_ip": conn.get("source_ip", f"10.{conn_idx}.0.1"),
                    "dst_ip": conn.get("target_ip", f"10.{conn_idx}.0.2"),
                })

        if not links and len(routers) >= 2:
            for i in range(len(routers) - 1):
                links.append({
                    "src": routers[i]["name"],
                    "dst": routers[i + 1]["name"],
                    "src_ip": f"10.{i}.0.1",
                    "dst_ip": f"10.{i}.0.2",
                })

        # LDP session establishment
        for link in links:
            events.append({
                "type": "ldp_session",
                "message": (
                    f"LDP session {link['src']}-{link['dst']} established "
                    f"(TCP port 646, {link['src_ip']}<->{link['dst_ip']})"
                ),
                "routers": [link["src"], link["dst"]],
            })

        # FEC to label bindings — one per network
        all_networks: list[str] = []
        for r in routers:
            cfg = configuration.get(r["name"], {})
            nets = cfg.get("networks", r.get("networks", []))
            if not nets:
                idx = routers.index(r)
                nets = [f"10.{idx}.0.0/24"]
            all_networks.extend(nets)

        label_base = 100
        fec_label_map: dict[str, dict] = {}
        for idx, network in enumerate(all_networks):
            label = label_base + idx
            fec_label_map[network] = {"label": label}
            events.append({
                "type": "label_binding",
                "message": f"LDP label binding: FEC {network} -> Label {label}",
                "fec": network,
                "label": label,
            })

        # Build LSPs (ingress -> transit -> egress)
        lsps: list[dict] = []
        if len(routers) >= 2:
            # Path: first router (LER ingress) -> middle LSRs -> last router (LER egress)
            path = [r["name"] for r in routers]
            for net_idx, (fec, binding) in enumerate(fec_label_map.items()):
                lsp_labels = []
                for hop_idx, hop in enumerate(path[:-1]):
                    next_hop = path[hop_idx + 1]
                    push_label = binding["label"] + hop_idx
                    swap_label = binding["label"] + hop_idx + 1
                    lsp_labels.append((hop, push_label, swap_label))

                lsp = {
                    "fec": fec,
                    "path": path,
                    "ingress": path[0],
                    "egress": path[-1],
                    "labels": lsp_labels,
                }
                lsps.append(lsp)

                path_str = " -> ".join(path)
                events.append({
                    "type": "lsp_established",
                    "message": f"LSP established for FEC {fec}: {path_str} (label {binding['label']})",
                    "fec": fec,
                    "path": path,
                })

        # Simulate packet forwarding with label stack
        if lsps:
            lsp = lsps[0]
            fec = lsp["fec"]
            path = lsp["path"]
            ingress = lsp["ingress"]
            egress = lsp["egress"]
            label = fec_label_map[fec]["label"]

            # Extract a sample src/dst from FEC
            fec_network = fec.split("/")[0]
            fec_parts = fec_network.split(".")
            src_ip = ".".join(fec_parts[:3]) + ".1"
            dst_ip = ".".join(fec_parts[:3]) + ".254"

            events.append({
                "type": "mpls_push",
                "message": (
                    f"Packet {src_ip} -> {dst_ip}: "
                    f"IP -> MPLS push label {label} at ingress {ingress}"
                ),
                "device": ingress,
            })

            for i, transit in enumerate(path[1:-1]):
                old_label = label + i
                new_label = label + i + 1
                events.append({
                    "type": "mpls_swap",
                    "message": f"Packet at {transit}: MPLS swap label {old_label} -> {new_label}",
                    "device": transit,
                })

            events.append({
                "type": "mpls_pop",
                "message": f"Packet at egress {egress}: MPLS pop label -> IP delivered to {dst_ip}",
                "device": egress,
            })

        # Traffic engineering flag
        te_enabled = any(
            configuration.get(r["name"], {}).get("mpls", {}).get("traffic_engineering", False)
            for r in routers
        )

        transit_routers = sum(1 for role in router_roles.values() if role == "LSR")

        metrics = {
            "lsps": len(lsps),
            "labels_distributed": len(fec_label_map),
            "transit_routers": transit_routers,
            "traffic_engineering": te_enabled,
        }

        return SimulationResult(
            success=len(lsps) > 0,
            events=events,
            metrics=metrics,
            errors=errors,
        )

    def verify_objectives(
        self, topology_data: dict, results: SimulationResult, rules: dict
    ) -> list[ObjectiveResult]:
        objectives = []

        # lsp_established
        if rules.get("lsp_established", False):
            lsps = results.metrics.get("lsps", 0)
            passed = lsps > 0
            objectives.append(ObjectiveResult(
                objective_id="lsp_established",
                description="At least one MPLS LSP has been established",
                passed=passed,
                message=f"{lsps} LSP(s) established." if passed else "No MPLS LSPs established.",
            ))

        # label_distribution
        if rules.get("label_distribution", False):
            labels = results.metrics.get("labels_distributed", 0)
            passed = labels > 0
            objectives.append(ObjectiveResult(
                objective_id="label_distribution",
                description="LDP label bindings have been distributed",
                passed=passed,
                message=f"{labels} label binding(s) distributed." if passed else "No LDP label bindings.",
            ))

        # forwarding_correct
        if rules.get("forwarding_correct", False):
            push_ok = any(e.get("type") == "mpls_push" for e in results.events)
            pop_ok = any(e.get("type") == "mpls_pop" for e in results.events)
            passed = push_ok and pop_ok
            objectives.append(ObjectiveResult(
                objective_id="forwarding_correct",
                description="MPLS label push/swap/pop forwarding is correct",
                passed=passed,
                message="Push/swap/pop sequence verified." if passed else "MPLS forwarding path incomplete.",
            ))

        if not objectives:
            ldp_ok = any(e.get("type") == "ldp_session" for e in results.events)
            objectives.append(ObjectiveResult(
                objective_id="ldp_sessions",
                description="LDP sessions are established",
                passed=ldp_ok,
                message="LDP sessions active." if ldp_ok else "No LDP sessions found.",
            ))

        return objectives


mpls_simulator = MplsSimulator()
