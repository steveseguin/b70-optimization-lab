"""Expose the candidate's actual pre-BF16 expression, without replacing its math."""
from pathlib import Path
P=Path(__file__).resolve().parent
def generate():
 s=(P/'specialised_layers.hpp').read_text();start=s.index('inline void qsa_host(');end=s.index('\n#ifdef OWN_RT_HOST_ONLY',start)
 body=s[start:end].replace('qsa_host(ng::Args a)','qsa_trace(ng::Args a,float* pre_gate)').replace('/den,nullptr);','/den,pre_gate);')
 assert 'pre_gate);' in body and 'nullptr' not in body
 (P/'build/qsa_trace.hpp').write_text('#pragma once\n#include "specialised_layers.hpp"\nnamespace p107 {\n'+body+'\n}\n')
if __name__=='__main__':generate()
