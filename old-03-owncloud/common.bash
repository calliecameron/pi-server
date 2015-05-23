# Common stuff; should be sourced, not run!

source "$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )/../01-core/common.bash"

export PI_SERVER_OWNCLOUD_DATA_PATH="${PI_SERVER_DATA_MOUNT_DIR}/owncloud-main"
export PI_SERVER_OWNCLOUD_DB='owncloud'
export PI_SERVER_OWNCLOUD_DB_USER='ownclouduser'
