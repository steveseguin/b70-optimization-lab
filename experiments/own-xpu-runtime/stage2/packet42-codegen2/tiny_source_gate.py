"""Mechanical arithmetic-copy identity proof against the read-only incumbent."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
source=P.parent/'packet29-merged/kernels.hpp';s=source.read_text();a=s.index('template<class Team> void group(');b=s.index('\ninline void cpu(',a);body=s[a:b]
expected=body.replace('template<class Team> void group(', 'template<ng::Op Code,class Team> inline void cooperative_group(').replace('s.op','Code').replace('if(Code==','if constexpr(Code==').replace('Code==select','Code==ng::select')
actual=(P/'tiny_cooperative_core.hpp').read_text();prefix='#pragma once\n#include "../packet29-merged/kernels.hpp"\n// Exact ng::group statement body; only op dispatch becomes a template constant.\nnamespace p42tiny {using namespace ng;\n'
assert actual==prefix+expected+'\n}\n','arithmetic-copy differs beyond allowed dispatch substitution'
r=json.loads((P/'tiny-cooperative-origin.json').read_text());assert hashlib.sha256(source.read_bytes()).hexdigest()==r['source_sha256'];assert hashlib.sha256(body.encode()).hexdigest()==r['original_body_sha256']
print('Exact cooperative arithmetic statement copy: PASS')
