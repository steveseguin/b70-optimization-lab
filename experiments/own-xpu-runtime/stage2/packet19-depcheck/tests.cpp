// CPU only. Isolated checker contract tests; no device backend or discovery.
#include "depcheck.hpp"
#include <iostream>
#include <atomic>
namespace ownrt {
std::uint64_t next_handle(){static std::atomic<std::uint64_t> n{1};return n++;}
std::string quote(const std::string& s){return "\""+s+"\"";}
}
namespace {
using depcheck::Checker;using depcheck::Access;using ownrt::Event;
int cases=0,failures=0;
void require(bool b,const char* m){if(!b)throw std::runtime_error(m);}
bool found(const Checker& c,const std::string& s){for(auto& v:c.violations)if(v.find(s)!=std::string::npos)return true;return false;}
Event submit(Checker& c,std::vector<Access> a={},std::vector<Event> d={},int queue=0,int context=7,std::function<void()> fn=[]{}){return c.submit(queue,context,std::move(a),d,std::move(fn));}
void add(Checker& c,int* p,size_t n=sizeof(int),int device=0){c.add(p,n,device,7,"buffer");}
void test(const char* name,std::function<void()> f){++cases;try{f();std::cout<<"PASS "<<name<<'\n';}catch(const std::exception& e){++failures;std::cout<<"FAIL "<<name<<": "<<e.what()<<'\n';}}
}
int main(){
 test("missing RAW includes exact writer",[]{Checker c;int x;add(c,&x);c.site="producer";auto w=submit(c,{{&x,4,false,true}});c.site="consumer";submit(c,{{&x,4,true,false}});require(found(c,"RAW allocation=buffer missing edge from event="+std::to_string(w)+" (producer)"),"RAW absent/wrong edge");});
 test("missing WAW",[]{Checker c;int x;add(c,&x);submit(c,{{&x,4,false,true}});submit(c,{{&x,4,false,true}});require(found(c,"WAW"),"WAW absent");});
 test("retain every outstanding reader for WAR",[]{Checker c;int x=1;add(c,&x);c.host_write(&x,4);c.site="reader-A";auto a=submit(c,{{&x,4,true,false}});c.site="reader-B";auto b=submit(c,{{&x,4,true,false}});c.site="overwrite";submit(c,{{&x,4,false,true}},{b});require(found(c,"WAR allocation=buffer missing edge from event="+std::to_string(a)+" (reader-A)"),"old reader disappeared");});
 test("transitive diamond satisfies both readers",[]{Checker c;int x=1;add(c,&x);c.host_write(&x,4);auto a=submit(c,{{&x,4,true,false}});auto b=submit(c,{{&x,4,true,false}});auto joined=submit(c,{}, {a,b});submit(c,{{&x,4,false,true}},{joined});require(c.violations.empty(),"valid diamond rejected");});
 test("cross queue transitive dependency",[]{Checker c;int x=1;add(c,&x,4,-1);c.host_write(&x,4);auto a=submit(c,{{&x,4,false,true}},{},0);auto b=submit(c,{}, {a},1);submit(c,{{&x,4,true,false}},{b},0);require(c.violations.empty(),"cross-queue chain rejected");});
 test("cross queue missing dependency",[]{Checker c;int x=1;add(c,&x,4,-1);c.host_write(&x,4);submit(c,{{&x,4,false,true}},{},0);submit(c,{{&x,4,true,false}},{},1);require(found(c,"RAW"),"cross-queue missing edge hidden");});
 test("same queue alone grants no implicit edge",[]{Checker c;int x=1;add(c,&x);submit(c,{{&x,4,false,true}});submit(c,{{&x,4,true,false}});require(found(c,"RAW"),"submission order mistaken for edge");});
 test("executed event is not a host fence",[]{Checker c;int x=0;add(c,&x);auto a=submit(c,{{&x,4,false,true}});c.execute_until(a);submit(c,{{&x,4,true,false}});require(found(c,"RAW"),"mere execution hides RAW");});
 test("explicit host fence establishes order",[]{Checker c;int x=0;add(c,&x);auto a=submit(c,{{&x,4,false,true}});c.fence(a);submit(c,{{&x,4,true,false}});require(c.violations.empty(),"fence not respected");});
 test("host fence does not expose unrelated executed work",[]{Checker c;c.randomized=false;int x=0;add(c,&x);submit(c,{{&x,4,false,true}});auto unrelated=submit(c);c.fence(unrelated);submit(c,{{&x,4,true,false}});require(found(c,"RAW"),"fence exposed unrelated event");});
 test("foreign owning device",[]{Checker c;int x=1;add(c,&x);c.host_write(&x,4);submit(c,{{&x,4,true,false}},{},1);require(found(c,"cross-device binding"),"foreign device not rejected");});
 test("foreign context even with matching device",[]{Checker c;int x=1;add(c,&x);c.host_write(&x,4);submit(c,{{&x,4,true,false}},{},0,8);require(found(c,"foreign context"),"foreign context not rejected");});
 test("partial byte poison in device index",[]{Checker c;int x[2];add(c,x,8);c.host_write(x,4);submit(c,{{x+1,4,true,false,true}});require(found(c,"uninitialized INDEX"),"untouched index bytes marked initialized");});
 test("disjoint ranges do not conflict",[]{Checker c;int x[2];add(c,x,8);submit(c,{{x,4,false,true}});submit(c,{{x+1,4,false,true}});require(c.violations.empty(),"disjoint writes conflict");});
 test("partial overlapping ranges conflict",[]{Checker c;int x[3];add(c,x,12);submit(c,{{x,8,false,true}});submit(c,{{x+1,8,false,true}});require(found(c,"WAW"),"overlap missed");});
 test("copy source and destination offset contract",[]{Checker c;int x[2]={1,2},y[2];add(c,x,8);add(c,y,8);c.host_write(x,8);auto copy=submit(c,{{x+1,4,true,false},{y,4,false,true}}, {},0,7,[&]{y[0]=x[1];});c.fence(copy);require(y[0]==2,"copy wrong source offset");submit(c,{{y+1,4,true,false,true}},{copy});require(found(c,"uninitialized INDEX"),"copy initialized uncopied destination bytes");});
 test("host slab overwrite catches pending reader",[]{Checker c;int x=1;add(c,&x,4,-1);c.host_write(&x,4);submit(c,{{&x,4,true,false}});c.host_write(&x,4);require(found(c,"host WAR"),"host slab hazard hidden");});
 test("release pending allocation is diagnosed",[]{Checker c;int x=1;add(c,&x);c.host_write(&x,4);submit(c,{{&x,4,true,false}});bool threw=false;try{c.release(&x);}catch(const std::exception&){threw=true;}require(threw||found(c,"release while pending"),"pending release allowed silently");});
 test("released allocation use diagnosed",[]{Checker c;int x=1;add(c,&x);c.host_write(&x,4);c.release(&x);submit(c,{{&x,4,true,false}});require(found(c,"use-after-release"),"released pointer accepted");});
 test("reused allocation loses old initialization",[]{Checker c;int x=1;add(c,&x);c.host_write(&x,4);c.release(&x);add(c,&x);submit(c,{{&x,4,true,false,true}});require(found(c,"uninitialized INDEX"),"reuse inherited initialized state");});
 test("retire cannot erase merely executed hazard history",[]{Checker c;int x=1;add(c,&x);auto a=submit(c,{{&x,4,false,true}});c.execute_until(a);bool rejected=false;try{c.clear();}catch(const std::exception&){rejected=true;}if(!rejected){submit(c,{{&x,4,true,false}});rejected=found(c,"RAW");}require(rejected,"unfenced event retirement erased writer");});
 test("overlapping allocation registration rejected",[]{Checker c;int x[4];add(c,x,16);bool rejected=false;try{add(c,x+1,4);}catch(const std::exception&){rejected=true;}require(rejected,"partial overlap accepted");});
 test("release pending retains allocation lifetime",[]{Checker c;int x=1;add(c,&x);c.host_write(&x,4);auto e=submit(c,{{&x,4,true,false}});try{c.release(&x);}catch(const std::exception&){}require(c.locate(&x,4)->second.live,"pending release discarded ownership");c.fence(e);c.release(&x);});
 test("double release fails closed",[]{Checker c;int x=1;add(c,&x);c.release(&x);bool rejected=false;try{c.release(&x);}catch(const std::exception&){rejected=true;}require(rejected&&found(c,"double release"),"double release allowed allocator free");});
 test("host write after release fails closed",[]{Checker c;int x=1;add(c,&x);c.release(&x);bool rejected=false;try{c.host_write(&x,4);}catch(const std::exception&){rejected=true;}require(rejected&&found(c,"host use-after-release"),"host writer allowed after free");});
 test("index poison cannot execute arbitrary addressing closure",[]{Checker c;int index;add(c,&index);bool ran=false;submit(c,{{&index,4,true,false,true}}, {},0,7,[&]{ran=true;});bool rejected=false;try{c.sync();}catch(const std::exception&){rejected=true;}require(rejected&&!ran,"uninitialized index closure executed");});
 test("unused foreign compute binding still rejected",[]{depcheck::checker=Checker{};int x=1,y=2;depcheck::checker.add(&x,4,0,0,"local");depcheck::checker.add(&y,4,1,0,"unused-foreign");depcheck::checker.host_write(&x,4);depcheck::card=0;depcheck::accesses={{&x,4,true,false}};depcheck::closure=[](std::span<void*const>){};depcheck::Backend b;ownrt::Operation op;void* bindings[]={&x,&y};b.compute(op,bindings,{});require(found(depcheck::checker,"cross-device binding allocation=unused-foreign"),"unaccessed foreign binding hidden");depcheck::checker.sync();depcheck::checker=Checker{};});
 test("copy propagates partial poison into device index",[]{Checker c;int src[2]={1,2},dst[2];add(c,src,8);add(c,dst,8);c.host_write(src,4);auto e=c.copy_bytes(0,7,dst,src,8,{});submit(c,{{dst,4,true,false,true}},{e});require(!found(c,"uninitialized INDEX"),"initialized prefix poisoned");submit(c,{{dst+1,4,true,false,true}},{e});require(found(c,"uninitialized INDEX"),"copied uninitialized suffix lost poison");});
 test("copy cannot erase poison through a second transfer",[]{Checker c;int src,dst,last;add(c,&src);add(c,&dst);add(c,&last);auto a=c.copy_bytes(0,7,&dst,&src,4,{});auto b=c.copy_bytes(0,7,&last,&dst,4,std::span(&a,1));submit(c,{{&last,4,true,false,true}},{b});require(found(c,"uninitialized INDEX"),"second copy cleared poison");});
 test("read-write alias does not create self hazard",[]{Checker c;int x=1;add(c,&x);c.host_write(&x,4);submit(c,{{&x,4,true,false},{&x,4,false,true}});require(c.violations.empty(),"self WAR fabricated");});
 test("deep ancestors across bitset word boundaries",[]{Checker c;int x=0;add(c,&x);auto e=submit(c,{{&x,4,false,true}});for(int i=0;i<140;++i)e=submit(c,{}, {e},i%2);submit(c,{{&x,4,true,false}},{e});require(c.violations.empty(),"long ancestor chain broken");});
 test("adversarial order exposes absent edge",[]{bool mismatch=false;for(int seed=1;seed<=32;++seed){Checker c;c.random.seed(seed);int x=0,y=0;add(c,&x);add(c,&y);c.host_write(&x,4);c.host_write(&y,4);submit(c,{{&x,4,false,true}}, {},0,7,[&]{x=13;});submit(c,{{&x,4,true,false},{&y,4,false,true}}, {},0,7,[&]{y=x;});c.sync();mismatch|=y!=13;require(c.max_ready==2,"scheduler did not expose two independent submissions");require(found(c,"RAW"),"seed failed sanitizer");}require(mismatch,"scheduler preserved accidental submission order");});
 test("adversarial declared DAG keeps exact results",[]{for(int seed=0;seed<=32;++seed){Checker c;c.randomized=seed!=0;c.random.seed(seed);int x=0,y=0;add(c,&x);add(c,&y);auto a=submit(c,{{&x,4,false,true}}, {},0,7,[&]{x=13;});submit(c,{{&x,4,true,false},{&y,4,false,true}},{a},0,7,[&]{y=x;});c.sync();require(y==13&&c.violations.empty(),"valid DAG changed result");}});
 std::cout<<"RESULT "<<cases-failures<<"/"<<cases<<" passed; device_executed=false\n";return failures?1:0;
}
