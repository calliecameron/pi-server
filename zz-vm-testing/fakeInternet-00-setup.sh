#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

sudo apt-get update &&
sudo apt-get upgrade &&
sudo apt-get dist-upgrade

if ! grep eth1 /etc/network/interfaces &>/dev/null; then
    sudo tee -a /etc/network/interfaces &>/dev/null <<EOF

# The fake internet
allow-hotplug eth1
iface eth1 inet dhcp
EOF

fi


DST='/etc/network/if-up.d/fakeInternet-boot-config'
sudo cp "${DIR}/fakeInternet-boot-config" "${DST}" &&
sudo chown root:root "${DST}" &&
sudo chmod a=r "${DST}" &&
sudo chmod u+x "${DST}"
