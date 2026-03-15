from app.engine.base import BaseSimulator, SimulationResult, ObjectiveResult


class WirelessControllerSimulator(BaseSimulator):
    def validate_topology(self, topology_data: dict) -> list[str]:
        errors = []
        devices = topology_data.get("devices", [])
        controllers = [
            d for d in devices
            if d.get("type", "").lower() in {
                "wireless_controller", "wlc", "controller", "wifi_controller"
            }
        ]
        aps = [
            d for d in devices
            if d.get("type", "").lower() in {
                "access_point", "ap", "wireless_ap", "wap", "lightweight_ap"
            }
        ]
        if not controllers:
            errors.append(
                "Wireless Controller simulation requires a wireless controller device "
                "(type: wireless_controller, wlc, or controller)."
            )
        if not aps:
            errors.append(
                "Wireless Controller simulation requires at least one AP "
                "(type: access_point, ap, wireless_ap, or lightweight_ap)."
            )
        return errors

    def simulate(self, topology_data: dict, configuration: dict) -> SimulationResult:
        devices = topology_data.get("devices", [])
        events = []
        errors = []

        controller_types = {
            "wireless_controller", "wlc", "controller", "wifi_controller"
        }
        ap_types = {
            "access_point", "ap", "wireless_ap", "wap", "lightweight_ap"
        }
        client_types = {
            "station", "wireless_client", "laptop", "phone",
            "mobile", "pc", "host", "workstation"
        }

        controllers = [d for d in devices if d.get("type", "").lower() in controller_types]
        aps = [d for d in devices if d.get("type", "").lower() in ap_types]
        clients = [d for d in devices if d.get("type", "").lower() in client_types]

        if not controllers:
            errors.append("No wireless controller found.")
            return SimulationResult(success=False, events=events, errors=errors)
        if not aps:
            errors.append("No access points found.")
            return SimulationResult(success=False, events=events, errors=errors)

        capwap_tunnels = 0
        managed_clients = 0
        roaming_events = 0

        for ctrl_idx, ctrl in enumerate(controllers):
            ctrl_name = ctrl["name"]
            cfg = configuration.get(ctrl_name, {})
            ctrl_cfg = cfg.get("wlc", ctrl.get("wlc", cfg.get("controller", ctrl.get("controller", {}))))

            ctrl_ip = ctrl_cfg.get(
                "management_ip",
                ctrl.get("management_ip", ctrl.get("ip_address", f"192.168.1.{100 + ctrl_idx}"))
            )
            dtls_enabled = ctrl_cfg.get("dtls", True)
            ssids = ctrl_cfg.get("ssids", ctrl.get("ssids", [
                {"ssid": "CorpNet", "vlan": 10, "security": "WPA2-Enterprise"},
            ]))
            rf_management = ctrl_cfg.get("rf_management", True)
            pmk_caching = ctrl_cfg.get("pmk_caching", True)

            # CAPWAP discovery and join for each AP
            for ap_idx, ap in enumerate(aps):
                ap_name = ap["name"]
                ap_cfg_raw = configuration.get(ap_name, {}).get("wireless", ap.get("wireless", {}))
                ap_ip = ap_cfg_raw.get("ap_ip", ap.get("ip_address", f"192.168.1.{ap_idx + 10}"))

                # CAPWAP Discovery
                events.append({
                    "type": "capwap_discovery",
                    "message": (
                        f"AP {ap_name} CAPWAP discovery via broadcast "
                        f"(src {ap_ip}, dst 255.255.255.255:5246)"
                    ),
                    "device": ap_name,
                })
                events.append({
                    "type": "capwap_discovery_response",
                    "message": (
                        f"Controller {ctrl_ip} responds to {ap_name}: "
                        f"CAPWAP Discovery Response (priority 1)"
                    ),
                    "device": ctrl_name,
                    "ap": ap_name,
                })

                # DTLS handshake + CAPWAP tunnel
                dtls_str = " (DTLS encrypted)" if dtls_enabled else ""
                events.append({
                    "type": "capwap_tunnel",
                    "message": (
                        f"CAPWAP tunnel {ap_name}<->{ctrl_name} established{dtls_str} "
                        f"(UDP 5246/5247)"
                    ),
                    "ap": ap_name,
                    "controller": ctrl_name,
                    "dtls": dtls_enabled,
                })
                capwap_tunnels += 1

                # AP join and configuration push
                ssid_names = [
                    s.get("ssid", s) if isinstance(s, dict) else s
                    for s in ssids
                ]
                vlan_list = [
                    str(s.get("vlan", 1)) if isinstance(s, dict) else "1"
                    for s in ssids
                ]
                events.append({
                    "type": "ap_joined",
                    "message": (
                        f"AP {ap_name} joined controller {ctrl_name}, "
                        f"configured: SSID(s) [{', '.join(ssid_names)}] "
                        f"VLAN [{', '.join(vlan_list)}]"
                    ),
                    "device": ap_name,
                    "controller": ctrl_name,
                    "ssids": ssid_names,
                })

                # RF management — auto channel and power
                if rf_management:
                    channel = [1, 6, 11, 36, 40, 44][ap_idx % 6]
                    power = 20 - ap_idx * 2
                    events.append({
                        "type": "rf_management",
                        "message": (
                            f"RF management: {ap_name} assigned channel {channel}, "
                            f"Tx power {max(8, power)}dBm (auto-selected by controller)"
                        ),
                        "device": ap_name,
                        "channel": channel,
                        "power": max(8, power),
                    })

            # Client associations via controller
            for c_idx, client in enumerate(clients):
                cname = client.get("name", f"Station{c_idx + 1}")
                target_ap = aps[c_idx % len(aps)]["name"] if aps else "AP1"
                ssid = ssid_names[0] if ssid_names else "CorpNet"
                events.append({
                    "type": "client_association",
                    "message": (
                        f"Client {cname} associated to {target_ap} "
                        f"(SSID '{ssid}', centrally managed)"
                    ),
                    "device": cname,
                    "ap": target_ap,
                    "controller": ctrl_name,
                })
                managed_clients += 1

            # Roaming simulation (if multiple APs)
            if len(aps) >= 2:
                roaming_client = clients[0].get("name", "Station1") if clients else "Station1"
                from_ap = aps[0]["name"]
                to_ap = aps[1]["name"]
                pmk_str = ", PMK cached" if pmk_caching else ""
                events.append({
                    "type": "client_roam",
                    "message": (
                        f"Client roam: {roaming_client} {from_ap}->{to_ap} "
                        f"(seamless{pmk_str}, L2 roam)"
                    ),
                    "client": roaming_client,
                    "from_ap": from_ap,
                    "to_ap": to_ap,
                })
                roaming_events += 1

        metrics = {
            "controller_aps": len(aps),
            "managed_clients": managed_clients,
            "capwap_tunnels": capwap_tunnels,
            "roaming_events": roaming_events,
            "controllers": len(controllers),
        }

        return SimulationResult(
            success=len(errors) == 0 and capwap_tunnels > 0,
            events=events,
            metrics=metrics,
            errors=errors,
        )

    def verify_objectives(
        self, topology_data: dict, results: SimulationResult, rules: dict
    ) -> list[ObjectiveResult]:
        objectives = []

        if rules.get("capwap_established", False):
            tunnels = results.metrics.get("capwap_tunnels", 0)
            passed = tunnels > 0
            objectives.append(ObjectiveResult(
                objective_id="capwap_established",
                description="CAPWAP tunnels established between APs and controller",
                passed=passed,
                message=(
                    f"{tunnels} CAPWAP tunnel(s) established." if passed
                    else "No CAPWAP tunnels established."
                ),
            ))

        if rules.get("ap_joined", False):
            joined = any(e.get("type") == "ap_joined" for e in results.events)
            ap_count = results.metrics.get("controller_aps", 0)
            objectives.append(ObjectiveResult(
                objective_id="ap_joined",
                description="APs have joined the wireless controller",
                passed=joined,
                message=(
                    f"{ap_count} AP(s) joined the controller." if joined
                    else "No APs have joined the controller."
                ),
            ))

        if rules.get("centralized_management", False):
            rf_managed = any(e.get("type") == "rf_management" for e in results.events)
            client_managed = results.metrics.get("managed_clients", 0) > 0
            passed = rf_managed or client_managed
            objectives.append(ObjectiveResult(
                objective_id="centralized_management",
                description="Centralized RF and client management is active",
                passed=passed,
                message=(
                    "Centralized management operational (RF + client)." if passed
                    else "Centralized management not active."
                ),
            ))

        if not objectives:
            capwap = any(e.get("type") == "capwap_tunnel" for e in results.events)
            objectives.append(ObjectiveResult(
                objective_id="wlc_simulation",
                description="Wireless controller simulation completed",
                passed=capwap,
                message=(
                    "CAPWAP tunnels established, APs managed." if capwap
                    else "No CAPWAP tunnels established."
                ),
            ))

        return objectives


wireless_controller_simulator = WirelessControllerSimulator()
