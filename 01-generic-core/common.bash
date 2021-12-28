# Common stuff; should be sourced, not run!

# Stop the user's umask messing up permissions on new files
umask 022

function echo-colour() {
    echo -e "\e[${1}m${2}\e[0m"
}

function echo-red() {
    echo-colour '31' "${1}"
}

function echo-green() {
    echo-colour '32' "${1}"
}

function echo-yellow() {
    echo-colour '33' "${1}"
}

function echo-blue() {
    echo-colour '34' "${1}"
}

# Make sure we are on a supported OS
if [ -z "${SKIP_OS_CHECK}" ]; then
    if ! grep focal /etc/apt/sources.list &>/dev/null; then
        echo-red "This only works on Ubuntu Focal; you are not on this."
        exit 1
    fi
fi

function on-pi() {
    # Are we on a Pi, or is this some other server?
    type raspi-config &>/dev/null
}

function yn-y() {
    # Y is the default
    local REPLY
    read -p "${1} [Y/n] " -r
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        return 1
    else
        return 0
    fi
}

function yn-n() {
    # N is the default
    local REPLY
    read -p "${1} [y/N] " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        return 0
    else
        return 1
    fi
}

function enter-to-continue() {
    read -r -p "Press ENTER to continue..."
}

function get-new-password() {
    local PASSWD_1
    local PASSWD_2

    read -r -s -p "Enter the ${1}: " PASSWD_1
    echo 1>&2
    if [ -z "${PASSWD_1}" ]; then
        echo 'Error: password must not be empty' 1>&2
        exit 1
    fi

    read -r -s -p 'Enter the new password again: ' PASSWD_2
    echo 1>&2
    if [ "${PASSWD_1}" != "${PASSWD_2}" ]; then
        echo 'Error: the passwords do not match' 1>&2
        exit 1
    fi

    echo "${PASSWD_1}"
}

function sed-install() {
    local IN_FILE="${1}"
    local OUT_FILE="${2}"
    # shellcheck disable=SC2155
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

function install-systemd-service() {
    local IN_FILE="${1}"
    # shellcheck disable=SC2155
    local OUT_FILE="/etc/systemd/system/$(basename "${IN_FILE}")" &&
    sed-install "${IN_FILE}" "${OUT_FILE}" "${@:2}" &&
    sudo chmod a=r "${OUT_FILE}" &&
    sudo systemctl daemon-reload
}

function get-pi-server-param() {
    if [ -n "${1}" ] && [ -e "${1}" ]; then
        cat "${1}"
    else
        echo
    fi
}

function set-pi-server-param() {
    local OUTPUT_FILE="${1}"
    local PROMPT="${2}"

    if [ -z "${OUTPUT_FILE}" ] || [ -z "${PROMPT}" ]; then
        echo "Bad input to set-pi-server-param"
        exit 1
    fi

    # shellcheck disable=SC2155
    local CURRENT_VALUE="$(get-pi-server-param "${OUTPUT_FILE}")"
    if [ -n "${CURRENT_VALUE}" ]; then
        CURRENT_VALUE=" [Current value: ${CURRENT_VALUE}]"
    fi

    read -r -p "${PROMPT}${CURRENT_VALUE}: " VALUE
    echo

    if [ -z "${VALUE}" ]; then
        echo "Error: ${OUTPUT_FILE} must have a valid value"
        exit 1
    fi

    if [ ! -e "${PI_SERVER_DIR}" ]; then
        sudo mkdir -p "${PI_SERVER_DIR}"
        sudo chown root:root "${PI_SERVER_DIR}"
        sudo chmod u=rwx "${PI_SERVER_DIR}"
        sudo chmod go-w "${PI_SERVER_DIR}"
    fi

    echo "${VALUE}" | sudo tee "${OUTPUT_FILE}" &>/dev/null
    sudo chown root:root "${OUTPUT_FILE}"
    sudo chmod u=rw "${OUTPUT_FILE}"
    sudo chmod go=r "${OUTPUT_FILE}"
}


export PI_SERVER_DIR='/etc/pi-server' # pi_server_etc


export PI_SERVER_IP_FILE="${PI_SERVER_DIR}/lan-ip"
# shellcheck disable=SC2155
export PI_SERVER_IP="$(get-pi-server-param "${PI_SERVER_IP_FILE}")"

export PI_SERVER_LAN_IFACE_FILE="${PI_SERVER_DIR}/lan-iface"
# shellcheck disable=SC2155
export PI_SERVER_LAN_IFACE="$(get-pi-server-param "${PI_SERVER_LAN_IFACE_FILE}")"

export PI_SERVER_FQDN_FILE="${PI_SERVER_DIR}/fqdn"
# shellcheck disable=SC2155
export PI_SERVER_FQDN="$(get-pi-server-param "${PI_SERVER_FQDN_FILE}")"

export PI_SERVER_NET_UP_SCRIPTS='/etc/networkd-dispatcher/routable.d' # pi_server_net_up
export PI_SERVER_NET_PRE_UP_SCRIPTS='/etc/networkd-dispatcher/routable.d' # pi_server_net_pre_up

export PI_SERVER_NOTIFICATION_EMAIL_SCRIPT="${PI_SERVER_DIR}/email/send-email" # pi_server_apps_email_script

export PI_SERVER_DISK_USAGE_SCRIPT="${PI_SERVER_DIR}/check-disk-usage"
