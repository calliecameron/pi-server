# Common stuff; should be sourced, not run!

source "$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )/../01-generic-core/common.bash"

if ! grep jessie /etc/apt/sources.list &>/dev/null; then
    echo-red "This only works on Raspbian/Debian Jessie; you are not on this."
    exit 1
fi


