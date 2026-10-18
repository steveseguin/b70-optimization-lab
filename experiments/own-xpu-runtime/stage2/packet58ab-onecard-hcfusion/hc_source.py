"""Resolve port headers into one private checked closure, with prepared submission."""
import importlib.util,json,re
from pathlib import Path
from native_source import P,BASE
from frozen_inputs import FROZEN
MIRROR=BASE/'build/checked'
CHECKED=MIRROR/'experiments/own-xpu-runtime/stage2/packet58j-onecard-port'
s=importlib.util.spec_from_file_location('p58ab_packet58ab_submission_overlay',BASE/'submission_overlay.py')
overlay=importlib.util.module_from_spec(s);s.loader.exec_module(overlay)
def header(source):
    if source.name=="kernel_guard.hpp":return BASE/"kernel_guard.hpp"
    target=MIRROR/source.relative_to(FROZEN)
    if target.exists():return target
    text=overlay.apply_submission_overlay(source,source.read_text())
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text('') # recursion sentinel; no cyclic header definitions
    def resolve(m):
        options=[source.parent/m[1],BASE/m[1],BASE.parents[1]/'stage1/packet3-prep/src'/m[1],BASE.parent/'packet2/kernels'/m[1],BASE.parent/'packet2/loader'/m[1]]
        original=next(p.resolve() for p in options if p.is_file())
        return '#include '+json.dumps(str(header(original)))
    text=re.sub(r'^\s*#include\s*"([^"\n]+)"',resolve,text,flags=re.M)
    target.write_text('#include '+json.dumps(str(BASE/'kernel_guard.hpp'))+'\n'+text)
    return target

def prepare():
    names=('p60_submit.cpp','p60_submit.hpp','p60_math.hpp','p60_kernels.hpp')
    for name in names:
        source=P/'native'/name
        text=overlay.apply_submission_overlay(source,source.read_text())
        def resolve(m):
            if m[1] in names:target=P/'build/native'/m[1]
            else:
                options=[BASE/m[1],BASE.parents[1]/'stage1/packet3-prep/src'/m[1],BASE.parent/'packet2/kernels'/m[1]]
                target=header(next(p.resolve() for p in options if p.is_file()))
            return '#include '+json.dumps(str(target))
        text=re.sub(r'^\s*#include\s*"([^"\n]+)"',resolve,text,flags=re.M)
        (P/'build/native'/name).write_text(text)
