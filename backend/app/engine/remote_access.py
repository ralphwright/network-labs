from app.engine.base import BaseSimulator, SimulationResult, ObjectiveResult


class RemoteAccessSimulator(BaseSimulator):
    def validate_topology(self, topology_data: dict) -> list[str]:
        errors = []
        devices = topology_data.get("devices", [])
        concentrators = [
            d for d in devices
            if d.get("type", "").lower() in {
                "vpn_gateway", "firewall", "router", "vpn_concentrator", "asa"
            } and (
                d.get("vpn") or d.get("ipsec") or d.get("vpn_gateway", False)
                or d.get("type", "").lower() in {"vpn_gateway", "vpn_concentrator", "asa"}
            )
        ]
        clients = [
            d for d in devices
            if d.get("type", "").lower() in {
                "vpn_client", "pc", "host", "workstation", "laptop"
            }
        ]
        if not concentrators:
            errors.append(
                "Remote Access VPN requires a VPN gateway/concentrator or firewall "
                "(set type to vpn_gateway, vpn_concentrator, firewall, or asa)."
            )
        if not clients:
            errors.append(
                "Remote Access VPN requires at least one VPN client device "
                "(type: vpn_client, pc, host, workstation, or laptop)."
            )
        return errors

    def simulate(self, topology_data: dict, configuration: dict) -> SimulationResult:
        devices = topology_data.get("devices", [])
        events = []
        errors = []

        gateway_types = {
            "vpn_gateway", "firewall", "router", "vpn_concentrator", "asa"
        }
        client_types = {"vpn_client", "pc", "host", "workstation", "laptop"}

        gateways = [
            d for d in devices
            if d.get("type", "").lower() in gateway_types
        ]
        clients = [
            d for d in devices
            if d.get("type", "").lower() in client_types
        ]

        if not gateways:
            gateways = [devices[0]] if devices else []
        if not clients:
            clients = devices[1:] if len(devices) > 1 else []

        # Build VPN gateway config
        gw_configs: dict[str, dict] = {}
        for idx, gw in enumerate(gateways):
            name = gw["name"]
            cfg = configuration.get(name, {})
            vpn_cfg = cfg.get("vpn", gw.get("vpn", cfg.get("ipsec", gw.get("ipsec", {}))))
            gw_ip = vpn_cfg.get("outside_ip", gw.get("outside_ip", f"203.0.113.{idx + 1}"))
            auth_method = vpn_cfg.get("auth_method", "pre-shared-key")
            ike_version = int(vpn_cfg.get("ike_version", 2))
            ike_mode = vpn_cfg.get("ike_mode", "main")
            encryption = vpn_cfg.get("encryption", "AES-256")
            hash_alg = vpn_cfg.get("hash", "SHA-256")
            dh_group = int(vpn_cfg.get("dh_group", 14))
            esp_enc = vpn_cfg.get("esp_encryption", "AES-128")
            client_pool = vpn_cfg.get("client_pool", "172.16.10.0/24")
            split_tunnel = vpn_cfg.get("split_tunnel", True)
            split_networks = vpn_cfg.get("split_networks", ["10.0.0.0/8"])
            gw_configs[name] = {
                "gw_ip": gw_ip,
                "auth_method": auth_method,
                "ike_version": ike_version,
                "ike_mode": ike_mode,
                "encryption": encryption,
                "hash": hash_alg,
                "dh_group": dh_group,
                "esp_encryption": esp_enc,
                "client_pool": client_pool,
                "split_tunnel": split_tunnel,
                "split_networks": split_networks,
            }

        # Select primary gateway
        primary_gw = gateways[0]["name"] if gateways else "VPN-GW"
        gw_cfg = gw_configs.get(primary_gw, {
            "gw_ip": "203.0.113.1",
            "auth_method": "pre-shared-key",
            "ike_version": 2,
            "ike_mode": "main",
            "encryption": "AES-256",
            "hash": "SHA-256",
            "dh_group": 14,
            "esp_encryption": "AES-128",
            "client_pool": "172.16.10.0/24",
            "split_tunnel": True,
            "split_networks": ["10.0.0.0/8"],
        })

        phase1_time_ms = 350
        phase2_time_ms = 120
        client_ip_base = 4  # 172.16.10.x start

        for idx, client in enumerate(clients):
            cname = client.get("name", f"Client{idx + 1}")
            ccfg = configuration.get(cname, {}).get("vpn", {})
            client_src_ip = ccfg.get("src_ip", client.get("ip_address", f"198.51.100.{idx + 10}"))

            # IKE Phase 1 — ISAKMP SA
            events.append({
                "type": "ike_phase1_init",
                "message": (
                    f"IKE Phase 1 initiated {cname}({client_src_ip})->VPN-GW({gw_cfg['gw_ip']})"
                ),
                "client": cname,
                "gateway": primary_gw,
            })
            mode_label = "Main Mode" if gw_cfg["ike_mode"] == "main" else "Aggressive Mode"
            events.append({
                "type": "ike_phase1_propose",
                "message": (
                    f"IKE Phase 1 {mode_label} proposal: "
                    f"enc={gw_cfg['encryption']}, hash={gw_cfg['hash']}, "
                    f"auth={gw_cfg['auth_method']}, DH-group={gw_cfg['dh_group']}"
                ),
                "client": cname,
            })
            events.append({
                "type": "ike_phase1_dh",
                "message": (
                    f"Diffie-Hellman Group {gw_cfg['dh_group']} key exchange completed "
                    f"(shared secret derived)"
                ),
                "client": cname,
            })
            events.append({
                "type": "ike_phase1_established",
                "message": (
                    f"ISAKMP SA established "
                    f"({gw_cfg['encryption']}, {gw_cfg['hash']}, DH-{gw_cfg['dh_group']})"
                ),
                "client": cname,
                "gateway": primary_gw,
                "time_ms": phase1_time_ms + idx * 20,
            })

            # IKE Phase 2 — IPSec SA (Quick Mode)
            events.append({
                "type": "ike_phase2_init",
                "message": f"IKE Phase 2 Quick Mode: IPSec SA negotiation {cname}<->VPN-GW",
                "client": cname,
            })
            events.append({
                "type": "ike_phase2_established",
                "message": (
                    f"IKE Phase 2: IPSec SA negotiated (ESP, {gw_cfg['esp_encryption']}, "
                    f"HMAC-SHA256, lifetime 3600s)"
                ),
                "client": cname,
                "gateway": primary_gw,
                "time_ms": phase2_time_ms + idx * 10,
            })

            # Client IP assignment from pool
            client_pool_base = gw_cfg["client_pool"].rsplit(".", 1)[0]
            assigned_ip = f"{client_pool_base}.{client_ip_base + idx}"
            events.append({
                "type": "vpn_ip_assigned",
                "message": f"VPN Client IP assigned: {assigned_ip} -> {cname}",
                "client": cname,
                "ip_address": assigned_ip,
            })

            # Split tunneling / full tunnel
            if gw_cfg["split_tunnel"]:
                networks_str = ", ".join(gw_cfg["split_networks"])
                events.append({
                    "type": "split_tunnel",
                    "message": (
                        f"Split tunnel: only {networks_str} via VPN for {cname} "
                        f"(all other traffic: direct Internet)"
                    ),
                    "client": cname,
                    "networks": gw_cfg["split_networks"],
                })
            else:
                events.append({
                    "type": "full_tunnel",
                    "message": (
                        f"Full tunnel: all traffic routed via VPN for {cname} "
                        f"(default route -> VPN)"
                    ),
                    "client": cname,
                })

        metrics = {
            "vpn_clients": len(clients),
            "ike_phase1_time_ms": phase1_time_ms,
            "ike_phase2_time_ms": phase2_time_ms,
            "encryption": gw_cfg["encryption"],
            "esp_encryption": gw_cfg["esp_encryption"],
            "auth_method": gw_cfg["auth_method"],
            "dh_group": gw_cfg["dh_group"],
            "split_tunnel": gw_cfg["split_tunnel"],
        }

        return SimulationResult(
            success=len(errors) == 0 and len(clients) > 0,
            events=events,
            metrics=metrics,
            errors=errors,
        )

    def verify_objectives(
        self, topology_data: dict, results: SimulationResult, rules: dict
    ) -> list[ObjectiveResult]:
        objectives = []

        if rules.get("ike_phase1", False):
            phase1 = any(
                e.get("type") == "ike_phase1_established" for e in results.events
            )
            objectives.append(ObjectiveResult(
                objective_id="ike_phase1",
                description="IKE Phase 1 (ISAKMP SA) established",
                passed=phase1,
                message=(
                    "IKE Phase 1 ISAKMP SA established." if phase1
                    else "IKE Phase 1 did not complete."
                ),
            ))

        if rules.get("ike_phase2", False):
            phase2 = any(
                e.get("type") == "ike_phase2_established" for e in results.events
            )
            objectives.append(ObjectiveResult(
                objective_id="ike_phase2",
                description="IKE Phase 2 (IPSec SA) established",
                passed=phase2,
                message=(
                    "IKE Phase 2 IPSec SA established." if phase2
                    else "IKE Phase 2 did not complete."
                ),
            ))

        if rules.get("client_connectivity", False):
            ip_assigned = any(
                e.get("type") == "vpn_ip_assigned" for e in results.events
            )
            clients = results.metrics.get("vpn_clients", 0)
            objectives.append(ObjectiveResult(
                objective_id="client_connectivity",
                description="VPN clients received IP addresses and are connected",
                passed=ip_assigned and clients > 0,
                message=(
                    f"{clients} VPN client(s) connected with assigned IPs." if ip_assigned
                    else "No VPN client IP assignments found."
                ),
            ))

        if not objectives:
            phase1_done = any(
                e.get("type") == "ike_phase1_established" for e in results.events
            )
            objectives.append(ObjectiveResult(
                objective_id="vpn_established",
                description="Remote Access VPN tunnel established",
                passed=phase1_done,
                message=(
                    "VPN tunnels established." if phase1_done
                    else "VPN tunnel establishment failed."
                ),
            ))

        return objectives


remote_access_simulator = RemoteAccessSimulator()
