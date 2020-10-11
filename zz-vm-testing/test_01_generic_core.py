from typing import Dict, List, Tuple
from testinfra.host import Host
from conftest import Email, Lines, for_host_types


class Test01GenericCore:
    @for_host_types('pi')
    def test_00_base_config(self, hostname: str, hosts: Dict[str, Host]) -> None:
        lines = Lines(hosts[hostname].check_output('debconf-show locales'), hostname)
        assert lines.contains(r'[^a-zA-Z]*locales/locales_to_be_generated: en_GB.UTF-8 UTF-8')
        assert lines.contains(r'[^a-zA-Z]*locales/default_environment_locale: en_GB.UTF-8')

    @for_host_types('pi')
    def test_01_packages(self, hostname: str, hosts: Dict[str, Host]) -> None:
        # We pick one of the packages that the script installs, that isn't installed by default.
        assert hosts[hostname].package('etckeeper').is_installed

    # 02-pi-new-user is a no-op in the testbed.

    @for_host_types('pi')
    def test_03_cleanup_users(self, hostname: str, hosts: Dict[str, Host]) -> None:
        host = hosts[hostname]
        # We pick the most important user - root - and a few that are changed
        with host.sudo():
            assert host.user('root').password == '!'
            assert host.user('systemd-timesync').shell == '/usr/sbin/nologin'
            assert host.user('systemd-timesync').password == '!*'
            assert host.user('messagebus').shell == '/usr/sbin/nologin'
            assert host.user('messagebus').password == '!*'

    @for_host_types('pi')
    def test_04_vars(self, hostname: str, hosts: Dict[str, Host], addrs: Dict[str, str]) -> None:
        host = hosts[hostname]
        assert host.file('/etc/pi-server/lan-ip').content_string.strip() == addrs[hostname]
        assert host.file('/etc/pi-server/lan-iface').content_string.strip() == 'eth1'
        assert host.file('/etc/pi-server/fqdn').content_string.strip() == hostname + '.testbed'
        assert (host.file('/etc/pi-server/email-target').content_string.strip() ==
                'fake@fake.testbed')
        assert (host.file('/etc/pi-server/email-smtp-server').content_string.strip() ==
                addrs['internet'])
        assert host.file('/etc/pi-server/email-smtp-port').content_string.strip() == '1025'

    # 05-network is tested by test_base's reachability and routing tests.

    @for_host_types('pi')
    def test_06_email(self, email: Email, hostname: str, hosts: Dict[str, Host]) -> None:
        hosts[hostname].check_output('/etc/pi-server/send-notification-email foo bar')
        email.assert_emails([
            {
                'from': 'notification@%s.testbed' % hostname,
                'subject': '[%s] foo' % hostname,
                'body': 'bar\n\n'
            },
        ])
