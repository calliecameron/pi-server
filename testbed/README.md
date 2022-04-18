# Testbed

A collection of VMs for development and integration testing. Simulates two LANs
separated by the internet. Each LAN has a router and a pi. There is also an
external client not on either LAN.

## Setup

1. Install [VirtualBox](https://www.virtualbox.org/),
   [Vagrant](https://www.vagrantup.com/) and
   [Geckodriver](https://github.com/mozilla/geckodriver).
2. Run `sudo apt-get install tidy`.
3. Run `pip install -r requirements.txt`.
4. Run `ansible-galaxy install -r ../requirements.yml`.
5. Run `ansible-galaxy install -r requirements.yml`.
6. Start the testbed with `vagrant up`.

## Integration tests

Run `pytest`. This can take several hours.
