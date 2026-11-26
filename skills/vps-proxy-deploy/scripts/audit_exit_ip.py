#!/usr/bin/env python3
"""Collect public records for a named IP or the verified exit of an explicit local HTTP proxy."""
import argparse
import ipaddress
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from lxml import etree, html

from probe_proxy import trace_ip, validate_url


class EvidenceError(Exception):
    """A short, safe reason to withhold this observation."""


def public_ip(value):
    address = ipaddress.ip_address(value)
    if not address.is_global or address.is_multicast or '%' in str(address):
        raise ValueError('A public unicast IP is required')
    return address


def verify_address(value, target):
    try:
        observed = ipaddress.ip_address(value)
    except (TypeError, ValueError):
        raise EvidenceError('returned_ip_missing_or_invalid') from None
    if observed != target:
        raise EvidenceError('returned_ip_mismatch')


def select(record, *keys):
    return {key: record[key] for key in keys if key in record}


def fetch(session, url, **options):
    response = session.request(options.pop('method', 'GET'), url, timeout=(6, 15), **options)
    response.raise_for_status()
    return response


def object_record(response):
    data = response.json()
    if not isinstance(data, dict):
        raise EvidenceError('unexpected_response_shape')
    return data


def confirmed_exit(session, expected):
    ipv6 = expected is not None and expected.version == 6
    cf = 'https://[2606:4700:4700::1111]' if ipv6 else 'https://1.1.1.1'
    echo = 'https://api6.ipify.org' if ipv6 else 'https://api4.ipify.org'
    first = trace_ip(fetch(session, cf + '/cdn-cgi/trace').text)
    second = public_ip(fetch(session, echo).text.strip())
    verify_address(first, second)
    if (expected is not None and second != expected) or second.version != (6 if ipv6 else 4):
        raise EvidenceError('unexpected_exit')
    return second


def table_fields(doc):
    fields = {}
    for row in doc.xpath('//tr'):
        cells = [' '.join(c.text_content().split()) for c in row.xpath('./th|./td')]
        if len(cells) == 2:
            fields[cells[0]] = cells[1]
    return fields


def ipinfo(session, url, target):
    response = fetch(session, url, headers={'Accept': 'text/html'})
    if 'json' in response.headers.get('Content-Type', ''):
        data = object_record(response)
        verify_address(data.get('ip'), target)
        return dict(view='basic_json', **select(data, 'city', 'region', 'country', 'org', 'timezone'))
    doc = html.fromstring(response.content)
    verify_address(doc.xpath('normalize-space((//h1)[1])'), target)
    fields = table_fields(doc)
    if not fields.get('ASN') or not fields.get('Location'):
        raise EvidenceError('summary_fields_unavailable')
    labels = {}
    for item in doc.xpath('//*[@id="anonymization"]//li'):
        words = [text.strip() for text in item.itertext() if text.strip()]
        if len(words) >= 2:
            labels[words[0]] = words[-1]
    summary = select(fields, 'Location', 'ASN', 'AS Type', 'Company', 'Range', 'Privacy')
    return dict(view='public_html', summary=summary, anonymization=labels)


def ip_api(session, url, target):
    keys = ('country', 'regionName', 'city', 'timezone', 'isp', 'org', 'as', 'mobile', 'proxy', 'hosting')
    data = object_record(fetch(session, url, params={'fields': ','.join(('status', 'query', *keys))}))
    if data.get('status') != 'success':
        raise EvidenceError('provider_did_not_return_a_record')
    verify_address(data.get('query'), target)
    return select(data, *keys)


def maxmind(session, url, target):
    # Normal public demo form. Keep its CSRF token, session cookie and demo bearer in memory.
    origin = 'https://www.maxmind.com'
    form = html.fromstring(fetch(session, url).content)
    csrf = form.xpath('//form//input[@name="csrf_token"]/@value')
    if not csrf:
        raise EvidenceError('demo_form_unavailable')
    token_response = fetch(session, origin + '/en/geoip2/demo/token', method='POST',
                           headers={'X-CSRF-Token': csrf[0], 'Origin': origin, 'Referer': url})
    token = object_record(token_response).get('token')
    if not isinstance(token, str) or not token:
        raise EvidenceError('demo_token_unavailable')
    response = fetch(session, f'https://geoip.maxmind.com/geoip/v2.1/city/{target}', params={'demo': '1'},
                     headers={'Authorization': 'Bearer ' + token, 'Origin': origin, 'Referer': origin + '/'})
    data = object_record(response)
    traits = data.get('traits', {})
    verify_address(traits.get('ip_address'), target)
    return dict(country=data.get('country', {}).get('iso_code'), city=data.get('city', {}).get('names', {}).get('en'),
                traits=select(traits, 'network', 'autonomous_system_number', 'autonomous_system_organization',
                              'isp', 'organization', 'connection_type', 'user_type'))


def ip2location(session, url, target):
    doc = html.fromstring(fetch(session, url).content)
    fields = table_fields(doc)
    verify_address(fields.get('IP Address'), target)
    record = select(fields, 'Country', 'Region', 'City', 'ISP', 'ASN', 'AS CIDR', 'Net Speed', 'Usage Type',
                    'Category', 'Anonymous Proxy', 'Proxy Type', 'Threat', 'Fraud Score')
    if not record:
        raise EvidenceError('lookup_fields_unavailable')
    for block in doc.xpath('//pre'):
        try:
            data = json.loads(block.text_content())
        except ValueError:
            continue
        if not isinstance(data, dict) or not data.get('ip'):
            continue
        if ipaddress.ip_address(data['ip']) == target:
            record.update(select(data, 'is_proxy', 'fraud_score'))
            record['flags'] = select(data.get('proxy') or {}, 'is_data_center', 'is_vpn', 'is_tor',
                                     'is_residential_proxy', 'is_public_proxy', 'is_spammer', 'is_botnet')
            break
    return record


def ippure(session, url, target):
    data = object_record(fetch(session, url))
    verify_address(data.get('ip'), target)
    return select(data, 'countryCode', 'city', 'timezone', 'asn', 'asOrganization',
                  'isResidential', 'isBroadcast', 'fraudScore')


def scamalytics(session, url, target):
    doc = html.fromstring(fetch(session, url).content)
    heading = doc.xpath('normalize-space((//h1)[1])')
    verify_address(heading.removesuffix(' Fraud Risk'), target)
    fields = select(table_fields(doc), 'Connection type', 'Datacenter', 'Anonymizing VPN',
                    'Tor Exit Node', 'Public Proxy', 'Web Proxy', 'Residential Proxy')
    # Read the target's visible assessment. The page also contains a partial API example.
    panel = doc.xpath('normalize-space((//div[contains(concat(" ", normalize-space(@class), " "),'
                      ' " panel_title ")])[1])')
    if panel:
        fields['risk_label'] = panel
    assessment = doc.xpath('normalize-space((//div[@class="panel_body"])[1])')
    if assessment:
        fields['assessment'] = assessment
    score_text = doc.xpath('normalize-space((//div[@class="score"])[1])')
    match = re.fullmatch(r'Fraud Score:\s*([0-9]{1,3})', score_text)
    if match and int(match[1]) <= 100:
        fields['fraud_score'] = int(match[1])
    return fields


def bgp(session, url, target):
    data = object_record(fetch(session, url))['data']
    if not data.get('prefix') or target not in ipaddress.ip_network(data['prefix']):
        raise EvidenceError('no_matching_routed_prefix')
    return select(data, 'prefix', 'asns')


def rdap(session, url, target):
    response = fetch(session, url)
    data = object_record(response)
    if not (ipaddress.ip_address(data['startAddress']) <= target <= ipaddress.ip_address(data['endAddress'])):
        raise EvidenceError('allocation_does_not_cover_target')
    names = []
    for entity in data.get('entities', []):
        if 'registrant' in entity.get('roles', []):
            vcard = entity.get('vcardArray') or ['', []]
            names.extend(entry[3] for entry in vcard[1] if len(entry) >= 4 and entry[0] == 'fn')
    return dict(registry_url=response.url, registrants=names,
                **select(data, 'name', 'handle', 'startAddress', 'endAddress', 'type'))


def tor_current(session, url, target):
    data = object_record(fetch(session, url))
    verify_address(data.get('IP'), target)
    if not isinstance(data.get('IsTor'), bool):
        raise EvidenceError('Tor_status_unavailable')
    return select(data, 'IsTor')


def tor_list(session, url, target):
    lines = fetch(session, url).text.splitlines()
    listed = {ipaddress.ip_address(line.strip()) for line in lines if line.strip() and not line.lstrip().startswith('#')}
    if not any(ip.version == target.version for ip in listed):
        raise EvidenceError('no_entries_for_address_family')
    return dict(in_published_exit_list=target in listed)


def spamhaus_drop(session, url, target):
    rows = [json.loads(line) for line in fetch(session, url).text.splitlines() if line.strip()]
    networks = [ipaddress.ip_network(r['cidr']) for r in rows if 'cidr' in r]
    metadata = next((r for r in rows if r.get('type') == 'metadata'), {})
    if len(networks) != metadata.get('records') or not networks or any(n.version != target.version for n in networks):
        raise EvidenceError('incomplete_DROP_list')
    return dict(matching_prefixes=[str(n) for n in networks if target in n],
                checked_prefixes=len(networks), list_timestamp=metadata.get('timestamp'))


def failure(error):
    if isinstance(error, requests.HTTPError):
        return 'HTTP ' + str(error.response.status_code)
    if isinstance(error, (KeyError, AttributeError, TypeError, IndexError)):
        return 'unexpected_response_shape'
    return str(error) if isinstance(error, EvidenceError) else type(error).__name__


CHECK_ERRORS = (EvidenceError, requests.RequestException, ValueError, TypeError, KeyError, AttributeError,
                IndexError, etree.LxmlError)


def missing_fields(provider, data):
    important = {
        'IPinfo': ('summary.Location', 'summary.ASN', 'summary.AS Type', 'summary.Company', 'summary.Range',
                   'anonymization.VPN', 'anonymization.Proxy', 'anonymization.Tor', 'anonymization.Relay',
                   'anonymization.Hosting', 'anonymization.Residential Proxy'),
        'ip-api': ('country', 'city', 'isp', 'org', 'as', 'mobile', 'proxy', 'hosting'),
        'MaxMind': ('country', 'city', 'traits.isp', 'traits.organization', 'traits.connection_type'),
        'IP2Location': ('City', 'ISP', 'ASN', 'Usage Type', 'Category', 'Anonymous Proxy', 'Proxy Type',
                        'Fraud Score', 'flags.is_data_center'),
        'RIPEstat': ('asns',),
        'IPPure': ('isResidential', 'isBroadcast', 'fraudScore'),
        'Scamalytics': ('fraud_score', 'risk_label', 'assessment', 'Datacenter', 'Anonymizing VPN',
                        'Tor Exit Node', 'Public Proxy', 'Residential Proxy'),
    }
    missing = []
    for path in important.get(provider, ()):
        value = data
        for key in path.split('.'):
            value = value.get(key) if isinstance(value, dict) else None
        if value is None or value in ('', '-', '—', []):
            missing.append(path)
    return missing


def audit(session, current, target):
    result = {'checked_at_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
              'scope': 'current_proxy_exit' if current else 'specified_address', 'sources': {}}
    if current:
        result['current_exit_verified'] = False
        try:
            target = confirmed_exit(session, target)
        except CHECK_ERRORS as exc:
            result['exit_check'] = failure(exc)
            return result, 2
    result['ip'] = str(target)
    # CleanIP's public HTML shows a placeholder score until the report renders in a browser.
    result['sources']['CleanIP'] = {
        'status': 'lookup_target_card',
        'url': f'https://cleanip.io/{target}/assessment',
        'reason': 'read_rendered_assessment',
    }
    checks = [
        ('IPinfo', ipinfo, f'https://ipinfo.io/{target}'),
        ('ip-api', ip_api, f'http://ip-api.com/json/{target}'),
        ('MaxMind', maxmind, f'https://www.maxmind.com/en/geoip-demo?ip_address={target}'),
        ('IP2Location', ip2location, f'https://www.ip2location.com/{target}'),
        ('Scamalytics', scamalytics, f'https://scamalytics.com/ip/{target}'),
        ('RIPEstat', bgp, f'https://stat.ripe.net/data/network-info/data.json?resource={target}'),
        ('RIR RDAP', rdap, f'https://rdap-bootstrap.arin.net/bootstrap/ip/{target}'),
        ('Spamhaus DROP', spamhaus_drop, f'https://www.spamhaus.org/drop/drop_v{target.version}.json'),
    ]
    if current:
        checks.extend([('IPPure', ippure, 'https://my.ippure.com/v1/info'),
                       ('Tor Project', tor_current, 'https://check.torproject.org/api/ip')])
    else:
        result['sources']['IPPure'] = {'status': 'lookup_target_card', 'url': f'https://ippure.com/?ip={target}'}
        checks.append(('Tor Project', tor_list, 'https://check.torproject.org/torbulkexitlist'))
    for name, lookup, url in checks:
        try:
            fields = lookup(session, url, target)
            missing = missing_fields(name, fields)
            row = {'status': 'partial' if missing else 'returned', 'fields': fields}
            if missing:
                row['missing_fields'] = missing
        except CHECK_ERRORS as exc:
            row = {'status': 'unavailable', 'reason': failure(exc)}
        result['sources'][name] = dict(url=url, **row)
    if current:
        try:
            confirmed_exit(session, target)
            if any(result['sources'][name].get('reason') == 'returned_ip_mismatch'
                   for name in ('IPPure', 'Tor Project')):
                raise EvidenceError('self_reported_ips_disagree')
            result['current_exit_verified'] = True
            result['exit_check'] = 'matched_cloudflare_and_ipify_before_and_after'
        except CHECK_ERRORS as exc:
            result['scope'] = 'address_records_only'
            result['exit_check'] = failure(exc)
            return result, 2
    incomplete = any(row['status'] != 'returned' for row in result['sources'].values())
    return result, int(incomplete)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    route = parser.add_mutually_exclusive_group(required=True)
    route.add_argument('--proxy', type=lambda value: validate_url(value, proxy=True),
                       help='Explicit loopback HTTP proxy URL, including its port.')
    route.add_argument('--host-route', action='store_true',
                       help='For --ip on a trusted host: use its network route without an HTTP proxy.')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--current', action='store_true', help='Verify current IPv4 exit twice (IPv6 with an expected IPv6).')
    mode.add_argument('--ip', type=public_ip, help='Look up a specified public IP without treating it as your exit.')
    parser.add_argument('--expected-exit-ip', type=public_ip, help='Require both current-exit probes to match this IP.')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.host_route and args.current:
        parser.error('--host-route is only available for --ip on a trusted host')
    if args.expected_exit_ip and not args.current:
        parser.error('--expected-exit-ip requires --current')
    with requests.Session() as session:
        session.trust_env = False
        if args.proxy:
            session.proxies = {'http': args.proxy, 'https': args.proxy}
        session.headers.update({'User-Agent': 'vps-proxy-deploy (public IP lookup)', 'Accept-Language': 'en-US,en;q=0.8'})
        result, code = audit(session, args.current, args.ip or args.expected_exit_ip)
        result['lookup_transport'] = 'explicit_loopback_http_proxy' if args.proxy else 'host_network_route'
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + '\n', encoding='utf-8')
    else:
        print(output)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
