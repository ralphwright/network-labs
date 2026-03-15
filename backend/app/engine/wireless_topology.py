from app.engine.base import BaseSimulator, SimulationResult, ObjectiveResult


class WirelessTopologySimulator(BaseSimulator):
    def validate_topology(self, topology_data: dict) -> list[str]:
        errors = []
        devices = topology_data.get("devices", [])
        aps = [
            d for d in devices
            if d.get("type", "").lower() in {
                "access_point", "ap", "wireless_ap", "wap", "lightweight_ap"
            }
        ]
        if not aps:
            errors.append(
                "Wireless Topology simulation requires at least one access point "
                "(type: access_point, ap, wireless_ap, or wap)."
            )
        return errors

    def simulate(self, topology_data: dict, configuration: dict) -> SimulationResult:
        devices = topology_data.get("devices", [])
        connections = topology_data.get("connections", [])
        events = []
        errors = []

        ap_types = {"access_point", "ap", "wireless_ap", "wap", "lightweight_ap"}

        aps = [d for d in devices if d.get("type", "").lower() in ap_types]

        if not aps:
            errors.append("No access points found.")
            return SimulationResult(success=False, events=events, errors=errors)

        # Coverage radius by band (meters, typical indoor)
        COVERAGE_24GHZ = 30
        COVERAGE_5GHZ = 15
        COVERAGE_6GHZ = 10

        # Standard non-overlapping channels
        NON_OVERLAPPING_24 = {1, 6, 11}
        NON_OVERLAPPING_5 = {36, 40, 44, 48, 149, 153, 157, 161}

        channel_assignments: dict[str, int] = {}
        ap_configs: dict[str, dict] = {}

        for ap_idx, ap in enumerate(aps):
            ap_name = ap["name"]
            cfg = configuration.get(ap_name, {})
            ap_cfg = cfg.get("wireless", ap.get("wireless", {}))

            band = ap_cfg.get("band", "2.4GHz")
            channel = int(ap_cfg.get("channel", [1, 6, 11][ap_idx % 3]))
            standard = ap_cfg.get("standard", "802.11n")
            mesh_enabled = ap_cfg.get("mesh", ap.get("mesh", False))
            bss_color = ap_cfg.get("bss_color", (ap_idx % 63) + 1)

            if band == "5GHz":
                coverage = COVERAGE_5GHZ
                no_ovlp = NON_OVERLAPPING_5
            elif band == "6GHz":
                coverage = COVERAGE_6GHZ
                no_ovlp = set()
            else:
                coverage = COVERAGE_24GHZ
                no_ovlp = NON_OVERLAPPING_24

            channel_assignments[ap_name] = channel
            ap_configs[ap_name] = {
                "band": band,
                "channel": channel,
                "coverage": coverage,
                "standard": standard,
                "mesh_enabled": mesh_enabled,
                "bss_color": bss_color,
                "no_ovlp": no_ovlp,
            }

            events.append({
                "type": "ap_coverage",
                "message": (
                    f"AP {ap_name} coverage: {COVERAGE_24GHZ}m radius @2.4GHz, "
                    f"{COVERAGE_5GHZ}m @5GHz (band={band}, ch={channel})"
                ),
                "device": ap_name,
                "band": band,
                "channel": channel,
                "coverage_m": coverage,
            })

        # Channel plan analysis
        all_channels = sorted({c for c in channel_assignments.values()})
        non_ovlp_used = all(
            c in NON_OVERLAPPING_24 or c in NON_OVERLAPPING_5
            for c in all_channels
        )
        chan_display = ", ".join(
            f"AP{i+1}:ch{channel_assignments[ap['name']]}" for i, ap in enumerate(aps)
        )
        events.append({
            "type": "channel_plan",
            "message": (
                f"Channel plan: {chan_display} "
                f"({'non-overlapping' if non_ovlp_used else 'overlapping channels present'})"
            ),
            "channels": channel_assignments,
        })

        # Co-channel interference detection
        channel_groups: dict[int, list[str]] = {}
        for ap_name, ch in channel_assignments.items():
            channel_groups.setdefault(ch, []).append(ap_name)

        channel_conflicts = 0
        for ch, ap_list in channel_groups.items():
            if len(ap_list) > 1:
                conflict_aps = ", ".join(ap_list)
                events.append({
                    "type": "co_channel_interference",
                    "message": (
                        f"Co-channel interference: {conflict_aps} both on ch{ch} - CONFLICT"
                    ),
                    "channel": ch,
                    "aps": ap_list,
                })
                channel_conflicts += 1
            else:
                events.append({
                    "type": "channel_clear",
                    "message": (
                        f"Channel {ch}: only {ap_list[0]} assigned - no co-channel interference"
                    ),
                    "channel": ch,
                    "ap": ap_list[0],
                })

        # BSS Coloring (802.11ax)
        ax_aps = [a for a in aps if "ax" in ap_configs[a["name"]]["standard"].lower()]
        if ax_aps:
            for ap in ax_aps:
                color = ap_configs[ap["name"]]["bss_color"]
                events.append({
                    "type": "bss_color",
                    "message": (
                        f"BSS color {color} assigned to {ap['name']} (802.11ax OBSS/PD)"
                    ),
                    "device": ap["name"],
                    "bss_color": color,
                })

        # Mesh links (AP-to-AP backhaul)
        mesh_links = 0
        mesh_capable = [a for a in aps if ap_configs[a["name"]]["mesh_enabled"]]

        # Also detect mesh from connections between APs
        ap_names = {a["name"] for a in aps}
        for conn in connections:
            src = conn.get("source", conn.get("from", ""))
            dst = conn.get("target", conn.get("to", ""))
            if src in ap_names and dst in ap_names:
                rssi = conn.get("rssi", -55)
                link_quality = min(100, max(0, int((rssi + 90) * 2.5)))
                events.append({
                    "type": "mesh_link",
                    "message": (
                        f"Mesh link {src}<->{dst}: RSSI {rssi}dBm, "
                        f"link quality {link_quality}%"
                    ),
                    "ap1": src,
                    "ap2": dst,
                    "rssi": rssi,
                    "link_quality": link_quality,
                })
                mesh_links += 1

        if not mesh_links and len(mesh_capable) >= 2:
            for i in range(len(mesh_capable) - 1):
                src = mesh_capable[i]["name"]
                dst = mesh_capable[i + 1]["name"]
                rssi = -(55 + i * 5)
                link_quality = min(100, max(0, int((rssi + 90) * 2.5)))
                events.append({
                    "type": "mesh_link",
                    "message": (
                        f"Mesh link {src}<->{dst}: RSSI {rssi}dBm, "
                        f"link quality {link_quality}%"
                    ),
                    "ap1": src, "ap2": dst,
                    "rssi": rssi,
                    "link_quality": link_quality,
                })
                mesh_links += 1

        # Coverage overlap estimate
        total_ap_count = len(aps)
        if total_ap_count > 1:
            # Simple model: overlapping if adjacent APs share coverage zones
            overlap_pct = round(min(85.0, (total_ap_count - 1) * 15.0), 1)
        else:
            overlap_pct = 0.0

        # Dead zone detection (areas with no AP coverage)
        area_size = topology_data.get("area_sqm", 500)
        ap_coverage_area = sum(
            3.14159 * (ap_configs[a["name"]]["coverage"] ** 2) for a in aps
        )
        uncovered_pct = max(0.0, (1.0 - ap_coverage_area / area_size) * 100)
        dead_zones = int(uncovered_pct // 20)

        if dead_zones > 0:
            events.append({
                "type": "dead_zone",
                "message": (
                    f"Coverage gap detected: ~{uncovered_pct:.0f}% area uncovered "
                    f"({dead_zones} estimated dead zone(s))"
                ),
                "dead_zones": dead_zones,
            })
        else:
            events.append({
                "type": "full_coverage",
                "message": "Full coverage achieved — no significant dead zones detected",
            })

        # Site survey summary
        events.append({
            "type": "site_survey",
            "message": (
                f"Site survey complete: {total_ap_count} APs, "
                f"coverage overlap {overlap_pct}%, "
                f"{channel_conflicts} channel conflict(s), "
                f"{mesh_links} mesh link(s)"
            ),
        })

        metrics = {
            "coverage_overlap_pct": overlap_pct,
            "channel_conflicts": channel_conflicts,
            "mesh_links": mesh_links,
            "dead_zones": dead_zones,
            "access_points": total_ap_count,
        }

        return SimulationResult(
            success=len(errors) == 0 and total_ap_count > 0,
            events=events,
            metrics=metrics,
            errors=errors,
        )

    def verify_objectives(
        self, topology_data: dict, results: SimulationResult, rules: dict
    ) -> list[ObjectiveResult]:
        objectives = []

        if rules.get("full_coverage", False):
            dead_zones = results.metrics.get("dead_zones", 0)
            passed = dead_zones == 0
            objectives.append(ObjectiveResult(
                objective_id="full_coverage",
                description="Full wireless coverage with no dead zones",
                passed=passed,
                message=(
                    "Full coverage achieved." if passed
                    else f"{dead_zones} dead zone(s) detected."
                ),
            ))

        if rules.get("no_channel_conflicts", False):
            conflicts = results.metrics.get("channel_conflicts", 0)
            passed = conflicts == 0
            objectives.append(ObjectiveResult(
                objective_id="no_channel_conflicts",
                description="No co-channel interference between APs",
                passed=passed,
                message=(
                    "No co-channel interference." if passed
                    else f"{conflicts} co-channel conflict(s) detected."
                ),
            ))

        if rules.get("mesh_configured", False):
            mesh_links = results.metrics.get("mesh_links", 0)
            passed = mesh_links > 0
            objectives.append(ObjectiveResult(
                objective_id="mesh_configured",
                description="Mesh links configured between access points",
                passed=passed,
                message=(
                    f"{mesh_links} mesh link(s) configured." if passed
                    else "No mesh links configured."
                ),
            ))

        if not objectives:
            survey_done = any(e.get("type") == "site_survey" for e in results.events)
            objectives.append(ObjectiveResult(
                objective_id="topology_simulation",
                description="Wireless topology simulation completed",
                passed=survey_done,
                message=(
                    "Wireless topology analysis complete." if survey_done
                    else "Simulation did not complete."
                ),
            ))

        return objectives


wireless_topology_simulator = WirelessTopologySimulator()
