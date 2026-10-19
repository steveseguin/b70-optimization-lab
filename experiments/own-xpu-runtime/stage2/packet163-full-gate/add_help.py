"""Expose parser-supported options before any model/device access."""
import json,re,resource,subprocess,sys
from pathlib import Path
from build_engine import P,turn,sha,save
name=sys.argv[1];p=P/name
r=json.loads((p/'lineage/build-inputs.json').read_text())
entry=Path(r['compile'][r['compile'].index('-c')+1]);main=Path(re.search(r'#include "([^"]+)"',entry.read_text())[1])
if not main.is_absolute():main=entry.parent/main
text=main.read_text()
flags=sorted(set(re.findall(r'k\s*==\s*"(--[a-z0-9-]+)"',text)))
assert '--max-new'in flags and '--authorized-device-window'in flags
pattern=r'(Options parse\(int argc,\s*char\s*\*\*\s*argv\)\s*\{)'
assert len(re.findall(pattern,text))==1
help='\n  // PACKET163_HELP_BEGIN: metadata only; before device or model access.\n  if(argc==2 && std::string(argv[1])=="--help") { std::cout << '+json.dumps('Options: '+' '.join(flags)+'\nResponse cap:1..512; full16-bit KV; unchanged engine arithmetic.\n')+';std::exit(0); }\n  // PACKET163_HELP_END\n'
assert 'PACKET163_HELP_BEGIN'not in text
main.write_text(re.sub(pattern,lambda m:m[1]+help,text,count=1))
(p/'native-help-flags.json').write_text(json.dumps(flags,indent=2)+'\n')
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2)
for label,cmd in [('compile',r['compile']),('link',r['link'])]:
 with turn(),(p/'build'/('help-'+label+'.log')).open('w')as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True)
 print(name,'help',label,'PASS',flush=True)
r= json.loads((p/'evidence/build.json').read_text());r.update(binary_sha256=sha(p/'build/device/own-rt-iq3'),help_before_device_access=True,source_main_sha256=sha(main));save(p/'evidence/build.json',r)
i=json.loads((p/'identity.json').read_text());i.update(binary_sha256=r['binary_sha256'],measurement_delta='response-cap parser128->512, one-card suite admission12->13, and pre-device --help only');save(p/'identity.json',i)
