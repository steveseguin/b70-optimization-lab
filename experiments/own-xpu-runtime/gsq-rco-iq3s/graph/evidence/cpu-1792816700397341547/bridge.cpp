#include "build/private/packet3/step/plan.hpp"
#include <iomanip>
#include <iostream>
using namespace flash;
static void strings(const std::vector<std::string> &v) {
  std::cout << '[';
  bool first = true;
  for (auto &s : v) {
    if (!first)
      std::cout << ',';
    first = false;
    std::cout << std::quoted(s);
  }
  std::cout << ']';
}
static void record(const Plan &p) {
  std::uint64_t bytes = 0, reads = 0, writes = 0;
  std::cout << "{\"launches\":[";
  bool first = true;
  for (auto &l : p.launches) {
    if (!first)
      std::cout << ',';
    first = false;
    std::cout << "{\"op\":" << std::quoted(l.op)
              << ",\"label\":" << std::quoted(l.label) << ",\"card\":" << l.card
              << ",\"parameter\":" << l.parameter
              << ",\"source_card\":" << l.source_card << ",\"shape\":[";
    for (size_t i = 0; i < l.shape.size(); ++i) {
      if (i)
        std::cout << ',';
      std::cout << l.shape[i];
    }
    std::cout << "],\"inputs\":";
    strings(l.inputs);
    std::cout << ",\"outputs\":";
    strings(l.outputs);
    std::cout << ",\"weights\":";
    strings(l.weights);
    std::cout << ",\"weight_bytes\":" << l.weight_bytes
              << ",\"read_bytes\":" << l.read_bytes
              << ",\"write_bytes\":" << l.write_bytes << '}';
    bytes += l.weight_bytes;
    reads += l.read_bytes;
    writes += l.write_bytes;
  }
  std::cout << "],\"launch_count\":" << p.launches.size()
            << ",\"weight_bytes\":" << bytes
            << ",\"buffer_read_extent_bytes\":" << reads
            << ",\"buffer_write_extent_bytes\":" << writes << ",\"buffers\":[";
  first = true;
  for (const auto &b : p.buffers) {
    if (!first)
      std::cout << ',';
    first = false;
    std::cout << "{\"name\":" << std::quoted(b.name) << ",\"card\":" << b.card
              << ",\"scalar\":" << int(b.type)
              << ",\"element_bytes\":" << scalar_bytes(b.type)
              << ",\"shape\":[";
    for (size_t i = 0; i < b.shape.size(); ++i) {
      if (i)
        std::cout << ',';
      std::cout << b.shape[i];
    }
    std::cout << "]}";
  }
  std::cout << "]}\n";
}

static Plan admitted_plan(const Directory& d,const Directory& expected,int context){
 if(d.size()!=expected.size())throw std::invalid_argument("directory coverage differs");
 for(const auto& [name,t]:d){const auto& e=expected.at(name);
  if(t.grid!=e.grid||t.shape!=e.shape||t.bytes!=e.bytes||t.component!=e.component)
   throw std::invalid_argument("frozen tensor identity differs: "+name);
  validate_descriptor(t);
 }
 auto original=model_plan(d); // actual 48-layer generator, geometry and all weights
 if(context==original.g.context)return original;
 if(context<1||context>32768)throw std::invalid_argument("context outside graph range");
 auto g=original.g;g.context=context;std::vector<bool> full;
 for(int i=0;i<48;++i)full.push_back(d.count("blk."+std::to_string(i)+".attn_q.weight"));
 return Builder(g,&d).build(full);
}
int main(int argc,char**argv){try{
 if(argc!=4)throw std::invalid_argument("directory expected-directory context required");
 std::ifstream input(argv[1]),expected_input(argv[2]);
 auto d=read_directory(input),expected=read_directory(expected_input);
 size_t used=0;int context=std::stoi(argv[3],&used);if(used!=std::string(argv[3]).size())throw std::invalid_argument("context syntax");
 record(admitted_plan(d,expected,context));return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
