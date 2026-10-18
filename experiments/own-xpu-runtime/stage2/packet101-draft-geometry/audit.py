"""Recomputable selection/source audit of packet69 against frozen packet97."""
import difflib,json
from build_engine import P,ROOT,BASE,sha,save,limits
def main():
    limits();old=P.parent/'packet69-rank1-head/candidates'
    read=lambda p:json.loads(p.read_text())
    control=read(old/'selections/production/selection.json');hc=read(old/'selections/draft-hc/selection.json')
    combined=read(old/'selections/combined/selection.json');current=read(BASE/'selection-template.json')
    delta={k:v for k,v in hc['draft'].items() if v!=control['draft'][k]}
    assert len(delta)==14 and all(current['draft'][k]==v for k,v in delta.items())
    assert current['draft']['qsa_attention']=='production'
    assert combined['choices']['target_head']==combined['choices']['draft_head']=='wide64'
    same={}
    for leaf in ('p59_hc.hpp','p59_draft.hpp','p49_qsa_submit.cpp','p49_qsa_reference.hpp','p49_qsa_kernel.hpp','dispatch.hpp'):
        same[leaf]=sha(old/leaf)==sha(BASE/leaf);assert same[leaf],leaf
    leaves=('mtp.hpp','p59c_select.hpp','p59_hc.hpp','p59_draft.hpp','p49_qsa_submit.cpp','p49_qsa_reference.hpp','p49_qsa_kernel.hpp','dispatch.hpp','adapter.cpp','arithmetic.hpp')
    sources={str(f.relative_to(ROOT)):sha(f) for root in (old,BASE) for leaf in leaves for f in [root/leaf]}
    for f in [old/'selections'/v/'selection.json' for v in ('production','combined','draft-attention','draft-hc')]+[BASE/'selection-template.json',BASE/'selection.json',BASE/'bundle_selection.py',BASE/'dispatch-speed6.json',old/'p69_head.hpp',old/'p69_head.cpp',old/'selections.py',P/'audit.py']:
        sources[str(f.relative_to(ROOT))]=sha(f)
    diff=''
    for leaf in ('mtp.hpp','p59_hc.hpp','p59_draft.hpp','p49_qsa_submit.cpp'):
        diff+=''.join(difflib.unified_diff((old/leaf).read_text().splitlines(True),(BASE/leaf).read_text().splitlines(True),fromfile='packet69/'+leaf,tofile='packet97/'+leaf))
    (P/'evidence/packet69-to-packet97.patch').write_text(diff)
    save(P/'evidence/source-audit.json',dict(passed=True,device_executed=False,
         draft_hc='already active, identical kernels; alias only',hc_keys_already_enabled=delta,
         draft_attention='compiled selectable split32 path present but not enabled in baseline',
         production_implementation=5,candidate_implementation=12,identical_sources=same,
         combined_included_target_and_draft_wide64=True,expanded_q6_row_stride=3380,
         head_policy='retain packet97 production/head-transpose dimensions and unchanged draft prefix; do not import wide heads',
         sources=sources))
    print('HC: all 14 settings already active. Attention: implementation 5 -> 12; distinct existing path.')
if __name__=='__main__':main()
