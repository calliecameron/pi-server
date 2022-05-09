from datetime import date
import time
from typing import Dict
from urllib.parse import urlparse
from selenium.webdriver.common.by import By
from testinfra.host import Host
from conftest import for_host_types, WebDriver


class TestRoleMinecraftServer:

    @for_host_types('ubuntu')
    def test_server(
            self,
            hostname: str,
            hosts: Dict[str, Host]) -> None:
        host = hosts[hostname]
        server_service = host.docker('minecraft-server_minecraft_1')
        map_service = host.docker('minecraft-server_dynmap_1')

        try:
            with host.sudo():
                host.check_output(
                    'docker-compose -f '
                    '/etc/pi-server/minecraft/minecraft-server/docker-compose.yml stop')

            with host.shadow_dir('/var/pi-server/minecraft/server') as server_dir, \
                    host.shadow_dir('/var/pi-server/minecraft/dynmap') as map_dir:
                server_properties = server_dir.file('server.properties')
                server_properties_world = server_dir.file('server.properties.world')
                server_properties_foo = server_dir.file('server.properties.foo')
                map_current = map_dir.file('current')
                map_world = map_dir.file('map.world')
                map_foo = map_dir.file('map.foo')
                try:
                    with host.sudo():
                        host.check_output(f"mkdir '{map_dir.path}/current'")
                        host.check_output(f"mkdir '{map_dir.path}/current/web'")
                        host.check_output(
                            'chown -R ' +
                            f"pi-server-minecraft:pi-server-minecraft '{map_dir.path}/current'")
                        host.check_output(f"chmod -R u=rwx,go=rx '{map_dir.path}/current'")

                    with host.sudo():
                        host.check_output(
                            'docker-compose -f '
                            '/etc/pi-server/minecraft/minecraft-server/docker-compose.yml start')

                    # Test 'is-running'
                    with host.sudo():
                        assert server_service.is_running
                        assert map_service.is_running
                    assert host.check_output(
                        '/var/pi-server/minecraft/bin/minecraft is-running') == 'yes'

                    # Test 'stop'
                    host.check_output('/var/pi-server/minecraft/bin/minecraft stop')
                    with host.sudo():
                        assert not server_service.is_running
                        assert not map_service.is_running
                    res = host.run(
                        '/var/pi-server/minecraft/bin/minecraft is-running')
                    assert res.failed
                    assert res.stdout.strip() == 'no'

                    # Test 'start'
                    host.check_output('/var/pi-server/minecraft/bin/minecraft start')
                    with host.sudo():
                        assert server_service.is_running
                        assert map_service.is_running
                    assert host.check_output(
                        '/var/pi-server/minecraft/bin/minecraft is-running') == 'yes'

                    # Give the server enough time to initialise things
                    time.sleep(10)

                    # All world-related commands should fail at this point
                    assert server_properties.is_file
                    assert not server_properties.is_symlink
                    assert server_properties.contains('^level-name=world$')
                    assert not server_properties_world.exists
                    assert not server_properties_foo.exists
                    assert map_current.is_directory
                    assert not map_current.is_symlink
                    assert not map_world.exists
                    assert not map_foo.exists

                    host.run_expect([1], '/var/pi-server/minecraft/bin/minecraft list-worlds')
                    host.run_expect([1], '/var/pi-server/minecraft/bin/minecraft current-world')
                    host.run_expect([1], '/var/pi-server/minecraft/bin/minecraft new-world foo')
                    host.run_expect([1], '/var/pi-server/minecraft/bin/minecraft set-world foo')

                    assert server_properties.is_file
                    assert not server_properties.is_symlink
                    assert server_properties.contains('^level-name=world$')
                    assert not server_properties_world.exists
                    assert not server_properties_foo.exists
                    assert map_current.is_directory
                    assert not map_current.is_symlink
                    assert not map_world.exists
                    assert not map_foo.exists

                    with host.sudo():
                        assert server_service.is_running
                        assert map_service.is_running
                    assert host.check_output(
                        '/var/pi-server/minecraft/bin/minecraft is-running') == 'yes'

                    # Test 'init-worlds'
                    host.check_output('/var/pi-server/minecraft/bin/minecraft init-worlds')

                    assert server_properties.is_symlink
                    assert server_properties.linked_to == ('/var/pi-server/minecraft/server/'
                                                           'server.properties.world')
                    assert server_properties.contains('^level-name=world$')
                    assert server_properties_world.is_file
                    assert not server_properties_world.is_symlink
                    assert server_properties_world.contains('^level-name=world$')
                    assert not server_properties_foo.exists
                    assert map_current.is_symlink
                    assert map_current.linked_to == '/var/pi-server/minecraft/dynmap/map.world'
                    assert map_world.is_directory
                    assert not map_world.is_symlink
                    assert not map_foo.exists

                    with host.sudo():
                        assert server_service.is_running
                        assert map_service.is_running
                    assert host.check_output(
                        '/var/pi-server/minecraft/bin/minecraft is-running') == 'yes'

                    # Test 'init-worlds' is idempotent
                    host.check_output('/var/pi-server/minecraft/bin/minecraft init-worlds')

                    assert server_properties.is_symlink
                    assert server_properties.linked_to == ('/var/pi-server/minecraft/server/'
                                                           'server.properties.world')
                    assert server_properties.contains('^level-name=world$')
                    assert server_properties_world.is_file
                    assert not server_properties_world.is_symlink
                    assert server_properties_world.contains('^level-name=world$')
                    assert not server_properties_foo.exists
                    assert map_current.is_symlink
                    assert map_current.linked_to == '/var/pi-server/minecraft/dynmap/map.world'
                    assert map_world.is_directory
                    assert not map_world.is_symlink
                    assert not map_foo.exists

                    with host.sudo():
                        assert server_service.is_running
                        assert map_service.is_running
                    assert host.check_output(
                        '/var/pi-server/minecraft/bin/minecraft is-running') == 'yes'

                    # Test 'list-worlds'
                    assert host.check_output(
                        '/var/pi-server/minecraft/bin/minecraft list-worlds') == 'world'

                    assert server_properties.is_symlink
                    assert server_properties.linked_to == ('/var/pi-server/minecraft/server/'
                                                           'server.properties.world')
                    assert server_properties.contains('^level-name=world$')
                    assert server_properties_world.is_file
                    assert not server_properties_world.is_symlink
                    assert server_properties_world.contains('^level-name=world$')
                    assert not server_properties_foo.exists
                    assert map_current.is_symlink
                    assert map_current.linked_to == '/var/pi-server/minecraft/dynmap/map.world'
                    assert map_world.is_directory
                    assert not map_world.is_symlink
                    assert not map_foo.exists

                    with host.sudo():
                        assert server_service.is_running
                        assert map_service.is_running
                    assert host.check_output(
                        '/var/pi-server/minecraft/bin/minecraft is-running') == 'yes'

                    # Test 'current-world'
                    assert host.check_output(
                        '/var/pi-server/minecraft/bin/minecraft current-world') == 'world'

                    assert server_properties.is_symlink
                    assert server_properties.linked_to == ('/var/pi-server/minecraft/server/'
                                                           'server.properties.world')
                    assert server_properties.contains('^level-name=world$')
                    assert server_properties_world.is_file
                    assert not server_properties_world.is_symlink
                    assert server_properties_world.contains('^level-name=world$')
                    assert not server_properties_foo.exists
                    assert map_current.is_symlink
                    assert map_current.linked_to == '/var/pi-server/minecraft/dynmap/map.world'
                    assert map_world.is_directory
                    assert not map_world.is_symlink
                    assert not map_foo.exists

                    with host.sudo():
                        assert server_service.is_running
                        assert map_service.is_running
                    assert host.check_output(
                        '/var/pi-server/minecraft/bin/minecraft is-running') == 'yes'

                    # Test 'set-world' does nothing on current world
                    assert host.check_output(
                        '/var/pi-server/minecraft/bin/minecraft set-world world') == (
                            'Already active, nothing to do')

                    assert server_properties.is_symlink
                    assert server_properties.linked_to == ('/var/pi-server/minecraft/server/'
                                                           'server.properties.world')
                    assert server_properties.contains('^level-name=world$')
                    assert server_properties_world.is_file
                    assert not server_properties_world.is_symlink
                    assert server_properties_world.contains('^level-name=world$')
                    assert not server_properties_foo.exists
                    assert map_current.is_symlink
                    assert map_current.linked_to == '/var/pi-server/minecraft/dynmap/map.world'
                    assert map_world.is_directory
                    assert not map_world.is_symlink
                    assert not map_foo.exists

                    with host.sudo():
                        assert server_service.is_running
                        assert map_service.is_running
                    assert host.check_output(
                        '/var/pi-server/minecraft/bin/minecraft is-running') == 'yes'

                    # Test 'set-world' fails on nonexistent world
                    host.run_expect([1],
                                    '/var/pi-server/minecraft/bin/minecraft set-world foo')

                    assert server_properties.is_symlink
                    assert server_properties.linked_to == ('/var/pi-server/minecraft/server/'
                                                           'server.properties.world')
                    assert server_properties.contains('^level-name=world$')
                    assert server_properties_world.is_file
                    assert not server_properties_world.is_symlink
                    assert server_properties_world.contains('^level-name=world$')
                    assert not server_properties_foo.exists
                    assert map_current.is_symlink
                    assert map_current.linked_to == '/var/pi-server/minecraft/dynmap/map.world'
                    assert map_world.is_directory
                    assert not map_world.is_symlink
                    assert not map_foo.exists

                    with host.sudo():
                        assert server_service.is_running
                        assert map_service.is_running
                    assert host.check_output(
                        '/var/pi-server/minecraft/bin/minecraft is-running') == 'yes'

                    # Test 'new-world'
                    host.check_output('/var/pi-server/minecraft/bin/minecraft new-world foo')

                    assert server_properties.is_symlink
                    assert server_properties.linked_to == ('/var/pi-server/minecraft/server/'
                                                           'server.properties.world')
                    assert server_properties.contains('^level-name=world$')
                    assert server_properties_world.is_file
                    assert not server_properties_world.is_symlink
                    assert server_properties_world.contains('^level-name=world$')
                    assert server_properties_foo.is_file
                    assert not server_properties_foo.is_symlink
                    assert server_properties_foo.contains('^level-name=foo$')
                    assert map_current.is_symlink
                    assert map_current.linked_to == '/var/pi-server/minecraft/dynmap/map.world'
                    assert map_world.is_directory
                    assert not map_world.is_symlink
                    assert not map_foo.exists

                    with host.sudo():
                        assert server_service.is_running
                        assert map_service.is_running
                    assert host.check_output(
                        '/var/pi-server/minecraft/bin/minecraft is-running') == 'yes'
                    assert host.check_output(
                        '/var/pi-server/minecraft/bin/minecraft list-worlds') == 'foo\nworld'
                    assert host.check_output(
                        '/var/pi-server/minecraft/bin/minecraft current-world') == 'world'

                    # Test 'new-world' fails on existing world
                    host.run_expect([1], '/var/pi-server/minecraft/bin/minecraft new-world foo')

                    assert server_properties.is_symlink
                    assert server_properties.linked_to == ('/var/pi-server/minecraft/server/'
                                                           'server.properties.world')
                    assert server_properties.contains('^level-name=world$')
                    assert server_properties_world.is_file
                    assert not server_properties_world.is_symlink
                    assert server_properties_world.contains('^level-name=world$')
                    assert server_properties_foo.is_file
                    assert not server_properties_foo.is_symlink
                    assert server_properties_foo.contains('^level-name=foo$')
                    assert map_current.is_symlink
                    assert map_current.linked_to == '/var/pi-server/minecraft/dynmap/map.world'
                    assert map_world.is_directory
                    assert not map_world.is_symlink
                    assert not map_foo.exists

                    with host.sudo():
                        assert server_service.is_running
                        assert map_service.is_running
                    assert host.check_output(
                        '/var/pi-server/minecraft/bin/minecraft is-running') == 'yes'
                    assert host.check_output(
                        '/var/pi-server/minecraft/bin/minecraft list-worlds') == 'foo\nworld'
                    assert host.check_output(
                        '/var/pi-server/minecraft/bin/minecraft current-world') == 'world'

                    # Test 'set-world'
                    host.check_output('/var/pi-server/minecraft/bin/minecraft set-world foo')

                    assert server_properties.is_symlink
                    assert server_properties.linked_to == ('/var/pi-server/minecraft/server/'
                                                           'server.properties.foo')
                    assert server_properties.contains('^level-name=foo$')
                    assert server_properties_world.is_file
                    assert not server_properties_world.is_symlink
                    assert server_properties_world.contains('^level-name=world$')
                    assert server_properties_foo.is_file
                    assert not server_properties_foo.is_symlink
                    assert server_properties_foo.contains('^level-name=foo$')
                    assert map_current.is_symlink
                    assert map_current.linked_to == '/var/pi-server/minecraft/dynmap/map.foo'
                    assert map_world.is_directory
                    assert not map_world.is_symlink
                    assert map_foo.is_directory
                    assert not map_foo.is_symlink

                    with host.sudo():
                        assert server_service.is_running
                        assert map_service.is_running
                    assert host.check_output(
                        '/var/pi-server/minecraft/bin/minecraft is-running') == 'yes'
                    assert host.check_output(
                        '/var/pi-server/minecraft/bin/minecraft list-worlds') == 'foo\nworld'
                    assert host.check_output(
                        '/var/pi-server/minecraft/bin/minecraft current-world') == 'foo'

                    # Test 'backup'
                    host.check_output('/var/pi-server/minecraft/bin/minecraft backup')
                    today = date.today()
                    backup = host.file(
                        f'/home/vagrant/backup-{today.strftime("%Y-%m-%d")}.tar.xz')
                    assert backup.exists
                    host.check_output(f"rm '{backup.path}'")

                    assert server_properties.is_symlink
                    assert server_properties.linked_to == ('/var/pi-server/minecraft/server/'
                                                           'server.properties.foo')
                    assert server_properties.contains('^level-name=foo$')
                    assert server_properties_world.is_file
                    assert not server_properties_world.is_symlink
                    assert server_properties_world.contains('^level-name=world$')
                    assert server_properties_foo.is_file
                    assert not server_properties_foo.is_symlink
                    assert server_properties_foo.contains('^level-name=foo$')
                    assert map_current.is_symlink
                    assert map_current.linked_to == '/var/pi-server/minecraft/dynmap/map.foo'
                    assert map_world.is_directory
                    assert not map_world.is_symlink
                    assert map_foo.is_directory
                    assert not map_foo.is_symlink

                    with host.sudo():
                        assert server_service.is_running
                        assert map_service.is_running
                    assert host.check_output(
                        '/var/pi-server/minecraft/bin/minecraft is-running') == 'yes'
                    assert host.check_output(
                        '/var/pi-server/minecraft/bin/minecraft list-worlds') == 'foo\nworld'
                    assert host.check_output(
                        '/var/pi-server/minecraft/bin/minecraft current-world') == 'foo'

                finally:
                    with host.sudo():
                        host.check_output(
                            'docker-compose -f '
                            '/etc/pi-server/minecraft/minecraft-server/docker-compose.yml stop')

        finally:
            with host.sudo():
                host.check_output(
                    'docker-compose -f '
                    '/etc/pi-server/minecraft/minecraft-server/docker-compose.yml start')

    @for_host_types('ubuntu')
    def test_site(
            self,
            hostname: str,
            addrs: Dict[str, str]) -> None:
        this_addr = addrs[hostname]

        with WebDriver() as driver:
            driver.get('http://' + this_addr)
            assert driver.title == 'Minecraft'
            link = driver.find_element(by=By.LINK_TEXT, value='Current world')
            assert urlparse(link.get_attribute('href')).hostname == this_addr
            driver.click(link)
