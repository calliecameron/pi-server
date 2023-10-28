#!/bin/bash
# MANAGED BY ANSIBLE, CHANGES WILL BE OVERWRITTEN

REPO_ROOT="${HOME}/git"
FOO="${REPO_ROOT}/foo"
BAR="${REPO_ROOT}/bar"
TEMP="${REPO_ROOT}/temp"

git config --global user.name foo
git config --global user.email foo@testbed

function setup-repo() {
    REPO="${1}"
    mkdir -p "${REPO}" &&
        cd "${REPO}" &&
        git init --bare &&
        cd "${REPO_ROOT}" &&
        git clone "${REPO}" "${TEMP}" &&
        cd "${TEMP}" &&
        touch foo &&
        git add foo &&
        git commit -m 'Initial commit.' &&
        git push &&
        cd "${REPO_ROOT}" &&
        rm -rf "${TEMP}"
}

setup-repo "${FOO}" &&
    setup-repo "${BAR}"
