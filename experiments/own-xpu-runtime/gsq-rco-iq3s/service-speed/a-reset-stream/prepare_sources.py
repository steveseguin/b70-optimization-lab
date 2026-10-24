"""Materialize this source-only packet; never builds or runs native code."""
from pathlib import Path
import difflib
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
BASE = ROOT / 'experiments/own-xpu-runtime/gsq-rco-iq3s/recurrent-f32/build/source-v2'
NAMES = ('entry.cpp', 'main.cpp', 'rank.hpp', 'request_reset.hpp',
         'native_controller.hpp', 'v3_boundary.hpp', 'v3_controller.hpp')
paths = {}
for name in NAMES:
    matches = list(BASE.rglob(name))
    assert len(matches) == 1, (name, matches)
    paths[name] = matches[0]
original = {name: path.read_text() for name, path in paths.items()}
changed = dict(original)

def replace(name, old, new):
    assert changed[name].count(old) == 1, (name, old)
    changed[name] = changed[name].replace(old, new)

replace('main.cpp', '  RetainSteps retain_steps;', '''  // Evidence/notification only. Defaults preserve the executed engine behavior.
  bool reset_dump=true,finish_dump=true,token_stream=false;
  RetainSteps retain_steps;''')
replace('main.cpp', '    else if (k == "--retain-steps")', '''    else if (k == "--reset-dump" || k == "--finish-dump") {
      auto v=value();require(v=="all"||v=="none","dump mode must be all or none");
      (k=="--reset-dump"?a.reset_dump:a.finish_dump)=v=="all";
    }
    else if (k == "--token-stream") {
      auto v=value();require(v=="none"||v=="jsonl","token stream must be none or jsonl");
      a.token_stream=v=="jsonl";
    }
    else if (k == "--retain-steps")''')
replace('request_reset.hpp', ' // Retain the complete completed state before resetting, including warm-up.\n state_dump', ' // Keep all boundary/drain/reset actions; only optional evidence readbacks disappear.\n if(e.a.reset_dump){state_dump')
replace('request_reset.hpp', 'provider->dump_all_state(e.a.output/"draft-final-state");', 'provider->dump_all_state(e.a.output/"draft-final-state");}')
replace('rank.hpp', 'if(provider)provider->dump_all_state(engine->a.output/"draft-final-state");break;', 'if(provider&&a.finish_dump)provider->dump_all_state(engine->a.output/"draft-final-state");break;')

stream = r'''// Rank-0-only append stream. No shared-map ABI change, device copy or fsync.
// One fresh file per native request. A stale path is an error, never truncated.
class ConfirmedStream {
  int fd_=-1;
  void line(const std::string& text) {
    size_t done=0;
    while(done<text.size()) {
      auto n=::write(fd_,text.data()+done,text.size()-done);
      if(n<0&&errno==EINTR)continue;
      require(n>0,"confirmed token stream write");done+=size_t(n);
    }
  }
public:
  ConfirmedStream()=default;
  ConfirmedStream(const ConfirmedStream&)=delete;
  ConfirmedStream& operator=(const ConfirmedStream&)=delete;
  ~ConfirmedStream(){if(fd_>=0)::close(fd_);}
  void begin(const fs::path& path,int request_sequence,int count,int vocab) {
    require(fd_<0,"confirmed token stream already open");
    fd_=::open(path.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600);
    require(fd_>=0,"confirmed token stream create");
    line("{\"type\":\"begin\",\"schema\":\"sc117.confirmed-tokens.v1\",\"request_sequence\":"+
         std::to_string(request_sequence)+",\"limit\":"+std::to_string(count)+
         ",\"vocab\":"+std::to_string(vocab)+"}\n");
  }
  void token(size_t index,int token,double target_completed) {
    std::ostringstream out;out.precision(17);
    out<<"{\"type\":\"token\",\"index\":"<<index<<",\"token_id\":"<<token
       <<",\"target_completed_monotonic\":"<<target_completed<<"}\n";
    line(out.str()); // write(2) makes a full line visible; no userspace buffering.
  }
  void end(size_t count) {
    line("{\"type\":\"end\",\"count\":"+std::to_string(count)+"}\n");
    int fd=fd_;fd_=-1;require(::close(fd)==0,"confirmed token stream close");
  }
};
using EmitConfirmed=std::function<void(size_t,int,double)>;
'''
replace('native_controller.hpp', 'inline Result run(Backend& b,const Config& c){', stream+'inline Result run(Backend& b,const Config& c,const EmitConfirmed& emit={}){')
replace('v3_controller.hpp', 'inline Result run_v3(Backend& b,const Config& c){', 'inline Result run_v3(Backend& b,const Config& c,const EmitConfirmed& emit={}){')
for name in ('native_controller.hpp', 'v3_controller.hpp'):
    replace(name, 'b.call(0,rollback);}break;}', 'b.call(0,rollback);}if(emit)emit(out.tokens.size(),out.tokens.back(),out.rows.back().stamp);break;}')
    replace(name, '  if(!more)break;', '  if(!more){if(emit)emit(out.tokens.size(),out.tokens.back(),out.rows.back().stamp);break;}')
    replace(name, '  if(c.dumps)b.call(0,dump,0,p+1);', '''   // Both ranks have accepted, or the miss has rolled back and been corrected.
   // Publish only the target output, never the next-token draft or speculative half.
   if(fixture(p)>0&&emit)emit(out.tokens.size(),out.tokens.back(),out.rows.back().stamp);
   if(c.dumps)b.call(0,dump,0,p+1);''')
replace('rank.hpp', '      auto result=engine->v3_active?native38::run_v3(backend,cfg):native38::run(backend,cfg); // packet186', '''       native38::ConfirmedStream stream;native38::EmitConfirmed emit;
       if(a.token_stream){
        stream.begin(engine->a.output/"confirmed-tokens.jsonl",r.sequence,cfg.count,cfg.vocab);
        emit=[&](size_t index,int token,double stamp){stream.token(index,token,stamp);};
       }
       auto result=engine->v3_active?native38::run_v3(backend,cfg,emit):native38::run(backend,cfg,emit); // packet186''')
replace('rank.hpp', '      save(a.shared.parent_path()/"native-result.json",native38::json(result,backend,cfg));', '''      save(a.shared.parent_path()/"native-result.json",native38::json(result,backend,cfg));
       // End seals the list, not overall request success: normal rank replies remain required.
       if(a.token_stream)stream.end(result.tokens.size());''')

# Absolute includes must bind the copied ancestors to the changed descendants.
# Unchanged dependencies and historical #line directives retain their identities.
destinations = {p: HERE/'source'/p.relative_to(ROOT) for p in paths.values()}
for name, text in changed.items():
    for old, new in destinations.items():
        text = text.replace('#include "'+str(old)+'"', '#include "'+str(new)+'"')
    changed[name] = text

(HERE/'patches').mkdir(exist_ok=True)
manifest = []
for number, name in enumerate(NAMES, 1):
    path = paths[name]; dest = destinations[path]; relative = path.relative_to(ROOT)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(changed[name])
    patch = ''.join(difflib.unified_diff(original[name].splitlines(True), changed[name].splitlines(True),
                                       fromfile='a/'+str(relative), tofile='b/'+str(relative)))
    assert patch
    (HERE/'patches'/f'{number:02d}-{name}.patch').write_text(patch)
    manifest.append(dict(original=str(relative), copy=str(dest.relative_to(HERE)),
                         original_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         patched_sha256=hashlib.sha256(dest.read_bytes()).hexdigest()))
(HERE/'source-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
print(f'Prepared {len(manifest)} copied sources and unified diffs; no build executed.')
