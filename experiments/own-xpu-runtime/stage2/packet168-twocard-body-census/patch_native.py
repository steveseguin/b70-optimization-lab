"""Apply the private, explicitly unqualified snapshot/skip prototype once."""
from build_engine import P,save,sha
import difflib
BASE=P/'native-source/repo/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/build/checked/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks'
def change(name,edits):
    path=BASE/name
    parent=P.parent/'packet165-warm-prefill/two-card'
    original=(parent/path.relative_to(P)).read_text().replace(str(parent),str(P));text=original
    for old,new in edits:
        assert text.count(old)==1,(name,old,text.count(old));text=text.replace(old,new)
    path.write_text(text)
    (P/'lineage'/f'{name}.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),text.splitlines(True),fromfile='a/'+name,tofile='b/'+name)))
def main():
    change('main.cpp',[
      ('struct Options {','struct Options {\n  bool census_probe=false;'),
      ('Options: --argument-audit','Options: --census-probe --argument-audit'),
      ('else if (k == "--draft-capture")','else if (k == "--census-probe") a.census_probe=true;\n    else if (k == "--draft-capture")')])
    change('strict_snapshot.hpp',[
      ('explicit SpeculativeImage(Engine& owner):e(owner) {\n  if(e.a.rank!=0)return;',
       'explicit SpeculativeImage(Engine& owner,bool diagnostic=false):e(owner) {\n  if(e.a.rank!=0&&!diagnostic)return;'),
      ('require(e.a.rank==0&&backup&&!valid&&!redo_pending,"snapshot begin ownership")',
       'require((e.a.rank==0||e.a.census_probe)&&backup&&!valid&&!redo_pending,"snapshot begin ownership")')])
    change('rank.hpp',[
      ('static int run_rank(const Options& a) {', '#include "'+str(P/'native_probe.hpp')+'"\nstatic int run_rank(const Options& a) {'),
      ('SpeculativeImage image(*engine);','SpeculativeImage image(*engine,a.census_probe);'),
      ('else if(r.op==11){image.boundary();','else if(r.op==20){require(!c.pending&&!async_half_ready,"packet168 probe boundary");p168::probe(*engine,image,r,static_cast<uint8_t*>(mapping));}\n   else if(r.op==11){image.boundary();')])
    save(P/'evidence/native-delta.json',dict(passed=True,device_executed=False,status='prototype only; no device readiness',
      changed_source_sha256={str((BASE/n).relative_to(P)):sha(BASE/n) for n in ('main.cpp','strict_snapshot.hpp','rank.hpp')},
      limitations=['not the native overlapped emission schedule','cross-card transfer arm refuses','head suffix and fused class coverage pending']))
if __name__=='__main__':main()
