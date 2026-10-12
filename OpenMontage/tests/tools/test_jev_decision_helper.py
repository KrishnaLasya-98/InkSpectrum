import copy
import json
from unittest.mock import MagicMock

import pytest

from tools.analysis import jev_decision_helper as helper


@pytest.fixture
def payload():
    return {'model': 'jev-latest', 'state': {'diff': '+ with open(path) as f: ...',
            'tests': 'Mock fixture only: 2 passed; no encoded video inspection.'}, 'questions': {
        'review': {'type': 'choice', 'instructions': 'Does this summary need closer review?',
                   'criteria': {'accept': 'No obvious concern in supplied evidence; not approval to merge.',
                                'review': 'Insufficient evidence or a concern requires closer review.'}},
        'tests_present': {'type': 'noul', 'instructions': 'Does state.tests report passing tests?',
                          'criteria': {'true': 'Passing tests explicitly reported.', 'false': 'Not reported.'}},
        'risk': {'type': 'score', 'instructions': 'Rate visible regression risk from the diff only.',
                 'criteria': ['Low', 'Moderate', 'High']}}}


@pytest.fixture
def transport(monkeypatch):
    monkeypatch.setenv('EXPERIENTIAL_API_KEY', 'fixture-key-not-real')
    factory = MagicMock()
    connection = factory.return_value
    response = connection.getresponse.return_value
    response.status = 200
    response.read.return_value = json.dumps({'model': 'jev-resolved-test', 'answers': {
        'risk': {'type': 'score', 'score': 1.5},
        'tests_present': {'type': 'noul', 'noul': .95},
        'review': {'type': 'choice', 'choice': 'review', 'confidence': .8,
                   'probabilities': {'accept': .1, 'review': .9}}},
        'usage': {'input_tokens': 120, 'output_tokens': 20}}).encode()
    monkeypatch.setattr(helper.http.client, 'HTTPSConnection', factory)
    return factory, connection, response


def test_native_gateway_once_and_answers_by_id(payload, transport):
    factory, conn, response = transport
    report = helper.evaluate(payload, approved_live=True, timeout_seconds=12)
    factory.assert_called_once_with('api.experientiallabs.ai', timeout=12)
    conn.request.assert_called_once()
    args, kwargs = conn.request.call_args
    assert args == ('POST', '/v1/systemone')
    assert json.loads(kwargs['body']) == payload
    assert kwargs['headers'] == {'Authorization': 'Bearer fixture-key-not-real',
                                 'Content-Type': 'application/json', 'Accept': 'application/json'}
    assert report['answers']['review']['choice'] == 'review'
    assert report['reported_usage'] == {'input_tokens': 120, 'output_tokens': 20}
    assert report['advisory_only'] is True
    conn.close.assert_called_once()


@pytest.mark.parametrize('state', ['short text', {'diff': 'small'}, ['a', 'b']])
def test_native_states_and_free_alias_preserved(payload, transport, state):
    payload.update(state=state, model='jev-latest:free')
    helper.evaluate(payload, approved_live=True)
    assert json.loads(transport[1].request.call_args.kwargs['body'])['model'] == 'jev-latest:free'


def test_opt_in_required(payload, transport):
    with pytest.raises(helper.JevError, match='not approved'):
        helper.evaluate(payload)
    transport[0].assert_not_called()


def test_only_gateway_environment_key(payload, transport, monkeypatch):
    monkeypatch.delenv('EXPERIENTIAL_API_KEY')
    monkeypatch.setenv('TYPESAFE_API_KEY', 'must-not-use')
    with pytest.raises(helper.JevError, match='Set EXPERIENTIAL_API_KEY locally'):
        helper.evaluate(payload, approved_live=True)
    transport[0].assert_not_called()


@pytest.mark.parametrize('status', [301, 302, 307, 308, 400, 401, 429, 500, 503])
def test_http_errors_and_redirects_never_retry(payload, transport, status):
    factory, conn, response = transport
    response.status = status
    with pytest.raises(helper.JevError, match=f'HTTP {status}'):
        helper.evaluate(payload, approved_live=True)
    conn.request.assert_called_once()
    response.read.assert_not_called()
    conn.close.assert_called_once()


@pytest.mark.parametrize('exc', [TimeoutError('fixture-key-not-real'),
                               OSError('fixture-key-not-real'),
                               helper.http.client.RemoteDisconnected('fixture-key-not-real')])
def test_transport_errors_safe_and_no_retry(payload, transport, exc):
    transport[1].getresponse.side_effect = exc
    with pytest.raises(helper.JevError, match='outcome unknown') as caught:
        helper.evaluate(payload, approved_live=True)
    assert 'fixture-key-not-real' not in str(caught.value)
    transport[1].request.assert_called_once()
    transport[1].close.assert_called_once()


@pytest.mark.parametrize('kind,count', [('questions', 33), ('choice', 65), ('score', 1), ('score', 11)])
def test_platform_bounds(payload, transport, kind, count):
    if kind == 'questions':
        payload['questions'] = {str(i): {'type': 'noul', 'instructions': 'True?'} for i in range(count)}
    elif kind == 'choice':
        payload['questions']['review']['criteria'] = {str(i): 'description' for i in range(count)}
    else:
        payload['questions']['risk']['criteria'] = ['level'] * count
    with pytest.raises(helper.JevError):
        helper.evaluate(payload, approved_live=True)
    transport[0].assert_not_called()


def test_boundary_counts_valid(payload):
    payload['questions']['review']['criteria'] = {str(i): 'description' for i in range(64)}
    payload['questions']['risk']['criteria'] = ['level'] * 10
    payload['questions'].update({str(i): {'type': 'noul', 'instructions': 'True?'} for i in range(29)})
    assert len(payload['questions']) == 32
    helper.validate_request(payload)


@pytest.mark.parametrize('change', [
    {'model': 'other-chat-model'}, {'state': 1}, {'questions': []}, {'stream': True},
    {'state': float('nan')}, {'state': {'invalid': float('inf')}}])
def test_invalid_payload(payload, transport, change):
    payload.update(change)
    with pytest.raises(helper.JevError):
        helper.evaluate(payload, approved_live=True)
    transport[0].assert_not_called()


@pytest.mark.parametrize('raw', [b'not json', b'{}', b'{"answers": {}}',
    b'{"answers":{"review":{"type":"choice","choice":"execute_shell"}}}'])
def test_invalid_answers_fail_closed(payload, transport, raw):
    transport[2].read.return_value = raw
    with pytest.raises(helper.JevError):
        helper.evaluate(payload, approved_live=True)
    transport[1].request.assert_called_once()
    transport[1].close.assert_called_once()


@pytest.mark.parametrize('value', [-1, 2, True, float('nan')])
def test_invalid_noul_rejected(payload, transport, value):
    data = json.loads(transport[2].read.return_value)
    data['answers']['tests_present']['noul'] = value
    transport[2].read.return_value = json.dumps(data).encode()
    with pytest.raises(helper.JevError):
        helper.evaluate(payload, approved_live=True)


def test_missing_usage_not_zero(payload, transport):
    data = json.loads(transport[2].read.return_value)
    del data['usage']
    transport[2].read.return_value = json.dumps(data).encode()
    result = helper.evaluate(payload, approved_live=True)
    assert result['reported_usage'] is None
    assert result['usage_reported'] is False


def test_response_echo_does_not_expose_key(payload, transport):
    data = json.loads(transport[2].read.return_value)
    data['usage']['unexpected_note'] = 'fixture-key-not-real'
    transport[2].read.return_value = json.dumps(data).encode()
    assert 'fixture-key-not-real' not in json.dumps(helper.evaluate(payload, approved_live=True))


def test_refuse_key_in_state(payload, transport):
    payload['state'] = 'fixture-key-not-real'
    with pytest.raises(helper.JevError, match='contains the configured credential'):
        helper.evaluate(payload, approved_live=True)
    transport[0].assert_not_called()


@pytest.mark.parametrize('timeout', [0, -1, 61, float('inf')])
def test_timeout_bounded(payload, transport, timeout):
    with pytest.raises(helper.JevError, match='timeout'):
        helper.evaluate(payload, approved_live=True, timeout_seconds=timeout)
    transport[0].assert_not_called()


def test_resource_limits(payload, transport):
    oversized = copy.deepcopy(payload)
    oversized['state'] = 'a' * helper.MAX_REQUEST_BYTES
    with pytest.raises(helper.JevError, match='local 256 KiB'):
        helper.validate_request(oversized)
    transport[2].read.return_value = b'a' * (helper.MAX_RESPONSE_BYTES + 1)
    with pytest.raises(helper.JevError, match='size guard'):
        helper.evaluate(payload, approved_live=True)
    transport[1].close.assert_called_once()


def test_cli_default_dry_run(payload, transport, tmp_path, capsys):
    path = tmp_path / 'request.json'
    path.write_text(json.dumps(payload))
    assert helper.main([str(path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['status'] == 'validated_no_network'
    transport[0].assert_not_called()
