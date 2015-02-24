# Common stuff; should be sourced, not run!

source "$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )/../01-core/common.bash"

export PI_SERVER_SYNCTHING_BINARY="${PI_SERVER_DIR}/syncthing"
export PI_SERVER_SYNCTHING_ROOT="${PI_SERVER_DATA_MOUNT_DIR}/syncthing-main"
export PI_SERVER_SYNCTHING_CONFIG="${PI_SERVER_SYNCTHING_ROOT}/config"
export PI_SERVER_SYNCTHING_DATA="${PI_SERVER_SYNCTHING_ROOT}/data"
