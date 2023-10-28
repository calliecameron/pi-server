import datetime
import json
import re
import time as time_lib
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Optional, cast

import pytest
from _pytest.fixtures import FixtureRequest
from _pytest.mark.structures import MarkDecorator
from _pytest.python import Metafunc
from helpers import (
    CronRunner,
    Email,
    Journal,
    MockServer,
    Net,
    OpenVPN,
    ShadowDir,
    ShadowFile,
    Time,
    Vagrant,
    timer,
)
from testinfra.host import Host
from testinfra.modules.file import File
from testinfra.utils import ansible_runner

_ANSIBLE_RUNNER = ansible_runner.AnsibleRunner(
    ".vagrant/provisioners/ansible/inventory/vagrant_ansible_inventory"
)

BASE_REACHABILITY = {
    "internet": ["external", "internet", "router1_wan", "router2_wan", "ubuntu"],
    "router1": [
        "external",
        "internet",
        "router1_lan",
        "router1_wan",
        "router2_wan",
        "pi1",
        "pi1_vpn",
        "ubuntu",
    ],
    "router2": [
        "external",
        "internet",
        "router1_wan",
        "router2_lan",
        "router2_wan",
        "pi2",
        "pi2_vpn",
        "ubuntu",
    ],
    "pi1": [
        "external",
        "internet",
        "router1_lan",
        "router1_wan",
        "router2_wan",
        "pi1",
        "pi1_vpn",
        "ubuntu",
    ],
    "pi2": [
        "external",
        "internet",
        "router1_wan",
        "router2_lan",
        "router2_wan",
        "pi2",
        "pi2_vpn",
        "ubuntu",
    ],
    "ubuntu": ["external", "internet", "router1_wan", "router2_wan", "ubuntu"],
}


def _file_write(self: File, content: str) -> None:
    self.check_output(f"echo '{content}' > {self.path}")


File.write = _file_write  # type: ignore


def _file_clear(self: File) -> None:
    self.write("")


File.clear = _file_clear  # type: ignore


def _host_shadow_file(self: Host, path: str) -> ShadowFile:
    return ShadowFile(self, path)


Host.shadow_file = _host_shadow_file  # type: ignore


def _host_shadow_dir(self: Host, path: str) -> ShadowDir:
    return ShadowDir(self, path)


Host.shadow_dir = _host_shadow_dir  # type: ignore


def _host_client_ip(self: Host) -> str:
    return self.check_output('echo "${SSH_CLIENT}"').split()[0]


Host.client_ip = _host_client_ip  # type: ignore


def _host_make_bigfile(self: Host, path: str, mount_point: str) -> None:
    output = self.check_output(f"df --output=size,used {mount_point} | tail -n 1")
    # Sizes in kiB
    size = int(output.split()[0])
    used = int(output.split()[1])
    # Want to get it up to 92% full
    needed = int(0.92 * size) - used
    self.check_output(f"dd if=/dev/zero of={path} bs=1M count={int(needed / 1024)}")


Host.make_bigfile = _host_make_bigfile  # type: ignore


@contextmanager
def _host_disable_login_emails(self: Host) -> Iterator[None]:
    client_ip = self.client_ip()
    with self.shadow_file("/etc/pi-server/ssh/email-on-login-exceptions") as f:
        with self.sudo():
            f.write(f"vagrant:{client_ip}")
        yield


Host.disable_login_emails = _host_disable_login_emails  # type: ignore


@contextmanager
def _host_group_membership(self: Host, user: str, group: str) -> Iterator[None]:
    in_group = group in self.user(user).groups
    try:
        if not in_group:
            with self.sudo():
                self.check_output(f"adduser '{user}' '{group}'")
            yield
    finally:
        if not in_group:
            with self.sudo():
                self.check_output(f"deluser '{user}' '{group}'")


Host.group_membership = _host_group_membership  # type: ignore


def _host_time(
    self: Host,
    time: datetime.time,
    date: Optional[datetime.date] = None,
) -> Time:
    if date is None:
        date = datetime.date.today()
    return Time(self, time, date)


Host.time = _host_time  # type: ignore


def _host_run_crons(
    self: Host,
    time: Optional[datetime.time] = None,
    cmd_to_watch: str = "/bin/bash /etc/pi-server/cron/cron-runner",
    disable_sources_list: bool = True,
    date: Optional[datetime.date] = None,
) -> CronRunner:
    if time is None:
        time = datetime.time(hour=2, minute=24, second=50)
    if date is None:
        date = datetime.date.today()
    return CronRunner(self, time, cmd_to_watch, disable_sources_list, date)


Host.run_crons = _host_run_crons  # type: ignore


def _host_journal(self: Host) -> Journal:
    return Journal(self)


Host.journal = _host_journal  # type: ignore


def _hostnames() -> list[str]:
    """Returns all host names from the ansible inventory."""
    return sorted(_ANSIBLE_RUNNER.get_hosts())


def _host_type(hostname: str) -> str:
    match = re.fullmatch(r"([^0-9]+)[0-9]*", hostname)
    if match is None:
        raise ValueError(f"Can't find host type for host '{hostname}'")
    return match.group(1)


def host_number(hostname: str) -> str:
    match = re.fullmatch(r"[^0-9]+([0-9]*)", hostname)
    if match is None:
        raise ValueError(f"Can't find host number for host '{hostname}'")
    return match.group(1)


def _hostnames_by_type() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for hostname in _hostnames():
        out.setdefault(_host_type(hostname), []).append(hostname)
    for value in out.values():
        value.sort()
    return out


def corresponding_hostname(hostname: str, host_type: str) -> str:
    num = host_number(hostname)
    if num:
        return host_type + num
    return "internet"


@pytest.fixture(scope="session")
def hosts() -> dict[str, Host]:
    """Returns all hosts by name from the ansible inventory."""
    return {name: _ANSIBLE_RUNNER.get_host(name, ssh_config="ssh_config") for name in _hostnames()}


@pytest.fixture(scope="session")
def hosts_by_type(
    hosts: Mapping[str, Host],  # pylint: disable=redefined-outer-name
) -> dict[str, list[tuple[str, Host]]]:
    out: dict[str, list[tuple[str, Host]]] = {}
    for host_type, hostnames in _hostnames_by_type().items():
        out[host_type] = [(hostname, hosts[hostname]) for hostname in hostnames]
    return out


def for_hosts(*args: str) -> MarkDecorator:
    if not args:
        raise ValueError("Input to for_hosts must be non-empty")
    return pytest.mark.for_hosts(hosts=args)


def for_host_types(*args: str) -> MarkDecorator:
    hostnames = []
    hostnames_by_type = _hostnames_by_type()
    for host_type in args:
        hostnames += hostnames_by_type[host_type]
    return for_hosts(*hostnames)


@pytest.fixture(scope="session")
def addrs() -> dict[str, str]:
    """Returns all IP addresses by name."""
    with open("config.json", encoding="utf-8") as f:
        return cast(dict[str, str], json.load(f)["addrs"])


@pytest.fixture(scope="session")
def masks() -> dict[str, str]:
    """Returns all net masks by name."""
    with open("config.json", encoding="utf-8") as f:
        return cast(dict[str, str], json.load(f)["masks"])


@pytest.fixture(scope="session")
def vagrant() -> Vagrant:
    return Vagrant()


def vms_down(*args: str) -> MarkDecorator:
    return pytest.mark.vms_down(vms=args)


@pytest.fixture(scope="session")
def net(
    hosts: Mapping[str, Host],  # pylint: disable=redefined-outer-name
    addrs: Mapping[str, str],  # pylint: disable=redefined-outer-name
    vagrant: Vagrant,  # pylint: disable=redefined-outer-name
) -> Net:
    return Net(hosts, addrs, vagrant)


@pytest.fixture(scope="session")
def openvpn(
    hosts: Mapping[str, Host],  # pylint: disable=redefined-outer-name
    vagrant: Vagrant,  # pylint: disable=redefined-outer-name
) -> OpenVPN:
    return OpenVPN(hosts, vagrant)


@pytest.fixture()
def email(
    addrs: Mapping[str, str],  # pylint: disable=redefined-outer-name
) -> Email:
    e = Email(addrs["internet"])
    e.clear()
    return e


@pytest.fixture()
def mockserver(
    addrs: Mapping[str, str],  # pylint: disable=redefined-outer-name
) -> MockServer:
    m = MockServer(addrs["internet"])
    m.clear()
    return m


@pytest.fixture(scope="function", autouse=True)
@timer
def ensure_vm_state(
    vagrant: Vagrant,  # pylint: disable=redefined-outer-name
    request: FixtureRequest,
) -> None:
    down: tuple[str, ...] = ()
    for mark in request.keywords.get("pytestmark", []):
        if mark.name == "vms_down":
            down = mark.kwargs["vms"]
    if vagrant.set_states(down):
        time_lib.sleep(30)


def pytest_generate_tests(metafunc: Metafunc) -> None:
    marker = metafunc.definition.get_closest_marker("for_hosts")
    if marker:
        metafunc.parametrize("hostname", marker.kwargs["hosts"])
