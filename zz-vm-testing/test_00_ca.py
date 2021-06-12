from typing import Dict, List
import datetime
import os.path
from cryptography.x509 import load_pem_x509_certificate, load_pem_x509_crl
from cryptography.x509.oid import ExtensionOID
from testinfra.host import Host


class Test00CA:
    def test_00_ca(self, hosts: Dict[str, Host]) -> None:
        host = hosts['internet']
        test_root_dir = '/home/vagrant/ca-test'
        root_dir = os.path.join(test_root_dir, 'ca')
        ca_dir = os.path.join(root_dir, 'ca')
        clients_dir = os.path.join(root_dir, 'certs/client')
        servers_dir = os.path.join(root_dir, 'certs/server')
        scripts_dir = os.path.join(root_dir, 'scripts')
        password = 'foobar'
        openvpn_path = 'PATH="/usr/sbin:${PATH}"'
        today = datetime.datetime.today().date()
        ten_years = today + datetime.timedelta(days=3650)

        def check_with_stdin(cmd: str, stdin: List[str]) -> None:
            host.check_output("printf '%s\n' | %s" % ('\n'.join(stdin), cmd))

        def matching_dir(dirs: List[str], prefix: str) -> str:
            for d in dirs:
                if d.startswith(prefix):
                    return d
            raise ValueError("Can't find dir matching '%s' in %s" % (prefix, dirs))

        try:
            # Setup
            host.check_output('mkdir %s' % test_root_dir)
            check_with_stdin(
                '%s /vagrant/00-ca/00-make-ca %s pi-server' % (openvpn_path, root_dir),
                [password, password, '', '', 'Test CA'])

            check_with_stdin(
                os.path.join(scripts_dir, 'make-client-cert'),
                ['C1', password, password, password])
            check_with_stdin(
                os.path.join(scripts_dir, 'make-client-cert'),
                ['C2', password, password, password])

            check_with_stdin(
                os.path.join(scripts_dir, 'make-pi-server-certs'),
                ['192.168.0.1', 'foo.local', password])

            ca_cert = os.path.join(ca_dir, 'ca.crt')
            crl_file = os.path.join(ca_dir, 'crl')
            client_dirs = host.file(clients_dir).listdir()
            c1_cert = os.path.join(clients_dir, matching_dir(client_dirs, 'C1'), 'C1.crt')
            c2_cert = os.path.join(clients_dir, matching_dir(client_dirs, 'C2'), 'C2.crt')
            server_dir = os.path.join(
                servers_dir, matching_dir(host.file(servers_dir).listdir(), '192.168.0.1'))
            server_openvpn_cert = os.path.join(server_dir, 'openvpn.crt')
            server_nginx_cert = os.path.join(server_dir, 'nginx.crt')

            # Verify
            ca = load_pem_x509_certificate(host.file(ca_cert).content)
            assert ca.issuer.rfc4514_string() == 'CN=Test CA,O=pi-server,C=GB'
            assert ca.subject.rfc4514_string() == 'CN=Test CA,O=pi-server,C=GB'
            assert ca.extensions.get_extension_for_oid(ExtensionOID.BASIC_CONSTRAINTS).value.ca
            assert ca.not_valid_before.date() == today
            assert ca.not_valid_after.date() == ten_years

            crl = load_pem_x509_crl(host.file(crl_file).content)
            assert not list(crl)

            c1 = load_pem_x509_certificate(host.file(c1_cert).content)
            assert c1.issuer.rfc4514_string() == 'CN=Test CA,O=pi-server,C=GB'
            assert c1.subject.rfc4514_string() == 'CN=C1,O=pi-server,C=GB'
            assert not c1.extensions.get_extension_for_oid(ExtensionOID.BASIC_CONSTRAINTS).value.ca
            assert c1.not_valid_before.date() == today
            assert c1.not_valid_after.date() == ten_years

            c2 = load_pem_x509_certificate(host.file(c2_cert).content)
            assert c2.issuer.rfc4514_string() == 'CN=Test CA,O=pi-server,C=GB'
            assert c2.subject.rfc4514_string() == 'CN=C2,O=pi-server,C=GB'
            assert not c2.extensions.get_extension_for_oid(ExtensionOID.BASIC_CONSTRAINTS).value.ca
            assert c2.not_valid_before.date() == today
            assert c2.not_valid_after.date() == ten_years

            openvpn = load_pem_x509_certificate(host.file(server_openvpn_cert).content)
            assert openvpn.issuer.rfc4514_string() == 'CN=Test CA,O=pi-server,C=GB'
            assert (openvpn.subject.rfc4514_string() ==
                    'CN=192.168.0.1 OpenVPN,O=pi-server,C=GB')
            assert not openvpn.extensions.get_extension_for_oid(
                ExtensionOID.BASIC_CONSTRAINTS).value.ca
            assert openvpn.not_valid_before.date() == today
            assert openvpn.not_valid_after.date() == ten_years

            nginx = load_pem_x509_certificate(host.file(server_nginx_cert).content)
            assert nginx.issuer.rfc4514_string() == 'CN=Test CA,O=pi-server,C=GB'
            assert (nginx.subject.rfc4514_string() ==
                    'CN=192.168.0.1,O=pi-server,C=GB')
            assert not nginx.extensions.get_extension_for_oid(
                ExtensionOID.BASIC_CONSTRAINTS).value.ca
            assert nginx.not_valid_before.date() == today
            assert nginx.not_valid_after.date() == ten_years

            # Revoke
            check_with_stdin(
                '%s %s' % (os.path.join(scripts_dir, 'revoke-cert'), c2_cert),
                [password, password])

            crl = load_pem_x509_crl(host.file(crl_file).content)
            assert len(crl) == 1
            assert crl.get_revoked_certificate_by_serial_number(1)

        finally:
            host.check_output('rm -r %s' % test_root_dir)
