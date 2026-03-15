from app.engine.base import BaseSimulator, SimulationResult, ObjectiveResult


class Ipv6Simulator(BaseSimulator):
    def validate_topology(self, topology_data: dict) -> list[str]:
        errors = []
        devices = topology_data.get("devices", [])
        ipv6_devices = [
            d for d in devices
            if d.get("ipv6") or d.get("ipv6_address") or d.get("ipv6_enabled")
        ]
        if not ipv6_devices:
            errors.append(
                "IPv6 simulation requires at least one device with IPv6 addresses configured "
                "(set ipv6, ipv6_address, or ipv6_enabled on device)."
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
        hosts = [
            d for d in devices
            if d.get("type", "").lower() in {"pc", "host", "workstation", "server", "laptop"}
        ]
        all_ipv6_devices = [
            d for d in devices
            if d.get("ipv6") or d.get("ipv6_address") or d.get("ipv6_enabled", False)
               or configuration.get(d.get("name", ""), {}).get("ipv6")
        ]
        if not all_ipv6_devices:
            all_ipv6_devices = devices  # treat all as IPv6-capable

        router_names = {r["name"] for r in routers}

        # Per-device IPv6 config
        dev_configs: dict[str, dict] = {}
        for idx, d in enumerate(devices):
            name = d.get("name", f"device{idx}")
            cfg = configuration.get(name, {})
            ipv6_cfg = cfg.get("ipv6", d.get("ipv6", {}))
            if isinstance(ipv6_cfg, str):
                ipv6_cfg = {"address": ipv6_cfg}
            global_addr = ipv6_cfg.get(
                "address",
                d.get("ipv6_address", f"2001:db8:{idx + 1}::1/64"),
            )
            link_local = ipv6_cfg.get("link_local", f"fe80::{idx + 1}")
            ra_enabled = ipv6_cfg.get("ra_enabled", d.get("type", "").lower() in {
                "router", "multilayer_switch", "layer3_switch"
            })
            slaac = ipv6_cfg.get("slaac", d.get("type", "").lower() in {
                "pc", "host", "workstation", "laptop"
            })
            dhcpv6 = ipv6_cfg.get("dhcpv6", False)
            dual_stack = ipv6_cfg.get("dual_stack", bool(d.get("ip") or d.get("ip_address")))
            ospfv3 = cfg.get("ospfv3", d.get("ospfv3", {}))
            dev_configs[name] = {
                "global_addr": global_addr,
                "link_local": link_local,
                "ra_enabled": ra_enabled,
                "slaac": slaac,
                "dhcpv6": dhcpv6,
                "dual_stack": dual_stack,
                "ospfv3": ospfv3,
                "type": d.get("type", "").lower(),
            }

        # IPv6 address assignment — link-local first (EUI-64 style)
        for name, dcfg in dev_configs.items():
            ll = dcfg["link_local"]
            iface = f"{name}:eth0"
            events.append({
                "type": "ipv6_link_local",
                "message": f"Link-local address {ll} assigned to {iface} (EUI-64 derived)",
                "device": name,
                "address": ll,
                "interface": iface,
            })
            if dcfg["global_addr"] and not dcfg["slaac"]:
                events.append({
                    "type": "ipv6_global_unicast",
                    "message": (
                        f"Global unicast address {dcfg['global_addr']} configured on {iface}"
                    ),
                    "device": name,
                    "address": dcfg["global_addr"],
                })
            if dcfg["dual_stack"]:
                events.append({
                    "type": "dual_stack",
                    "message": f"Dual-stack (IPv4+IPv6) enabled on {name}",
                    "device": name,
                })

        # Router Advertisements and SLAAC
        ra_routers = [name for name, dcfg in dev_configs.items() if dcfg["ra_enabled"]]
        slaac_clients = []
        dhcpv6_clients = []
        slaac_counter = 0xa1b2

        for ra_router in ra_routers:
            rcfg = dev_configs[ra_router]
            # Derive prefix from global address
            raw_prefix = rcfg["global_addr"].split("::")[0] if "::" in rcfg["global_addr"] else "2001:db8"
            prefix = f"{raw_prefix}::/64"
            events.append({
                "type": "router_advertisement",
                "message": (
                    f"Router Advertisement sent from {ra_router} "
                    f"(prefix {prefix}, lifetime 1800s, M=0, O=0)"
                ),
                "device": ra_router,
                "prefix": prefix,
            })

            # NDP Router Solicitation from hosts
            for host in hosts:
                hname = host.get("name", "host")
                events.append({
                    "type": "router_solicitation",
                    "message": (
                        f"NDP Router Solicitation from {hname} "
                        f"(ff02::2 all-routers multicast)"
                    ),
                    "device": hname,
                })
                hcfg = dev_configs.get(hname, {})
                if hcfg.get("slaac", True):
                    # SLAAC address derived from prefix + interface ID
                    slaac_addr = f"{raw_prefix}::{slaac_counter:x}"
                    slaac_counter += 1
                    events.append({
                        "type": "slaac_configured",
                        "message": (
                            f"SLAAC: {hname} configured {slaac_addr} "
                            f"from RA (prefix {prefix})"
                        ),
                        "device": hname,
                        "address": slaac_addr,
                        "from_router": ra_router,
                    })
                    slaac_clients.append(hname)
                elif hcfg.get("dhcpv6", False):
                    events.append({
                        "type": "dhcpv6_request",
                        "message": (
                            f"DHCPv6 Solicit from {hname} -> ff02::1:2 "
                            f"(managed address config)"
                        ),
                        "device": hname,
                    })
                    events.append({
                        "type": "dhcpv6_reply",
                        "message": (
                            f"DHCPv6 Reply to {hname}: address {raw_prefix}::d{slaac_counter:x}/64, "
                            f"DNS 2001:db8::53"
                        ),
                        "device": hname,
                    })
                    slaac_counter += 1
                    dhcpv6_clients.append(hname)

        # NDP — Neighbor Solicitation/Advertisement (replaces ARP)
        for conn_idx, conn in enumerate(connections):
            src = conn.get("source", conn.get("from", ""))
            dst = conn.get("target", conn.get("to", ""))
            if src not in dev_configs or dst not in dev_configs:
                continue
            dst_addr = dev_configs[dst].get("global_addr", f"2001:db8::{conn_idx + 1}").split("/")[0]
            events.append({
                "type": "ndp_solicitation",
                "message": (
                    f"NDP Neighbor Solicitation from {src} for {dst_addr} "
                    f"(solicited-node multicast ff02::1:ff{dst_addr[-2:]})"
                ),
                "from": src,
                "target": dst_addr,
            })
            events.append({
                "type": "ndp_advertisement",
                "message": (
                    f"NDP Neighbor Advertisement: {dst} -> {src} "
                    f"(target {dst_addr}, link-layer addr resolved)"
                ),
                "from": dst,
                "to": src,
                "target": dst_addr,
            })

        # Loopback multicast addresses
        events.append({
            "type": "ipv6_multicast",
            "message": "IPv6 multicast group ff02::1 (all-nodes) active on all interfaces",
        })
        events.append({
            "type": "ipv6_loopback",
            "message": "IPv6 loopback ::1/128 active on all IPv6-enabled devices",
        })

        # OSPFv3 adjacencies for routers
        ospfv3_adjacencies = 0
        for conn_idx, conn in enumerate(connections):
            src = conn.get("source", conn.get("from", ""))
            dst = conn.get("target", conn.get("to", ""))
            if src in router_names and dst in router_names:
                src_ospf = dev_configs.get(src, {}).get("ospfv3") or True
                dst_ospf = dev_configs.get(dst, {}).get("ospfv3") or True
                if src_ospf and dst_ospf:
                    events.append({
                        "type": "ospfv3_adjacency",
                        "message": (
                            f"OSPFv3 adjacency {src}-{dst} formed "
                            f"(Hello interval 10s, area 0)"
                        ),
                        "routers": [src, dst],
                    })
                    ospfv3_adjacencies += 1

        # Count metrics
        global_unicast_count = sum(
            1 for dcfg in dev_configs.values()
            if dcfg.get("global_addr")
        )
        dual_stack_count = sum(
            1 for dcfg in dev_configs.values()
            if dcfg.get("dual_stack")
        )

        metrics = {
            "ipv6_devices": len(dev_configs),
            "global_unicast": global_unicast_count,
            "dual_stack": dual_stack_count,
            "slaac_clients": len(set(slaac_clients)),
            "dhcpv6_clients": len(set(dhcpv6_clients)),
            "ospfv3_adjacencies": ospfv3_adjacencies,
            "ra_routers": len(ra_routers),
        }

        return SimulationResult(
            success=len(errors) == 0 and len(dev_configs) > 0,
            events=events,
            metrics=metrics,
            errors=errors,
        )

    def verify_objectives(
        self, topology_data: dict, results: SimulationResult, rules: dict
    ) -> list[ObjectiveResult]:
        objectives = []

        if rules.get("ipv6_addressing", False):
            ipv6_devs = results.metrics.get("ipv6_devices", 0)
            passed = ipv6_devs > 0
            objectives.append(ObjectiveResult(
                objective_id="ipv6_addressing",
                description="IPv6 addresses configured on network devices",
                passed=passed,
                message=(
                    f"{ipv6_devs} device(s) with IPv6 addressing." if passed
                    else "No IPv6 addressing configured."
                ),
            ))

        if rules.get("neighbor_discovery", False):
            ndp_events = [e for e in results.events if e.get("type") in {
                "ndp_solicitation", "ndp_advertisement"
            }]
            passed = len(ndp_events) > 0
            objectives.append(ObjectiveResult(
                objective_id="neighbor_discovery",
                description="NDP Neighbor Discovery is operational",
                passed=passed,
                message=(
                    f"{len(ndp_events)} NDP message(s) exchanged." if passed
                    else "No NDP activity detected."
                ),
            ))

        if rules.get("routing_ipv6", False):
            ospfv3_adj = results.metrics.get("ospfv3_adjacencies", 0)
            passed = ospfv3_adj > 0
            objectives.append(ObjectiveResult(
                objective_id="routing_ipv6",
                description="IPv6 routing (OSPFv3) is configured and operational",
                passed=passed,
                message=(
                    f"{ospfv3_adj} OSPFv3 adjacency/adjacencies formed." if passed
                    else "No IPv6 routing adjacencies formed."
                ),
            ))

        if not objectives:
            ll_assigned = any(e.get("type") == "ipv6_link_local" for e in results.events)
            objectives.append(ObjectiveResult(
                objective_id="ipv6_simulation",
                description="IPv6 simulation completed successfully",
                passed=ll_assigned,
                message=(
                    "IPv6 link-local addresses assigned." if ll_assigned
                    else "IPv6 addressing not configured."
                ),
            ))

        return objectives


ipv6_simulator = Ipv6Simulator()
