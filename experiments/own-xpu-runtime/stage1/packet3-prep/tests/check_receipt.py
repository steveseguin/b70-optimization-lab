"""Validate emitted refusal and success, then reject unsafe success receipts."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import jsonschema

schema = json.loads(Path(__file__).with_name('teardown.schema.json').read_text())
jsonschema.Draft202012Validator.check_schema(schema)
rows = [json.loads(line) for line in subprocess.check_output([sys.argv[1], 'receipt'], text=True).splitlines()]
assert len(rows) == 2 and [r['status'] for r in rows] == ['refused', 'complete']
for row in rows:
    jsonschema.validate(row, schema)
for key, value in [('in_flight', 1), ('live_bytes', 1), ('idle_marker_complete', False),
                   ('safe_to_exit', False), ('exit_code', 75)]:
    bad = copy.deepcopy(rows[1]); bad[key] = value
    try:
        jsonschema.validate(bad, schema)
    except jsonschema.ValidationError:
        pass
    else:
        raise AssertionError(f'accepted unsafe receipt: {key}')
print('2 emitted receipts valid; 5 unsafe success mutations rejected')
