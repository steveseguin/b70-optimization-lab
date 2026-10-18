"""Packet-owned checked include closure; never write a frozen source."""
import json
import importlib.util
import re
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
BASE=P.parent/'packet103-record-bundle'
OWNER=P.parents[1]/'stage1/packet3-prep/src'
DEST=P/'build/checked'

def prepare(entry):
    seen={}
    def copy(src):
        src=Path(src).resolve()
        if src==OWNER/'owner.hpp':src=BASE/'owner_api.hpp'
        dest=DEST/src.relative_to(ROOT)
        if src in seen:return dest
        seen[src]=dest
        text=src.read_text()
        if src==BASE/'argument_block.hpp':
            # CPU capture audit must include every new dispatch choice plus
            # packet60's capacity; device arithmetic and functor bytes stay put.
            text=text.replace('||requires{op.family;};','||requires{op.family;}||requires{op.capacity;}||requires{op.arm;}||requires{op.down;};')
            text=text.replace('FIELD(a);FIELD(width);FIELD(family);FIELD(metadata);FIELD(count);','FIELD(a);FIELD(width);FIELD(family);FIELD(metadata);FIELD(count);FIELD(capacity);FIELD(arm);FIELD(down);')
        # Runtime captures prepared command groups. Preserve that protocol across
        # the shared expert image; q.submit at capture time would execute work.
        spec=importlib.util.spec_from_file_location('p115_submission_overlay',BASE/'submission_overlay.py')
        overlay=importlib.util.module_from_spec(spec);spec.loader.exec_module(overlay)
        text=overlay.apply_submission_overlay(src,text)
        def include(m):
            name=m[1]
            options=[src.parent/name,BASE/name,OWNER/name,P.parent/'packet2/kernels'/name,P.parent/'packet2/loader'/name]
            target=next((p for p in options if p.is_file()),None)
            if target is None:raise ValueError(f'include unresolved: {src}: {name}')
            return '#include '+json.dumps(str(copy(target)))
        text=re.sub(r'^\s*#include\s*"([^"\n]+)"',include,text,flags=re.M)
        dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists() or dest.read_text()!=text:dest.write_text(text)
        return dest
    return copy(entry)
