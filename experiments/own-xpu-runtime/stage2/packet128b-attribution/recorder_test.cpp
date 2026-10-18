#include "attribution.hpp"
#include <cassert>
int main(){
 p57::Recorder r;r.enabled=true;unsigned long long id=1;
 for(int fixture=0;fixture<=65;++fixture){
  r.current={"blk.0.gdn",fixture,100+fixture,false};
  r.record(id++);
 }
 assert(r.events.size()==8);
 for(const auto& [event,site]:r.events)assert(site.fixture>=9&&site.fixture<=16);
 r.events.clear();r.enabled=false;r.current={"blk.47.ffn.combine",9,109,true};r.record(id++);assert(r.events.empty());
 r.enabled=true;
 for(int layer=0;layer<48;++layer){r.current={"blk."+std::to_string(layer)+".gdn",16,116,false};r.record(id++);}
 assert(r.events.size()==48);
 r.current={"transfer.readback",16,116,false,"copy-auto"};r.record(id++);
 assert(std::string(r.events.rbegin()->second.queue)=="copy-auto");
}
