#!/usr/bin/env python3
"""Build a checked source overlay only. Never compiles, launches or changes the parent."""
import difflib,hashlib,json,os,shutil
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];PARENT=P.parent/'packet181-session-swap-v3'
NATIVE=PARENT/'one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/build/native'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def replace(text,old,new,count=1):
 assert text.count(old)==count,(old[:100],text.count(old),count)
 return text.replace(old,new)
def transform(main,checkpoint):
 main='#include "request_front.hpp"\n'+main
 main=replace(main,'fs::path(__FILE__).parent_path()/"rope.bf16"','fs::path("/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet181-session-swap-v3/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/rope.bf16")')
 main=replace(main,'fs::path(__FILE__).parent_path()/"selection.json"','fs::path("/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet181-session-swap-v3/one-card/selection.json")')
 main=replace(main,'struct Options {','struct Options {\n  bool request_front=false;int front_max_requests=0,front_idle_seconds=0;\n  fs::path front_checkpoints,front_tokenizer;')
 main=replace(main,'Options: --argument-audit','Options: --request-front --request-front-max-requests --request-front-idle-seconds --request-front-checkpoints --request-front-tokenizer-identity --argument-audit')
 main=replace(main,'    if(k=="--cache-cap")a.cache_cap=value();','''    if(k=="--request-front")a.request_front=true;
    else if(k=="--request-front-max-requests")a.front_max_requests=requestfront::number(value(),1,1024);
    else if(k=="--request-front-idle-seconds")a.front_idle_seconds=requestfront::number(value(),1,3600);
    else if(k=="--request-front-checkpoints")a.front_checkpoints=value();
    else if(k=="--request-front-tokenizer-identity")a.front_tokenizer=value();
    else if(k=="--cache-cap")a.cache_cap=value();''')
 main=replace(main,'  require(a.native_nice>=0', '''  if(a.request_front) {
    require(a.front_max_requests>0&&a.front_idle_seconds>0,"explicit request-front bounds required");
    require(a.front_checkpoints.is_absolute()&&a.front_tokenizer.is_absolute(),"absolute startup checkpoint/tokenizer paths required");
    require(a.inputs.empty()&&a.suite_inputs.empty()&&a.bracket_inputs.empty()&&a.checkpoint_save.empty()&&a.checkpoint_restore.empty()&&a.tokenizer_identity.empty(),"front owns request inputs and checkpoint modes");
    require(!a.first&&!a.record&&!a.priority_probe&&!a.mtp&&a.rank<0&&a.cards==1&&a.oracle.empty()&&a.retain_steps.ranges.empty(),"front requires plain single owner and --retain-steps none");
  } else require(a.front_max_requests==0&&a.front_idle_seconds==0&&a.front_checkpoints.empty()&&a.front_tokenizer.empty(),"request-front options without mode");
  require(a.native_nice>=0''')
 main=replace(main,'  bool comparison = true, did_compare = false, compute_started = false;','''  bool comparison = true, did_compare = false, compute_started = false;
  bool owner_shutdown_attempted=false,owner_shutdown_complete=false;
  std::unique_ptr<requestfront::Channel> front;
  Options front_base;''')
 main=replace(main,'    a = parse(argc, argv);','''    a = parse(argc, argv);
    if(a.request_front){
      front=std::make_unique<requestfront::Channel>(a.front_max_requests,a.front_idle_seconds);
      pipeline::checkpoint_tokenizer_identity(a.front_tokenizer,"front startup");
      front_base=a;
    }''')
 main=replace(main,'    if(!a.suite_inputs.empty()) {','    if(!a.request_front&&!a.suite_inputs.empty()) {')
 main=replace(main,'    }else requests.push_back({"",a.inputs});','    }else if(!a.request_front)requests.push_back({"",a.inputs});')
 main=replace(main,'    e->bracket_weights_locked=!a.bracket_inputs.empty();','''    if(front)front->emit("{\\"event\\":\\"ready\\",\\"protocol\\":\\"ownrt.request-front.v1\\",\\"context\\":"+std::to_string(p.g.context)+",\\"vocab\\":"+std::to_string(p.g.vocab)+",\\"max_requests\\":"+std::to_string(a.front_max_requests)+",\\"model_loads\\":1,\\"experimental\\":true}");
    e->bracket_weights_locked=!a.bracket_inputs.empty();''')
 main=replace(main,'    for(const auto& [request_id,input_path]:requests) {','''    for(size_t request_number=0;;++request_number) {
    std::string request_id;fs::path input_path;
    if(front){
      auto request=front->reader.next(p.g.vocab,p.g.context,stopped,e->deadline);
      if(!request)break;
      a=front_base;request_id=request->id;a.tokens=request->max_new;
      const auto request_output=root_output/"requests"/request_id;
      require(!fs::exists(fs::symlink_status(request_output)),"fresh request output required");
      fs::create_directories(request_output);input_path=request_output/"input.tokens";
      std::ostringstream tokens;for(auto token:request->tokens)tokens<<token<<'\\n';save(input_path,tokens.str());a.inputs=input_path;
      if(!request->restore.empty()){a.checkpoint_restore=a.front_checkpoints;a.checkpoint_id=request->restore;}
      if(!request->save.empty()){a.checkpoint_save=a.front_checkpoints;if(request->restore.empty())a.checkpoint_id=request->save;else a.checkpoint_save_id=request->save;}
      if(!request->restore.empty()||!request->save.empty())a.tokenizer_identity=a.front_tokenizer;
      if(!a.checkpoint_save.empty()){const auto sid=a.checkpoint_restore.empty()?a.checkpoint_id:a.checkpoint_save_id;
        require(!fs::exists(fs::symlink_status(a.checkpoint_save/sid)),"checkpoint save refused: never overwrite");}
      if(!a.checkpoint_restore.empty())pipeline::checkpoint_precheck(a.checkpoint_restore,a.checkpoint_id,a.inputs,a.tokens,!a.checkpoint_save.empty(),a.tokenizer_identity,a.mini);
      else if(!a.checkpoint_save.empty())pipeline::checkpoint_tokenizer_identity(a.tokenizer_identity,"save");
      // Quiesce publication without invalidating immutable expert-cache residency.
      e->drain();e->cache_quiesce();e->a.tokens=a.tokens;
      front->emit("{\\"event\\":\\"request-start\\",\\"id\\":"+ownrt::quote(request_id)+"}");
    }else{
      if(request_number==requests.size())break;
      request_id=requests[request_number].first;input_path=requests[request_number].second;
    }''')
 main=replace(main,'    output=request_id.empty()?view_output:view_output/request_id;','    output=front?root_output/"requests"/request_id:(request_id.empty()?view_output:view_output/request_id);')
 main=replace(main,'      std::cout<<"token_id "<<next<<\'\\n\';','      if(front)front->token(request_id,generated.size()-1,next);else std::cout<<"token_id "<<next<<\'\\n\';',2)
 main=replace(main,'    save(output/"lookup-request-complete.json","{\\"passed\\":true}\\n");','''    save(output/"lookup-request-complete.json","{\\"passed\\":true}\\n");
    if(front){
      e->drain();e->cache_quiesce();require(!e->poisoned&&!e->integer(0,"error"),"front request boundary failure");
      front->emit("{\\"event\\":\\"request-complete\\",\\"id\\":"+ownrt::quote(request_id)+",\\"result\\":"+ownrt::quote("requests/"+request_id+"/result.json")+",\\"generated_tokens\\":"+std::to_string(generated.size())+",\\"owner_resident\\":true,\\"request_quiesced\\":true}");
    }''')
 main=replace(main, r'<<",\"cached_tokens\":0,\"gpu_count\":1,\"decode_mode\":\"plain\",\"context\":"<<a.context', r'<<",\"cached_tokens\":"<<(front&&restoring?std::to_string(restored.position):"0")<<(front?",\"request_front_scope\":\"experimental-warm-owner-v1\",\"session_reuse\":"+std::string(restoring?"true":"false"):"")<<",\"gpu_count\":1,\"decode_mode\":\"plain\",\"context\":"<<a.context')
 main=replace(main,'    teardown = e->shutdown();\n    e.reset();','    owner_shutdown_attempted=true;teardown = e->shutdown();owner_shutdown_complete=true;\n    e.reset();')
 main=replace(main,'    if(!a.bracket_inputs.empty()&&!a.output.empty())output=a.output;','    if((front||!a.bracket_inputs.empty())&&!a.output.empty())output=a.output;')
 main=replace(main,'      try {teardown=e->shutdown();}catch(const std::exception& close_error) {error+="; ";error+=close_error.what();}', '      if(!owner_shutdown_attempted){owner_shutdown_attempted=true;try {teardown=e->shutdown();owner_shutdown_complete=true;}catch(const std::exception& close_error) {error+="; ";error+=close_error.what();}}')
 main=replace(main,'  r << ",\\"safe_to_exit\\":true,\\"cpu_affinity\\":"<<affinity_json', '  r << ",\\"safe_to_exit\\":"<<(front?(owner_shutdown_complete?"true":"false"):"true")<<",\\"cpu_affinity\\":"<<affinity_json')
 main=replace(main,'  save(output / "receipt.json", r.str());\n  return error.empty() && comparison ? 0 : 1;', '''  save(output / "receipt.json", r.str());
  if(front){
    try {
      if(error.empty()&&comparison&&owner_shutdown_complete)
        front->emit("{\\"event\\":\\"stopped\\",\\"reason\\":"+ownrt::quote(front->reader.reason)+",\\"safe_to_exit\\":true,\\"completed_requests\\":"+std::to_string(front->reader.count())+"}");
      else front->emit("{\\"event\\":\\"fatal\\",\\"error\\":"+ownrt::quote(error)+",\\"safe_to_exit\\":"+(owner_shutdown_complete?"true":"false")+"}");
    }catch(const std::exception& transport_error){std::cerr<<transport_error.what()<<'\\n';return 1;}
  }
  return error.empty() && comparison ? 0 : 1;''')
 checkpoint=checkpoint.replace('"qualified-one-card"','"experimental-warm-front"').replace('"v1.2+p181"','"v1.2+p197"').replace('"packet181-session-swap-v3"','"packet197-warm-request-front"')
 begin=checkpoint.index('static const char* const CHECKPOINT_QUALIFIED_BY=');end=checkpoint.index('// The only prompt mechanism',begin)
 checkpoint=checkpoint[:begin]+'''// New transport/binary is unqualified; these inherited field names do not assert a device gate.
static const char* const CHECKPOINT_QUALIFIED_BY="{\\"scope\\":\\"experimental warm request front; no device qualification\\",\\"device_gates\\":[]}";
'''+checkpoint[end:]
 checkpoint=checkpoint.replace('this engine reads v1.2+p181 and v1.2+p180 checkpoints','this engine reads experimental v1.2+p197 and legacy v1.2+p180 metadata; exact binary identity still required')
 return main,checkpoint

def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert shutil.disk_usage('/').free>=27_000_000_000
 pins=json.loads((P/'parent-pins.json').read_text())
 for name,digest in pins['sources'].items():assert sha(ROOT/name)==digest,name
 original=(NATIVE/'main.cpp').read_text();header=(NATIVE/'checkpoint.hpp').read_text();main_source,checkpoint=transform(original,header)
 out=P/'build/native';out.mkdir(parents=True,exist_ok=True)
 for name,text in [('main.cpp',main_source),('checkpoint.hpp',checkpoint),('entry-main.cpp',(NATIVE/'entry-main.cpp').read_text())]:(out/name).write_text(text)
 shutil.copy2(P/'native/request_front.hpp',out/'request_front.hpp')
 patch=''.join(difflib.unified_diff(original.splitlines(True),main_source.splitlines(True),fromfile='p181/main.cpp',tofile='p197/main.cpp'))+''.join(difflib.unified_diff(header.splitlines(True),checkpoint.splitlines(True),fromfile='p181/checkpoint.hpp',tofile='p197/checkpoint.hpp'))
 (P/'native-request-front.patch').write_text(patch)
 row=dict(passed=True,device_executed=False,compiled=False,parent_pins_sha256=sha(P/'parent-pins.json'),patch_sha256=sha(P/'native-request-front.patch'),outputs={str(p.relative_to(P)):sha(p) for p in out.iterdir() if p.is_file()},scope='Source overlay only; parser, integration, native compilation and arithmetic qualification remain separate gates.')
 (P/'evidence').mkdir(exist_ok=True);(P/'evidence/source-overlay.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row))
if __name__=='__main__':main()
