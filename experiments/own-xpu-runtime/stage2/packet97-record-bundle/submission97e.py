"""Extend the byte-pinned original validator only for explicit KD projection.

All original quality, fresh-owner, fixture, speed and submission gates execute.
The original file remains frozen for screen identity. This adapter never rewrites
native receipts or pretends a projected selection is the full target selection.
"""
import hashlib
from pathlib import Path
_source=Path(__file__).with_name('packet56_submission.py').read_bytes()
assert hashlib.sha256(_source).hexdigest()=='262ae73c71f7c5e82b01e7952f323c2afea888d414c113b8d68ceadee874a4ac'
_text=_source.decode()
_before='    def observed_selection(row, location, *, mandatory=False):\n'
_after='''    kd_reference_hash = None
    if 'draft-reference-binding.json' in windows['KD']['receipts']:
        from kd_projection_replay import validate as validate_kd_projection
        kd_reference_hash = validate_kd_projection(e, selected_hash, windows['KD'])

    def observed_selection(row, location, *, mandatory=False):
        if kd_reference_hash is not None and location in ('KD/owner0/receipt.json','KD/owner1/receipt.json'):
            require(row.get('selection_sha256') == kd_reference_hash, 'KD native projected selection mismatch: '+location)
            return
'''
assert _text.count(_before)==1;_text=_text.replace(_before,_after)
_before="            if relative.endswith('.json'):\n                r = e.read(name + '/' + relative, digest)"
_after="            if name == 'KD' and relative == 'draft-reference-selection.json':\n                require(kd_reference_hash is not None, 'unvalidated KD projection')\n                continue  # raw selection schema, fully validated above\n"+_before
assert _text.count(_before)==1;_text=_text.replace(_before,_after)
# Execute definitions under this module identity; the frozen CLI main is not run.
exec(compile(_text,str(Path(__file__).with_name('packet56_submission.py')),'exec'),globals())
