#!/bin/bash

# TODO setup in vagrant
exit 0

# We're running this on Mint, so don't check the OS
export SKIP_OS_CHECK='t'

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "${DIR}/../01-generic-core/common.bash" || exit 1

function usage() {
    echo "Usage: $(basename "${0}") lan_iface"
    exit 1
}

test -z "${1}" && usage

LAN_IFACE="${1}"

sudo apt-get update &&
sudo apt-get -y upgrade &&
sudo apt-get -y dist-upgrade &&
sudo apt-get -y install curl openssh-server openvpn &&

curl -s https://syncthing.net/release-key.txt | sudo apt-key add - &&
echo deb http://apt.syncthing.net/ syncthing release | sudo tee /etc/apt/sources.list.d/syncthing-release.list &&
sudo add-apt-repository -y ppa:nilarimogard/webupd8 &&
sudo apt-get update &&
sudo apt-get -y install syncthing syncthing-gtk &&

read -r -p "Enter the address of the default route (corresponding FakeRouter): " DEFAULT_ROUTE &&

CONFIG_SRC="${DIR}/fakeClient-boot-config" &&
CONFIG_DST='/etc/network/if-up.d/fakeClient-boot-config' &&
sed-install "${CONFIG_SRC}" "${CONFIG_DST}" \
            "${DEFAULT_ROUTE}" \
            "${LAN_IFACE}" &&
sudo chmod a=r "${CONFIG_DST}" &&
sudo chmod u+x "${CONFIG_DST}"
