from typing import Dict
from testinfra.host import Host
from conftest import Net, OpenVPN


class TestServerToServerClient:
    def test_reachability(self, net: Net, openvpn: OpenVPN) -> None:
        with openvpn.connect('pi1', 'openvpn-server-to-server-client.conf', 'pi2'):
            net.assert_reachability({
                'internet': ['external', 'internet', 'router1_wan', 'router2_wan', 'ubuntu'],
                'router1': ['external', 'internet', 'router1_lan', 'router1_wan', 'router2_lan',
                            'router2_wan', 'pi1', 'pi2', 'ubuntu'],
                'router2': ['external', 'internet', 'router1_lan', 'router1_wan', 'router2_lan',
                            'router2_wan', 'pi1', 'pi2', 'ubuntu'],
                'pi1': ['external', 'internet', 'router1_lan', 'router1_wan', 'router2_lan',
                        'router2_wan', 'pi1', 'pi2', 'ubuntu'],
                'pi2': ['external', 'internet', 'router1_lan', 'router1_wan', 'router2_lan',
                        'router2_wan', 'pi1', 'pi2', 'ubuntu'],
                'ubuntu': ['external', 'internet', 'router1_wan', 'router2_wan', 'ubuntu']})


# class TestRouting:
#     def test_base(self, net: Net) -> None:
#         # Base routing when all VMs are up
#         net.assert_routes({
#             'internet': {
#                 'external': [],
#                 'internet': [],
#                 'router1_wan': [],
#                 'router2_wan': [],
#                 'ubuntu': [],
#             },
#             'router1': {
#                 'external': ['internet'],
#                 'internet': [],
#                 'router1_lan': [],
#                 'router1_wan': [],
#                 'router2_wan': [],
#                 'pi1': [],
#                 'ubuntu': [],
#             },
#             'router2': {
#                 'external': ['internet'],
#                 'internet': [],
#                 'router1_wan': [],
#                 'router2_lan': [],
#                 'router2_wan': [],
#                 'pi2': [],
#                 'ubuntu': [],
#             },
#             'pi1': {
#                 'external': ['router1_lan', 'internet'],
#                 'internet': ['router1_lan'],
#                 'router1_lan': [],
#                 'router1_wan': [],
#                 'router2_wan': ['router1_lan'],
#                 'pi1': [],
#                 'ubuntu': ['router1_lan'],
#             },
#             'pi2': {
#                 'external': ['router2_lan', 'internet'],
#                 'internet': ['router2_lan'],
#                 'router1_wan': ['router2_lan'],
#                 'router2_lan': [],
#                 'router2_wan': [],
#                 'pi2': [],
#                 'ubuntu': ['router2_lan'],
#             },
#             'ubuntu': {
#                 'external': ['internet'],
#                 'internet': [],
#                 'router1_wan': [],
#                 'router2_wan': [],
#                 'ubuntu': [],
#             },
#         })
