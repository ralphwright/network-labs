from app.engine.base import BaseSimulator, SimulationResult, ObjectiveResult


class VlanSimulator(BaseSimulator):
    VALID_DEVICE_TYPES = {"switch", "router", "pc", "server", "host", "firewall", "access_point"}

    def validate_topology(self, topology_data: dict) -> list[str]:
        errors = []
        devices = topology_data.get("devices", [])
        if not devices:
            errors.append("Topology has no devices defined.")
            return errors

        switch_found = any(
            d.get("type", "").lower() in {"switch", "multilayer_switch", "layer3_switch"}
            for d in devices
        )
        if not switch_found:
            errors.append("VLAN simulation requires at least one switch.")

        for device in devices:
            dtype = device.get("type", "").lower()
            if dtype and dtype not in self.VALID_DEVICE_TYPES | {"multilayer_switch", "layer3_switch"}:
                errors.append(f"Device '{device.get('name', '?')}' has unrecognized type '{dtype}'.")

        return errors

    def simulate(self, topology_data: dict, configuration: dict) -> SimulationResult:
        devices = topology_data.get("devices", [])
        connections = topology_data.get("connections", [])
        events = []
        errors = []

        # Index devices by name
        device_map = {d["name"]: d for d in devices}

        # Parse VLAN config per switch
        switches = [d for d in devices if d.get("type", "").lower() in {"switch", "multilayer_switch", "layer3_switch"}]
        routers = [d for d in devices if d.get("type", "").lower() in {"router", "multilayer_switch", "layer3_switch"}]
        hosts = [d for d in devices if d.get("type", "").lower() in {"pc", "server", "host"}]

        all_vlans: dict[int, list[str]] = {}  # vlan_id -> [switch_names]
        access_ports: list[dict] = []
        trunk_ports: list[dict] = []

        for switch in switches:
            sw_name = switch["name"]
            sw_config = configuration.get(sw_name, {})
            vlans_cfg = sw_config.get("vlans", [])

            if not vlans_cfg:
                vlans_cfg = switch.get("vlans", [10, 20])

            for vlan_id in vlans_cfg:
                vlan_id = int(vlan_id)
                all_vlans.setdefault(vlan_id, []).append(sw_name)
                events.append({
                    "type": "vlan_created",
                    "message": f"VLAN {vlan_id} created on {sw_name}",
                    "device": sw_name,
                    "vlan": vlan_id,
                })

            # Access port assignments
            ports_cfg = sw_config.get("ports", switch.get("ports", {}))
            interface_names = ["fa0/1", "fa0/2", "fa0/3", "fa0/4", "gi0/1", "gi0/2"]
            assigned = 0
            for port_name, port_cfg in (ports_cfg.items() if isinstance(ports_cfg, dict) else {}):
                mode = port_cfg.get("mode", "access")
                vlan = port_cfg.get("vlan", 1)
                if mode == "access":
                    access_ports.append({"switch": sw_name, "port": port_name, "vlan": vlan})
                    events.append({
                        "type": "port_assigned",
                        "message": f"Port {port_name} assigned to VLAN {vlan} (access) on {sw_name}",
                        "device": sw_name,
                        "port": port_name,
                        "vlan": vlan,
                    })
                    assigned += 1

            if not ports_cfg and vlans_cfg:
                # Auto-assign hosts to VLANs round-robin for simulation
                vlan_list = list(vlans_cfg)
                for idx, host in enumerate(hosts):
                    vlan_id = int(vlan_list[idx % len(vlan_list)])
                    port = interface_names[idx % len(interface_names)]
                    access_ports.append({"switch": sw_name, "port": port, "vlan": vlan_id, "host": host["name"]})
                    events.append({
                        "type": "port_assigned",
                        "message": f"Port {port} assigned to VLAN {vlan_id} (access) on {sw_name} [{host['name']}]",
                        "device": sw_name,
                        "port": port,
                        "vlan": vlan_id,
                    })

        # Detect trunk links between switches
        switch_names = {s["name"] for s in switches}
        for conn in connections:
            src = conn.get("source", conn.get("from", ""))
            dst = conn.get("target", conn.get("to", ""))
            if src in switch_names and dst in switch_names:
                src_port = conn.get("sourcePort", conn.get("source_port", "gi0/1"))
                dst_port = conn.get("targetPort", conn.get("target_port", "gi0/1"))
                trunk_ports.append({"sw1": src, "port1": src_port, "sw2": dst, "port2": dst_port})
                events.append({
                    "type": "trunk_established",
                    "message": f"802.1Q trunk established between {src}:{src_port} and {dst}:{dst_port}",
                    "devices": [src, dst],
                })

        # Simulate traffic isolation
        vlan_host_map: dict[int, list[str]] = {}
        for ap in access_ports:
            host = ap.get("host", f"host-on-{ap['switch']}-{ap['port']}")
            vlan_host_map.setdefault(ap["vlan"], []).append(host)

        vlan_ids = sorted(all_vlans.keys())
        for i, v1 in enumerate(vlan_ids):
            for v2 in vlan_ids[i + 1:]:
                h1 = vlan_host_map.get(v1, [f"host-vlan{v1}"])
                h2 = vlan_host_map.get(v2, [f"host-vlan{v2}"])
                events.append({
                    "type": "traffic_isolation",
                    "message": f"{h1[0]} (VLAN {v1}) cannot reach {h2[0]} (VLAN {v2}) - isolated",
                    "vlan_a": v1,
                    "vlan_b": v2,
                })

        # Inter-VLAN routing
        inter_vlan_routing = False
        if routers and len(vlan_ids) > 1:
            router_name = routers[0]["name"]
            inter_vlan_routing = True
            events.append({
                "type": "inter_vlan_routing",
                "message": f"Inter-VLAN routing enabled on {router_name} (router-on-a-stick)",
                "device": router_name,
            })
            for vlan_id in vlan_ids:
                sub_iface = f"fa0/0.{vlan_id}"
                # Derive a plausible gateway IP
                third_octet = vlan_id if vlan_id < 256 else (vlan_id % 256)
                gw_ip = f"192.168.{third_octet}.1"
                events.append({
                    "type": "subinterface_configured",
                    "message": (
                        f"Sub-interface {sub_iface} on {router_name}: "
                        f"encapsulation dot1Q {vlan_id}, IP {gw_ip}/24"
                    ),
                    "device": router_name,
                    "vlan": vlan_id,
                    "ip": gw_ip,
                })
            for v1 in vlan_ids:
                for v2 in vlan_ids:
                    if v1 != v2:
                        h1 = vlan_host_map.get(v1, [f"host-vlan{v1}"])[0]
                        h2 = vlan_host_map.get(v2, [f"host-vlan{v2}"])[0]
                        events.append({
                            "type": "inter_vlan_traffic",
                            "message": (
                                f"{h1} (VLAN {v1}) can reach {h2} (VLAN {v2}) via {router_name}"
                            ),
                        })
                        break

        metrics = {
            "vlans_configured": len(all_vlans),
            "trunk_ports": len(trunk_ports),
            "access_ports": len(access_ports),
            "inter_vlan_routing": inter_vlan_routing,
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

        # required_vlans
        required_vlans = rules.get("required_vlans", [])
        if required_vlans:
            configured = {
                e["vlan"]
                for e in results.events
                if e.get("type") == "vlan_created"
            }
            missing = [v for v in required_vlans if int(v) not in configured]
            passed = len(missing) == 0
            objectives.append(ObjectiveResult(
                objective_id="required_vlans",
                description=f"Required VLANs {required_vlans} are configured",
                passed=passed,
                message="All required VLANs configured." if passed else f"Missing VLANs: {missing}",
            ))

        # trunk_configured
        if rules.get("trunk_configured", False):
            trunks = [e for e in results.events if e.get("type") == "trunk_established"]
            passed = len(trunks) > 0
            objectives.append(ObjectiveResult(
                objective_id="trunk_configured",
                description="At least one 802.1Q trunk link is configured",
                passed=passed,
                message=f"{len(trunks)} trunk link(s) established." if passed else "No trunk links found.",
            ))

        # inter_vlan_routing
        if rules.get("inter_vlan_routing", False):
            passed = results.metrics.get("inter_vlan_routing", False)
            objectives.append(ObjectiveResult(
                objective_id="inter_vlan_routing",
                description="Inter-VLAN routing is configured",
                passed=passed,
                message="Inter-VLAN routing active." if passed else "Inter-VLAN routing not configured.",
            ))

        if not objectives:
            vlans_ok = results.metrics.get("vlans_configured", 0) > 0
            objectives.append(ObjectiveResult(
                objective_id="vlans_exist",
                description="At least one VLAN is configured",
                passed=vlans_ok,
                message="VLANs are configured." if vlans_ok else "No VLANs were configured.",
            ))

        return objectives


vlan_simulator = VlanSimulator()
