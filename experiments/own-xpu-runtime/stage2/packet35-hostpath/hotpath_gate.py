"""Source audit complements the actual-family mock's zero-allocation counter."""
import hashlib,json,re
from pathlib import Path
P=Path(__file__).resolve().parent

def body(path, signature):
 text=path.read_text();start=text.index(signature);opening=text.index('{',start);end=opening+1;depth=1
 while depth:
  depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]

def main():
 owner=body(P/'owner.cpp','Event Device::issue(')
 engine=body(P/'main.cpp','flash::Event issue_site(')
 finish=body(P/'main.cpp','void finish(int, Launch')
 checks={}
 checks['device_no_lookup_or_construction']=not re.search(r'fast_owners|arena\.row|\.find\(|std::(map|string|vector)|\bnew\b|\b(?:malloc|calloc|realloc|aligned_alloc)\s*\(|get_device\(|get_info<|chrono::',owner)
 checks['device_one_bound_call']=owner.count('item.submit()')==1
 checks['engine_no_string_dispatch']=not re.search(r'a\.timing|\.find\(|\.substr\(|std::stoi|l\.op|l\.label|gemv_choices|buffers\[',engine)
 checks['engine_clock_guarded']='auto started=class_timing?std::chrono::steady_clock::now()' in engine and 'if(class_timing)family_ms' in engine
 checks['finish_mode_cached']='profile_events' in finish and 'a.timing' not in finish
 checks['device_generation_guard']='item.generation!=generation_' in owner
 assert all(checks.values()),checks
 r=dict(passed=True,device_executed=False,checks=checks,count=len(checks),reviewed_hotpath_sha256={k:hashlib.sha256(v.encode()).hexdigest() for k,v in [('Device::issue',owner),('Engine::issue_site',engine),('Engine::finish',finish)]},scope='Application fast path source audit. Failure branches may construct diagnostics; checked/mini/class modes deliberately perform extra work. Per-family malloc/new hooks cover actual owner issue calls. SYCL internals excluded.')
 (P/'hotpath-gates.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
if __name__=='__main__':main()
