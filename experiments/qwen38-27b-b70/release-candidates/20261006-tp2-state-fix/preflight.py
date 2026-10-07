#!/usr/bin/env python3
"""Validate a TP2 state-fix runtime receipt without importing a runtime or launching anything.

An input manifest is evidence to check, never authority to qualify its own hashes.
The reviewed allowlist below is deliberately empty until exact runtime evidence exists.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

CANDIDATE = '20261006-tp2-state-fix'
SCHEMA = 'lab.qwen38.tp2-state-fix-runtime.v1'
PLUGIN = {'name': 'b70_gdn_state_width', 'entrypoint': 'b70_gdn_state_width:register',
          'distribution': 'b70-gdn-state-width', 'version': '0.1.0'}
FILES = {'kernel', 'gdn_library', 'plugin_loader', 'metadata_builder', 'xpu_ops',
         'overlay', 'entry_points', 'distribution_metadata'}
BUILDER_PARAMETERS = ['self', 'common_prefix_len', 'common_attn_metadata',
                      'num_accepted_tokens', 'num_decode_draft_tokens_cpu', 'fast_build']
# Reviewed code is the trust boundary. No CLI/env/manifest option may populate this.
# Future entries must bind image identity, every FILES hash, and a hash-bound
# qualification receipt from the exact candidate, with independently reviewed evidence.
QUALIFIED_RUNTIMES = {}


class Refused(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Refused(message)


def digest_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def valid_digest(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def validate_manifest(m):
    require(isinstance(m, dict), 'manifest must be an object')
    require(set(m) == {'schema', 'candidate', 'status', 'plugin', 'image_id',
                      'qualification_path', 'qualification_sha256', 'artifacts', 'activation'},
            'manifest field set must be complete and exact')
    require(m.get('schema') == SCHEMA and m.get('candidate') == CANDIDATE, 'wrong manifest identity')
    require(m.get('status') in ('pending', 'qualified'), 'invalid status')
    require(m.get('plugin') == PLUGIN, 'wrong plugin identity/version')
    require(isinstance(m.get('artifacts'), dict) and set(m['artifacts']) == FILES,
            'artifact set must be complete and exact')
    for role, row in m['artifacts'].items():
        require(isinstance(row, dict) and set(row) == {'path', 'sha256'}, f'invalid artifact: {role}')
        require(isinstance(row['path'], str) and bool(row['path']), f'missing path: {role}')
        require(row['sha256'] is None or valid_digest(row['sha256']), f'invalid digest: {role}')
    require(m.get('image_id') is None or (isinstance(m['image_id'], str)
            and m['image_id'].startswith('sha256:') and valid_digest(m['image_id'][7:])), 'invalid image ID')
    require(m.get('qualification_sha256') is None or valid_digest(m['qualification_sha256']),
            'invalid qualification digest')
    require(isinstance(m.get('qualification_path'), str), 'qualification_path must be a string')
    require(m.get('activation') is None or isinstance(m['activation'], dict), 'invalid activation receipt')
    if m['status'] == 'qualified':
        require(m['image_id'] is not None and valid_digest(m['qualification_sha256'])
                and bool(m['qualification_path']) and isinstance(m['activation'], dict),
                'qualified claim missing runtime evidence')
        require(all(valid_digest(row['sha256']) for row in m['artifacts'].values()),
                'qualified claim missing artifact digest')


def check(m):
    """Return only offline evidence consistency. This never authorizes serving."""
    validate_manifest(m)
    require(m['status'] == 'qualified', 'kernel/runtime qualification is pending; no serving allowed')
    trusted = QUALIFIED_RUNTIMES.get(m['image_id'])
    require(trusted is not None, 'runtime is not in the reviewed allowlist; supplied digests cannot qualify it')
    require(m['qualification_sha256'] == trusted['qualification_sha256'], 'unreviewed qualification receipt')
    for role, row in m['artifacts'].items():
        require(row['sha256'] == trusted['artifacts'][role], f'unreviewed artifact digest: {role}')
        require(digest_file(row['path']) == row['sha256'], f'artifact bytes differ: {role}')
    require(digest_file(m['qualification_path']) == m['qualification_sha256'], 'qualification receipt bytes differ')
    a = m['activation']
    require(a.get('candidate') == CANDIDATE and a.get('plugin') == PLUGIN, 'activation identity mismatch')
    require(a.get('image_id') == m['image_id'], 'activation belongs to another image')
    require(a.get('artifact_hashes') == trusted['artifacts'], 'activation belongs to different artifacts')
    require(a.get('enabled') is True and a.get('discovered_entrypoints') == [PLUGIN['entrypoint']],
            'plugin absent, excluded, duplicated or ignored')
    require(a.get('module_marker') == CANDIDATE and a.get('builder_marker') == CANDIDATE
            and a.get('group_marker') == CANDIDATE, 'plugin activation markers missing')
    require(a.get('builder_parameters') == BUILDER_PARAMETERS and type(a.get('group_anchor_count')) is int
            and a['group_anchor_count'] == 1,
            'runtime source contract mismatch')
    require(a.get('register_failure_propagated') is True and a.get('missing_plugin_rejected') is True,
            'pre-serving failure propagation unproved')
    # Bind activation to reviewed evidence, not freely editable values in this manifest.
    qualification = json.loads(Path(m['qualification_path']).read_text())
    require(qualification.get('activation') == a, 'activation is not bound to reviewed qualification receipt')
    return {'status': 'offline-evidence-consistent', 'serving_authorized': False,
            'next_gate': 'same-process and every-worker activation before model construction/listening'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = check(json.loads(args.manifest.read_text()))
    except (Refused, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'refused', 'serving_authorized': False, 'reason': str(exc)}))
        return 2
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
