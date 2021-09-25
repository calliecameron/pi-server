Testbed
=======

A collection of VMs for development and integration testing. The
testbed simulates two LANs separated by the internet. Each LAN has a
router and a pi.

Setup
=====

1. Install VirtualBox and Vagrant.
2. Run `sudo apt-get install firefox-geckodriver tidy`.
3. Run `pip install -r requirements.txt`.
4. Run `ansible-galaxy install -r ../requirements.yml`
5. Run `ansible-galaxy install -r requirements.yml`.
6. Start the testbed with `vagrant up`.

Integration tests
=================

Run `pytest`. Note that this can take several hours.
