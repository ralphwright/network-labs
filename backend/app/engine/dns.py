from app.engine.base import BaseSimulator, SimulationResult, ObjectiveResult


class DnsSimulator(BaseSimulator):
    def validate_topology(self, topology_data: dict) -> list[str]:
        errors = []
        devices = topology_data.get("devices", [])
        dns_servers = [
            d for d in devices
            if d.get("type", "").lower() in {"dns_server", "server"}
            and (
                "dns" in d.get("name", "").lower()
                or d.get("role", "").lower() == "dns"
                or d.get("services", {}).get("dns", False)
            )
        ]
        if not dns_servers:
            # Fallback: any server
            dns_servers = [d for d in devices if d.get("type", "").lower() == "server"]
        if not dns_servers:
            errors.append("DNS simulation requires at least one DNS server.")
        return errors

    def simulate(self, topology_data: dict, configuration: dict) -> SimulationResult:
        devices = topology_data.get("devices", [])
        events = []
        errors = []

        dns_servers = [
            d for d in devices
            if d.get("type", "").lower() in {"dns_server", "server"}
            and (
                "dns" in d.get("name", "").lower()
                or d.get("role", "").lower() == "dns"
                or d.get("services", {}).get("dns", False)
            )
        ]
        if not dns_servers:
            dns_servers = [d for d in devices if d.get("type", "").lower() == "server"]

        clients = [
            d for d in devices
            if d.get("type", "").lower() in {"pc", "host", "workstation", "server"}
            and d not in dns_servers
        ]

        server = dns_servers[0]
        server_name = server["name"]
        server_cfg = configuration.get(server_name, {})
        dns_cfg = server_cfg.get("dns", server.get("dns_config", {}))

        # Zone configuration
        forward_zone = dns_cfg.get("forward_zone", "example.com")
        reverse_zone = dns_cfg.get("reverse_zone", "1.168.192.in-addr.arpa")
        domain_name = forward_zone

        # Build DNS records
        records = dns_cfg.get("records", [])
        if not records:
            records = [
                {"type": "SOA",  "name": f"{domain_name}.",           "value": f"ns1.{domain_name}. admin.{domain_name}. 2024010101 3600 900 604800 300"},
                {"type": "NS",   "name": f"{domain_name}.",           "value": f"ns1.{domain_name}."},
                {"type": "A",    "name": f"ns1.{domain_name}.",       "value": "192.168.1.2",  "ttl": 300},
                {"type": "A",    "name": f"www.{domain_name}.",       "value": "192.168.1.10", "ttl": 300},
                {"type": "A",    "name": f"mail.{domain_name}.",      "value": "192.168.1.20", "ttl": 300},
                {"type": "A",    "name": f"ftp.{domain_name}.",       "value": "192.168.1.30", "ttl": 300},
                {"type": "CNAME","name": f"smtp.{domain_name}.",      "value": f"mail.{domain_name}."},
                {"type": "MX",   "name": f"{domain_name}.",           "value": f"10 mail.{domain_name}."},
                {"type": "PTR",  "name": "10.1.168.192.in-addr.arpa.","value": f"www.{domain_name}."},
                {"type": "PTR",  "name": "20.1.168.192.in-addr.arpa.","value": f"mail.{domain_name}."},
            ]

        events.append({
            "type": "dns_server_start",
            "message": f"DNS server {server_name} started — authoritative for {domain_name}",
            "device": server_name,
        })

        # Zone load
        events.append({
            "type": "zone_loaded",
            "message": f"Forward zone '{forward_zone}' loaded with {sum(1 for r in records if r['type'] not in ('SOA','NS'))} records",
            "zone": forward_zone,
        })
        events.append({
            "type": "zone_loaded",
            "message": f"Reverse zone '{reverse_zone}' loaded",
            "zone": reverse_zone,
        })

        a_records = {r["name"]: r for r in records if r["type"] == "A"}
        ptr_records = {r["name"]: r for r in records if r["type"] == "PTR"}
        cname_records = {r["name"]: r for r in records if r["type"] == "CNAME"}

        queries_simulated = 0
        cache_hits = 0
        cache = {}

        # Simulate queries from each client
        query_targets = [
            (f"www.{domain_name}", "A"),
            (f"mail.{domain_name}", "A"),
            (f"smtp.{domain_name}", "CNAME"),
            (f"{domain_name}", "MX"),
        ]
        for idx, client in enumerate(clients[:4]):
            client_name = client["name"]
            qname, qtype = query_targets[idx % len(query_targets)]

            events.append({
                "type": "dns_query",
                "message": f"DNS Query from {client_name}: {qname} {qtype}?",
                "device": client_name,
                "query": qname,
                "qtype": qtype,
            })

            cache_key = (qname, qtype)
            if cache_key in cache:
                cache_hits += 1
                events.append({
                    "type": "dns_cache_hit",
                    "message": f"DNS Cache hit: {qname} -> {cache[cache_key]['value']} (TTL remaining {cache[cache_key].get('ttl', 300)}s)",
                })
            else:
                # Recursive resolution steps
                events.append({
                    "type": "dns_recursive",
                    "message": f"DNS Recursive lookup: {qname} {qtype} (authoritative: {domain_name})",
                    "device": server_name,
                })

                fqdn = f"{qname}."
                record = a_records.get(fqdn)

                if qtype == "CNAME" and fqdn in cname_records:
                    cname = cname_records[fqdn]
                    events.append({
                        "type": "dns_cname_follow",
                        "message": f"DNS CNAME: {qname} -> {cname['value']} (following chain)",
                    })
                    target_a = a_records.get(cname["value"])
                    if target_a:
                        record = target_a
                elif qtype == "MX":
                    mx_record = next((r for r in records if r["type"] == "MX"), None)
                    if mx_record:
                        events.append({
                            "type": "dns_response",
                            "message": f"DNS Response: {qname} MX -> {mx_record['value']} (TTL 300)",
                            "device": server_name,
                        })
                        cache[cache_key] = mx_record
                        queries_simulated += 1
                        continue

                if record:
                    ttl = record.get("ttl", 300)
                    events.append({
                        "type": "dns_response",
                        "message": f"DNS Response: {qname} A -> {record['value']} (TTL {ttl})",
                        "device": server_name,
                        "answer": record["value"],
                        "ttl": ttl,
                    })
                    cache[cache_key] = record
                else:
                    events.append({
                        "type": "dns_nxdomain",
                        "message": f"DNS NXDOMAIN: {qname} not found in zone {domain_name}",
                        "device": server_name,
                    })

            queries_simulated += 1

        # Reverse lookup example
        if ptr_records:
            ptr_key = list(ptr_records.keys())[0]
            ptr_val = ptr_records[ptr_key]["value"]
            events.append({
                "type": "dns_ptr",
                "message": f"Reverse lookup: {ptr_key} PTR -> {ptr_val}",
                "device": server_name,
            })
            queries_simulated += 1

        zones_configured = 2  # forward + reverse
        total_records = len(records)

        metrics = {
            "zones_configured": zones_configured,
            "records_total": total_records,
            "queries_simulated": queries_simulated,
            "cache_hits": cache_hits,
        }

        return SimulationResult(
            success=True,
            events=events,
            metrics=metrics,
            errors=errors,
        )

    def verify_objectives(
        self, topology_data: dict, results: SimulationResult, rules: dict
    ) -> list[ObjectiveResult]:
        objectives = []

        # forward_zone
        if rules.get("forward_zone", False):
            fz_loaded = any(
                e.get("type") == "zone_loaded" and "in-addr.arpa" not in e.get("zone", "")
                for e in results.events
            )
            objectives.append(ObjectiveResult(
                objective_id="forward_zone",
                description="Forward DNS zone is configured",
                passed=fz_loaded,
                message="Forward zone loaded." if fz_loaded else "No forward zone configured.",
            ))

        # reverse_zone
        if rules.get("reverse_zone", False):
            rz_loaded = any(
                e.get("type") == "zone_loaded" and "in-addr.arpa" in e.get("zone", "")
                for e in results.events
            )
            objectives.append(ObjectiveResult(
                objective_id="reverse_zone",
                description="Reverse DNS zone (PTR) is configured",
                passed=rz_loaded,
                message="Reverse zone loaded." if rz_loaded else "No reverse zone configured.",
            ))

        # records_configured
        if "records_configured" in rules:
            expected_min = int(rules["records_configured"])
            actual = results.metrics.get("records_total", 0)
            passed = actual >= expected_min
            objectives.append(ObjectiveResult(
                objective_id="records_configured",
                description=f"At least {expected_min} DNS records configured",
                passed=passed,
                message=f"{actual} record(s) configured." if passed else f"Only {actual}/{expected_min} records.",
            ))

        if not objectives:
            server_up = any(e.get("type") == "dns_server_start" for e in results.events)
            objectives.append(ObjectiveResult(
                objective_id="dns_server_active",
                description="DNS server is active",
                passed=server_up,
                message="DNS server running." if server_up else "DNS server not started.",
            ))

        return objectives


dns_simulator = DnsSimulator()
