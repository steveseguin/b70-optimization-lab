"""Verify the frozen source copy, arithmetic object identity and limited overlay."""
import difflib
import json
from pathlib import Path
from build_engine import P, ROOT, BASE, B, sha, save, limits
from native_source import CHECKED

def main():
    limits()
    provenance=json.loads((P/'source-copy-provenance.json').read_text())
    unchanged=[];deltas=[];patch=[]
    prefix=BASE/'build/checked'
    for name,digest in provenance['packet97'].items():
        original=ROOT/name
        assert sha(original)==digest, name
        local=P/'sources'/original.relative_to(prefix)
        expected=original.read_text().replace(str(prefix),str(P/'sources'))
        actual=local.read_text()
        if actual==expected:unchanged.append(str(local.relative_to(ROOT)))
        else:
            assert local==CHECKED/'argument_block.hpp','unexpected arithmetic source delta: '+name
            deltas.append(str(local.relative_to(ROOT)))
            patch.extend(difflib.unified_diff(expected.splitlines(True),actual.splitlines(True),
                         fromfile='packet97/argument_block.hpp',tofile='packet98c/argument_block.hpp'))
    assert len(deltas)==1
    for name in ('main.cpp','rank.hpp','mtp.hpp'):
        patch.extend(difflib.unified_diff((CHECKED/name).read_text().splitlines(True),
             (B/'native'/name).read_text().splitlines(True),fromfile='copied/'+name,tofile='native/'+name))
    (P/'native-overlay.patch').write_text(''.join(patch))
    build=json.loads((P/'evidence/build.json').read_text())
    for name,digest in build['sources'].items():
        assert '/ops/' not in name, 'mutable orchestration dependency'
        assert not name.endswith('/packet97-record-bundle/selection.json')
        assert sha(ROOT/name)==digest,name
    prior=json.loads((BASE/'engine-commands.json').read_text())
    objects=[]
    for mode in ('gnu-host','device'):
        original=next(r['command'] for r in prior if r['name']==mode+'-link')
        new=next(r['command'] for r in build['commands'] if r['name']==mode+'-link')
        unchanged_objects=[x for x in original if x.endswith('.o') and not x.endswith('/entry-main.o')]
        assert unchanged_objects==[x for x in new if x.endswith('.o') and not x.endswith('/entry-main.o')]
        objects.extend(dict(mode=mode,path=str(Path(x).relative_to(ROOT)),sha256=sha(x)) for x in unchanged_objects)
    save(P/'evidence/native-source-audit.json',dict(passed=True,device_executed=False,
         unchanged_after_include_relocation=len(unchanged),cpu_audit_only_deltas=deltas,
         unchanged_linked_objects=objects,parent_orchestration_dependencies=[],
         overlay_sha256=sha(P/'native-overlay.patch'),
         sources={str((P/'audit_sources.py').relative_to(ROOT)):sha(P/'audit_sources.py')}))
    print('192 copied sources verified; only CPU argument audit differs; all arithmetic objects retained')

if __name__=='__main__':main()
