# Common stuff; should be sourced, not run!

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../01-generic-core/common.bash" || exit 1

if [ -z "${SKIP_OS_CHECK}" ]; then
    if ! grep focal /etc/apt/sources.list &>/dev/null; then
        echo-red "This only works on Ubuntu Focal; you are not on this."
        exit 1
    fi
fi

export PI_SERVER_LAN_NETWORK_FILE="${PI_SERVER_DIR}/lan-network-addr"
# shellcheck disable=SC2155
export PI_SERVER_LAN_NETWORK="$(get-pi-server-param "${PI_SERVER_LAN_NETWORK_FILE}")"

export PI_SERVER_VPN_NETWORK_FILE="${PI_SERVER_DIR}/vpn-network-addr"
# shellcheck disable=SC2155
export PI_SERVER_VPN_NETWORK="$(get-pi-server-param "${PI_SERVER_VPN_NETWORK_FILE}")"

export PI_SERVER_OPENVPN_DH_PARAMS="${PI_SERVER_CERT_DIR}/openvpn-dh2048.pem"
export PI_SERVER_OPENVPN_TLS_AUTH="${PI_SERVER_CERT_DIR}/openvpn-tls-auth.key"
export PI_SERVER_OPENVPN_SERVER_TO_SERVER_CONFIG="${PI_SERVER_DIR}/openvpn-server-to-server-clients"
export PI_SERVER_OPENVPN_CLIENT_CONFIG_DIR="${PI_SERVER_DIR}/openvpn-client-config.d"
export PI_SERVER_OPENVPN_NIGHTLY_CONFIG="${PI_SERVER_DIR}/openvpn-nightly-config"
export PI_SERVER_OPENVPN_NIGHTLY_LOG="${PI_SERVER_DIR}/openvpn-nightly.log"
export PI_SERVER_OPENVPN_NIGHTLY_SCRIPT="${PI_SERVER_DIR}/openvpn-nightly"
export PI_SERVER_OPENVPN_LOGIN_EMAIL_SCRIPT="${PI_SERVER_DIR}/openvpn-email-on-login"
