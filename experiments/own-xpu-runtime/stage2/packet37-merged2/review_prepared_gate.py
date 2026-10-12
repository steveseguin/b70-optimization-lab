"""Independent CPU source/mutation gate for banked prepared-launch ownership.

This structural proof complements forced-miss execution; it never substitutes for
mini/real-model output, state-byte or actual argument-block gates.
"""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent

def body(source,signature):
 start=source.index('{',source.index(signature));depth=1;end=start+1
 while depth:
  depth += (source[end]=='{')-(source[end]=='}');end+=1
 return source[start+1:end-1]

def check(main,rank,owner,native):
 checks=[]
 def has(name,text,*tokens):
  assert all(t in text for t in tokens),name
  checks.append(name)
 swap=body(main,'void swap_state_banks()')
 has('bank ids/maps/commands/parity move together after drain',swap,'drain();','std::swap(buffers[0].at(name).id,id)','prepared.swap(alternate_prepared)','issue_sites.swap(alternate_issue_sites)','bank_parity^=1','fp32_sources[0]=0','fp32_extents[0]=0')
 assert swap.index('drain();')<swap.index('std::swap')
 banks=body(rank,'static void banks(')
 has('both command parities captured before request admission',banks,'e.prepare_plan();e.prepare_commands();','e.swap_state_banks();e.prepare_plan();e.prepare_commands();e.swap_state_banks();')
 undo=body(rank,'static void undo(')
 has('miss drains before bank restore and history/cache reset',undo,'e.drain();','sticky error cannot be rolled back','e.swap_state_banks();','e.history0=c.h0','e.history1=c.h1','c.token_history.data()','e.put(0,"position",&c.position,4)','e.lookup_ids.clear()','e.fp32_sources[0]=0','e.fp32_extents[0]=0')
 assert undo.index('e.drain();')<undo.index('e.swap_state_banks();')
 half=body(rank,'static Reply half_step(')
 has('rank1 cannot speculate and rank0 swaps only after drain',half,'e.a.rank==0||!request.speculative','e.drain();','if(e.a.rank==0)e.swap_state_banks();')
 assert half.index('e.drain();')<half.index('if(e.a.rank==0)e.swap_state_banks();')
 audit=body(main,'void audit_issue_site(')
 has('audit compares selected commands to independent current-bank reconstruction',audit,'fresh_arguments=true','issue_sites[index].fp32_source','issue_sites[index].fp32_extent','execute_site(l)','x.ids==y.ids','x.pointers==y.pointers','x.argument_bytes==y.argument_bytes','x.operation_bytes==y.operation_bytes','fresh_arguments=false')
 execute=body(main,'void execute_site(')
 has('audit bypasses cached operation binding map',execute,'a.memory=="resident"&&!fresh_arguments','temporary=prepare_site(l)')
 issue=body(owner,'Event Device::issue(')
 has('issue rejects changed owner and generation',issue,'admit();','item.owner!=this','item.generation!=generation_','item.submit()')
 release=body(owner,'void Arena::release(')
 has('release requires idle and invalidates commands',release,'owner_.in_flight()','owner_.generation_=next_handle()','owner_.backend_->release')
 assert release.index('owner_.generation_=next_handle()')<release.index('owner_.backend_->release')
 has('single native owner supports prepared submission on in-order queue',native,'sycl::property::queue::in_order{}','SubmissionCapture scope(captured)','native.submit(*queue_,p,{})','captured->make_callback({&events_,&error_mutex_,&error_,&allocation_card_,0})')
 dev=body(main,'ownrt::Device &dev(')
 assert 'require(' not in dev,'device accessor constructs string on success'
 has('device accessor rejects only on failure without temporary string',dev,'if(c!=0)throw','return *devices.at(0)')
 issue_site=body(main,'flash::Event issue_site(').split('if(a.checked',1)[0]
 issue_success=issue.split('catch(',1)[0]
 for name,text in [('prepared issue site',issue_site),('owner issue success',issue_success)]:
  for token in ('std::string','std::map','std::unordered','malloc(','calloc(','realloc(','new ','make_shared','make_unique','get_device(','get_info<','.find(','set_class(','require('):
   assert token not in text,(name,'prohibited success-path work',token)
  checks.append(name+' has no allocation/string/map/query calls')
 has('rank loop uses captured metadata and fixed layer capture array',half,'e.prepared_path?&e.issue_sites','ready?ready->prefill_skip','ready?ready->layer_end','ready?ready->layer','std::array<int,48> captured')
 enqueue=body(main,'flash::Event enqueue(').split('guard();',1)[0]
 has('per-launch prepared decision is cached boolean',enqueue,'if(prepared_path)')
 assert 'a.memory==' not in enqueue
 return checks

def run():
 names=('main.cpp','rank.hpp','owner.cpp','single_device.cpp')
 source={n:(P/n).read_text() for n in names}
 checks=check(*(source[n] for n in names));mutations=[]
 for token in ('prepared.swap(alternate_prepared)','issue_sites.swap(alternate_issue_sites)','std::swap(buffers[0].at(name).id,id)','bank_parity^=1','x.operation_bytes==y.operation_bytes','fresh_arguments=true'):
  damaged=source['main.cpp'].replace(token,'REMOVED_BY_NEGATIVE_TEST',1)
  try:check(damaged,source['rank.hpp'],source['owner.cpp'],source['single_device.cpp'])
  except AssertionError:mutations.append(token)
  else:raise AssertionError('stale-bank regression escaped: '+token)
 row=dict(passed=True,device_executed=False,structural_checks=checks,checks=len(checks),negative_mutations_rejected=len(mutations),mutations=mutations,source_sha256={n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in names},limitation='Source/mutation proof only; execution gates independently establish arguments, tokens, layers and rollback bytes.')
 (P/'review-prepared-gates.json').write_text(json.dumps(row,indent=2)+'\n')
 print(json.dumps({k:row[k] for k in ('passed','checks','negative_mutations_rejected','device_executed')}))
if __name__=='__main__':run()
