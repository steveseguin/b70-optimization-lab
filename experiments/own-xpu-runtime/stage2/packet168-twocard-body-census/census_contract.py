"""Diagnostic contract. A missing qualification is never an inferred zero cost."""
from pathlib import Path
import json
import suite_metrics
P=Path(__file__).resolve().parent
ARITHMETIC='iq3-p49-split32-v1'
CLASSES=('attention','gdn','router','routed_experts','shared_expert',
         'dense_hc','norms_glue','cross_card_transfer','lm_head_argmax')
CONTROLS=('C0','C1','C2')
ORDER=('C0',*CLASSES[:4],'C1',*CLASSES[4:],'C2')
IDS=tuple(suite_metrics.PROMPT_CLASSES)
CLOSED={
 'attention':'p116: scheduling stays closed unless new matched net saving supports it',
 'gdn':'p113/p107: unchanged recurrence order; no nonfinite arithmetic waiver',
 'router':'p112/p164: normalized probabilities and exact ties remain required',
 'routed_experts':'p81/p95/p102/p162: fewer loads are not measured end-to-end savings',
 'shared_expert':'p104/p109: existing fused down/blend cannot be counted twice',
 'dense_hc':'p140: replaces assumed transfer pricing only after complete matched census',
 'norms_glue':'p78/p94/p107: full rounded producer/consumer boundary remains required',
 'cross_card_transfer':'p149/p160: no extrapolation from 96 exchanges to a new shape',
 'lm_head_argmax':'p127/p160/p161: both prefix and suffix, merge and verification required',
}
def require(ok,message):
    if not ok:raise ValueError(message)
def read(path):return json.loads(Path(path).read_text())
