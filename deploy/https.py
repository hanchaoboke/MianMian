"""Serve the built frontend and API through a persistent local HTTPS gateway."""
import argparse
import ipaddress
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / '.local' / 'https'
PUBLIC_CERT = ROOT / 'doc' / 'mianmian-local-ca.crt'
ADMIN_ADDRESS = '127.0.0.1:2020'
ADMIN = 'http://' + ADMIN_ADDRESS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'reload', 'stop', 'status'])
    parser.add_argument('--host', action='append', default=[], help='LAN IP; repeat for multiple interfaces')
    parser.add_argument('--port', type=int, default=8443)
    args = parser.parse_args()
    caddy = shutil.which('caddy')
    if not caddy:
        parser.error('Install Caddy first: https://caddyserver.com/docs/install (macOS: brew install caddy)')
    if args.action == 'stop':
        subprocess.run([caddy, 'stop', '--address', ADMIN_ADDRESS], check=True)
        return
    if args.action == 'status':
        try:
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(ADMIN + '/config/', timeout=3):
                print('HTTPS gateway is running; public CA:', PUBLIC_CERT)
        except (urllib.error.URLError, OSError):
            raise SystemExit('HTTPS gateway is not running')
        return
    if not 1024 <= args.port <= 65535:
        parser.error('--port must be between 1024 and 65535')
    if not args.host:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('192.0.2.1', 80))
            args.host = [sock.getsockname()[0]]
    try:
        hosts = list(dict.fromkeys(str(ipaddress.IPv4Address(host)) for host in args.host))
    except ipaddress.AddressValueError:
        parser.error('--host must be an IPv4 address')
    os.umask(0o077)
    public = RUNTIME / 'public'
    public.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'XDG_DATA_HOME': str(RUNTIME / 'data'), 'XDG_CONFIG_HOME': str(RUNTIME / 'config'),
           'MIANMIAN_HTTPS_SITES': ', '.join(f'https://{host}:{args.port}' for host in dict.fromkeys([*hosts, 'localhost', '127.0.0.1'])),
           'MIANMIAN_FRONTEND_DIR': str(ROOT / 'frontend' / 'dist'), 'MIANMIAN_CERT_EXPORT_DIR': str(public)}
    subprocess.run(['npm', 'run', 'build'], cwd=ROOT / 'frontend', check=True)
    config = str(ROOT / 'deploy' / 'Caddyfile.lan')
    subprocess.run([caddy, 'validate', '--config', config, '--adapter', 'caddyfile'], env=env, check=True)
    command = [caddy, args.action, '--config', config, '--adapter', 'caddyfile']
    if args.action == 'start':
        with (RUNTIME / 'gateway.log').open('ab') as log:
            subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=log, check=True, start_new_session=True)
    else:
        subprocess.run([*command, '--address', ADMIN_ADDRESS], cwd=ROOT, env=env, check=True)
    ca = RUNTIME / 'data' / 'caddy' / 'pki' / 'authorities' / 'local' / 'root.crt'
    for _ in range(50):
        if ca.is_file():
            break
        time.sleep(0.1)
    if not ca.is_file():
        raise SystemExit(f'CA not ready. See {RUNTIME / "gateway.log"}')
    shutil.copyfile(ca, public / 'mianmian-local-ca.crt')
    PUBLIC_CERT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ca, PUBLIC_CERT)
    print('Install this public CA in each client trusted root store:', PUBLIC_CERT)
    for host in hosts:
        print(f'Student: https://{host}:{args.port}/')
        print(f'Teacher: https://{host}:{args.port}/teacher/login')
    print('Backend must remain running on 127.0.0.1:8010. Logs:', RUNTIME / 'gateway.log')


if __name__ == '__main__':
    main()
