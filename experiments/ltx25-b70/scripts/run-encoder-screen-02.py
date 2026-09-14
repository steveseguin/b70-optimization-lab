#!/usr/bin/env python3
"""New evidence names for the unchanged encoder screen after the startup fix."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
SOURCE = Path(__file__).with_name('run-encoder-screen.py')
SOURCE_SHA256 = '4ec94d7e69c3d93b2caa740209f6a84ff35d56bdbbb8bf55f4b9782bacde10b0'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--server-run', type=Path, required=True)
    args = parser.parse_args()
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise RuntimeError('Original bounded client changed')
    spec = importlib.util.spec_from_file_location('encoder_screen_02_client', SOURCE)
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    client.CAMPAIGN = 'encoder-screen-02'
    client.identity_binding(args.packet, args.manifest_sha256, args.server_run)
    strict = json.loads((args.server_run / 'determinism-after-import.json').read_text())
    if not (strict['enabled'] is True and strict['warn_only'] is False and
            strict['server_identity_sha256'] == client.sha(args.server_run / 'server-identity.json')):
        raise RuntimeError('Strict startup receipt failed')
    with (args.server_run / 'encoder-screen-02-wrapper.json').open('x') as handle:
        json.dump({'client_sha256': SOURCE_SHA256, 'wrapper_sha256': client.sha(Path(__file__)),
                   'campaign': client.CAMPAIGN, 'strict_startup': strict,
                   'change': 'campaign/output names only; original schedule, comparison and retention unchanged'},
                  handle, indent=2)
        handle.write('\n')
    client.main()


if __name__ == '__main__':
    main()
