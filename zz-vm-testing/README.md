The files in this folder are for setting up a network of VMs for
testing on, using VirtualBox.

Need three host-only networks, appropriately configured with DHCP:
- vboxnet0 - 192.168.56.0/24; 'fake internet'
- vboxnet1 - 192.168.57.0/24; 'fake LAN 1'
- vboxnet2 - 192.168.58.0/24; 'fake LAN 2'

Need 7 VMs:
- FakeInternet - Debian, two network interfaces: NAT and vboxnet0
- FakeRouter1 - Debian, two network interfaces: vboxnet0 and vboxnet1
- FakeRouter2 - Debian, two network interfaces: vboxnet0 and vboxnet2
- FakePi1 - Debian, vboxnet1 only; VPN subnet set to 10.30.1.0/24; with a second hard disk
- FakePi2 - Debian, vboxnet2 only; VPN subnet set to 10.30.2.0/24; with a second hard disk
- FakeClient1 - a desktop OS, vboxnet1 only (FakePi1's LAN)
- FakeClient2 - a desktop OS, vboxnet2 only (FakePi2's LAN)
- FakeClient3 - a desktop OS, vboxnet0 only (a client elsewhere on the Internet)

All but FakeInternet will have no valid internet connection during
installation. The Debian installations should be command-line only,
with only system tools selected during tasksel.


FakeInternet:
1. `sudo apt-get update; sudo apt-get -y install git`
2. Clone this repository, `cd pi-server/zz-vm-testing`
3. `./fakeInternet-00-setup.sh`
4. Reboot.


FakeRouter*:
1. `sudo ip route add default via ${FakeInternet's addr} dev eth0`
2. `echo nameserver 8.8.8.8 | sudo tee /etc/resolv.conf`
3. Edit /etc/apt/sources.list to look like FakeInternet's
4. `sudo apt-get update; sudo apt-get -y install git`
5. Clone this repository, `cd pi-server/zz-vm-testing`
6. Make sure the corresponding FakePi is set up to the point where you
   can get its IP address with `/sbin/config`; you need this in step 7
7. `./fakeRouter-00-setup.sh`
8. Reboot.


FakePi*:
1. `sudo ip route add default via ${corresponding FakeRouter's addr} dev eth0`
2. `echo nameserver 8.8.8.8 | sudo tee /etc/resolv.conf`
3. Edit /etc/apt/sources.list to look like FakeInternet's
4. `sudo apt-get update; sudo apt-get -y install git`
5. Clone this repository, `cd pi-server/zz-vm-testing`
6. `./fakePi-00-setup.sh`
7. Reboot
8. Set the Pi up normally as per `01-core`


FakeClient*: assuming use of Mint 17.3
1. Edit /etc/network/interfaces to add the following:
    auto eth0
    iface eth0 inet dhcp
    dns-nameservers 8.8.8.8
2. Reboot
3. `sudo ip route add default via ${corresponding FakeRouter's addr} dev eth0`
4. `sudo apt-get update; sudo apt-get -y install git`
5. Clone this repository, `cd pi-server/zz-vm-testing`
6. `./fakeClient-00-setup.sh`
7. Reboot
