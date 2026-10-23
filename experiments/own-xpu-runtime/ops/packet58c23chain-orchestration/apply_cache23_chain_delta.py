#!/usr/bin/env python3
"""Phase 2 of packet58-onecard-cache23-chain: apply the cache23 harness delta to the derived chain packet.

CPU only; edits only files inside stage2/packet58-onecard-cache23-chain (never a parent). Every change is an
exact-once literal replacement or a byte copy from packet58-onecard-cache23's root chain harness (read in
place, provenance recorded), logged with before/after digests in evidence/cache23-chain-delta.json.
Refuses if a literal is missing or occurs more than once, so a second run cannot double-apply.

What changes versus packet182c-chain (the phase-1 derivation already carries the max23 argv/selection and
the cache23 engine bytes; see capacity-patch.json):
  memory plan      memory_plan.py, admission.json (the lineage pin respelled to this packet), budget_gate.py,
                   test_memory_plan.py, test_memory_sensor.py, test_admission58e.py, test_resident.py: the
                   packet58-onecard-cache23 re-partitioned device plan (bound 29,828,911,360; driver allowance
                   671,088,640; transient 784,567,808; arena 23,049,601,024; host 100,487,123,456 = bound
                   91,897,188,864 + 8 GiB).
  validator        packet58_submission.py: the record argv is `--cache-cap max23 --cache-bytes 23049601024`,
                   full_cache_bytes 23,049,601,024, label/identity/notes disclose the capacity change and the
                   128-token scope, immutableExpertWeightCacheBytes 23,049,601,024; test_submission.py and
                   rehearse_submission.py adapted (the 21.55 GB record argv is now a refused value).
  provenance       engine-binding.json (this packet's binaries pinned, the cache23 sources as provenance),
                   restore-inputs.json gains the two engine records, .gitignore keeps the chain's bulky device
                   streams host-local, MEMORY.md carries the new table.
"""
import json, shutil, sys
from pathlib import Path

ROOT = Path('/home/steve/llm-optimizations')
X = ROOT / 'experiments/own-xpu-runtime'
P = X / 'stage2/packet58-onecard-cache23-chain'
C = X / 'stage2/packet58-onecard-cache23'          # the screen packet: read only
C182 = X / 'stage2/packet182c-chain'               # the record-line chain: read only
sys.path.insert(0, str(X / 'ops'))
import onecard_chain_derive as G  # noqa: E402  (sha, put, save, read, refuse)

ARENA_OLD, ARENA_NEW = 21552729600, 23049601024
HOST_OLD, HOST_NEW = 98990252032, 100487123456
HOST_BOUND_OLD, HOST_BOUND_NEW = 90400317440, 91897188864
BOUND_OLD, BOUND_NEW = 29963128848, 29828911360
DEVICE_SHA = '083e3853427041be36faeaf804781e4204b79ed19296648e0aaa7f6c5f1b151a'
HOST_SHA = '03a2aa12187d02276995a1cba5d0fffc0bdd5e78632144f2529db44103be705b'
K1_SHA = 'ba49aa8156437e0a1f95e52efe5b6b61141f96af62614a8f903c0c627f9e9c35'
LABEL_OLD = 'qwen38-flash-next-unsloth-iq3xxs-ownrt-tp1-packet58aj-chain-a-realistic-20261019'
LABEL_NEW = 'qwen38-flash-next-unsloth-iq3xxs-ownrt-tp1-packet58-onecard-cache23-chain-a-realistic-20261023'
LOG = []


def rel(p):
    return str(Path(p).relative_to(ROOT))


def record(path):
    return dict(name=Path(path).name, parent_relpath=rel(path), parent_digest=G.sha(path))


def replace_once(name, old, new, count=1):
    path = P / name
    text = path.read_text()
    G.refuse(text.count(old) == count, f'{name}: literal must occur exactly {count}x: {old[:80]!r} (found {text.count(old)})')
    before = G.sha(path)
    G.put(path, text.replace(old, new))
    LOG.append(dict(file=name, action='literal', before_sha256=before, after_sha256=G.sha(path), old=old, new=new, occurrences=count))
    if name.endswith('.py'):
        compile(path.read_text(), str(path), 'exec')


def copy_from_screen(name, rewrite=()):
    src, dst = C / name, P / name
    G.refuse(src.is_file() and dst.is_file(), f'{name}: both the screen copy and the derived copy must exist')
    before = G.sha(dst)
    text = src.read_text()
    for old, new in rewrite:
        G.refuse(text.count(old) >= 1, f'{name}: rewrite literal missing: {old!r}')
        text = text.replace(old, new)
    G.put(dst, text)
    LOG.append(dict(file=name, action='copied from packet58-onecard-cache23 root harness', source=record(src), before_sha256=before,
                    after_sha256=G.sha(dst), rewrites=[dict(old=o, new=n) for o, n in rewrite]))
    if name.endswith('.py'):
        compile(dst.read_text(), str(dst), 'exec')


def memory_plan():
    copy_from_screen('memory_plan.py')
    copy_from_screen('admission.json', rewrite=[('experiments/own-xpu-runtime/stage2/packet58-onecard-cache23/lineage/58ag-admission.json',
                                                 'experiments/own-xpu-runtime/stage2/packet58-onecard-cache23-chain/lineage/58ag-admission.json')])
    adm = G.read(P / 'admission.json')
    G.refuse(adm['admission']['cache_bytes'] == ARENA_NEW and adm['admission']['host_required_available_bytes'] == HOST_NEW
             and adm['admission']['device_owned_bound_bytes'] == BOUND_NEW and adm['admission']['host_bound_bytes'] == HOST_BOUND_NEW
             and adm['admission']['driver_allowance_bytes'] == 671088640 and adm['admission']['usable_cache_bytes'] == dict(max=ARENA_OLD, max23=ARENA_NEW),
             'copied admission block differs from the ruling')
    G.refuse(G.sha(P / 'lineage/58ag-admission.json') == 'dc13ab6ef8c23a5c747616dafe32d88d7b946b9e32e0ea1c757e39eff5fa7f41', 'lineage/58ag-admission.json differs from the pinned bytes')
    copy_from_screen('test_memory_plan.py')
    for name in ('budget_gate.py', 'test_memory_sensor.py', 'test_admission58e.py'):
        replace_once(name, str(HOST_OLD), str(HOST_NEW))
    replace_once('test_resident.py', f"self.assertEqual(b['device_categories']['expert_cache_arena'],{ARENA_OLD})", f"self.assertEqual(b['device_categories']['expert_cache_arena'],{ARENA_NEW})")
    replace_once('test_resident.py', f"self.assertEqual(b['host_bound_bytes'],{HOST_BOUND_OLD})", f"self.assertEqual(b['host_bound_bytes'],{HOST_BOUND_NEW})")
    replace_once('test_resident.py', f"self.assertEqual(b['host_required_available_bytes'],{HOST_OLD})", f"self.assertEqual(b['host_required_available_bytes'],{HOST_NEW})")
    # The plan now yields the ruling's numbers through the unchanged window.py / queue_runner.py path.
    sys.path.insert(0, str(P))
    import importlib
    for m in ('legacy_memory_plan', 'memory_plan'):
        sys.modules.pop(m, None)
    M = importlib.import_module('memory_plan')
    plan = M.window_plan('WS128')
    G.refuse(plan['host_required_available_bytes'] == HOST_NEW and plan['device_owned_bound_bytes'] == BOUND_NEW
             and plan['device_categories']['expert_cache_arena'] == ARENA_NEW and plan['driver_allowance_bytes'] == 671088640
             and plan['device_margin_bytes'] == 240 and M.CACHE_BYTES == ARENA_NEW and plan['host_bound_bytes'] == HOST_BOUND_NEW,
             'window_plan(WS128) does not reproduce the cache23 plan')
    return dict(host_required_available_bytes=plan['host_required_available_bytes'], device_owned_bound_bytes=plan['device_owned_bound_bytes'],
                device_categories=plan['device_categories'], driver_allowance_bytes=plan['driver_allowance_bytes'], device_margin_bytes=plan['device_margin_bytes'],
                host_bound_bytes=plan['host_bound_bytes'], memory_plan_source=record(C / 'memory-plan.json'))


def validator():
    n = 'packet58_submission.py'
    replace_once(n, "and command.count('--cache-bytes')==1 and command[command.index('--cache-bytes')+1]=='21552729600'",
                 "and command.count('--cache-bytes')==1 and command[command.index('--cache-bytes')+1]=='23049601024'")
    replace_once(n, "and command.count('--cache-cap')==1 and command[command.index('--cache-cap')+1]=='max'",
                 "and command.count('--cache-cap')==1 and command[command.index('--cache-cap')+1]=='max23'")
    replace_once(n, "memory['full_cache_bytes'] == 21_552_729_600", "memory['full_cache_bytes'] == 23_049_601_024")
    replace_once(n, f"label='{LABEL_OLD}'", f"label='{LABEL_NEW}'")
    replace_once(n, "optimization_identity='packet58aj-resident-tile16-overlap-tp1-plain-lru21.55gb-c4096-'",
                 "optimization_identity='packet58-onecard-cache23-chain-resident-tile16-overlap-tp1-plain-lru23.05gb-max23-c4096-'")
    replace_once(n, "'Target-only greedy; no draft/MTP. 29.3 GB anonymous exact resident lookup copies; 21.55 GB expert cache; zero-copy misses; '",
                 "'Target-only greedy; no draft/MTP. 29.3 GB anonymous exact resident lookup copies; 23.05 GB expert cache (cache_cap max23 = 23,049,601,024 B, '\n"
                 "          '+1.5 GB over the 21.55 GB record line, the only change; 30.5 GB DRM guard unchanged); zero-copy misses; '")
    replace_once(n, "immutableExpertWeightCacheBytes=21_552_729_600", "immutableExpertWeightCacheBytes=23_049_601_024")
    replace_once(n, "'# Packet58aj one-card scoped measurement\\n\\n'",
                 "'# Packet58-onecard-cache23-chain: one-card scoped measurement (128-token capped suite; expert cache 21.55 -> 23.05 GB, max23)\\n\\n'")
    t = 'test_submission.py'
    replace_once(t, "'--cache-cap','max','--cache-bytes','21552729600'", "'--cache-cap','max23','--cache-bytes','23049601024'")
    replace_once(t, "full_cache_bytes=21_552_729_600", "full_cache_bytes=23_049_601_024")
    replace_once(t, "for flag,value in [('--cache-cap','18GB'),('--cache-bytes','18000000000')]:",
                 "for flag,value in [('--cache-cap','18GB'),('--cache-bytes','18000000000'),('--cache-cap','max'),('--cache-bytes','21552729600')]:  # the 35.927 record line is refused as this candidate")
    replace_once(t, "        self.assertIn('realistic_final_gate.passed=false',notes)\n",
                 "        self.assertIn('realistic_final_gate.passed=false',notes)\n"
                 "        for text in ('23.05 GB expert cache', 'cache_cap max23', '23,049,601,024', '21.55 GB record line', '128-token owner scope', '30.5 GB DRM guard unchanged'):\n"
                 "            self.assertIn(text, notes)\n"
                 "        self.assertEqual(r['label'], '" + LABEL_NEW + "')\n"
                 "        self.assertIn('lru23.05gb-max23', r['promotionIdentity']['optimization_identity'])\n")
    r = 'rehearse_submission.py'
    replace_once(r, "w['postload_memory']['full_cache_bytes']=21552729600", "w['postload_memory']['full_cache_bytes']=23049601024")
    replace_once(r, "            driver['command']+=['--lookups','resident','--hc-geometry','hc-wide','--experts','wide64+halfcache','--other-fusion','fused','--retirement','ordered-foreground']\n",
                 "            driver['command']+=['--lookups','resident','--hc-geometry','hc-wide','--experts','wide64+halfcache','--other-fusion','fused','--retirement','ordered-foreground']\n"
                 "            # packet58-onecard-cache23-chain: synthetic capacity identity substitution (in memory only), like the composition flags above.\n"
                 "            for flag,value in (('--cache-cap','max23'),('--cache-bytes','23049601024')):\n"
                 "                if flag in driver['command']:driver['command'][driver['command'].index(flag)+1]=value\n"
                 "                else:driver['command']+=[flag,value]\n")
    replace_once(r, "assert len(notes)<=2000 and '21.55 GB' in notes", "assert len(notes)<=2000 and '23.05 GB expert cache' in notes and 'max23' in notes")
    replace_once(r, "        for text in ('128-token', 'no strict512', 'anonymous exact resident', 'Post-result',\n                     '26.928/31.959/31.558/32.061/31.525', '60/60 exact', '58ah a:', '58ah quiet-host b'):",
                 "        for text in ('128-token', 'no strict512', 'anonymous exact resident', '23.05 GB expert cache', 'cache_cap max23',\n                     '35.892 / 36.546 / 35.929 / 36.569 / 35.925', '60/60 exact', 'cmvjejvoi03qcrf0138emu5a6', '58ah a:', '58ah quiet-host b'):")
    replace_once(r, "(P/'evidence/submission-rehearsal.json')", "(P/'evidence/submission-rehearsal-cache23.json')")


def engine_binding():
    binaries = dict(device=('build/device/own-rt-iq3', DEVICE_SHA), host_parser=('build/gnu-host/own-rt-iq3', HOST_SHA), k1_fixture=('build/device/p58-cache-fixtures', K1_SHA))
    for key, (leaf, digest) in binaries.items():
        G.refuse(G.sha(P / leaf) == digest, f'{leaf} is not the expected binary ({key})')
    G.refuse(G.sha(C / 'build/device/own-rt-iq3') == DEVICE_SHA and G.sha(C / 'build/gnu-host/own-rt-iq3') == HOST_SHA, 'packet58-onecard-cache23 build binaries changed')
    G.refuse(G.sha(C182 / 'build/device/p58-cache-fixtures') == K1_SHA, 'packet182c-chain K1 fixture differs from the inherited one')
    provenance = [record(C / n) for n in ('native/generated/main.cpp', 'native-cache23-delta.patch', 'evidence/build.json', 'evidence/cache-identity.json',
                                           'evidence/preparation.json', 'evidence/loader.json', 'screen/build-receipt.json', 'memory-plan.json', 'READY-FOR-DEVICE.json')]
    build = G.read(C / 'evidence/build.json')
    G.refuse(build['artifacts']['build/device/own-rt-iq3'] == DEVICE_SHA and build['warnings'] == 0, 'cache23 build receipt does not bind the engine')
    row = dict(schema='packet58cache23chain.engine-binding.v1', passed=True, device_executed=False, compiled_here=False, compiler_runs=0, relinked=False,
               reused_byte_for_byte=True,
               engine=dict(path='build/device/own-rt-iq3', sha256=DEVICE_SHA, source=record(C / 'build/device/own-rt-iq3'),
                           parent_record_line_engine='1b41fb4da10a3c8c644f44f6288b9b1af0f46300847a06a254420796af921145',
                           identity='packet58-onecard-cache23 rebuilt entry TU (native-cache23-delta.patch: one 23,049,601,024-byte arena, --cache-cap 18GB|max|max23, '
                                    'device bound 29,828,911,360) over the packet182c/176 engine text; 79 parent objects relinked unchanged; 0 warnings'),
               host_parser=dict(path='build/gnu-host/own-rt-iq3', sha256=HOST_SHA, source=record(C / 'build/gnu-host/own-rt-iq3'),
                                role='--p58r-parse-test real-parser gate and the script-mode argv check; never a timing binary'),
               k1_fixture=dict(path='build/device/p58-cache-fixtures', sha256=K1_SHA, source=record(C182 / 'build/device/p58-cache-fixtures'),
                               role='K1a/K1b inherited fixture (packet58ag/58aj/182c byte-identical); no model flags'),
               cache23_provenance=provenance,
               inherited_gates_note='evidence/postload-allocation-cpu.json, fullshape-submit-cpu.json, resident-*-cpu.json and packet58ajb-preparation.json are the parent '
                                    'harness gates copied byte for byte (packet182c did the same for its engine); the cache23 engine\'s own allocation/full-shape/startup '
                                    'proofs are the provenance records above (read in place)')
    G.save(P / 'engine-binding.json', row)
    LOG.append(dict(file='engine-binding.json', action='written', after_sha256=G.sha(P / 'engine-binding.json')))
    # restore path: the two engine binaries restore from the screen packet's host-local build (digest-verified by restore_build.py)
    manifest = G.read(P / 'restore-inputs.json')
    G.refuse(not any(r['destination'] in ('build/device/own-rt-iq3', 'build/gnu-host/own-rt-iq3') for r in manifest['files']), 'restore manifest already carries the engines')
    before = G.sha(P / 'restore-inputs.json')
    manifest['files'] += [dict(destination='build/device/own-rt-iq3', source=rel(C / 'build/device/own-rt-iq3'), sha256=DEVICE_SHA),
                          dict(destination='build/gnu-host/own-rt-iq3', source=rel(C / 'build/gnu-host/own-rt-iq3'), sha256=HOST_SHA)]
    manifest['engine_note'] = 'packet58-onecard-cache23-chain: the engines are byte copies of packet58-onecard-cache23/build (083e3853 / 03a2aa12); never run build_engine.py here'
    G.save(P / 'restore-inputs.json', manifest)
    LOG.append(dict(file='restore-inputs.json', action='engine records appended', before_sha256=before, after_sha256=G.sha(P / 'restore-inputs.json')))
    return row


def gitignore():
    path = P / '.gitignore'
    before = G.sha(path)
    extra = ('\n# packet58-onecard-cache23-chain: bulky device streams of the chain stay host-local but IGNORED (never untracked-and-unignored);\n'
             '# summary.json / window.json / queue.json / *.log of every window are committable and are committed right after the window.\n'
             '/evidence/card0-cache23-a/*/run/\n/evidence/card0-cache23-a/*/native-home/\n/evidence/card0-cache23-a/*/*.jsonl\n')
    G.refuse('card0-cache23-a' not in path.read_text(), '.gitignore already carries the chain rules')
    G.put(path, path.read_text().rstrip('\n') + '\n' + extra)
    LOG.append(dict(file='.gitignore', action='chain output ignore rules appended', before_sha256=before, after_sha256=G.sha(path)))


def memory_md(plan):
    path = P / 'MEMORY.md'
    before = G.sha(path)
    cats = plan['device_categories']
    text = f'''# Production-size memory accounting (packet58-onecard-cache23-chain)

The packet58u/58ah accounting is extended by the packet58-onecard-cache23 re-partition (coordinator
ruling, one-card synthesis 1): the 98,990,252,032-byte admission at a 21.55 GB cache (packet182c) becomes
**100,487,123,456 bytes** at the 23,049,601,024-byte arena (`cache_cap max23`): full host backing of the
+1,496,871,424-byte growth. No admission is lowered. Source: `admission.json` (`admission` block, copied from
packet58-onecard-cache23) and that packet's `memory-plan.json` (every number with its receipt).

| Window | Pinned experts | Resident lookups | Host bound | Reserve | Required available |
| --- | ---: | ---: | ---: | ---: | ---: |
| K1a | 0 | 0 | 4,294,967,296 | 8,589,934,592 | 12,884,901,888 |
| K1b | 0 | 0 | 4,294,967,296 | 8,589,934,592 | 12,884,901,888 |
| KD | 48,627,712,000 | 29,321,610,240 | {plan['host_bound_bytes']:,} | 8,589,934,592 | {plan['host_required_available_bytes']:,} |
| W2m | 48,627,712,000 | 29,321,610,240 | {plan['host_bound_bytes']:,} | 8,589,934,592 | {plan['host_required_available_bytes']:,} |
| WS | 48,627,712,000 | 29,321,610,240 | {plan['host_bound_bytes']:,} | 8,589,934,592 | {plan['host_required_available_bytes']:,} |
| WS128x | 48,627,712,000 | 29,321,610,240 | {plan['host_bound_bytes']:,} | 8,589,934,592 | {plan['host_required_available_bytes']:,} |
| WS128 | 48,627,712,000 | 29,321,610,240 | {plan['host_bound_bytes']:,} | 8,589,934,592 | {plan['host_required_available_bytes']:,} |

All numbers are bytes. K1 is a bounded synthetic fixture, not the full model.
Device cache allocation is 23,049,601,024 bytes in every model window (`--cache-bytes 23049601024`,
`--cache-cap max23`: the whole arena is usable; `max` = 21,552,729,600 usable is the packet182c record policy).
Device-owned bound {plan['device_owned_bound_bytes']:,} = floor 32,000,000,000 - reserve 1,500,000,000 - driver
allowance {plan['driver_allowance_bytes']:,} (measured lifetime overhead 604,827,916 over the packet182c chain).
Device categories: target_nonexpert {cats['target_nonexpert']:,}; KV {cats['target_4k_bf16_kv_index']:,}; recurrent
{cats['target_recurrent']:,}; pointer tables {cats['expert_pointer_generation_tables']:,}; publication staging
{cats['async_publication_staging']:,}; half table {cats['exact_half_decode_table']:,}; arena {cats['expert_cache_arena']:,};
transfer bound {cats['transfer_bound']:,}; control transaction bound {cats['control_transaction_bound']:,}; workspace
bound {cats['workspace_bound']:,}; category sum {sum(cats.values()):,}; margin {plan['device_margin_bytes']} bytes.
Projected after growth (packet58-onecard-cache23 `memory-plan.json`): allocate() peak 29,338,775,796 (490,135,564
under the bound); DRM 29,943,603,712 (556,396,288 under the unchanged 30.5 GB native/supervisor guard). The
packet58-onecard-cache23 screen measured the same plan live on card 0 (2026-10-23) with no guard trip.

The host categories are disjoint: pinned experts 48,627,712,000; resident lookups 29,321,610,240; remaining
file allowance 4,001,477,120; measured process overhead 565,325,824; independent shadow margin 4,294,967,296;
cache/metadata/staging 5,084,859,392 (3,587,987,968 + the 1,496,871,424 growth); newer observed increment
1,236,992. They total {plan['host_bound_bytes']:,} bytes. The unchanged 8 GiB reserve is additional.
The 4 GiB shadow and 8 GiB available-memory stops are retained. No model payload was read to derive this table.
'''
    G.put(path, text)
    LOG.append(dict(file='MEMORY.md', action='rewritten for the cache23 plan', before_sha256=before, after_sha256=G.sha(path)))


def inherited_docs():
    for name in ('README.md', 'DO-NOT-REPEAT.md'):
        src = P / name
        dst = P / 'lineage' / ('inherited-58aj-' + name)
        G.refuse(not dst.exists(), f'{dst.name} already exists')
        shutil.copy2(src, dst)
        LOG.append(dict(file='lineage/' + dst.name, action='inherited packet58aj document moved aside (README/DO-NOT-REPEAT are rewritten for this packet)',
                        after_sha256=G.sha(dst)))


def main():
    G.refuse(P.is_dir() and (P / 'derived-chain.json').is_file(), 'derived packet missing; run derive_cache23_chain.py first')
    G.refuse(not (P / 'evidence/cache23-chain-delta.json').exists(), 'cache23 chain delta already applied')
    plan = memory_plan()
    validator()
    binding = engine_binding()
    gitignore()
    memory_md(plan)
    inherited_docs()
    remaining = []
    for f in sorted(P.glob('*.py')) + [P / 'runtime-selection.json', P / 'views.py', P / 'MEMORY.md']:
        text = f.read_text()
        for lit in (str(ARENA_OLD), '21_552_729_600', str(HOST_OLD), str(HOST_BOUND_OLD), str(BOUND_OLD)):
            if lit in text:
                remaining.append(dict(file=f.name, literal=lit))
    row = dict(schema='packet58cache23chain.delta.v1', passed=True, device_executed=False, edits=LOG, plan=plan,
               engine=dict(device=DEVICE_SHA, host_parser=HOST_SHA, k1_fixture=K1_SHA),
               old_literals_remaining=remaining,
               old_literals_note='remaining occurrences sit in inherited gate scripts whose receipts were copied byte for byte from the parent '
                                 '(argument_gate.py, native_parser_gate.py, screen_gate.py, plan_queue.py proposal text, screen-reader/views.py) '
                                 'and in the validator/tests as the REFUSED old values; none is on the chain launch path, which carries max23/23049601024 '
                                 '(evidence/chain-flags.json, evidence/script-argv-check.json)')
    G.save(P / 'evidence/cache23-chain-delta.json', row)
    print(json.dumps(dict(passed=True, edits=len(LOG), remaining=remaining)))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except G.Refused as e:
        print('apply_cache23_chain_delta: REFUSED ' + str(e), file=sys.stderr)
        raise SystemExit(2)
