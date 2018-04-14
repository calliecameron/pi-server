function first-time() {
    mkdir /tmp/testbed-setup-done &> /dev/null
}

function with-lock() {
    local MUTEX
    local LOG
    MUTEX='/tmp/testbed-setup-mutex'
    LOG='/tmp/testbed-setup-log'
    while ! mkdir "${MUTEX}" &>/dev/null; do
        sleep 0.1
    done
    echo STARTING >> "${LOG}"
    "${1}" 2>&1 | tee -a "${LOG}"
    echo DONE >> "${LOG}"
    echo >> "${LOG}"
    rmdir "${MUTEX}" &>/dev/null
}
