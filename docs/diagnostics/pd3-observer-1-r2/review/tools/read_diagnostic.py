"""Strict offline diagnostic reader. Never joins captures by dump number alone.

Exit status 2 means warnings, incomplete or unidentified data; 0 means every
diagnostic capture in this input was read without an integrity warning.
COMPLETE concerns delivery of the bounded buffer, not electrical completeness.
"""
import argparse
import json
import math
import re
from pathlib import Path

MARKER = '[GAPGUARD_PD3_DIAG]'


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError('non-standard JSON constant: ' + value)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_identity(p):
    if not isinstance(p, dict):
        raise ValueError('diagnostic payload must be a JSON object')
    if type(p.get('schema')) is not int or p['schema'] != 2:
        raise ValueError('missing/unsupported schema; legacy dump numbers cannot establish capture identity')
    if p.get('kind') not in ('FAULT_CONTEXT', 'EVENTS'):
        raise ValueError('unknown or missing diagnostic kind')
    instance = p.get('instance_id')
    if not isinstance(instance, str) or not re.fullmatch(r'[0-9a-f]{32}', instance):
        raise ValueError('missing/invalid instance_id')
    if not integer(p.get('dump'), 1):
        raise ValueError('dump must be a positive integer')
    if p.get('capture_id') != '%s:%d' % (instance, p['dump']):
        raise ValueError('capture_id must match instance_id and dump')
    if not isinstance(p.get('build'), str) or not p['build']:
        raise ValueError('missing/invalid build')


def validate_payload(p):
    if p['kind'] == 'FAULT_CONTEXT':
        if not integer(p.get('records')) or not integer(p.get('capacity'), 1) or p['records'] > p['capacity']:
            raise ValueError('invalid header records/capacity')
        if not finite(p.get('captured_at')) or not integer(p.get('wrapper_errors')):
            raise ValueError('invalid header time/error counter')
        for name in ('context', 'detector', 'counters'):
            if not isinstance(p.get(name), dict):
                raise ValueError('missing/invalid header ' + name)
        if not isinstance(p.get('checkpoints'), list):
            raise ValueError('missing/invalid checkpoints')
        if 'last_callback' not in p or (p['last_callback'] is not None and
                                      (not isinstance(p['last_callback'], list) or len(p['last_callback']) != 3)):
            raise ValueError('missing/invalid last_callback')
    else:
        if not integer(p.get('offset')) or type(p.get('complete')) is not bool or not isinstance(p.get('records'), list):
            raise ValueError('invalid event offset/records/complete')
        for r in p['records']:
            if not isinstance(r, dict) or not integer(r.get('id'), 1) or not finite(r.get('eventtime')):
                raise ValueError('invalid event id/eventtime')
            for name in ('processing', 'effect', 'queued'):
                if name in r and not isinstance(r[name], dict):
                    raise ValueError('invalid event ' + name)
            for parent, child in (('processing', 'before'), ('effect', 'after')):
                if child in r.get(parent, {}) and not isinstance(r[parent][child], dict):
                    raise ValueError('invalid event ' + parent + '.' + child)


def read(path):
    """Return captures and explicit issues; orphan data never becomes a capture."""
    captures, issues = {}, []

    def issue(line, code, message, capture=None):
        item = dict(line=line, code=code, message=message)
        if capture is not None:
            item['capture_id'] = capture
        issues.append(item)
        if capture in captures:
            captures[capture]['issues'].append(item)
            captures[capture]['complete'] = False

    def unreadable(line, message, payload):
        capture = payload.get('capture_id') if isinstance(payload, dict) else None
        capture = capture if isinstance(capture, str) else None
        issue(line, 'UNREADABLE_DIAGNOSTIC', message, capture)
        if capture not in captures:
            # A damaged line with no usable identity invalidates still-open
            # captures conservatively; it cannot silently fill or finish one.
            for key, d in captures.items():
                if not d['closed']:
                    issue(line, 'UNATTRIBUTED_DAMAGE', 'unreadable diagnostic line while this capture was open', key)

    for line_number, line in enumerate(path.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
        if MARKER not in line:
            continue
        p = None
        try:
            p = json.loads(line.split(MARKER, 1)[1].strip(),
                           object_pairs_hook=unique_keys, parse_constant=reject_constant)
            validate_identity(p)
            validate_payload(p)
        except (ValueError, TypeError, OverflowError, RecursionError) as exc:
            unreadable(line_number, str(exc), p)
            continue

        key = p['capture_id']
        if p['kind'] == 'FAULT_CONTEXT':
            if key in captures:
                issue(line_number, 'DUPLICATE_HEADER', 'capture identity reused; neither header supersedes the other', key)
                continue
            captures[key] = dict(header=p, records=[], complete=False, closed=False,
                                 lines=[line_number], issues=[])
            continue

        if key not in captures:
            issue(line_number, 'ORPHAN_EVENTS',
                  'no readable preceding FAULT_CONTEXT for this capture; dump=%d offset=%d records=%d' %
                  (p['dump'], p['offset'], len(p['records'])), key)
            continue
        d = captures[key]
        h = d['header']
        d['lines'].append(line_number)
        if any(p[name] != h[name] for name in ('schema', 'instance_id', 'capture_id', 'dump', 'build')):
            issue(line_number, 'METADATA_MISMATCH', 'batch identity/build differs from header', key)
            continue
        if d['closed']:
            issue(line_number, 'EVENTS_AFTER_END', 'batch received after final batch', key)
            continue
        if p['offset'] != len(d['records']):
            issue(line_number, 'OFFSET_MISMATCH', 'expected offset %d, got %d (missing, duplicated or reordered batch)' %
                  (len(d['records']), p['offset']), key)
        if not p['records'] and not (h['records'] == 0 and p['offset'] == 0 and p['complete']):
            issue(line_number, 'EMPTY_BATCH', 'empty batch is only valid for an empty capture', key)
        d['records'].extend(p['records'])
        if len(d['records']) > h['records'] or p['offset'] + len(p['records']) > h['records']:
            issue(line_number, 'TOO_MANY_RECORDS', 'batch exceeds header record count', key)
        if p['complete']:
            d['closed'] = True
            if len(d['records']) != h['records']:
                issue(line_number, 'FINAL_COUNT_MISMATCH', 'final batch does not supply the header record count', key)
        d['complete'] = d['closed'] and len(d['records']) == h['records'] and not d['issues']

    for key, d in captures.items():
        if not d['complete']:
            issue(d['lines'][0], 'INCOMPLETE_CAPTURE',
                  'capture starting here is not complete at end of input; received=%d expected=%d final_seen=%s' %
                  (len(d['records']), d['header']['records'], d['closed']), key)
    if not captures and not issues:
        issue(None, 'NO_DIAGNOSTIC_DATA', 'no diagnostic records found in input')
    return dict(captures=captures, issues=issues)


def render(path, result=None):
    result = read(path) if result is None else result
    lines = ['SOURCE: ' + str(path),
             'Times below are Reactor monotonic seconds, not wall-clock timestamps.',
             'INTEGRITY: ' + ('WARNINGS — see line numbers below' if result['issues'] else 'OK')]
    for item in result['issues']:
        lines.append('WARNING line %s [%s] %s%s' %
                     (item['line'] if item['line'] is not None else '-', item['code'], item['message'],
                      ' capture=' + item['capture_id'] if 'capture_id' in item else ''))
    for key, d in result['captures'].items():
        h = d['header']
        lines += ['', 'CAPTURE %s dump=%s lines %s COMPLETE=%s' % (key, h['dump'], d['lines'], d['complete']),
                  'Captured: ' + str(h['captured_at']),
                  'Last callback [id,event,processed]: ' + str(h['last_callback']),
                  'Counters: ' + json.dumps(h['counters'], sort_keys=True),
                  'Observer errors: ' + str(h['wrapper_errors']),
                  'Fault detector: ' + json.dumps(h['detector'], sort_keys=True)]
        for r in d['records']:
            p = r.get('processing', {}); b = p.get('before', {})
            e = r.get('effect', {}); a = e.get('after', {})
            lines.append(' | '.join([
                'id=' + str(r['id']), 'event=' + str(r['eventtime']),
                'received=' + str(r.get('processed_at', 'UNRECORDED')),
                'return=' + json.dumps(r.get('return', {}), sort_keys=True),
                'E=' + str(p.get('E', r.get('queued', {}).get('E'))), 'ref=' + str(b.get('reference')),
                'state=' + str(b.get('state')) + '->' + str(a.get('state')),
                'VERIFY=' + str(b.get('start')) + '..' + str(b.get('end')),
                'count=' + str(b.get('count')) + '->' + str(a.get('count')),
                'electrical=' + str(e.get('electrical_transition')),
                'machine_accepted=' + str(e.get('machine_accepted')),
                'verify_counted=' + str(e.get('verify_counted'))]))
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    result = read(args.log)
    text = render(args.log, result)
    if args.output:
        args.output.write_text(text, encoding='utf-8')
    else:
        print(text, end='')
    return 2 if result['issues'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
