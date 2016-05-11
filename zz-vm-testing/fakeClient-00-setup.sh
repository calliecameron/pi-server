#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

sudo apt-get update &&
sudo apt-get -y upgrade &&
sudo apt-get -y dist-upgrade &&
sudo apt-get -y install curl openssh-server openvpn &&

curl -s https://syncthing.net/release-key.txt | sudo apt-key add - &&
echo deb http://apt.syncthing.net/ syncthing release | sudo tee /etc/apt/sources.list.d/syncthing-release.list &&
sudo apt-get update &&
sudo apt-get -y install syncthing syncthing-gtk &&

echo &&
printf "Enter the address of the default route (corresponding FakeRouter): " &&
read -r DEFAULT_ROUTE &&

CONFIG_SRC="${DIR}/fakeClient-boot-config" &&
CONFIG_DST='/etc/network/if-up.d/fakeClient-boot-config' &&
TMPFILE="$(mktemp)" &&
cp "${CONFIG_SRC}" "${TMPFILE}" &&
sed -i "s/@@@@@1@@@@@/${DEFAULT_ROUTE}/g" "${TMPFILE}" &&
sudo cp "${TMPFILE}" "${CONFIG_DST}" &&
sudo chown root:root "${CONFIG_DST}" &&
sudo chmod a=r "${CONFIG_DST}" &&
sudo chmod u+x "${CONFIG_DST}" &&
rm "${TMPFILE}"
