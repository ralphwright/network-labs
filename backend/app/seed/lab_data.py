from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lab import Lab

LAB_SEED_DATA = [
    {
        "slug": "vlans",
        "title": "VLANs (Virtual Local Area Networks)",
        "description": "Learn how to segment a network using VLANs to improve security and performance.",
        "category": "Switching",
        "difficulty": "beginner",
        "estimated_minutes": 30,
        "objectives": [
            "Create and name VLANs on a switch",
            "Assign access ports to VLANs",
            "Configure trunk ports to carry multiple VLANs",
            "Verify VLAN connectivity and isolation",
        ],
        "theory_content": (
            "A VLAN (Virtual Local Area Network) is a logical grouping of network devices "
            "regardless of their physical location. VLANs allow network administrators to "
            "partition a single switched network into multiple broadcast domains, improving "
            "security and performance. Devices on different VLANs cannot communicate directly "
            "without a Layer 3 device such as a router or Layer 3 switch."
        ),
        "instructions": [
            {"step": 1, "title": "Create VLANs", "description": "Use the vlan command to create VLAN 10 and VLAN 20 on the switch."},
            {"step": 2, "title": "Assign access ports", "description": "Configure switchport access mode and assign each port to its VLAN."},
            {"step": 3, "title": "Configure trunk port", "description": "Set up a trunk port between switches using switchport mode trunk."},
            {"step": 4, "title": "Verify connectivity", "description": "Ping between hosts in the same VLAN and confirm isolation between VLANs."},
        ],
        "initial_topology": {
            "devices": [
                {"type": "switch", "label": "SW1", "x": 100, "y": 200},
                {"type": "host", "label": "PC1", "x": 300, "y": 200},
                {"type": "host", "label": "PC2", "x": 500, "y": 200},
                {"type": "host", "label": "PC3", "x": 700, "y": 200},
            ],
            "connections": [
                {"source": "PC1", "target": "SW1", "source_interface": "eth0", "target_interface": "fa0/1"},
                {"source": "PC2", "target": "SW1", "source_interface": "eth0", "target_interface": "fa0/2"},
                {"source": "PC3", "target": "SW1", "source_interface": "eth0", "target_interface": "fa0/3"},
            ],
        },
        "verification_rules": {"required_vlans": [10, 20], "trunk_ports": ["fa0/24"]},
        "prerequisites": [],
        "sort_order": 1,
        "is_active": True,
    },
    {
        "slug": "stp",
        "title": "Spanning Tree Protocol (STP)",
        "description": "Understand how STP prevents Layer 2 loops and learn to configure and tune it.",
        "category": "Switching",
        "difficulty": "intermediate",
        "estimated_minutes": 45,
        "objectives": [
            "Understand how STP elects the root bridge",
            "Identify port roles: root, designated, and blocked",
            "Configure bridge priority to influence root bridge election",
            "Verify STP topology convergence",
        ],
        "theory_content": (
            "Spanning Tree Protocol (STP) is a Layer 2 protocol that prevents network loops "
            "in Ethernet networks with redundant paths. STP elects a root bridge and then "
            "computes a loop-free path by blocking redundant links. Rapid STP (RSTP) "
            "provides faster convergence. Understanding port roles and states is essential "
            "for designing resilient switched networks."
        ),
        "instructions": [
            {"step": 1, "title": "Observe default STP", "description": "Allow STP to converge and identify the root bridge using show spanning-tree."},
            {"step": 2, "title": "Change root bridge", "description": "Set bridge priority to make SW1 the root bridge."},
            {"step": 3, "title": "Identify blocked ports", "description": "Locate which ports are in blocking state to prevent loops."},
            {"step": 4, "title": "Test convergence", "description": "Disable the root bridge uplink and observe STP reconvergence."},
        ],
        "initial_topology": {
            "devices": [
                {"type": "switch", "label": "SW1", "x": 100, "y": 200},
                {"type": "switch", "label": "SW2", "x": 300, "y": 200},
                {"type": "switch", "label": "SW3", "x": 500, "y": 200},
            ],
            "connections": [
                {"source": "SW1", "target": "SW2", "source_interface": "fa0/1", "target_interface": "fa0/1"},
                {"source": "SW2", "target": "SW3", "source_interface": "fa0/2", "target_interface": "fa0/1"},
                {"source": "SW1", "target": "SW3", "source_interface": "fa0/2", "target_interface": "fa0/2"},
            ],
        },
        "verification_rules": {"root_bridge": "sw1", "check_no_loops": True},
        "prerequisites": ["vlans"],
        "sort_order": 2,
        "is_active": True,
    },
    {
        "slug": "ospf",
        "title": "OSPF (Open Shortest Path First)",
        "description": "Configure OSPF dynamic routing to enable scalable, automatic route discovery.",
        "category": "Routing",
        "difficulty": "intermediate",
        "estimated_minutes": 60,
        "objectives": [
            "Enable OSPF on routers and assign router IDs",
            "Advertise networks into OSPF",
            "Verify OSPF neighbor adjacencies",
            "Check that routes are learned via OSPF",
        ],
        "theory_content": (
            "OSPF (Open Shortest Path First) is a link-state routing protocol that uses "
            "Dijkstra's shortest path algorithm to build a complete map of the network. "
            "Routers exchange Link State Advertisements (LSAs) to build a Link State "
            "Database (LSDB). OSPF is widely used in enterprise networks and supports "
            "areas, authentication, and fast convergence."
        ),
        "instructions": [
            {"step": 1, "title": "Configure interfaces", "description": "Assign IP addresses to all router interfaces."},
            {"step": 2, "title": "Enable OSPF", "description": "Configure OSPF process and add network statements."},
            {"step": 3, "title": "Verify neighbors", "description": "Check OSPF neighbor adjacencies with show ip ospf neighbor."},
            {"step": 4, "title": "Check routing table", "description": "Verify routes marked with O in the routing table."},
        ],
        "initial_topology": {
            "devices": [
                {"type": "router", "label": "R1", "x": 100, "y": 200},
                {"type": "router", "label": "R2", "x": 300, "y": 200},
                {"type": "router", "label": "R3", "x": 500, "y": 200},
            ],
            "connections": [
                {"source": "R1", "target": "R2", "source_interface": "gi0/0", "target_interface": "gi0/0"},
                {"source": "R2", "target": "R3", "source_interface": "gi0/1", "target_interface": "gi0/0"},
            ],
        },
        "verification_rules": {"ospf_neighbors": True, "full_reachability": True},
        "prerequisites": [],
        "sort_order": 3,
        "is_active": True,
    },
    {
        "slug": "lacp",
        "title": "LACP (Link Aggregation Control Protocol)",
        "description": "Bundle multiple physical links into a single logical EtherChannel using LACP.",
        "category": "Switching",
        "difficulty": "intermediate",
        "estimated_minutes": 40,
        "objectives": [
            "Configure LACP EtherChannel between two switches",
            "Verify the port-channel is active",
            "Test link redundancy by disabling one member link",
            "Observe load balancing across member links",
        ],
        "theory_content": (
            "LACP (Link Aggregation Control Protocol) is an IEEE 802.3ad standard that "
            "allows multiple physical Ethernet links to be combined into a single logical "
            "link called an EtherChannel or port-channel. This increases bandwidth and "
            "provides redundancy. LACP negotiates the formation of the bundle automatically "
            "between two connected switches."
        ),
        "instructions": [
            {"step": 1, "title": "Configure port-channel", "description": "Create port-channel interface and assign member ports."},
            {"step": 2, "title": "Enable LACP", "description": "Set channel-group mode to active on both switches."},
            {"step": 3, "title": "Verify port-channel", "description": "Check port-channel status with show etherchannel summary."},
            {"step": 4, "title": "Test redundancy", "description": "Shut down one member link and verify the EtherChannel stays up."},
        ],
        "initial_topology": {
            "devices": [
                {"type": "switch", "label": "SW1", "x": 100, "y": 200},
                {"type": "switch", "label": "SW2", "x": 300, "y": 200},
            ],
            "connections": [
                {"source": "SW1", "target": "SW2", "source_interface": "fa0/1", "target_interface": "fa0/1"},
                {"source": "SW1", "target": "SW2", "source_interface": "fa0/2", "target_interface": "fa0/2"},
            ],
        },
        "verification_rules": {"port_channel_active": True, "min_member_links": 2},
        "prerequisites": ["vlans"],
        "sort_order": 4,
        "is_active": True,
    },
    {
        "slug": "dhcp",
        "title": "DHCP (Dynamic Host Configuration Protocol)",
        "description": "Configure a DHCP server to automatically assign IP addresses to hosts.",
        "category": "Routing",
        "difficulty": "beginner",
        "estimated_minutes": 30,
        "objectives": [
            "Configure a DHCP pool on a router",
            "Exclude static IP addresses from the pool",
            "Verify clients receive IP addresses via DHCP",
            "Configure DHCP relay for remote subnets",
        ],
        "theory_content": (
            "DHCP (Dynamic Host Configuration Protocol) automates the assignment of IP "
            "addresses, subnet masks, default gateways, and DNS servers to network clients. "
            "A DHCP server maintains a pool of available IP addresses and leases them to "
            "clients on request. For hosts on different subnets, a DHCP relay agent "
            "forwards requests to a centralized DHCP server."
        ),
        "instructions": [
            {"step": 1, "title": "Create DHCP pool", "description": "Define the network, default gateway, and DNS server in the DHCP pool."},
            {"step": 2, "title": "Exclude static IPs", "description": "Use ip dhcp excluded-address to reserve static addresses."},
            {"step": 3, "title": "Verify client lease", "description": "On a client, run ipconfig or dhclient to obtain an address."},
            {"step": 4, "title": "Check DHCP bindings", "description": "Use show ip dhcp binding to see allocated leases."},
        ],
        "initial_topology": {
            "devices": [
                {"type": "router", "label": "R1", "x": 100, "y": 200},
                {"type": "host", "label": "PC1", "x": 300, "y": 200},
                {"type": "host", "label": "PC2", "x": 500, "y": 200},
            ],
            "connections": [
                {"source": "R1", "target": "PC1", "source_interface": "gi0/0", "target_interface": "eth0"},
                {"source": "R1", "target": "PC2", "source_interface": "gi0/0", "target_interface": "eth0"},
            ],
        },
        "verification_rules": {"clients_get_ip": True, "correct_pool": "192.168.1.0/24"},
        "prerequisites": [],
        "sort_order": 5,
        "is_active": True,
    },
    {
        "slug": "dns",
        "title": "DNS (Domain Name System)",
        "description": "Configure DNS to resolve hostnames to IP addresses within your network.",
        "category": "Routing",
        "difficulty": "beginner",
        "estimated_minutes": 30,
        "objectives": [
            "Configure a DNS server with A records",
            "Set up DNS client on hosts",
            "Verify hostname resolution",
            "Understand DNS query process",
        ],
        "theory_content": (
            "DNS (Domain Name System) translates human-readable domain names into IP "
            "addresses. It operates in a hierarchical, distributed manner with root servers, "
            "top-level domain servers, and authoritative name servers. Understanding DNS "
            "record types (A, AAAA, CNAME, MX, PTR) and the resolution process is "
            "fundamental to network administration."
        ),
        "instructions": [
            {"step": 1, "title": "Configure DNS server", "description": "Set up the DNS server with A records for local hosts."},
            {"step": 2, "title": "Configure DNS client", "description": "Point hosts to the DNS server IP address."},
            {"step": 3, "title": "Test resolution", "description": "Ping hosts by name to verify DNS resolution works."},
            {"step": 4, "title": "Inspect DNS queries", "description": "Use debug ip dns or packet capture to see DNS traffic."},
        ],
        "initial_topology": {
            "devices": [
                {"type": "server", "label": "DNS1", "x": 100, "y": 200},
                {"type": "host", "label": "PC1", "x": 300, "y": 200},
                {"type": "switch", "label": "SW1", "x": 500, "y": 200},
            ],
            "connections": [
                {"source": "DNS1", "target": "SW1", "source_interface": "eth0", "target_interface": "fa0/1"},
                {"source": "PC1", "target": "SW1", "source_interface": "eth0", "target_interface": "fa0/2"},
            ],
        },
        "verification_rules": {"dns_resolution": True, "resolve_local_names": True},
        "prerequisites": ["dhcp"],
        "sort_order": 6,
        "is_active": True,
    },
    {
        "slug": "bgp",
        "title": "BGP (Border Gateway Protocol)",
        "description": "Configure BGP to exchange routing information between autonomous systems.",
        "category": "Routing",
        "difficulty": "advanced",
        "estimated_minutes": 90,
        "objectives": [
            "Configure eBGP peering between two ASes",
            "Advertise networks via BGP",
            "Verify BGP neighbor state is Established",
            "Understand BGP path selection attributes",
        ],
        "theory_content": (
            "BGP (Border Gateway Protocol) is the routing protocol that powers the internet. "
            "It is a path-vector protocol used to exchange routing information between "
            "autonomous systems (ASes). BGP uses TCP port 179 and employs a rich set of "
            "attributes (AS-path, MED, local preference) to make routing decisions. "
            "Understanding BGP is essential for internet service providers and large enterprises."
        ),
        "instructions": [
            {"step": 1, "title": "Configure eBGP", "description": "Set up BGP neighbor relationships between routers in different ASes."},
            {"step": 2, "title": "Advertise networks", "description": "Use network statements or redistribution to advertise prefixes."},
            {"step": 3, "title": "Verify adjacency", "description": "Check BGP neighbor state with show ip bgp summary."},
            {"step": 4, "title": "Inspect BGP table", "description": "View the BGP routing table with show ip bgp."},
        ],
        "initial_topology": {
            "devices": [
                {"type": "router", "label": "R1", "x": 100, "y": 200, "asn": 65001},
                {"type": "router", "label": "R2", "x": 300, "y": 200, "asn": 65002},
            ],
            "connections": [
                {"source": "R1", "target": "R2", "source_interface": "gi0/0", "target_interface": "gi0/0"},
            ],
        },
        "verification_rules": {"bgp_established": True, "routes_exchanged": True},
        "prerequisites": ["ospf"],
        "sort_order": 7,
        "is_active": True,
    },
    {
        "slug": "mpls",
        "title": "MPLS (Multiprotocol Label Switching)",
        "description": "Implement MPLS to improve packet forwarding efficiency across a provider network.",
        "category": "WAN",
        "difficulty": "advanced",
        "estimated_minutes": 90,
        "objectives": [
            "Enable MPLS on provider router interfaces",
            "Configure LDP for label distribution",
            "Verify label bindings with show mpls ldp bindings",
            "Trace an MPLS-switched path",
        ],
        "theory_content": (
            "MPLS (Multiprotocol Label Switching) is a high-performance routing technique "
            "that directs data from one node to the next based on short path labels rather "
            "than long network addresses. Labels are added at the ingress router and removed "
            "at the egress router. MPLS enables VPNs, traffic engineering, and QoS in "
            "service provider networks."
        ),
        "instructions": [
            {"step": 1, "title": "Enable MPLS", "description": "Enable MPLS IP forwarding on all core router interfaces."},
            {"step": 2, "title": "Configure LDP", "description": "LDP will start automatically; verify with show mpls ldp neighbor."},
            {"step": 3, "title": "Verify labels", "description": "Check label bindings with show mpls ldp bindings."},
            {"step": 4, "title": "Trace MPLS path", "description": "Use mpls traceroute to follow the label-switched path."},
        ],
        "initial_topology": {
            "devices": [
                {"type": "router", "label": "PE1", "x": 100, "y": 200},
                {"type": "router", "label": "P1", "x": 300, "y": 200},
                {"type": "router", "label": "PE2", "x": 500, "y": 200},
            ],
            "connections": [
                {"source": "PE1", "target": "P1", "source_interface": "gi0/0", "target_interface": "gi0/0"},
                {"source": "P1", "target": "PE2", "source_interface": "gi0/1", "target_interface": "gi0/0"},
            ],
        },
        "verification_rules": {"mpls_enabled": True, "ldp_neighbors": True},
        "prerequisites": ["ospf", "bgp"],
        "sort_order": 8,
        "is_active": True,
    },
    {
        "slug": "tunneling",
        "title": "IP Tunneling",
        "description": "Create GRE and IP-in-IP tunnels to encapsulate traffic across networks.",
        "category": "WAN",
        "difficulty": "intermediate",
        "estimated_minutes": 45,
        "objectives": [
            "Configure a GRE tunnel between two routers",
            "Assign IP addresses to tunnel interfaces",
            "Route traffic over the tunnel",
            "Verify tunnel operation with ping and traceroute",
        ],
        "theory_content": (
            "IP tunneling encapsulates one network protocol within another, allowing "
            "traffic to traverse networks that would otherwise not support it. Common "
            "tunnel types include GRE (Generic Routing Encapsulation), IP-in-IP, and "
            "IPSec tunnels. Tunnels are used for VPNs, connecting isolated networks, "
            "and supporting IPv6 over IPv4 networks."
        ),
        "instructions": [
            {"step": 1, "title": "Create tunnel interface", "description": "Define the tunnel interface with source and destination addresses."},
            {"step": 2, "title": "Assign tunnel IP", "description": "Configure an IP address on the tunnel interface."},
            {"step": 3, "title": "Add static route", "description": "Add a route pointing remote networks via the tunnel interface."},
            {"step": 4, "title": "Verify tunnel", "description": "Ping the remote tunnel endpoint and check show interface tunnel."},
        ],
        "initial_topology": {
            "devices": [
                {"type": "router", "label": "R1", "x": 100, "y": 200},
                {"type": "router", "label": "R2", "x": 300, "y": 200},
                {"type": "cloud", "label": "Internet", "x": 500, "y": 200},
            ],
            "connections": [
                {"source": "R1", "target": "Internet", "source_interface": "gi0/0", "target_interface": "port1"},
                {"source": "R2", "target": "Internet", "source_interface": "gi0/0", "target_interface": "port2"},
            ],
        },
        "verification_rules": {"tunnel_up": True, "end_to_end_ping": True},
        "prerequisites": ["ospf"],
        "sort_order": 9,
        "is_active": True,
    },
    {
        "slug": "gre",
        "title": "GRE (Generic Routing Encapsulation)",
        "description": "Configure GRE tunnels to create virtual point-to-point links between routers.",
        "category": "WAN",
        "difficulty": "intermediate",
        "estimated_minutes": 45,
        "objectives": [
            "Configure a GRE tunnel interface",
            "Set tunnel source and destination",
            "Run a routing protocol over the GRE tunnel",
            "Verify GRE encapsulation with packet capture",
        ],
        "theory_content": (
            "GRE (Generic Routing Encapsulation) is a tunneling protocol that can "
            "encapsulate a wide variety of network-layer protocols inside virtual "
            "point-to-point links. GRE adds a 24-byte overhead (4-byte GRE header + "
            "20-byte IP header) to each packet. It is commonly used to carry multicast "
            "traffic or routing protocol updates across the internet."
        ),
        "instructions": [
            {"step": 1, "title": "Create GRE tunnel", "description": "Configure the tunnel interface with mode gre ip."},
            {"step": 2, "title": "Set source/destination", "description": "Specify the physical source and destination IP addresses."},
            {"step": 3, "title": "Configure routing", "description": "Enable OSPF on the tunnel interface to exchange routes."},
            {"step": 4, "title": "Verify encapsulation", "description": "Capture packets to observe GRE encapsulation."},
        ],
        "initial_topology": {
            "devices": [
                {"type": "router", "label": "R1", "x": 100, "y": 200},
                {"type": "router", "label": "R2", "x": 300, "y": 200},
            ],
            "connections": [
                {"source": "R1", "target": "R2", "source_interface": "gi0/0", "target_interface": "gi0/0"},
            ],
        },
        "verification_rules": {"gre_tunnel_up": True, "routing_over_tunnel": True},
        "prerequisites": ["tunneling"],
        "sort_order": 10,
        "is_active": True,
    },
    {
        "slug": "autonomous-systems",
        "title": "Autonomous Systems",
        "description": "Explore autonomous system concepts and inter-AS routing with BGP.",
        "category": "Routing",
        "difficulty": "advanced",
        "estimated_minutes": 75,
        "objectives": [
            "Understand autonomous system numbering",
            "Configure multiple ASes with BGP",
            "Apply BGP policies between ASes",
            "Verify inter-AS reachability",
        ],
        "theory_content": (
            "An Autonomous System (AS) is a collection of IP networks and routers under "
            "the control of a single organization with a unified routing policy. Each AS "
            "is assigned a unique AS number (ASN) by IANA. BGP is the protocol used to "
            "exchange routing information between ASes. Understanding AS topology and "
            "BGP policies is crucial for internet routing."
        ),
        "instructions": [
            {"step": 1, "title": "Design AS topology", "description": "Plan ASN assignments and peering relationships."},
            {"step": 2, "title": "Configure BGP peerings", "description": "Set up eBGP sessions between AS border routers."},
            {"step": 3, "title": "Apply routing policies", "description": "Use route maps and prefix lists to control route advertisement."},
            {"step": 4, "title": "Verify reachability", "description": "Test connectivity between hosts in different ASes."},
        ],
        "initial_topology": {
            "devices": [
                {"type": "router", "label": "R1", "x": 100, "y": 200, "asn": 65001},
                {"type": "router", "label": "R2", "x": 300, "y": 200, "asn": 65002},
                {"type": "router", "label": "R3", "x": 500, "y": 200, "asn": 65003},
            ],
            "connections": [
                {"source": "R1", "target": "R2", "source_interface": "gi0/0", "target_interface": "gi0/0"},
                {"source": "R2", "target": "R3", "source_interface": "gi0/1", "target_interface": "gi0/0"},
            ],
        },
        "verification_rules": {"inter_as_reachability": True, "policy_applied": True},
        "prerequisites": ["bgp"],
        "sort_order": 11,
        "is_active": True,
    },
    {
        "slug": "ipv6",
        "title": "IPv6 Fundamentals",
        "description": "Configure and verify IPv6 addressing, routing, and neighbor discovery.",
        "category": "Routing",
        "difficulty": "intermediate",
        "estimated_minutes": 60,
        "objectives": [
            "Configure IPv6 addresses on interfaces",
            "Enable IPv6 unicast routing",
            "Configure OSPFv3 for IPv6",
            "Verify IPv6 connectivity and neighbor discovery",
        ],
        "theory_content": (
            "IPv6 is the next generation of the Internet Protocol, providing a vastly "
            "larger address space (128-bit addresses) compared to IPv4. IPv6 introduces "
            "new features including stateless address autoconfiguration (SLAAC), mandatory "
            "IPSec support, and improved multicast capabilities. Neighbor Discovery Protocol "
            "(NDP) replaces ARP for address resolution."
        ),
        "instructions": [
            {"step": 1, "title": "Configure IPv6 addresses", "description": "Assign IPv6 global unicast addresses to router interfaces."},
            {"step": 2, "title": "Enable routing", "description": "Enable IPv6 unicast routing with ipv6 unicast-routing."},
            {"step": 3, "title": "Configure OSPFv3", "description": "Configure OSPFv3 to distribute IPv6 routes."},
            {"step": 4, "title": "Verify connectivity", "description": "Ping IPv6 addresses and verify the routing table."},
        ],
        "initial_topology": {
            "devices": [
                {"type": "router", "label": "R1", "x": 100, "y": 200},
                {"type": "router", "label": "R2", "x": 300, "y": 200},
                {"type": "host", "label": "PC1", "x": 500, "y": 200},
            ],
            "connections": [
                {"source": "R1", "target": "R2", "source_interface": "gi0/0", "target_interface": "gi0/0"},
                {"source": "R1", "target": "PC1", "source_interface": "gi0/1", "target_interface": "eth0"},
            ],
        },
        "verification_rules": {"ipv6_routing": True, "end_to_end_ipv6": True},
        "prerequisites": ["ospf"],
        "sort_order": 12,
        "is_active": True,
    },
    {
        "slug": "remote-access",
        "title": "Remote Access VPN",
        "description": "Set up remote access VPN to securely connect remote users to the corporate network.",
        "category": "Security",
        "difficulty": "intermediate",
        "estimated_minutes": 60,
        "objectives": [
            "Configure a VPN gateway",
            "Set up user authentication",
            "Connect a remote client to the VPN",
            "Verify encrypted traffic and access to internal resources",
        ],
        "theory_content": (
            "Remote access VPNs allow individual users to securely connect to a private "
            "network over the internet. Common technologies include IPSec with IKEv2, "
            "SSL/TLS VPN, and OpenVPN. The VPN client establishes an encrypted tunnel "
            "to the VPN gateway, and traffic is encapsulated and encrypted before "
            "traversing the public internet."
        ),
        "instructions": [
            {"step": 1, "title": "Configure VPN gateway", "description": "Set up IKEv2 or SSL VPN on the gateway router/firewall."},
            {"step": 2, "title": "Create user accounts", "description": "Add user credentials for VPN authentication."},
            {"step": 3, "title": "Connect client", "description": "Use a VPN client to establish a connection to the gateway."},
            {"step": 4, "title": "Verify access", "description": "Ping internal hosts and verify the traffic is encrypted."},
        ],
        "initial_topology": {
            "devices": [
                {"type": "firewall", "label": "FW1", "x": 100, "y": 200},
                {"type": "host", "label": "Remote Client", "x": 300, "y": 200},
                {"type": "server", "label": "Internal Server", "x": 500, "y": 200},
            ],
            "connections": [
                {"source": "Remote Client", "target": "FW1", "source_interface": "eth0", "target_interface": "outside"},
                {"source": "FW1", "target": "Internal Server", "source_interface": "inside", "target_interface": "eth0"},
            ],
        },
        "verification_rules": {"vpn_connected": True, "internal_access": True},
        "prerequisites": ["firewalls"],
        "sort_order": 13,
        "is_active": True,
    },
    {
        "slug": "ssh",
        "title": "SSH (Secure Shell)",
        "description": "Configure SSH for secure remote management of network devices.",
        "category": "Security",
        "difficulty": "beginner",
        "estimated_minutes": 25,
        "objectives": [
            "Generate RSA keys on a router or switch",
            "Configure SSH version 2",
            "Create a local user for SSH access",
            "Verify SSH connectivity from a remote host",
        ],
        "theory_content": (
            "SSH (Secure Shell) provides encrypted communication between a client and a "
            "server, replacing insecure protocols like Telnet and rsh. SSH uses public-key "
            "cryptography for authentication and encrypts all traffic including passwords. "
            "Configuring SSH on network devices is a fundamental security best practice "
            "for all managed network infrastructure."
        ),
        "instructions": [
            {"step": 1, "title": "Set hostname and domain", "description": "Configure hostname and ip domain-name, required for key generation."},
            {"step": 2, "title": "Generate RSA keys", "description": "Use crypto key generate rsa modulus 2048."},
            {"step": 3, "title": "Configure SSH", "description": "Set ip ssh version 2 and configure VTY lines to use SSH."},
            {"step": 4, "title": "Create local user", "description": "Add a username and password with privilege 15."},
            {"step": 5, "title": "Test SSH", "description": "SSH from a client to the device and verify secure login."},
        ],
        "initial_topology": {
            "devices": [
                {"type": "router", "label": "R1", "x": 100, "y": 200},
                {"type": "host", "label": "Admin PC", "x": 300, "y": 200},
            ],
            "connections": [
                {"source": "Admin PC", "target": "R1", "source_interface": "eth0", "target_interface": "gi0/0"},
            ],
        },
        "verification_rules": {"ssh_enabled": True, "ssh_version": 2, "telnet_disabled": True},
        "prerequisites": [],
        "sort_order": 14,
        "is_active": True,
    },
    {
        "slug": "acls",
        "title": "ACLs (Access Control Lists)",
        "description": "Use ACLs to filter network traffic and control access to resources.",
        "category": "Security",
        "difficulty": "intermediate",
        "estimated_minutes": 50,
        "objectives": [
            "Create standard and extended ACLs",
            "Apply ACLs to router interfaces",
            "Verify traffic is permitted or denied as expected",
            "Understand ACL processing order and implicit deny",
        ],
        "theory_content": (
            "Access Control Lists (ACLs) are ordered lists of permit and deny statements "
            "used to filter network traffic. Standard ACLs filter based only on source IP "
            "address, while extended ACLs can filter based on source/destination IP, "
            "protocol, and port numbers. ACLs are applied to router interfaces in the "
            "inbound or outbound direction and are processed top-down with an implicit "
            "deny all at the end."
        ),
        "instructions": [
            {"step": 1, "title": "Create extended ACL", "description": "Define an ACL with permit and deny statements for specific traffic."},
            {"step": 2, "title": "Apply to interface", "description": "Apply the ACL inbound or outbound on the appropriate interface."},
            {"step": 3, "title": "Test permit rules", "description": "Generate permitted traffic and verify it passes."},
            {"step": 4, "title": "Test deny rules", "description": "Generate denied traffic and verify it is blocked."},
        ],
        "initial_topology": {
            "devices": [
                {"type": "router", "label": "R1", "x": 100, "y": 200},
                {"type": "host", "label": "PC1", "x": 300, "y": 200},
                {"type": "server", "label": "Web Server", "x": 500, "y": 200},
            ],
            "connections": [
                {"source": "PC1", "target": "R1", "source_interface": "eth0", "target_interface": "gi0/0"},
                {"source": "R1", "target": "Web Server", "source_interface": "gi0/1", "target_interface": "eth0"},
            ],
        },
        "verification_rules": {"acl_applied": True, "traffic_filtered": True},
        "prerequisites": ["ospf"],
        "sort_order": 15,
        "is_active": True,
    },
    {
        "slug": "nat",
        "title": "NAT (Network Address Translation)",
        "description": "Configure NAT to allow private IP addresses to communicate with the internet.",
        "category": "Routing",
        "difficulty": "intermediate",
        "estimated_minutes": 45,
        "objectives": [
            "Configure static NAT for a server",
            "Configure dynamic NAT for internal hosts",
            "Define inside and outside NAT interfaces",
            "Verify translations with show ip nat translations",
        ],
        "theory_content": (
            "NAT (Network Address Translation) allows multiple devices on a private network "
            "to share a single public IP address. Static NAT maps a private IP to a fixed "
            "public IP, commonly used for servers. Dynamic NAT uses a pool of public IPs. "
            "PAT (Port Address Translation) is the most common form, mapping multiple "
            "private IPs to a single public IP using port numbers to distinguish sessions."
        ),
        "instructions": [
            {"step": 1, "title": "Define NAT interfaces", "description": "Mark the LAN interface as ip nat inside and WAN as ip nat outside."},
            {"step": 2, "title": "Configure static NAT", "description": "Create a static translation for the internal server."},
            {"step": 3, "title": "Configure dynamic NAT", "description": "Create an ACL and NAT pool for dynamic translation."},
            {"step": 4, "title": "Verify translations", "description": "Check active translations with show ip nat translations."},
        ],
        "initial_topology": {
            "devices": [
                {"type": "router", "label": "R1", "x": 100, "y": 200},
                {"type": "host", "label": "PC1", "x": 300, "y": 200},
                {"type": "cloud", "label": "Internet", "x": 500, "y": 200},
            ],
            "connections": [
                {"source": "PC1", "target": "R1", "source_interface": "eth0", "target_interface": "gi0/0"},
                {"source": "R1", "target": "Internet", "source_interface": "gi0/1", "target_interface": "port1"},
            ],
        },
        "verification_rules": {"nat_translations_active": True, "internet_reachability": True},
        "prerequisites": ["acls"],
        "sort_order": 16,
        "is_active": True,
    },
    {
        "slug": "pat",
        "title": "PAT (Port Address Translation)",
        "description": "Configure PAT (NAT overload) to allow many hosts to share one public IP address.",
        "category": "Routing",
        "difficulty": "intermediate",
        "estimated_minutes": 40,
        "objectives": [
            "Configure PAT using the outside interface address",
            "Create an ACL defining inside hosts",
            "Enable NAT overload",
            "Verify multiple hosts share the single public IP",
        ],
        "theory_content": (
            "PAT (Port Address Translation), also known as NAT Overload, is the most "
            "widely deployed form of NAT. It maps multiple private IP addresses to a "
            "single public IP address using unique source port numbers to distinguish "
            "sessions. PAT is the technology that allows home networks and offices to "
            "connect many devices through a single internet IP address."
        ),
        "instructions": [
            {"step": 1, "title": "Configure ACL", "description": "Create an ACL matching all inside hosts."},
            {"step": 2, "title": "Enable PAT", "description": "Apply ip nat inside source list with overload keyword."},
            {"step": 3, "title": "Define interfaces", "description": "Mark inside and outside interfaces."},
            {"step": 4, "title": "Verify overload", "description": "Multiple hosts connect to the internet; verify with show ip nat translations."},
        ],
        "initial_topology": {
            "devices": [
                {"type": "router", "label": "R1", "x": 100, "y": 200},
                {"type": "host", "label": "PC1", "x": 300, "y": 200},
                {"type": "host", "label": "PC2", "x": 500, "y": 200},
                {"type": "cloud", "label": "Internet", "x": 700, "y": 200},
            ],
            "connections": [
                {"source": "PC1", "target": "R1", "source_interface": "eth0", "target_interface": "gi0/0"},
                {"source": "PC2", "target": "R1", "source_interface": "eth0", "target_interface": "gi0/0"},
                {"source": "R1", "target": "Internet", "source_interface": "gi0/1", "target_interface": "port1"},
            ],
        },
        "verification_rules": {"pat_active": True, "multiple_sessions": True},
        "prerequisites": ["nat"],
        "sort_order": 17,
        "is_active": True,
    },
    {
        "slug": "wireless-ap",
        "title": "Wireless Access Point Configuration",
        "description": "Configure a standalone wireless access point for client connectivity.",
        "category": "Wireless",
        "difficulty": "beginner",
        "estimated_minutes": 30,
        "objectives": [
            "Configure SSID and security settings on an AP",
            "Set the wireless channel and transmit power",
            "Connect a wireless client to the AP",
            "Verify wireless connectivity",
        ],
        "theory_content": (
            "A wireless access point (AP) extends a wired network to wireless clients "
            "using the IEEE 802.11 standard. Key configuration elements include the SSID "
            "(network name), security mode (WPA2/WPA3), channel selection, and transmit "
            "power. Standalone APs operate independently, while managed APs are controlled "
            "by a wireless LAN controller (WLC)."
        ),
        "instructions": [
            {"step": 1, "title": "Configure SSID", "description": "Set the network name (SSID) that clients will see."},
            {"step": 2, "title": "Set security mode", "description": "Configure WPA2-PSK with a strong passphrase."},
            {"step": 3, "title": "Select channel", "description": "Choose a non-overlapping channel (1, 6, or 11 for 2.4 GHz)."},
            {"step": 4, "title": "Connect client", "description": "Associate a wireless client and verify it gets an IP address."},
        ],
        "initial_topology": {
            "devices": [
                {"type": "wireless-ap", "label": "AP1", "x": 100, "y": 200},
                {"type": "wireless-host", "label": "Laptop1", "x": 300, "y": 200},
                {"type": "switch", "label": "SW1", "x": 500, "y": 200},
            ],
            "connections": [
                {"source": "AP1", "target": "SW1", "source_interface": "eth0", "target_interface": "fa0/1"},
                {"source": "Laptop1", "target": "AP1", "source_interface": "wlan0", "target_interface": "radio0", "wireless": True},
            ],
        },
        "verification_rules": {"ssid_broadcast": True, "client_associated": True},
        "prerequisites": ["vlans"],
        "sort_order": 18,
        "is_active": True,
    },
    {
        "slug": "wireless-controller",
        "title": "Wireless LAN Controller (WLC)",
        "description": "Deploy and configure a centralized WLC to manage multiple access points.",
        "category": "Wireless",
        "difficulty": "advanced",
        "estimated_minutes": 75,
        "objectives": [
            "Configure a WLC with management interface",
            "Join APs to the WLC using CAPWAP",
            "Create a WLAN on the WLC",
            "Verify centralized AP management and client roaming",
        ],
        "theory_content": (
            "A Wireless LAN Controller (WLC) centralizes the management of multiple access "
            "points using the CAPWAP (Control and Provisioning of Wireless Access Points) "
            "protocol. APs in controller mode (lightweight APs) handle only the radio "
            "functions while the WLC manages configuration, security, and roaming. "
            "This architecture simplifies large-scale wireless deployments."
        ),
        "instructions": [
            {"step": 1, "title": "Configure WLC interfaces", "description": "Set up the management and AP-manager interfaces on the WLC."},
            {"step": 2, "title": "Join APs", "description": "APs discover the WLC via DHCP option 43 or DNS; verify they join."},
            {"step": 3, "title": "Create WLAN", "description": "Define a new WLAN with SSID, VLAN, and security settings."},
            {"step": 4, "title": "Verify roaming", "description": "Move a client between APs and verify seamless roaming."},
        ],
        "initial_topology": {
            "devices": [
                {"type": "wireless-controller", "label": "WLC1", "x": 100, "y": 200},
                {"type": "wireless-ap", "label": "AP1", "x": 300, "y": 200},
                {"type": "wireless-ap", "label": "AP2", "x": 500, "y": 200},
                {"type": "switch", "label": "SW1", "x": 700, "y": 200},
            ],
            "connections": [
                {"source": "WLC1", "target": "SW1", "source_interface": "gi0/0", "target_interface": "fa0/24"},
                {"source": "AP1", "target": "SW1", "source_interface": "eth0", "target_interface": "fa0/1"},
                {"source": "AP2", "target": "SW1", "source_interface": "eth0", "target_interface": "fa0/2"},
            ],
        },
        "verification_rules": {"aps_joined": True, "wlan_active": True},
        "prerequisites": ["wireless-ap", "vlans"],
        "sort_order": 19,
        "is_active": True,
    },
    {
        "slug": "wireless-security",
        "title": "Wireless Security",
        "description": "Implement robust wireless security using WPA3, 802.1X, and rogue AP detection.",
        "category": "Wireless",
        "difficulty": "advanced",
        "estimated_minutes": 60,
        "objectives": [
            "Configure WPA3 enterprise with 802.1X",
            "Set up a RADIUS server for authentication",
            "Enable rogue AP detection",
            "Verify only authenticated clients can connect",
        ],
        "theory_content": (
            "Wireless security is critical because the wireless medium is inherently "
            "broadcast and accessible to anyone within range. WPA3 is the current "
            "standard, offering improved protection against brute-force attacks. "
            "Enterprise wireless uses 802.1X with a RADIUS server for individual user "
            "authentication. Additional protections include rogue AP detection, "
            "management frame protection (MFP), and client isolation."
        ),
        "instructions": [
            {"step": 1, "title": "Configure RADIUS server", "description": "Set up a RADIUS server with user credentials."},
            {"step": 2, "title": "Configure 802.1X", "description": "Enable WPA3-Enterprise with RADIUS authentication on the WLAN."},
            {"step": 3, "title": "Enable rogue detection", "description": "Turn on rogue AP detection and containment."},
            {"step": 4, "title": "Test authentication", "description": "Attempt to connect with valid and invalid credentials."},
        ],
        "initial_topology": {
            "devices": [
                {"type": "wireless-controller", "label": "WLC1", "x": 100, "y": 200},
                {"type": "wireless-ap", "label": "AP1", "x": 300, "y": 200},
                {"type": "server", "label": "RADIUS", "x": 500, "y": 200},
            ],
            "connections": [
                {"source": "WLC1", "target": "RADIUS", "source_interface": "gi0/0", "target_interface": "eth0"},
                {"source": "AP1", "target": "WLC1", "source_interface": "eth0", "target_interface": "gi0/1"},
            ],
        },
        "verification_rules": {"wpa3_enabled": True, "radius_auth": True},
        "prerequisites": ["wireless-controller", "acls"],
        "sort_order": 20,
        "is_active": True,
    },
    {
        "slug": "wireless-topology",
        "title": "Wireless Network Topology Design",
        "description": "Design and implement a complete enterprise wireless network topology.",
        "category": "Wireless",
        "difficulty": "advanced",
        "estimated_minutes": 90,
        "objectives": [
            "Design wireless coverage for a building floor plan",
            "Configure roaming between multiple APs",
            "Implement wireless VLANs and traffic segmentation",
            "Optimize channel assignment to minimize interference",
        ],
        "theory_content": (
            "Designing an enterprise wireless topology requires careful planning of AP "
            "placement, channel assignment, and capacity planning. Overlapping cells "
            "provide roaming capability. Channel reuse patterns (1-6-11 for 2.4 GHz) "
            "minimize co-channel interference. Wireless VLANs allow different SSIDs to "
            "map to different network segments, providing traffic segmentation."
        ),
        "instructions": [
            {"step": 1, "title": "Plan AP placement", "description": "Position APs for optimal coverage with appropriate cell overlap."},
            {"step": 2, "title": "Assign channels", "description": "Assign non-overlapping channels to adjacent APs."},
            {"step": 3, "title": "Configure wireless VLANs", "description": "Map SSIDs to VLANs for traffic segmentation."},
            {"step": 4, "title": "Test roaming", "description": "Verify seamless client roaming between APs."},
        ],
        "initial_topology": {
            "devices": [
                {"type": "wireless-controller", "label": "WLC1", "x": 100, "y": 200},
                {"type": "wireless-ap", "label": "AP1", "x": 300, "y": 200, "channel": 1},
                {"type": "wireless-ap", "label": "AP2", "x": 500, "y": 200, "channel": 6},
                {"type": "wireless-ap", "label": "AP3", "x": 700, "y": 200, "channel": 11},
            ],
            "connections": [
                {"source": "WLC1", "target": "AP1", "source_interface": "gi0/0", "target_interface": "eth0"},
                {"source": "WLC1", "target": "AP2", "source_interface": "gi0/1", "target_interface": "eth0"},
                {"source": "WLC1", "target": "AP3", "source_interface": "gi0/2", "target_interface": "eth0"},
            ],
        },
        "verification_rules": {"coverage_complete": True, "no_channel_overlap": True},
        "prerequisites": ["wireless-controller", "vlans"],
        "sort_order": 21,
        "is_active": True,
    },
    {
        "slug": "firewalls",
        "title": "Firewall Configuration",
        "description": "Configure stateful firewall rules to protect network zones.",
        "category": "Security",
        "difficulty": "intermediate",
        "estimated_minutes": 60,
        "objectives": [
            "Define security zones (inside, outside, DMZ)",
            "Configure stateful inspection rules",
            "Allow specific traffic between zones",
            "Verify traffic filtering with packet tests",
        ],
        "theory_content": (
            "A stateful firewall tracks the state of network connections and makes "
            "filtering decisions based on connection context. Firewalls are configured "
            "with security zones (inside = trusted, outside = untrusted, DMZ = "
            "semi-trusted) and policies control what traffic can flow between zones. "
            "Modern next-generation firewalls (NGFW) add application awareness, "
            "intrusion prevention, and URL filtering."
        ),
        "instructions": [
            {"step": 1, "title": "Define security zones", "description": "Create inside, outside, and DMZ zones on the firewall."},
            {"step": 2, "title": "Configure policies", "description": "Allow outbound web traffic and deny unsolicited inbound connections."},
            {"step": 3, "title": "Set up DMZ rules", "description": "Permit external access to DMZ servers on specific ports."},
            {"step": 4, "title": "Verify filtering", "description": "Test permitted and denied traffic flows."},
        ],
        "initial_topology": {
            "devices": [
                {"type": "firewall", "label": "FW1", "x": 100, "y": 200},
                {"type": "host", "label": "Internal PC", "x": 300, "y": 200},
                {"type": "server", "label": "DMZ Server", "x": 500, "y": 200},
                {"type": "cloud", "label": "Internet", "x": 700, "y": 200},
            ],
            "connections": [
                {"source": "Internal PC", "target": "FW1", "source_interface": "eth0", "target_interface": "inside"},
                {"source": "DMZ Server", "target": "FW1", "source_interface": "eth0", "target_interface": "dmz"},
                {"source": "Internet", "target": "FW1", "source_interface": "port1", "target_interface": "outside"},
            ],
        },
        "verification_rules": {"zones_defined": True, "stateful_inspection": True, "dmz_accessible": True},
        "prerequisites": ["acls", "nat"],
        "sort_order": 22,
        "is_active": True,
    },
    {
        "slug": "comprehensive",
        "title": "Comprehensive Network Lab",
        "description": "A complete end-to-end network deployment combining all major technologies.",
        "category": "Routing",
        "difficulty": "advanced",
        "estimated_minutes": 120,
        "objectives": [
            "Design and implement a multi-site enterprise network",
            "Integrate switching, routing, security, and wireless",
            "Configure redundancy at every layer",
            "Verify full end-to-end connectivity and security policies",
        ],
        "theory_content": (
            "This comprehensive lab integrates all the networking technologies covered in "
            "the curriculum: VLANs and STP for Layer 2, OSPF and BGP for routing, NAT/PAT "
            "for internet access, firewalls and ACLs for security, wireless for client "
            "access, and SSH for management. Building a complete network from scratch "
            "reinforces how these technologies work together in a real enterprise deployment."
        ),
        "instructions": [
            {"step": 1, "title": "Design the topology", "description": "Plan the IP addressing, VLANs, and device placement."},
            {"step": 2, "title": "Configure Layer 2", "description": "Set up VLANs, trunks, and STP."},
            {"step": 3, "title": "Configure routing", "description": "Deploy OSPF internally and BGP toward the internet."},
            {"step": 4, "title": "Configure security", "description": "Implement firewall zones, ACLs, NAT, and SSH management."},
            {"step": 5, "title": "Configure wireless", "description": "Deploy APs and WLC with secure WLAN."},
            {"step": 6, "title": "Verify full connectivity", "description": "Test all traffic flows and verify security policies."},
        ],
        "initial_topology": {
            "devices": [
                {"type": "switch", "label": "Core Switch", "x": 100, "y": 200},
                {"type": "router", "label": "Edge Router", "x": 300, "y": 200},
                {"type": "firewall", "label": "Firewall", "x": 500, "y": 200},
                {"type": "wireless-controller", "label": "WLC", "x": 700, "y": 200},
                {"type": "wireless-ap", "label": "AP1", "x": 900, "y": 200},
                {"type": "host", "label": "Workstation", "x": 1100, "y": 200},
                {"type": "server", "label": "App Server", "x": 1300, "y": 200},
            ],
            "connections": [
                {"source": "Workstation", "target": "Core Switch", "source_interface": "eth0", "target_interface": "fa0/1"},
                {"source": "Core Switch", "target": "Firewall", "source_interface": "gi0/1", "target_interface": "inside"},
                {"source": "Firewall", "target": "Edge Router", "source_interface": "outside", "target_interface": "gi0/0"},
                {"source": "Core Switch", "target": "WLC", "source_interface": "gi0/2", "target_interface": "gi0/0"},
                {"source": "WLC", "target": "AP1", "source_interface": "gi0/1", "target_interface": "eth0"},
                {"source": "App Server", "target": "Firewall", "source_interface": "eth0", "target_interface": "dmz"},
            ],
        },
        "verification_rules": {
            "full_reachability": True,
            "security_policies": True,
            "redundancy": True,
        },
        "prerequisites": [
            "vlans", "stp", "ospf", "bgp", "acls", "nat", "firewalls",
            "wireless-controller", "ssh",
        ],
        "sort_order": 23,
        "is_active": True,
    },
]


async def seed_labs(db: AsyncSession) -> None:
    result = await db.execute(select(Lab).limit(1))
    if result.scalars().first() is not None:
        return

    for lab_data in LAB_SEED_DATA:
        lab = Lab(**lab_data)
        db.add(lab)

    await db.commit()
