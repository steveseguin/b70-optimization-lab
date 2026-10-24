"""P213-derived disabled Engine with an independent frozen-table publisher mode."""
from pathlib import Path
import hashlib,json
P=Path(__file__).resolve().parent;ROOT=P.parents[3];PARENT=P.parent/'packet213-production-prefill-control'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def once(text,old,new):
 assert text.count(old)==1,(old[:120],text.count(old))
 return text.replace(old,new)
def generate():
 pins=json.loads((P/'parent-pins.json').read_text())
 for name,want in pins.items():assert sha(ROOT/name)==want,name
 parent=PARENT/'build/native';main=(parent/'main.cpp').read_text()
 main=once(main,'struct Options {','struct Options {\n  std::string p214_publication;')
 main=once(main,' require(a.p213_prefill&&',' require((a.p214_publication=="copies"||a.p214_publication=="kernel")&&a.p213_prefill&&')
 main=once(main,'    if(k=="--p213-future-prefill")','    if(k=="--p214-publication")a.p214_publication=value();\n    else if(k=="--p213-future-prefill")')
 main=once(main,'class Engine final : public flash::Backend {','#include "'+str(P/'publication.hpp')+'"\nclass Engine final : public flash::Backend {')
 main=once(main,'  std::unique_ptr<p213::CacheInterval> prefill_interval;','  std::unique_ptr<p213::CacheInterval> prefill_interval;\n  ownrt::Backend* publication_backend=nullptr;\n  std::unique_ptr<p214::Publisher> table_publisher;')
 factory='    devices.push_back(std::make_unique<ownrt::Device>(ownrt::make_sycl_device(a.card,profile_events||a.mtp||!a.draft_capture.empty())));'
 main=once(main,factory,'''    auto owned_publication_backend=ownrt::make_sycl_device(a.card,profile_events||a.mtp||!a.draft_capture.empty());
    publication_backend=owned_publication_backend.get();
    devices.push_back(std::make_unique<ownrt::Device>(std::move(owned_publication_backend)));''')
 # The same factory object remains exclusively Device-owned. The Publisher only
 # borrows it for positive full synchronization before terminal cleanup.
 start=main.index('  void publish_cache_table(');end=main.index('  void initialize_cache()',start)
 main=main[:start]+'''  void publish_cache_table(const std::vector<p58::Entry>& table) {
    require(!prefill_interval||!prefill_interval->running(),"p214 publication while readers");
    require(table_publisher&&!overlapping()&&!allocation_probe&&!dev(0).capturing(),"p214 immediate serial-policy publisher");
    const auto begin=std::chrono::steady_clock::now();
    auto result=table_publisher->publish(table,a.p214_publication=="kernel"?p214::PublicationMode::kernel:p214::PublicationMode::copies);
    tail=result.last;
    // Complete the helper-owned event IDs before Engine retirement. A failed
    // submit has no success return and is settled only in terminal shutdown.
    table_publisher->complete(std::chrono::seconds(a.wait_seconds));
    drain();publication_uploads+=result.operations;publication_bytes+=result.bytes;publication_host_ms+=ms(begin);
    std::ofstream proof(a.output/"p214-publication.jsonl",std::ios::app);require(bool(proof),"p214 publication evidence open");
    proof<<"{\\"mode\\":"<<ownrt::quote(a.p214_publication)<<",\\"tables\\":144,\\"entries_per_table\\":512,\\"logical_operations\\":"<<result.operations<<",\\"bytes\\":"<<result.bytes<<",\\"completed\\":true}\\n";proof.flush();require(bool(proof),"p214 publication evidence write");
  }
'''+main[end:]
 needle='    publish_cache_table(expert_cache->table());\n    for(const auto& l:p.launches)'
 main=once(main,needle,'''    require(publication_backend,"p214 exact owned backend missing");
    std::array<p214::TableBinding,144> publication_bindings{};size_t publication_index=0;
    for(const auto&[name,b]:expert_banks){require(publication_index<144,"p214 table census overflow");publication_bindings[publication_index++]={b.table,unsigned(b.layer),unsigned(b.projection)};}
    require(publication_index==144,"p214 exact table census");
    table_publisher=std::make_unique<p214::Publisher>(dev(0),*publication_backend,table_staging,publication_device,publication_bindings);
    publish_cache_table(expert_cache->table());
    for(const auto& l:p.launches)''')
 # Fail closed at every Engine path that can touch/release storage or start
 # further work. Raw Arena cannot know a failed pre-ledger native submission.
 for signature in ('  flash::Event issue_site(size_t index,flash::Event dep) {','  void prepare_commands() {','  void guard() {','  void upload(int c, Allocation dst, size_t offset, const void *src, size_t n) {','  void release(int c,Allocation id) {','  void fill_cache(const std::vector<uint32_t>& routes) {','  void cache_capacity(const std::string& cap) {'):
  main=once(main,signature,signature+'\n    require(!table_publisher||table_publisher->ready(),"p214 publisher owns storage/intake");')
 main=once(main,'static void p58_reset_request(Engine& e,const fs::path& destination) {','static void p58_reset_request(Engine& e,const fs::path& destination) {\n  require(!e.table_publisher||e.table_publisher->ready(),"p214 reset during publication ownership");')
 main=once(main,'  std::vector<std::string> shutdown() {','''  std::vector<std::string> shutdown() {
    if(table_publisher){bool safe=false;try{
      // Pending/uncertain publication must be settled before Engine can retire
      // its event IDs. Ordinary later work is drained first when no such work
      // is owned by this helper.
      if(!table_publisher->pending()&&!table_publisher->uncertain())drain();
      safe=table_publisher->close(std::chrono::seconds(a.wait_seconds))&&table_publisher->release_allowed();
    }catch(...){safe=false;}
    if(!safe){try{save(a.output/"p214-publication-retained.json","{\\"retained\\":true,\\"full_backend_sync_proved\\":false}\\n");}catch(...){}
      ownrt::hold_for_supervisor(); // never reach outer catch's e.reset
    }
    table_publisher.reset();publication_backend=nullptr;
    }''')
 checkpoint=(parent/'checkpoint.hpp').read_text().replace('v1.2+p213','v1.2+p214')
 entry='''#define main p214_model_body
#include "main.cpp"
#undef main
extern "C" int p214_future_entry(int argc,char**argv){return p214_model_body(argc,argv);}
int main(int,char**){std::cerr<<"P214 compile-only: all executable invocations disabled; native qualification pending\\n";return 64;}
'''
 out=P/'build/native';out.mkdir(parents=True,exist_ok=True)
 files={'main.cpp':main,'checkpoint.hpp':checkpoint,'request_front.hpp':(parent/'request_front.hpp').read_text(),'entry-main.cpp':entry}
 for name,data in files.items():(out/name).write_text(data)
 receipt={'schema':'packet214.source-overlay.v1','parent_source_sha256':pins,'source_sha256':{str((P/n).relative_to(ROOT)):sha(P/n) for n in ('source_overlay.py','publication.hpp','parent-pins.json')},'outputs':{str((out/n).relative_to(P)):sha(out/n) for n in files},'entry_disabled':True,'native_execution_allowed':False}
 (P/'evidence/source-overlay.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n');return receipt
if __name__=='__main__':print(json.dumps(generate(),indent=2))
