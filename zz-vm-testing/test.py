import json
import pytest
from testinfra.utils import ansible_runner
from easydict import EasyDict as edict


@pytest.fixture(scope='session')
def hosts():
    """Returns all hosts by name from the ansible inventory."""
    runner = ansible_runner.AnsibleRunner(
        '.vagrant/provisioners/ansible/inventory/vagrant_ansible_inventory')
    return edict({name: runner.get_host(name) for name in runner.get_hosts()})


@pytest.fixture(scope='session')
def addrs():
    """Returns all IP addresses by name."""
    with open('config.json') as f:
        j = json.load(f)
    return edict(j['addrs'])


def check_reachability(reachable, hosts, addrs):
    """Check that the reachability of the hosts is as expected.

    Args:
      reachable: mapping from hostname to addr names that should be reachable
        from that host. All host/addr pairs not listed will be checked for
        being unreachable.
      hosts: output of the hosts fixture.
      addrs: output of the addrs fixture.
    """
    all_checks = []
    for host in sorted(hosts):
        for addr in sorted(addrs):
            all_checks.append(
                (host, addr, host in reachable and addr in reachable[host]))

    reachable_failing = []
    unreachable_failing = []

    for host, addr, expected in all_checks:
        if hosts[host].addr(addrs[addr]).is_reachable != expected:
            if expected:
                reachable_failing.append((host, addr))
            else:
                unreachable_failing.append((host, addr))

    def format_failing(failing):
        return ['  %s -> %s (%s)' % (host, addr, addrs[addr])
                for host, addr in failing]

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
    assert not msg, msg


def test_reachability(hosts, addrs):
    check_reachability({
        'internet': ['internet'],
        'router1': ['internet', 'router1_lan', 'router1_wan', 'pi1'],
        'router2': ['internet', 'router2_lan', 'router2_wan', 'pi2'],
        'pi1': ['internet', 'router1_lan', 'router1_wan', 'pi1'],
        'pi2': ['internet', 'router2_lan', 'router2_wan', 'pi2']},
                       hosts, addrs)
    # TODO check that taking machines down makes things inaccessible
