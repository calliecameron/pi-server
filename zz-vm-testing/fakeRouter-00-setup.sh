#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "${DIR}/../01-generic-core/common.bash" || exit 1

function usage() {
    echo "Usage: $(basename "${0}") internet_iface lan_iface"
    exit 1
}

test -z "${1}" && usage
test -z "${2}" && usage

INTERNET_IFACE="${1}"
LAN_IFACE="${2}"

sudo apt-get update &&
sudo apt-get -y upgrade &&
sudo apt-get -y dist-upgrade

if ! grep "${LAN_IFACE}" /etc/network/interfaces &>/dev/null; then
    sudo tee -a /etc/network/interfaces &>/dev/null <<EOF

# The fake LAN
allow-hotplug ${LAN_IFACE}
iface ${LAN_IFACE} inet dhcp
EOF

fi


read -r -p "Enter the address of the default route (FakeInternet): " DEFAULT_ROUTE &&
read -r -p "Enter the LAN address of this router's FakePi (for port forwarding): " FAKE_PI &&
read -r -p "Enter the FakePi's VPN network address, without the '/24': " PI_VPN_NET &&

CONFIG_SRC="${DIR}/fakeRouter-boot-config" &&
CONFIG_DST='/etc/network/if-up.d/fakeRouter-boot-config' &&
sed-install "${CONFIG_SRC}" "${CONFIG_DST}" \
            "${DEFAULT_ROUTE}" \
            "${FAKE_PI}" \
            "${PI_VPN_NET}" \
            "${INTERNET_IFACE}" \
            "${LAN_IFACE}" &&
sudo chmod a=r "${CONFIG_DST}" &&
sudo chmod u+x "${CONFIG_DST}"
