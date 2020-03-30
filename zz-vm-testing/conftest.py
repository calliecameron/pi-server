from typing import Dict, List, Tuple, cast
import json
import pytest
import vagrant as vagrant_lib
from testinfra.host import Host
from testinfra.utils import ansible_runner


class Vagrant:
    def __init__(self) -> None:
        super(Vagrant, self).__init__()
        self._v = vagrant_lib.Vagrant()

    def state(self) -> Dict[str, bool]:
        out = {}
        for vm in self._v.status():
            out[vm.name] = vm.state == self._v.RUNNING
        return out

    def running_vms(self) -> List[str]:
        return sorted([vm for vm, up in self.state().items() if up])

    def up(self, vm: str) -> None:
        self._v.up(vm_name=vm)

    def down(self, vm: str) -> None:
        self._v.halt(vm_name=vm)

    def ensure_all_up(self) -> None:
        for vm, up in sorted(self.state().items()):
            if not up:
                self.up(vm)


class Net:
    def __init__(self, hosts: Dict[str, Host], addrs: Dict[str, str], vagrant: Vagrant) -> None:
        super(Net, self).__init__()
        self._hosts = hosts
        self._addrs = addrs
        self._vagrant = vagrant

    def assert_reachability(self, reachable: Dict[str, List[str]]) -> None:
        """Verify reachability of all host/addr pairs is as expected.

        Args:
          reachable: mapping from hostname to addr names that should be reachable
            from that host. All host/addr pairs not listed will be checked for
            being unreachable.
        """
        running_vms = self._vagrant.running_vms()
        if sorted(reachable) != running_vms:
            raise ValueError(
                ("The keys in 'reachable' must exactly match the running VMs: "
                 "got %s, want %s. Either there is a mistake in 'reachable', "
                 "or some VMs are in the wrong state.") % (
                     sorted(reachable), running_vms))

        all_checks = []
        for host in sorted(running_vms):
            for addr in sorted(self._addrs):
                all_checks.append(
                    (host, addr, host in reachable and addr in reachable[host]))

        reachable_failing = []
        unreachable_failing = []

        for host, addr, expected in all_checks:
            if self._hosts[host].addr(self._addrs[addr]).is_reachable != expected:
                if expected:
                    reachable_failing.append((host, addr))
                else:
                    unreachable_failing.append((host, addr))

        def format_failing(failing: List[Tuple[str, str]]) -> List[str]:
            return ['  %s -> %s (%s)' % (host, addr, self._addrs[addr])
                    for host, addr in failing]

        if reachable_failing or unreachable_failing:
            lines = []
            if reachable_failing:
                lines.append(
                    'The following host/addr combinations should be reachable, but '
                    'are not:')
                lines += format_failing(reachable_failing)
            if unreachable_failing:
                lines.append(
                    'The following host/addr combinations are reachable, but should '
                    'not be:')
                lines += format_failing(unreachable_failing)

            msg = '\n'.join(lines)
            pytest.fail(msg)


@pytest.fixture(scope='session')
def hosts() -> Dict[str, Host]:
    """Returns all hosts by name from the ansible inventory."""
    runner = ansible_runner.AnsibleRunner(
        '.vagrant/provisioners/ansible/inventory/vagrant_ansible_inventory')
    return {name: runner.get_host(name) for name in runner.get_hosts()}


@pytest.fixture(scope='session')
def addrs() -> Dict[str, str]:
    """Returns all IP addresses by name."""
    with open('config.json') as f:
        return cast(Dict[str, str], json.load(f)['addrs'])


@pytest.fixture(scope='session')
def vagrant() -> Vagrant:
    return Vagrant()


@pytest.fixture(scope='session')
def net(hosts: Dict[str, Host], addrs: Dict[str, str], vagrant: Vagrant) -> Net:
    return Net(hosts, addrs, vagrant)


@pytest.fixture(scope='function', autouse=True)
def ensure_vms_up(vagrant: Vagrant) -> None:
    vagrant.ensure_all_up()
