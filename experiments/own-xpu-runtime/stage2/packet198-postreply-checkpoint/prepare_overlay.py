#!/usr/bin/env python3
"""Generate a thin source-only p198 overlay from the exact frozen p197 sources."""
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
PARENT = P.parent / 'packet197-warm-request-front'
NATIVE = PARENT / 'build/native'


def sha(path):
    with Path(path).open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def replace(text, old, new, count=1):
    assert text.count(old) == count, (old[:100], text.count(old), count)
    return text.replace(old, new)


CONTROL = r'''      if(request->kind!=requestfront::Kind::run){
        require(front_pending.present&&front_pending.request_id==request->request_id,"stale postreply descriptor");
        e->drain();e->cache_quiesce();require(!e->poisoned&&!e->integer(0,"error"),"postreply control boundary failure");
        const bool final_request=front->reader.final_request();
        if(request->kind==requestfront::Kind::save){
          require(request->tokens.size()==front_pending.processed.size()+1&&
            std::equal(front_pending.processed.begin(),front_pending.processed.end(),request->tokens.begin())&&
            request->tokens.back()==front_pending.next_token,"postreply full visible tokens differ from retained state");
          const auto operation_output=root_output/"operations"/request->id;
          require(!fs::exists(fs::symlink_status(operation_output)),"fresh operation output required");
          fs::create_directories(operation_output);
          const auto saved=pipeline::checkpoint_save(*e,front_base.front_checkpoints,request->checkpoint_id,
            front_pending.prompt,front_pending.processed,front_pending.next_token,front_base.front_tokenizer,front_pending.parent);
          e->drain();e->cache_quiesce();require(!e->poisoned&&!e->integer(0,"error"),"postreply save boundary failure");
          std::ostringstream event;
          event<<"{\"event\":\"checkpoint-saved\",\"operation_id\":"<<ownrt::quote(request->id)
            <<",\"request_id\":"<<ownrt::quote(request->request_id)<<",\"checkpoint_id\":"<<ownrt::quote(request->checkpoint_id)
            <<",\"manifest_sha256\":"<<ownrt::quote(saved.manifest_sha256)<<",\"checkpoint_path\":"<<ownrt::quote(request->checkpoint_id)
            <<",\"path_scope\":\"startup-checkpoint-root\",\"receipt\":"<<ownrt::quote("operations/"+request->id+"/save.json")
            <<",\"processed_tokens\":"<<front_pending.processed.size()<<",\"visible_tokens\":"<<(front_pending.processed.size()+1)
            <<",\"pending_token\":"<<front_pending.next_token
            <<",\"request_disposed\":true,\"request_quiesced\":true,\"final_request\":"<<(final_request?"true":"false")<<"}";
          save(operation_output/"save.json",event.str()+"\n");
          front->reader.complete_control(request->request_id);front_pending=FrontPending{};
          front->emit(event.str());
        }else{
          front->reader.complete_control(request->request_id);front_pending=FrontPending{};
          front->emit("{\"event\":\"request-released\",\"operation_id\":"+ownrt::quote(request->id)+
            ",\"request_id\":"+ownrt::quote(request->request_id)+
            ",\"request_disposed\":true,\"request_quiesced\":true,\"final_request\":"+(final_request?"true":"false")+"}");
        }
        continue;
      }
'''

DESCRIPTOR = r'''      require(!front_pending.present&&!generated.empty(),"one nonempty postreply descriptor required");
      front_pending.request_id=request_id;front_pending.prompt=input;
      if(restoring&&!appending){front_pending.processed=restored.tokens;front_pending.processed.push_back(restored.next_token);}
      else front_pending.processed=input;
      front_pending.processed.insert(front_pending.processed.end(),generated.begin(),generated.end()-1);
      front_pending.next_token=generated.back();
      if(restoring){front_pending.parent.checkpoint_id=restored.checkpoint_id;
        front_pending.parent.manifest_sha256=restored.manifest_sha256;front_pending.parent.present=true;}
      require(!front_pending.processed.empty()&&front_pending.processed.size()<size_t(p.g.context),"postreply descriptor context bound");
      front_pending.present=true;front->reader.complete_request(request_id);
'''


def transform(main, checkpoint):
    main = replace(main, '  Options front_base;', '''  Options front_base;
  struct FrontPending {
    bool present=false;std::string request_id;
    std::vector<int> prompt,processed;int next_token=-1;
    pipeline::CheckpointParent parent;
  } front_pending;''')
    main = replace(main, '      if(!request)break;\n      a=front_base;',
                   '      if(!request)break;\n' + CONTROL + '      a=front_base;')
    # Postreply SAVE must remain possible after a same-generation restore. The
    # inherited native classifier reserves one free position when saving=true.
    main = replace(main,
        'pipeline::checkpoint_precheck(a.checkpoint_restore,a.checkpoint_id,a.inputs,a.tokens,!a.checkpoint_save.empty(),a.tokenizer_identity,a.mini);',
        'pipeline::checkpoint_precheck(a.checkpoint_restore,a.checkpoint_id,a.inputs,a.tokens,a.request_front||!a.checkpoint_save.empty(),a.tokenizer_identity,a.mini);', 2)
    main = replace(main,
        'pipeline::checkpoint_restore(*e,a.checkpoint_restore,a.checkpoint_id,input,a.tokenizer_identity,a.tokens,!a.checkpoint_save.empty());',
        'pipeline::checkpoint_restore(*e,a.checkpoint_restore,a.checkpoint_id,input,a.tokenizer_identity,a.tokens,front||!a.checkpoint_save.empty());')
    main = replace(main, 'ownrt.request-front.v1', 'ownrt.request-front.v2')
    main = replace(main, r'+std::to_string(a.front_max_requests)+",\"model_loads\":1',
                   r'+std::to_string(a.front_max_requests)+",\"max_control_ops\":"+std::to_string(a.front_max_requests)+",\"model_loads\":1')
    boundary = '      front->emit("{\\"event\\":\\"request-complete\\"'
    assert main.count(boundary) == 1
    main = main.replace(boundary, DESCRIPTOR + boundary)
    main = replace(main,
        r'+",\"owner_resident\":true,\"request_quiesced\":true}");',
        r'+",\"owner_resident\":true,\"request_quiesced\":true,\"save_pending\":true,\"pending_request_id\":"+ownrt::quote(request_id)+",\"processed_tokens\":"+std::to_string(front_pending.processed.size())+",\"visible_tokens\":"+std::to_string(front_pending.processed.size()+1)+",\"pending_token\":"+std::to_string(front_pending.next_token)+"}");')
    main = replace(main, 'experimental-warm-owner-v1', 'experimental-postreply-owner-v2')
    main = replace(main,
        r'+std::to_string(front->reader.count())+"}");',
        r'+std::to_string(front->reader.count())+",\"completed_controls\":"+std::to_string(front->reader.control_count())+",\"discarded_pending\":"+(front_pending.present?"true":"false")+",\"pending_request_id\":"+ownrt::quote(front_pending.present?front_pending.request_id:"")+"}");')
    checkpoint = checkpoint.replace('"experimental-warm-front"', '"experimental-postreply-front"')
    checkpoint = checkpoint.replace('"v1.2+p197"', '"v1.2+p198"')
    checkpoint = checkpoint.replace('"packet197-warm-request-front"', '"packet198-postreply-checkpoint"')
    checkpoint = checkpoint.replace('experimental warm request front; no device qualification',
                                    'experimental postreply checkpoint front; no device qualification')
    checkpoint = checkpoint.replace('experimental v1.2+p197', 'experimental v1.2+p198')
    return main, checkpoint


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8,16)) | set(range(24,32))
    assert shutil.disk_usage('/').free >= 27_000_000_000
    pins = json.loads((P / 'parent-pins.json').read_text())
    for name, digest in pins['sources'].items():
        assert sha(ROOT / name) == digest, name
    parent_ready = json.loads((PARENT / 'READY-FOR-DEVICE.json').read_text())
    for leaf in ('main.cpp', 'checkpoint.hpp', 'entry-main.cpp', 'request_front.hpp'):
        name = str((NATIVE / leaf).relative_to(ROOT))
        assert sha(NATIVE / leaf) == parent_ready['files_sha256'][name], name
    original = (NATIVE / 'main.cpp').read_text()
    header = (NATIVE / 'checkpoint.hpp').read_text()
    main_source, checkpoint = transform(original, header)
    output = P / 'build/native'; output.mkdir(parents=True, exist_ok=True)
    (output / 'main.cpp').write_text(main_source)
    (output / 'checkpoint.hpp').write_text(checkpoint)
    for source, leaf in ((NATIVE / 'entry-main.cpp', 'entry-main.cpp'), (P / 'native/request_front.hpp', 'request_front.hpp')):
        shutil.copyfile(source, output / leaf)
    delta = ''.join(difflib.unified_diff(original.splitlines(True), main_source.splitlines(True), fromfile='p197/main.cpp', tofile='p198/main.cpp'))
    delta += ''.join(difflib.unified_diff(header.splitlines(True), checkpoint.splitlines(True), fromfile='p197/checkpoint.hpp', tofile='p198/checkpoint.hpp'))
    delta += ''.join(difflib.unified_diff((NATIVE / 'request_front.hpp').read_text().splitlines(True),
                                        (P / 'native/request_front.hpp').read_text().splitlines(True),
                                        fromfile='p197/request_front.hpp', tofile='p198/request_front.hpp'))
    (P / 'native-postreply.patch').write_text(delta)
    receipt = dict(passed=True, device_executed=False, compiled=False,
                   parent_pins_sha256=sha(P / 'parent-pins.json'), parent_ready_sha256=sha(PARENT / 'READY-FOR-DEVICE.json'),
                   patch_sha256=sha(P / 'native-postreply.patch'),
                   outputs={str((output / leaf).relative_to(P)): sha(output / leaf) for leaf in
                            ('main.cpp', 'checkpoint.hpp', 'entry-main.cpp', 'request_front.hpp')},
                   scope='Source-only postreply SAVE/RELEASE; no compilation or native execution.')
    (P / 'evidence/source-overlay.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(passed=True, compiled=False, device_executed=False)))


if __name__ == '__main__': main()
