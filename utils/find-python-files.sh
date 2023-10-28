#!/bin/bash

set -eu

git ls-files | LC_ALL=C sort | while read -r line; do
    HEAD="$(head -n 1 "${line}" | tr '\0' '0')"
    if [[ "${line}" == *'.py' ]] || [[ "${line}" == *'.pyi' ]] ||
        [ "${HEAD}" = '#!/usr/bin/env python3' ]; then
        echo "${line}"
    fi
done
