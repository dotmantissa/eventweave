from genlayer import *
import json
import hashlib
from datetime import datetime, timezone

MAX_JSON_BYTES = 24576
MAX_SOURCE_BYTES = 49152
MAX_DECODED_CHARS = 49152
MAX_CONTEXT_BYTES = 98304
MAX_PROMPT_CHARS = 110000
MAX_INPUT_TOKENS = 49152
MAX_HISTORY = 10000
ATTRIBUTES = ('issuer', 'place', 'interval', 'occurrence_type', 'official_reference')
DECISIONS = ('SAME', 'DISTINCT', 'UNKNOWN')
KINDS = ('release', 'security_incident', 'operational_notice')
ENVELOPE_KEYS = ('request_id', 'owner', 'parties', 'policy_id', 'policy_revision', 'subject_id', 'subject_digest', 'source_manifest_digest', 'consumer_address', 'consequence_digest', 'generation', 'deadline')


def fail(message: str):
    raise gl.vm.UserError('[EXPECTED] ' + message)


def encoded(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(value) -> str:
    return hashlib.sha256(encoded(value).encode('utf-8')).hexdigest()


def parse(raw: str) -> dict:
    if len(raw.encode('utf-8')) > MAX_JSON_BYTES:
        fail('Request exceeds byte limit')
    try:
        value = json.loads(raw)
    except Exception:
        fail('Invalid JSON')
    if not isinstance(value, dict):
        fail('Expected object')
    return value


def text(value, limit: int = 128) -> str:
    if not isinstance(value, str) or not value or len(value.encode('utf-8')) > limit:
        fail('Invalid bounded text')
    return value


def number(value, maximum: int = 4294967295) -> int:
    if type(value) is not int or value < 0 or value > maximum:
        fail('Invalid unsigned integer')
    return value


def hash_text(value) -> str:
    text(value, 64)
    if len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        fail('Invalid SHA256 commitment')
    return value


def address(value) -> str:
    text(value, 42)
    try:
        return str(Address(value)).lower()
    except Exception:
        fail('Invalid address')


def now() -> datetime:
    return datetime.fromisoformat(gl.message_raw['datetime'].replace('Z', '+00:00')).astimezone(timezone.utc)


def timestamp(value) -> datetime:
    text(value, 40)
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.tzinfo is None:
            fail('Timezone required')
        return result.astimezone(timezone.utc)
    except Exception:
        fail('Invalid timestamp')


def envelope(value: dict) -> dict:
    if set(value.keys()) != set(ENVELOPE_KEYS):
        fail('Envelope fields do not match schema')
    for key in ('request_id', 'policy_id', 'subject_id'):
        identifier(value[key])
    for key in ('subject_digest', 'source_manifest_digest', 'consequence_digest'):
        hash_text(value[key])
    for key in ('owner', 'consumer_address'):
        value[key] = address(value[key])
    parties = value['parties']
    if not isinstance(parties, list) or not 1 <= len(parties) <= 6:
        fail('One to six parties required')
    value['parties'] = sorted(set(address(p) for p in parties))
    number(value['policy_revision']); number(value['generation'])
    if value['policy_revision'] < 1 or value['generation'] < 1:
        fail('Revision and generation start at one')
    timestamp(value['deadline'])
    return value


def pair_key(left: str, right: str, scope: str) -> str:
    identifier(left); identifier(right)
    if left == right:
        fail('A pair needs distinct records')
    return 'pair:' + digest({'scope': scope, 'records': sorted((left, right))})


def source_record(value: dict) -> dict:
    keys = {'record_id', 'authority_id', 'channel', 'url', 'raw_hash', 'revision', 'scope', 'byte_length', 'spans'}
    if set(value.keys()) != keys:
        fail('Source fields do not match schema')
    for key in ('record_id', 'authority_id', 'channel', 'revision', 'scope'):
        identifier(value[key])
    text(value['url'], 2048); hash_text(value['raw_hash'])
    size = number(value['byte_length'], MAX_SOURCE_BYTES)
    if size < 1:
        fail('Empty source')
    spans = value['spans']
    if not isinstance(spans, list) or len(spans) != len(ATTRIBUTES):
        fail('Every mandatory attribute requires a span')
    seen = set()
    for span in spans:
        if not isinstance(span, dict) or set(span) != {'span_id', 'attribute', 'start', 'end', 'raw_hash'}:
            fail('Invalid span locator')
        identifier(span['span_id']); hash_text(span['raw_hash'])
        if span['raw_hash'] != value['raw_hash'] or span['attribute'] not in ATTRIBUTES or span['attribute'] in seen:
            fail('Invalid span coverage')
        seen.add(span['attribute'])
        start = number(span['start'], size); end = number(span['end'], size)
        if start >= end:
            fail('Empty or reversed span')
    return value


def page(history, offset: int, limit: int) -> list:
    number(offset); number(limit, 50)
    if limit < 1:
        fail('Page limit starts at one')
    return [json.loads(history[i]) for i in range(offset, min(offset + limit, len(history)))]


def append(history, value):
    history.append(encoded(value))


def https_channel(url: str, prefix: str) -> bool:
    # Parse an intentionally strict HTTPS subset without ambiguous URL normalization.
    def parts(value):
        if not value.startswith('https://') or any(c in value for c in ('\\', '#', '?', '%')) or any(ord(c) <= 32 or ord(c) >= 127 for c in value):
            fail('Invalid authority HTTPS URL')
        rest = value[8:]; host, separator, path = rest.partition('/')
        if not host or '@' in host or ':' in host or host.startswith('.') or host.endswith('.') or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-' for c in host):
            fail('Invalid authority host')
        path = '/' + path if separator else '/'
        if any(segment in ('.', '..') for segment in path.split('/')):
            fail('Ambiguous authority path')
        return host.lower(), path
    host, path = parts(url); prefix_host, prefix_path = parts(prefix)
    return host == prefix_host and (path == prefix_path or path.startswith(prefix_path if prefix_path.endswith('/') else prefix_path + '/'))


def identifier(value) -> str:
    text(value)
    if any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:' for c in value):
        fail('Invalid record identifier')
    return value
