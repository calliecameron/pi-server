# Common stuff; should be sourced, not run!

function get-pi-server-param()
{
    if [ ! -z "${1}" ] && [ -e "${1}" ]; then
        cat "${1}"
    else
        echo
    fi
}

export PI_SERVER_DIR='/etc/pi-server'
export PI_SERVER_DATA_MOUNT_DIR='/mnt/data'
export PI_SERVER_BACKUP_MOUNT_DIR='/mnt/backup'

export PI_SERVER_IP_FILE="${PI_SERVER_DIR}/lan-ip"
export PI_SERVER_IP="$(get-pi-server-param "${PI_SERVER_IP_FILE}")"

export PI_SERVER_LAN_NETWORK_FILE="${PI_SERVER_DIR}/lan-network-addr"
export PI_SERVER_LAN_NETWORK="$(get-pi-server-param "${PI_SERVER_LAN_NETWORK_FILE}")"

export PI_SERVER_VPN_NETWORK_FILE="${PI_SERVER_DIR}/vpn-network-addr"
export PI_SERVER_VPN_NETWORK="$(get-pi-server-param "${PI_SERVER_VPN_NETWORK_FILE}")"

export PI_SERVER_FQDN_FILE="${PI_SERVER_DIR}/fqdn"
export PI_SERVER_FQDN="$(get-pi-server-param "${PI_SERVER_FQDN_FILE}")"

export PI_SERVER_EMAIL_TARGET_FILE="${PI_SERVER_DIR}/email-target"
export PI_SERVER_EMAIL_TARGET="$(get-pi-server-param "${PI_SERVER_EMAIL_TARGET_FILE}")"

export PI_SERVER_EMAIL_SMTP_FILE="${PI_SERVER_DIR}/email-smtp-server"
export PI_SERVER_EMAIL_SMTP="$(get-pi-server-param "${PI_SERVER_EMAIL_SMTP_FILE}")"

export PI_SERVER_STORAGE_DRIVE_DEV_FILE="${PI_SERVER_DIR}/storage-drive-dev"
export PI_SERVER_STORAGE_DRIVE_DEV="$(get-pi-server-param "${PI_SERVER_STORAGE_DRIVE_DEV_FILE}")"

export PI_SERVER_STORAGE_DATA_PARTITION_FILE="${PI_SERVER_DIR}/storage-data-partition"
export PI_SERVER_STORAGE_DATA_PARTITION="$(get-pi-server-param "${PI_SERVER_STORAGE_DATA_PARTITION_FILE}")"

export PI_SERVER_STORAGE_BACKUP_PARTITION_FILE="${PI_SERVER_DIR}/storage-backup-partition"
export PI_SERVER_STORAGE_BACKUP_PARTITION="$(get-pi-server-param "${PI_SERVER_STORAGE_BACKUP_PARTITION_FILE}")"

export PI_SERVER_STORAGE_SPINNING_DRIVE_FILE="${PI_SERVER_DIR}/storage-spinning-disk"
export PI_SERVER_STORAGE_SPINNING_DRIVE="$(get-pi-server-param "${PI_SERVER_STORAGE_SPINNING_DRIVE_FILE}")"


export PI_SERVER_NOTIFICATION_EMAIL_SCRIPT="${PI_SERVER_DIR}/send-notification-email"
export PI_SERVER_SSH_LOGIN_EMAIL_SCRIPT="${PI_SERVER_DIR}/ssh-email-on-login"
export PI_SERVER_OPENVPN_LOGIN_EMAIL_SCRIPT="${PI_SERVER_DIR}/openvpn-email-on-login"

export PI_SERVER_IPTABLES_RULES="${PI_SERVER_DIR}/iptables-rules"
export PI_SERVER_IPTABLES_TCP_OPEN_BOOT="${PI_SERVER_DIR}/iptables-tcp-open-boot"
export PI_SERVER_IPTABLES_UDP_OPEN_BOOT="${PI_SERVER_DIR}/iptables-udp-open-boot"
export PI_SERVER_IPTABLES_OPEN_TCP_AT_BOOT_SCRIPT="${PI_SERVER_DIR}/open-tcp-port-at-boot"
export PI_SERVER_IPTABLES_OPEN_UDP_AT_BOOT_SCRIPT="${PI_SERVER_DIR}/open-udp-port-at-boot"
export PI_SERVER_IPTABLES_TCP_OPENS_AT_BOOT_SCRIPT="${PI_SERVER_DIR}/tcp-port-opens-at-boot"
export PI_SERVER_IPTABLES_UDP_OPENS_AT_BOOT_SCRIPT="${PI_SERVER_DIR}/udp-port-opens-at-boot"

export PI_SERVER_ZONEEDIT_USERNAME_FILE="${PI_SERVER_DIR}/zoneedit-username"
export PI_SERVER_ZONEEDIT_PASSWORD_FILE="${PI_SERVER_DIR}/zoneedit-password"
export PI_SERVER_ZONEEDIT_LOG_FILE="${PI_SERVER_DIR}/zoneedit-last-attempt.log"
export PI_SERVER_ZONEEDIT_CONFIG_SCRIPT="${PI_SERVER_DIR}/zoneedit-config"

export PI_SERVER_SHUTDOWND_SCRIPT="${PI_SERVER_DIR}/shutdownd"

export PI_SERVER_CA_CERT="${PI_SERVER_DIR}/ca.crt"
export PI_SERVER_CRL="${PI_SERVER_DIR}/crl"

export PI_SERVER_OPENVPN_DH_PARAMS="${PI_SERVER_DIR}/openvpn-dh2048.pem"
export PI_SERVER_OPENVPN_TLS_AUTH="${PI_SERVER_DIR}/openvpn-tls-auth.key"
export PI_SERVER_OPENVPN_SERVER_TO_SERVER_CONFIG="${PI_SERVER_DIR}/openvpn-server-to-server-clients"
export PI_SERVER_OPENVPN_CLIENT_CONFIG_DIR="${PI_SERVER_DIR}/openvpn-client-config.d"

function pi-server-cert()
{
    echo "${PI_SERVER_DIR}/${1}.crt"
}

function pi-server-key()
{
    echo "${PI_SERVER_DIR}/${1}.key"
}

function check-pi-server-cert()
{
    local NAME="${1}"
    local CERT="$(pi-server-cert "${2}")"
    local KEY="$(pi-server-key "${2}")"

    if [ ! -e "${PI_SERVER_CA_CERT}" ] ||
       [ ! -e "${PI_SERVER_CRL}" ] ||
       [ ! -e "${CERT}" ] ||
       [ ! -e "${KEY}" ]; then
        cat <<EOF
Certificates are missing; not going any further
Put the certificates at:
    CA ceritificate: ${PI_SERVER_CA_CERT}
    CRL: ${PI_SERVER_CRL}
    ${1} certificate: ${CERT}
    ${1} private key: ${KEY}
EOF
        exit 1
    else
        sudo chown root:root "${PI_SERVER_CA_CERT}" "${PI_SERVER_CRL}" "${CERT}" "${KEY}"
        sudo chmod u=r "${PI_SERVER_CA_CERT}" "${PI_SERVER_CRL}" "${CERT}" "${KEY}"
        sudo chmod go-rwx "${KEY}"
        sudo chmod go-wx "${PI_SERVER_CA_CERT}" "${PI_SERVER_CRL}" "${CERT}"
    fi

    # Check extra files
    shift
    shift

    while (($#)); do
        if [ ! -e "${1}" ]; then
            cat <<EOF
Missing file; not going any further:
    ${1}
EOF
            exit 1
        else
            sudo chown root:root "${1}"
            sudo chmod u=r "${1}"
            sudo chmod go-rwx "${1}"
        fi

        shift
    done
}

function real-pi()
{
    # Is this really a Pi, or is it a Debian VM for testing?
    if [ "$(uname -m)" = 'armv6l' ]; then
        return 0
    else
        return 1
    fi
}

function enter-to-continue()
{
    read -p "Press ENTER to continue..."
}

function sed-install()
{
    local IN_FILE="${1}"
    local OUT_FILE="${2}"
    local TMPFILE="$(mktemp)" &&
    cp "${IN_FILE}" "${TMPFILE}" &&
    shift &&
    shift &&

    local i='1'
    while (($#)); do
        sed -i "s|@@@@@${i}@@@@@|${1}|g" "${TMPFILE}"
        shift
        i=$(( i + 1 ))
    done

    sudo cp "${TMPFILE}" "${OUT_FILE}" &&
    sudo chown root:root "${OUT_FILE}" &&
    rm "${TMPFILE}"
}

function yn_y()
{
    # Y is the default
    local REPLY
    read -p "${1} [Y/n] " -r
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        return 1
    else
        return 0
    fi
}

function yn_n()
{
    # N is the default
    local REPLY
    read -p "${1} [y/N] " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        return 0
    else
        return 1
    fi
}

function get-new-password()
{
    local PASSWD_1
    local PASSWD_2

    read -s -p "Enter the ${1}: " PASSWD_1
    echo 1>&2
    if [ -z "${PASSWD_1}" ]; then
        echo 'Error: password must not be empty' 1>&2
        exit 1
    fi

    read -s -p 'Enter the new password again: ' PASSWD_2
    echo 1>&2
    if [ "${PASSWD_1}" != "${PASSWD_2}" ]; then
        echo 'Error: the passwords do not match' 1>&2
        exit 1
    fi

    echo "${PASSWD_1}"
}

function stop-web-services()
{
    sudo service nginx stop
    sudo service php5-fpm stop
    sudo service mysql stop
}

function start-web-services()
{
    sudo service mysql start
    sudo service php5-fpm start
    sudo service nginx start
}