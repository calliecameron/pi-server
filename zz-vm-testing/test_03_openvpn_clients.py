from typing import Dict
from testinfra.host import Host
from conftest import BASE_REACHABILITY, AddrInNet, Email, Net, OpenVPN, Vagrant


SERVER_TO_SERVER_REACHABILITY = {
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
    'ubuntu': ['external', 'internet', 'router1_wan', 'router2_wan', 'ubuntu']}


class TestServerToServerClient:
    def test_reachability(
            self,
            hosts: Dict[str, Host],
            addrs: Dict[str, str],
            email: Email,
            net: Net,
            openvpn: OpenVPN) -> None:
        with hosts['pi2'].disable_login_emails():
            email.clear()
            with openvpn.connect('pi1', 'openvpn-server-to-server-client.conf', 'pi2'):
                net.assert_reachability(SERVER_TO_SERVER_REACHABILITY)
                email.assert_emails([{
                    'from': 'notification@pi2.testbed',
                    'to': 'fake@fake.testbed',
                    'subject': ('[pi2] OpenVPN connection: pi1-client from %s' %
                                addrs['router1_wan']),
                    'body_re': r'Connected at .*\n(.*\n)*',
                }], only_from='pi2')

    def test_routing(
            self,
            hosts: Dict[str, Host],
            addrs: Dict[str, str],
            masks: Dict[str, str],
            email: Email,
            net: Net,
            openvpn: OpenVPN) -> None:
        with hosts['pi2'].disable_login_emails():
            email.clear()
            with openvpn.connect('pi1', 'openvpn-server-to-server-client.conf', 'pi2'):
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
                        # pi2's VPN address, and router1 doesn't know how to route the replies to
                        # that subnet.
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
                email.assert_emails([{
                    'from': 'notification@pi2.testbed',
                    'to': 'fake@fake.testbed',
                    'subject': ('[pi2] OpenVPN connection: pi1-client from %s' %
                                addrs['router1_wan']),
                    'body_re': r'Connected at .*\n(.*\n)*',
                }], only_from='pi2')


class TestSingleMachineClient:
    def test_reachability(
            self,
            hosts: Dict[str, Host],
            addrs: Dict[str, str],
            email: Email,
            net: Net,
            openvpn: OpenVPN) -> None:
        with hosts['pi2'].disable_login_emails():
            email.clear()
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
                email.assert_emails([{
                    'from': 'notification@pi2.testbed',
                    'to': 'fake@fake.testbed',
                    'subject': '[pi2] OpenVPN connection: ubuntu-client from %s' % addrs['ubuntu'],
                    'body_re': r'Connected at .*\n(.*\n)*',
                }], only_from='pi2')

    def test_routing(
            self,
            hosts: Dict[str, Host],
            addrs: Dict[str, str],
            email: Email,
            net: Net,
            openvpn: OpenVPN) -> None:
        with hosts['pi2'].disable_login_emails():
            email.clear()
            with openvpn.connect('ubuntu', '%s-client.conf' % addrs['router2_wan'], 'pi2'):
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
                        # The non-VPN route takes precedence here.
                        'ubuntu': ['router2_lan'],
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
                email.assert_emails([{
                    'from': 'notification@pi2.testbed',
                    'to': 'fake@fake.testbed',
                    'subject': '[pi2] OpenVPN connection: ubuntu-client from %s' % addrs['ubuntu'],
                    'body_re': r'Connected at .*\n(.*\n)*',
                }], only_from='pi2')


class TestCron:
    def test_cron(
            self,
            hosts: Dict[str, Host],
            addrs: Dict[str, str],
            email: Email,
            net: Net,
            vagrant: Vagrant) -> None:
        pi1 = hosts['pi1']
        pi2 = hosts['pi2']

        try:
            with pi2.disable_login_emails():
                # No nightly config; nothing happens
                email.clear()
                with pi1.run_crons(
                        time='22:59:50',
                        cmd_to_watch='/bin/bash /etc/pi-server/openvpn-nightly'):
                    net.assert_reachability(BASE_REACHABILITY)
                    email.assert_emails([], only_from='pi2')

                # Nightly config enabled
                email.clear()
                with pi1.shadow_file('/etc/pi-server/openvpn-nightly-config') as f:
                    with pi1.sudo():
                        f.write('openvpn-server-to-server-client.conf')
                    with pi1.run_crons(
                            time='22:59:50',
                            cmd_to_watch='/bin/bash /etc/pi-server/openvpn-nightly'):
                        net.assert_reachability(SERVER_TO_SERVER_REACHABILITY)
                        email.assert_emails([{
                            'from': 'notification@pi2.testbed',
                            'to': 'fake@fake.testbed',
                            'subject': ('[pi2] OpenVPN connection: pi1-client from %s' %
                                        addrs['router1_wan']),
                            'body_re': r'Connected at .*\n(.*\n)*',
                        }], only_from='pi2')
        finally:
            vagrant.reboot('pi1', 'pi2')
