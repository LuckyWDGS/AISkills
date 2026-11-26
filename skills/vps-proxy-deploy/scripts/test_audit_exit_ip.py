"""Offline regressions for missing evidence, split routing and specified-IP lookups."""
import ipaddress
import json
import unittest
from unittest.mock import Mock, patch

import requests

import audit_exit_ip as audit


TARGET = ipaddress.ip_address('192.0.2.77')


def reply(payload, status=200):
    response = requests.Response()
    response.status_code = status
    response.url = 'https://example.invalid/'
    response._content = json.dumps(payload).encode()
    return response


class AuditExitTests(unittest.TestCase):
    def test_scamalytics_reads_the_target_panel_and_preserves_score_basis(self):
        session = Mock(spec=requests.Session)
        page = '''<h1>192.0.2.77 Fraud Risk</h1><pre>{"score": 83}</pre>
                  <div class="panel_title high_risk">Low Risk</div>
                  <div class="panel_body">Score based on the operator.</div>
                  <table><tr><th>Public Proxy</th><td>No</td></tr></table>'''
        for displayed, expected in [('0', 0), ('100', 100), ('101', None), ('', None)]:
            with self.subTest(displayed=displayed):
                session.request.return_value.content = (page + f'<div class="score">Fraud Score: {displayed}</div>').encode()
                fields = audit.scamalytics(session, 'https://example.invalid/', TARGET)
                self.assertEqual(fields.get('fraud_score'), expected)
                self.assertEqual(fields['risk_label'], 'Low Risk')
                self.assertIn('operator', fields['assessment'])
                self.assertEqual(fields['Public Proxy'], 'No')
                missing = audit.missing_fields('Scamalytics', fields)
                self.assertIn('Tor Exit Node', missing)
                self.assertEqual('fraud_score' in missing, expected is None)

    def test_scamalytics_rejects_challenge_or_other_address(self):
        session = Mock(spec=requests.Session)
        for heading in ('Checking your browser', '192.0.2.78 Fraud Risk'):
            with self.subTest(heading=heading):
                session.request.return_value.content = f'<h1>{heading}</h1><div class="score">Fraud Score: 2</div>'.encode()
                with self.assertRaises(audit.EvidenceError):
                    audit.scamalytics(session, 'https://example.invalid/', TARGET)

    def current_with_ippure(self, payload):
        session = Mock(spec=requests.Session)
        session.request.side_effect = lambda method, url, **options: (
            reply(payload) if url == 'https://my.ippure.com/v1/info' else reply({}, 429))
        with patch.object(audit, 'confirmed_exit', return_value=TARGET):
            return audit.audit(session, True, TARGET)

    def test_invalid_provider_payload_leaves_other_sources_available(self):
        result, code = self.current_with_ippure([])
        self.assertEqual(code, 1)
        self.assertTrue(result['current_exit_verified'])
        self.assertEqual(result['sources']['IPPure']['reason'], 'unexpected_response_shape')
        self.assertEqual(result['sources']['Tor Project']['reason'], 'HTTP 429')

    def test_missing_fields_do_not_become_negative_findings(self):
        result, code = self.current_with_ippure({'ip': str(TARGET), 'isResidential': False, 'fraudScore': 0})
        self.assertEqual(code, 1)
        self.assertEqual(result['sources']['IPPure']['missing_fields'], ['isBroadcast'])
        self.assertFalse(result['sources']['IPPure']['fields']['isResidential'])
        self.assertIn('anonymization.Proxy', audit.missing_fields('IPinfo', {'anonymization': {'VPN': 'Not detected'}}))

    def test_disagreeing_self_check_invalidates_current_exit(self):
        result, code = self.current_with_ippure({'ip': '198.51.100.4'})
        self.assertEqual(code, 2)
        self.assertFalse(result['current_exit_verified'])
        self.assertEqual(result['scope'], 'address_records_only')
        self.assertNotIn('198.51.100.4', json.dumps(result))

    def test_specified_ip_never_uses_the_readers_ip_as_its_result(self):
        session = Mock(spec=requests.Session)
        session.request.return_value = reply({}, 429)
        result, code = audit.audit(session, False, TARGET)
        self.assertEqual(code, 1)
        self.assertEqual(result['sources']['IPPure']['url'], f'https://ippure.com/?ip={TARGET}')
        urls = [call.args[1] for call in session.request.call_args_list]
        self.assertFalse(any('ipify.org' in url or 'cdn-cgi/trace' in url or 'my.ippure.com' in url
                             or url.endswith('/api/ip') for url in urls))

    def test_cleanip_pending_report_is_for_the_verified_exit_or_supplied_address(self):
        session = Mock(spec=requests.Session)
        session.request.return_value = reply({}, 429)
        for current, target in ((True, TARGET), (False, ipaddress.ip_address('2001:db8::77'))):
            with self.subTest(current=current), patch.object(audit, 'confirmed_exit', return_value=target):
                result, _ = audit.audit(session, current, None if current else target)
                source = result['sources']['CleanIP']
                self.assertEqual(source['url'], f'https://cleanip.io/{target}/assessment')
                self.assertEqual(source['status'], 'lookup_target_card')
                self.assertNotIn('fields', source)


if __name__ == '__main__':
    unittest.main()
