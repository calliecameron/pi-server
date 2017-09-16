# Common stuff; should be sourced, not run!

source "$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )/../01-generic-core/common.bash" || exit 1

if ! grep stretch /etc/apt/sources.list &>/dev/null; then
    echo-red "This only works on Raspbian/Debian Stretch; you are not on this."
    exit 1
fi


# Stored data paths (on external drive)
export PI_SERVER_DATA_MOUNT_DIR='/mnt/data'
export PI_SERVER_DATA_DIR="${PI_SERVER_DATA_MOUNT_DIR}/pi-server-data"
export PI_SERVER_DATA_CONFIG_DIR="${PI_SERVER_DATA_DIR}/config"
export PI_SERVER_DATA_MAIN_DIR="${PI_SERVER_DATA_DIR}/data"
export PI_SERVER_DATA_NO_BACKUP_DIR="${PI_SERVER_DATA_DIR}/data-no-backups"
export PI_SERVER_SCRATCH_DIR="${PI_SERVER_DATA_MOUNT_DIR}/scratch"

export PI_SERVER_BACKUP_MOUNT_DIR='/mnt/backup'
export PI_SERVER_BACKUP_DIR="${PI_SERVER_BACKUP_MOUNT_DIR}/pi-server-backup"
export PI_SERVER_BACKUP_MAIN_DIR="${PI_SERVER_BACKUP_DIR}/main"
export PI_SERVER_BACKUP_GIT_DIR="${PI_SERVER_BACKUP_DIR}/git"
export PI_SERVER_BACKUP_EMAIL_DIR="${PI_SERVER_BACKUP_DIR}/email"


export PI_SERVER_LAN_NETWORK_FILE="${PI_SERVER_DIR}/lan-network-addr"
# shellcheck disable=SC2155
export PI_SERVER_LAN_NETWORK="$(get-pi-server-param "${PI_SERVER_LAN_NETWORK_FILE}")"

export PI_SERVER_VPN_NETWORK_FILE="${PI_SERVER_DIR}/vpn-network-addr"
# shellcheck disable=SC2155
export PI_SERVER_VPN_NETWORK="$(get-pi-server-param "${PI_SERVER_VPN_NETWORK_FILE}")"

export PI_SERVER_STORAGE_DRIVE_DEV_FILE="${PI_SERVER_DIR}/storage-drive-dev"
# shellcheck disable=SC2155
export PI_SERVER_STORAGE_DRIVE_DEV="$(get-pi-server-param "${PI_SERVER_STORAGE_DRIVE_DEV_FILE}")"

export PI_SERVER_STORAGE_DATA_PARTITION_FILE="${PI_SERVER_DIR}/storage-data-partition"
# shellcheck disable=SC2155
export PI_SERVER_STORAGE_DATA_PARTITION="$(get-pi-server-param "${PI_SERVER_STORAGE_DATA_PARTITION_FILE}")"

export PI_SERVER_STORAGE_BACKUP_PARTITION_FILE="${PI_SERVER_DIR}/storage-backup-partition"
# shellcheck disable=SC2155
export PI_SERVER_STORAGE_BACKUP_PARTITION="$(get-pi-server-param "${PI_SERVER_STORAGE_BACKUP_PARTITION_FILE}")"

export PI_SERVER_STORAGE_SPINNING_DRIVE_FILE="${PI_SERVER_DIR}/storage-spinning-disk"
# shellcheck disable=SC2155
export PI_SERVER_STORAGE_SPINNING_DRIVE="$(get-pi-server-param "${PI_SERVER_STORAGE_SPINNING_DRIVE_FILE}")"


export PI_SERVER_ZONEEDIT_DIR="${PI_SERVER_DIR}/zoneedit"
export PI_SERVER_ZONEEDIT_USERNAME_FILE="${PI_SERVER_ZONEEDIT_DIR}/zoneedit-username"
export PI_SERVER_ZONEEDIT_PASSWORD_FILE="${PI_SERVER_ZONEEDIT_DIR}/zoneedit-password"
export PI_SERVER_ZONEEDIT_LOG_FILE="${PI_SERVER_ZONEEDIT_DIR}/zoneedit-last-attempt.log"
export PI_SERVER_ZONEEDIT_CONFIG_SCRIPT="${PI_SERVER_ZONEEDIT_DIR}/zoneedit-config"
export PI_SERVER_ZONEEDIT_UPDATE_SCRIPT="${PI_SERVER_ZONEEDIT_DIR}/zoneedit-update"

export PI_SERVER_SHUTDOWND_SCRIPT="${PI_SERVER_DIR}/shutdownd"
export PI_SERVER_SHUTDOWND_SERVICE='pi-server-shutdownd.service'
export PI_SERVER_SHUTDOWND_PORT='23145'

export PI_SERVER_WEB_PAGE_DIR='/var/www/pi-server'
export PI_SERVER_WEB_PAGE_PARTS_DIR="${PI_SERVER_DIR}/web-page-parts"
export PI_SERVER_WEB_PAGE_HEADER="${PI_SERVER_DIR}/web-page-header"
export PI_SERVER_WEB_PAGE_FOOTER="${PI_SERVER_DIR}/web-page-footer"
export PI_SERVER_WEB_PAGE_MAIN_HEADER="${PI_SERVER_DIR}/main-page-header"
export PI_SERVER_WEB_PAGE_MAIN_FOOTER="${PI_SERVER_DIR}/main-page-footer"
export PI_SERVER_WEB_PAGE_GENERATE="${PI_SERVER_DIR}/generate-main-web-page"

export PI_SERVER_CERT_DIR="${PI_SERVER_DIR}/certs"
export PI_SERVER_CA_CERT="${PI_SERVER_CERT_DIR}/ca.crt"
export PI_SERVER_CRL="${PI_SERVER_CERT_DIR}/crl"
export PI_SERVER_HTTPS_KEY_GROUP='pi-server-https-key-readers'

export PI_SERVER_OPENVPN_DH_PARAMS="${PI_SERVER_CERT_DIR}/openvpn-dh2048.pem"
export PI_SERVER_OPENVPN_TLS_AUTH="${PI_SERVER_CERT_DIR}/openvpn-tls-auth.key"
export PI_SERVER_OPENVPN_SERVER_TO_SERVER_CONFIG="${PI_SERVER_DIR}/openvpn-server-to-server-clients"
export PI_SERVER_OPENVPN_CLIENT_CONFIG_DIR="${PI_SERVER_DIR}/openvpn-client-config.d"
export PI_SERVER_OPENVPN_NIGHTLY_CONFIG="${PI_SERVER_DIR}/openvpn-nightly-config"
export PI_SERVER_OPENVPN_NIGHTLY_LOG="${PI_SERVER_DIR}/openvpn-nightly.log"
export PI_SERVER_OPENVPN_LOGIN_EMAIL_SCRIPT="${PI_SERVER_DIR}/openvpn-email-on-login"

export PI_SERVER_BACKUP_SCRIPT_DIR="${PI_SERVER_DIR}/backup"
export PI_SERVER_BACKUP_LAST_RUN="${PI_SERVER_BACKUP_DIR}/last-run-date.txt"
# shellcheck disable=SC2155
export PI_SERVER_BACKUP_CONFIG_DIR="${PI_SERVER_DATA_MAIN_DIR}/$(hostname)-backup-config"
export PI_SERVER_BACKUP_GIT_CONFIG="${PI_SERVER_BACKUP_CONFIG_DIR}/git-backup-configuration.txt"
export PI_SERVER_BACKUP_GIT_SSH="${PI_SERVER_BACKUP_SCRIPT_DIR}/git-ssh"
export PI_SERVER_DEPLOYMENT_KEY="${PI_SERVER_CERT_DIR}/deployment-key"
export PI_SERVER_DEPLOYMENT_KEY_PUB="${PI_SERVER_CERT_DIR}/deployment-key.pub"


function pi-server-cert() {
    echo "${PI_SERVER_CERT_DIR}/${1}.crt"
}

function pi-server-key() {
    echo "${PI_SERVER_CERT_DIR}/${1}.key"
}

function check-pi-server-cert() {
    local NAME="${1}"
    # shellcheck disable=SC2155
    local CERT="$(pi-server-cert "${2}")"
    # shellcheck disable=SC2155
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
    ${NAME} certificate: ${CERT}
    ${NAME} private key: ${KEY}
EOF
        exit 1
    else
        sudo chown root:root "${PI_SERVER_CA_CERT}" "${PI_SERVER_CRL}" "${CERT}" "${KEY}" &&
        sudo chmod u=r "${PI_SERVER_CA_CERT}" "${CERT}" "${KEY}" &&
        sudo chmod go-rwx "${KEY}" &&
        sudo chmod go=r "${PI_SERVER_CA_CERT}" "${CERT}" &&

        # The CRL is not secret, and must be world-readable
        sudo chmod a=r "${PI_SERVER_CRL}" || return 1
    fi

    # Check extra files
    shift
    shift

    while (($#)); do
        local FILENAME="${1}"
        if [ ! -e "${FILENAME}" ]; then
            cat <<EOF
Missing file; not going any further:
    ${FILENAME}
EOF
            exit 1
        else
            sudo chown root:root "${FILENAME}" &&
            sudo chmod u=r "${FILENAME}" &&
            sudo chmod go-rwx "${FILENAME}" || return 1
        fi

        shift
    done

    # Install the CA cert for OS use
    sudo cp -t '/usr/local/share/ca-certificates' "${PI_SERVER_CA_CERT}" &&
    sudo update-ca-certificates || return 1
}
