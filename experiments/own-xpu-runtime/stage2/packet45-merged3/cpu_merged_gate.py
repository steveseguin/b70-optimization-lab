#!/usr/bin/env python3
"""Fresh CPU-only merged runtime gates; no device binaries or discovery.

Default: 54 pipeline cases, two EOS references, three standalone sequential
references plus20 bucket-boundary terminal cases (79 fresh executions). --real adds a separately receipted, fixed
first-prompt eight-token oracle subset; it is not a suite performance gate.
"""
import argparse
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import time
import pipeline as pipe
from storage import admit, discard

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
B = P / 'build'
CONTEXTS = (256, 4096, 32768)
PROMPT = ([2, 5, 3, 7, 1] * 7)[:31]


def hash_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for part in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(part)
    return digest.hexdigest()


def assert_host_build(binary):
    binary = binary.resolve()
    mode = binary.parent.name
    assert mode in ('gnu-host', 'icpx-host') and binary.parent.parent == B
    receipt_path = P / ('build-' + mode + '-receipt.json')
    receipt = json.loads(receipt_path.read_text())
    assert receipt['passed'] and receipt['device_executed'] is False and receipt['mode'] == mode
    assert receipt['artifacts_sha256'][str(binary.relative_to(B))] == hash_file(binary)
    for name, expected in receipt['compiled_sources_sha256'].items():
        assert hash_file(ROOT / name) == expected, 'stale binary source: ' + name
    commands = binary.parent / 'compile_commands.json'
    assert hash_file(commands) == receipt['compile_commands_sha256']
    entries = json.loads(commands.read_text())
    model = [r for r in entries if Path(r['file']).name in ('main.cpp','entry-main.cpp')]
    assert model and all('OWN_RT_HOST_ONLY' in r.get('command', ' '.join(r.get('arguments', []))) for r in model)
    return dict(mode=mode, binary_sha256=hash_file(binary), build_receipt_sha256=hash_file(receipt_path),
                compiled_sources_sha256=receipt['compiled_sources_sha256'])


def anonymous_bytes(pids):
    total = 0
    for pid in pids:
        try:
            for line in Path('/proc', str(pid), 'status').read_text().splitlines():
                if line.startswith('RssAnon:'):
                    total += int(line.split()[1]) * 1024
        except FileNotFoundError:
            pass
    return total


def fixtures(root):
    files = sorted(root.glob('step*/layer-*.bf16'))
    for rank in (0, 1):
        files += sorted((root / f'rank{rank}').glob('step*/layer-*.bf16'))
    result = {}
    for file in files:
        key = '/'.join(file.parts[-2:])
        assert key not in result, 'duplicate layer evidence'
        result[key] = hash_file(file)
    assert result, 'missing layer evidence'
    return result


def target_state(root):
    result = {}; raw_events = {}
    for rank in (0, 1):
        directory = root / f'rank{rank}' / 'state-2147483647'
        files = sorted(directory.rglob('*'))
        assert any(f.suffix == '.bin' for f in files), 'missing full target state'
        result[f'rank{rank}/files'] = {f.name: hash_file(f) for f in files if f.is_file()}
        path = root / f'rank{rank}' / 'request-state-inventory.json'
        inventory = json.loads(path.read_text())
        # Exact model and host metadata. The sole excluded field counts issued
        # launches, necessarily different after a discarded half; retain it raw.
        raw_events[str(rank)] = dict(logical_event=inventory.pop('logical_event'), raw_sha256=hash_file(path))
        assert inventory['standalone_target_mutable'], 'missing raw standalone scratch hashes'
        result[f'rank{rank}/inventory'] = inventory
    return result, raw_events


def draft_state(root, rank):
    directory = root / f'rank{rank}' / 'draft-final-state'
    assert (directory / 'all-state.json').is_file(), 'missing complete draft mutable-state inventory'
    return {f.name: hash_file(f) for f in sorted(directory.rglob('*')) if f.is_file()}


class Campaign:
    def __init__(self, binary, dispatch, receipt, *, anonymous_limit=8_000_000_000):
        self.binary = binary.resolve(); self.dispatch = dispatch.resolve(); self.receipt = receipt
        assert anonymous_limit in (8_000_000_000,9_000_000_000), 'unsupported CPU gate anonymous limit'
        self.anonymous_limit = anonymous_limit
        self.build = assert_host_build(self.binary)
        self.affinity = sorted(os.sched_getaffinity(0)); self.rows = []; self.peak_anon = 0
        self.completed=False; self.campaign_error=None
        self.root = B / ('merged-gate-' + str(time.time_ns())); admit(100_000_000); self.root.mkdir()
        # Bind executed Python dependencies, not unrelated seal/test generators.
        dependencies = ('cpu_merged_gate.py', 'cpu_real_gate.py', 'pipeline.py',
                        'storage.py', 'memory_gate.py', 'memory_plan.py', 'suite_metrics.py')
        self.source_pins = {name: hash_file(P/name) for name in dependencies}
        self.source_pins['dispatch'] = hash_file(self.dispatch)

    def check(self, children=()):
        assert sorted(os.sched_getaffinity(0)) == self.affinity, 'affinity changed'
        used = anonymous_bytes([os.getpid(), *children]); self.peak_anon = max(used, self.peak_anon)
        assert used < self.anonymous_limit, f'CPU gate aggregate RssAnon reached {self.anonymous_limit} bytes'

    def seal(self):
        result = dict(schema='packet45.merged-cpu-gates.v1', passed=self.completed and bool(self.rows) and all(r['passed'] for r in self.rows),
            completed=self.completed,campaign_error=self.campaign_error,
            device_executed=False, arithmetic='iq3-p17-detmath-v2', no_speed_claim=True,
            build=self.build, source_pins=self.source_pins, cpu_affinity=self.affinity,
            peak_self_and_children_rssanon_bytes=self.peak_anon, anonymous_limit_bytes=self.anonymous_limit, cases=len(self.rows), rows=self.rows,
            state_comparison='all plan and alternate bytes, standalone target scratch hashes and host metadata; raw logical_event retained separately; no model-state masking')
        pipe.save(self.receipt, result)
        return result

    def retain(self, out, row):
        pipe.save(out / 'gate-case.json', row)
        self.rows.append(row); self.seal()  # Gate receipt exists before fixture deletion.
        row['scratch_archive'] = discard(out)
        self.seal()
        print(json.dumps({k: row[k] for k in ('name', 'passed')}), flush=True)

    def sequential(self, context):
        assert_host_build(self.binary); admit(150_000_000)
        out = self.root / f'sequential-{context}'; out.mkdir()
        tokens = out / 'input.txt'; tokens.write_text(' '.join(map(str, PROMPT)))
        dest = out / 'run'
        cmd = ['nice', '-n', '19', 'ionice', '-c', '3', str(self.binary), '--mini', '--pipeline-mini',
               '--context', str(context), '--max-new', '8', '--prompt-tokens', str(tokens),
               '--output', str(dest), '--dispatch', str(self.dispatch)]
        with (out / 'run.log').open('w') as log:
            child = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
            while child.poll() is None:
                try:
                    self.check([child.pid])
                except Exception:
                    child.terminate(); child.wait(timeout=65); raise
                time.sleep(.1)
            assert child.returncode == 0
        raw = json.loads((dest / 'receipt.json').read_text()); assert raw['passed'] and raw['device_executed'] is False
        signature = dict(tokens=raw['tokens'], fixtures=fixtures(dest)); assert len(signature['tokens']) == 8
        self.retain(out, dict(name=f'sequential-{context}', passed=True, context=context, signature=signature))
        return signature

    def case(self, name, context, rank, controller, mode='mtp', fault='none', count=8,
             eos=(), guesses=(), cancel=-1, real=None, prompt_tokens=None):
        assert_host_build(self.binary); admit(1_300_000_000 if real else 250_000_000)
        out = self.root / name; out.mkdir()
        argv = ['--binary', str(self.binary), '--output', str(out), '--context', str(context),
            '--tokens', str(count), '--draft', mode, '--draft-rank', str(rank), '--controller', controller,
            '--draft-fault', fault, '--dispatch', str(self.dispatch), '--seconds', '1800', '--wait-seconds', '1800',
            '--retain-steps', '1-8', '--cancel-launch', str(cancel)]
        argv += ['--input', str(real['input'])] if real else ['--mini']
        args = pipe.parser().parse_args(argv); args.draft = mode
        args.host_memory = 'layer-streaming' if real else 'resident'
        prompt = list(map(int, (real['input'] / 'tokens.txt').read_text().split())) if real else (list(prompt_tokens) if prompt_tokens is not None else PROMPT)
        children = []; transport = None
        try:
            transport = pipe.Transport.__new__(pipe.Transport)
            transport.__init__(args, out, check=lambda: self.check(children), launch_hook=children.append)
            result = pipe.request_run(transport, pipe.Draft(mode, guesses), prompt, count, eos)
            for owner in (0, 1):
                transport.call(owner, pipe.DUMP, position=2147483647)
            transport.close(True)
            result.update(passed=True, device_executed=False, arithmetic='iq3-p17-detmath-v2', no_speed_claim=True)
            pipe.save(out / 'receipt.json', result)
            state, raw_events = target_state(out)
            signature = dict(tokens=result['tokens'], fixtures=fixtures(out), target_state=state)
            if mode == 'mtp':
                signature['draft_state'] = draft_state(out, rank)
            timing_rows = [json.loads(line) for r in (0, 1)
                for file in (out / f'rank{r}').glob('*timing*.jsonl') for line in file.read_text().splitlines()]
            if cancel >= 0:
                assert any(row.get('cancelled') for row in timing_rows), 'cancellation injection did not exercise a cancelled half'
            return out, dict(name=name, passed=True, context=context, draft_rank=rank, controller=controller,
                draft=mode, fault=fault, prompt_tokens=len(prompt), count=count, eos=list(eos),
                cancel_launch=cancel, signature=signature, raw_inventory_events=raw_events,
                stats=result['stats'], guess_sequence=result['guess_sequence'],
                cancellation_observed=any(row.get('cancelled') for row in timing_rows))
        except Exception as error:
            if transport is not None and hasattr(transport, 'stop_write') and not transport.closed:
                transport.stop(error); transport.close(False)
            row = dict(name=name, passed=False, error=str(error), context=context, draft_rank=rank, controller=controller)
            self.retain(out, row)
            raise


def target_equal(left, right):
    for key in ('tokens', 'fixtures', 'target_state'):
        assert left[key] == right[key], 'target difference: ' + key


def mini(c):
    sequential = {}; controls = {}; normal = {}
    for context in CONTEXTS:
        sequential[context] = c.sequential(context)
        if context != CONTEXTS[0]:
            assert sequential[context] == sequential[CONTEXTS[0]], 'cross-capacity arithmetic changed'
        for rank in (0, 1):
            out, row = c.case(f'c{context}-r{rank}-control', context, rank, 'python', mode='none')
            control = row['signature']; controls[context, rank] = control
            assert control['tokens'] == sequential[context]['tokens'] and control['fixtures'] == sequential[context]['fixtures']
            c.retain(out, row)
            for controller in ('python', 'native'):
                for fault in ('none', 'wrong', 'late-error'):
                    out, row = c.case(f'c{context}-r{rank}-{controller}-{fault}', context, rank, controller, fault=fault)
                    signature = row['signature']; target_equal(signature, control)
                    if fault == 'none':
                        normal[context, rank, controller] = signature
                        if controller == 'native':
                            assert signature == normal[context, rank, 'python'], 'controller model/draft difference'
                    elif fault == 'wrong':
                        assert signature['draft_state'] == normal[context, rank, controller]['draft_state'], 'wrong guess changed draft confirmed state'
                    c.retain(out, row)
    context = 32768
    for rank in (0, 1):
        out, row = c.case(f'c{context}-r{rank}-eos-control', context, rank, 'python', mode='none', count=1)
        eos_control = row['signature']; c.retain(out, row)
        for controller in ('python', 'native'):
            out, row = c.case(f'c{context}-r{rank}-{controller}-suppress', context, rank, controller, fault='suppress')
            target_equal(row['signature'], controls[context, rank])
            assert row['signature']['draft_state'] == normal[context, rank, controller]['draft_state']
            c.retain(out, row)
            out, row = c.case(f'c{context}-r{rank}-{controller}-eos', context, rank, controller,
                              eos=(eos_control['tokens'][0],))
            target_equal(row['signature'], eos_control); c.retain(out, row)
        guesses = [(x + 1) % 16 for x in controls[context, rank]['tokens'][:-1]]
        out, row = c.case(f'c{context}-r{rank}-native-cancel', context, rank, 'native', mode='script', guesses=guesses, cancel=7)
        target_equal(row['signature'], controls[context, rank]); c.retain(out, row)
        out, row = c.case(f'c{context}-r{rank}-native-fresh', context, rank, 'native')
        assert row['signature'] == normal[context, rank, 'native'], 'fresh process changed model/draft state'
        c.retain(out, row)


def boundaries(c):
    """Terminal rollback must restore both32-position command-bank extents.

    The earlier31-token prompt ends before the bucket-crossing speculative
    half. Here the terminal token is produced at p31/p63 while the discarded
    rank0 candidate runs at p32/p64. Full-state equality includes both extents.
    """
    for boundary in (32,64):
        prompt=([2,5,3,7,1]*13)[:boundary]
        for rank in (0,1):
            prefix=f'boundary{boundary}-r{rank}'
            out,row=c.case(prefix+'-control',32768,rank,'python',mode='none',count=1,prompt_tokens=prompt)
            control=row['signature']
            inventory=control['target_state']['rank0/inventory']
            assert inventory['launch_extent']==boundary and inventory['alternate_launch_extent']==boundary
            # The comparison must catch precisely the metadata the pre-fix
            # rollback left behind. This is a comparator negative control,
            # not an execution of a fabricated historical binary.
            rejected=[]
            for field in ('launch_extent','alternate_launch_extent'):
                mutated=copy.deepcopy(control)
                mutated['target_state']['rank0/inventory'][field]=boundary+32
                try:target_equal(mutated,control)
                except AssertionError:rejected.append(field)
                else:raise AssertionError('full-state gate missed stale '+field)
            row['metadata_negative_controls']=rejected
            c.retain(out,row)
            token=control['tokens'][0]
            for controller in ('python','native'):
                for cancel in (-1,7):
                    label='terminal' if cancel<0 else 'cancel-terminal'
                    out,row=c.case(prefix+'-'+controller+'-'+label,32768,rank,controller,
                        mode='script',guesses=[(token+1)%16]*7,eos=(token,),cancel=cancel,prompt_tokens=prompt)
                    target_equal(row['signature'],control)
                    assert row['signature']['tokens']==[token]
                    assert row['stats']['guesses']==1,'terminal boundary must exercise one abandoned guess'
                    row.update(discarded_position=boundary,restored_launch_extent=boundary,
                        restored_alternate_launch_extent=boundary,full_terminal_state_identical=True)
                    c.retain(out,row)


def real(c, manifest, prompt_id):
    data = json.loads(manifest.read_text())
    entry = next((r for r in data['prompts'] if r['prompt_id'] == prompt_id), None) if prompt_id else data['prompts'][0]
    assert entry is not None, 'unknown real prompt'
    bundle = ROOT / entry['input_bundle']; oracle = ROOT / entry['oracle_directory']
    for leaf, expected in entry['input_bundle_hashes'].items():
        assert hash_file(bundle / leaf) == expected
    expected = json.loads((oracle / 'result.json').read_text())['tokens'][:8]
    refs = {}
    for context in CONTEXTS:
        for rank in (0, 1):
            for controller in ('python', 'native'):
                out, row = c.case(f'real-c{context}-r{rank}-{controller}', context, rank, controller, real=dict(input=bundle))
                signature = row['signature']; assert signature['tokens'] == expected
                assert len(signature['fixtures']) == 384
                assert all(value == hash_file(oracle / key) for key, value in signature['fixtures'].items())
                if controller == 'python':
                    refs[context, rank] = signature
                else:
                    assert signature == refs[context, rank], 'real controller model/draft state difference'
                row.update(oracle_subset_tokens=8, oracle_layer_fixtures=384, prompt_id=entry['prompt_id'],
                    manifest_sha256=hash_file(manifest), oracle_receipt_sha256=hash_file(oracle / 'result.json'))
                c.retain(out, row)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--binary', type=Path, default=B/'gnu-host/own-rt-iq3')
    ap.add_argument('--dispatch', type=Path, default=P/'dispatch-p45.json')
    ap.add_argument('--receipt', type=Path, default=P/'cpu-merged-gates.json')
    ap.add_argument('--real', action='store_true')
    ap.add_argument('--boundary-only', action='store_true')
    ap.add_argument('--real-manifest', type=Path, default=P.parent/'suite-inputs-20261012/suite-manifest.json')
    ap.add_argument('--real-prompt-id')
    a = ap.parse_args()
    assert not (a.real and a.boundary_only), 'choose one campaign mode'
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19 and os.environ.get('OMP_NUM_THREADS') == '2'
    resource.setrlimit(resource.RLIMIT_AS, (8_000_000_000, 8_000_000_000))
    B.mkdir(exist_ok=True)
    with (B/'cpu-merged-gate.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        campaign = Campaign(a.binary, a.dispatch, a.receipt)
        try:
            if a.real:real(campaign, a.real_manifest, a.real_prompt_id)
            elif a.boundary_only:boundaries(campaign)
            else:mini(campaign);boundaries(campaign)
        except Exception as error:
            campaign.campaign_error=str(error)
            # Comparison failures occur after child teardown. Preserve their
            # raw receipts and hashes before removing the one live scratch case.
            for scratch in list(campaign.root.iterdir()):
                if scratch.is_dir():
                    campaign.retain(scratch, dict(name=scratch.name, passed=False,
                        error=str(error), phase='case comparison or execution'))
            campaign.seal()
            raise
        campaign.completed=True
        result = campaign.seal()
        assert result['passed']
        discard(campaign.root)
        print(json.dumps(dict(passed=True, cases=result['cases'], receipt=str(a.receipt))), flush=True)

if __name__ == '__main__':
    main()
