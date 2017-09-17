#!/bin/bash
# Don't run this manually, use the numbered setup script, which will
# pass the correct arguments

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )" &&
source "${DIR}/common.bash" &&


function fail() {
    echo "${@}"
    exit 1
}

function usage() {
    fail "Usage: $(basename "${0}") syncthing_user config_dir home_dir"
}

test -z "${1}" && usage
test -z "${2}" && usage
test -z "${3}" && usage
SYNCTHING_USER="${1}"
SYNCTHING_CONFIG_DIR="${2}"
SYNCTHING_HOME_DIR="${3}"


# Sanity check
if ! id -u "${1}" &>/dev/null; then
    fail "User '${SYNCTHING_USER}' does not exist"
fi

SYSTEMD_UNIT_FILE="/etc/systemd/system/${PI_SERVER_SYNCTHING_SERVICE}"
if [ -f "${SYSTEMD_UNIT_FILE}" ] &&
       ! grep "User=${SYNCTHING_USER}" "${SYSTEMD_UNIT_FILE}" &>/dev/null; then
    fail 'Syncthing is set up for a different user; not going any further'
fi


# Make sure the certificates are in place, and have the correct permissions
CERT_NAME='nginx'
check-pi-server-cert "Nginx" "${CERT_NAME}" &&
sudo chgrp "${PI_SERVER_HTTPS_KEY_GROUP}" "$(pi-server-key "${CERT_NAME}")" &&
sudo chmod g=r "$(pi-server-key "${CERT_NAME}")" &&
sudo usermod -a -G "${PI_SERVER_HTTPS_KEY_GROUP}" "${SYNCTHING_USER}" &&


# Install syncthing
curl -s 'https://syncthing.net/release-key.txt' | sudo apt-key add - &&
echo 'deb http://apt.syncthing.net/ syncthing release' | sudo tee /etc/apt/sources.list.d/syncthing-release.list >/dev/null &&
sudo apt-get update &&
sudo apt-get -y install syncthing &&


# Prepare directories
sudo mkdir -p "${SYNCTHING_CONFIG_DIR}" &&
sudo chown "${SYNCTHING_USER}:${SYNCTHING_USER}" "${SYNCTHING_CONFIG_DIR}" &&
sudo chmod o-rwx "${SYNCTHING_CONFIG_DIR}" || exit 1

function cert-link() {
    if ! sudo test -e "${2}"; then
        sudo ln -s "${1}" "${2}"
    fi
}

cert-link "$(pi-server-cert "${CERT_NAME}")" "${SYNCTHING_CONFIG_DIR}/https-cert.pem" &&
cert-link "$(pi-server-key "${CERT_NAME}")" "${SYNCTHING_CONFIG_DIR}/https-key.pem" &&


# Make it run at boot
install-systemd-service "${DIR}/${PI_SERVER_SYNCTHING_SERVICE}" \
                        "${PI_SERVER_SYNCTHING_BINARY}" \
                        "${SYNCTHING_CONFIG_DIR}" \
                        "${SYNCTHING_USER}" \
                        "${SYNCTHING_HOME_DIR}" &&
sudo systemctl enable "${PI_SERVER_SYNCTHING_SERVICE}" &&
sudo touch "${PI_SERVER_CRON_PAUSE_DIR}/${PI_SERVER_SYNCTHING_SERVICE}" &&


# Generate initial setup if necessary
if ! sudo test -e "${SYNCTHING_CONFIG_DIR}/config.xml"; then
    sudo -u "${SYNCTHING_USER}" "${PI_SERVER_SYNCTHING_BINARY}" "-generate=${SYNCTHING_CONFIG_DIR}" || exit 1
fi


# Webpage
DST="${PI_SERVER_WEB_PAGE_PARTS_DIR}/00-syncthing" &&
sed-install "${DIR}/webpage-template" "${DST}" &&
sudo chmod a=r "${DST}" &&

sudo "${PI_SERVER_WEB_PAGE_GENERATE}" &&


# Firewall
"${PI_SERVER_IPTABLES_PORT_SCRIPT}" open-at-boot 22000 tcp &&
"${PI_SERVER_IPTABLES_PORT_SCRIPT}" open-at-boot 21027 udp &&
"${PI_SERVER_IPTABLES_PORT_SCRIPT}" open-at-boot 8080 tcp &&
"${PI_SERVER_IPTABLES_PORT_SCRIPT}" open 22000 tcp &&
"${PI_SERVER_IPTABLES_PORT_SCRIPT}" open 21027 udp &&
"${PI_SERVER_IPTABLES_PORT_SCRIPT}" open 8080 tcp &&


# Cleanup
sudo systemctl restart "${PI_SERVER_SYNCTHING_SERVICE}" &&
echo 'About to display instructions' &&
enter-to-continue &&


less <<EOF
Syncthing should now be running on http://${PI_SERVER_IP}:8080 (might take a while to start up).

Configure settings as follows:

GUI Listen Address:
0.0.0.0:8080

Untick 'Enable NAT Traversal'
Untick 'Global Discovery'
Untick 'Start Browser'
Untick 'Enable Relaying'

Tick 'Use HTTPS for GUI', and fill in a username and password as desired.


Delete the default folder.


Restart syncthing.


You can then add folders as desired.
EOF
