"""CPU-only report regression; synthetic tokens/timings are never measurements."""
import ast
import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import bracket_job  # Match the coordinator entry's import order.
import common as C
import cpu_seal
import screen
import packet137_report as report

P = Path(__file__).resolve().parent
OLD_COMMIT = '981a673c8'


def fixture(output, kind):
    choices = ['candidate'] if kind == 'smoke' else ['control', 'candidate', 'control', 'candidate', 'control']
    count = 64 if kind == 'smoke' else 128
    identity = dict(bracket=dict(kind=kind, views=[]), placement={}, lane='B', conditions={}, timing='token')
    views = []
    for index, choice in enumerate(choices):
        dest = output / 'run/views' / f'{index:02d}-{choice}'
        (dest / 'boundary').mkdir(parents=True)
        (dest / 'incident64').mkdir()
        selection = dict(choice=choice, selection_sha256=choice)
        identity['bracket']['views'].append(selection)
        boundary = []
        for rank in (0, 1):
            row = dict(passed=True, total_reset=True, cached_tokens=0, weight_uploads_after_load=0,
                       selection_sha256=choice, arena_descriptors_sha256='arena', weight_descriptors_sha256='weights')
            C.save(dest / 'boundary' / f'boundary-rank{rank}.json', row)
            boundary.append(row)
        incident = dict(passed=True, exact_oracle=True, cached_tokens=0, tokens=list(range(64)))
        C.save(dest / 'incident64/receipt.json', incident)
        incident['receipt_sha256'] = C.sha(dest / 'incident64/receipt.json')
        rows = []
        rate = 102.0 if choice == 'candidate' else 100.0
        for prompt in C.D.CHECK.PROMPT_IDS:
            rows.append(dict(prompt_id=prompt, prompt_class=C.METRICS.PROMPT_CLASSES[prompt], passed=True,
                exact_oracle=True, cached_tokens=0, repeat=1, tokens=list(range(count)),
                token_timestamps=[i/rate for i in range(count)], tok_s_1_100_intervals_after_ttft=rate,
                hits=32, guesses=64, acceptance=0.5))
            for rank in (0, 1):
                path = dest / prompt / f'rank{rank}/p105-transfers.jsonl'
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('')
            (dest / prompt / 'rank0/timings.jsonl').write_text('')
        for name in ['incident64', *C.D.CHECK.PROMPT_IDS]:
            path = dest / name / 'rank1/draft-rows.jsonl'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(dict(draft_position=0, confirmed_token=1, guess=2, head=True))+'\n')
        views.append(dict(index=index, choice=choice, selection_sha256=choice, output=str(dest), passed=True,
                          started_utc_ns=index*10+1, finished_utc_ns=index*10+2,
                          boundary=boundary, requests=rows, incident64=incident))
    C.save(output / 'run/bracket-inputs.json', dict(passed=True, kind=kind, views=views))
    C.save(output / 'run/device-isolation.json', dict(passed=True))
    (output / 'run/ranks/rank1').mkdir(parents=True)
    C.save(output / 'run/ranks/rank1/token-table-samples.json', dict(passed=True, samples=32, before_ready=True))
    C.save(output / 'run/report-inputs.json', dict(passed=True, device_isolation=dict(passed=True), lane='B',
             requests=views[0]['requests'], incident64=views[0]['incident64'], placement={}))
    return SimpleNamespace(output=output, profile='tp2', lane='B'), dict(boot_id='synthetic', started_utc_ns=1), identity, {}


def old_report():
    path = str((P/'screen.py').relative_to(C.ROOT))
    source = subprocess.run(['git', 'show', OLD_COMMIT+':'+path], check=True, capture_output=True,
                            text=True, stdin=subprocess.DEVNULL).stdout
    start = source.index("            proof = read(args.output / 'run/report-inputs.json')")
    end = source.index('            record.update(passed=True', start)
    body = '\n'.join(line[8:] for line in source[start:end].splitlines())
    namespace = dict(vars(screen))
    exec('def old_report(args, record, identity, coordination):\n'+body, namespace)
    return namespace['old_report']


def main():
    screen.cpu_gate()
    prior = sys.path[:]
    # Reproduce oracle()'s original path pollution and an already cached collision.
    sys.path.insert(0, str(P.parent))
    # The legacy compare bootstrap rechecks the seal; stub only that external
    # admission here, never the imported module or either reporting function.
    with patch.object(cpu_seal, 'verify', return_value={}):
        import compare
    sys.path[:] = [str(P.parent), *prior]
    assert Path(compare.__file__).resolve() == P.parent/'compare.py'
    rows = []
    try:
        with tempfile.TemporaryDirectory(prefix='p137b-report-') as tmp, \
             patch.object(C.D.CHECK, 'token_record', return_value=list(range(128))):
            for kind in ('smoke', 'bracket'):
                args = fixture(Path(tmp)/kind, kind)
                try:
                    old_report()(*args)
                except ImportError as error:
                    assert "finish_bracket" in str(error) and 'compare' in str(error)
                    old_failure = str(error)
                else:
                    raise AssertionError('old report unexpectedly passed')
                if kind == 'smoke':
                    with patch.object(report, 'finish_bracket', side_effect=AssertionError('smoke called bracket')):
                        screen.report_step(*args)
                else:
                    screen.report_step(*args)
                result = C.read(args[0].output/'bracket-summary.json')
                assert result['passed'] and result['kind'] == kind
                assert len(result['views']) == (1 if kind == 'smoke' else 5)
                assert not result['speed_evidence_eligible']
                rows.append(dict(kind=kind, passed=True, old_code_failure=old_failure))
                proof_path = args[0].output/'run/bracket-inputs.json'
                proof = C.read(proof_path)
                proof['views'][0]['requests'][0]['tokens'][0] = -1
                C.save(proof_path, proof)
                try:
                    screen.report_step(*args)
                except ValueError:
                    pass
                else:
                    raise AssertionError('corrupted report accepted')
    finally:
        sys.path[:] = prior
    # Run the actual oracle helper with only its expensive external checks stubbed.
    fake = SimpleNamespace(static_binding=lambda: {})
    for error in (None, ValueError('synthetic oracle refusal')):
        with patch.dict(sys.modules, shared_oracle=fake), \
             patch.object(cpu_seal.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stderr='')):
            if error:
                fake.static_binding = lambda: (_ for _ in ()).throw(error)
            before = sys.path[:]
            try:
                cpu_seal.oracle()
            except ValueError:
                assert error
            assert sys.path == before, 'oracle leaked module search path'
    # Full tree census, including historical modules; do not follow directory links.
    modules = {}
    imports = []
    for path in P.parent.rglob('*.py'):
        if path.is_file():
            modules.setdefault(path.stem, []).append(str(path.relative_to(P.parent)))
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.ImportFrom) and node.module:
                    imports.append((str(path.relative_to(P.parent)), node.module))
    duplicates = {k:v for k,v in modules.items() if len(v)>1}
    census = dict(duplicates=duplicates, ambiguous_from_imports=[r for r in imports if r[1] in duplicates],
                  mitigation='oracle restores sys.path on success/refusal; active report uses unique packet137_report')
    C.save(P/'evidence/report137b-collision-audit.json', census)
    sources = {str((P/n).relative_to(C.ROOT)):C.sha(P/n) for n in
               ('report_gate.py','screen.py','packet137_report.py','bracket_job.py','cpu_seal.py')}
    C.save(P/'evidence/report137b-gate.json', dict(passed=True, device_executed=False, synthetic=True,
        cases=rows, corrupted_tokens_refused=True, oracle_path_restored_on_success_and_failure=True, sources=sources))
    print('PASS: smoke and five-view bracket reports; both old-code failures; corruption refusals; import census')


if __name__ == '__main__':
    main()
