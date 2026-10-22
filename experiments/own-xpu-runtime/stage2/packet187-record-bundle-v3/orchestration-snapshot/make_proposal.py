"""Write proposal.jsonl: the entry-check descriptor of the packet187 chain (PROPOSAL ONLY; never appended to a queue).

The chain is launched by `ready.json.chain_command` (systemd unit packet187-chain-a -> device-entry.sh ->
coordinator_windows.sh -> chain_entry.py queue), through launch_chain.sh's guards. This descriptor exists so
the shared ops/rehearse_entry.py packaging checks (and rehearse_entry187.py's report adapter) can run.
"""
import json, sys
from pathlib import Path
from chain_adapter import O, P, ROOT, sha
sys.path.insert(0, str(P))
def main():
    import storage
    prep = json.loads((O / 'evidence/preparation.json').read_text())
    native = json.loads((O / 'inputs/packet186-native.json').read_text())
    prefix = ROOT / 'experiments/own-xpu-runtime/stage2/packet56-draft-prefix/evidence'
    row = dict(name='packet187-chain-A', lane='A',
               argv=['/usr/bin/python3', '-B', 'experiments/own-xpu-runtime/ops/packet187-orchestration/chain_entry.py', 'queue', '--authorized-device-window',
                     '--phase', 'all', '--output-root', str(P / 'build/device-cards01-p187-a'), '--wait-oracle', '--prefix-windows',
                     str(prefix / 'head-k-a/window.json'), str(prefix / 'head-k-b/window.json')],
               env_extra={},
               planned_write_bytes=sum(storage.chain_window_bytes(n) for n in storage.CHAIN_WINDOWS),
               plan=dict(coordinator_unit='packet187-chain-a', proposal_only=True,
                         launch_via='launch_chain.sh -> ready.json chain_command (device-entry.sh with coordinator_windows.sh); do not append to a lane queue',
                         entry_rehearsal=dict(binaries=[dict(path=str((P / k).relative_to(ROOT)), sha256=v['sha256']) for k, v in sorted(native['binaries'].items())],
                                              prepare_probe=prep['probes'][0]),
                         planned_writes=sum(storage.chain_window_bytes(n) for n in storage.CHAIN_WINDOWS),
                         device_floor_bytes=25_000_000_000, cpu_stop_bytes=27_000_000_000,
                         host_required_available_bytes=107_667_817_956, host_queue_start_extra_bytes=1024**3))
    (O / 'proposal.jsonl').write_text(json.dumps(row) + '\n')
    print('proposal descriptor written', sha(O / 'proposal.jsonl')[:16])
if __name__ == '__main__':
    main()
