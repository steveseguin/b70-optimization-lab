"""Packet58-onecard-diet-engine source-delta test. Passes on this packet's native sources and fails on the pre-delta
snapshot (lineage/p58c23-parent-native: packet58-onecard-cache23's native tree after the path rewrite, before the diet
delta). Keeps the cache23 capacity delta checks (the engine must still carry max23 and the 29,828,911,360 bound), the
packet176 kernel-I/O checks, and requires the backend TU, the cache policy header and the record kernel header untouched.
CPU only; reads text."""
import hashlib, json, re, unittest
from pathlib import Path
P = Path(__file__).resolve().parent
OLD = P / 'lineage/p58c23-parent-native/native'
ARENA, MAX, BOUND = '23049601024ull', '21552729600ull', '29828911360ull'
DIET_HEADER_SHA = '35005ee3b3f3561902b727f9658ea0b08513e58a3a5651aff540fd1fabd66089'


def contains_diet_device_code(text):
    # This TU may explain the separate diet TU in comments, but must not include
    # its header or instantiate its kernel: both would alter the record images.
    code = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    return bool(re.search(r'^\s*#\s*include\s*[<"][^>"\n]*p58ag_diet', code, re.M)
                or re.search(r'\bp58ag_diet\s*::', code))


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
    sub = (root / 'generated/p58ag_submit.cpp').read_text(); hdr = (root / 'generated/p58ag_submit.hpp').read_text()
    # the diet key
    if 'std::string expert_gateup="production";' not in main: out.append('key default')
    if 'else if (k == "--expert-gateup") {a.expert_gateup=value();require(a.expert_gateup=="production"||a.expert_gateup=="diet","expert gate/up dimension");}' not in main: out.append('key parser')
    if 'require(a.expert_gateup=="production"||a.experts=="wide64+halfcache","expert_gateup=diet requires experts=wide64+halfcache");' not in main: out.append('diet needs halfcache')
    if 'void expert_gateup(const std::string& key) {' not in main or 'drain();cache_quiesce(); // the drained view boundary' not in main: out.append('drained boundary switch')
    if 'a.experts=="wide64+halfcache",expert_gateup_for(l)):p49d::expert(' not in main: out.append('dispatch key')
    if 'e->expert_gateup(view.gateup);e->bracket_select(' not in main: out.append('view loop switch before re-preparation')
    if 'require(view.gateup!="diet"||e->expert_diet_sites>0,"selected diet prepared no gate/up site");require(view.gateup!="production"||e->expert_diet_sites==0,"production view prepared a diet site");' not in main: out.append('site refusals')
    if '",\\"expert_gateup\\":"+ownrt::quote(view.gateup)+",\\"expert_diet_sites\\":"' not in main: out.append('boundary record')
    if '--expert-gateup production|diet (default:production)' not in main: out.append('help')
    if 'const std::string& gateup){' not in sub or 'return expert_diet(d,m,b,halfcache);' not in sub or contains_diet_device_code(sub): out.append('record TU dispatch (host only, no diet header)')
    if 'integrated::Launch expert_diet(' not in hdr: out.append('expert_diet declaration')
    if not (root / 'generated/p58ag_diet_submit.cpp').exists() or 'p58ag_diet::GateUp k;' not in (root / 'generated/p58ag_diet_submit.cpp').read_text(): out.append('diet TU')
    if not (root / 'generated/p58ag_diet.hpp').exists() or hashlib.sha256((root / 'generated/p58ag_diet.hpp').read_bytes()).hexdigest() != DIET_HEADER_SHA: out.append('pinned diet header')
    if 'std::string gateup="production";};' not in bt or 'require(v.gateup=="production"||v.gateup=="diet","expert gate/up dimension");' not in bt: out.append('bracket gate-up field')
    if 'views[i].capacity=="max23"&&views[i].gateup==(i%2?"diet":"production")&&views[i].hc=="spin-kio"' not in bt: out.append('bracket order max23 production/diet')
    if 'views[0].capacity=="max23"&&views[0].gateup=="diet"' not in bt: out.append('smoke diet')
    if 'engine->expert_gateup(view.gateup);engine->bracket_select(' not in probe or 'gateup-capture.json' not in probe: out.append('probe switch + capture record')
    # cache23 capacity delta still present
    if f'uint64_t cache_bytes={ARENA};std::string cache_cap="max";' not in main: out.append('default arena')
    if f'expert_cache->reset_capacity(cap=="18GB"?18000000000ull:cap=="max23"?{ARENA}:{MAX});' not in main: out.append('usable extents')
    if f'owned_bytes.at(c) + bytes <= {BOUND}' not in main or f'require(peak_bytes<={BOUND},' not in main: out.append('device bound 29,828,911,360')
    if main.count('21552729600') != 1: out.append('max usable literal must appear exactly once')
    if '--cache-cap 18GB|max|max23 (default:max)' not in main: out.append('capacity help')
    if 'peak<=30500000000ull' not in main: out.append('DRM guard 30.5 GB unchanged')
    if 'require(v.capacity=="max"||v.capacity=="max23","cache capacity dimension");' not in bt: out.append('bracket capacity dimension')
    if 'require(v.hc=="spin-kio","kernel foreground io fixed throughout the capacity bracket");' not in bt: out.append('bracket kernel io fixed')
    if 'transport->kernel_tail==60&&transport->kernel_head==60' not in probe or 'peak_device_bytes' not in probe: out.append('probe: 5 kernel-io views + census peak')
    if 'p176::kernel_io=a.bracket_inputs.empty()?a.foreground_io=="kernel":view.hc=="spin-kio";' not in main: out.append('kernel io view switch')
    if not re.search(r'if\(kernel_io\)e->tail_store\(\);', main): out.append('tail store placement')
    if 'require(!status,"sticky device error at token "' not in main: out.append('sticky error check')
    return out


def norm(text):
    return text.replace('packet58-onecard-diet-engine', 'X').replace('packet58-onecard-cache23', 'X')


class DietEngineDelta(unittest.TestCase):
    def test_record_tu_rejects_diet_code_but_allows_comments(self):
        self.assertFalse(contains_diet_device_code('// p58ag_diet::GateUp lives in its own TU\n'))
        self.assertFalse(contains_diet_device_code('/* #include "p58ag_diet.hpp" */\n'))
        self.assertTrue(contains_diet_device_code('#include "p58ag_diet.hpp"\n'))
        self.assertTrue(contains_diet_device_code('p58ag_diet::GateUp k;'))

    def test_candidate_source(self):
        self.assertEqual(problems(P / 'native'), [])

    def test_fails_on_parent_source(self):
        self.assertGreaterEqual(len(problems(OLD)), 14)

    def test_backend_policy_and_untouched_bodies(self):
        self.assertEqual(norm((P / 'native/generated/single_device.cpp').read_text()), norm((OLD / 'generated/single_device.cpp').read_text()))
        self.assertEqual((P / 'native/cache_table.hpp').read_text(), (OLD / 'cache_table.hpp').read_text())
        self.assertEqual((P / 'native/generated/p58ag_expert.hpp').read_text(), (OLD / 'generated/p58ag_expert.hpp').read_text())
        main = norm((P / 'native/generated/main.cpp').read_text()); parent = norm((OLD / 'generated/main.cpp').read_text())
        for head in ('void cache_boundary()', 'void cache_plan_during_position()', 'void publish_cache_table(const std::vector<p58::Entry>& table)',
                     'void upload(int c, Allocation dst, size_t offset, const void *src, size_t n)', 'void drain()', 'void prepare_token(int token)',
                     'void tail_store()', 'void head_end()', 'void cache_mode(const std::string& mode)', 'void cache_capacity(const std::string& cap)',
                     'void prepare_commands()', 'void admit_position(int position)', 'flash::Event issue_site(size_t index,flash::Event dep)'):
            self.assertEqual(body(main, head), body(parent, head), head)
        # the record TU: only the host dispatch (expert) changed; issue<> verbatim
        sub = norm((P / 'native/generated/p58ag_submit.cpp').read_text()); psub = norm((OLD / 'generated/p58ag_submit.cpp').read_text())
        self.assertEqual(body(sub, 'integrated::Launch issue('), body(psub, 'integrated::Launch issue('))
        self.assertNotEqual(body(sub, 'integrated::Launch expert('), body(psub, 'integrated::Launch expert('))

    def test_diet_tu_is_the_production_issue_body(self):
        diet = norm((P / 'native/generated/p58ag_diet_submit.cpp').read_text()); psub = norm((OLD / 'generated/p58ag_submit.cpp').read_text())
        a = body(diet, 'integrated::Launch issue_diet('); b = body(psub, 'integrated::Launch issue(')
        a = a.replace('issue_diet(', 'issue(').replace(' p58ag_diet::GateUp k;', ' p58ag_exp::Kernel<T,K,64,false,true,0,Cached> k;')
        a = re.sub(r'\n static_assert\(T==Type::IQ2_S[^\n]*\n', '\n', a)
        self.assertEqual(a, b)

    def test_delta_scope(self):
        touched = sorted({l[6:].strip() for l in (P / 'native-dietengine-delta.patch').read_text().splitlines() if l.startswith('+++ b/')})
        self.assertEqual(touched, ['native/bracket_table.hpp', 'native/generated/main.cpp', 'native/generated/p58ag_diet.hpp', 'native/generated/p58ag_diet_submit.cpp',
                                   'native/generated/p58ag_submit.cpp', 'native/generated/p58ag_submit.hpp', 'native/p58ag_diet.hpp', 'native/p58ag_diet_submit.cpp',
                                   'native/p58ag_submit.cpp', 'native/p58ag_submit.hpp', 'native/preparation_probe.cpp'])
        copy = json.loads((P / 'lineage/packet58de-copy.json').read_text())
        self.assertEqual(copy['parent']['name'], 'packet58-onecard-cache23')
        self.assertGreater(copy['path_rewrite']['occurrences'], 300)


if __name__ == '__main__':
    unittest.main()
