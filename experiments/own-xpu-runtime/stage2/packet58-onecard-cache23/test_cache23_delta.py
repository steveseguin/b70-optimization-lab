"""Packet58-cache23 source-delta test. Passes on this packet's native sources and fails on the
pre-delta snapshot (lineage/p182-parent-native: packet182 = packet176 engine text after the path
self-containment rewrite, before the cache23 delta). Also keeps the packet176 kernel-I/O delta
checks of packet182's test (the engine must still carry kernel foreground I/O) and requires the
backend TU and the cache policy header untouched. CPU only; reads text."""
import re, unittest
from pathlib import Path
P = Path(__file__).resolve().parent
OLD = P / 'lineage/p182-parent-native/native'
ARENA, MAX, BOUND = '23049601024ull', '21552729600ull', '29828911360ull'


def body(text, head):
    i = text.index(head); depth = 0
    for j in range(text.index('{', i), len(text)):
        depth += text[j] == '{'; depth -= text[j] == '}'
        if depth == 0:
            return text[i:j + 1]
    raise AssertionError(head)


def problems(root):
    out = []
    main = (root / 'generated/main.cpp').read_text(); bt = (root / 'bracket_table.hpp').read_text(); probe = (root / 'preparation_probe.cpp').read_text()
    full = (root / 'generated/fullshape_submit_test.hpp').read_text(); post = (root / 'generated/postload_allocation_test.hpp').read_text()
    if f'uint64_t cache_bytes={ARENA};std::string cache_cap="max";' not in main: out.append('default arena')
    if 'a.cache_cap=="max23"' not in main or 'cap=="max23"' not in main: out.append('max23 accepted')
    if f'require(a.mini||a.cache_bytes=={ARENA},"single admitted maximum allocation required");' not in main: out.append('single allocation literal')
    if f'a.cache_bytes<={ARENA} && (a.mini||a.memory=="resident")' not in main: out.append('cache bound literal')
    if f'require(arena.live&&arena.bytes=={ARENA},"maximum arena must remain allocated");' not in main: out.append('arena extent check')
    if f'expert_cache->reset_capacity(cap=="18GB"?18000000000ull:cap=="max23"?{ARENA}:{MAX});' not in main: out.append('usable extents')
    if f'owned_bytes.at(c) + bytes <= {BOUND}' not in main or f'require(peak_bytes<={BOUND},' not in main: out.append('device bound 29,828,911,360')
    if '29963128848' in main: out.append('old bound literal still present')
    if main.count('21552729600') != 1: out.append('max usable literal must appear exactly once')
    if '"cache_allocation_bytes\\":23049601024,\\"cache_usable_bytes\\":"' not in main: out.append('boundary record allocation/usable')
    if '--cache-cap 18GB|max|max23 (default:max)' not in main: out.append('help')
    if 'peak<=30500000000ull' not in main: out.append('DRM guard 30.5 GB unchanged')
    if f'a.cache_bytes={ARENA};' not in full or f'engine.cache_capacity("max23");require(engine.expert_cache->capacity()=={ARENA}' not in full: out.append('fullshape max23 switch')
    if f'a.cache_bytes=={ARENA},"KD geometry"' not in post or f'bytes=={ARENA},"cache allocation extent"' not in post: out.append('postload literals')
    if 'require(v.capacity=="max"||v.capacity=="max23","cache capacity dimension");' not in bt: out.append('bracket capacity dimension')
    if 'require(v.hc=="spin-kio","kernel foreground io fixed throughout the capacity bracket");' not in bt: out.append('bracket kernel io fixed')
    if 'views[i].capacity==(i%2?"max23":"max")&&views[i].hc=="spin-kio"' not in bt: out.append('bracket order max/max23')
    if 'transport->kernel_tail==60&&transport->kernel_head==60' not in probe or 'peak_device_bytes' not in probe: out.append('probe: 5 kernel-io views + census peak')
    # packet176 kernel I/O delta still present (packet182 test_kernelio_delta essentials)
    if 'p176::kernel_io=a.bracket_inputs.empty()?a.foreground_io=="kernel":view.hc=="spin-kio";' not in main: out.append('kernel io view switch')
    if not re.search(r'if\(kernel_io\)e->tail_store\(\);', main): out.append('tail store placement')
    if 'if(p176::kernel_io){require(tail_routes_written,"kernel route log missing for this position");' not in main: out.append('route log from kernel')
    if 'require(!status,"sticky device error at token "' not in main: out.append('sticky error check')
    return out


def norm(text):
    return text.replace('packet58-onecard-cache23', 'X').replace('packet182-onecard-kio-rebracket', 'X')


class Cache23Delta(unittest.TestCase):
    def test_candidate_source(self):
        self.assertEqual(problems(P / 'native'), [])

    def test_fails_on_parent_source(self):
        self.assertGreaterEqual(len(problems(OLD)), 12)

    def test_backend_policy_and_untouched_bodies(self):
        self.assertEqual(norm((P / 'native/generated/single_device.cpp').read_text()), norm((OLD / 'generated/single_device.cpp').read_text()))
        main = norm((P / 'native/generated/main.cpp').read_text()); parent = norm((OLD / 'generated/main.cpp').read_text())
        for head in ('void cache_boundary()', 'void cache_plan_during_position()', 'void publish_cache_table(const std::vector<p58::Entry>& table)',
                     'void upload(int c, Allocation dst, size_t offset, const void *src, size_t n)', 'void drain()', 'void prepare_token(int token)',
                     'void tail_store()', 'void head_end()', 'void cache_mode(const std::string& mode)'):
            self.assertEqual(body(main, head), body(parent, head), head)
        cap_new, cap_old = body(main, 'void cache_capacity(const std::string& cap)'), body(parent, 'void cache_capacity(const std::string& cap)')
        self.assertNotEqual(cap_new, cap_old)
        self.assertEqual(cap_new.replace('||cap=="max23"', '').replace(ARENA, MAX).replace('cap=="max23"?' + MAX + ':', ''), cap_old)

    def test_delta_scope(self):
        touched = sorted({l[6:].strip() for l in (P / 'native-cache23-delta.patch').read_text().splitlines() if l.startswith('+++ b/')})
        self.assertEqual(touched, ['native/bracket_table.hpp', 'native/generated/fullshape_submit_test.hpp', 'native/generated/main.cpp',
                                   'native/generated/postload_allocation_test.hpp', 'native/preparation_probe.cpp'])
        import json
        rewrite = json.loads((P / 'lineage/path-rewrite.json').read_text())
        self.assertEqual(rewrite['files']['native/generated/main.cpp'], 41)
        self.assertEqual(len(rewrite['frozen_inputs']['files']), 79)

    def test_cache_policy_header_untouched(self):
        import subprocess
        parent = subprocess.run(['git', '-C', str(P.parents[3]), 'show', 'HEAD:experiments/own-xpu-runtime/stage2/packet182-onecard-kio-rebracket/native/cache_table.hpp'],
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True).stdout
        self.assertEqual((P / 'native/cache_table.hpp').read_text(), parent)


if __name__ == '__main__':
    unittest.main()
