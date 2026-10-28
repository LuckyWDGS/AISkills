#!/usr/bin/env python3
"""Check an explicit local HTTP proxy. Does not prove physical, DNS, or TUN paths."""
import argparse
import ipaddress
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


def validate_url(value, *, proxy=False):
    try:
        url = urlsplit(value)
        port = url.port
        if url.scheme not in (('http',) if proxy else ('http', 'https')):
            raise ValueError
        if not url.hostname or url.username is not None or url.password is not None:
            raise ValueError
        if url.fragment:
            raise ValueError
        if proxy:
            if not ipaddress.ip_address(url.hostname).is_loopback or not port:
                raise ValueError
            if url.path not in ('', '/') or url.query:
                raise ValueError
    except ValueError:
        detail = 'HTTP loopback IP and explicit port' if proxy else 'HTTP(S) URL without credentials or fragment'
        raise argparse.ArgumentTypeError('Expected ' + detail) from None
    return value


def request(curl, proxy, url, timeout):
    # --disable must be first: do not inherit ~/.curlrc. --noproxy overrides NO_PROXY.
    command = [curl, '--disable', '--silent', '--show-error', '--noproxy', '',
               '--proxy', proxy, '--connect-timeout', str(min(timeout, 10)),
               '--max-time', str(timeout), '--max-filesize', '131072',
               '--retry', '0', '--write-out', '\n%{http_code} %{time_total}', url]
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                encoding='utf-8', errors='replace', timeout=timeout + 5)
    except subprocess.TimeoutExpired:
        return {'curl_exit': None, 'status': 0, 'seconds': None, 'error': 'process_timeout'}, ''
    except OSError:
        return {'curl_exit': None, 'status': 0, 'seconds': None, 'error': 'curl_start_failed'}, ''
    body, sep, metrics = result.stdout.rpartition('\n')
    try:
        status, seconds = metrics.split()
        status, seconds = int(status), float(seconds)
        if not sep:
            raise ValueError
    except ValueError:
        status, seconds, body = 0, None, ''
    row = {'curl_exit': result.returncode, 'status': status, 'seconds': seconds}
    if result.returncode:
        # Never echo raw stderr, headers, or response bodies: they may contain secrets.
        row['error'] = 'curl_failed'
    return row, body


def trace_ip(body):
    values = [line[3:].strip() for line in body.splitlines() if line.startswith('ip=')]
    if len(values) != 1:
        return None
    try:
        return str(ipaddress.ip_address(values[0]))
    except ValueError:
        return None


def run_checks(args, curl):
    trace, body = request(curl, args.proxy, args.trace_url, args.timeout)
    observed_ip = trace_ip(body)
    trace['observed_exit_ip'] = observed_ip
    exit_matches = (trace['curl_exit'] == 0 and trace['status'] == 200
                    and observed_ip == str(args.expected_exit_ip))
    rows = []
    for _ in range(args.attempts):
        row, _ = request(curl, args.proxy, args.check_url, args.timeout)
        row['passed'] = row['curl_exit'] == 0 and row['status'] == args.expected_status
        rows.append(row)
    successes = sum(row['passed'] for row in rows)
    return {
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'explicit-local-http-proxy-only',
        'physical_path_verified': False,
        'dns_path_verified': False,
        'client_tun_verified': False,
        'expected_exit_ip': str(args.expected_exit_ip),
        'expected_status': args.expected_status,
        'trace': trace,
        'exit_ip_matches': exit_matches,
        'attempts': args.attempts,
        'successes': successes,
        'requests': rows,
        'proxy_http_passed': exit_matches and successes == args.attempts,
        'limitations': 'Verify selected node, physical egress, DNS and client/TUN separately.'
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proxy', required=True, type=lambda value: validate_url(value, proxy=True))
    parser.add_argument('--expected-exit-ip', required=True, type=ipaddress.ip_address)
    parser.add_argument('--trace-url', type=validate_url, default='https://www.cloudflare.com/cdn-cgi/trace')
    parser.add_argument('--check-url', type=validate_url, default='https://www.google.com/generate_204')
    parser.add_argument('--expected-status', type=int, default=204)
    parser.add_argument('--attempts', type=int, default=10)
    parser.add_argument('--timeout', type=int, default=15)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if not 1 <= args.attempts <= 30 or not 1 <= args.timeout <= 60:
        parser.error('attempts must be 1..30; timeout must be 1..60')
    if not 200 <= args.expected_status <= 299:
        parser.error('expected-status must be a success status (200..299)')
    curl = shutil.which('curl.exe') or shutil.which('curl')
    if not curl:
        parser.error('curl is required')
    report = run_checks(args, curl)
    content = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            # Keep previous evidence intact; choose a new report name for another run.
            with args.output.open('x', encoding='utf-8') as file:
                file.write(content + '\n')
        except OSError:
            print('Cannot create report; output must be a new writable file.', file=sys.stderr)
            return 2
    print(content)
    return 0 if report['proxy_http_passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
