"""Read-only native/source audit; no device output is inherited."""
from source_decision import O,P,ROOT,sha,save
import sys
sys.path.insert(0,str(P))
def main():
 from reuse_build import native_sources,OLD
 row=dict(passed=True,device_executed=False,source=str(OLD.relative_to(ROOT)),sources=native_sources(),binaries={m:sha(P/'build'/m/'own-rt-iq3') for m in ('gnu-host','device')})
 save(O/'source-audit.json',row)
if __name__=='__main__':main()
