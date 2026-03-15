from app.engine.base import BaseSimulator, SimulationResult, ObjectiveResult


class WirelessSecuritySimulator(BaseSimulator):
    def validate_topology(self, topology_data: dict) -> list[str]:
        errors = []
        devices = topology_data.get("devices", [])
        radius_servers = [
            d for d in devices
            if d.get("type", "").lower() in {"radius_server", "aaa_server", "server"}
            and (d.get("radius") or d.get("aaa") or
                 d.get("type", "").lower() in {"radius_server", "aaa_server"})
        ]
        aps = [
            d for d in devices
            if d.get("type", "").lower() in {
                "access_point", "ap", "wireless_ap", "wap", "lightweight_ap"
            }
        ]
        if not radius_servers and not any(
            d.get("radius") for d in devices
        ):
            errors.append(
                "Wireless Security simulation requires a RADIUS server "
                "(type: radius_server, aaa_server, or configure radius=true on server)."
            )
        if not aps:
            errors.append(
                "Wireless Security simulation requires at least one AP "
                "(type: access_point, ap, wireless_ap, or wap)."
            )
        return errors

    def simulate(self, topology_data: dict, configuration: dict) -> SimulationResult:
        devices = topology_data.get("devices", [])
        events = []
        errors = []

        radius_types = {"radius_server", "aaa_server"}
        ap_types = {"access_point", "ap", "wireless_ap", "wap", "lightweight_ap"}
        client_types = {
            "station", "wireless_client", "laptop", "phone",
            "mobile", "pc", "host", "workstation"
        }

        radius_servers = [
            d for d in devices
            if d.get("type", "").lower() in radius_types
            or (d.get("type", "").lower() == "server" and d.get("radius"))
        ]
        aps = [d for d in devices if d.get("type", "").lower() in ap_types]
        clients = [d for d in devices if d.get("type", "").lower() in client_types]

        if not radius_servers:
            # Find any server with radius config
            radius_servers = [d for d in devices if d.get("radius") or d.get("aaa")]
        if not radius_servers:
            radius_servers = [{"name": "RADIUS-Server", "ip_address": "192.168.1.200"}]

        if not aps:
            aps = [{"name": "AP1", "type": "ap"}]
        if not clients:
            clients = [{"name": "Station1", "type": "station"}]

        radius = radius_servers[0]
        radius_name = radius.get("name", "RADIUS-Server")
        radius_ip = radius.get("ip_address", "192.168.1.200")

        # RADIUS / security config
        r_cfg_raw = configuration.get(radius_name, {}).get("radius", radius.get("radius", {}))
        r_cfg = r_cfg_raw if isinstance(r_cfg_raw, dict) else {}
        auth_port = r_cfg.get("auth_port", 1812)
        acct_port = r_cfg.get("acct_port", 1813)

        pmk_cache_entries = 0

        for ap_idx, ap in enumerate(aps):
            ap_name = ap["name"]
            ap_cfg = configuration.get(ap_name, {}).get("wireless", ap.get("wireless", {}))
            wpa_version = ap_cfg.get("wpa_version", "WPA2")
            eap_type = ap_cfg.get("eap_type", "PEAP")
            pmk_caching = ap_cfg.get("pmk_caching", True)
            auth_method = f"{wpa_version}-Enterprise"

            for c_idx, client in enumerate(clients):
                cname = client.get("name", f"Station{c_idx + 1}")

                # WPA2-Enterprise association request
                events.append({
                    "type": "wpa2_assoc_request",
                    "message": (
                        f"Client {cname} association request ({wpa_version}-Enterprise) "
                        f"-> {ap_name}"
                    ),
                    "device": cname,
                    "ap": ap_name,
                })

                # 802.1X EAPOL Start
                events.append({
                    "type": "eapol_start",
                    "message": (
                        f"802.1X EAPOL-Start from {cname} -> {ap_name} "
                        f"(port blocked pending authentication)"
                    ),
                    "device": cname,
                })

                # EAP identity exchange
                events.append({
                    "type": "eap_request_identity",
                    "message": (
                        f"EAP-Request/Identity from {ap_name} -> {cname}"
                    ),
                    "device": ap_name,
                })
                events.append({
                    "type": "eap_response_identity",
                    "message": (
                        f"EAP-Response/Identity from {cname}: "
                        f"user@corp.local"
                    ),
                    "device": cname,
                    "identity": "user@corp.local",
                })

                # RADIUS Access-Request
                events.append({
                    "type": "radius_access_request",
                    "message": (
                        f"RADIUS Access-Request: {ap_name} -> {radius_name}({radius_ip}:{auth_port}) "
                        f"(EAP, NAS-IP {ap.get('ip_address', '192.168.1.' + str(ap_idx + 10))})"
                    ),
                    "device": ap_name,
                    "radius_server": radius_name,
                })

                # EAP method negotiation
                if eap_type == "EAP-TLS":
                    events.append({
                        "type": "eap_tls_start",
                        "message": (
                            f"EAP-TLS: {radius_name} sends TLS Start, "
                            f"{cname} initiates TLS ClientHello"
                        ),
                        "device": cname,
                    })
                    events.append({
                        "type": "eap_tls_cert",
                        "message": (
                            f"EAP-TLS: Certificate exchange (client + server certs), "
                            f"mutual authentication"
                        ),
                    })
                else:  # PEAP
                    events.append({
                        "type": "peap_start",
                        "message": (
                            f"EAP-PEAP: {radius_name} sends PEAP Start (TLS tunnel), "
                            f"{cname} sends TLS ClientHello"
                        ),
                        "device": cname,
                    })
                    events.append({
                        "type": "peap_inner_auth",
                        "message": (
                            f"EAP-PEAP inner method: MSCHAPv2 identity/challenge inside TLS"
                        ),
                    })

                # RADIUS Access-Accept with keying material
                events.append({
                    "type": "radius_access_accept",
                    "message": (
                        f"RADIUS Access-Accept from {radius_name} -> {ap_name}: "
                        f"MS-MPPE-Recv-Key + MS-MPPE-Send-Key (PMK derived)"
                    ),
                    "device": radius_name,
                    "client": cname,
                })

                # 4-way handshake (PTK derivation)
                events.append({
                    "type": "fourway_handshake_1",
                    "message": (
                        f"4-way handshake msg 1/4: {ap_name} -> {cname} (ANonce)"
                    ),
                    "device": ap_name,
                })
                events.append({
                    "type": "fourway_handshake_2",
                    "message": (
                        f"4-way handshake msg 2/4: {cname} -> {ap_name} (SNonce, MIC)"
                    ),
                    "device": cname,
                })
                events.append({
                    "type": "fourway_handshake_3",
                    "message": (
                        f"4-way handshake msg 3/4: {ap_name} -> {cname} (GTK, MIC)"
                    ),
                    "device": ap_name,
                })
                events.append({
                    "type": "fourway_handshake_4",
                    "message": (
                        f"4-way handshake msg 4/4: {cname} -> {ap_name} (ACK) "
                        f"— PTK derived"
                    ),
                    "device": cname,
                })

                # Port unblocked
                events.append({
                    "type": "port_unblocked",
                    "message": (
                        f"{cname} authenticated, 802.1X port unblocked "
                        f"(PTK installed, data traffic permitted)"
                    ),
                    "device": cname,
                })

                # PMK caching
                if pmk_caching:
                    events.append({
                        "type": "pmkid_cache",
                        "message": (
                            f"PMKID cached for {cname} on {ap_name} "
                            f"(fast roaming enabled)"
                        ),
                        "device": ap_name,
                        "client": cname,
                    })
                    pmk_cache_entries += 1

        metrics = {
            "auth_method": f"{wpa_version}-Enterprise" if aps else "WPA2-Enterprise",
            "radius_servers": len(radius_servers),
            "eap_type": eap_type if aps else "PEAP",
            "pmk_cache_entries": pmk_cache_entries,
            "authenticated_clients": len(clients) * len(aps),
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

        if rules.get("wpa2_enterprise", False):
            wpa2_ent = any(
                e.get("type") == "wpa2_assoc_request" for e in results.events
            )
            objectives.append(ObjectiveResult(
                objective_id="wpa2_enterprise",
                description="WPA2-Enterprise (802.1X) authentication configured",
                passed=wpa2_ent,
                message=(
                    "WPA2-Enterprise authentication in use." if wpa2_ent
                    else "WPA2-Enterprise not configured."
                ),
            ))

        if rules.get("radius_auth", False):
            radius = any(
                e.get("type") == "radius_access_accept" for e in results.events
            )
            objectives.append(ObjectiveResult(
                objective_id="radius_auth",
                description="RADIUS authentication completed successfully",
                passed=radius,
                message=(
                    "RADIUS Access-Accept received." if radius
                    else "RADIUS authentication not completed."
                ),
            ))

        if rules.get("eap_negotiated", False):
            eap = any(
                e.get("type") in {"eap_tls_start", "peap_start"} for e in results.events
            )
            eap_type = results.metrics.get("eap_type", "unknown")
            objectives.append(ObjectiveResult(
                objective_id="eap_negotiated",
                description="EAP method negotiated for wireless authentication",
                passed=eap,
                message=(
                    f"EAP type {eap_type} negotiated." if eap
                    else "EAP negotiation not detected."
                ),
            ))

        if not objectives:
            port_unblocked = any(
                e.get("type") == "port_unblocked" for e in results.events
            )
            objectives.append(ObjectiveResult(
                objective_id="wireless_security",
                description="Wireless security authentication completed",
                passed=port_unblocked,
                message=(
                    "Clients authenticated and ports unblocked." if port_unblocked
                    else "Authentication did not complete."
                ),
            ))

        return objectives


wireless_security_simulator = WirelessSecuritySimulator()
