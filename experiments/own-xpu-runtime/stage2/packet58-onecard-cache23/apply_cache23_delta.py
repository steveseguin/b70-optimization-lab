#!/usr/bin/env python3
"""Packet58-onecard-cache23 native delta over the packet182 HEAD copy.

Coordinator ruling (one-card synthesis 1, 2026-10-22): the packet182c selection unchanged
plus a `cache_cap max23` view value = 23,049,601,024 bytes (256-aligned, +6.95 %), switched
at the drained view boundary like `18GB|max`, with the device plan re-partitioned from the
182c lifetime receipts (driver allowance 671,088,640; device-owned bound 29,828,911,360).

What this applies, every replacement exact and counted (rerunning on changed text refuses):

1. Self-containment: every absolute `stage2/packet176-onecard-kernelio/` include/#line path in
   native/ becomes this packet's path (the 78 frozen headers and 12 native headers are
   byte-identical tracked copies; __FILE__ now resolves rope.bf16 inside this packet).
2. main.cpp: one arena of 23,049,601,024 bytes per load (`--cache-bytes`), `--cache-cap`
   18GB|max|max23 with `max` = 21,552,729,600 usable (packet182c's policy, byte-for-byte: the
   cache's decisions depend only on base and capacity, see cache23_identity_test.cpp) and
   `max23` = the full arena; both device bound literals 29,963,128,848 -> 29,828,911,360;
   the view boundary record reports the new allocation.
3. fullshape_submit_test.hpp / postload_allocation_test.hpp: arena literals, plus a max23
   switch check in the full-shape mock.
4. bracket_table.hpp: capacity is the view dimension (A = max, B = max23), kernel foreground
   I/O fixed in every view.
5. preparation_probe.cpp: kernel I/O expected in all five views (60 tail stores / 60 head
   loads) and the device census peak written into preparation.json.

Literals changed (name every one): 21552729600 (default/require/arena/reset/boundary-record,
fullshape, postload), 29963128848 (allocate bound, plan bound), "max" accept lists (parse,
cache_capacity, bracket rows/smoke/order), kernel_tail/head 24 -> 60. Unchanged on purpose:
18000000000 (18GB usable value), 30500000000 (DRM guard, never lowered), 1500000000 reserve.
"""
import difflib, json, shutil, sys
from pathlib import Path

P = Path(__file__).resolve().parent
N = P / 'native'
OLD_PACKET = 'stage2/packet176-onecard-kernelio/'
NEW_PACKET = 'stage2/' + P.name + '/'
SNAPSHOT = P / 'lineage/p182-parent-native/native'
ARENA = 23049601024
MAX = 21552729600
BOUND = 29828911360
OLD_BOUND = 29963128848
TOUCHED = ('generated/main.cpp', 'generated/fullshape_submit_test.hpp', 'generated/postload_allocation_test.hpp',
           'bracket_table.hpp', 'preparation_probe.cpp')


def sub(path, old, new, count=1):
    text = path.read_text()
    assert text.count(old) == count, (str(path), old[:90], text.count(old))
    path.write_text(text.replace(old, new))


def rewrite_paths():
    changed = {}
    for f in sorted(N.rglob('*')):
        if not f.is_file():
            continue
        text = f.read_text()
        n = text.count(OLD_PACKET)
        if n:
            f.write_text(text.replace(OLD_PACKET, NEW_PACKET))
            changed[str(f.relative_to(P))] = n
    assert changed['native/generated/main.cpp'] == 41 and changed['native/generated/single_device.cpp'] == 8, changed
    return changed


def snapshot():
    assert not SNAPSHOT.exists(), 'snapshot exists: delta already applied'
    for rel in TOUCHED + ('generated/single_device.cpp',):
        dest = SNAPSHOT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(N / rel, dest)


def main_cpp(path):
    sub(path, 'uint64_t cache_bytes=21552729600ull;std::string cache_cap="max";',
        f'uint64_t cache_bytes={ARENA}ull;std::string cache_cap="max";')
    sub(path, '--cache-bytes --cache-cap --cache-maintenance', '--cache-bytes --cache-cap 18GB|max|max23 (default:max) --cache-maintenance')
    sub(path, 'require(a.cache_cap=="18GB"||a.cache_cap=="max","cache capacity mode");',
        'require(a.cache_cap=="18GB"||a.cache_cap=="max"||a.cache_cap=="max23","cache capacity mode");')
    sub(path, 'require(a.mini||a.cache_bytes==21552729600ull,"single admitted maximum allocation required");',
        f'require(a.mini||a.cache_bytes=={ARENA}ull,"single admitted maximum allocation required");')
    sub(path, 'a.cache_bytes<=21552729600ull && (a.mini||a.memory=="resident")',
        f'a.cache_bytes<={ARENA}ull && (a.mini||a.memory=="resident")')
    sub(path, 'require(cap=="18GB"||cap=="max","cache capacity dimension");',
        'require(cap=="18GB"||cap=="max"||cap=="max23","cache capacity dimension");')
    sub(path, 'require(arena.live&&arena.bytes==21552729600ull,"maximum arena must remain allocated");',
        f'require(arena.live&&arena.bytes=={ARENA}ull,"maximum arena must remain allocated");')
    sub(path, 'expert_cache->reset_capacity(cap=="18GB"?18000000000ull:21552729600ull);',
        f'expert_cache->reset_capacity(cap=="18GB"?18000000000ull:cap=="max23"?{ARENA}ull:{MAX}ull);')
    sub(path, f'require(owned_bytes.at(c) + bytes <= {OLD_BOUND}ull,\n              "29,963,128,848-byte admitted device allocation bound");',
        f'require(owned_bytes.at(c) + bytes <= {BOUND}ull,\n              "29,828,911,360-byte admitted packet58-cache23 device allocation bound");')
    sub(path, f'require(peak_bytes<={OLD_BOUND}ull,"planned card exceeds admitted packet58x device bound");',
        f'require(peak_bytes<={BOUND}ull,"planned card exceeds admitted packet58-cache23 device bound");')
    sub(path, '",\\"cache_cap\\":"+ownrt::quote(view.capacity)+",\\"cache_allocation_bytes\\":21552729600,\\"cache_started_empty\\":true"+',
        '",\\"cache_cap\\":"+ownrt::quote(view.capacity)+",\\"cache_allocation_bytes\\":' + str(ARENA) + ',\\"cache_usable_bytes\\":"+std::to_string(e->expert_cache?e->expert_cache->capacity():0)+",\\"cache_started_empty\\":true"+')
    assert '21552729600' not in path.read_text().replace(f'{MAX}ull', '') or True
    text = path.read_text()
    assert text.count('21552729600') == 1, 'only the max usable literal remains'
    assert str(OLD_BOUND) not in text


def fullshape(path):
    sub(path, 'a.cache_bytes=21552729600ull;', f'a.cache_bytes={ARENA}ull;')
    sub(path, 'engine.cache_mode(mode);engine.cache_capacity("max");require(engine.expert_cache->capacity()==21552729600ull,"fullshape active cache cap");',
        f'engine.cache_mode(mode);engine.cache_capacity("max23");require(engine.expert_cache->capacity()=={ARENA}ull,"fullshape max23 cache cap");'
        f'engine.cache_capacity("max");require(engine.expert_cache->capacity()=={MAX}ull,"fullshape active cache cap");')


def postload(path):
    sub(path, 'a.cache_bytes==21552729600ull,"KD geometry"', f'a.cache_bytes=={ARENA}ull,"KD geometry"')
    sub(path, 'require(arena.row(engine.cache_arena).bytes==21552729600ull,"cache allocation extent");',
        f'require(arena.row(engine.cache_arena).bytes=={ARENA}ull,"cache allocation extent");')


def bracket_table(path):
    sub(path, 'require(v.capacity=="max","fixed maximum cache");',
        'require(v.capacity=="max"||v.capacity=="max23","cache capacity dimension");')
    sub(path, 'require(v.hc=="spin"||v.hc=="spin-kio","foreground io dimension");',
        'require(v.hc=="spin-kio","kernel foreground io fixed throughout the capacity bracket");')
    sub(path, 'views[0].label=="S0"&&views[0].capacity=="max"&&views[0].hc=="spin-kio"',
        'views[0].label=="S0"&&views[0].capacity=="max23"&&views[0].hc=="spin-kio"')
    sub(path, 'require(views[i].label==labels[i]&&views[i].hc==(i%2?"spin-kio":"spin"),"production/p60fusion bracket order");',
        'require(views[i].label==labels[i]&&views[i].capacity==(i%2?"max23":"max")&&views[i].hc=="spin-kio","max/max23 capacity bracket order");')


def probe(path):
    sub(path, 'require(transport->kernel_tail==24&&transport->kernel_head==24,"p176 kernel io in both B views");',
        'require(transport->kernel_tail==60&&transport->kernel_head==60,"p176 kernel io in all five views");')
    sub(path, ',\\"synthetic_weights\\":true,\\"driver_stall_tested\\":false}\\n";',
        ',\\"synthetic_weights\\":true,\\"driver_stall_tested\\":false,\\"peak_device_bytes\\":"+std::to_string(engine->peak_device_bytes)+'
        '",\\"cache_allocation_bytes\\":"+std::to_string(a.cache_bytes)+",\\"device_owned_bound_bytes\\":' + str(BOUND) + '}\\n";')


def patch():
    out = []
    for rel in TOUCHED:
        a = (SNAPSHOT / rel).read_text().splitlines(keepends=True)
        b = (N / rel).read_text().splitlines(keepends=True)
        out += difflib.unified_diff(a, b, 'a/native/' + rel, 'b/native/' + rel)
    (P / 'native-cache23-delta.patch').write_text(''.join(out))


if __name__ == '__main__':
    assert '--apply' in sys.argv, 'pass --apply once on the fresh copy'
    changed = rewrite_paths()
    snapshot()
    main_cpp(N / 'generated/main.cpp')
    fullshape(N / 'generated/fullshape_submit_test.hpp')
    postload(N / 'generated/postload_allocation_test.hpp')
    bracket_table(N / 'bracket_table.hpp')
    probe(N / 'preparation_probe.cpp')
    patch()
    (P / 'lineage/p182-parent-native/README.md').write_text(
        '# Pre-delta native snapshot\n\nThe packet182 (= packet176 engine) native text of the five files the cache23 delta touches, '
        'plus single_device.cpp, taken after the path self-containment rewrite and before `apply_cache23_delta.py`. '
        'test_cache23_delta.py must fail on this tree and pass on native/.\n')
    (P / 'lineage/path-rewrite.json').write_text(json.dumps(dict(old=OLD_PACKET, new=NEW_PACKET, files=changed), indent=2) + '\n')
    print(json.dumps(dict(applied=True, path_rewritten_files=len(changed), touched=list(TOUCHED))))
