from app.engine.base import BaseSimulator, SimulationResult, ObjectiveResult


class NatSimulator(BaseSimulator):
    def validate_topology(self, topology_data: dict) -> list[str]:
        errors = []
        devices = topology_data.get("devices", [])
        nat_routers = [
            d for d in devices
            if d.get("nat") or d.get("nat_inside") or d.get("nat_outside") or
            (
                d.get("type", "").lower() in {"router", "firewall"}
                and (d.get("inside_interface") or d.get("outside_interface"))
            )
        ]
        routers = [
            d for d in devices
            if d.get("type", "").lower() in {"router", "firewall", "multilayer_switch"}
        ]
        if not nat_routers and not routers:
            errors.append(
                "NAT simulation requires a router or firewall with inside/outside interfaces. "
                "Configure nat, nat_inside/nat_outside, or use type: router/firewall."
            )
        return errors

    def simulate(self, topology_data: dict, configuration: dict) -> SimulationResult:
        devices = topology_data.get("devices", [])
        events = []
        errors = []

        nat_capable = {
            "router", "firewall", "multilayer_switch", "layer3_switch"
        }

        nat_devices = [
            d for d in devices
            if d.get("type", "").lower() in nat_capable
            or d.get("nat") or d.get("nat_inside") or d.get("nat_outside")
        ]
        if not nat_devices:
            nat_devices = [d for d in devices if d.get("type", "").lower() in nat_capable]

        hosts = [
            d for d in devices
            if d.get("type", "").lower() in {"pc", "host", "workstation", "server", "laptop"}
        ]

        static_mappings = 0
        dynamic_pool_size = 0
        active_translations = 0

        for idx, dev in enumerate(nat_devices):
            dname = dev["name"]
            cfg = configuration.get(dname, {})
            nat_cfg = cfg.get("nat", dev.get("nat", {}))

            # Inside interface
            inside_iface = nat_cfg.get(
                "inside_interface", dev.get("nat_inside", f"{dname}:eth0")
            )
            inside_network = nat_cfg.get(
                "inside_network", dev.get("inside_network", f"192.168.{idx + 1}.0/24")
            )
            inside_ip = nat_cfg.get(
                "inside_ip", dev.get("inside_ip", f"192.168.{idx + 1}.1")
            )

            # Outside interface
            outside_iface = nat_cfg.get(
                "outside_interface", dev.get("nat_outside", f"{dname}:eth1")
            )
            outside_network = nat_cfg.get(
                "outside_network", dev.get("outside_network", "203.0.113.0/24")
            )
            outside_ip = nat_cfg.get(
                "outside_ip", dev.get("outside_ip", f"203.0.113.{idx + 1}")
            )

            # Static NAT mappings
            static_nats = nat_cfg.get("static", dev.get("static_nat", []))
            if not isinstance(static_nats, list):
                static_nats = [static_nats]

            # Dynamic pool
            pool_start = nat_cfg.get("pool_start", f"203.0.113.{20 + idx * 10}")
            pool_end = nat_cfg.get("pool_end", f"203.0.113.{29 + idx * 10}")
            pool_name = nat_cfg.get("pool_name", f"NAT_POOL_{idx + 1}")
            use_dynamic = nat_cfg.get("dynamic", True)

            events.append({
                "type": "nat_inside",
                "message": (
                    f"NAT inside interface: {inside_iface} ({inside_network})"
                ),
                "device": dname,
                "interface": inside_iface,
                "network": inside_network,
            })
            events.append({
                "type": "nat_outside",
                "message": (
                    f"NAT outside interface: {outside_iface} ({outside_network})"
                ),
                "device": dname,
                "interface": outside_iface,
                "network": outside_network,
            })

            # Static NAT entries
            if not static_nats:
                # Auto-generate based on inside hosts
                inside_base = inside_network.rsplit(".", 1)[0]
                outside_base = outside_network.rsplit(".", 1)[0] if "/" in outside_network else "203.0.113"
                for h_idx, host in enumerate(hosts[:3]):
                    static_nats.append({
                        "inside": f"{inside_base}.{10 + h_idx}",
                        "outside": f"{outside_base}.{10 + h_idx}",
                    })

            for sm in static_nats:
                inside_addr = sm.get("inside", sm.get("local", "192.168.1.10"))
                outside_addr = sm.get("outside", sm.get("global", "203.0.113.10"))
                events.append({
                    "type": "static_nat",
                    "message": (
                        f"Static NAT: {inside_addr} <-> {outside_addr} "
                        f"(one-to-one mapping on {dname})"
                    ),
                    "device": dname,
                    "inside": inside_addr,
                    "outside": outside_addr,
                })
                static_mappings += 1
                active_translations += 1

            # Dynamic NAT pool
            if use_dynamic:
                pool_parts_start = pool_start.split(".")
                pool_parts_end = pool_end.split(".")
                try:
                    pool_size = int(pool_parts_end[-1]) - int(pool_parts_start[-1]) + 1
                except (ValueError, IndexError):
                    pool_size = 10
                dynamic_pool_size += pool_size

                events.append({
                    "type": "nat_pool",
                    "message": (
                        f"Dynamic NAT pool {pool_name}: {pool_start}-{pool_end} "
                        f"({pool_size} addresses) on {dname}"
                    ),
                    "device": dname,
                    "pool_name": pool_name,
                    "pool_start": pool_start,
                    "pool_end": pool_end,
                    "pool_size": pool_size,
                })

                # Simulate translations for inside hosts
                pool_base = pool_start.rsplit(".", 1)[0]
                pool_offset = int(pool_start.rsplit(".", 1)[-1])

                for h_idx, host in enumerate(hosts):
                    hname = host.get("name", f"host{h_idx}")
                    inside_base = inside_network.rsplit(".", 1)[0]
                    src_ip = host.get("ip_address", f"{inside_base}.{5 + h_idx}")
                    nat_ip = f"{pool_base}.{pool_offset + h_idx}"

                    events.append({
                        "type": "nat_translation",
                        "message": (
                            f"Translation: {src_ip}:src -> {nat_ip}:src (outbound, {dname})"
                        ),
                        "device": dname,
                        "inside_ip": src_ip,
                        "outside_ip": nat_ip,
                        "direction": "outbound",
                    })
                    events.append({
                        "type": "nat_translation",
                        "message": (
                            f"Translation: {nat_ip}:dst -> {src_ip}:dst (inbound, {dname})"
                        ),
                        "device": dname,
                        "inside_ip": src_ip,
                        "outside_ip": nat_ip,
                        "direction": "inbound",
                    })
                    active_translations += 1

        translations_per_sec = float(active_translations) * 12.5 if active_translations else 0.0

        metrics = {
            "static_mappings": static_mappings,
            "dynamic_pool_size": dynamic_pool_size,
            "active_translations": active_translations,
            "translations_per_sec": round(translations_per_sec, 1),
        }

        return SimulationResult(
            success=len(errors) == 0 and (static_mappings > 0 or dynamic_pool_size > 0),
            events=events,
            metrics=metrics,
            errors=errors,
        )

    def verify_objectives(
        self, topology_data: dict, results: SimulationResult, rules: dict
    ) -> list[ObjectiveResult]:
        objectives = []

        if rules.get("nat_configured", False):
            static = results.metrics.get("static_mappings", 0)
            dynamic = results.metrics.get("dynamic_pool_size", 0)
            passed = static > 0 or dynamic > 0
            objectives.append(ObjectiveResult(
                objective_id="nat_configured",
                description="NAT is configured (static or dynamic)",
                passed=passed,
                message=(
                    f"NAT configured: {static} static mapping(s), "
                    f"dynamic pool size {dynamic}." if passed
                    else "No NAT configuration found."
                ),
            ))

        if rules.get("inside_outside_defined", False):
            inside_defined = any(e.get("type") == "nat_inside" for e in results.events)
            outside_defined = any(e.get("type") == "nat_outside" for e in results.events)
            passed = inside_defined and outside_defined
            objectives.append(ObjectiveResult(
                objective_id="inside_outside_defined",
                description="NAT inside and outside interfaces are defined",
                passed=passed,
                message=(
                    "Inside and outside NAT interfaces configured." if passed
                    else "Missing NAT inside or outside interface definition."
                ),
            ))

        if rules.get("translation_working", False):
            translations = results.metrics.get("active_translations", 0)
            passed = translations > 0
            objectives.append(ObjectiveResult(
                objective_id="translation_working",
                description="NAT translations are active",
                passed=passed,
                message=(
                    f"{translations} active NAT translation(s)." if passed
                    else "No active NAT translations."
                ),
            ))

        if not objectives:
            nat_active = any(
                e.get("type") in {"static_nat", "nat_translation"} for e in results.events
            )
            objectives.append(ObjectiveResult(
                objective_id="nat_simulation",
                description="NAT simulation completed",
                passed=nat_active,
                message=(
                    "NAT translations configured and active." if nat_active
                    else "No NAT activity detected."
                ),
            ))

        return objectives


nat_simulator = NatSimulator()
