"""Exact lookup implementation from hash-bound packet58aj native sources."""
import re
from prepare import P, sha

def port(t):
    import json
    for row in json.loads((P/'lineage/resident-port.json').read_text())['files']:
        assert sha(P/row['destination']) == row['source_sha256']
    parent=(P/'lineage/resident-main.cpp').read_text()
    t='#include '+json.dumps(str(P/'native/resident_lookup.hpp'))+'\n'+t
    t=t.replace('  int wait_seconds=300;', '  bool resident_lookups=false;\n  int wait_seconds=300;')
    parser=next(line for line in parent.splitlines() if 'k == "--lookups"' in line)
    t=t.replace('    else if(k=="--cpu-preparation-probe")',parser+'\n    else if(k=="--cpu-preparation-probe")')
    start=t.index('  void warm_lookups() {');end=t.index('  Weights(const Options',start)
    t=t[:start]+'#include '+json.dumps(str(P/'native/resident_weights.hpp'))+'\n'+t[end:]
    start=t.index('  std::vector<uint8_t> read(const std::string &name');end=t.index('  std::vector<int64_t> metadata()',start)
    a=parent.index('  std::vector<uint8_t> read(const std::string &name');b=parent.index('  std::vector<int64_t> metadata()',a)
    t=t[:start]+parent[a:b]+t[end:]
    t=t.replace('e->initialize();e->cache_capacity(a.cache_cap);','e->initialize();\n    if(a.resident_lookups)w->load_resident_lookups();\n    w->use_resident_lookups=a.resident_lookups;e->cache_capacity(a.cache_cap);')
    t=t.replace('    for(const auto& view:bracket_views) {','    for(const auto& view:bracket_views) {\n    w->use_resident_lookups=a.resident_lookups;')
    t=t.replace('      save(view_output/"boundary.json",','      save(view_output/"lookup-backing.json","{\\"resident\\":"+std::string(a.resident_lookups?"true":"false")+",\\"copies\\":"+w->residency+"}\\n");\n      save(view_output/"boundary.json",')
    t=t.replace('<<",\\"prepare_ms\\":"', '<<",\\"resident_lookups\\":"<<(w->use_resident_lookups?"true":"false")<<",\\"prepare_ms\\":"')
    t=t.replace('    if(!request_id.empty())save(output/"receipt.json",rr.str());', '    if(!request_id.empty())save(output/"receipt.json",rr.str());\n    e->timings.flush();e->prefill_timings.flush();\n    save(output/"lookup-request-complete.json","{\\"passed\\":true}\\n");')
    # The legacy outer wrapper forwards unknown flags to this entry. Help is
    # derived from the real parser, before any environment/model/device access.
    flags=sorted(set(re.findall(r'k\s*==\s*"(--[a-z0-9-]+)"',t)))
    text='packet58an demand transfer; --lookups mapped|resident; --wait-seconds 300..3600\n'+' '.join(flags)+'\n'
    t=t.replace('int main(int argc, char **argv) {','int main(int argc, char **argv) {\n  if(argc==2&&std::string(argv[1])=="--help"){std::cout<<'+json.dumps(text)+';return 0;}')
    return t
