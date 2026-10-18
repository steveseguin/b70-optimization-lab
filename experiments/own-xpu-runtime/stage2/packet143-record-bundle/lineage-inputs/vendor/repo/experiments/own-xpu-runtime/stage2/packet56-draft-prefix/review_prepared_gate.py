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

def check(main,rank,owner,native,snapshot):
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
 has('miss drains and checks sticky failure before parity reversal and exact image restore',undo,'e.drain();','sticky error cannot be rolled back','if(c.swapped)e.swap_state_banks();','image.restore();','c={};')
 assert undo.index('e.drain();')<undo.index('sticky error cannot be rolled back')<undo.index('e.swap_state_banks();')<undo.index('image.restore();')<undo.index('c={};')
 constructor=body(snapshot,'explicit SpeculativeImage(')
 has('snapshot covers imperative token/control writes and every plan output',constructor,'outputs{"token","position","token_history"}','outputs.insert(site.outputs.begin(),site.outputs.end())','Category::runtime_overhead,Lifetime::process','zero_private();')
 begin=body(snapshot,'void begin(')
 has('snapshot captures exact host histories and derived metadata after drain and sticky check',begin,'e.drain();','!e.poisoned&&!e.integer(0,"error")','parity=e.bank_parity;history0=e.history0;history1=e.history1;','lookup=e.lookup_ids;selected=e.selected;loaded=e.loaded_layer;fp32_sources=e.fp32_sources;fp32_extents=e.fp32_extents;','copy(false);')
 assert begin.index('e.drain();')<begin.index('!e.poisoned')<begin.index('parity=e.bank_parity')<begin.index('copy(false);')
 has('snapshot excludes committed banks and QSA prefixes from restoration',begin,'source.bank?e.state_spares.at(source.name):e.buffers[0].at(source.name).id','protected_active.push_back','size_t valid_rows=source.pooled?size_t(position/4):size_t(position);','skip=valid_rows*(source.bytes/rows);','size_t bytes=source.bytes-skip;','saved.push_back({id,skip,bytes,offset})')
 restore=body(snapshot,'void restore()')
 has('strict restore requires live image, drained owner, unpoisoned target and original bank parity',restore,'require(valid,','e.drain();','!e.poisoned&&!e.integer(0,"error")','e.bank_parity==parity','copy(true);e.drain();')
 assert restore.index('e.drain();')<restore.index('!e.poisoned')<restore.index('e.bank_parity==parity')<restore.index('copy(true);e.drain();')
 has('strict restore reinstates histories and host caches instead of clearing them',restore,'e.history0=history0;e.history1=history1;','e.lookup_ids=std::move(lookup);','e.selected=std::move(selected);','e.loaded_layer=std::move(loaded);','e.fp32_sources=std::move(fp32_sources);','e.fp32_extents=std::move(fp32_extents);','arena.row(e.fp32_sources[card]).live','valid=false;++restores;')
 assert restore.index('copy(true);e.drain();')<restore.index('e.history0=history0')<restore.index('valid=false;++restores;')
 for token in ('e.lookup_ids.clear()','e.fp32_sources[0]=0','e.fp32_extents[0]=0'):assert token not in restore,'host cache restore was replaced by clearing'
 has('streaming snapshot never resurrects released layer weights',begin,'if(!e.resident)for(int layer:e.loaded_layer)require(layer==-1,')
 has('streaming restore checks layer release and shared slot lifetime',restore,'if(!e.resident)for(int layer:e.loaded_layer)require(layer==-1,','shared_slot!=nullptr','std::memcpy(shared_slot,shared_before.data(),shared_before.size())')
 copy=body(snapshot,'void copy(bool restore)')
 has('snapshot copy preserves exact allocation ids/extents and chains owner tail',copy,'e.tail=restore?engine.copy(x.id,x.offset+off,backup,x.backup_offset+off,count,{})','engine.copy(backup,x.backup_offset+off,x.id,x.offset+off,count,{})')
 boundary=body(snapshot,'void boundary()')
 has('private image retirement requires resolved speculation and drain',boundary,'require(!valid,','e.drain();if(dirty)zero_private();','lookup.clear();selected.clear();loaded.clear();fp32_sources.clear();fp32_extents.clear();saved.clear();','shared_before.fill(0);shared_slot=nullptr;')
 assert boundary.index('require(!valid,')<boundary.index('e.drain();')<boundary.index('zero_private();')
 half=body(rank,'static Reply half_step(')
 has('snapshot begins before any guessed token or derived-state write',half,'if(request.speculative)image.begin(shared);','e.put(0,"token",&request.token,4)','e.prepare_token(request.token)')
 assert half.index('image.begin(shared)')<half.index('e.put(0,"token"')<half.index('e.prepare_token(request.token)')
 has('rank1 cannot speculate and only a completed rank0 candidate swaps after drain',half,'e.a.rank==0||!request.speculative','e.drain();','if(e.a.rank==0&&!candidate.cancelled){e.swap_state_banks();candidate.swapped=true;}')
 assert half.index('e.drain();')<half.index('if(e.a.rank==0&&!candidate.cancelled)')
 has('partial launch cancellation preserves issued prefix owner tail',half,'e.dev(0).before_compute=[&](){if(cancel_at_boundary())throw CancelledLaunch{};}', 'e.dev(0).after_compute=[&](ownrt::Event event){e.tail=event;++issued;}', 'catch(const CancelledLaunch&){candidate.cancelled=true;}', 'e.dev(0).before_compute={};e.dev(0).after_compute={};')
 assert half.count('e.dev(0).before_compute={};e.dev(0).after_compute={};')>=2,'observers survive normal or exceptional loop exit'
 assert half.rindex('e.dev(0).before_compute={};')<half.index('e.drain();'),'observer lifetime extends into drain'
 publication=body(rank,'static void publish(')
 has('cancelled candidate cannot publish fixtures',publication,'require(!c.cancelled,')
 has('target-only verification identity guards cancellation',half,'__atomic_load_n(&confirmed.position_plus_one,__ATOMIC_ACQUIRE)==uint32_t(request.position)','confirmed.token!=request.token','__atomic_store_n(&confirmed.position_plus_one,uint32_t(request.position+1),__ATOMIC_RELEASE)')
 audit=body(main,'void audit_issue_site(')
 has('audit compares selected commands to independent current-bank reconstruction',audit,'fresh_arguments=true','issue_sites[index].fp32_source','issue_sites[index].fp32_extent','execute_site(l)','x.ids==y.ids','x.pointers==y.pointers','x.argument_bytes==y.argument_bytes','x.operation_bytes==y.operation_bytes','fresh_arguments=false')
 execute=body(main,'void execute_site(')
 has('audit bypasses cached operation binding map',execute,'a.memory=="resident"&&!fresh_arguments','temporary=prepare_site(l)')
 issue=body(owner,'Event Device::issue(')
 has('compute and prepared submission poll before backend fault catch',issue,'if(!item.copy_counter&&before_compute)before_compute();','else if(after_compute)after_compute(e);')
 assert issue.index('before_compute();')<issue.index('try {'),'cancellation treated as backend fault'
 compute=body(owner,'Event Device::compute(')
 has('legacy multi-pass submission has the same cancellation boundary',compute,'if(before_compute)before_compute();','if(after_compute)after_compute(e);')
 assert compute.index('before_compute();')<compute.index('try {'),'legacy cancellation treated as backend fault'
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
 names=('main.cpp','rank.hpp','owner.cpp','single_device.cpp','strict_snapshot.hpp')
 source={n:(P/n).read_text() for n in names}
 checks=check(*(source[n] for n in names));mutations=[]
 for token in ('prepared.swap(alternate_prepared)','issue_sites.swap(alternate_issue_sites)','std::swap(buffers[0].at(name).id,id)','bank_parity^=1','x.operation_bytes==y.operation_bytes','fresh_arguments=true'):
  damaged=source['main.cpp'].replace(token,'REMOVED_BY_NEGATIVE_TEST',1)
  try:check(damaged,source['rank.hpp'],source['owner.cpp'],source['single_device.cpp'],source['strict_snapshot.hpp'])
  except AssertionError:mutations.append(token)
  else:raise AssertionError('stale-bank regression escaped: '+token)
 for name,token in [('rank.hpp','!candidate.cancelled'),('rank.hpp','candidate.swapped=true;'),('rank.hpp','if(c.swapped)'),('rank.hpp','e.tail=event;++issued;'),('rank.hpp','require(!c.cancelled,'),('rank.hpp','__ATOMIC_ACQUIRE'),('owner.cpp','if(!item.copy_counter&&before_compute)before_compute();'),('owner.cpp','if(before_compute)before_compute();')]:
  damaged=dict(source);damaged[name]=damaged[name].replace(token,'REMOVED_BY_NEGATIVE_TEST',1)
  try:check(*(damaged[n] for n in names))
  except AssertionError:mutations.append(name+':'+token)
  else:raise AssertionError('partial-cancellation ownership regression escaped: '+name+':'+token)
 # Scoped mutations remove guarantees within the exact helper body, so a
 # similarly named check elsewhere cannot accidentally satisfy the negative.
 strict_mutations=[
  ('rank.hpp','static void undo(','e.drain();'),
  ('rank.hpp','static void undo(','require(!e.integer(0,"error"),"sticky error cannot be rolled back");'),
  ('rank.hpp','static void undo(','image.restore();'),
  ('rank.hpp','static Reply half_step(','if(request.speculative)image.begin(shared);'),
  ('strict_snapshot.hpp','explicit SpeculativeImage(','"token","position","token_history"'),
  ('strict_snapshot.hpp','explicit SpeculativeImage(','outputs.insert(site.outputs.begin(),site.outputs.end())'),
  ('strict_snapshot.hpp','void begin(','e.drain();'),
  ('strict_snapshot.hpp','void begin(','!e.poisoned&&!e.integer(0,"error")'),
  ('strict_snapshot.hpp','void begin(','history0=e.history0;history1=e.history1;'),
  ('strict_snapshot.hpp','void begin(','lookup=e.lookup_ids;'),
  ('strict_snapshot.hpp','void begin(','source.bank?e.state_spares.at(source.name):e.buffers[0].at(source.name).id'),
  ('strict_snapshot.hpp','void begin(','skip=valid_rows*(source.bytes/rows);'),
  ('strict_snapshot.hpp','void begin(','copy(false);'),
  ('strict_snapshot.hpp','void restore()','require(valid,'),
  ('strict_snapshot.hpp','void restore()','e.drain();'),
  ('strict_snapshot.hpp','void restore()','!e.poisoned&&!e.integer(0,"error")'),
  ('strict_snapshot.hpp','void restore()','e.bank_parity==parity'),
  ('strict_snapshot.hpp','void restore()','copy(true);e.drain();'),
  ('strict_snapshot.hpp','void restore()','e.history0=history0;e.history1=history1;'),
  ('strict_snapshot.hpp','void restore()','e.lookup_ids=std::move(lookup);'),
  ('strict_snapshot.hpp','void restore()','e.selected=std::move(selected);'),
  ('strict_snapshot.hpp','void restore()','e.loaded_layer=std::move(loaded);'),
  ('strict_snapshot.hpp','void restore()','e.fp32_sources=std::move(fp32_sources);'),
  ('strict_snapshot.hpp','void restore()','e.fp32_extents=std::move(fp32_extents);'),
  ('strict_snapshot.hpp','void restore()','arena.row(e.fp32_sources[card]).live'),
  ('strict_snapshot.hpp','void restore()','if(!e.resident)for(int layer:e.loaded_layer)require(layer==-1,'),
  ('strict_snapshot.hpp','void restore()','std::memcpy(shared_slot,shared_before.data(),shared_before.size())'),
  ('strict_snapshot.hpp','void copy(bool restore)','e.tail=restore?engine.copy(x.id,x.offset+off,backup,x.backup_offset+off,count,{})'),
  ('strict_snapshot.hpp','void boundary()','require(!valid,'),
 ]
 for name,signature,token in strict_mutations:
  damaged=dict(source);original=body(damaged[name],signature);assert token in original,(name,signature,token)
  damaged[name]=damaged[name].replace(original,original.replace(token,'REMOVED_BY_NEGATIVE_TEST',1),1)
  try:check(*(damaged[n] for n in names))
  except AssertionError:mutations.append(name+':'+signature+':'+token)
  else:raise AssertionError('strict snapshot guarantee escaped: '+name+':'+token)
 row=dict(passed=True,device_executed=False,structural_checks=checks,checks=len(checks),negative_mutations_rejected=len(mutations),mutations=mutations,source_sha256={n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in (*names,'review_prepared_gate.py')},limitation='Source/mutation proof only; execution gates independently establish arguments, tokens, layers and rollback bytes.')
 (P/'review-prepared-gates.json').write_text(json.dumps(row,indent=2)+'\n')
 print(json.dumps({k:row[k] for k in ('passed','checks','negative_mutations_rejected','device_executed')}))
if __name__=='__main__':run()
