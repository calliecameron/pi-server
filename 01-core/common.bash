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

export PI_SERVER_IP_FILE="${PI_SERVER_DIR}/lan-ip"
export PI_SERVER_IP="$(get-pi-server-param "${PI_SERVER_IP_FILE}")"

export PI_SERVER_FQDN_FILE="${PI_SERVER_DIR}/fqdn"
export PI_SERVER_FQDN="$(get-pi-server-param "${PI_SERVER_FQDN_FILE}")"

export PI_SERVER_EMAIL_TARGET_FILE="${PI_SERVER_DIR}/email-target"
export PI_SERVER_EMAIL_TARGET="$(get-pi-server-param "${PI_SERVER_EMAIL_TARGET_FILE}")"

export PI_SERVER_EMAIL_SMTP_FILE="${PI_SERVER_DIR}/email-smtp-server"
export PI_SERVER_EMAIL_SMTP="$(get-pi-server-param "${PI_SERVER_EMAIL_SMTP_FILE}")"


export PI_SERVER_NOTIFICATION_EMAIL_SCRIPT="${PI_SERVER_DIR}/send-notification-email"
export PI_SERVER_SSH_LOGIN_EMAIL_SCRIPT="${PI_SERVER_DIR}/ssh-email-on-login"

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
