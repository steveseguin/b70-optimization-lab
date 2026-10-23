#!/usr/bin/env python3
"""Packet58-onecard-cache23-chain derivation: ops/onecard_chain_derive.py with the packet182 repairs.

CPU only; never launches, queues or touches a device, service or PAUSE file. The ops generator is
imported unchanged (its file is byte-pinned in the orchestration); this wrapper replaces functions in
the imported module only, exactly as packet182's chain/derive_chain.py did for packet182c:

1. inject: the generated suite_driver flag block is moved before the single `if __name__` entry guard
   (the chain-176-a defect; window.py runs suite_driver.py as a script). Byte-identical repair to
   packet182 chain/derive_chain.py (relocate_flag_block / fixed_inject).
2. postnative_gate: the generator looks for completed chain evidence only under the bracket packet and
   the parent packet; neither has any. packet182c-chain/evidence/card0-182-a (2026-10-22, all 7 windows
   passed on this boot) is the real completed one-card chain of this harness, so it is used as the
   post-native report rehearsal input (read in place; the generator copies it to a temporary dir).
3. prefix_gate: the generator refuses any --packet whose prefix (text before the first '-') matches an
   existing stage2 directory. The ruling names this packet `packet58-onecard-cache23-chain`, prefix
   `packet58`, which stage2 already carries (packet58-onecard, packet58-onecard-cache23). The pin guard
   only globs ops/<prefix>-* into a packet's closure, so the real hazard is an ops directory named
   packet58-*: this orchestration is therefore `ops/packet58c23chain-orchestration` (never matched by
   `packet58-*`) and the override requires that glob to be empty. packet58-onecard-cache23 itself was
   sealed under the same prefix with 0 cross-packet mutable pins.

4. capacity argv/selection (this packet's one functional change at derivation time): the cache23 engine
   hard-codes one 23,049,601,024-byte arena and refuses the parent argv (`--cache-bytes 21552729600`:
   "single admitted maximum allocation required", seen on the first run), so before the generator's
   real-parser gate the copied suite_driver.py argv/summary literals and the views.py sealed-selection
   literal become `--cache-cap max23 --cache-bytes 23049601024`; runtime-selection.json gets the same
   three keys at the first pin-relocation call (after the generator's parent-selection equality check,
   before seal/verify_ready/pre-device rehearsal). Every edit is an exact-once literal replacement,
   recorded in capacity-patch.json. The memory plan, admission, submission validator and tests are
   the second phase (apply_cache23_chain_delta.py + reseal.py).

Phase 1 result: packet182c-chain re-derived from packet58aj-orchestration with the cache23 engine
bytes and the max23 capacity argv/selection.

Usage (repo root, CPU cores): nice -n 19 taskset -c 8-15,24-31 python3 -B <this> </dev/null
"""
import json, sys
from pathlib import Path

ROOT = Path('/home/steve/llm-optimizations')
HERE = ROOT / 'experiments/own-xpu-runtime/ops/packet58c23chain-orchestration'   # created by the generator; the wrapper is copied in afterwards
X = ROOT / 'experiments/own-xpu-runtime'
OPS = X / 'ops'
GUARD = "if __name__=='__main__':"
BRACKET_PACKET = X / 'stage2/packet58-onecard-cache23'
REAL_CHAIN_EVIDENCE = X / 'stage2/packet182c-chain/evidence/card0-182-a'
PACKET = X / 'stage2/packet58-onecard-cache23-chain'
UNIT = 'packet58-onecard-cache23-a'
OUTPUT = 'evidence/card0-cache23-a'

sys.path.insert(0, str(OPS))
sys.path.insert(0, str(OPS / 'lane-queue'))
import onecard_chain_derive as G  # noqa: E402

_original_inject = G.inject
_original_postnative = G.postnative_gate
_original_prefix_gate = G.prefix_gate


def relocate_flag_block(text):
    """Move the generated suite_driver block (appended at EOF) before the single entry guard (packet182)."""
    G.refuse(text.count(G.MARK) == 1, 'suite_driver.py must carry exactly one generated block')
    head, _, block = text.partition('\n\n' + G.MARK)
    G.refuse(block and head.count(GUARD) == 1 and GUARD not in block,
             'suite_driver.py must have exactly one entry guard before the generated block')
    at = head.index(GUARD)
    fixed = head[:at] + G.MARK + block.rstrip('\n') + '\n\n\n' + head[at:].rstrip('\n') + '\n'
    G.refuse(fixed.index(G.MARK) < fixed.index(GUARD) and fixed.count(GUARD) == 1,
             'generated chain flags must precede the script entry')
    return fixed


def fixed_inject(P, flags):
    _original_inject(P, flags)
    sd = P / 'suite_driver.py'
    G.put(sd, relocate_flag_block(sd.read_text()))
    compile(sd.read_text(), str(sd), 'exec')


def real_evidence_postnative(P, evidence):
    if evidence is None or not Path(evidence).is_dir():
        evidence = REAL_CHAIN_EVIDENCE
    rows = [evidence / w / 'window.json' for w in ('K1a', 'K1b', *G.MODEL_WINDOWS)]
    G.refuse(all(r.is_file() and G.read(r).get('passed') is True and G.read(r).get('device_executed') is True for r in rows),
             'packet182c-chain evidence card0-182-a is not a completed 7-window chain')
    row = _original_postnative(P, evidence)
    row['evidence_source'] = dict(packet='packet182c-chain', relpath=str(Path(evidence).relative_to(ROOT)),
                                  note='real completed one-card chain of this harness (2026-10-22); arena 21,552,729,600 B, so this '
                                       'rehearsal runs with the parent memory plan; the cache23 plan is rehearsed separately on the '
                                       'packet58-onecard-cache23 WSCREEN evidence (postnative-cache23.json)')
    return row


def relaxed_prefix_gate(P, O):
    prefix, sep, label = P.name.partition('-')
    G.refuse(sep == '-' and label and G.PREFIX.fullmatch(prefix), f'--packet name must be packet<digits><letters>-<label>: {P.name!r}')
    hits = sorted(str(p) for p in O.parent.glob(prefix + '-*'))
    G.refuse(not hits, f'ops/{prefix}-* must be empty (the pin guard globs it into this packet\'s closure): {hits}')
    G.refuse(not O.name.startswith(prefix + '-'), f'--out must not match ops/{prefix}-*: it would enter the closure of every stage2/{prefix}-* packet')
    return prefix


ARENA_OLD, ARENA_NEW = '21552729600', '23049601024'
CAPACITY_EDITS = {
    'suite_driver.py': [("'--cache-cap','max','--cache-bytes','21552729600'", "'--cache-cap','max23','--cache-bytes','23049601024'"),
                        ("cache_cap='max',cache_bytes=21552729600", "cache_cap='max23',cache_bytes=23049601024")],
    'views.py': [("cache_cap='max',cache_allocation_bytes=21552729600,cache_bytes=21552729600", "cache_cap='max23',cache_allocation_bytes=23049601024,cache_bytes=23049601024")],
}
PATCH_LOG = []
_original_parser_gate = G.parser_gate
_original_relocate_pins = G.relocate_pins


def replace_once(path, old, new):
    text = path.read_text()
    G.refuse(text.count(old) == 1, f'{path.name}: literal must occur exactly once: {old!r} (found {text.count(old)})')
    before = G.sha(path)
    G.put(path, text.replace(old, new))
    PATCH_LOG.append(dict(file=path.name, before_sha256=before, after_sha256=G.sha(path), old=old, new=new))


def capacity_patch_sources(P):
    for name, edits in CAPACITY_EDITS.items():
        for old, new in edits:
            replace_once(P / name, old, new)
        compile((P / name).read_text(), str(P / name), 'exec')
    text = (P / 'suite_driver.py').read_text() + (P / 'views.py').read_text() + (P / 'composition.py').read_text()
    G.refuse(ARENA_OLD not in text, 'a 21552729600 literal survives in the chain argv/selection sources')


def patched_parser_gate(P, flags):
    capacity_patch_sources(P)
    return _original_parser_gate(P, flags)


def patched_relocate_pins(P, P0, root, extra, changed=None):
    sel_path = P / 'runtime-selection.json'
    sel = G.read(sel_path)
    if sel.get('cache_cap') == 'max':
        G.refuse(sel['cache_allocation_bytes'] == sel['cache_bytes'] == int(ARENA_OLD), 'parent runtime selection carries an unexpected arena')
        before = G.sha(sel_path)
        sel.update(cache_cap='max23', cache_allocation_bytes=int(ARENA_NEW), cache_bytes=int(ARENA_NEW))
        G.save(sel_path, sel)
        PATCH_LOG.append(dict(file='runtime-selection.json', before_sha256=before, after_sha256=G.sha(sel_path),
                              old=dict(cache_cap='max', cache_allocation_bytes=int(ARENA_OLD), cache_bytes=int(ARENA_OLD)),
                              new=dict(cache_cap='max23', cache_allocation_bytes=int(ARENA_NEW), cache_bytes=int(ARENA_NEW))))
    return _original_relocate_pins(P, P0, root, extra, changed)


def install():
    G.inject = fixed_inject
    G.postnative_gate = real_evidence_postnative
    G.prefix_gate = relaxed_prefix_gate
    G.parser_gate = patched_parser_gate
    G.relocate_pins = patched_relocate_pins


def main():
    install()
    argv = ['--parent-orch', str(OPS / 'packet58aj-orchestration'), '--packet', str(PACKET), '--out', str(HERE),
            '--unit', UNIT, '--output', OUTPUT,
            '--binary', str(BRACKET_PACKET / 'build/device/own-rt-iq3'),
            '--host-binary', str(BRACKET_PACKET / 'build/gnu-host/own-rt-iq3'),
            '--bracket-summary', str(BRACKET_PACKET / 'screen/evidence/card0-58c23-v5-a/resident/WSCREEN/summary.json'),
            '--threshold-file', str(ROOT / 'scripts/packet58_onecard_record_threshold.json'),
            '--flag', 'wait-policy=spin', '--flag', 'foreground-io=kernel']
    rc = G.main(argv)
    if rc == 0:
        receipt = dict(schema='packet58c23chain.derivation.v1', passed=True, device_executed=False, generator='ops/onecard_chain_derive.py',
                       generator_sha256=G.sha(OPS / 'onecard_chain_derive.py'), argv=argv,
                       repairs=['inject: flag block before the entry guard (packet182 chain/derive_chain.py)',
                                'postnative_gate: real packet182c-chain evidence card0-182-a',
                                'prefix_gate: ops/packet58-* glob must be empty; orchestration dir outside that glob',
                                'parser_gate/relocate_pins: max23 capacity argv + selection literals before the real-parser gate (capacity-patch.json)'])
        import shutil
        shutil.copy2(__file__, HERE / 'derive_cache23_chain.py')
        receipt['wrapper_sha256'] = G.sha(HERE / 'derive_cache23_chain.py')
        G.save(HERE / 'derivation.json', receipt)
        G.save(HERE / 'capacity-patch.json', dict(schema='packet58c23chain.capacity-patch.v1', passed=True, device_executed=False,
                                                  arena_old=int(ARENA_OLD), arena_new=int(ARENA_NEW), edits=PATCH_LOG,
                                                  note='phase 1: argv/selection only; memory plan, admission, validator and tests follow in apply_cache23_chain_delta.py'))
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
