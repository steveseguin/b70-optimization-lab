from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
BASE=P/"frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port"
def once(text,old,new):
    assert text.count(old)==1,(old,text.count(old))
    return text.replace(old,new)
