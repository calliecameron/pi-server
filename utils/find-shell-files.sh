#!/bin/bash

set -eu

git ls-files | LC_ALL=C sort | while read -r line; do
    # TODO lint jinja files too
    if [[ "${line}" != *'.j2' ]]; then
        HEAD="$(head -n 1 "${line}" | tr '\0' '0')"
        if [[ "${line}" == *'.sh' ]] || [[ "${line}" == *'.bash' ]] ||
            [ "${HEAD}" = '#!/bin/sh' ] || [ "${HEAD}" = '#!/bin/bash' ]; then
            echo "${line}"
        fi
    fi
done
