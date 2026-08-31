"""Diagnostic-only GDN output trace installed as sitecustomize."""
import hashlib,json,os
from pathlib import Path
OUTPUT=os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_OUT")
TARGET_CALL=int(os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_CALL","2"))
TARGET_LAYER=int(os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_LAYER","0"))
if OUTPUT:
 import torch
 from vllm.model_executor.models.qwen3_5 import QwenGatedDeltaNetAttention
 _original=QwenGatedDeltaNetAttention.forward
 def _hash(x):
  v=x.detach(); raw=v.contiguous().cpu().reshape(-1).view(torch.uint8)
  return {"dtype":str(v.dtype),"shape":list(v.shape),"stride":list(v.stride()),"sha256":hashlib.sha256(raw.numpy().tobytes()).hexdigest()}
 def _trace(self,*args,**kwargs):
  call=getattr(self,"_neural_download_gdn_trace_call",0); self._neural_download_gdn_trace_call=call+1
  result=_original(self,*args,**kwargs)
  if self.layer_idx==TARGET_LAYER and call==TARGET_CALL:
   item=_hash(result); payload={"schema":"neural.download.qwen38-gdn-output-trace.raw.v1","call_index":call,"layer_index":self.layer_idx,"positions":{"boundary":"gdn-output"},"hidden_states":item,"residual":item}
   dst=Path(OUTPUT); tmp=dst.with_suffix(dst.suffix+".tmp"); tmp.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n"); os.replace(tmp,dst)
  return result
 QwenGatedDeltaNetAttention.forward=_trace
