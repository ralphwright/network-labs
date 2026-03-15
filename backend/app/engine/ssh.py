from app.engine.base import BaseSimulator, SimulationResult, ObjectiveResult


class SshSimulator(BaseSimulator):
    def validate_topology(self, topology_data: dict) -> list[str]:
        errors = []
        devices = topology_data.get("devices", [])
        ssh_servers = [
            d for d in devices
            if d.get("ssh_enabled") or d.get("ssh") or
            d.get("type", "").lower() in {
                "router", "switch", "multilayer_switch", "layer3_switch", "server"
            }
        ]
        if not ssh_servers:
            errors.append(
                "SSH simulation requires at least one device with SSH configured "
                "(router, switch, server, or set ssh_enabled=true)."
            )
        return errors

    def simulate(self, topology_data: dict, configuration: dict) -> SimulationResult:
        devices = topology_data.get("devices", [])
        events = []
        errors = []

        server_types = {
            "router", "switch", "multilayer_switch", "layer3_switch",
            "firewall", "server", "linux_server"
        }
        client_types = {"pc", "host", "workstation", "laptop", "admin_pc", "management"}

        ssh_servers = [
            d for d in devices
            if d.get("type", "").lower() in server_types
            or d.get("ssh_enabled", False)
            or d.get("ssh", {})
        ]
        ssh_clients = [
            d for d in devices
            if d.get("type", "").lower() in client_types
        ]

        if not ssh_servers:
            ssh_servers = [d for d in devices if d.get("type", "").lower() not in client_types]
        if not ssh_clients:
            ssh_clients = [d for d in devices if d.get("type", "").lower() in client_types]
            if not ssh_clients and len(devices) > 1:
                ssh_clients = [devices[-1]]

        # Per-server SSH config
        server_configs: dict[str, dict] = {}
        for idx, srv in enumerate(ssh_servers):
            name = srv["name"]
            cfg = configuration.get(name, {})
            ssh_cfg = cfg.get("ssh", srv.get("ssh", {}))
            mgmt_ip = ssh_cfg.get(
                "management_ip",
                srv.get("management_ip", srv.get("ip_address", f"192.168.1.{idx + 1}"))
            )
            ssh_version = ssh_cfg.get("version", "SSH-2.0")
            kex = ssh_cfg.get("kex", "diffie-hellman-group14-sha256")
            host_key_type = ssh_cfg.get("host_key_type", "RSA-2048")
            host_key_fp = ssh_cfg.get(
                "host_key_fingerprint",
                f"SHA256:abc{idx:02x}def{idx:02x}123{idx:02x}456{idx:02x}"
            )
            auth_methods = ssh_cfg.get("auth_methods", ["publickey", "password"])
            preferred_auth = auth_methods[0] if auth_methods else "password"
            ciphers = ssh_cfg.get("ciphers", ["aes256-ctr", "aes128-ctr"])
            macs = ssh_cfg.get("macs", ["hmac-sha2-256", "hmac-sha2-512"])
            commands = cfg.get("commands", srv.get("commands", ["show ip route", "show interfaces"]))
            server_configs[name] = {
                "mgmt_ip": mgmt_ip,
                "ssh_version": ssh_version,
                "kex": kex,
                "host_key_type": host_key_type,
                "host_key_fp": host_key_fp,
                "auth_methods": auth_methods,
                "preferred_auth": preferred_auth,
                "ciphers": ciphers,
                "macs": macs,
                "commands": commands,
            }

        kex_time_ms = 85
        total_servers = len(server_configs)

        for srv_idx, (srv_name, srv_cfg) in enumerate(server_configs.items()):
            # Determine connecting client
            if ssh_clients:
                client = ssh_clients[srv_idx % len(ssh_clients)]
                cname = client.get("name", "admin-pc")
                client_ip = client.get("ip_address", f"192.168.1.{200 + srv_idx}")
            else:
                cname = "admin-pc"
                client_ip = "192.168.1.200"

            mgmt_ip = srv_cfg["mgmt_ip"]

            # TCP SYN to port 22
            events.append({
                "type": "tcp_syn",
                "message": (
                    f"TCP SYN {cname}({client_ip}) -> {srv_name}({mgmt_ip}):22"
                ),
                "from": cname,
                "to": srv_name,
                "dst_port": 22,
            })
            events.append({
                "type": "tcp_established",
                "message": (
                    f"TCP connection established {cname} <-> {srv_name}:22 "
                    f"(src port {32768 + srv_idx})"
                ),
                "from": cname,
                "to": srv_name,
            })

            # SSH version exchange
            events.append({
                "type": "ssh_version_exchange",
                "message": (
                    f"SSH-2.0 version exchange: "
                    f"{cname} sends SSH-2.0-OpenSSH_8.9, "
                    f"{srv_name} sends {srv_cfg['ssh_version']}-Cisco-1.25"
                ),
                "client": cname,
                "server": srv_name,
            })

            # Key exchange
            events.append({
                "type": "kex_init",
                "message": (
                    f"Key exchange: {srv_cfg['kex']} "
                    f"(ciphers: {', '.join(srv_cfg['ciphers'])}, "
                    f"MACs: {', '.join(srv_cfg['macs'])})"
                ),
                "kex": srv_cfg["kex"],
                "server": srv_name,
            })
            events.append({
                "type": "kex_dh_exchange",
                "message": (
                    f"DH key exchange: {cname} sends e (client public key), "
                    f"{srv_name} sends f (server public key) + host key signature"
                ),
                "client": cname,
                "server": srv_name,
            })
            events.append({
                "type": "kex_complete",
                "message": (
                    f"Key exchange complete ({kex_time_ms + srv_idx * 5}ms): "
                    f"session keys derived (encryption + MAC)"
                ),
                "time_ms": kex_time_ms + srv_idx * 5,
            })

            # Host key verification
            events.append({
                "type": "host_key_verify",
                "message": (
                    f"Host key fingerprint verified: {srv_cfg['host_key_fp']} "
                    f"({srv_cfg['host_key_type']}) for {srv_name}"
                ),
                "server": srv_name,
                "fingerprint": srv_cfg["host_key_fp"],
            })

            # User authentication
            auth = srv_cfg["preferred_auth"]
            if auth == "publickey":
                events.append({
                    "type": "ssh_auth",
                    "message": (
                        f"Authentication: publickey ({srv_cfg['host_key_type']}) "
                        f"accepted for {cname}@{srv_name}"
                    ),
                    "method": "publickey",
                    "client": cname,
                    "server": srv_name,
                })
            else:
                events.append({
                    "type": "ssh_auth",
                    "message": (
                        f"Authentication: password accepted for {cname}@{srv_name}"
                    ),
                    "method": "password",
                    "client": cname,
                    "server": srv_name,
                })

            # Session establishment
            cipher = srv_cfg["ciphers"][0]
            mac = srv_cfg["macs"][0]
            events.append({
                "type": "ssh_session_established",
                "message": (
                    f"SSH session established {cname} -> {srv_name} "
                    f"(cipher: {cipher}, MAC: {mac})"
                ),
                "client": cname,
                "server": srv_name,
                "cipher": cipher,
            })

            # Command execution simulation
            for cmd in srv_cfg["commands"][:3]:
                events.append({
                    "type": "ssh_command",
                    "message": f"Command executed on {srv_name}: {cmd}",
                    "device": srv_name,
                    "command": cmd,
                })

        # Determine session security rating
        preferred_kex = list(server_configs.values())[0]["kex"] if server_configs else ""
        if "group14" in preferred_kex or "group16" in preferred_kex:
            session_security = "strong"
        elif "group1" in preferred_kex:
            session_security = "weak"
        else:
            session_security = "moderate"

        primary_cfg = list(server_configs.values())[0] if server_configs else {}

        metrics = {
            "ssh_servers": total_servers,
            "key_exchange_ms": kex_time_ms,
            "auth_method": primary_cfg.get("preferred_auth", "password"),
            "session_security": session_security,
            "ciphers": primary_cfg.get("ciphers", []),
            "kex_algorithm": primary_cfg.get("kex", ""),
        }

        return SimulationResult(
            success=len(errors) == 0 and total_servers > 0,
            events=events,
            metrics=metrics,
            errors=errors,
        )

    def verify_objectives(
        self, topology_data: dict, results: SimulationResult, rules: dict
    ) -> list[ObjectiveResult]:
        objectives = []

        if rules.get("ssh_enabled", False):
            servers = results.metrics.get("ssh_servers", 0)
            passed = servers > 0
            objectives.append(ObjectiveResult(
                objective_id="ssh_enabled",
                description="SSH is enabled on network devices",
                passed=passed,
                message=(
                    f"SSH enabled on {servers} device(s)." if passed
                    else "No SSH-enabled devices found."
                ),
            ))

        if rules.get("strong_encryption", False):
            security = results.metrics.get("session_security", "weak")
            passed = security == "strong"
            objectives.append(ObjectiveResult(
                objective_id="strong_encryption",
                description="SSH uses strong encryption (DH group14 or higher)",
                passed=passed,
                message=(
                    f"Strong encryption configured (session_security={security})." if passed
                    else f"Weak or moderate encryption in use (session_security={security})."
                ),
            ))

        if rules.get("key_auth_configured", False):
            key_auth = any(
                e.get("type") == "ssh_auth" and e.get("method") == "publickey"
                for e in results.events
            )
            objectives.append(ObjectiveResult(
                objective_id="key_auth_configured",
                description="SSH public key authentication is configured",
                passed=key_auth,
                message=(
                    "Public key authentication in use." if key_auth
                    else "Password authentication in use; public key not configured."
                ),
            ))

        if not objectives:
            session_up = any(
                e.get("type") == "ssh_session_established" for e in results.events
            )
            objectives.append(ObjectiveResult(
                objective_id="ssh_session",
                description="SSH sessions established successfully",
                passed=session_up,
                message=(
                    "SSH sessions established." if session_up
                    else "No SSH sessions established."
                ),
            ))

        return objectives


ssh_simulator = SshSimulator()
