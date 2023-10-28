from conftest import BASE_REACHABILITY, Net, vms_down

PORT_RANGES_TO_SCAN = [
    (1, 2000),
    (8000, 9000),
    (20000, 26000),
]


class TestBase:
    def test_reachability_base(self, net: Net) -> None:
        # Base reachability when all VMs are up
        net.assert_reachability(BASE_REACHABILITY)

    @vms_down("internet")
    def test_reachability_no_internet(self, net: Net) -> None:
        # If internet is down, nothing can reach the outside world
        net.assert_reachability(
            {
                "router1": [
                    "router1_lan",
                    "router1_wan",
                    "router2_wan",
                    "pi1",
                    "pi1_vpn",
                    "ubuntu",
                ],
                "router2": [
                    "router1_wan",
                    "router2_lan",
                    "router2_wan",
                    "pi2",
                    "pi2_vpn",
                    "ubuntu",
                ],
                "pi1": ["router1_lan", "router1_wan", "router2_wan", "pi1", "pi1_vpn", "ubuntu"],
                "pi2": ["router1_wan", "router2_lan", "router2_wan", "pi2", "pi2_vpn", "ubuntu"],
                "ubuntu": ["router1_wan", "router2_wan", "ubuntu"],
            }
        )

    @vms_down("router1")
    def test_reachability_no_router(self, net: Net) -> None:
        # If a router is down, that LAN can't access any other network
        net.assert_reachability(
            {
                "internet": ["external", "internet", "router2_wan", "ubuntu"],
                "router2": [
                    "external",
                    "internet",
                    "router2_lan",
                    "router2_wan",
                    "pi2",
                    "pi2_vpn",
                    "ubuntu",
                ],
                "pi1": ["pi1", "pi1_vpn"],
                "pi2": [
                    "external",
                    "internet",
                    "router2_lan",
                    "router2_wan",
                    "pi2",
                    "pi2_vpn",
                    "ubuntu",
                ],
                "ubuntu": ["external", "internet", "router2_wan", "ubuntu"],
            }
        )

    def test_routing_base(self, net: Net) -> None:
        # Base routing when all VMs are up
        net.assert_routes(
            {
                "internet": {
                    "external": [],
                    "internet": [],
                    "router1_wan": [],
                    "router2_wan": [],
                    "ubuntu": [],
                },
                "router1": {
                    "external": ["internet"],
                    "internet": [],
                    "router1_lan": [],
                    "router1_wan": [],
                    "router2_wan": [],
                    "pi1": [],
                    "pi1_vpn": [],
                    "ubuntu": [],
                },
                "router2": {
                    "external": ["internet"],
                    "internet": [],
                    "router1_wan": [],
                    "router2_lan": [],
                    "router2_wan": [],
                    "pi2": [],
                    "pi2_vpn": [],
                    "ubuntu": [],
                },
                "pi1": {
                    "external": ["router1_lan", "internet"],
                    "internet": ["router1_lan"],
                    "router1_lan": [],
                    "router1_wan": [],
                    "router2_wan": ["router1_lan"],
                    "pi1": [],
                    "pi1_vpn": [],
                    "ubuntu": ["router1_lan"],
                },
                "pi2": {
                    "external": ["router2_lan", "internet"],
                    "internet": ["router2_lan"],
                    "router1_wan": ["router2_lan"],
                    "router2_lan": [],
                    "router2_wan": [],
                    "pi2": [],
                    "pi2_vpn": [],
                    "ubuntu": ["router2_lan"],
                },
                "ubuntu": {
                    "external": ["internet"],
                    "internet": [],
                    "router1_wan": [],
                    "router2_wan": [],
                    "ubuntu": [],
                },
            }
        )

    @vms_down("internet")
    def test_routing_no_internet(self, net: Net) -> None:
        # If internet is down, nothing can reach the outside world
        net.assert_routes(
            {
                "router1": {
                    "router1_lan": [],
                    "router1_wan": [],
                    "router2_wan": [],
                    "pi1": [],
                    "pi1_vpn": [],
                    "ubuntu": [],
                },
                "router2": {
                    "router1_wan": [],
                    "router2_lan": [],
                    "router2_wan": [],
                    "pi2": [],
                    "pi2_vpn": [],
                    "ubuntu": [],
                },
                "pi1": {
                    "router1_lan": [],
                    "router1_wan": [],
                    "router2_wan": ["router1_lan"],
                    "pi1": [],
                    "pi1_vpn": [],
                    "ubuntu": ["router1_lan"],
                },
                "pi2": {
                    "router1_wan": ["router2_lan"],
                    "router2_lan": [],
                    "router2_wan": [],
                    "pi2": [],
                    "pi2_vpn": [],
                    "ubuntu": ["router2_lan"],
                },
                "ubuntu": {
                    "router1_wan": [],
                    "router2_wan": [],
                    "ubuntu": [],
                },
            }
        )

    @vms_down("router1")
    def test_routing_no_router(self, net: Net) -> None:
        # If a router is down, that LAN can't access any other network
        net.assert_routes(
            {
                "internet": {
                    "external": [],
                    "internet": [],
                    "router2_wan": [],
                    "ubuntu": [],
                },
                "router2": {
                    "external": ["internet"],
                    "internet": [],
                    "router2_lan": [],
                    "router2_wan": [],
                    "pi2": [],
                    "pi2_vpn": [],
                    "ubuntu": [],
                },
                "pi1": {
                    "pi1": [],
                    "pi1_vpn": [],
                },
                "pi2": {
                    "external": ["router2_lan", "internet"],
                    "internet": ["router2_lan"],
                    "router2_lan": [],
                    "router2_wan": [],
                    "pi2": [],
                    "pi2_vpn": [],
                    "ubuntu": ["router2_lan"],
                },
                "ubuntu": {
                    "external": ["internet"],
                    "internet": [],
                    "router2_wan": [],
                    "ubuntu": [],
                },
            }
        )

    def test_firewall(self, net: Net) -> None:
        net.assert_ports_open(
            {
                "internet": {
                    "router1_wan": {
                        "tcp": {
                            1194,  # OpenVPN port forwarding
                        },
                        "udp": set(),
                    },
                    "router2_wan": {
                        "tcp": {
                            1194,  # OpenVPN port forwarding
                        },
                        "udp": set(),
                    },
                    "ubuntu": {
                        "tcp": {
                            22,  # SSH
                        },
                        "udp": set(),
                    },
                },
                "router1": {
                    "pi1": {
                        "tcp": {
                            22,  # SSH
                            53,  # DNS
                            80,  # Control panel
                            1194,  # OpenVPN
                            22000,  # Syncthing
                        },
                        "udp": {
                            53,  # DNS
                        },
                    },
                },
                "router2": {
                    "pi2": {
                        "tcp": {
                            22,  # SSH
                            53,  # DNS
                            80,  # Control panel
                            1194,  # OpenVPN
                            22000,  # Syncthing
                        },
                        "udp": {
                            53,  # DNS
                        },
                    },
                },
            },
            PORT_RANGES_TO_SCAN,
        )
