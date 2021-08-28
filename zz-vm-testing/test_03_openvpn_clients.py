from typing import Dict
from testinfra.host import Host
from conftest import AddrInNet, Net, OpenVPN


class TestServerToServerClient:
    def test_reachability(self, net: Net, openvpn: OpenVPN) -> None:
        with openvpn.connect('pi1', 'openvpn-server-to-server-client.conf', 'pi2'):
            net.assert_reachability({
                'internet': ['external', 'internet', 'router1_wan', 'router2_wan', 'ubuntu'],
                'router1': ['external', 'internet', 'router1_lan', 'router1_wan', 'router2_lan',
                            'router2_wan', 'pi1', 'pi1_vpn', 'pi2', 'ubuntu'],
                'router2': ['external', 'internet', 'router1_lan', 'router1_wan', 'router2_lan',
                            'router2_wan', 'pi1', 'pi2', 'pi2_vpn', 'ubuntu'],
                'pi1': ['external', 'internet', 'router1_lan', 'router1_wan', 'router2_lan',
                        'router2_wan', 'pi1', 'pi1_vpn', 'pi2', 'pi2_vpn', 'ubuntu'],
                # pi2 -> router1_lan should work, but doesn't, because the packets come from
                # pi2's VPN address, and router1 doesn't know how to route the replies to that
                # subnet. Same for pi2 -> pi1_vpn
                'pi2': ['external', 'internet', 'router1_wan', 'router2_lan', 'router2_wan',
                        'pi1', 'pi2', 'pi2_vpn', 'ubuntu'],
                'ubuntu': ['external', 'internet', 'router1_wan', 'router2_wan', 'ubuntu']})

    def test_routing(self, masks: Dict[str, str], net: Net, openvpn: OpenVPN) -> None:
        with openvpn.connect('pi1', 'openvpn-server-to-server-client.conf', 'pi2'):
            # Base routing when all VMs are up
            net.assert_routes({
                'internet': {
                    'external': [],
                    'internet': [],
                    'router1_wan': [],
                    'router2_wan': [],
                    'ubuntu': [],
                },
                'router1': {
                    'external': ['internet'],
                    'internet': [],
                    'router1_lan': [],
                    'router1_wan': [],
                    'router2_lan': ['pi1', 'pi2_vpn'],
                    'router2_wan': [],
                    'pi1': [],
                    'pi1_vpn': [],
                    'pi2': ['pi1'],
                    'ubuntu': [],
                },
                'router2': {
                    'external': ['internet'],
                    'internet': [],
                    'router1_lan': ['pi2', AddrInNet(masks['pi2_vpn'] + '/24')],
                    'router1_wan': [],
                    'router2_lan': [],
                    'router2_wan': [],
                    'pi1': ['pi2'],
                    'pi2': [],
                    'pi2_vpn': [],
                    'ubuntu': [],
                },
                'pi1': {
                    'external': ['router1_lan', 'internet'],
                    'internet': ['router1_lan'],
                    'router1_lan': [],
                    'router1_wan': [],
                    'router2_lan': ['pi2_vpn'],
                    'router2_wan': ['router1_lan'],
                    'pi1': [],
                    'pi1_vpn': [],
                    'pi2': [],
                    'pi2_vpn': [],
                    'ubuntu': ['router1_lan'],
                },
                'pi2': {
                    'external': ['router2_lan', 'internet'],
                    'internet': ['router2_lan'],
                    # pi2 -> router1_lan should work, but doesn't, because the packets come from
                    # pi2's VPN address, and router1 doesn't know how to route the replies to that
                    # subnet.
                    'router1_wan': ['router2_lan'],
                    'router2_lan': [],
                    'router2_wan': [],
                    'pi1': [],
                    # pi2 -> pi1_vpn should also work
                    'pi2': [],
                    'pi2_vpn': [],
                    'ubuntu': ['router2_lan'],
                },
                'ubuntu': {
                    'external': ['internet'],
                    'internet': [],
                    'router1_wan': [],
                    'router2_wan': [],
                    'ubuntu': [],
                },
            })


class TestSingleMachineClient:
    def test_reachability(self, addrs: Dict[str, str], net: Net, openvpn: OpenVPN) -> None:
        with openvpn.connect('ubuntu', '%s-client.conf' % addrs['router2_wan'], 'pi2'):
            net.assert_reachability({
                'internet': ['external', 'internet', 'router1_wan', 'router2_wan', 'ubuntu'],
                'router1': ['external', 'internet', 'router1_lan', 'router1_wan', 'router2_wan',
                            'pi1', 'pi1_vpn', 'ubuntu'],
                'router2': ['external', 'internet', 'router1_wan', 'router2_lan', 'router2_wan',
                            'pi2', 'pi2_vpn', 'ubuntu'],
                'pi1': ['external', 'internet', 'router1_lan', 'router1_wan', 'router2_wan',
                        'pi1', 'pi1_vpn', 'ubuntu'],
                'pi2': ['external', 'internet', 'router1_wan', 'router2_lan', 'router2_wan',
                        'pi2', 'pi2_vpn', 'ubuntu'],
                'ubuntu': ['external', 'internet', 'router1_wan', 'router2_lan', 'router2_wan',
                           'pi2', 'pi2_vpn', 'ubuntu']})

    def test_routing(self, addrs: Dict[str, str], net: Net, openvpn: OpenVPN) -> None:
        with openvpn.connect('ubuntu', '%s-client.conf' % addrs['router2_wan'], 'pi2'):
            # Base routing when all VMs are up
            net.assert_routes({
                'internet': {
                    'external': [],
                    'internet': [],
                    'router1_wan': [],
                    'router2_wan': [],
                    'ubuntu': [],
                },
                'router1': {
                    'external': ['internet'],
                    'internet': [],
                    'router1_lan': [],
                    'router1_wan': [],
                    'router2_wan': [],
                    'pi1': [],
                    'pi1_vpn': [],
                    'ubuntu': [],
                },
                'router2': {
                    'external': ['internet'],
                    'internet': [],
                    'router1_wan': [],
                    'router2_lan': [],
                    'router2_wan': [],
                    'pi2': [],
                    'pi2_vpn': [],
                    'ubuntu': [],
                },
                'pi1': {
                    'external': ['router1_lan', 'internet'],
                    'internet': ['router1_lan'],
                    'router1_lan': [],
                    'router1_wan': [],
                    'router2_wan': ['router1_lan'],
                    'pi1': [],
                    'pi1_vpn': [],
                    'ubuntu': ['router1_lan'],
                },
                'pi2': {
                    'external': ['router2_lan', 'internet'],
                    'internet': ['router2_lan'],
                    'router1_wan': ['router2_lan'],
                    'router2_lan': [],
                    'router2_wan': [],
                    'pi2': [],
                    'pi2_vpn': [],
                    'ubuntu': [],
                },
                'ubuntu': {
                    'external': ['internet'],
                    'internet': [],
                    'router1_wan': [],
                    'router2_lan': ['pi2_vpn'],
                    'router2_wan': [],
                    'pi2': [],
                    'pi2_vpn': [],
                    'ubuntu': [],
                },
            })

# email
# cron
