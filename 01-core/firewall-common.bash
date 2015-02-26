# Sourced by the other firewall scripts

DEFAULT_PROTOCOL='tcp'

function valid-protocol()
{
    if [ "${1}" = 'tcp'] || [ "${1}" = 'udp' ]; then
        return 0
    else
        return 1
    fi
}

function valid-port()
{
    if [ ! -z "${1}" ]; then
        if [[ "${1}" != *[!0-9]* ]]; then
            if (( "${1}" >= 0 && "${1}" <= 65535 )); then
                return 0
            fi
        fi
    fi
    return 1
}

function open-at-boot-file()
{
    if [ "${1}" = 'tcp' ]; then
        echo '@@@@@1@@@@@'
    elif [ "${1}" = 'udp' ]; then
        echo '@@@@@2@@@@@'
    fi
}

function usage()
{
    echo "Usage: $(basename "${0}") ${COMMANDS} port [protocol=tcp|udp]"
    echo "    protocol defaults to ${DEFAULT_PROTOCOL}"
    exit 1
}

function valid-command()
{
    local CHECK="${1}"
    if sed 's/|/\n/g' <(echo "${COMMANDS}") | grep "^${CHECK}\$" &>/dev/null; then
        return 0
    else
        return 1
    fi
}

function process-args()
{
    # These are deliberately globals
    COMMAND="${1}"
    test -z "${COMMAND}" && usage
    valid-command "${COMMAND}" || usage

    PORT="${2}"
    test -z "${PORT}" && usage
    valid-port "${PORT}" || usage

    PROTOCOL="${3}"
    if [ -z "${PROTOCOL}" ]; then
        PROTOCOL="${DEFAULT_PROTOCOL}"
    fi
    valid-protocol "${PROTOCOL}" || usage

    BOOTFILE="$(open-at-boot-file "${PROTOCOL}")"

    "${COMMAND}"
}
