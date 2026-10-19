"""CPU-only tests for onecard_chain_derive.py (temp dirs only; no GPU, no queue change).

Regenerates a packet58as-equivalent chain from packet58aj-orchestration in a
temporary repo root whose other entries are read-only symlinks, then runs a temp
copy of fn-run/onecard-chain.sh --check against it. Also: a binary without the
flag (bracket-table-only dimension) and a failed bracket must refuse.
Run: nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest test_onecard_chain_derive </dev/null
"""
import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

OPS = Path(__file__).resolve().parent
REPO = OPS.parents[2]
S = REPO / 'experiments/own-xpu-runtime/stage2'
AS = S / 'packet58as-onecard-spinwait'
AJ = S / 'packet58aj-onecard-resident'
REAL_COPIES = {'suite-inputs-20261012'}
CHAIN_SH = Path('/tmp/claude-1000/-home-steve/fn-run/onecard-chain.sh')
SUMMARY = 'experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/screen/evidence/card0-58as-v5-a/resident/WSCREEN/summary.json'


def temp_root(tmp):
    """A repo-shaped root: new dirs are real, every existing entry is a symlink."""
    root = Path(tmp) / 'repo'
    for rel in ('experiments/own-xpu-runtime/stage2', 'experiments/own-xpu-runtime/ops'):
        (root / rel).mkdir(parents=True)
        for entry in (REPO / rel).iterdir():
            if entry.name in REAL_COPIES:
                # The harness resolves these and requires them inside its root.
                shutil.copytree(entry, root / rel / entry.name, symlinks=False)
            else:
                (root / rel / entry.name).symlink_to(entry)
    for entry in REPO.iterdir():
        if not (root / entry.name).exists() and entry.name != 'experiments':
            (root / entry.name).symlink_to(entry)
    return root


def derive(root, name, binary, host, summary=SUMMARY, flags=('wait-policy=spin',)):
    argv = [sys.executable, '-B', str(OPS / 'onecard_chain_derive.py'),
            '--parent-orch', str(root / 'experiments/own-xpu-runtime/ops/packet58aj-orchestration'),
            '--packet', str(root / 'experiments/own-xpu-runtime/stage2' / name),
            '--out', str(root / 'experiments/own-xpu-runtime/ops' / (name + '-orchestration')),
            '--unit', 'packet58-onecard-58as-a', '--output', 'evidence/card0-58as-a',
            '--binary', str(binary), '--host-binary', str(host), '--bracket-summary', str(root / summary),
            # The ledger as pinned by packet58as (before its own record was added).
            '--threshold-file', str(AS / 'record-threshold.snapshot'), '--cpu-rehearsal']
    for f in flags:
        argv += ['--flag', f]
    return subprocess.run(argv, cwd=root, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=3000)


@unittest.skipUnless(AS.is_dir() and AJ.is_dir(), 'packet58aj/58as trees required')
class DeriveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='onecard-derive-')
        cls.root = temp_root(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_failed_bracket_refuses(self):
        bad = self.root / 'bad-bracket'; bad.mkdir()
        s = json.loads((REPO / SUMMARY).read_text()); s['candidate_beats_all_controls'] = False
        (bad / 'summary.json').write_text(json.dumps(s))
        shutil.copy2((REPO / SUMMARY).parent / 'window.json', bad / 'window.json')
        cp = derive(self.root, 'packet58as-derived-badbracket', AS / 'build/device/own-rt-iq3',
                    AS / 'build/gnu-host/own-rt-iq3', summary='bad-bracket/summary.json')
        self.assertEqual(cp.returncode, 2, cp.stderr)
        self.assertIn('candidate_beats_all_controls', cp.stderr)
        self.assertFalse((self.root / 'experiments/own-xpu-runtime/stage2/packet58as-derived-badbracket').exists())

    def test_bracket_table_only_flag_refuses(self):
        # packet58aj binaries have no --wait-policy; packet58as selected spin only
        # through its bracket table (the packet58asc failure).
        cp = derive(self.root, 'packet58as-derived-noflag', AJ / 'build/device/own-rt-iq3', AJ / 'build/gnu-host/own-rt-iq3')
        self.assertEqual(cp.returncode, 2, cp.stderr)
        self.assertIn('only through the bracket table', cp.stderr)
        self.assertFalse((self.root / 'experiments/own-xpu-runtime/stage2/packet58as-derived-noflag').exists())

    def test_unknown_flag_refuses(self):
        cp = derive(self.root, 'packet58as-derived-unknown', AS / 'build/device/own-rt-iq3', AS / 'build/gnu-host/own-rt-iq3',
                    flags=('no-such-option=1',))
        self.assertEqual(cp.returncode, 2, cp.stderr)
        self.assertIn('does not list it', cp.stderr)

    def test_regenerates_packet58as_and_passes_chain_check(self):
        name = 'packet58as-derived'
        cp = derive(self.root, name, AS / 'build/device/own-rt-iq3', AS / 'build/gnu-host/own-rt-iq3')
        self.assertEqual(cp.returncode, 0, cp.stderr[-3000:])
        O = self.root / 'experiments/own-xpu-runtime/ops' / (name + '-orchestration')
        P = self.root / 'experiments/own-xpu-runtime/stage2' / name
        ready = json.loads((O / 'READY-FOR-DEVICE.json').read_text())
        hand = json.loads((REPO / 'experiments/own-xpu-runtime/ops/packet58as-orchestration/READY-FOR-DEVICE.json').read_text())
        self.assertEqual(ready['chain_binary_sha256'], hand['chain_binary_sha256'])
        self.assertEqual(ready['chain_command'].replace(name, 'packet58as-onecard-spinwait').replace(str(self.root), str(REPO)),
                         hand['chain_command'])
        for key in ('windows', 'gap_seconds', 'wait_seconds', 'bracket_rates_tok_s', 'control_drift_fraction', 'minimum_gain', 'pinned_predecessor'):
            self.assertEqual(ready[key], hand[key], key)
        self.assertEqual(ready['configuration'].get('wait_policy'), 'spin')
        flags = json.loads((P / 'evidence/chain-flags.json').read_text())
        self.assertEqual([r['window'] for r in flags['parser']], ['KD', 'W2m', 'WS', 'WS128x', 'WS128'])
        self.assertTrue(all(r['flags']['--wait-policy']['invalid_value_refused'] for r in flags['parser']))
        # Pin-guard hygiene: parent digests only as {name,parent_relpath,parent_digest} records.
        for rec in ready['orchestration_provenance'] + ready['parent_provenance']:
            self.assertEqual(set(rec), {'name', 'parent_relpath', 'parent_digest'})
        # fn-run/onecard-chain.sh hard-codes the repo root: run a temp copy with only
        # the root and log path changed; the original is never edited.
        script = Path(self.tmp.name) / 'onecard-chain.sh'
        text = CHAIN_SH.read_text()
        self.assertIn('cd /home/steve/llm-optimizations\n', text)
        text = text.replace('cd /home/steve/llm-optimizations\n', f'cd {self.root}\n')
        text = text.replace('LOG=/tmp/claude-1000/-home-steve/fn-run/p58k.log', f'LOG={self.tmp.name}/p58k.log')
        script.write_text(text)
        ch = subprocess.run(['bash', str(script), name, name + '-orchestration', '--check'], stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=600)
        self.assertEqual(ch.returncode, 0, ch.stdout + ch.stderr)
        self.assertIn('seal verify: ok', ch.stdout)
        self.assertIn('check complete', ch.stdout)
        self.assertIn('unit=packet58-onecard-58as-a', ch.stdout)


if __name__ == '__main__':
    unittest.main()
