# Sourced by the other firewall scripts

function valid-protocol()
{
    if [ "${1}" = 'tcp' ] || [ "${1}" = 'udp' ]; then
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
