from conftest import Net, vms_down


class TestReachability:
    def test_base(self, net: Net) -> None:
        # Base reachability when all VMs are up
        net.assert_reachability({
            'internet': ['external', 'internet', 'router1_wan', 'router2_wan'],
            'router1': ['external', 'internet', 'router1_lan', 'router1_wan', 'router2_wan', 'pi1'],
            'router2': ['external', 'internet', 'router1_wan', 'router2_lan', 'router2_wan', 'pi2'],
            'pi1': ['external', 'internet', 'router1_lan', 'router1_wan', 'router2_wan', 'pi1'],
            'pi2': ['external', 'internet', 'router1_wan', 'router2_lan', 'router2_wan', 'pi2']})

    @vms_down('internet')
    def test_no_internet(self, net: Net) -> None:
        # If internet is down, nothing can reach the outside world
        net.assert_reachability({
            'router1': ['router1_lan', 'router1_wan', 'router2_wan', 'pi1'],
            'router2': ['router1_wan', 'router2_lan', 'router2_wan', 'pi2'],
            'pi1': ['router1_lan', 'router1_wan', 'router2_wan', 'pi1'],
            'pi2': ['router1_wan', 'router2_lan', 'router2_wan', 'pi2']})

    @vms_down('router1')
    def test_no_router(self, net: Net) -> None:
        # If a router is down, that LAN can't access any other network
        net.assert_reachability({
            'internet': ['external', 'internet', 'router2_wan'],
            'router2': ['external', 'internet', 'router2_lan', 'router2_wan', 'pi2'],
            'pi1': ['pi1'],
            'pi2': ['external', 'internet', 'router2_lan', 'router2_wan', 'pi2']})


class TestRouting:
    def test_base(self, net: Net) -> None:
        # Base routing when all VMs are up
        net.assert_routes({
            'internet': {
                'external': [],
                'internet': [],
                'router1_wan': [],
                'router2_wan': [],
            },
            'router1': {
                'external': ['internet'],
                'internet': [],
                'router1_lan': [],
                'router1_wan': [],
                'router2_wan': [],
                'pi1': [],
            },
            'router2': {
                'external': ['internet'],
                'internet': [],
                'router1_wan': [],
                'router2_lan': [],
                'router2_wan': [],
                'pi2': [],
            },
            'pi1': {
                'external': ['router1_lan', 'internet'],
                'internet': ['router1_lan'],
                'router1_lan': [],
                'router1_wan': [],
                'router2_wan': ['router1_lan'],
                'pi1': [],
            },
            'pi2': {
                'external': ['router2_lan', 'internet'],
                'internet': ['router2_lan'],
                'router1_wan': ['router2_lan'],
                'router2_lan': [],
                'router2_wan': [],
                'pi2': [],
            },
        })

    @vms_down('internet')
    def test_no_internet(self, net: Net) -> None:
        # If internet is down, nothing can reach the outside world
        net.assert_routes({
            'router1': {
                'router1_lan': [],
                'router1_wan': [],
                'router2_wan': [],
                'pi1': [],
            },
            'router2': {
                'router1_wan': [],
                'router2_lan': [],
                'router2_wan': [],
                'pi2': [],
            },
            'pi1': {
                'router1_lan': [],
                'router1_wan': [],
                'router2_wan': ['router1_lan'],
                'pi1': [],
            },
            'pi2': {
                'router1_wan': ['router2_lan'],
                'router2_lan': [],
                'router2_wan': [],
                'pi2': [],
            },
        })

    @vms_down('router1')
    def test_no_router(self, net: Net) -> None:
        # If a router is down, that LAN can't access any other network
        net.assert_routes({
            'internet': {
                'external': [],
                'internet': [],
                'router2_wan': [],
            },
            'router2': {
                'external': ['internet'],
                'internet': [],
                'router2_lan': [],
                'router2_wan': [],
                'pi2': [],
            },
            'pi1': {
                'pi1': [],
            },
            'pi2': {
                'external': ['router2_lan', 'internet'],
                'internet': ['router2_lan'],
                'router2_lan': [],
                'router2_wan': [],
                'pi2': [],
            },
        })


class TestFirewall:
    def test_firewall(self, net: Net) -> None:
        net.assert_ports_open({
            'internet': {
                'router1_wan': {'tcp': set(), 'udp': set()},
                'router2_wan': {'tcp': set(), 'udp': set()},
            },
            'router1': {
                'pi1': {'tcp': {22}, 'udp': {68}},
            },
            'router2': {
                'pi2': {'tcp': {22}, 'udp': {68}},
            },
        })
