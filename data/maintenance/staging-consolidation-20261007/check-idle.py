"""Read only /proc check; emits reference locations, never environment values."""
import json
import os
from pathlib import Path
import sys

audit = json.loads(Path(__file__).with_name('audit.json').read_text())
targets = [row['path'].encode() for row in audit['paths']]
matches, errors = [], []
count = 0
for process in Path('/proc').iterdir():
    if not process.name.isdigit() or int(process.name) == os.getpid():
        continue
    count += 1
    for field in ('cmdline', 'environ', 'maps', 'cwd', 'exe', 'fd'):
        path = process / field
        try:
            if field == 'fd':
                values = []
                for entry in path.iterdir():
                    try:
                        values.append(os.fsencode(os.readlink(entry)))
                    except FileNotFoundError:
                        pass
            elif field in ('cwd', 'exe'):
                values = [os.fsencode(os.readlink(path))]
            else:
                values = [path.read_bytes()]
            for target in targets:
                if any(target in value for value in values):
                    matches.append({'pid': int(process.name), 'field': field,
                                    'target': target.decode()})
        except (FileNotFoundError, ProcessLookupError):
            pass
        except OSError as error:
            errors.append({'pid': int(process.name), 'field': field,
                           'errno': error.errno})
report = {'effective_uid': os.geteuid(), 'processes_scanned': count,
          'matches': matches, 'errors': errors}
print(json.dumps(report, indent=2))
sys.exit(bool(matches or errors))
