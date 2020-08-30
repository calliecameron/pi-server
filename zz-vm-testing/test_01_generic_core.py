from typing import Dict, List, Tuple
from testinfra.host import Host
from conftest import Lines


class Test01GenericCore:
    def test_00_base_config(self, host_types: Dict[str, List[Tuple[str, Host]]]) -> None:
        for name, host in host_types['pi']:
            lines = Lines(host.check_output('debconf-show locales'), name)
            assert lines.contains(r'[^a-zA-Z]*locales/locales_to_be_generated: en_GB.UTF-8 UTF-8')
            assert lines.contains(r'[^a-zA-Z]*locales/default_environment_locale: en_GB.UTF-8')

    def test_01_packages(self, host_types: Dict[str, List[Tuple[str, Host]]]) -> None:
        for _, host in host_types['pi']:
            # We pick one of the packages that the script installs, that isn't installed by default.
            assert host.package('etckeeper').is_installed

    # 02-pi-new-user is a no-op in the testbed

    def test_03_cleanup_users(self, host_types: Dict[str, List[Tuple[str, Host]]]) -> None:
        for _, host in host_types['pi']:
            # We pick the most important user - root - and a few that are changed
            with host.sudo():
                assert host.user('root').password == '!'
                assert host.user('systemd-timesync').shell == '/usr/sbin/nologin'
                assert host.user('systemd-timesync').password == '!*'
                assert host.user('messagebus').shell == '/usr/sbin/nologin'
                assert host.user('messagebus').password == '!*'
