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
