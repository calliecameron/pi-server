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
4. `git clone https://github.com/CallumCameron/pi-server`
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


Updates
-------

If you pull the repo and see that something has changed, re-run the
changed script or the scripts that use changed files. Or, if it is a
big update, it is probably easier to re-run everything, in order; all
the scripts are idempotent, so anything that hasn't changed will just
do nothing.


Upgrading from Jessie to Stretch
--------------------------------

You will need to reinstall the OS from scratch. But nothing on the
external hard drive has changed, so you can re-use that as is.

To make the upgrade completely seamless, use the same certificates as
before, and configure everything in the same way when you run the
setup scripts, and the existing data/config on the hard drive will be
picked up and should just work (e.g. Syncthing peers shouldn't notice
anything has changed).
