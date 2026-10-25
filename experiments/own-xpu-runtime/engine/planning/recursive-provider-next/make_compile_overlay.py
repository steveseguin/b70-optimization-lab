#!/usr/bin/env python3
"""Create one fresh temporary include overlay; never edit canonical source."""
import argparse, hashlib, json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
here=Path(__file__).resolve().parent;engine=here.parent.parent
relative=Path('gsq-rco-iq3s/integration/build/private/source/diet-native/native-src/mtp.hpp')
source=engine/'src'/relative;fragment=here/'draft_runtime_extension.inc'
a.output.mkdir(parents=True,exist_ok=False)
text=source.read_text();assert text.count('\npublic:\n')==1
text=text.replace('namespace mtp36 {','#include "'+str(here/'batch.hpp')+'"\nnamespace mtp36 {',1)
text=text.replace('\npublic:\n','\npublic:\n'+fragment.read_text()+'\n',1)
target=a.output/relative;target.parent.mkdir(parents=True);target.write_text(text)
(a.output/'syntax.cpp').write_text('#include "'+str(engine/'planning/checkpoint_fixture.hpp')+'"\n')
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
(a.output/'overlay.json').write_text(json.dumps({'schema':'ownrt.recursive-provider-syntax-overlay.v1','source':str(source),'source_sha256':sha(source),'fragment_sha256':sha(fragment),'batch_sha256':sha(here/'batch.hpp'),'generated_sha256':sha(target),'purpose':'CPU syntax only; does not call preparation or execute models'},indent=2)+'\n')
print(a.output)
