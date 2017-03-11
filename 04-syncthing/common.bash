# Common stuff; should be sourced, not run!

source "$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )/../02-pi-core/common.bash"

export PI_SERVER_SYNCTHING_BINARY='/usr/bin/syncthing'
export PI_SERVER_SYNCTHING_CONFIG="${PI_SERVER_DATA_CONFIG_DIR}/syncthing"
