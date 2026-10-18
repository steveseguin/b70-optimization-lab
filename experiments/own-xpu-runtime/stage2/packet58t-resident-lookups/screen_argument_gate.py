"""CPU replay of both real Python entry points up to intercepted native exec.

Operational state is synthetic. Real argument parsers, view validation, oracle
inputs, K1 miss selection, memory admission, masks and native argv run unchanged.
Each probe is isolated; audit hooks deny execution, device opens and writes
outside its scratch. No synthetic receipt can be consumed by a device chain.
"""
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

P = Path(__file__).resolve().parent
ROOT = P.parents[3]


class Reached(BaseException):
    pass


class Forbidden(BaseException):
    pass


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def sandbox(tmp):
    def audit(event, values):
        if event == 'open' and isinstance(values[0], (str, bytes)):
            path = Path(os.fsdecode(values[0])).absolute()
            if str(path).startswith('/dev/dri/') or path.suffix == '.gguf':
                raise Forbidden('device/model payload open forbidden')
            if (values[2] or 0) & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                if path != Path('/dev/null') and not path.resolve().is_relative_to(tmp):
                    raise Forbidden('write outside CPU scratch: ' + str(path))
        if event in ('subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn'):
            raise Forbidden('execution forbidden in argument probe')
    sys.addaudithook(audit)


def sources():
    files = [*P.glob('*.py'), P/'views.json', P/'oracle-binding.json',
             P/'selections/resident.json', P/'dispatch-speed6.json']
    return {str(f.relative_to(ROOT)): sha(f) for f in files}


def probe(name, miss, candidate):
    # Capture all resource limits BEFORE runtime imports. No cap is installed in
    # this tiny intercepted-exec process: it must test the actual unlimited AS
    # inherited by the future coordinator. Peak RSS is checked by the parent.
    from exec_limits import snapshot, check
    before = snapshot()
    import screen_runner as Q
    import screen_window as W
    import screen_driver as D
    import screen_views as V
    assert snapshot() == before
    V.validate(candidate)
    native_hashes = {str(f.relative_to(P)):sha(f) for f in (P/'build/device').glob('*') if f.name in ('own-rt-iq3','p58-cache-fixtures')}
    assert len(native_hashes)==2
    model = not name.startswith('K1')
    mode = name if model else 'K1'
    with tempfile.TemporaryDirectory(prefix='packet58p-arguments-') as directory:
        tmp = Path(directory)
        sandbox(tmp)
        packet = tmp/'packet'; packet.mkdir(); (packet/'evidence').mkdir()
        (packet/'build').symlink_to(P/'build', target_is_directory=True)
        for leaf in ('oracle-binding.json', 'screen_driver.py', 'dispatch-speed6.json', 'k1-cpu.json'):
            shutil.copyfile(P/leaf, packet/leaf)
        build = dict(artifacts=native_hashes, synthetic_build_envelope=True)
        (packet/'build-receipt.json').write_text(json.dumps(build))
        out = packet/'evidence/chain'
        # Only previous operational receipts are synthetic. Real K1 parser and
        # bandwidth selection consume these bytes, including both miss branches.
        for index, stage in enumerate(Q.ORDER):
            if stage == name:
                continue
            dest = out/stage; (dest/'run').mkdir(parents=True)
            (dest/'window.json').write_text('{}')
            native = dict(passed=True, safe_to_exit=True, device_executed=True,
                zero_copy_supported=True, zero_copy_bytes_equal=True,
                mixed_bytes_equal=True, streamed_bytes_equal=True,
                exact_output_sha256=D.read(P/'k1-cpu.json')['exact_output_sha256'],
                cold_rotation=True, working_set_bytes=128*1024**2,
                bytes_per_iteration=25_000_000, host_ms=1 if miss == 'zero-copy' else 3,
                vram_ms=.1, streamed_ms=1.1)
            (dest/'run/k1.json').write_text(json.dumps(native))
        command = Q.commands(out, 0, '2026-01-01T00:00:00Z', '', candidate)[name]
        argv = command[command.index(str(P/'screen_window.py'))+1:]
        observations = []
        env = {'PATH':'/usr/bin:/bin', 'OMP_NUM_THREADS':'2'}

        class Admission:
            def __init__(self, *args):
                self.scope = 'whole-host'
                self.record = dict(synthetic=True, scope=self.scope)
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def before_launch(self, recheck): recheck()

        def predecessor(path, expected, identity):
            return dict(identity, window=expected, pid=100+Q.ORDER.index(path.parent.name),
                process_start_ticks=1, miss_path=miss,
                postload_memory=dict(W.M.seed_observation(), complete_postload=True))

        def capture(cmd, *args, **kwargs):
            limits = check()  # actual getrlimit at every intercepted exec
            observations.append(dict(argv=list(map(str, cmd)), limits=limits))
            if model and len(observations) == 1:
                assert Path(cmd[2]).name == 'screen_driver.py'
                with patch.dict(os.environ, kwargs['env'], clear=True):
                    result = D.main(cmd[3:])
                raise AssertionError('suite driver did not reach native exec: ' + str(result))
            assert '--authorized-device-window' in cmd
            assert cmd[cmd.index('--card')+1] == '0'
            if model:
                assert cmd[cmd.index('--selection')+1] == str(V.selection('tile16'))
                assert cmd[cmd.index('--selection-sha256')+1] == V.digest('tile16')
                assert cmd[cmd.index('--miss-path')+1] == miss
                assert cmd[cmd.index('--cards')+1] == '1'
                assert cmd[cmd.index('--context')+1] == '4096'
                assert cmd[cmd.index('--max-new')+1] == ('8' if mode in ('KD','W2m') else '128')
                assert cmd[cmd.index('--retain-steps')+1] == ('1-8' if mode in ('KD','W2m','WS') else 'none')
                bt=Path(cmd[cmd.index('--bracket-inputs')+1]).read_text().splitlines()
                assert [x.split()[0] for x in bt]==['A0','B0','A1']
                assert [x.split()[2] for x in bt]==[V.digest(v) for _,v in V.bracket(candidate)]
                table = Path(cmd[cmd.index('--suite-inputs')+1]).read_text().splitlines()
                assert all(len(x.split())==3 for x in table)
                assert len(table) == (1 if mode in ('KD','W2m') else 12)
            else:
                assert cmd[cmd.index('--down-layout')+1] == 'down-tile16'
                assert cmd[cmd.index('--iterations')+1] == '20'
            raise Reached()

        with ExitStack() as stack:
            changes = [patch.object(W,'HERE',packet), patch.object(D,'HERE',packet),
                patch.object(W,'build_gate',return_value=build),
                patch.object(W,'user_unit_gate'), patch.object(W,'closed_environment',return_value=env),
                patch.object(W,'prerequisite',side_effect=predecessor),
                patch.object(W.SUPPORT,'storage',return_value={'synthetic':True}),
                patch.object(W,'memory_fence',return_value={'synthetic':True}),
                patch.object(W,'selected_clients',return_value={'synthetic':True}),
                patch.object(W.S,'journal',return_value=('',None)),
                patch.object(W.S,'ldd_preflight',return_value={'intercepted':True}),
                patch.object(W.M,'meminfo',return_value={'MemAvailable':128*1024**3}),
                patch.object(W.A,'Admission',Admission),
                patch.object(W.A.D,'onecard_topology',return_value={'synthetic':True}),
                patch.object(os,'getpriority',return_value=0 if mode.startswith('W') else 19),
                patch.object(os,'sched_getaffinity',return_value=set(range(4))|set(range(16,20)) if mode.startswith('W') else set(range(8,16))|set(range(24,32))),
                patch.object(subprocess,'Popen',side_effect=capture)]
            for change in changes: stack.enter_context(change)
            try:
                result = W.main(argv)
                raise AssertionError('window did not reach native exec: '+str(result)+' '+(out/name/'window.json').read_text())
            except Reached:
                pass
        assert len(observations) == (2 if model else 1)
        assert snapshot() == before
        return dict(window=name, miss_path=miss, passed=True, device_executed=False,
            native_exec_intercepted=True, operational_state_synthetic=True,
            selection=V.validate(candidate), candidate=candidate, observations=observations,
            resource_limits_unchanged=True, finite_address_space_limit=False)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--probe'); ap.add_argument('--miss',default='zero-copy'); ap.add_argument('--candidate',default='resident'); args=ap.parse_args()
    if args.probe:
        print('ARGUMENT_RESULT='+json.dumps(probe(args.probe,args.miss,args.candidate)))
        return
    import screen_runner as Q
    before=sources(); records=[]
    for candidate in ('resident',):
      for name in Q.ORDER:
        for miss in (('zero-copy',) if name.startswith('K1') else ('zero-copy','streamed')):
            result=subprocess.run([sys.executable,'-B',str(Path(__file__)),'--probe',name,'--miss',miss,'--candidate',candidate],
                stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
            (P/'evidence'/f'arguments-{candidate}-{name}-{miss}.log').write_text(result.stdout+result.stderr)
            assert result.returncode==0, name+': '+result.stderr[-4000:]
            records.append(json.loads(next(s.split('=',1)[1] for s in result.stdout.splitlines() if s.startswith('ARGUMENT_RESULT='))))
            print(candidate,name,miss,'PASS',flush=True)
    assert before==sources()
    rss=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024
    assert rss < 8*1024**3
    row=dict(passed=True,device_executed=False,checks=len(records),records=records,sources=before,
        peak_child_rss_bytes=rss,model_payload_reads=False,services_started=False,
        seal_validation='separate seal verification; construction envelope synthetic to avoid circular gate dependency')
    (P/'evidence/screen-argument-gate.json').write_text(json.dumps(row,indent=2)+'\n')


if __name__=='__main__':
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    assert shutil.disk_usage('/').free>=25_000_000_000
    main()
