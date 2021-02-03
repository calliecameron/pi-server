Testbed
=======

A collection of VMs for development and integration testing. The
testbed simulates two LANs separated by the internet. Each LAN has a
router, a pi, and a client (e.g. a laptop).

Setup
=====

1. Install VirtualBox and Vagrant.
2. Run `pip install -r requirements.txt`.
3. Run `ansible-galaxy install -r requirements.yml`.
4. Start the testbed with `vagrant up`.

Integration tests
=================

TODO
