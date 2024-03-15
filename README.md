# pi-server

Ansible roles for a home server, using Ubuntu 22.04 on amd64 or arm64 (e.g.
Raspberry Pi 4).

## Top-level roles

| Role | Description |
| --- | --- |
| `pi_server.roles.base` | Basic server setup: Docker, monitoring with Prometheus, Traefik, automatic updates. |
| `pi_server.roles.pi_core` | Home server base: dynamic DNS and a control panel for services. Only suitable for use on a LAN, since most services are configured without authentication. Includes `pi_server.roles.base`. |
| `pi_server.roles.pi_full`| Home server services: Syncthing, MiniDLNA, PhotoPrism, Pi-hole, OpenVPN, backups via restic. Includes `pi_server.roles.pi_core`. Requires a ZFS pool for storing synced data, and certificates for OpenVPN; see below. |

For finer-grained choice of services, directly use the roles that
`pi_server.roles.pi_full` calls.

## Preparation

1. Install Ubuntu 22.04 on the server.

2. Create a non-root user with sudo access:

    ```shell
    sudo adduser USER
    sudo adduser USER sudo
    ```

3. Add the dev machine's SSH key to the new user's `authorized_keys`.

4. If using `pi_server.roles.pi_full`, set up a ZFS pool for storing synced
   data:

    ```shell
    # DEV_* should be the device files of the disks, e.g. /dev/sda, /dev/sdb.
    # ZPOOL_NAME must match pi_server_storage_zpool in the inventory.
    zpool create -m /mnt/data -o autoexpand=on -O acltype=posix -O atime=off -O \
        compression=on -O xattr=sa "${ZPOOL_NAME}" mirror "${DEV_1}" "${DEV_2}"
    ```

5. If using `pi_server.roles.pi_full`, create certificates for OpenVPN:

    ```shell
    # One time only: create the CA. DIR should be encrypted.
    cd ca
    ./make-ca "${DIR}" "${CA_NAME}"

    # For each server: create certs.
    cd "${DIR}"
    ./scripts/make-pi-server-certs
    ```

   Copy the generated certs to `/etc/pi-server/certs` on the server.

## Installation

Before using any of these roles, include `pi_server.role_helpers`. Example
playbook:

```yaml
- hosts: pi
  tasks:
    - ansible.builtin.include_role:
        name: pi_server.role_helpers

    - ansible.builtin.include_role:
        name: pi_server.roles.pi_core
```

Example inventory:

```yaml
all:
  hosts:
    pi:
      ansible_host: # the server's IP address
      ansible_user: # the user created on the server
      # pi_server_*: many vars needed by the roles; roles will complain if the
      #              vars they need are unset. See testbed/Vagrantfile for
      #              examples.

```

On the dev machine:

1. `pip install -r requirements.txt`.
2. `ansible-galaxy install -r requirements.yml`.
3. `ansible-playbook --ask-become-pass --inventory "${INVENTORY}" "${PLAYBOOK}"`

## VPN

Forward TPC port 1194 to the server on the server's LAN's router.

Set static routes on the server's LAN's router:

```text
${pi_server_vpn_network} via ${pi_server_lan_ip}
```

If using `pi_server.apps.openvpn.server_to_server_client` and
`pi_server.apps.openvpn.server_to_server_server`, set extra static routes on the
client server's LAN's router:

```text
${remote server's pi_server_lan_network} via ${pi_server_lan_ip}
${remote server's pi_server_vpn_network} via ${pi_server_lan_ip}
```

And on the remote server's LAN's router:

```text
${pi_server_lan_network} via ${remote server's pi_server_lan_ip}
${pi_server_vpn_network} via ${remote server's pi_server_lan_ip}
```

## Vagrant testbed

See [testbed/README.md](testbed/README.md).
