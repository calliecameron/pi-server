LAST_RUN_FILE='@@@@@1@@@@@'
DATA_DIR='@@@@@2@@@@@'
BACKUP_PARTITION='@@@@@3@@@@@'
GIT_BACKUP_CONFIG='@@@@@4@@@@@'
GIT_DIR='@@@@@5@@@@@'
GIT_SSH_SCRIPT='@@@@@6@@@@@'


function _extra-cleanup() {
    sync
    if mount | grep "${BACKUP_PARTITION}" &>/dev/null; then
        umount "${BACKUP_PARTITION}"
    fi
}


if [ ! -e "${DATA_DIR}" ]; then
    fail 'Data directory does not exist.'
fi

if ! mount | grep "${BACKUP_PARTITION}" &>/dev/null; then
    if ! mount "${BACKUP_PARTITION}" &>/dev/null; then
        fail 'Cannot mount backup partition.'
    fi
fi


# Main backup
TODAY="$(date '+%Y-%m-%d')" &&
DAY_OF_WEEK="$(date '+%u')" &&
# shellcheck disable=SC2015
DAY_OF_MONTH="$(date '+%d')" || fail 'Something went wrong.'

if [ ! -e "${LAST_RUN_FILE}" ] || [ "${TODAY}" != "$(cat "${LAST_RUN_FILE}")" ]; then
    echo "${TODAY}" > "${LAST_RUN_FILE}" &&

    # shellcheck disable=SC2015
    rsnapshot daily &>> "${LOG}" || fail 'Daily backup failed.'
    echo 'Daily backup succeeded.' >> "${LOG}"

    if [ "${DAY_OF_WEEK}" == '1' ]; then
        rsnapshot weekly &>> "${LOG}" || fail 'Weekly backup failed.'
        echo 'Weekly backup succeeded.' >> "${LOG}"
    fi

    if [ "${DAY_OF_MONTH}" == '1' ]; then
        rsnapshot monthly &>> "${LOG}" || fail 'Monthly backup failed.'
        echo 'Monthly backup succeeded.' >> "${LOG}"
    fi

    sync
else
    echo 'Already backed up today; nothing to do for main backup.' >> "${LOG}"
fi


# Git backup
echo "Git backup started at $(date)" >> "${LOG}" &&

if [ -f "${GIT_BACKUP_CONFIG}" ]; then
    while read -r line; do
        if [ ! -z "${line}" ]; then
            REPO_PATH="${GIT_DIR}/$(basename "${line}" '.git')"
            if [ ! -e "${REPO_PATH}" ]; then
                echo "Cloning to ${REPO_PATH}..." >> "${LOG}"
                cd / &&
                # shellcheck disable=SC2015
                su -s /bin/bash -c "export GIT_SSH='${GIT_SSH_SCRIPT}' && git clone --mirror '${line}' '${REPO_PATH}'" www-data &>> "${LOG}" || fail 'Cloning a repository failed.'
                echo "Cloned to ${REPO_PATH}." >> "${LOG}"
            else
                echo "Updating ${REPO_PATH}..." >> "${LOG}"
                cd / &&
                # shellcheck disable=SC2015
                su -s /bin/bash -c "export GIT_SSH='${GIT_SSH_SCRIPT}' && cd '${REPO_PATH}' && git fetch --all && git fetch --all --tags" www-data &>> "${LOG}" || fail 'Fetching a repository failed.'
                echo "Updated ${REPO_PATH}." >> "${LOG}"
            fi
        fi
    done < "${GIT_BACKUP_CONFIG}"
fi


_extra-cleanup

unset LAST_RUN_FILE DATA_DIR BACKUP_PARTITION GIT_BACKUP_CONFIG GIT_DIR GIT_SSH_SCRIPT
unset -f _extra-cleanup
