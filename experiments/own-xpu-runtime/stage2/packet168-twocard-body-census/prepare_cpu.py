"""Build actual private device entry on the existing CPU marker transport."""
from pathlib import Path
import resource
from build_engine import P,STAGE,save,sha
def main():
    dependencies=('native_fixture.cpp','native_probe.hpp','native_arm_order.hpp','census_contract.py')
    initial={n:sha(P/n) for n in dependencies}
    save(P/'evidence/cpu-builder-status.json',dict(passed=False,status='building'))
    source=STAGE/'packet163-full-gate/prepare_probe.py'
    text=source.read_text()
    old="p=P/name;B=p/'build/preparation163'"
    assert text.count(old)==1;text=text.replace(old,"p=P;B=p/'build/preparation163'")
    old=" (B/'fixture.cpp').write_text(fixture)"
    assert text.count(old)==1;text=text.replace(old," fixture=(P/'native_fixture.cpp').read_text()\n"+old)
    old="  (B/'preparation_backend.hpp').write_text(backend)"
    assert text.count(old)==1
    text=text.replace(old,"  backend=backend.replace('public:\\n bool ordered_prefix_complete', 'public:\\n ownrt::Event compute(const ownrt::Operation&,std::span<void*const>,std::span<const ownrt::Event>) override;\\n bool ordered_prefix_complete')\n"+old)
    scope={'__name__':'packet168_cpu_builder','__file__':str(source)}
    exec(compile(text,str(source),'exec'),scope)
    scope['main']('two-card')
    assert initial=={n:sha(P/n) for n in dependencies},'CPU source changed during build; rebuild required'
    save(P/'evidence/cpu-builder-status.json',dict(passed=True,fixture_sha256=sha(P/'native_fixture.cpp'),binary_sha256=sha(P/'build/preparation163/prepare-probe'),
      inputs_sha256={n:sha(P/n) for n in ('native_probe.hpp','native_arm_order.hpp','census_contract.py')}))
    origin(source)
def origin(source=STAGE/'packet163-full-gate/prepare_probe.py'):
    rel=str(source.resolve().relative_to(P.parents[3]))
    save(P/'evidence/cpu-builder-origin.json',dict(parent_records=[dict(name=source.name,parent_relpath=rel,parent_digest=sha(source))],
      edits=['private packet root','native_fixture.cpp replaces fixture only'],device_executed=False))
if __name__=='__main__':
    import sys
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2)
    origin() if sys.argv[1:]==['--origin-only'] else main()
