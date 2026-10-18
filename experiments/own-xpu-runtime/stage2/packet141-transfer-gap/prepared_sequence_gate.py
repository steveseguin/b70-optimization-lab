"""CPU regression: real Engine/Device/selection/capture, mock device payloads.

Runs the actual probe arm loop, cleanup, request reset and all six bank pairs.
No model payload or device API is used. Address tokens represent device storage;
tiny stand-in readbacks and synthetic clocks are bookkeeping, never quality or
performance evidence. Compile AND execute under the shared compiler turn so no
full-shape metadata read overlaps a protected one-card timing window.
"""
import ast
import gzip
import json
import resource
import subprocess
import sys
from pathlib import Path
from build_engine import P, ROOT, B, sha, save, limits

S = B / 'prepared-sequence-final'
E = P / 'evidence/repair141c'


def generate():
    S.mkdir(exist_ok=True)
    prior = json.loads((P / 'parent-commands.snapshot.json').read_text())
    base = next(r['command'] for r in prior if r['name'] == 'gnu-host-entry-main')
    mirror = Path(next(x[2:] for x in base if x.startswith('-I') and '/checked/' in x))
    source = P / 'compiled-sources/experiments/own-xpu-runtime/stage2/packet136-record-bundle/full_shape.py'
    text = source.read_text()
    code = '\n\n'.join(ast.get_source_segment(text, n) for n in ast.parse(text).body
                       if isinstance(n, ast.FunctionDef) and n.name in ('replace', 'body', 'generate'))
    code = code.replace("mirror=B/'checked'/P.relative_to(ROOT)", 'mirror=Path(' + repr(str(mirror)) + ')')
    code = code.replace("t=(mirror/'main.cpp').read_text()", "t=(B/'cow/main.cpp').read_text()")
    scope = dict(P=P, ROOT=ROOT, B=B, S=S, json=json, Path=Path)
    exec(compile(code, str(source), 'exec'), scope)
    scope['generate']()
    body = scope['body']
    text = (S / 'main.cpp').read_text()
    text = text.replace('#include ' + json.dumps(str(P / 'probe_touch.hpp')),
                        'struct P141Touch final:ownrt::Operation {size_t offset=0,bytes=0;};')
    text = text.replace('#include ' + json.dumps(str(P / 'probe.hpp')), '#include P141_GATE_PROBE')
    text = text.replace(' bool ordered_prefix_complete(ownrt::Event e)override',
        ' ownrt::EventTiming timing(ownrt::Event e)override{return {e*1000,e*1000+100};}\n bool ordered_prefix_complete(ownrt::Event e)override')
    # Only payload work is elided; real launch arguments, generations, ownership,
    # capture, enqueue/finish, event retirement and bank selection remain intact.
    text = body(text, 'void lookup(const flash::Launch &l)', '\n fp32_sources[l.card]=0;\n')
    text = body(text, 'int integer(int c, const std::string &name)', '\n return name=="position"?133:0;\n')
    text = body(text, 'std::vector<uint8_t> readback(int c, Allocation src, size_t n)', r'''
 drain();
 for(const auto& l:p.launches)if(l.op=="routed_gemv"&&!l.weights.empty()&&l.weights[0].find("ffn_down_exps")!=std::string::npos&&buffers[c].at(l.inputs.at(1)).id==src&&n==120){
  std::ifstream f(fs::path(P141_PACKET)/"routes.bin",std::ios::binary);f.seekg(std::stoi(l.label.substr(4))*120);
  std::vector<uint8_t> r(120);f.read(reinterpret_cast<char*>(r.data()),120);require(bool(f),"mock route fixture");return r;
 }
 return std::vector<uint8_t>(std::min(n,size_t(4)),0);
''')
    (S / 'main.cpp').write_text(text)
    old = json.loads(gzip.decompress((E / 'prior-metadata.json.gz').read_bytes()))['probe.hpp']
    for name, probe in [('old', old), ('fixed', (P / 'probe.hpp').read_text())]:
        assert probe.count('#ifndef OWN_RT_HOST_ONLY') == 1
        (S / (name + '-probe.hpp')).write_text(probe.replace('#ifndef OWN_RT_HOST_ONLY', '#if 1 // CPU bookkeeping gate only'))
    entry = r'''#include <cxxabi.h>
#define main packet141_unexecuted_model_entry
#include "main.cpp"
#undef main
static std::string stage="startup";
static auto signatures(Engine& e){
 std::map<int,std::vector<std::vector<unsigned char>>> out;
 auto add=[&](int key,const auto& sites){for(const auto& site:sites)for(const auto& cmd:site.commands){
  require(!cmd.argument_bytes.empty(),"missing real prepared binding bytes");
  out[key].push_back(cmd.argument_bytes);
  require(cmd.generation==e.dev(0).generation(),"stale cached generation in signature");
 }};
 add(e.active_bank*3+e.spare_bank,e.issue_sites);
 for(int k=0;k<9;++k)if(k!=e.active_bank*3+e.spare_bank&&e.bank_cache[k].ready)add(k,e.bank_cache[k].sites);
 require(out.size()==6,"six prepared bank pairs");return out;
}
int main(int argc,char**argv){std::unique_ptr<Engine> e;try{
 require(argc==4,"selection hash output");Options a;a.context=4096;a.cards=1;a.card=0;a.rank=0;a.draft_rank=1;a.target_split=0;a.mtp=true;a.memory="resident";a.gemv="r5";a.nongemv="parallel";a.selection=argv[1];a.selection_sha256=argv[2];a.output=argv[3];fs::create_directories(a.output);
 a.plan=fs::path(P141_PACKET)/"inputs/incident-retrospective/plan.tsv";
 packet26::dispatch.load((fs::path(P141_PACKET)/"dispatch-speed6.json").string());Weights w(a);auto p=pipeline::split(plan(w,a),0,false,1,0);
 e=std::make_unique<Engine>(w,a,p);e->initialize();std::unique_ptr<p105::Runtime> head;if(e->split_head())head=std::make_unique<p105::Runtime>(*e);
 pipeline::banks(*e);
 // Start away from pair 01/parity 0, with only this pair in the 160 bucket.
 // This catches a repair which resets bank selection or flattens all extents.
 e->rotate_spare_bank();e->swap_state_banks();e->admit_position(133);auto before=signatures(*e);
 const auto generation=e->dev(0).generation();const int active=e->active_bank,spare=e->spare_bank,parity=e->bank_parity;
 std::vector<std::vector<unsigned char>> head_before;
 require(bool(head)&&!head->suffix_commands.empty(),"selected split-head suffix missing");
 for(const auto& cmd:head->suffix_commands)head_before.push_back(cmd.argument_bytes);
 stage="full-arm-sequence";p141_run_probe(*e,head.get(),10015,133);
 require(e->dev(0).generation()!=generation,"probe cleanup must invalidate owner");
 require(e->active_bank==active&&e->spare_bank==spare&&e->bank_parity==parity,"probe changed bank selection");
 stage="post-probe-reset";pipeline::Candidate candidate;auto meta=a.output/"reset-meta.txt";auto post=a.output/"post-probe";
 save(meta,post.string()+"\n\n");pipeline::request_reset(*e,candidate,nullptr,meta,0);
 stage="post-probe-enqueue";
 // The old probe fails at this exact normal model continuation, after all arms.
 for(size_t i=0;i<e->p.launches.size();++i)if(!e->issue_sites[i].commands.empty()){e->enqueue(e->p.launches[i],e->logical);break;}e->drain();
 require(signatures(*e)==before,"reprepare changed real prepared binding bytes");
 stage="post-probe-head-service";
 std::vector<std::vector<unsigned char>> head_after;
 for(const auto& cmd:head->suffix_commands){require(cmd.generation==e->dev(0).generation(),"stale split-head generation");head_after.push_back(cmd.argument_bytes);}
 require(head_before==head_after,"split-head argument bytes changed");
 p105::Mailbox box{};box.position=0;box.fixture=1;p105::publish(box.request,1);
 head->service(box,1,0,1,[]{});require(p105::load(box.reply)==1,"split-head continuation reply");
 stage="all-bank-continuations";size_t halves=0;
 for(int i=0;i<6;++i){
  for(const auto& l:e->p.launches)e->enqueue(l,e->logical);e->drain();++halves;
  if(i%2==0)e->rotate_spare_bank();else e->swap_state_banks();
 }
 require(halves==6,"all bank continuations");
 save(a.output/"result.json","{\"passed\":true,\"device_executed\":false,\"model_payload_read\":false,\"blocks\":4,\"arms\":16,\"controls\":4,\"post_reset_bank_pairs\":6,\"split_head_service\":true,\"argument_blocks_unchanged\":true}");
 e->shutdown();e.reset();std::cout<<"prepared sequence PASS\n";return 0;
 }catch(const std::exception&x){std::cerr<<stage<<": "<<x.what()<<'\n';if(e){try{e->shutdown();}catch(...){}e.reset();}return 1;}}
'''
    (S / 'entry.cpp').write_text(entry)
    return prior, base, source


def main():
    limits()
    prior, base, generator = generate()
    base = base[:base.index('-o')]
    base = [x for x in base if not x.startswith('-O')] + ['-O0', '-I' + str(P)]
    commands, runs = [], []
    for variant in ('old', 'fixed'):
        obj, binary = S / (variant + '.o'), S / (variant + '-gate')
        compile_cmd = [*base, '-DP141_GATE_PROBE=' + json.dumps(str(S / (variant + '-probe.hpp'))),
                       '-c', str(S / 'entry.cpp'), '-o', str(obj)]
        link = list(next(r['command'] for r in prior if r['name'] == 'gnu-host-link'))
        link = [x for x in link if not x.endswith('own-rt-iq3-entry.cpp.o')]
        link = [str(obj) if x.endswith('/entry-main.o') else x for x in link]
        link[link.index('-o') + 1] = str(binary)
        for name, cmd in [('compile', compile_cmd), ('link', link)]:
            commands.append(cmd)
            with (E / (variant + '-' + name + '.log')).open('w') as log:
                subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                               check=True, timeout=600)
        output = S / (variant + '-run')
        assert not output.exists(), 'retain each gate run; use a fresh build directory for a rerun'
        cmd = [str(binary), str(P / 'selection.json'), sha(P / 'selection.json'), str(output)]
        cp = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=180)
        (E / (variant + '-run.log')).write_text(cp.stdout + cp.stderr)
        assert cp.returncode == (1 if variant == 'old' else 0), cp.stderr
        if variant == 'old':
            assert 'post-probe-enqueue: stale prepared launch' in cp.stderr, cp.stderr
        result = json.loads((output / 'p141-complete.json').read_text())
        assert result['passed']
        for name, count in [('p141-halves.jsonl', 16), ('p141-controls.jsonl', 4)]:
            assert len((output / name).read_text().splitlines()) == count
        row = dict(variant=variant, returncode=cp.returncode, binary_sha256=sha(binary),
                   completed_arms=16, completed_controls=4, command=cmd)
        if variant == 'fixed': row['result'] = json.loads((output / 'result.json').read_text())
        runs.append(row)
        print(variant, 'expected result PASS', flush=True)
    sources = {str(f.relative_to(ROOT)): sha(f) for f in [Path(__file__).resolve(), generator,
        P / 'probe.hpp', P / 'probe_lifetime.hpp', P / 'probe_dispatch.hpp', P / 'selection.json', B / 'cow/main.cpp', B / 'cow/p105_runtime.hpp',
        B / 'cow/rank.hpp', B / 'cow/request_reset.hpp', *sorted(S.glob('*.hpp')), S / 'main.cpp', S / 'mtp.hpp', S / 'entry.cpp']}
    save(E / 'prepared-sequence.json', dict(passed=True, device_executed=False, model_payload_read=False,
         mock_payloads_and_clocks=True, old_code_rejected=True, sources=sources, runs=runs, commands=commands,
         max_child_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    sys.path.insert(0, str(P.parents[1] / 'ops'))
    from compile_turn import turn
    with turn(): main()
