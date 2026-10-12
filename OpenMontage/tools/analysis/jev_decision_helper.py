"""Opt-in advisory Jev decisions through the Experiential gateway only.

No SDK, dotenv loading, chat-model changes, retries, redirects, or execution of
returned choices. Importing this module never performs a request.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import sys
from typing import Any


GATEWAY_HOST = 'api.experientiallabs.ai'
GATEWAY_PATH = '/v1/systemone'
ENDPOINT = f'https://{GATEWAY_HOST}{GATEWAY_PATH}'
ALLOWED_MODELS = {'jev-latest', 'jev-latest:free'}
MAX_RESPONSE_BYTES = 1024 * 1024  # Local resource limit, not a provider limit.
MAX_REQUEST_BYTES = 256 * 1024  # Local guard; this is NOT a token counter.
DISCLAIMER = ('Advisory only. Probabilities and confidence are not guarantees. '
              'Do not execute choices, merge changes, or bypass review automatically.')


class JevError(RuntimeError):
    """Safe-to-display error without credentials or raw provider payloads."""


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _structured(value: Any) -> bool:
    return isinstance(value, (str, dict, list))


def validate_request(payload: Any) -> bytes:
    """Validate native request shape and user-specified gateway admission bounds."""
    if not isinstance(payload, dict) or set(payload) != {'model', 'state', 'questions'}:
        raise JevError('Request must contain exactly model, state, and questions.')
    if not isinstance(payload['model'], str) or payload['model'] not in ALLOWED_MODELS:
        raise JevError('Select jev-latest or jev-latest:free explicitly; no model substitution.')
    if not _structured(payload['state']):
        raise JevError('state must be text, an object, or an array.')
    questions = payload['questions']
    if not isinstance(questions, dict) or not 1 <= len(questions) <= 32:
        raise JevError('Gateway requires a question map containing 1-32 questions.')
    for question_id, question in questions.items():
        if not _nonempty_text(question_id) or not isinstance(question, dict):
            raise JevError('Question IDs must be nonempty strings and questions must be objects.')
        if not {'type', 'instructions'} <= set(question) or set(question) - {'type', 'instructions', 'criteria'}:
            raise JevError('Each question needs type and instructions; only criteria is optional.')
        instructions = question['instructions']
        if not _structured(instructions) or not instructions or (isinstance(instructions, str) and not instructions.strip()):
            raise JevError('instructions must be nonempty text, an object, or an array.')
        kind = question['type']
        criteria = question.get('criteria')
        if kind == 'choice':
            if (not isinstance(criteria, dict) or not 1 <= len(criteria) <= 64
                    or not all(_nonempty_text(k) and _nonempty_text(v) for k, v in criteria.items())):
                raise JevError('choice criteria must map 1-64 options to nonempty descriptions.')
        elif kind == 'score':
            if (not isinstance(criteria, list) or not 2 <= len(criteria) <= 10
                    or not all(_nonempty_text(v) for v in criteria)):
                raise JevError('score criteria must contain 2-10 ordered level descriptions.')
        elif kind == 'noul':
            if 'criteria' in question and (not isinstance(criteria, dict)
                    or set(criteria) != {'true', 'false'}
                    or not all(_nonempty_text(v) for v in criteria.values())):
                raise JevError('Optional noul criteria must describe true and false.')
        else:
            raise JevError('Question type must be choice, noul, or score.')
    try:
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise JevError('Request is not valid finite JSON.') from None
    if len(body) > MAX_REQUEST_BYTES:
        raise JevError('Request exceeds the local 256 KiB guard. Use a concise diff and test summary.')
    return body


def _number(value: Any, minimum: float, maximum: float) -> bool:
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value) and minimum <= value <= maximum)


def parse_response(payload: dict, response: Any) -> dict:
    """Read each answer by the caller's ID; a malformed response is never approval."""
    if not isinstance(response, dict) or not isinstance(response.get('answers'), dict):
        raise JevError('Gateway returned no native answers map. No decision is available.')
    answers = {}
    for question_id, question in payload['questions'].items():
        answer = response['answers'].get(question_id)
        kind = question['type']
        if not isinstance(answer, dict) or answer.get('type') != kind:
            raise JevError('Gateway response has a missing or mismatched answer. No approval inferred.')
        value = answer.get(kind)
        if kind == 'choice':
            valid = isinstance(value, str) and value in question['criteria']
        else:
            valid = _number(value, 0, 1 if kind == 'noul' else len(question['criteria']) - 1)
        if not valid:
            raise JevError('Gateway returned an invalid answer value. No approval inferred.')
        if 'confidence' in answer and not _number(answer['confidence'], 0, 1):
            raise JevError('Gateway returned invalid confidence.')
        if 'probabilities' in answer and (not isinstance(answer['probabilities'], dict)
                or not all(_number(v, 0, 1) for v in answer['probabilities'].values())):
            raise JevError('Gateway returned invalid probabilities.')
        answers[question_id] = {k: v for k, v in answer.items()
                                if k in {'type', kind, 'confidence', 'probabilities', 'legend'}}
    usage = response.get('usage')
    if usage is not None and not isinstance(usage, dict):
        raise JevError('Gateway returned invalid usage metadata.')
    return {'status': 'received', 'requested_model': payload['model'],
            'reported_model': response.get('model'), 'answers': answers,
            'reported_usage': usage, 'usage_reported': usage is not None,
            'advisory_only': True, 'warning': DISCLAIMER}


def evaluate(payload: dict, *, approved_live: bool = False, timeout_seconds: float = 30) -> dict:
    """Make exactly one opted-in HTTPS POST. Unknown outcomes must not auto-retry."""
    body = validate_request(payload)
    if not approved_live:
        raise JevError('Live call not approved. Ask the user before a potentially charged request.')
    key = os.environ.get('EXPERIENTIAL_API_KEY', '').strip()
    if not key:
        raise JevError('Set EXPERIENTIAL_API_KEY locally, then retry only after live-call approval. Do not paste it in chat.')
    if any(char.isspace() for char in key) or not key.isascii():
        raise JevError('EXPERIENTIAL_API_KEY is malformed; correct it locally.')
    if not _number(timeout_seconds, .1, 60):
        raise JevError('Network timeout must be between 0.1 and 60 seconds.')
    # Do not accidentally upload the configured credential as evaluation state.
    if key.encode() in body:
        raise JevError('Request contains the configured credential. Remove it before evaluation.')
    connection = http.client.HTTPSConnection(GATEWAY_HOST, timeout=timeout_seconds)
    try:
        connection.request('POST', GATEWAY_PATH, body=body, headers={
            'Authorization': f'Bearer {key}', 'Content-Type': 'application/json',
            'Accept': 'application/json',
        })
        response = connection.getresponse()
        # http.client does not follow redirects. Never send keys to another origin.
        if not 200 <= response.status < 300:
            raise JevError(f'Gateway HTTP {response.status}; no retry performed. '
                           'Outcome may already be charged. Raw error body withheld.')
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise JevError('Gateway response exceeds local size guard; outcome may be charged. No retry.')
        # Never echo our key even if a broken gateway reflects it in response data.
        raw = raw.replace(key.encode(), b'[REDACTED]')
        try:
            parsed = json.loads(raw)
        except (ValueError, UnicodeError):
            raise JevError('Gateway returned invalid JSON; outcome may be charged. No retry.') from None
        return parse_response(payload, parsed)
    except (OSError, http.client.HTTPException) as exc:
        raise JevError(f'Gateway transport failure ({type(exc).__name__}); '
                       'outcome unknown and may be charged. No retry performed.') from None
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request', type=Path, help='Reviewed native JSON request, not a repository dump')
    parser.add_argument('--approve-live', action='store_true', help='Use only after explicit approval for this call')
    parser.add_argument('--timeout', type=float, default=30)
    args = parser.parse_args(argv)
    try:
        if args.request.stat().st_size > MAX_REQUEST_BYTES:
            raise JevError('Request file exceeds local 256 KiB guard.')
        payload = json.loads(args.request.read_text(encoding='utf-8'))
        body = validate_request(payload)
        if args.approve_live:
            report = evaluate(payload, approved_live=True, timeout_seconds=args.timeout)
        else:
            report = {'status': 'validated_no_network', 'endpoint': ENDPOINT,
                      'model': payload['model'], 'question_count': len(payload['questions']),
                      'request_bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(),
                      'reported_usage': None, 'warning': DISCLAIMER}
        print(json.dumps(report, indent=2, ensure_ascii=True))
        return 0
    except (JevError, OSError, ValueError, RecursionError) as exc:
        message = str(exc) if isinstance(exc, JevError) else f'Cannot load request ({type(exc).__name__}).'
        print(json.dumps({'status': 'error', 'error': message}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
