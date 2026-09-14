#!/usr/bin/env python3
"""Independent CPU-only checks; invokes the workspace's real download script."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path.cwd()
SCRIPT = ROOT / 'tools/container-packet/download-model.sh'
assert SCRIPT.is_file(), 'Run acceptance from the repository workspace'

with tempfile.TemporaryDirectory(prefix='packet-path-acceptance-') as temporary:
    root = Path(temporary)
    commands = root / 'commands'
    commands.mkdir()
    curl = commands / 'curl'
    curl.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
destination = Path(args[args.index('-o') + 1])
destination.write_bytes(b'{}\\n')
with open(os.environ['CURL_RECEIPT'], 'a') as receipt:
    receipt.write(json.dumps({'url': args[-1], 'destination': str(destination)}) + '\\n')
''')
    curl.chmod(0o755)
    for index, folder in enumerate(('ordinary packet', "reader's packet", 'double "quoted" packet')):
        source = root / folder
        source.mkdir()
        manifest = source / 'model.json'
        manifest.write_text(json.dumps({'repository': 'example/model', 'revision': '0123456789abcdef',
                                       'lfs_files': [], 'small_files': [{'path': 'nested/config.json', 'bytes': 3}]}))
        destination = root / f'download {index}'
        receipt = root / f'curl-{index}.jsonl'
        env = {'PATH': f'{commands}:/usr/local/bin:/usr/bin:/bin', 'MODEL_MANIFEST': str(manifest),
               'MODEL_DIR': str(destination), 'CURL_RECEIPT': str(receipt), 'LANG': 'C.UTF-8'}
        result = subprocess.run(['bash', str(SCRIPT)], cwd=ROOT, env=env, text=True,
                                capture_output=True, timeout=15)
        assert result.returncode == 0, f'Valid manifest path {folder!r} failed:\n{result.stdout}\n{result.stderr}'
        assert (destination / 'nested/config.json').read_bytes() == b'{}\n', 'Downloaded file missing or changed'
        rows = [json.loads(line) for line in receipt.read_text().splitlines()]
        assert rows == [{'url': 'https://huggingface.co/example/model/resolve/0123456789abcdef/nested/config.json',
                         'destination': str(destination / 'nested/config.json')}], rows
print('PASS: ordinary, apostrophe, and double-quoted manifest paths preserve pinned download behavior')
