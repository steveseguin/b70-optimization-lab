"""Replay byte-verified compressed receipts without mutable sibling evidence."""
import argparse
import gzip
import json
import os
from pathlib import Path
import resource
import shutil
import tempfile

from analyze_slack import P, analyze, demand, digest


def main():
    resource.setrlimit(resource.RLIMIT_AS, (2*1024**3, 2*1024**3))
    demand(os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice19 required')
    demand(set(os.sched_getaffinity(0)) <= set(range(8,16)) | set(range(24,32)), 'CPU affinity')
    demand(shutil.disk_usage('/').free >= 27_000_000_000, 'CPU preparation disk floor 27 GB')
    ap = argparse.ArgumentParser()
    ap.add_argument('report', type=Path)
    args = ap.parse_args()
    report = json.loads(args.report.read_text())
    demand(digest((P/'method/packet154_analyze.py').read_bytes()) == report['analyzer_sha256'], 'analyzer pin')
    demand(digest((P/'analyze_slack.py').read_bytes()) == report['method_sha256'], 'method pin')
    with tempfile.TemporaryDirectory(prefix='p156-replay-') as temporary:
        root = Path(temporary)
        input_path = summary_path = None
        seen = set()
        for entry in report['inputs']:
            relative = Path(entry['source'])
            retained = Path(entry['retained'])
            demand(not relative.is_absolute() and '..' not in relative.parts and
                   relative not in seen, 'unsafe/duplicate source path')
            demand(not retained.is_absolute() and '..' not in retained.parts,
                   'unsafe retained path')
            seen.add(relative)
            packed = (P/retained).read_bytes()
            demand(digest(packed) == entry['retained_sha256'] and len(packed) == entry['retained_bytes'], 'compressed receipt pin')
            raw = gzip.decompress(packed)
            demand(digest(raw) == entry['sha256'] and len(raw) == entry['bytes'], 'receipt byte identity')
            path = root/relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            if path.name == 'bracket-inputs.json':
                input_path = path
            elif path.name == 'bracket-summary.json':
                summary_path = path
        demand(input_path and summary_path, 'complete input/report missing')
        inputs = json.loads(input_path.read_text())
        summary = json.loads(summary_path.read_text())
        for view in inputs['views']:
            suffix = Path(view['output']).parts
            marker = suffix.index('experiments')
            view['output'] = str(root/Path(*suffix[marker:]))
        replay = analyze(inputs, summary)
        demand(all(replay[key] == report[key] for key in replay), 'retained replay changed')
    print(json.dumps(dict(passed=True, retained_files=len(report['inputs']),
        complete_original_split_equal=True, complete_packet156_bound_equal=True,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)))


if __name__ == '__main__':
    main()
