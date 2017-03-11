# Common stuff; should be sourced, not run!

source "$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )/../02-pi-core/common.bash"

export PI_SERVER_MEDIA_SCRIPT_DIR="${PI_SERVER_DIR}/media-server"
export PI_SERVER_PODCAST_MANAGER_SCRIPT="${PI_SERVER_MEDIA_SCRIPT_DIR}/podcast-manager"
export PI_SERVER_MASHPODDER_SCRIPT="${PI_SERVER_MEDIA_SCRIPT_DIR}/mashpodder.sh"
export PI_SERVER_PODCAST_DOWNLOAD_SCRIPT="${PI_SERVER_MEDIA_SCRIPT_DIR}/download-podcasts"
export PI_SERVER_PODCAST_DOWNLOAD_SUMMARY="${PI_SERVER_MEDIA_SCRIPT_DIR}/summarise-downloaded-podcasts"

export PI_SERVER_MEDIA_DIR="${PI_SERVER_DATA_DIR}/media-server"
export PI_SERVER_PODCASTS="${PI_SERVER_MEDIA_DIR}/Podcasts - New"
export PI_SERVER_PODCASTS_LISTENED="${PI_SERVER_MEDIA_DIR}/Podcasts - Listened"

export PI_SERVER_MEDIA_CONFIG_DIR="${PI_SERVER_DATA_CONFIG_DIR}/media-server"

export PI_SERVER_MINIDLNA_CONFIG_DIR="${PI_SERVER_MEDIA_CONFIG_DIR}/minidlna"
export PI_SERVER_MINIDLNA_DB="${PI_SERVER_MINIDLNA_CONFIG_DIR}/db"

# shellcheck disable=SC2155
export PI_SERVER_MASHPODDER_CONFIG_DIR="${PI_SERVER_DATA_MAIN_DIR}/$(hostname)-podcasts-config"
export PI_SERVER_MASHPODDER_RSS_FILE="${PI_SERVER_MASHPODDER_CONFIG_DIR}/configuration.txt"
export PI_SERVER_MASHPODDER_ROOT="${PI_SERVER_MEDIA_CONFIG_DIR}/mashpodder"
export PI_SERVER_MASHPODDER_TMP_DIR="${PI_SERVER_MASHPODDER_ROOT}/tmp"
export PI_SERVER_MASHPODDER_DOWNLOAD_LOG="${PI_SERVER_MASHPODDER_ROOT}/daily-download.log"
export PI_SERVER_MASHPODDER_DOWNLOAD_COUNT="${PI_SERVER_MASHPODDER_ROOT}/last-download-count.txt"
export PI_SERVER_MASHPODDER_LOCK='/run/lock/pi-server-podcasts.lock'
