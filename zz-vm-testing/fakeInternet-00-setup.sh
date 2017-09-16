#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "${DIR}/../01-generic-core/common.bash" || exit 1

function usage() {
    echo "Usage: $(basename "${0}") real_internet_iface fake_internet_iface"
    exit 1
}

test -z "${1}" && usage
test -z "${2}" && usage

REAL_IFACE="${1}"
FAKE_IFACE="${2}"

sudo apt-get update &&
sudo apt-get -y upgrade &&
sudo apt-get -y dist-upgrade

if ! grep "${FAKE_IFACE}" /etc/network/interfaces &>/dev/null; then
    sudo tee -a /etc/network/interfaces &>/dev/null <<EOF

# The fake internet
allow-hotplug ${FAKE_IFACE}
iface ${FAKE_IFACE} inet dhcp
EOF

fi


DST='/etc/network/if-up.d/fakeInternet-boot-config'
sed-install "${DIR}/fakeInternet-boot-config" "${DST}" \
            "${REAL_IFACE}" \
            "${FAKE_IFACE=}" &&
sudo chmod a=r "${DST}" &&
sudo chmod u+x "${DST}"
