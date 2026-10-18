"""Generate a new entry from retained checked 58j source; parents are read-only."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
BASE=P.parent/'packet58j-onecard-port'


def once(text, old, new):
    if text.count(old)!=1:
        raise ValueError('native integration boundary: '+old[:100])
    return text.replace(old,new,1)


def generate():
    out=P/'build/native';out.mkdir(parents=True,exist_ok=True)
    text=(P/'sources/main.cpp').read_text()
    text=once(text,'  fs::path inputs, output, model, plan, auth, oracle, suite_inputs;',
              '  fs::path inputs, output, model, plan, auth, oracle, suite_inputs, bracket_inputs;')
    text=once(text,'    else if (k == "--suite-inputs")',
              '    else if (k == "--bracket-inputs") a.bracket_inputs=value();\n    else if (k == "--suite-inputs")')
    text=once(text,'  void guard() {','#include '+json.dumps(str(P/'native/engine_bracket.hpp'))+'\n  void guard() {')
    text=once(text,'  void upload(int c, Allocation dst, size_t offset, const void *src, size_t n) {',
              '  void upload(int c, Allocation dst, size_t offset, const void *src, size_t n) {\n'
              '    require(!bracket_weights_locked||dev(c).arena.row(dst).category!=Category::weights,"bracket immutable weight write refused");')
    text=once(text,'int main(int argc, char **argv) {',
              '#include '+json.dumps(str(P/'native/bracket_table.hpp'))+'''\nint main(int argc, char **argv) {
#ifdef OWN_RT_HOST_ONLY
  if(argc>2&&std::string(argv[1])=="--p58r-parse-test") {
    try {
      auto parsed=parse(argc-1,argv+1);auto views=bracket_table(parsed);
      require(views.size()==5,"parser bracket coverage");
      require(!fs::exists(parsed.output),"fresh parser output required");fs::create_directories(parsed.output);
      save(parsed.output/"parser.json","{\\"passed\\":true,\\"device_executed\\":false,\\"model_reads\\":false,\\"views\\":5}\\n");return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<"\\n";return 1;}
  }
#endif
''')
    text=once(text,'    const auto cold_load_start=std::chrono::steady_clock::now();',
              '    const auto bracket_views=bracket_table(a);\n    const auto cold_load_start=std::chrono::steady_clock::now();')
    text=once(text,'    std::vector<std::pair<std::string,fs::path>> requests;',
              '    std::map<std::string,std::vector<int>> expected_tokens;\n    std::vector<std::pair<std::string,fs::path>> requests;')
    text=once(text,'        require(fs::path(path).is_absolute(),"suite input path absolute");requests.push_back({id,path});',
              '''        require(fs::path(path).is_absolute(),"suite input path absolute");requests.push_back({id,path});
        if(!a.bracket_inputs.empty()) {
          std::string oracle_path;require(bool(f>>oracle_path)&&fs::path(oracle_path).is_absolute(),"bracket oracle path");
          std::ifstream oracle(oracle_path);int token;std::vector<int> tokens;
          while(oracle>>token){require(token>=0&&token<p.g.vocab,"oracle token range");tokens.push_back(token);}
          require(oracle.eof()&&!tokens.empty()&&tokens.size()<=size_t(a.tokens),"bounded oracle tokens");
          expected_tokens[id]=std::move(tokens);
        }''')
    text=once(text,'    }else requests.push_back({"",a.inputs});',
              '      require(a.bracket_inputs.empty()||a.mini||requests.size()==12,"twelve bracket prompts required");\n    }else requests.push_back({"",a.inputs});')
    text=once(text,'    for(const auto& [request_id,input_path]:requests) {',
              '''    e->bracket_weights_locked=!a.bracket_inputs.empty();
    const auto loaded_arena=e->bracket_arena_hash(),loaded_weights=e->bracket_arena_hash(true);
    if(!a.bracket_inputs.empty())save(root_output/"loaded-arena-descriptors.txt",e->bracket_arena_descriptors());
    for(const auto& view:bracket_views) {
    const auto view_output=view.label.empty()?root_output:root_output/view.label;
    if(!view.label.empty()) {
      fs::create_directories(view_output);e->bracket_select(view.selection,view.digest);
      require(loaded_arena==e->bracket_arena_hash()&&loaded_weights==e->bracket_arena_hash(true),"bracket loaded identity changed");
      save(view_output/"boundary.json","{\\"passed\\":true,\\"selection_sha256\\":"+ownrt::quote(view.digest)+
        ",\\"arena_descriptors_sha256\\":"+ownrt::quote(loaded_arena)+",\\"weight_descriptors_sha256\\":"+ownrt::quote(loaded_weights)+
        ",\\"allocation_ids_preserved\\":true,\\"weight_uploads_during_switch\\":0,\\"cache_fill_bytes_total\\":"+std::to_string(e->cache_fill_bytes)+
        ",\\"context_extent\\":32,\\"model_loads\\":1}\\n");
    }
    for(const auto& [request_id,input_path]:requests) {''')
    text=once(text,'    output=request_id.empty()?root_output:root_output/request_id;',
              '    output=request_id.empty()?view_output:view_output/request_id;')
    text=once(text,'      generated.push_back(next);',
              '''      if(!a.bracket_inputs.empty()) {
        const auto& expected=expected_tokens.at(request_id);
        require(generated.size()<expected.size()&&next==expected[generated.size()],"packet49 oracle token mismatch: "+view.label+"/"+request_id+" token "+std::to_string(generated.size()));
      }
      generated.push_back(next);''')
    text=once(text,'    decode_ms=Engine::ms(decode_start);',
              '    require(a.bracket_inputs.empty()||generated==expected_tokens.at(request_id),"packet49 completion length mismatch");\n    decode_ms=Engine::ms(decode_start);')
    text=once(text,'    output=root_output;', '    } // bracket views; weights and owner stay resident\n    output=root_output;')
    text=once(text,'  } catch (const std::exception &ex) {\n    error = ex.what();',
              '  } catch (const std::exception &ex) {\n    if(!a.bracket_inputs.empty()&&!a.output.empty())output=a.output;\n    error = ex.what();')
    # Full-size mock calls the SAME switch for every view on one allocation set.
    full=(P/'sources/fullshape_submit_test.hpp').read_text()
    full=once(full,'    size_t commands=0;', '''    const auto arena=engine.bracket_arena_hash();
    for(const auto* name:{"tile16","route-fast","rec-both-plus","route-rec","tile16"}) {
      auto path=fs::path(P58R_SELECTIONS)/(std::string(name)+".json");
      std::ifstream f(path,std::ios::binary);std::vector<uint8_t> raw((std::istreambuf_iterator<char>(f)),{});
      // FullShapeMock.copy intentionally does no transfer. Its error readback
      // must therefore explicitly represent the clean zero device-error word.
      std::memset(engine.dev(0).arena.row(engine.slab[0]).pointer,0,4);
      engine.bracket_select(path,hash(raw));require(arena==engine.bracket_arena_hash(),"fullshape switch allocations changed");
      // Exercise the selected view at both startup and maximum context, then
      // let the next real switch reset it from 4096 back to 32.
      engine.context_extent=4096;engine.prepared.clear();engine.alternate_prepared.clear();
      engine.issue_sites.clear();engine.matrices.clear();engine.prepare_plan();engine.prepare_commands();
      require(arena==engine.bracket_arena_hash(),"full-context view allocations changed");
    }
    size_t commands=0;''')
    (out/'fullshape_submit_test.hpp').write_text('#define P58R_SELECTIONS '+json.dumps(str(P/'selections'))+'\n'+full)
    old=next(line for line in text.splitlines() if line.startswith('#include ') and line.endswith('/fullshape_submit_test.hpp"'))
    text=once(text,old,'#include '+json.dumps(str(out/'fullshape_submit_test.hpp')))
    (out/'main.cpp').write_text(text)
    (out/'entry-main.cpp').write_text('#define main packet26_model_entry\n#include "main.cpp"\n#undef main\n')
    return out

if __name__=='__main__':generate()
