import datetime
import os.path
from collections.abc import Mapping, Sequence
from typing import cast

from cryptography.x509 import load_pem_x509_certificate, load_pem_x509_crl
from cryptography.x509.extensions import BasicConstraints
from cryptography.x509.oid import ExtensionOID
from testinfra.host import Host


class TestCA:
    def test_ca(self, hosts: Mapping[str, Host]) -> None:
        host = hosts["internet"]
        test_root_dir = "/home/vagrant/ca-test"
        root_dir = os.path.join(test_root_dir, "ca")
        ca_dir = os.path.join(root_dir, "ca")
        clients_dir = os.path.join(root_dir, "certs/client")
        servers_dir = os.path.join(root_dir, "certs/server")
        scripts_dir = os.path.join(root_dir, "scripts")
        password = "foobar"
        openvpn_path = 'PATH="/usr/sbin:${PATH}"'
        today = datetime.datetime.today().date()
        one_hundred_years = today + datetime.timedelta(days=36500)

        def check_with_stdin(cmd: str, stdin: Sequence[str]) -> None:
            host.check_output("printf '%s\n' | %s" % ("\n".join(stdin), cmd))

        def matching_dir(dirs: Sequence[str], prefix: str) -> str:
            for d in dirs:
                if d.startswith(prefix):
                    return d
            raise ValueError(f"Can't find dir matching '{prefix}' in {dirs}")

        try:
            # Setup
            host.check_output(f"mkdir {test_root_dir}")
            check_with_stdin(
                f"{openvpn_path} /vagrant/ca/make-ca {root_dir} pi-server",
                [password, password, "", "", "Test CA"],
            )

            check_with_stdin(
                os.path.join(scripts_dir, "make-client-cert"), ["C1", password, password, password]
            )
            check_with_stdin(
                os.path.join(scripts_dir, "make-client-cert"), ["C2", password, password, password]
            )

            check_with_stdin(
                os.path.join(scripts_dir, "make-pi-server-certs"),
                ["192.168.0.1", "foo.local", password],
            )

            ca_cert = os.path.join(ca_dir, "ca.crt")
            crl_file = os.path.join(ca_dir, "crl")
            client_dirs = host.file(clients_dir).listdir()
            c1_cert = os.path.join(clients_dir, matching_dir(client_dirs, "C1"), "C1.crt")
            c2_cert = os.path.join(clients_dir, matching_dir(client_dirs, "C2"), "C2.crt")
            server_dir = os.path.join(
                servers_dir, matching_dir(host.file(servers_dir).listdir(), "192.168.0.1")
            )
            server_openvpn_cert = os.path.join(server_dir, "openvpn.crt")
            server_https_cert = os.path.join(server_dir, "https.crt")

            # Verify
            ca = load_pem_x509_certificate(host.file(ca_cert).content)
            assert ca.issuer.rfc4514_string() == "CN=Test CA,O=pi-server,C=GB"
            assert ca.subject.rfc4514_string() == "CN=Test CA,O=pi-server,C=GB"
            assert cast(
                BasicConstraints,
                ca.extensions.get_extension_for_oid(ExtensionOID.BASIC_CONSTRAINTS).value,
            ).ca
            assert ca.not_valid_before.date() == today
            assert ca.not_valid_after.date() == one_hundred_years

            crl = load_pem_x509_crl(host.file(crl_file).content)
            assert not list(crl)

            c1 = load_pem_x509_certificate(host.file(c1_cert).content)
            assert c1.issuer.rfc4514_string() == "CN=Test CA,O=pi-server,C=GB"
            assert c1.subject.rfc4514_string() == "CN=C1,O=pi-server,C=GB"
            assert not cast(
                BasicConstraints,
                c1.extensions.get_extension_for_oid(ExtensionOID.BASIC_CONSTRAINTS).value,
            ).ca
            assert c1.not_valid_before.date() == today
            assert c1.not_valid_after.date() == one_hundred_years

            c2 = load_pem_x509_certificate(host.file(c2_cert).content)
            assert c2.issuer.rfc4514_string() == "CN=Test CA,O=pi-server,C=GB"
            assert c2.subject.rfc4514_string() == "CN=C2,O=pi-server,C=GB"
            assert not cast(
                BasicConstraints,
                c2.extensions.get_extension_for_oid(ExtensionOID.BASIC_CONSTRAINTS).value,
            ).ca
            assert c2.not_valid_before.date() == today
            assert c2.not_valid_after.date() == one_hundred_years

            openvpn = load_pem_x509_certificate(host.file(server_openvpn_cert).content)
            assert openvpn.issuer.rfc4514_string() == "CN=Test CA,O=pi-server,C=GB"
            assert openvpn.subject.rfc4514_string() == "CN=192.168.0.1 OpenVPN,O=pi-server,C=GB"
            assert not cast(
                BasicConstraints,
                openvpn.extensions.get_extension_for_oid(ExtensionOID.BASIC_CONSTRAINTS).value,
            ).ca
            assert openvpn.not_valid_before.date() == today
            assert openvpn.not_valid_after.date() == one_hundred_years

            https = load_pem_x509_certificate(host.file(server_https_cert).content)
            assert https.issuer.rfc4514_string() == "CN=Test CA,O=pi-server,C=GB"
            assert https.subject.rfc4514_string() == "CN=192.168.0.1,O=pi-server,C=GB"
            assert not cast(
                BasicConstraints,
                https.extensions.get_extension_for_oid(ExtensionOID.BASIC_CONSTRAINTS).value,
            ).ca
            assert https.not_valid_before.date() == today
            assert https.not_valid_after.date() == one_hundred_years

            # Revoke
            path = os.path.join(scripts_dir, "revoke-cert")
            check_with_stdin(f"{path} {c2_cert}", [password, password])

            crl = load_pem_x509_crl(host.file(crl_file).content)
            assert len(crl) == 1
            assert crl.get_revoked_certificate_by_serial_number(1)

        finally:
            host.check_output(f"rm -r {test_root_dir}")
