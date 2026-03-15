from app.engine.base import BaseSimulator, SimulationResult, ObjectiveResult


class WirelessApSimulator(BaseSimulator):
    def validate_topology(self, topology_data: dict) -> list[str]:
        errors = []
        devices = topology_data.get("devices", [])
        aps = [
            d for d in devices
            if d.get("type", "").lower() in {
                "access_point", "ap", "wireless_ap", "wap"
            }
        ]
        if not aps:
            errors.append(
                "Wireless AP simulation requires at least one access point device "
                "(type: access_point, ap, wireless_ap, or wap)."
            )
        return errors

    def simulate(self, topology_data: dict, configuration: dict) -> SimulationResult:
        devices = topology_data.get("devices", [])
        events = []
        errors = []

        ap_types = {"access_point", "ap", "wireless_ap", "wap"}
        client_types = {
            "station", "wireless_client", "laptop", "phone",
            "mobile", "pc", "host", "workstation"
        }

        aps = [d for d in devices if d.get("type", "").lower() in ap_types]
        clients = [d for d in devices if d.get("type", "").lower() in client_types]

        if not aps:
            aps = [d for d in devices if "ap" in d.get("name", "").lower()]
        if not aps:
            errors.append("No access point devices found in topology.")
            return SimulationResult(success=False, events=events, errors=errors)

        total_ssids = set()
        total_associated = 0
        total_channel_utilization = 0.0
        dhcp_assigned_clients = []

        for ap_idx, ap in enumerate(aps):
            ap_name = ap["name"]
            cfg = configuration.get(ap_name, {})
            ap_cfg = cfg.get("wireless", ap.get("wireless", cfg.get("ap", ap.get("ap", {}))))

            # Radio configuration
            band = ap_cfg.get("band", "2.4GHz")
            standard = ap_cfg.get("standard", "802.11n")
            channel = ap_cfg.get("channel", [1, 6, 11][ap_idx % 3])
            channel_width = ap_cfg.get("channel_width", "20MHz")
            tx_power = ap_cfg.get("tx_power", 20)  # dBm
            ssids_cfg = ap_cfg.get("ssids", ap.get("ssids", []))
            if not ssids_cfg:
                ssids_cfg = [{"ssid": "CorpNet", "vlan": 10, "security": "WPA2"}]

            events.append({
                "type": "ap_radio",
                "message": (
                    f"AP {ap_name} radio: {standard} {band} channel {channel} "
                    f"{channel_width} (tx power {tx_power}dBm)"
                ),
                "device": ap_name,
                "band": band,
                "channel": channel,
                "standard": standard,
            })

            for ssid_cfg in ssids_cfg:
                ssid = ssid_cfg.get("ssid", ssid_cfg) if isinstance(ssid_cfg, dict) else str(ssid_cfg)
                vlan = ssid_cfg.get("vlan", 1) if isinstance(ssid_cfg, dict) else 1
                security = ssid_cfg.get("security", "WPA2") if isinstance(ssid_cfg, dict) else "WPA2"
                total_ssids.add(ssid)

                events.append({
                    "type": "ssid_broadcast",
                    "message": (
                        f"SSID '{ssid}' broadcasting on {ap_name} "
                        f"(VLAN {vlan}, security {security})"
                    ),
                    "device": ap_name,
                    "ssid": ssid,
                    "vlan": vlan,
                })

                # Associate clients to this AP/SSID
                ap_clients = [
                    c for c in clients
                    if c.get("ssid", ssid) == ssid or c.get("ap", ap_name) == ap_name
                ]
                if not ap_clients:
                    # Auto-assign clients round-robin to APs
                    start = ap_idx * max(1, len(clients) // len(aps))
                    end = start + max(1, len(clients) // len(aps))
                    ap_clients = clients[start:end]

                for c_idx, client in enumerate(ap_clients):
                    cname = client.get("name", f"Station{c_idx + 1}")
                    rssi = -(55 + c_idx * 5)  # simulated signal strength

                    # 802.11 probe
                    events.append({
                        "type": "probe_request",
                        "message": f"Client {cname} probe request (SSID: '{ssid}')",
                        "device": cname,
                        "ssid": ssid,
                    })
                    events.append({
                        "type": "probe_response",
                        "message": (
                            f"AP {ap_name} probe response to {cname} "
                            f"(RSSI {rssi}dBm, channel {channel})"
                        ),
                        "device": ap_name,
                        "rssi": rssi,
                    })

                    # 802.11 authentication (open system before WPA2 handshake)
                    events.append({
                        "type": "dot11_auth",
                        "message": (
                            f"802.11 authentication (open system) {cname} <-> {ap_name}"
                        ),
                        "device": cname,
                    })

                    # Association
                    aid = total_associated + c_idx + 1
                    events.append({
                        "type": "association_request",
                        "message": (
                            f"Association request from {cname} -> {ap_name} "
                            f"(SSID '{ssid}', capabilities: {standard})"
                        ),
                        "device": cname,
                    })
                    events.append({
                        "type": "association_response",
                        "message": (
                            f"Association response {ap_name} -> {cname}: "
                            f"SUCCESS (AID {aid}, status 0)"
                        ),
                        "device": ap_name,
                        "aid": aid,
                    })

                    # DHCP
                    dhcp_server = cfg.get("dhcp_server", ap_cfg.get("dhcp_server", True))
                    if dhcp_server:
                        base_octet = 100 + ap_idx * 50 + c_idx
                        dhcp_ip = f"192.168.{10 + vlan}.{base_octet}"
                        events.append({
                            "type": "dhcp_assigned",
                            "message": (
                                f"DHCP lease for {cname}: {dhcp_ip}/24 "
                                f"(GW 192.168.{10 + vlan}.1)"
                            ),
                            "device": cname,
                            "ip_address": dhcp_ip,
                        })
                        dhcp_assigned_clients.append(cname)

                    total_associated += 1

            # Channel utilization estimate
            utilization = min(95.0, 15.0 + total_associated * 3.5)
            total_channel_utilization += utilization

        avg_utilization = (
            total_channel_utilization / len(aps) if aps else 0.0
        )

        metrics = {
            "access_points": len(aps),
            "ssids": len(total_ssids),
            "associated_clients": total_associated,
            "channel_utilization_pct": round(avg_utilization, 1),
            "dhcp_assigned": len(dhcp_assigned_clients),
        }

        return SimulationResult(
            success=len(errors) == 0 and len(aps) > 0,
            events=events,
            metrics=metrics,
            errors=errors,
        )

    def verify_objectives(
        self, topology_data: dict, results: SimulationResult, rules: dict
    ) -> list[ObjectiveResult]:
        objectives = []

        if rules.get("ssid_configured", False):
            ssids = results.metrics.get("ssids", 0)
            passed = ssids > 0
            objectives.append(ObjectiveResult(
                objective_id="ssid_configured",
                description="SSID(s) are configured and broadcasting",
                passed=passed,
                message=(
                    f"{ssids} SSID(s) broadcasting." if passed
                    else "No SSIDs configured."
                ),
            ))

        if rules.get("clients_associated", False):
            associated = results.metrics.get("associated_clients", 0)
            passed = associated > 0
            objectives.append(ObjectiveResult(
                objective_id="clients_associated",
                description="Wireless clients have associated with the AP",
                passed=passed,
                message=(
                    f"{associated} client(s) associated." if passed
                    else "No clients associated with any AP."
                ),
            ))

        if rules.get("dhcp_assigned", False):
            dhcp = results.metrics.get("dhcp_assigned", 0)
            passed = dhcp > 0
            objectives.append(ObjectiveResult(
                objective_id="dhcp_assigned",
                description="DHCP addresses assigned to wireless clients",
                passed=passed,
                message=(
                    f"{dhcp} DHCP lease(s) assigned to wireless clients." if passed
                    else "No DHCP leases assigned to wireless clients."
                ),
            ))

        if not objectives:
            ap_radios = any(e.get("type") == "ap_radio" for e in results.events)
            objectives.append(ObjectiveResult(
                objective_id="ap_simulation",
                description="Wireless AP simulation completed",
                passed=ap_radios,
                message=(
                    "Access points configured and operational." if ap_radios
                    else "No access point configuration detected."
                ),
            ))

        return objectives


wireless_ap_simulator = WirelessApSimulator()
