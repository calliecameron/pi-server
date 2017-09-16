#!/bin/bash

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
sudo apt-get -y dist-upgrade


read -r -p "Enter the address of the default route (corresponding FakeRouter): " DEFAULT_ROUTE &&

CONFIG_SRC="${DIR}/fakePi-boot-config" &&
CONFIG_DST='/etc/network/if-up.d/fakePi-boot-config' &&
sed-install "${CONFIG_SRC}" "${CONFIG_DST}" \
            "${DEFAULT_ROUTE}" \
            "${LAN_IFACE}" &&
sudo chmod a=r "${CONFIG_DST}" &&
sudo chmod u+x "${CONFIG_DST}"

echo "${DEFAULT_ROUTE}" | sudo tee '/fakepi-default-route' &>/dev/null
