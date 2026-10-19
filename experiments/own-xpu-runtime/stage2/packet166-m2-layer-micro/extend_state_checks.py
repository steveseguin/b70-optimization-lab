"""Add optional validation-only first-row state stores to private native copies."""
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'native/experiments/own-xpu-runtime/stage2/packet136-record-bundle'
p=B/'p82b_recurrence.hpp';s=p.read_text();s=s.replace('for(unsigned x=0;x<128;++x)a.put(7,state+x,v[x]);','for(unsigned x=0;x<128;++x){a.put(7,state+x,v[x]);if(r==0&&a.p[8])a.put(8,state+x,v[x]);}')
s=s.replace('raw.store(0,static_cast<uint16_t*>(a.p[7])+state+lane*4);','raw.store(0,static_cast<uint16_t*>(a.p[7])+state+lane*4);\n  if(r==0&&a.p[8])raw.store(0,static_cast<uint16_t*>(a.p[8])+state+lane*4);')
p.write_text(s)
p=B/'kernels.hpp';s=p.read_text();old='history[hist-1]=x;}'
assert old in s;s=s.replace(old,'history[hist-1]=x;if(r==0&&a.p[8])for(int j=0;j<hist;++j)a.put(8,ch*hist+j,history[j]);}')
p.write_text(s)
