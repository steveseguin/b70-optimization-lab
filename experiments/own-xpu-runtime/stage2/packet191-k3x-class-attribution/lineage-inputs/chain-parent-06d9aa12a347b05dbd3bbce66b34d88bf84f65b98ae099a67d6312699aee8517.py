#!/usr/bin/env python3
"""CPU-only strict terminal rollback: all target bytes, both controllers, raw inventory.

Requires strict-terminal-snapshot.patch to be applied and freshly rebuilt.
No terminal-state masking or reset-before-hash; logical event counter retained separately.
"""
import argparse
import fcntl
import hashlib
import json
import os
import random
import time
from pathlib import Path
import pipeline
from storage import admit, discard
P = Path(__file__).resolve().parent


def state(root):
    result = {}
    bookkeeping = {}
    for rank in (0, 1):
        base = root / f'rank{rank}'
        directory = base / 'state-2147483647'
        assert directory.is_dir(), 'missing final state'
        for file in sorted(directory.iterdir()):
            if file.is_file():
                result[str(file.relative_to(root))] = pipeline.sha(file)
        file = base / 'request-state-inventory.json'
        inventory = json.loads(file.read_text())
        bookkeeping[str(rank)] = dict(logical_event=inventory.pop('logical_event'),
                                      raw_inventory_sha256=pipeline.sha(file))
        result[f'rank{rank}/inventory'] = inventory
    return result, bookkeeping


def owner(binary, root, mini, inputs, controller, retain, prompt, count,
          guesses=(), eos=(), cut=-1, corrupt=None):
    assert prompt and count > 0 and len(prompt) + count <= 256, "prompt + cap exceeds context"
    admit(600_000_000 if not mini else 50_000_000)
    assert not root.exists()
    root.mkdir()
    argv = ['--binary', str(binary), '--output', str(root), '--controller', controller,
            '--draft', 'none', '--tokens', str(count), '--context', '256',
            '--retain-steps', retain, '--cancel-launch', str(cut),
            '--seconds', '172800', '--wait-seconds', '7200', '--native-nice', '19']
    argv += ['--mini'] if mini else ['--input', str(inputs)]
    args = pipeline.parser().parse_args(argv)
    args.dispatch = P / ('dispatch-all-new.json' if mini else 'dispatch-p38.json')
    args.host_memory = 'resident' if mini else 'layer-streaming'
    transport = None
    receipt = dict(passed=False, device_executed=False, controller=controller,
                   retain_steps=retain, cancel_launch=cut, corruption=corrupt,
                   prompt_tokens=len(prompt), prompt_token_sha256=hashlib.sha256(json.dumps(prompt,separators=(",", ":")).encode()).hexdigest(),
                   context_capacity=256, max_new=count)
    try:
        transport = pipeline.Transport.__new__(pipeline.Transport)
        transport.__init__(args, root)
        draft = pipeline.Draft('script' if guesses else 'none', list(guesses))
        result = pipeline.request_run(transport, draft, prompt, count, eos, True, False)
        if corrupt is not None:
            # Actual CPU memory corruption of a committed allocation. A complete
            # speculative half swaps banks; the injected pointer is the saved
            # active-bank ID, so restoring the inactive destination cannot hide it.
            position = len(prompt) + len(result['tokens']) - 1
            transport.call(0, pipeline.HALF, token=(result['tokens'][-1] + 1) % (16 if mini else 248320),
                           position=position, fixture=len(result['tokens']) + 1, speculative=1)
            transport.call(0, 12, token=0 if corrupt == 'active-bank' else 1)
            transport.call(0, pipeline.ROLLBACK)
        for rank in (0, 1):
            transport.call(rank, pipeline.DUMP, position=2147483647)
        signature, bookkeeping = state(root)
        signature['rank0/shared-stream-slot'] = hashlib.sha256(transport.mapping[:pipeline.SLOT]).hexdigest()
        snapshot = json.loads((root/'rank0/speculative-snapshot.json').read_text())
        assert snapshot['private_backup_zeroed'] and not snapshot['committed_state_scrubbed']
        assert snapshot['private_host_backup_empty'] and not snapshot['snapshot_valid']
        transport.close(True)
        transport = None
        timings = [json.loads(line) for line in (root/'rank0/timings.jsonl').read_text().splitlines()]
        receipt.update(passed=True, tokens=result['tokens'], state=signature,
                       bookkeeping=bookkeeping, timings=timings, snapshot=snapshot)
        return receipt
    except BaseException as error:
        receipt['error'] = str(error) or type(error).__name__
        raise
    finally:
        try:
            if transport is not None:
                transport.stop('strict terminal gate cleanup')
                transport.close(False)
        finally:
            # Never archive/remove files still owned by a retained rank.
            live = [child.pid for child in getattr(transport, 'children', ()) if child.poll() is None]
            receipt['retained_pids'] = live
            receipt['owner_log_sha256'] = {file.name: pipeline.sha(file) for file in sorted(root.glob('rank*.log'))}
            pipeline.save(root/'strict-terminal-owner.json', receipt)
            receipt['owner_receipt_sha256'] = pipeline.sha(root/'strict-terminal-owner.json')
            if not live:
                receipt['archive'] = discard(root)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--binary', type=Path, required=True)
    ap.add_argument('--real', action='store_true')
    ap.add_argument('--screen', action='store_true', help='mini diagnostic cuts only; never qualifies exhaustive coverage')
    ap.add_argument('--input', type=Path, default=P/'build/input')
    ap.add_argument('--controller', choices=('native', 'python', 'both'), default='both')
    ap.add_argument('--random-count', type=int, default=4)
    ap.add_argument('--real-prefix', type=int, default=7, help='diagnostic unchanged original prompt prefix length')
    ap.add_argument('--positions', default='0,1', help='extra confirmed generated tokens appended to the real prompt')
    ap.add_argument('--output', type=Path)
    a = ap.parse_args()
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19 and os.environ.get('OMP_NUM_THREADS') == '2'
    binary = a.binary.resolve()
    assert binary.is_relative_to((P/'build').resolve()) and 'device' not in binary.parts
    assert a.random_count > 0
    assert not (a.real and a.screen), '--screen is mini-only'
    positions = sorted(set(map(int, a.positions.split(',')))) if a.real else [0]
    assert positions and min(positions) >= 0 and max(positions) <= 8
    controllers = ['native', 'python'] if a.controller == 'both' else [a.controller]
    root = P/'build'/('strict-terminal-'+str(time.time_ns()))
    admit(600_000_000)
    root.mkdir()
    destination = a.output or P/('terminal-eos-all-state-'+('real' if a.real else 'mini')+'-'+a.controller+('-screen' if a.screen else '')+'.json')
    before_sources = {n: pipeline.sha(P/n) for n in ('strict_terminal_gate.py', 'strict_snapshot.hpp', 'rank.hpp',
                     'main.cpp', 'request_state_inventory.hpp', 'pipeline.py', 'native_controller.hpp', 'storage.py')}
    before_binary = pipeline.sha(binary)
    receipt = dict(passed=False, device_executed=False, binary_sha256=before_binary,
                   source_sha256=before_sources, real_model=a.real, controllers=controllers, screen=a.screen,
                   terminal_eos=True, raw_allocation_bytes_equal=False, all_inventoried_allocations=True,
                   logical_event_scope='scheduling counter excluded from equality; raw hash/counter retained per owner',
                   committed_state_scrubbed=False, rows=[], negative_controls=[], owners=[],
                   diagnostic_only=True, performance_claim=False, real_prompt_scope='unchanged original prompt prefix; full-weight production launch plan' if a.real else 'mini model')
    def invoke(*args, **kwargs):
        result = owner(*args, **kwargs)
        receipt['owners'].append({key: result[key] for key in ('archive','owner_receipt_sha256','owner_log_sha256','prompt_tokens','prompt_token_sha256','controller','retain_steps','cancel_launch','corruption')})
        return result
    try:
        original = list(map(int, (a.input/'tokens.txt').read_text().split())) if a.real else [2, 5, 3, 7, 1]
        assert not a.real or 1 <= a.real_prefix <= len(original)
        prompt = original[:a.real_prefix] if a.real else original
        assert len(prompt) + max(positions) + 2 <= 256
        receipt.update(original_prompt_tokens=len(original), original_prompt_token_sha256=hashlib.sha256(json.dumps(original,separators=(",", ":")).encode()).hexdigest(),
                       diagnostic_prefix_tokens=len(prompt), prefix_token_sha256=hashlib.sha256(json.dumps(prompt,separators=(",", ":")).encode()).hexdigest(),
                       sampled_positions=[len(prompt)+offset for offset in positions])
        baseline = invoke(binary, root/'seed', not a.real, a.input, controllers[0], 'none', prompt, max(positions)+1)
        seed_tokens = baseline['tokens']
        assert len(seed_tokens) > max(positions)
        for controller in controllers:
            for position in positions:
                request_prompt = prompt + seed_tokens[:position]
                reference = invoke(binary, root/f'{controller}-p{position}-reference', not a.real, a.input,
                                  controller, 'none', request_prompt, 1)
                expected = reference['tokens']
                assert expected == [seed_tokens[position]]
                n = next(row['launches_issued'] for row in reference['timings'] if row['position'] == len(request_prompt)-1)
                cuts = list(range(n+2)) if not a.real else sorted({0, n, n+1, *random.Random(4040+position).sample(range(1, n), min(a.random_count, n-1))})
                if a.screen:
                    cuts = sorted({0, n//2, n, n+1})
                for retain in ('none', '1-8,97-104'):
                    for cut in cuts:
                        actual = invoke(binary, root/f'{controller}-p{position}-r{int(retain != "none")}-c{cut}',
                                       not a.real, a.input, controller, retain, request_prompt, 2,
                                       [(expected[0]+1) % (248320 if a.real else 16)], expected, cut)
                        assert actual['tokens'] == expected, 'terminal output changed'
                        assert actual['state'] == reference['state'], ('terminal all-state mismatch', controller, position, retain, cut)
                        speculative = [row for row in actual['timings'] if row['speculative']]
                        assert len(speculative) == 1 and speculative[0]['launches_issued'] == min(cut,n)
                        assert speculative[0]['cancelled'] == (cut <= n)
                        assert actual['snapshot']['captures'] == actual['snapshot']['restores'] == 1
                        receipt['rows'].append(dict(controller=controller, position=len(request_prompt), retain_steps=retain,
                                                    launch_boundary=cut, actual_compute_launches=n, tokens_equal=True,
                                                    raw_allocation_bytes_equal=True, bookkeeping=actual['bookkeeping']))
                        print('strict EOS', controller, len(request_prompt), retain, cut, '/', n, 'PASS', flush=True)
                for kind in ('active-bank', 'valid-qsa-prefix'):
                    negative = invoke(binary, root/f'{controller}-p{position}-negative-{kind}', not a.real, a.input,
                                     controller, 'none', request_prompt, 1, cut=n+1, corrupt=kind)
                    assert negative['state'] != reference['state'], ('rollback hid committed-state corruption',kind)
                    receipt['negative_controls'].append(dict(controller=controller, position=len(request_prompt), kind=kind,
                                                              actual_cpu_memory_corruption=True, rejected_by_full_state_comparison=True))
        assert before_sources == {n: pipeline.sha(P/n) for n in before_sources}, 'gate source changed'
        assert pipeline.sha(binary) == before_binary, 'gate binary changed'
        receipt.update(passed=True, raw_allocation_bytes_equal=True, gate_count=len(receipt['rows'])+len(receipt['negative_controls']),
                       every_mini_launch_boundary=not a.real and not a.screen, real_model_sampled_boundaries=a.real,
                       snapshot_rollback=True, negative_control_count=len(receipt['negative_controls']))
    except BaseException as error:
        receipt['error'] = str(error) or type(error).__name__
        raise
    finally:
        pipeline.save(destination, receipt)
        # All model children are reaped inside owner(), or its root is preserved.
        if not any(root.iterdir()):
            root.rmdir()
    print(json.dumps(dict(passed=True, receipt=str(destination), gates=receipt['gate_count'])))

if __name__ == '__main__':
    # Serializes real MTP/capture owners; caller still owns the two CPU-rank slots.
    with (P/'build/cpu-mtp.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        main()
