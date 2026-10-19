"""Packet174 source-delta test. Passes on this packet's native sources and
fails on the parent packet58as sources (lineage/p174-parent-native, copied from
the git-archive tree before the delta). CPU only; reads text."""
import re,unittest
from pathlib import Path
P=Path(__file__).resolve().parent
OLD=P/'lineage/p174-parent-native/native'

def body(text,head):
    i=text.index(head);depth=0
    for j in range(text.index('{',i),len(text)):
        depth+=text[j]=='{';depth-=text[j]=='}'
        if depth==0:return text[i:j+1]
    raise AssertionError(head)

def problems(root):
    out=[]
    main=(root/'generated/main.cpp').read_text();sd=(root/'generated/single_device.cpp').read_text();bt=(root/'bracket_table.hpp').read_text()
    if 'std::string fill_kick="off"; bool fill_kick_supplied=false;' not in main:out.append('default off option')
    if 'if (k == "--fill-kick")' not in main or '--fill-kick off|on (default:off)' not in main:out.append('cli/help')
    if 'p174::fill_kick=a.bracket_inputs.empty()?a.fill_kick=="on":view.hc=="spin-kick";' not in main:out.append('view switch')
    # The kick is issued once, after the ticket is owned, only for a non-empty batch.
    m=re.search(r'maintenance\.submitted\(true,last\);\n\s*if\(p174::fill_kick&&!maintenance\.plan->fills\.empty\(\)\)kick_fills\(\);',main)
    if not m:out.append('kick placement')
    if main.count('kick_fills();')!=2:out.append('kick call count')
    try:
        k=body(sd,'void kick_fills() override')
        code='\n'.join(l.split('//')[0] for l in k.splitlines())
        if 'zeCommandListHostSynchronize(maintenance_native_,0)' not in code or any(w in code for w in ('.wait(','wait_and_throw','finish_fills','sleep_for','synchronize()')):out.append('non-blocking kick')
    except ValueError:out.append('device kick missing')
    if 'public p174::FillKick' not in sd:out.append('device interface')
    if 'v.hc=="spin"||v.hc=="spin-kick"' not in bt or 'views[i].hc==(i%2?"spin-kick":"spin")' not in bt:out.append('bracket arms')
    if '"bracket selects the fill kick per view"' not in bt:out.append('bracket refusal')
    if 'route_hits_total' not in main or 'fill_kicks_total' not in main:out.append('readout fields')
    return out

class FillKickDelta(unittest.TestCase):
    def test_candidate_source(self):
        self.assertEqual(problems(P/'native'),[])
    def test_fails_on_parent_source(self):
        self.assertGreaterEqual(len(problems(OLD)),8)
    def test_fill_path_unchanged(self):
        for name in ('generated/single_device.cpp',):
            new=(P/'native'/name).read_text().replace('packet174-onecard-fillkick','X');old=(OLD/name).read_text().replace('packet58as-onecard-spinwait','X')
            for head in ('Event fill(void* dst,const void* src,size_t bytes) override','bool fill_complete(Event ticket) override','void finish_fills() override','Event copy(void* dst,const void* src,std::size_t n,std::span<const Event> deps) override'):
                self.assertEqual(body(new,head),body(old,head),head)
    def test_cache_policy_unchanged(self):
        main=(P/'native/generated/main.cpp').read_text().replace('packet174-onecard-fillkick','X');old=(OLD/'generated/main.cpp').read_text().replace('packet58as-onecard-spinwait','X')
        for head in ('void cache_plan_during_position()','void cache_capacity(const std::string& cap)','void publish_cache_table(const std::vector<p58::Entry>& table)'):
            self.assertEqual(body(main,head),body(old,head),head)
        touched=sorted({l[6:].strip() for l in (P/'native-delta.patch').read_text().splitlines() if l.startswith('+++ b/')})
        self.assertEqual(touched,['native/bracket_table.hpp','native/fill_kick.hpp','native/generated/main.cpp','native/generated/single_device.cpp'])
if __name__=='__main__':unittest.main()
