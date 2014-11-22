#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

sudo apt-get update &&
sudo apt-get -y upgrade &&
sudo apt-get -y dist-upgrade

if ! grep eth1 /etc/network/interfaces &>/dev/null; then
    sudo tee -a /etc/network/interfaces &>/dev/null <<EOF

# The fake LAN
allow-hotplug eth1
iface eth1 inet dhcp
EOF

fi


echo &&
printf "Enter the address of the default route (FakeInternet): " &&
read DEFAULT_ROUTE &&

CONFIG_SRC="${DIR}/fakeRouter-boot-config" &&
CONFIG_DST='/etc/network/if-up.d/fakeRouter-boot-config' &&
TMPFILE="$(mktemp)" &&
cp "${CONFIG_SRC}" "${TMPFILE}" &&
sed -i "s/@@@@@1@@@@@/${DEFAULT_ROUTE}/g" "${TMPFILE}" &&
sudo cp "${TMPFILE}" "${CONFIG_DST}" &&
sudo chown root:root "${CONFIG_DST}" &&
sudo chmod a=r "${CONFIG_DST}" &&
sudo chmod u+x "${CONFIG_DST}" &&
rm "${TMPFILE}"
