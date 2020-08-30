#!/bin/bash -e
# This is a horrible hack, but the only reliable way I can get debconf values
# to change. Call as:
#   EDITOR=debconf_edit.sh DEBIAN_FRONTEND=editor dpkg-reconfigure <package>

OUTFILE="${1}"
TMPFILE="$(mktemp)"

function setvar() {
    sed "s|${1}="'".*'"|${1}="'"'"${2}"'"|g' "${OUTFILE}" > "${TMPFILE}"
    cp "${TMPFILE}" "${OUTFILE}"
}

setvar 'locales/locales_to_be_generated' 'en_GB.UTF-8 UTF-8'
setvar 'locales/default_environment_locale' 'en_GB.UTF-8'
