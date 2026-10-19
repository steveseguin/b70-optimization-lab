"""Build actual private device entry on the existing CPU marker transport."""
from pathlib import Path
import resource
from build_engine import P,STAGE,save,sha
def main():
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
    save(P/'evidence/cpu-builder-status.json',dict(passed=True,fixture_sha256=sha(P/'native_fixture.cpp'),binary_sha256=sha(P/'build/preparation163/prepare-probe')))
    save(P/'evidence/cpu-builder-origin.json',dict(source_sha256={str(source):sha(source)},
      edits=['private packet root','native_fixture.cpp replaces fixture only'],device_executed=False))
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);main()
