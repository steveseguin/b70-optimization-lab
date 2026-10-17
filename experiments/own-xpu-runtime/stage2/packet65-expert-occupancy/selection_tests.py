#!/usr/bin/env python3
"""Exercise the actual engine parser: no alternate permissive Python parser."""
import copy,json,subprocess
from build_engine import P,B,ROOT,sha,save,limits

def main():
 limits();source=B/"selection-fixture.cpp"
 source.write_text("#include \"p49d_submit.hpp\"\n#include <iostream>\nint main(int argc,char**argv){try{if(argc!=3||!*argv[2])return 2;p49d::Selection s;s.load(argv[1],argv[2]);return 0;}catch(const std::exception&e){std::cerr<<e.what();return 1;}}\n")
 commands=json.loads((P/"engine-commands.json").read_text())
 cc=next(r["command"] for r in commands if r["name"]=="gnu-host-entry-main");cc=cc[:cc.index("-o")]+["-o",str(B/"selection-fixture.o"),"-c",str(source)]
 link=list(next(r["command"] for r in commands if r["name"]=="gnu-host-link"))
 link=[x for x in link if not x.endswith("own-rt-iq3-entry.cpp.o")]
 link=[str(B/"selection-fixture.o") if x==str(B/"gnu-host/entry-main.o") else x for x in link];link[link.index("-o")+1]=str(B/"selection-fixture")
 for cmd in (cc,link):subprocess.run(cmd,check=True,stdin=subprocess.DEVNULL,capture_output=True)
 links=subprocess.check_output(["readelf","-d",str(B/"selection-fixture")],text=True).lower();assert not any(s in links for s in ("libsycl","libze_loader","libur_loader","libopencl"))
 rows=[];cases=[]
 for name in ("production","wg64","wg128","prefetch64","wide64"):
  cases.append((name,(P/"selections"/name/"selection.json").read_text(),None,True))
 good=json.loads(cases[0][1])
 for name,change in [("bad-experts",lambda x:x["choices"].update(experts="free-order")),("bad-target",lambda x:x["choices"].update(route="production")),("missing-experts",lambda x:x["choices"].pop("experts")),("extra",lambda x:x["choices"].update(kv="fp8")),("missing-draft",lambda x:x["draft"].pop("gate_up"))]:
  bad=copy.deepcopy(good);change(bad);cases.append((name,json.dumps(bad),None,False))
 raw=json.dumps(good);cases.extend([("duplicate",raw.replace("\"experts\": \"production\"","\"experts\": \"production\", \"experts\": \"wide64\""),None,False),("trailing",raw+"x",None,False),("bad-hash",raw,"0"*64,False),("missing-hash",raw,"",False)])
 path=B/"selection-test.json"
 for name,text,digest,valid in cases:
  path.write_text(text);r=subprocess.run([str(B/"selection-fixture"),str(path),sha(path) if digest is None else digest],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=10)
  assert (r.returncode==0)==valid,(name,r.stderr);rows.append(dict(name=name,accepted=valid))
 save(P/"evidence/selection-tests.json",dict(passed=True,device_executed=False,cases=rows,compile=cc,link=link,binary_sha256=sha(B/"selection-fixture"),source_sha256=sha(source),driver_sha256=sha(P/"selection_tests.py")))
 print(len(rows),"parser cases PASS")
if __name__=="__main__":main()
