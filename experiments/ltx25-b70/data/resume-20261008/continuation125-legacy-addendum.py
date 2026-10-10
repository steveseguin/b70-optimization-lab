#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Read one bounded legacy-session snapshot without replacing the first capture."""
from datetime import datetime, timezone
import json
from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
analysis = runpy.run_path(str(here / 'continuation125-evidence-analysis.py'))
run = analysis['collect']('s123b-legacy-live01')
result = {'schema': 'ltx.continuation125.cpu-timeline-addendum.v1',
          'observed_utc': datetime.now(timezone.utc).isoformat(),
          'session': 's123b-legacy-live01', 'run': run, 'sources': analysis['SOURCES']}
(here / 'continuation125-legacy-addendum.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps({key: run[key] for key in ('manifest_rows', 'analysis_rows', 'analysis_range', 'ten_second_model', 'conditioning_sources')}, indent=2))
for parity, values in run['parity'].items():
    print(parity, {key: values[key]['median'] for key in ('period_to_next', 'next_commit_to_first_served', 'request_snapshot_inner', 'own_fifo')} )
