from p184_v5_exec_limits import install as _install_exec_limits
_install_exec_limits()
#!/usr/bin/env python3
"""Internal device worker for packet184's two-card checkpoint rows (one supervised screen job).

Every leg is a FRESH rank pair (one load, its own device-isolation monitor, its own serialized
drain), launched by the vendored packet56 pipeline.Transport exactly as the bundle-8 v5 worker
(tp2_worker.py) launches it. Checkpoint operations go through tp2_checkpoint.Pair; commit, inspect
and delete run the device-free tool binary (no SYCL). The worker stages raw receipts only
(run/lifecycle-inputs.json); every gate is judged by lifecycle_report.py after the lane release.

smoke      leg1: reference P x (K+M) [fresh-process reference, oracle-128 anchor], then P x K + save S1
           leg2: restore S1 (fresh pair) + resume M
lifecycle  leg1: P x K + save S1; NEW = S1 history + pending + T; NEW x (M+R) one-shot reference;
                 NEW x M one-shot + save SREF
           leg2: restore S1 + append T + M + save S2 (restore-then-save)
           leg3: restore S2 + resume R; then, in the same warm pair, restore S1 + append T + M + save S2b
           tools: inspect-metadata S1/S2/S2b/SREF, full inspect S2/S2b, delete S2b
P = incident-retrospective (87 tokens), K=256, M=128, T = the 126-token delta packet180 appended
(v5/lineage/append-delta.json), R=64.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
KINDS = dict(smoke=dict(K=256, M=128), lifecycle=dict(K=256, M=128, R=64))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def guesses(result):
    return [d.get('guess') for d in result.get('draft_rows', [])]


def compact(result):
    """The fields a report needs from one request (no rank traces)."""
    keep = ('tokens', 'stats', 'prompt_wall_ms', 'decode_wall_ms', 'ttft_ms', 'request_wall_ms', 'decode_tok_s',
            'submission_tok_s', 'resume_start', 'coordinator_request_seconds', 'prompt_tokens', 'output_tokens')
    row = {k: result.get(k) for k in keep}
    row['guesses'] = guesses(result)
    row['draft_rows'] = len(row['guesses'])
    return row


def write_samples(output, rows):
    """One JSON line per request (the report contract's sample stream; lifecycle-inputs.json holds all)."""
    with open(output / 'lifecycle-samples.jsonl', 'w') as f:
        for leg in rows['legs']:
            for name, r in leg.get('requests', {}).items():
                f.write(json.dumps(dict(leg=leg['leg'], request=name, tokens=len(r['tokens']), draft_rows=r['draft_rows'],
                                        resume_start=r.get('resume_start') or 0)) + '\n')


def append_event(path, row):
    with open(path, 'a') as f:
        f.write(json.dumps(row) + '\n')


def drain(transport, output, success, reason=None, root=None):
    """Packet153/183 worker drain, verbatim in behavior: a stop arriving during FINISH must drain
    inside the same spacing permit; the drain is serialized host-wide by conditions.Teardown."""
    from conditions import Teardown
    failure = None

    def refused(error):
        transport.teardown_refused = True
        transport.check = lambda: None
        try:
            transport.stop(error)
        finally:
            transport.close(False)
        return dict(cooperative_stop_requested=True, own_ranks_exited=True, drain_bound_seconds=65)
    kwargs = dict(on_refusal=refused) if root is None else dict(root=root, on_refusal=refused)
    with Teardown(output, **kwargs):
        try:
            if not success:
                transport.stop(reason)
                transport.check = lambda: None
            transport.close(success)
        except Exception as error:
            failure = error
            transport.stop(error)
            transport.check = lambda: None
            transport.close(False)
    if failure is not None:
        raise failure


def smoke(env, out, root):
    K, M = env.K, env.M
    pid, P = env.prompt()
    rows = dict(kind='smoke', prompt_id=pid, prompt_tokens=len(P), K=K, M=M, legs=[])
    with env.leg('leg1') as pair:
        pair.reset(out / 'leg1-reference')
        ref = pair.request(P, K + M)
        pair.reset(out / 'leg1-save')
        a = pair.request(P, K)
        s1 = pair.save(root, 's1', len(P))
        rows['legs'].append(dict(leg='leg1', requests=dict(reference=compact(ref), save_request=compact(a)), saves=dict(s1=s1)))
    with env.leg('leg2') as pair:
        rec, prompt = pair.restore(root, 's1', P, M, out / 'leg2-resume')
        b = pair.request(prompt, M, rec['position'])
        rows['legs'].append(dict(leg='leg2', restores=dict(s1=rec), requests=dict(resume=compact(b))))
    rows['oracle'] = env.oracle(pid)
    rows['tools'] = env.tools(root, metadata=['s1'], full=['s1'], delete=[])
    return rows


def lifecycle(env, out, root):
    K, M, R = env.K, env.M, env.R
    pid, P = env.prompt()
    rows = dict(kind='lifecycle', prompt_id=pid, prompt_tokens=len(P), K=K, M=M, R=R, legs=[])
    with env.leg('leg1') as pair:
        pair.reset(out / 'leg1-save')
        a = pair.request(P, K)
        s1 = pair.save(root, 's1', len(P))
        history, pending = list(pair.history), pair.pending
        delta, delta_meta = env.append_delta(history, pending)
        rows['append_delta'] = delta_meta
        new = history + [pending] + delta
        (out / 'new.txt').write_text(' '.join(map(str, new)) + '\n')
        pair.reset(out / 'leg1-new-reference')
        rnew = pair.request(new, M + R)
        pair.reset(out / 'leg1-new-oneshot')
        rref = pair.request(new, M)
        sref = pair.save(root, 'sref', len(new))
        rows['legs'].append(dict(leg='leg1', requests=dict(save_request=compact(a), new_reference=compact(rnew), new_oneshot=compact(rref)),
                                 saves=dict(s1=s1, sref=sref), new_length=len(new), delta_length=len(delta)))
    with env.leg('leg2') as pair:
        rec2, prompt2 = pair.restore(root, 's1', new, M, out / 'leg2-append')
        x = pair.request(prompt2, M, rec2['position'])
        s2 = pair.save(root, 's2', len(new), parent=rec2)
        rows['legs'].append(dict(leg='leg2', restores=dict(s1=rec2), requests=dict(append=compact(x)), saves=dict(s2=s2)))
    with env.leg('leg3') as pair:
        rec3, prompt3 = pair.restore(root, 's2', new, R, out / 'leg3-resume')
        y = pair.request(prompt3, R, rec3['position'])
        rec4, prompt4 = pair.restore(root, 's1', new, M, out / 'leg3-append-warm')
        x2 = pair.request(prompt4, M, rec4['position'])
        s2b = pair.save(root, 's2b', len(new), parent=rec4)
        rows['legs'].append(dict(leg='leg3', restores=dict(s2=rec3, s1=rec4), requests=dict(resume_s2=compact(y), append_warm=compact(x2)),
                                 saves=dict(s2b=s2b)))
    rows['oracle'] = env.oracle(pid)
    rows['tools'] = env.tools(root, metadata=['s1', 's2', 's2b', 'sref'], full=['s2', 's2b'], delete=['s2b'])
    return rows


class Env:
    """Shared leg/tool plumbing; DeviceEnv (rows) and CpuEnv (rehearsal) supply the launch."""

    def __init__(self, output, kind, tool, tokenizer, drain_root=None):
        self.output, self.kind, self.tool, self.tokenizer, self.drain_root = output, kind, tool, tokenizer, drain_root
        for k, v in KINDS[kind].items():
            setattr(self, k, v)
        self.pairs = 0

    def leg(self, name):
        env = self

        class Leg:
            def __enter__(self):
                env.check()
                self.pair = env.open_pair(name)
                env.pair = self.pair
                return self.pair

            def __exit__(self, kind, value, trace):
                leg_out = env.output / 'legs' / name
                env.pair = None
                if kind is None:
                    # As the bundle-8 worker: a final reset retains the last request's state
                    # (hashed archive, raw dump deleted) before FINISH.
                    self.pair.reset(leg_out / 'after-leg')
                env.before_drain(self.pair)
                drain(self.pair.t, leg_out, kind is None, value, env.teardown_root(name))
                if kind is None:
                    teardown = json.loads((leg_out / 'teardown.json').read_text())
                    require(teardown.get('drained') is True, 'leg teardown unproven: ' + name)
                env.after_drain(name)
                return False
        return Leg()

    def tools(self, root, metadata, full, delete):
        import tp2_checkpoint as T
        rows = {}
        for cid in metadata:
            code, row = T.tool(self.tool, '--checkpoint-inspect-metadata', root / cid)
            rows['metadata:' + cid] = dict(exit=code, ok=row.get('ok'), manifest_sha256=row.get('manifest_sha256'), error=row.get('error'))
        for cid in full:
            code, row = T.tool(self.tool, '--checkpoint-inspect', root / cid)
            rows['full:' + cid] = dict(exit=code, ok=row.get('ok'), manifest_sha256=row.get('manifest_sha256'),
                                       blobs_verified=(row.get('verified') or {}).get('blobs_verified'), error=row.get('error'))
        for cid in delete:
            # Keep the manifest and its index before the delete tool removes the checkpoint (the
            # report compares this checkpoint's blob hashes; packet180 kept the same copy).
            keep = self.output / (cid + '-manifest-copy')
            keep.mkdir()
            for leaf in ('manifest.json', 'fields.tsv'):
                (keep / leaf).write_bytes((root / cid / leaf).read_bytes())
            code, row = T.tool(self.tool, '--checkpoint-delete', root / cid)
            rows['delete:' + cid] = dict(exit=code, deleted=row.get('deleted'), files_removed=row.get('files_removed'), error=row.get('error'))
            code, row = T.tool(self.tool, '--checkpoint-inspect-metadata', root / cid)
            rows['after-delete:' + cid] = dict(exit=code, ok=row.get('ok'), error=row.get('error'))
        return rows

    # hooks
    def teardown_root(self, name):
        return self.drain_root     # None = conditions.DEFAULT_DRAIN_ROOT (device rows)

    def check(self):
        pass

    def before_drain(self, pair):
        pass

    def after_drain(self, name):
        pass


class DeviceEnv(Env):
    def __init__(self, identity, output, seconds, kind):
        from common import D, P56, ROOT, SUPPORT
        from devices import DeviceMonitor, masked_environment
        super().__init__(output, kind, HERE / 'build/tool/own-rt-ckpt-tool', HERE / 'tokenizer-identity.tsv')
        subprocess.run(['nice', '-n', '19', 'taskset', '-c', '8-15,24-31', 'python3', '-B', str(HERE.parent / 'shared_oracle.py'), '--require-complete'],
                       stdin=subprocess.DEVNULL, check=True, timeout=180)
        from p184_v5_placement import verify_identity
        self.placement, memory_gate = verify_identity(identity)
        sys.modules['memory_gate'] = memory_gate
        sys.path.insert(0, str(P56))
        import pipeline
        import suite
        suite.ROOT = ROOT
        import storage
        self.D, self.identity, self.seconds, self.suite, self.storage = D, identity, seconds, suite, storage
        manifest = D.oracle_inputs()
        self.entries = manifest['prompts']
        require(self.entries[0]['prompt_id'] == 'incident-retrospective', 'incident prompt first')
        adapter = output / 'adapter'
        (adapter / 'build').mkdir(parents=True)
        for name in ('selection.json', 'memory-plan.json'):
            (adapter / name).write_bytes((Path(identity['lineage']) / name).read_bytes())
        pipeline.P = adapter
        storage.P, storage.B = adapter, adapter / 'build'
        storage.admit = lambda extra, **unused: SUPPORT.storage(output, extra)
        self.args = pipeline.parser().parse_args(['--output', str(output), '--device', '--binary', identity['binary'], '--dispatch', identity['dispatch'],
            '--controller', 'native', '--draft', 'mtp', '--draft-rank', str(self.placement['draft_rank']),
            '--target-split', str(self.placement['target_split']), '--context', '4096', '--tokens', '64',
            '--retain-steps', 'none', '--timing', 'token', '--native-nice', '0', '--card', '0',
            '--seconds', str(seconds), '--wait-seconds', str(seconds)])
        self.args.timing = identity['timing']
        self.args.selection_sha256 = identity['selection_sha256']
        checker = suite.checker_module(P56.parent / 'packet49-integrate/oracle/suite_check.py')
        self.snapshots = suite.admit_inputs(self.entries, output, checker)
        self.args.input = self.snapshots[self.entries[0]['prompt_id']][0]
        self.environment = masked_environment(identity['lane'], dict(os.environ), inherited=True)
        self.stopped = []
        self.monitor = None
        self.pair = None
        self.handlers = {s: signal.signal(s, lambda n, f: self.stopped.append(n)) for s in (signal.SIGTERM, signal.SIGINT)}
        self.DeviceMonitor = DeviceMonitor

    def check(self):
        require(not self.stopped, 'coordinator stop requested')
        if self.monitor is not None:
            self.monitor.poll()

    def open_pair(self, name):
        import tp2_checkpoint as T
        leg_out = self.output / 'legs' / name
        leg_out.mkdir(parents=True)
        self.monitor = self.DeviceMonitor(self.identity['lane'], leg_out)
        self.args.output = leg_out / 'ranks'
        pair = T.open_pair(self.args, leg_out / 'ranks', self.identity['binary'], self.tokenizer, False,
                           environment=self.environment, check=self.check, launch_hook=self.monitor.register,
                           log=lambda row: append_event(leg_out / 'events.jsonl', row))
        pair.binary = self.tool
        pair.before_reset = lambda: self.storage.admit(self.storage.state_write_bytes(4096))
        pair.retainer = self.suite.retain_request_state
        self.monitor.poll(ready=True)
        self.pairs += 1
        return pair

    def before_drain(self, pair):
        if self.monitor is not None:
            self.monitor.poll(ready=True)
        self.monitor = None   # FINISH legitimately closes rank FDs and PIDs

    def prompt(self):
        e = self.entries[0]
        return e['prompt_id'], list(self.snapshots[e['prompt_id']][1])

    def oracle(self, prompt_id):
        return list(self.D.CHECK.token_record(self.D.ORACLE / 'results' / prompt_id))[:128]

    def append_delta(self, history, pending):
        d = json.loads((HERE / 'lineage/append-delta.json').read_text())
        meta = {k: d[k] for k in ('tp1_saved_history_sha256', 'tp1_pending_token', 'tp1_new_sha256', 'construction')}
        return list(d['delta']), dict(meta, delta_tokens=len(d['delta']), source='lineage/append-delta.json')


def run(identity, output, seconds, kind):
    from common import save
    root = output / 'checkpoints'
    root.mkdir(parents=True)
    env = None
    try:
        env = DeviceEnv(identity, output, seconds, kind)
        started = time.monotonic()
        rows = (smoke if kind == 'smoke' else lifecycle)(env, output, root)
        rows.update(passed=True, device_executed=True, legs_launched=env.pairs, worker_seconds=time.monotonic() - started,
                    placement=env.placement, lane=identity['lane'], tool_sha256=__import__('hashlib').sha256(env.tool.read_bytes()).hexdigest())
        save(output / 'lifecycle-inputs.json', rows)
        write_samples(output, rows)
        # The last leg's drain receipt stands for the job (screen requires run/teardown.json drained).
        last = sorted((output / 'legs').iterdir())[-1]
        (output / 'teardown.json').write_bytes((last / 'teardown.json').read_bytes())
        return 0
    except Exception as error:
        save(output / 'failure.json', dict(passed=False, error=str(error), kind=kind))
        pair = getattr(env, 'pair', None) if env is not None else None
        if pair is not None and hasattr(pair.t, 'stop_write') and not getattr(pair.t, 'closed', False):
            try:
                drain(pair.t, output / 'legs' / 'failure-drain', False, error)
            except Exception as drain_error:
                save(output / 'drain-error.json', dict(error=str(drain_error)))
            while any(p.poll() is None for p in pair.t.children):
                time.sleep(.25)
        return 1
    finally:
        if env is not None:
            for s, handler in env.handlers.items():
                signal.signal(s, handler)


if __name__ == '__main__':
    from common import read
    from conditions import lane_gate
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--identity', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=int, required=True)
    parser.add_argument('--kind', choices=tuple(KINDS), required=True)
    args = parser.parse_args()
    lane_gate(read(args.identity)['lane'])
    require((args.identity.parent / 'window.json').is_file(), 'outer screen admission required')
    raise SystemExit(run(read(args.identity), args.output, args.seconds, args.kind))
