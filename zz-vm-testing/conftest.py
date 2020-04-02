from typing import Dict, List, Tuple, cast
import json
import pytest
import trparse
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

    def traceroute(self, host: str, addr: str) -> List[str]:
        """Gets the hops from host to addr; empty list means unreachable."""
        result = trparse.loads(
            self._hosts[host].check_output('sudo traceroute -I %s', self._addrs[addr]))
        for hop in result.hops:
            for probe in hop.probes:
                if probe.annotation:
                    return []
        out = []
        for hop in result.hops:
            for probe in hop.probes:
                if probe.ip:
                    out.append(probe.ip)
                    break
        return out

    def _host_addr_pairs(self, hosts: List[str]) -> List[Tuple[str, str]]:
        running_vms = self._vagrant.running_vms()
        if sorted(hosts) != running_vms:
            raise ValueError(
                ("'hosts' must exactly match the running VMs: got %s, want %s. Either the wrong "
                 "hosts were passed in , or some VMs are in the wrong state.") % (
                     sorted(hosts), running_vms))

        out = []
        for host in sorted(hosts):
            for addr in sorted(self._addrs):
                out.append((host, addr))
        return out

    def assert_reachability(self, reachable: Dict[str, List[str]]) -> None:
        """Verify reachability of all host/addr pairs is as expected.

        Args:
          reachable: mapping from hostname to addr names that should be reachable
            from that host. All host/addr pairs not listed will be checked for
            being unreachable.
        """
        host_addr_pairs = self._host_addr_pairs(sorted(reachable))

        all_checks = []  # host, addr, expected reachability
        for host, addr in host_addr_pairs:
            all_checks.append((host, addr, addr in reachable[host]))

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

            pytest.fail('\n'.join(lines))

    def assert_routes(self, routes: Dict[str, Dict[str, List[str]]]) -> None:
        """Verify routes between all host/addr pairs are as expected.

        Args:
          routes: mapping from host to target addr to intermediate hops (i.e. not including the
          target itself), for all addrs that should be reachable from host. All host/addr pairs
          not listed will be checked for being unreachable.
        """
        host_addr_pairs = self._host_addr_pairs(sorted(routes))

        all_checks = []  # host, addr, expected route
        for host, addr in host_addr_pairs:
            all_checks.append(
                (host, addr, routes[host][addr] + [addr] if addr in routes[host] else []))

        incorrect = []

        for host, addr, route in all_checks:
            result = self.traceroute(host, addr)

            if addr == 'external':
                # External is a special case, in that we don't care where the packets go once they
                # leave the testbed.
                new_result = []
                for hop in result:
                    if hop not in self._addrs.values():
                        break
                    new_result.append(hop)
                result = new_result + [self._addrs[addr]]

            expected = [self._addrs[hop] for hop in route]
            if result != expected:
                incorrect.append((host, addr, route, expected, result))

        if incorrect:
            lines = ['Traceroute gave the wrong route for the following host/addr combinations:']
            for host, addr, route, expected, result in incorrect:
                lines.append('  %s -> %s (%s): want %s (%s), got %s' % (
                    host, addr, self._addrs[addr], route, expected, result))
            pytest.fail('\n'.join(lines))


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
