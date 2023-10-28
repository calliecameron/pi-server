# pi-server

Ansible roles for servers running Ubuntu 22.04 LTS. Intended for use on
Raspberry Pi 4.

## Roles

Include one or more of the following roles in your playbook:

- `pi_server.roles.base`: basic system with docker, monitoring and automatic
  updates.
- `pi_server.roles.pi_core`: basic home server setup; only install this on a
  machine on a LAN, since it opens various ports. Includes
  `pi_server.roles.base`.
- `pi_server.roles.pi_full`: more apps for a home server / NAS: syncthing,
  minidlna, pihole, restic and openvpn. Includes `pi_server.roles.pi_core`.
  Requires a zfs pool for storing synced data, and certificates for openvpn; see
  below.

Before using any of these roles, you must include `pi_server.role_helpers`.
Example playbook:

```yaml
- hosts: pi
  tasks:
    - ansible.builtin.include_role:
        name: pi_server.role_helpers

    - ansible.builtin.include_role:
        name: pi_server.roles.pi_core
```

## Preparation

Install Ubuntu 22.04 and create a non-root user that you can SSH into using an
SSH key:

```shell
sudo adduser USER
sudo adduser USER sudo
```

If you're using `pi_server.roles.pi_full`, you must also set up a zfs pool for
storing synced data (e.g. on a USB disk if using a Raspberry Pi):

```shell
# DEV should be the device file of your disk, e.g. /dev/sda
# ZPOOL_NAME must match pi_server_storage_zpool in your inventory
zpool create -m /mnt/data -o autoexpand=on -O acltype=posix -O atime=off -O \
    compression=on -O xattr=sa "${ZPOOL_NAME}" "${DEV}"
```

If you're using `pi_server.roles.pi_full`, you also need to create certificates:

```shell
# One time only: create the CA. DIR should be encrypted.
cd 00-ca
./00-make-ca "${DIR}" "${YOUR_NAME}"

# For each server: create certs.
cd "${DIR}"
./scripts/make-pi-server-certs
```

Then copy the generated certs to `/etc/pi-server/certs` on the server.

## Installation

On the host where you'll run ansible:

1. Run `pip install -r requirements.txt`.
2. Run `ansible-galaxy install -r requirements.yml`.
3. Run `sudo apt-get install graphviz tidy`

## Certificates

## VPN

TODO old notes:

From 08-openvpn-server:

```shell
Log in to your router, and setup a static route to ${PI_SERVER_VPN_NETWORK}/24 via ${PI_SERVER_IP}
```

From 00-openvpn-server-to-server-client:

```shell
On your local router, add the following route:

route to <remote server's LAN subnet> via ${PI_SERVER_IP}
route to <remote server's VPN subnet> via ${PI_SERVER_IP}
route to ${PI_SERVER_VPN_NETWORK} via ${PI_SERVER_IP}

On the remote server's router, add the following route:

route to ${PI_SERVER_LAN_NETWORK} via <remote server's LAN IP>
route to ${PI_SERVER_VPN_NETWORK} via <remote server's LAN IP>
route to <remote server's VPN subnet via <remote server's LAN IP>
```

## Testing

See [testbed/README.md](testbed/README.md).

Pi Server
=========

These are the scripts I use to setup and manage my Raspberry Pi home
server. Nothing fancy, just a basic Raspbian Stretch setup with:

- SSH
- OpenVPN
- Syncthing
- a media server
- podcast downloading through RSS

plus some stuff for generating and managing keys. Intended usage is
for the VPN to be accessible through the home router's firewall, with
everything else accessible only to machines on the LAN or through the
VPN.

It's also set up so that a second Pi on another LAN somewhere else can
connect to the first, and they will maintain a site-to-site VPN with
each other, so that clients on either LAN have full access to both
networks. The intended usage for this is so that the two side's
Syncthing instances can talk without having to be exposed to the
internet.

Installation
------------

One time only: on your desktop/laptop, use `00-ca` to create the CA
folder:

1. `cd 00-ca`
2. `./00-make-ca <dir> <your_name>`, where dir should typically be
   inside an encrypted volume.

To install on a Pi:

1. Generate certificates and keys for the Pi by running
   `make-pi-server-certs` in the folder created by `00-make-ca`.
2. Install the Raspbian Stretch Lite image on the Pi,
   [enable SSH](https://www.raspberrypi.org/blog/a-security-update-for-raspbian-pixel/)
   by creating a file `ssh` in the boot partition, boot, and log
   in.
3. `sudo apt-get update; sudo apt-get -y install git`
4. `git clone https://github.com/calliecameron/pi-server`
5. `cd pi-server`

In each of the numbered folders starting with `01-generic-core` in
order, run each of the numbered scripts in order, and follow the
instructions they give.

Other servers
-------------

The scripts in `01-generic-core` can be used, on their own, to do the
basic setup of any Debian/Raspbian Stretch or Ubuntu 16.04 server - not
just a Pi. All the other folders are Pi-specific, though.

The scripts should be run as a non-root user with sudo access, so you
may need to create one manually first.

Upgrading from Jessie to Stretch
--------------------------------

You will need to reinstall the OS from scratch. But nothing on the
external hard drive has changed, so you can re-use that as is.

To make the upgrade completely seamless, use the same certificates as
before, and configure everything in the same way when you run the
setup scripts, and the existing data/config on the hard drive will be
picked up and should just work (e.g. Syncthing peers shouldn't notice
anything has changed).
