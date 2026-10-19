"""Diagnostic contract. A missing qualification is never an inferred zero cost."""
from pathlib import Path
import json
import suite_metrics
P=Path(__file__).resolve().parent
ARITHMETIC='iq3-p49-split32-v1'
# v3 (after device-census-B-v2): attention has no arm. Its qsa_* launches run
# in every control/arm/repair body pass and fall into the residual. packet173's
# lever table finds no attention lever, so nothing ranked is lost.
CLASSES=('gdn','routed_experts','router_shared_expert',
         'dense_hc','norms_glue')
DROPPED_TO_RESIDUAL=('attention','cross-card transfer','split head/argmax/merge')
RESIDUAL='residual'
REPORT_CLASSES=(*CLASSES,RESIDUAL)
# Native classify() codes; router+shared expert is ONE fused class (code 3).
ARM_CODES={'gdn':2,'router_shared_expert':3,'routed_experts':4,'dense_hc':6,'norms_glue':7}
NATIVE_ARMS=tuple(ARM_CODES[c] for c in CLASSES)
REFUSED_NATIVE_ARMS=(1,5,8,9)  # attention(1) is residual work; 5/8/9 have no class
TOKENS=64      # exact oracle-prefix tokens per control/setup request
REPEATS=3      # paired control/arm passes per probe call (native fixture repeats)
PROBE_OP=20    # native diagnostic command
CONTROLS=('C0','C1','C2')
ORDER=('C0',*CLASSES[:2],'C1',*CLASSES[2:],'C2')
NATIVE_ORDER=(0,*NATIVE_ARMS[:2],0,*NATIVE_ARMS[2:],0)
IDS=tuple(suite_metrics.PROMPT_CLASSES)
CLOSED={
 'gdn':'p113/p107: unchanged recurrence order; no nonfinite arithmetic waiver',
 'router_shared_expert':'p109/p112/p164: route/shared activation and shared-down/mixture stay fused; exact routes/ties required',
 'routed_experts':'p81/p95/p102/p162: fewer loads are not measured end-to-end savings',
 'dense_hc':'p140: replaces assumed transfer pricing only after complete matched census',
 'norms_glue':'p78/p94/p107: full rounded producer/consumer boundary remains required',
 'residual':'Attention (qsa_*; no arm since v3, p116 scheduling closed, p173 no lever), cross-card transfer, split head and all unisolated work/overlap; subtraction only, not causally isolated',
}
def require(ok,message):
    if not ok:raise ValueError(message)
def read(path):return json.loads(Path(path).read_text())
