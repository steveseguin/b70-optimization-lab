"""CPU-only tests for onecard_chain_derive.py (no GPU, no live queue change).

Refusal cases run in a temporary repo root whose other entries are read-only
symlinks. The positive case runs in the REAL repo layout (packet172b): the
lanequeue pin guard resolves its root from its own real path, so a temp-root
derive was guarded against the wrong packet (blind by construction). It derives
into the real stage2/ and ops/ under a unique, collision-free prefix, runs the
real pin guard, the generated seal/verify_ready and a temp copy of
fn-run/onecard-chain.sh --check and the pre-device window rehearsal (every
chain window's window.main to its device boundary; it must also refuse the
packet58asb views.py/runtime-selection mismatch), and ALWAYS removes what it created (class
cleanup runs even when setUpClass fails) and asserts nothing is left for git.
Run: nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest test_onecard_chain_derive </dev/null
"""
import json, os, secrets, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

OPS = Path(__file__).resolve().parent
REPO = OPS.parents[2]
S = REPO / 'experiments/own-xpu-runtime/stage2'
AS = S / 'packet58as-onecard-spinwait'
AJ = S / 'packet58aj-onecard-resident'
REAL_COPIES = {'suite-inputs-20261012'}
CHAIN_SH = Path('/tmp/claude-1000/-home-steve/fn-run/onecard-chain.sh')
SUMMARY = 'experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/screen/evidence/card0-58as-v5-a/resident/WSCREEN/summary.json'
sys.path.insert(0, str(OPS)); sys.path.insert(0, str(OPS / 'lane-queue'))
import onecard_chain_derive as G  # noqa: E402


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


def derive(root, name, binary, host, summary=SUMMARY, flags=('wait-policy=spin',), out=None,
           threshold=AS / 'record-threshold.snapshot'):
    argv = [sys.executable, '-B', str(OPS / 'onecard_chain_derive.py'),
            '--parent-orch', str(root / 'experiments/own-xpu-runtime/ops/packet58aj-orchestration'),
            '--packet', str(root / 'experiments/own-xpu-runtime/stage2' / name),
            '--out', str(root / 'experiments/own-xpu-runtime/ops' / (out or name.split('-', 1)[0] + '-orchestration')),
            '--unit', 'packet58-onecard-58as-a', '--output', 'evidence/card0-58as-a',
            '--binary', str(binary), '--host-binary', str(host), '--bracket-summary', str(root / summary),
            # Default: the ledger as pinned by packet58as (before its own record was added).
            '--threshold-file', str(threshold), '--cpu-rehearsal']
    for f in flags:
        argv += ['--flag', f]
    return subprocess.run(argv, cwd=root, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=3000)


def unique_prefix():
    for _ in range(50):
        prefix = 'packet990t' + ''.join(secrets.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(6))
        if not G.prefix_taken(prefix, S, REPO / 'experiments/own-xpu-runtime/ops'):
            return prefix
    raise RuntimeError('no free test prefix')


def git_leftovers(*paths):
    cp = subprocess.run(['git', '-C', str(REPO), 'status', '--porcelain', '--untracked-files=all', '--', *map(str, paths)],
                        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
    return cp.stdout.strip()


@unittest.skipUnless(AS.is_dir() and AJ.is_dir(), 'packet58aj/58as trees required')
class RefusalTest(unittest.TestCase):
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
        cp = derive(self.root, 'packet990tmpa-badbracket', AS / 'build/device/own-rt-iq3',
                    AS / 'build/gnu-host/own-rt-iq3', summary='bad-bracket/summary.json')
        self.assertEqual(cp.returncode, 2, cp.stderr)
        self.assertIn('candidate_beats_all_controls', cp.stderr)
        self.assertFalse((self.root / 'experiments/own-xpu-runtime/stage2/packet990tmpa-badbracket').exists())

    def test_bracket_table_only_flag_refuses(self):
        # packet58aj binaries have no --wait-policy; packet58as selected spin only
        # through its bracket table (the packet58asc failure).
        cp = derive(self.root, 'packet990tmpb-noflag', AJ / 'build/device/own-rt-iq3', AJ / 'build/gnu-host/own-rt-iq3')
        self.assertEqual(cp.returncode, 2, cp.stderr)
        self.assertIn('only through the bracket table', cp.stderr)
        self.assertFalse((self.root / 'experiments/own-xpu-runtime/stage2/packet990tmpb-noflag').exists())

    def test_unknown_flag_refuses(self):
        cp = derive(self.root, 'packet990tmpc-unknown', AS / 'build/device/own-rt-iq3', AS / 'build/gnu-host/own-rt-iq3',
                    flags=('no-such-option=1',))
        self.assertEqual(cp.returncode, 2, cp.stderr)
        self.assertIn('does not list it', cp.stderr)


class PrefixGateTest(unittest.TestCase):
    """The packet58as-b-confirm failure: ops/packet58as-* pulled packet58as-orchestration in."""
    OPSDIR = REPO / 'experiments/own-xpu-runtime/ops'

    def test_colliding_prefix_refuses_with_free_suggestion(self):
        P, O = S / 'packet58as-b-confirm', self.OPSDIR / 'packet58as-b-orchestration'
        with self.assertRaises(G.Refused) as cm:
            G.prefix_gate(P, O)
        msg = str(cm.exception)
        self.assertIn("prefix 'packet58as'", msg)
        self.assertIn('packet58as-orchestration', msg)
        suggestion = msg.split('--packet .../stage2/')[1].split('-', 1)[0]
        self.assertTrue(suggestion.startswith('packet58as') and suggestion != 'packet58as')
        self.assertEqual(G.prefix_taken(suggestion, S, self.OPSDIR), [])
        self.assertFalse(P.exists() or O.exists())

    def test_cli_refuses_before_creating_anything(self):
        X = 'experiments/own-xpu-runtime'
        cp = subprocess.run([sys.executable, '-B', str(OPS / 'onecard_chain_derive.py'), '--parent-orch', f'{X}/ops/packet58aj-orchestration',
                             '--packet', f'{X}/stage2/packet58as-zzprefixtest', '--out', f'{X}/ops/packet58as-zzprefixtest-orchestration',
                             '--unit', 'packet58-onecard-58as-z', '--output', 'evidence/card0-58as-z', '--binary', 'x', '--host-binary', 'x',
                             '--bracket-summary', 'x', '--threshold-file', 'x', '--flag', 'wait-policy=spin'],
                            cwd=REPO, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
        self.assertEqual(cp.returncode, 2, cp.stderr)
        self.assertIn('collides with', cp.stderr)
        self.assertFalse((S / 'packet58as-zzprefixtest').exists())

    def test_out_must_share_prefix_and_name_must_parse(self):
        with self.assertRaises(G.Refused):
            G.prefix_gate(S / 'packet990tzzzz-x', self.OPSDIR / 'packet990tyyyy-orchestration')
        with self.assertRaises(G.Refused):
            G.prefix_gate(S / 'packet58as_b-x', self.OPSDIR / 'packet58as_b-orchestration')

    def test_live_ledger_line_is_a_confirmation(self):
        ledger = json.loads((REPO / 'scripts/packet58_onecard_record_threshold.json').read_text())
        c = G.confirmation_of(ledger['records'][-1], REPO, AS, G.sha(AS / 'build/device/own-rt-iq3'))
        if 'packet58as-onecard-spinwait' in ledger['records'][-1]['result']['path']:
            self.assertTrue(c and c['same_chain_binary'] and c['resubmission'] is False)
            self.assertIn('not a resubmission', c['text'])
        self.assertIsNone(G.confirmation_of(dict(result=dict(path='experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/x.json'),
                                                 threshold_tok_s=1.0, reference_submission='r'), REPO, AS, '0' * 64))


@unittest.skipUnless(AS.is_dir() and AJ.is_dir() and CHAIN_SH.is_file(), 'packet58aj/58as trees and fn-run chain script required')
class RealLayoutTest(unittest.TestCase):
    """Derive into the real stage2/ops under a unique prefix; the real pin guard must pass."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='onecard-derive-real-')
        cls.addClassCleanup(cls.tmp.cleanup)
        prefix = unique_prefix()
        cls.name = prefix + '-pintest'
        cls.P = S / cls.name
        cls.O = REPO / 'experiments/own-xpu-runtime/ops' / (prefix + '-orchestration')
        cls.addClassCleanup(cls.cleanup)          # registered BEFORE anything is created
        cls.cp = derive(REPO, cls.name, AS / 'build/device/own-rt-iq3', AS / 'build/gnu-host/own-rt-iq3')

    @classmethod
    def cleanup(cls):
        for d in (cls.P, cls.O):
            if d.is_relative_to(REPO / 'experiments/own-xpu-runtime') and d.name.startswith('packet990t') and d.exists():
                shutil.rmtree(d)
        left = git_leftovers(cls.P, cls.O)
        if left or cls.P.exists() or cls.O.exists():
            raise AssertionError('real-layout test left files behind: ' + left)

    def setUp(self):
        self.assertEqual(self.cp.returncode, 0, self.cp.stderr[-4000:])

    def test_pin_guard_passes_on_real_layout(self):
        import pin_guard
        job = json.loads((self.O / 'entry-proposal.jsonl').read_text())
        self.assertEqual(pin_guard.packet_for_job(job, REPO, S), self.P)      # the guard checks THIS packet
        row = pin_guard.check_job(job, REPO, S)
        self.assertTrue(row['passed']); self.assertEqual(row['packet'], str(self.P))
        self.assertIn('"plan": "passed"', (self.O / 'queue-plan.log').read_text())

    def test_no_manifest_pins_the_parent_packet(self):
        P0 = AJ
        bad, manifests = G.pin_audit(self.P, REPO, parent=P0)
        self.assertEqual(bad, [])
        guard = G.load_guard()
        for manifest in manifests:                                            # each manifest, not the deduplicated set
            for name, digest in G.manifest_entries(guard, manifest)[3]:
                target = guard.pin_path(name, manifest, self.P, REPO)
                self.assertFalse(target.is_relative_to(P0), f'{manifest} pins parent {target}')
        relocation = json.loads((self.P / 'evidence/pin-relocation.json').read_text())
        touched = {c['manifest'] for c in relocation['changes']}
        self.assertIn(str((self.P / 'evidence/argument-gate.json').relative_to(REPO)), touched)
        for c in relocation['changes']:
            self.assertTrue(c['parent_digest'] and c['parent_relpath'])
        ready = json.loads((self.O / 'READY-FOR-DEVICE.json').read_text())
        self.assertTrue(ready['pin_audit']['passed'])
        for rec in ready['orchestration_provenance'] + ready['parent_provenance']:
            self.assertEqual(set(rec), {'name', 'parent_relpath', 'parent_digest'})

    def predevice(self):
        return subprocess.run([sys.executable, '-B', str(OPS / 'onecard_chain_derive.py'), '--predevice-check', str(self.P)],
                              cwd=REPO, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=1200)

    def test_predevice_rehearsal_runs_every_window_to_its_device_boundary(self):
        ready = json.loads((self.O / 'READY-FOR-DEVICE.json').read_text())
        self.assertEqual(ready['predevice_rehearsal']['windows'], ['K1a', 'K1b', 'KD', 'W2m', 'WS', 'WS128x', 'WS128'])
        self.assertEqual(ready['predevice_rehearsal']['boundaries']['K1a'], 'output directory creation')
        self.assertEqual(ready['predevice_rehearsal']['boundaries']['WS128'], 'previous-window prerequisite WS128x')
        selection = json.loads((self.P / 'runtime-selection.json').read_text())
        self.assertEqual(selection['wait_policy'], 'spin'); self.assertEqual(selection['chain_flags'], {'--wait-policy': 'spin'})
        cp = self.predevice()
        self.assertEqual(cp.returncode, 0, cp.stderr[-3000:])
        self.assertFalse(any(self.P.joinpath('evidence').glob('.predevice-*')))
        # The packet58asb launch failure: runtime-selection.json carried the flag, views.py's literal did not,
        # under a consistent seal. Reproduce it transiently (views.py + its seal entry), then restore both.
        views, receipt = self.P / 'views.py', self.P / 'build-receipt.json'
        original, original_receipt = views.read_bytes(), receipt.read_bytes()
        try:
            text = original.decode().replace('if runtime!=dict(**GENERATED_RUNTIME_SELECTION,', 'if runtime!=dict(')
            self.assertNotEqual(text, original.decode())
            views.write_text(text)
            row = json.loads(original_receipt); row['sources'][str(views.relative_to(REPO))] = G.sha(views)
            receipt.write_text(json.dumps(row, indent=2) + '\n')
            bad = self.predevice()
            self.assertEqual(bad.returncode, 2, bad.stdout + bad.stderr)
            self.assertIn('sealed overlap runtime selection changed', bad.stderr)
            for window in ('K1a', 'K1b', 'KD', 'W2m', 'WS', 'WS128x', 'WS128'):
                self.assertIn(window + ': ValueError', bad.stderr)
        finally:
            views.write_bytes(original); receipt.write_bytes(original_receipt)
        self.assertEqual(G.sha(views), json.loads((self.P / 'build-receipt.json').read_text())['sources'][str(views.relative_to(REPO))])

    def test_matches_hand_built_packet58as_and_chain_check(self):
        ready = json.loads((self.O / 'READY-FOR-DEVICE.json').read_text())
        hand = json.loads((REPO / 'experiments/own-xpu-runtime/ops/packet58as-orchestration/READY-FOR-DEVICE.json').read_text())
        self.assertEqual(ready['chain_binary_sha256'], hand['chain_binary_sha256'])
        self.assertEqual(ready['chain_command'].replace(self.name, 'packet58as-onecard-spinwait'), hand['chain_command'])
        for key in ('windows', 'gap_seconds', 'wait_seconds', 'bracket_rates_tok_s', 'control_drift_fraction', 'minimum_gain', 'pinned_predecessor'):
            self.assertEqual(ready[key], hand[key], key)
        self.assertEqual(ready['configuration'].get('wait_policy'), 'spin')
        flags = json.loads((self.P / 'evidence/chain-flags.json').read_text())
        self.assertEqual([r['window'] for r in flags['parser']], ['KD', 'W2m', 'WS', 'WS128x', 'WS128'])
        self.assertTrue(all(r['flags']['--wait-policy']['invalid_value_refused'] for r in flags['parser']))
        vr = subprocess.run([sys.executable, '-B', str(self.P / 'verify_ready.py')], cwd=REPO, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=600, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        self.assertEqual(vr.returncode, 0, vr.stdout[-2000:] + vr.stderr[-2000:])
        # fn-run/onecard-chain.sh: real repo root; only the log path moves to the temp dir.
        script = Path(self.tmp.name) / 'onecard-chain.sh'
        text = CHAIN_SH.read_text()
        self.assertIn('LOG=/tmp/claude-1000/-home-steve/fn-run/p58k.log', text)
        script.write_text(text.replace('LOG=/tmp/claude-1000/-home-steve/fn-run/p58k.log', f'LOG={self.tmp.name}/p58k.log'))
        ch = subprocess.run(['bash', str(script), self.name, self.O.name, '--check'], stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=600)
        self.assertEqual(ch.returncode, 0, ch.stdout + ch.stderr)
        self.assertIn('seal verify: ok', ch.stdout)
        self.assertIn('check complete', ch.stdout)
        self.assertIn('unit=packet58-onecard-58as-a', ch.stdout)


if __name__ == '__main__':
    unittest.main()
