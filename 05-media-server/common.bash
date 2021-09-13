# Common stuff; should be sourced, not run!

source "$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )/../02-pi-core/common.bash" || exit 1

export PI_SERVER_MEDIA_DIR="${PI_SERVER_DATA_DIR}/media-server"
export PI_SERVER_MEDIA_CONFIG_DIR="${PI_SERVER_DATA_CONFIG_DIR}/media-server"

export PI_SERVER_MINIDLNA_CONFIG_DIR="${PI_SERVER_MEDIA_CONFIG_DIR}/minidlna"
export PI_SERVER_MINIDLNA_DB="${PI_SERVER_MINIDLNA_CONFIG_DIR}/db"
