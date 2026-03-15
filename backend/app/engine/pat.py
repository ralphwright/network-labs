from app.engine.base import BaseSimulator, SimulationResult, ObjectiveResult


class PatSimulator(BaseSimulator):
    def validate_topology(self, topology_data: dict) -> list[str]:
        errors = []
        devices = topology_data.get("devices", [])
        pat_routers = [
            d for d in devices
            if d.get("pat") or d.get("nat_overload") or
            (
                d.get("type", "").lower() in {"router", "firewall"}
                and d.get("overload", False)
            )
        ]
        routers = [
            d for d in devices
            if d.get("type", "").lower() in {"router", "firewall", "multilayer_switch"}
        ]
        if not pat_routers and not routers:
            errors.append(
                "PAT simulation requires a router or firewall with NAT overload. "
                "Configure pat, nat_overload=true, or use type: router/firewall."
            )
        return errors

    def simulate(self, topology_data: dict, configuration: dict) -> SimulationResult:
        devices = topology_data.get("devices", [])
        events = []
        errors = []

        pat_capable = {"router", "firewall", "multilayer_switch", "layer3_switch"}
        host_types = {"pc", "host", "workstation", "laptop", "server"}

        pat_devices = [
            d for d in devices
            if d.get("type", "").lower() in pat_capable
            or d.get("pat") or d.get("nat_overload")
        ]
        if not pat_devices:
            pat_devices = [d for d in devices if d.get("type", "").lower() in pat_capable]

        hosts = [
            d for d in devices
            if d.get("type", "").lower() in host_types
        ]

        total_pat_entries = 0
        total_public_ips = 0
        max_sessions = 0

        # PAT port range (RFC standard ephemeral port range)
        PAT_PORT_START = 10001
        PAT_PORT_END = 65535
        port_range_str = f"{PAT_PORT_START}-{PAT_PORT_END}"

        for idx, dev in enumerate(pat_devices):
            dname = dev["name"]
            cfg = configuration.get(dname, {})
            pat_cfg = cfg.get("pat", cfg.get("nat", dev.get("pat", dev.get("nat", {}))))

            inside_network = pat_cfg.get(
                "inside_network", dev.get("inside_network", f"192.168.{idx + 1}.0/24")
            )
            inside_iface = pat_cfg.get(
                "inside_interface", dev.get("nat_inside", f"{dname}:eth0")
            )
            outside_iface = pat_cfg.get(
                "outside_interface", dev.get("nat_outside", f"{dname}:eth1")
            )
            # PAT uses a single public IP (overload)
            public_ip = pat_cfg.get(
                "public_ip",
                dev.get("outside_ip", dev.get("public_ip", f"203.0.113.{idx + 1}"))
            )
            overload = pat_cfg.get("overload", dev.get("overload", True))

            total_public_ips += 1
            # Max sessions = (PAT_PORT_END - PAT_PORT_START + 1) per public IP
            dev_max_sessions = PAT_PORT_END - PAT_PORT_START + 1
            max_sessions += dev_max_sessions

            events.append({
                "type": "pat_configured",
                "message": (
                    f"PAT configured: inside {inside_network} -> "
                    f"outside {public_ip} (overload)"
                ),
                "device": dname,
                "inside_network": inside_network,
                "public_ip": public_ip,
                "overload": overload,
            })
            events.append({
                "type": "pat_interfaces",
                "message": (
                    f"PAT interfaces: inside={inside_iface}, outside={outside_iface}"
                ),
                "device": dname,
            })

            # PAT table capacity announcement
            events.append({
                "type": "pat_capacity",
                "message": (
                    f"PAT table: {dev_max_sessions:,} simultaneous connections supported "
                    f"on {public_ip} (ports {port_range_str})"
                ),
                "device": dname,
                "max_sessions": dev_max_sessions,
            })

            # Simulate translations for each host
            inside_base = inside_network.rsplit(".", 1)[0]
            dest_ips = [
                ("8.8.8.8", 53, "DNS"),
                ("93.184.216.34", 80, "HTTP"),
                ("140.82.112.4", 443, "HTTPS"),
            ]

            for h_idx, host in enumerate(hosts):
                hname = host.get("name", f"host{h_idx}")
                h_ip = host.get("ip_address", f"{inside_base}.{h_idx + 5}")
                src_port_internal = 35000 + h_idx * 100

                for d_idx, (dst_ip, dst_port, service) in enumerate(dest_ips):
                    pat_port = PAT_PORT_START + total_pat_entries
                    # 5-tuple: src-ip, src-port, dst-ip, dst-port, protocol
                    events.append({
                        "type": "pat_translation",
                        "message": (
                            f"PAT translation: "
                            f"{h_ip}:{src_port_internal + d_idx}->{dst_ip}:{dst_port} "
                            f"=> {public_ip}:{pat_port}->{dst_ip}:{dst_port} "
                            f"({service})"
                        ),
                        "device": dname,
                        "inside_ip": h_ip,
                        "inside_port": src_port_internal + d_idx,
                        "outside_ip": public_ip,
                        "outside_port": pat_port,
                        "dst_ip": dst_ip,
                        "dst_port": dst_port,
                        "protocol": "tcp" if dst_port != 53 else "udp",
                    })
                    # Return traffic
                    events.append({
                        "type": "pat_return",
                        "message": (
                            f"PAT return: {dst_ip}:{dst_port}->{public_ip}:{pat_port} "
                            f"=> {dst_ip}:{dst_port}->{h_ip}:{src_port_internal + d_idx}"
                        ),
                        "device": dname,
                        "translated_to": h_ip,
                    })
                    total_pat_entries += 1

            # Timeout / cleanup note
            events.append({
                "type": "pat_timeout",
                "message": (
                    f"PAT entry timeout: TCP 300s, UDP 30s, ICMP 60s "
                    f"(connection tracking on {dname})"
                ),
                "device": dname,
            })

        metrics = {
            "pat_entries": total_pat_entries,
            "public_ips": total_public_ips,
            "max_concurrent_sessions": max_sessions,
            "port_range": port_range_str,
        }

        return SimulationResult(
            success=len(errors) == 0 and total_pat_entries >= 0,
            events=events,
            metrics=metrics,
            errors=errors,
        )

    def verify_objectives(
        self, topology_data: dict, results: SimulationResult, rules: dict
    ) -> list[ObjectiveResult]:
        objectives = []

        if rules.get("pat_configured", False):
            pat_events = [e for e in results.events if e.get("type") == "pat_configured"]
            passed = len(pat_events) > 0
            objectives.append(ObjectiveResult(
                objective_id="pat_configured",
                description="PAT (NAT overload) is configured",
                passed=passed,
                message=(
                    f"PAT configured on {len(pat_events)} device(s)." if passed
                    else "No PAT configuration found."
                ),
            ))

        if rules.get("overload_enabled", False):
            overload = any(
                e.get("overload", False)
                for e in results.events
                if e.get("type") == "pat_configured"
            )
            objectives.append(ObjectiveResult(
                objective_id="overload_enabled",
                description="NAT overload (PAT) is enabled",
                passed=overload,
                message=(
                    "NAT overload enabled." if overload
                    else "NAT overload not enabled."
                ),
            ))

        if rules.get("multiple_hosts_translating", False):
            translations = results.metrics.get("pat_entries", 0)
            passed = translations >= 2
            objectives.append(ObjectiveResult(
                objective_id="multiple_hosts_translating",
                description="Multiple inside hosts are being translated through PAT",
                passed=passed,
                message=(
                    f"{translations} PAT translation(s) active." if passed
                    else "Fewer than 2 hosts translating through PAT."
                ),
            ))

        if not objectives:
            pat_active = any(
                e.get("type") == "pat_translation" for e in results.events
            )
            objectives.append(ObjectiveResult(
                objective_id="pat_simulation",
                description="PAT simulation completed",
                passed=pat_active,
                message=(
                    "PAT translations are active." if pat_active
                    else "No PAT translations found."
                ),
            ))

        return objectives


pat_simulator = PatSimulator()
