// Exercise actual production/candidate submitters and admission, no engine run.
#include "p49d_submit.hpp"
#include "p60_submit.hpp"
#include "p67_recurrence.hpp"
#include <iostream>
#include <cstring>
namespace {
using namespace ownrt;using namespace integrated;
void ck(bool v,const char*m){if(!v)throw std::runtime_error(m);}
struct CPU final:Backend {
 std::string identity()const override{return "packet67 host fixture";}
 void* allocate(size_t n,Memory)override{return ::operator new(n,std::align_val_t(64));}
 void release(void*p,Memory)override{::operator delete(p,std::align_val_t(64));}
 Event copy(void*a,const void*b,size_t n,std::span<const Event>)override{std::memcpy(a,b,n);return next_handle();}
 Event marker(std::span<const Event>)override{return next_handle();}
 Event compute(const Operation&o,std::span<void*const>p,std::span<const Event>)override{dynamic_cast<const HostOperation&>(o).run(p);return next_handle();}
 bool complete(Event)override{return true;}bool wait(Event,Deadline)override{return true;}EventTiming timing(Event)override{return {};}
 void synchronize()override{}void clear_events()override{}void close_queue()override{}void close_context()override{}
};
struct Run {
 Device d{std::make_unique<CPU>()};std::vector<Allocation>owned;
 Allocation alloc(size_t n){auto a=d.arena.allocate("fixture-"+std::to_string(owned.size()),n,Memory::device,Category::scratch,Lifetime::transaction);owned.push_back(a);std::memset(d.arena.row(a).pointer,0,n);return a;}
 template<class T>Allocation vec(size_t n,T value){auto a=alloc(n*sizeof(T));std::fill_n(static_cast<T*>(d.arena.row(a).pointer),n,value);return a;}
 void finish(Launch l){ck(d.wait(l.last,std::chrono::milliseconds(1000)),"submit wait");d.retire_completed_events();}
 std::vector<uint8_t>bytes(Allocation a){auto&r=d.arena.row(a);auto p=static_cast<uint8_t*>(r.pointer);return {p,p+r.bytes};}
 void clear(){d.retire_completed_events();for(auto a:owned)d.arena.release(a);owned.clear();}
 ~Run(){clear();}
};
template<class F>void reject(F f){bool threw=false;try{f();}catch(const std::invalid_argument&){threw=true;}ck(threw,"invalid binding admitted");}
void tests(){
 Run r;auto active=r.vec<uint32_t>(1,1),error=r.vec<uint32_t>(1,0),pos=r.vec<uint32_t>(1,7),control=r.alloc(12),dummy=r.alloc(rope_constants::bytes);
 Spec s{};s.op=Op::gdn;s.ni=6;s.no=2;s.nw=2;s.implementation=2;s.packed_heads=true;s.g.h=2560;s.g.context=4096;s.grids[0]=s.grids[1]=iq3::Type::F32;
 for(unsigned j=0;j<8;++j)s.types[j]=flash::Scalar::bf16;s.types[4]=s.types[5]=flash::Scalar::u32;s.sizes[0]=10240;s.sizes[1]=s.sizes[2]=48;s.sizes[3]=6144*128;s.sizes[4]=s.sizes[5]=1;s.sizes[6]=6144;s.sizes[7]=6144*128;
 auto state=r.vec<uint16_t>(6144*128,0x3d00),out=r.alloc(6144*128*2),y=r.alloc(6144*2),scratch=r.alloc(p67rec::scratch_bytes+64);
 std::vector<Allocation>a{r.vec<uint16_t>(10240,0x3d00),r.vec<uint16_t>(48,0x3d00),r.vec<uint16_t>(48,0x3d80),state,active,error,y,out,r.vec<float>(48,-.125f),r.vec<float>(48,.03125f),scratch,error,pos,active,dummy};
 auto f=p49d::resolve("recurrence_head","head-once"),base=p49d::resolve("recurrence","rows4-shared");
 r.finish(base(r.d,s,a,control,dummy,dummy,{}));auto expected=r.bytes(out),ey=r.bytes(y);r.finish(f(r.d,s,a,control,dummy,dummy,{}));ck(r.bytes(out)==expected&&r.bytes(y)==ey,"actual recurrence submit differs");
 auto bound=p49drec::recurrence_bindings(s,a);ck(bound.shape.tokens==1,"serial token ABI");
 auto bad=a;bad[10]=control;reject([&]{f(r.d,s,bad,control,dummy,dummy,{});});bad=a;bad[10]=state;reject([&]{f(r.d,s,bad,control,dummy,dummy,{});});bad=a;bad[6]=a[0];reject([&]{f(r.d,s,bad,control,dummy,dummy,{});});
 p49d::Selection sel;ck(sel.site(s)==p49d::resolve("recurrence","production"),"default recurrence changed");sel.choices["recurrence"]="rows4-shared";ck(sel.site(s)==base,"production sealed recurrence changed");sel.choices["recurrence_head"]="head-once";ck(sel.site(s)==f,"candidate not resolved");
 r.clear();
 p60::IDs ids;const size_t sizes[]{20480,40960,320*iq3::expanded::row_bytes(iq3::Type::Q8_0,10240),10240*iq3::expanded::row_bytes(iq3::Type::Q8_0,320),163840,20480,640,640,20480,5120,8,1280,128,4,4,4};
 for(unsigned i=0;i<16;++i)ids[i]=r.alloc(sizes[i]);*static_cast<uint32_t*>(r.d.arena.row(ids[14]).pointer)=1;
 auto w=static_cast<uint8_t*>(r.d.arena.row(ids[3]).pointer);const size_t rb=iq3::expanded::row_bytes(iq3::Type::Q8_0,320);
 for(unsigned row=0;row<10240;++row){for(unsigned k=0;k<320;++k)w[row*rb+k]=uint8_t(k+row);for(unsigned g=0;g<10;++g){float v=.00390625f;std::memcpy(w+row*rb+320+g*4,&v,4);}}
 std::fill_n(static_cast<uint16_t*>(r.d.arena.row(ids[7]).pointer),320,0x3d00);std::fill_n(static_cast<uint16_t*>(r.d.arena.row(ids[5]).pointer),10240,0x3e00);
 r.finish(p60::submit(r.d,ids,2,4096,false));auto gate=r.bytes(ids[8]),mix=r.bytes(ids[9]);r.finish(p60::submit(r.d,ids,2,4096,true));ck(r.bytes(ids[8])==gate&&r.bytes(ids[9])==mix,"actual HC submit differs");
 auto acts=static_cast<uint16_t*>(r.d.arena.row(ids[7]).pointer);acts[0]=0x7fc1;acts[8]=0xffd5;
 r.finish(p60::submit(r.d,ids,2,4096,false));gate=r.bytes(ids[8]);mix=r.bytes(ids[9]);r.finish(p60::submit(r.d,ids,2,4096,true));ck(r.bytes(ids[8])==gate&&r.bytes(ids[9])==mix,"actual HC exceptional submit differs");
 auto bid=ids;bid[9]=ids[8];reject([&]{p60::submit(r.d,bid,2,4096,true);});reject([&]{p60::submit(r.d,ids,2,0,true);});
}
}
int main(int argc,char**argv){try{
 if(argc==3){if(!*argv[2])return 2;p49d::Selection s;s.load(argv[1],argv[2]);return 0;}
 ck(argc==1,"arguments");tests();std::cout<<"actual submitters, selection dispatch, scratch and aliases PASS\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
