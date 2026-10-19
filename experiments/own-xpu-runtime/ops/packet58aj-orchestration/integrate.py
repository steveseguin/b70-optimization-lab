"""Apply the exact packed-lookup copy to the private 58ah/58ag composition."""
import json,sys
from pathlib import Path
R=Path(__file__).resolve().parents[4];P=R/'experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident';Q=P/'screen'
def edit(path,old,new):
    text=path.read_text();assert old in text,(path,old);path.write_text(text.replace(old,new))
def main():
    # Keep packet58t's copy implementation verbatim; the integration has one
    # added explicit option and the existing five-view protocol.
    (P/'native_source.py').write_text('from pathlib import Path\nP=Path(__file__).resolve().parent\nROOT=P.parents[3]\nBASE=P/"frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port"\ndef once(text,old,new):\n    assert text.count(old)==1,(old,text.count(old))\n    return text.replace(old,new)\n')
    sys.path.insert(0,str(P));import resident_source
    f=P/'build/native/main.cpp';text=resident_source.integrate(f.read_text())
    text=text.replace('else if (k == "--resident-lookups") a.resident_lookups=true;', 'else if (k == "--lookups") {auto v=value();require(v=="mapped"||v=="resident","lookup dimension");a.resident_lookups=v=="resident";}')
    text=text.replace('e->bracket_select(view.selection,view.digest,view.hc);','e->bracket_select(view.selection,view.digest,"p60fusion","hc-wide","wide64+halfcache","fused","ordered-foreground");')
    # --lookups governs single-view chain loads; bracket copies always exist.
    text=text.replace('w->use_resident_lookups=view.resident;', 'w->use_resident_lookups=view.resident;')
    text=text.replace('\",\\\"hc\\\":"+ownrt::quote(view.hc)+', '\",\\\"hc\\\":\\\"p60fusion\\\",\\\"lookups\\\":"+ownrt::quote(view.resident?"resident":"mapped")+')
    f.write_text(text)
    f=P/'native/bracket_table.hpp';text=f.read_text().replace('capacity,hc;','capacity,hc;bool resident=false;')
    text=text.replace('a.cache_cap,a.hc}}','a.cache_cap,a.hc,a.resident_lookups}}')
    text=text.replace('require(v.hc=="production"||v.hc=="p60fusion","HC dimension");','require(v.hc=="mapped"||v.hc=="resident","lookup dimension");v.resident=v.hc=="resident";')
    text=text.replace('views[0].hc=="p60fusion"','views[0].hc=="resident"').replace('(i%2?"p60fusion":"production")','(i%2?"resident":"mapped")')
    f.write_text(text)
    # Lifetime allocation view must include copies even in mapped bracket arms.
    for f in (P/'memory_plan.py',Q/'memory_plan.py'):
        edit(f,"view='tile16'","view='tile16-resident'")
    edit(P/'composition.py',"FLAGS = {'--hc':'p60fusion'", "FLAGS = {'--lookups':'resident', '--hc':'p60fusion'")
    selection=json.loads((P/'runtime-selection.json').read_text());selection['lookups']='resident';(P/'runtime-selection.json').write_text(json.dumps(selection,indent=2)+'\n')
    # Private screen keeps full composition fixed while the lookup path switches.
    for n in ('views.py','queue_runner.py','suite_driver.py','window.py','argument_gate.py','test_bracket.py','test_launch_unit.py'):
        f=Q/n;text=f.read_text().replace("'p60fusion'","'resident'").replace("'production'","'mapped'")
        # Dispatch identity is unchanged; only the runtime view names change.
        text=text.replace("hc='mapped'","hc='production'")
        text=text.replace("boundary.get('hc')==view", "boundary.get('hc')=='p60fusion' and boundary.get('lookups')==view")
        text=text.replace('card0-ports-a','card0-58aj-screen-a')
        f.write_text(text)
    # Ensure fixed runtime flags are explicitly present even before view switch.
    edit(Q/'suite_driver.py',"'--seconds','7200','--bracket-inputs'", "'--lookups','resident','--hc','p60fusion','--hc-geometry','hc-wide','--experts','wide64+halfcache','--other-fusion','fused','--retirement','ordered-foreground','--seconds','7200','--bracket-inputs'")
    # The nested harness owns its files but shares only our own native artifacts.
    for n in ('admission.json','legacy_memory_plan.py','oracle-binding.json','dispatch-speed6.json','k1-cpu.json','library-path.json'):
        f=Q/n
        if f.exists():f.unlink()
        f.symlink_to('../'+n)
    for n in ('postload-census.json','58c-kd','fullshape-submit-cpu.json','postload-allocation-cpu.json','startup-cpu.json'):
        (Q/'evidence'/n).symlink_to('../../evidence/'+n)
    # Build validation checks are owned by the new seal, without sibling maps.
    (Q/'input_scope.py').write_text('from pathlib import Path\nP=Path(__file__).resolve().parents[1]\nROOT=P.parents[3]\ndef check_pins(root,pins):\n    assert isinstance(pins,dict) and pins\n    oracle=__import__("json").loads((P/"oracle-binding.json").read_text())["files_sha256"]\n    for n,h in pins.items():\n        p=(root/n).resolve()\n        assert p.is_relative_to(P) or oracle.get(str(p.relative_to(ROOT)))==h,(n,"external mutable pin")\n')
    # No subprocess wall timeouts: freezing preparation cannot kill a compiler
    # or turn a CPU check into an intermittent failure.
    import re
    for folder in (P,Q):
        for f in folder.glob('*.py'):
            if f.is_symlink():continue
            text=f.read_text();text=re.sub(r',\s*timeout\s*=\s*\d+(?:\.\d+)?', '',text)
            f.write_text(text)
    print('Integrated resident copies, explicit lookup switch, fixed composition and resident admission')
if __name__=='__main__':main()
