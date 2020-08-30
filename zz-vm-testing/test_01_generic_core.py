from typing import Dict, List, Tuple
from testinfra.host import Host
from conftest import Lines


class Test01GenericCore:
    def test_00_base_config(self, host_types: Dict[str, List[Tuple[str, Host]]]) -> None:
        for name, host in host_types['pi']:
            lines = Lines(host.check_output('debconf-show locales'), name)
            assert lines.contains(r'[^a-zA-Z]*locales/locales_to_be_generated: en_GB.UTF-8 UTF-8')
            assert lines.contains(r'[^a-zA-Z]*locales/default_environment_locale: en_GB.UTF-8')
