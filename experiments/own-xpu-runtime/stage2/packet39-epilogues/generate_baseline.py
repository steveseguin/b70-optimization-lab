#!/usr/bin/env python3
"""Extract unchanged packet29 runtime bodies for a matched unfused timing control."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;R=P.parent/'packet29-merged'
def section(text,start,end):
 a=text.index(start);return text[a:text.index(end,a)]
def main():
 src=(R/'adapter.cpp').read_text();native=(R/'native.cpp').read_text()
 parts=[section(src,'struct Bound {','template<class Team> void simple('),section(src,'template<class Team> void simple(', '#ifdef OWN_RT_HOST_ONLY\ntemplate<Op Code'),section(src,'struct Team {','struct Glue final:ownrt::SyclOperation')]
 # Included functions and their operation switches retain original runtime scope.
 out='#pragma once\n#include "../packet29-merged/runtime_kernels.hpp"\n#include "../packet29-merged/kernels.hpp"\nnamespace p39_runtime { using namespace integrated;\n'+''.join(parts)+'\n}\nnamespace p39_ng { using namespace ng;\n'+section(native,'struct DeviceTeam {','struct Kernel final:')+'\n}\n'
 target=P/'runtime_bodies.hpp';target.write_text(out)
 (P/'runtime-baseline-source.json').write_text(json.dumps(dict(device_executed=False,source_sha256={str(f.relative_to(P.parent)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [R/'adapter.cpp',R/'native.cpp',R/'kernels.hpp']},generated_sha256=hashlib.sha256(out.encode()).hexdigest(),edits=['extract entire Bound, simple, subtree, simple_body, Team, DeviceTeam unchanged','namespace/include scaffolding only; original dynamic operation switches retained']),indent=2)+'\n')
if __name__=='__main__':main()
