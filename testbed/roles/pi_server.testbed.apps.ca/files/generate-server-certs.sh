#!/bin/bash
# MANAGED BY ANSIBLE, CHANGES WILL BE OVERWRITTEN

set -eu

function usage() {
    echo "Usage: $(basename "${0}") ca_out [hostname ip]..."
    exit 1
}

test -z "${1:-}" && usage
CA_OUT="${1}"
shift

while (($#)); do
    test -z "${1:-}" && usage
    test -z "${2:-}" && usage
    HOST="${1}"
    IP="${2}"

    printf '%s\n%s.local\nfoobar\n' "${IP}" "${HOST}" | "${CA_OUT}/scripts/make-pi-server-certs"
    cd "${CA_OUT}/certs/server"
    cd "${IP}"__*

    cat >"${HOST}-server-certs" <<EOF
Section: misc
Priority: optional
Standards-Version: 3.9.2
Package: ${HOST}-server-certs
Version: 1
Files: ca.crt /etc/pi-server/certs/
 crl /etc/pi-server/certs/
 deployment-key /etc/pi-server/certs/
 deployment-key.pub /etc/pi-server/certs/
 https.crt /etc/pi-server/certs/
 https.key /etc/pi-server/certs/
 openvpn.crt /etc/pi-server/certs/
 openvpn-dh2048.pem /etc/pi-server/certs/
 openvpn.key /etc/pi-server/certs/
 openvpn-tls-auth.key /etc/pi-server/certs/
EOF

    equivs-build "${HOST}-server-certs"
    aptly repo add certs "${HOST}-server-certs_1_all.deb"
    cat 'deployment-key.pub' >>"${HOME}/.ssh/authorized_keys"

    printf '%s\nfoobar\nfoobar\nfoobar\n' "${HOST}-client" | "${CA_OUT}/scripts/make-client-cert"
    cd "${CA_OUT}/certs/client"
    cd "${HOST}-client"__*

    cp "${HOST}-client.crt" 'openvpn-server-to-server-client.crt'
    cp "${HOST}-client.key" 'openvpn-server-to-server-client.key'

    cat >"${HOST}-client-certs" <<EOF
Section: misc
Priority: optional
Standards-Version: 3.9.2
Package: ${HOST}-client-certs
Version: 1
Files: openvpn-server-to-server-client.crt /etc/pi-server/certs/
 openvpn-server-to-server-client.key /etc/pi-server/certs/
EOF

    equivs-build "${HOST}-client-certs"
    aptly repo add certs "${HOST}-client-certs_1_all.deb"

    cp "${HOST}-client.crt" 'openvpn-client.crt'
    cp "${HOST}-client.key" 'openvpn-client.key'

    cat >"${HOST}-single-machine-client-certs" <<EOF
Section: misc
Priority: optional
Standards-Version: 3.9.2
Package: ${HOST}-single-machine-client-certs
Version: 1
Files: openvpn-client.crt /etc/pi-server/certs/
 openvpn-client.key /etc/pi-server/certs/
EOF

    equivs-build "${HOST}-single-machine-client-certs"
    aptly repo add certs "${HOST}-single-machine-client-certs_1_all.deb"

    shift
    shift
done

aptly publish update certs
touch ~/certs-generated
