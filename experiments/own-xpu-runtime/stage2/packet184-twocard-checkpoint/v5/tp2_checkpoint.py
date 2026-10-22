#!/usr/bin/env python3
"""Packet184 two-card checkpoint coordinator (packet181's CLI shape over the two-rank pipeline).

The two-card engine is two rank processes (one per card) driven by the vendored packet56
pipeline.Transport (the same transport, rank argv and native controller the bundle-8 v5 harness
runs on device). This module adds the checkpoint operations on top of it:

  save                    --checkpoint-save ROOT --checkpoint-id ID --tokenizer-identity FILE
  same-generation resume  --checkpoint-restore ROOT --checkpoint-id ID --input <original prompt>
  append                  --checkpoint-restore ROOT --checkpoint-id ID --input <history + pending + delta>
  restore-then-save       a restore form plus --checkpoint-save ROOT2 --checkpoint-save-id ID2
  inspect / delete        the engine binary's device-free tools: --checkpoint-inspect[-metadata] DIR,
                          --checkpoint-delete DIR (no coordinator needed)

Two-card atomicity: the coordinator holds the sibling lock ROOT/ID.lock (exclusive for save,
shared for restore) across BOTH ranks. Save = stage on both ranks (each writes its own blob set),
then the device-free commit tool writes the manifest last (rename = visibility); a failed save
removes the invisible directory. Restore = the device-free full inspect (both rank sets hashed),
then verify on both ranks (each hashes its own set again and holds it), then apply on both ranks
only after both verified. Any refusal happens before the first upload; a rank refusal fails the
whole pair (fail-closed), the coordinator never continues with one restored rank.

CPU use (--mini) runs the real host binary as two rank processes; --device is refused here
(device rows go through tp2_lifecycle.py under the sealed screen supervisor).
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
PACKET = HERE.parent
P56 = PACKET / 'lineage-inputs/vendor/repo/experiments/own-xpu-runtime/stage2/packet56-draft-prefix'
if str(P56) not in sys.path:
    sys.path.insert(0, str(P56))
import pipeline  # noqa: E402  (vendored packet56 transport, unchanged)

NATIVE, RESET, CHECKPOINT = 10, 11, 15
PHASE_STAGE, PHASE_VERIFY, PHASE_APPLY = 1, 3, 4
DEVICE_EOS = (248044, 248046)
LABEL, CONTRACT = 'experimental-two-card', 'v1.2+p184'


class Refused(RuntimeError):
    def __init__(self, op, check, detail, rank=None):
        self.op, self.check, self.detail, self.rank = op, check, detail, rank
        super().__init__(f'checkpoint {op} refused: {check}: {detail}' + (f' (rank {rank})' if rank is not None else ''))


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def valid_id(cid):
    ok = bool(cid) and len(cid) <= 96 and cid[0].isascii() and cid[0].isalnum()
    ok = ok and all(c.isascii() and (c.isalnum() or c in '._-') for c in cid)
    return ok and not cid.endswith('.lock')


class Lock:
    """Sibling ROOT/ID.lock, flock, never blocks (the C++ tools' protocol)."""

    def __init__(self, root, cid, exclusive, op):
        self.path, self.fd = Path(root) / (cid + '.lock'), None
        for _ in range(3):
            fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o644)
            try:
                fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
            except BlockingIOError:
                os.close(fd)
                raise Refused(op, 'lock', f'checkpoint {cid} is in use; no checkpoint operation waits') from None
            held = os.fstat(fd)
            try:
                live = os.stat(self.path)
            except FileNotFoundError:
                live = None
            if live is not None and (held.st_dev, held.st_ino) == (live.st_dev, live.st_ino):
                self.fd = fd
                return
            os.close(fd)
        raise Refused(op, 'lock io', 'lock file replaced by concurrent deletes')

    def release(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.release()


def tool(binary, *args, timeout=600):
    """Run a device-free host tool of the engine binary; returns (exit code, parsed JSON line)."""
    cp = subprocess.run([str(binary), *map(str, args)], stdin=subprocess.DEVNULL, capture_output=True,
                        text=True, timeout=timeout, env={'PATH': '/usr/bin:/bin'})
    lines = [l for l in cp.stdout.splitlines() if l.startswith('{')]
    row = json.loads(lines[-1]) if lines else dict(ok=False, error=dict(check='io', detail=cp.stderr[-2000:]))
    return cp.returncode, row


def write_tokens(path, tokens):
    data = struct.pack('<%di' % len(tokens), *tokens)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o644)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def read_tokens(path):
    raw = Path(path).read_bytes()
    return list(struct.unpack('<%di' % (len(raw) // 4), raw))


def stop_token(token, mini):
    return (not mini) and token in DEVICE_EOS


@contextlib.contextmanager
def mini_selection(selection):
    """CPU only: the vendored Transport omits --selection for --mini ranks; append it."""
    if selection is None:
        yield
        return
    digest = sha(selection)
    real = subprocess.Popen

    def shim(cmd, *a, **k):
        if cmd and str(cmd[0]) == 'ionice' and '--mini' in cmd:
            cmd = list(cmd) + ['--selection', str(selection), '--selection-sha256', digest]
        return real(cmd, *a, **k)
    with patch.object(pipeline.subprocess, 'Popen', shim):
        yield


class Pair:
    """One loaded rank pair (one process lifetime) with the checkpoint operations."""

    def __init__(self, transport, args, binary, tokenizer, mini, log=None):
        self.t, self.a, self.binary, self.tokenizer, self.mini = transport, args, Path(binary), Path(tokenizer), mini
        self.log = log or (lambda row: None)
        self.inputs = 0
        self.history = None        # processed tokens of the last request
        self.pending = None        # its pending (last generated) token
        self.prompt = None         # that request's --input (prompt_length source)
        self.restored = None       # manifest of the restore that seeded the last request
        # Device rows wire the vendored suite discipline in here: storage admission before every reset
        # and retain_request_state (hash, archive, delete the raw state dump of the previous request).
        self.before_reset = None
        self.retainer = None
        self.retained = []

    # ------------------------------------------------------------------ plumbing
    def rank_dir(self, rank):
        return self.t.out / f'rank{rank}'

    def both(self, op, files=None, token=0):
        """Start op on both ranks (in parallel), wait for both; per-rank request files."""
        stems = []
        for rank in (0, 1):
            stem = self.rank_dir(rank) / f'checkpoint-{self.t.seq[rank] + 1}'
            if files is not None:
                Path(str(stem) + '.txt').write_text(''.join(f'{k}\t{v}\n' for k, v in files[rank].items()))
            stems.append(stem)
        self.t.start(1, op, token)
        self.t.start(0, op, token)
        errors = []
        for rank in (0, 1):
            try:
                self.t.wait(rank)
            except Exception as error:   # a refused rank raises inside its process and exits
                errors.append((rank, error))
                break
        if errors:
            # Two-card atomicity: stop the pair and let the surviving rank exit (bounded, the
            # transport's own 65 s drain) before anything acts on the refusal, e.g. before a failed
            # save removes its invisible directory.
            try:
                self.t.stop(errors[0][1])
            except Exception:
                pass
            end = time.monotonic() + 65
            while any(c.poll() is None for c in self.t.children) and time.monotonic() < end:
                time.sleep(.05)
            for rank in (0, 1):
                refusal = Path(str(stems[rank]) + '-refusal.json')
                if refusal.exists():
                    row = json.loads(refusal.read_text())
                    raise Refused({1: 'save', 3: 'restore', 4: 'restore'}.get(token, 'checkpoint'),
                                  row['check'], row['detail'], rank) from errors[0][1]
            raise errors[0][1]
        return [json.loads(Path(str(s) + '.json').read_text()) for s in stems]

    def reset(self, destination):
        require = pipeline.require
        require(not any(self.t.pending), 'reset with pending commands')
        if self.before_reset:
            self.before_reset()
        previous = getattr(self.t, 'request_output', self.t.out)
        destination = Path(destination).resolve()
        destination.mkdir(parents=True, exist_ok=True)
        for rank in (0, 1):
            metadata = self.rank_dir(rank) / f'reset-{self.t.seq[rank] + 1}.txt'
            metadata.write_text(str(destination / f'rank{rank}') + '\n\n')
            self.t.call(rank, RESET)
        if self.retainer:
            self.retained.append(self.retainer(previous))
        self.t.request_output = destination
        self.t.mapping[:pipeline.SHARED] = bytes(pipeline.SHARED)
        self.t.trace = []
        self.t.metrics = [dict(busy_ms=0., handover_ms=0., calls=0, gpu_ms=0.) for _ in range(2)]
        self.t.last_complete = [0., 0.]
        self.history = self.pending = self.prompt = self.restored = None

    def request(self, prompt, count, start=0):
        """One native-controller request; start>0 only right after a restore applied at `start`."""
        resume = self.t.shared_path.parent / 'native-resume.txt'
        pipeline.require(not resume.exists(), 'stale native-resume.txt')
        if start:
            resume.write_text(f'{start}\n')
        provider = pipeline.Draft(self.a.draft, [])
        eos = () if self.mini else DEVICE_EOS
        started = time.monotonic()
        result = pipeline.request_run(self.t, provider, list(prompt), count, eos, True, False)
        pipeline.require(not resume.exists(), 'rank 0 did not consume native-resume.txt')
        tokens = result['tokens']
        pipeline.require(tokens, 'request produced no token')
        self.history = list(prompt) + tokens[:-1]
        self.pending = tokens[-1]
        result['coordinator_request_seconds'] = time.monotonic() - started
        result['resume_start'] = start
        return result

    def dump(self):
        """CPU gates only: the engine's own state dump + request_state_inventory at this boundary
        (DUMP with position 2147483647), written into each rank's current request directory."""
        for rank in (0, 1):
            self.t.call(rank, pipeline.DUMP, position=2147483647)

    # ------------------------------------------------------------------ save
    def save(self, root, cid, prompt_length, parent=None):
        op = 'save'
        root = Path(root)
        if not valid_id(cid):
            raise Refused(op, 'id', 'invalid checkpoint id ' + cid)
        pipeline.require(self.history is not None, 'save needs a completed request on this pair')
        root.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        with Lock(root, cid, True, op):
            d = root / cid
            if d.exists() or d.is_symlink():
                raise Refused(op, 'never overwrite', f'checkpoint {cid} already exists in {root}')
            d.mkdir()
            try:
                (d / 'rank0').mkdir()
                (d / 'rank1').mkdir()
                write_tokens(d / 'tokens.bin', self.history)
                files = [dict(dir=d, position=len(self.history), pending=self.pending)] * 2
                stage = self.both(CHECKPOINT, files, PHASE_STAGE)
                args = ['--checkpoint-commit', d, '--tokenizer-identity', self.tokenizer, '--prompt-length', prompt_length]
                if parent:
                    args += ['--parent-id', parent['checkpoint_id'], '--parent-manifest-sha256', parent['manifest_sha256']]
                code, commit = tool(self.binary, *args)
                if code or not commit.get('ok'):
                    err = commit.get('error') or {}
                    raise Refused(op, err.get('check', 'commit'), err.get('detail', 'commit tool failed'))
            except BaseException:
                if not (d / 'manifest.json').exists():
                    shutil.rmtree(d, ignore_errors=True)
                raise
        manifest = json.loads((d / 'manifest.json').read_text())
        row = dict(checkpoint_id=cid, manifest_sha256=commit['manifest_sha256'], position=len(self.history),
                   pending_token=self.pending, bytes=commit['save_bytes'], seconds=time.monotonic() - started,
                   stage=[dict(rank=s['rank'], bytes=s['bytes'], blobs=s['blobs'], stage_seconds=s['stage_seconds']) for s in stage],
                   coverage=[s['coverage'] for s in stage], host_fields=[s['host_fields'] for s in stage],
                   commit_seconds=commit['commit_seconds'], parent_checkpoint_id=(parent or {}).get('checkpoint_id'),
                   label=manifest['label'], contract=manifest['contract'], operation=manifest['lineage']['operation'])
        self.log(dict(event='checkpoint-save', **{k: v for k, v in row.items() if k not in ('coverage', 'host_fields')}))
        return row

    # ------------------------------------------------------------------ restore
    def restore(self, root, cid, input_tokens, max_new, destination, precheck=True, hold_lock=True):
        """Reset, full device-free precheck, verify both ranks, apply both. Returns the restore record
        and the controller prompt; the caller then runs request(prompt, max_new, start=position).
        precheck=False / hold_lock=False exist for CPU refusal tests of the rank-side checks only."""
        op = 'restore'
        root, d = Path(root), Path(root) / cid
        if not valid_id(cid):
            raise Refused(op, 'id', 'invalid checkpoint id ' + cid)
        started = time.monotonic()
        if precheck:
            code, inspect = tool(self.binary, '--checkpoint-inspect', d)
            if code or not inspect.get('ok'):
                err = inspect.get('error') or {}
                raise Refused(op, err.get('check', 'inspect'), err.get('detail', 'precheck failed'))
        else:
            text = (d / 'manifest.json').read_bytes()
            inspect = dict(manifest=json.loads(text), manifest_sha256=hashlib.sha256(text).hexdigest())
        manifest = inspect['manifest']
        precheck_seconds = time.monotonic() - started
        self.reset(destination)
        self.inputs += 1
        input_path = self.t.out / f'checkpoint-input-{self.inputs}.txt'
        input_path.write_text(' '.join(map(str, input_tokens)) + '\n')
        with (Lock(root, cid, False, op) if hold_lock else contextlib.nullcontext()):
            files = [dict(dir=d, tokenizer_identity=self.tokenizer, max_new=max_new, input=input_path)] * 2
            verify = self.both(CHECKPOINT, files, PHASE_VERIFY)
            pipeline.require(len({(v['operation'], v['controller_prompt_sha256'], v['manifest_sha256']) for v in verify}) == 1,
                             'ranks disagree on the restore operation')
            apply = self.both(CHECKPOINT, None, PHASE_APPLY)
        history = read_tokens(d / 'tokens.bin')
        position, pending = manifest['token_state']['position'], manifest['token_state']['next_token']
        operation = verify[0]['operation']
        prompt = list(input_tokens) if operation == 'append' else history + [pending]
        digest = hashlib.sha256(struct.pack('<%di' % len(prompt), *prompt)).hexdigest()
        pipeline.require(digest == verify[0]['controller_prompt_sha256'], 'controller prompt differs from the ranks\' derivation')
        self.restored = manifest
        record = dict(checkpoint_id=cid, manifest_sha256=inspect['manifest_sha256'], operation=operation, position=position,
                      pending_token=pending, pending_is_stop=stop_token(pending, self.mini), input_length=len(input_tokens),
                      appended_length=len(input_tokens) - position - 1 if operation == 'append' else 0,
                      restore_seconds=time.monotonic() - started, precheck_seconds=precheck_seconds,
                      restored_bytes=sum(a['uploaded_bytes'] for a in apply),
                      ranks=[dict(rank=v['rank'], verify_seconds=v['verify_seconds'], bytes_read=v['bytes_read'],
                                  apply_seconds=a['apply_seconds'], uploaded_bytes=a['uploaded_bytes']) for v, a in zip(verify, apply)])
        self.log(dict(event='checkpoint-restore', **{k: v for k, v in record.items() if k != 'ranks'}))
        return record, prompt


def open_pair(args, out, binary, tokenizer, mini, selection=None, environment=None, check=None, launch_hook=None, log=None):
    """Launch one rank pair through the vendored Transport (same argv as the v5 device harness)."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    transport = pipeline.Transport.__new__(pipeline.Transport)
    with mini_selection(selection if mini else None):
        try:
            pipeline.Transport.__init__(transport, args, out, environment, check, launch_hook)
        except BaseException:
            if hasattr(transport, 'stop_write'):
                try:
                    transport.stop('launch failure')
                finally:
                    transport.close(False)
            raise
    return Pair(transport, args, binary, tokenizer, mini, log)


def cpu_args(binary, out, context=256, seconds=600):
    """Pipeline arguments for a CPU (host-only, --mini) rank pair with the MTP draft on rank 1."""
    a = pipeline.parser().parse_args(['--binary', str(binary), '--output', str(out), '--mini', '--context', str(context),
                                      '--tokens', '1', '--seconds', str(seconds), '--wait-seconds', '300', '--native-nice',
                                      str(os.getpriority(os.PRIO_PROCESS, 0)), '--draft', 'mtp', '--draft-rank', '1',
                                      '--target-split', '0', '--retain-steps', 'none', '--controller', 'native'])
    a.host_memory = 'resident'
    return a


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--binary', type=Path, default=HERE / 'build/gnu-host/own-rt-iq3')
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--input', type=Path, required=True, help='whitespace-separated token ids')
    ap.add_argument('--max-new', type=int, required=True)
    ap.add_argument('--tokenizer-identity', type=Path, required=True)
    ap.add_argument('--checkpoint-save', type=Path)
    ap.add_argument('--checkpoint-id')
    ap.add_argument('--checkpoint-restore', type=Path)
    ap.add_argument('--checkpoint-save-id')
    ap.add_argument('--mini', action='store_true')
    ap.add_argument('--selection', type=Path)
    ap.add_argument('--context', type=int, default=256)
    ap.add_argument('--device', action='store_true')
    a = ap.parse_args(argv)
    pipeline.require(not a.device, 'device two-card checkpoint runs go through tp2_lifecycle.py under the sealed screen supervisor')
    pipeline.require(a.mini, 'this CLI runs CPU (--mini) rank pairs only')
    pipeline.require(bool(a.checkpoint_save or a.checkpoint_restore) and bool(a.checkpoint_id), 'a checkpoint operation and --checkpoint-id are required')
    restore_then_save = bool(a.checkpoint_restore and a.checkpoint_save)
    pipeline.require(restore_then_save == bool(a.checkpoint_save_id), '--checkpoint-save-id goes with a restore plus --checkpoint-save')
    tokens = list(map(int, a.input.read_text().split()))
    out = a.output.resolve()
    pair = open_pair(cpu_args(a.binary, out / 'pair', a.context), out / 'pair', a.binary, a.tokenizer_identity, True, a.selection)
    result, ok = dict(schema='packet184.tp2-checkpoint-cli.v1', label=LABEL, contract=CONTRACT, device_executed=False), False
    try:
        start, restore = 0, None
        if a.checkpoint_restore:
            restore, prompt = pair.restore(a.checkpoint_restore, a.checkpoint_id, tokens, a.max_new, out / 'request')
            start = restore['position']
        else:
            pair.reset(out / 'request')
            prompt = tokens
        request = pair.request(prompt, a.max_new, start)
        result.update(tokens=request['tokens'], restore=restore, prefill=dict(
            path='incremental' if len(prompt) > start else None, first_position=start, tokens=len(prompt) - start))
        if a.checkpoint_save:
            parent = restore if restore_then_save else None
            sid = a.checkpoint_save_id if restore_then_save else a.checkpoint_id
            result['save'] = pair.save(a.checkpoint_save, sid, len(tokens), parent)
        ok = True
    except Refused as error:
        result.update(refused=dict(op=error.op, check=error.check, detail=error.detail, rank=error.rank))
    finally:
        pair.t.close(ok) if ok else (pair.t.stop('checkpoint cli failure'), pair.t.close(False))
    result['passed'] = ok
    (out / 'result.json').write_text(json.dumps(result, indent=1) + '\n')
    print(json.dumps({k: result[k] for k in ('passed', 'tokens', 'refused') if k in result}))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
