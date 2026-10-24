// Standalone synthetic production-shape IQ2 arithmetic, not Engine/native integration.
#include "selected_cpu.hpp"
#include "paired_iq2.hpp"
#include <algorithm>
#include <array>
#include <bit>
#include <cstring>
#include <iostream>
#include <map>
#include <openssl/sha.h>
#include <sstream>
using namespace ownrt;
namespace {
constexpr unsigned K=2560,N=640,T=10,E=512,BANKS=21;constexpr size_t RB=820,BYTES=N*RB;
void need(bool v,const char*why){if(!v)throw std::runtime_error(why);}
std::string sha(const std::vector<uint8_t>&v){unsigned char h[32];SHA256(v.data(),v.size(),h);std::string s;for(auto b:h){s+="0123456789abcdef"[b>>4];s+="0123456789abcdef"[b&15];}return s;}
std::string hex(const std::vector<uint8_t>&v){std::string s;for(auto b:v){s+="0123456789abcdef"[b>>4];s+="0123456789abcdef"[b&15];}return s;}
struct Row{
 Allocation x,routes,workspace,error,active,position,reference_error;
 std::array<Allocation,2>table,y,status,reference_y,reference_status;
 std::array<void*,20>p{};std::vector<integrated::Matrix>m; p39::Bindings bindings;
};
struct Fixture{
 Host*host;Device d;bool closed=false;unsigned sequence=0;std::array<Allocation,2>weights;Allocation halfcache,other_halfcache;std::array<Row,2>rows;p215::Selected selected;
 Fixture():host(new Host),d(std::unique_ptr<Backend>(host)){
  static_assert(p49bgemv::layout(iq3::Type::IQ2_S,K).row_bytes==RB);selected.rows=N;selected.count=T;selected.experts=E;selected.indirect=true;
  halfcache=alloc("half-table",65536*4);other_halfcache=alloc("other-half-table",65536*4);for(unsigned i=0;i<65536;++i){float v=iq3::half(uint16_t(i));static_cast<float*>(ptr(halfcache))[i]=v;static_cast<float*>(ptr(other_halfcache))[i]=v;}
  for(unsigned projection=0;projection<2;++projection){weights[projection]=alloc("packed-weights",BANKS*BYTES);fill_weights(projection,false);}
  for(unsigned r=0;r<2;++r){auto&row=rows[r];row.x=alloc("x",K*2);row.routes=alloc("routes",T*sizeof(iq3::Route));row.workspace=alloc("workspace",4);row.error=alloc("error",4);row.active=alloc("active",4);row.position=alloc("position",4);row.reference_error=alloc("reference-error",4);
   for(unsigned projection=0;projection<2;++projection){row.table[projection]=alloc("table",E*sizeof(p58::Pointer));row.y[projection]=alloc("paired-output",N*T*2);row.reference_y[projection]=alloc("selected-output",N*T*2);row.status[projection]=alloc("paired-status",T*4);row.reference_status[projection]=alloc("selected-status",T*4);}
  }reset(3);
 }
 ~Fixture(){if(!closed){auto receipt=d.shutdown(std::chrono::seconds(1));std::cerr<<"P215_FAILURE_OWNER "<<receipt.json()<<'\n';if(!receipt.safe_to_exit)std::abort();}}
 Allocation alloc(const char*name,size_t n){auto id=d.arena.allocate("card0:p215:"+std::to_string(++sequence)+":"+name,n,Memory::device,Category::scratch,Lifetime::transaction);std::memset(ptr(id),0,n);return id;}
 void*ptr(Allocation id){return d.arena.row(id).pointer;}
 std::vector<uint8_t>bytes(Allocation id){auto&r=d.arena.row(id);auto*p=static_cast<uint8_t*>(r.pointer);return {p,p+r.bytes};}
 void fill_weights(unsigned projection,bool exceptional){constexpr auto layout=p49bgemv::layout(iq3::Type::IQ2_S,K);auto*w=static_cast<uint8_t*>(ptr(weights[projection]));
  for(unsigned bank=0;bank<BANKS;++bank)for(unsigned row=0;row<N;++row){auto*p=w+bank*BYTES+row*RB;for(size_t i=0;i<RB;++i)p[i]=uint8_t(i*37+bank*19+row*11+projection*83);for(unsigned block=0;block<10;++block){uint16_t scale=uint16_t(0x2400+((bank*7+row*3+block+projection*13)%512));if(exceptional&&bank==0&&row<10){constexpr uint16_t cases[]{0x0000,0x8000,0x0001,0x03ff,0x7c00,0xfc00,0x7e11,0xfe22,0x0400,0x3555};scale=cases[row];}std::memcpy(p+layout.halves+block*2,&scale,2);}}
 }
 void reset(unsigned count){for(unsigned r=0;r<2;++r){auto&row=rows[r];auto*x=static_cast<uint16_t*>(ptr(row.x));for(unsigned k=0;k<K;++k){float value=float(int((k*17+r*23)%67)-33)*0.03125f;x[k]=(k%37==0)?uint16_t(r?0x8000:0):iq3::bf16_bits(value);}
  for(unsigned projection=0;projection<2;++projection){auto*t=static_cast<p58::Pointer*>(ptr(row.table[projection]));for(unsigned e=0;e<E;++e)t[e]={uint64_t(ptr(weights[projection]))+(e%BANKS)*BYTES,1};}
  auto*routes=static_cast<iq3::Route*>(ptr(row.routes));for(unsigned slot=0;slot<T;++slot)routes[slot]={slot,0,count};*static_cast<uint32_t*>(ptr(row.active))=1;*static_cast<uint32_t*>(ptr(row.position))=3;*static_cast<uint32_t*>(ptr(row.error))=0;*static_cast<uint32_t*>(ptr(row.reference_error))=0;bind(r);
 }}
 void bind(unsigned r){auto&x=rows[r];x.p={ptr(x.table[0]),ptr(x.table[1]),ptr(x.x),ptr(x.y[0]),ptr(x.y[1]),ptr(x.routes),ptr(x.status[0]),ptr(x.status[1]),ptr(x.workspace),ptr(x.x),ptr(x.y[0]),ptr(x.y[0]),ptr(x.x),ptr(x.x),ptr(x.x),ptr(x.x),ptr(x.error),ptr(x.active),ptr(x.position),ptr(halfcache)};
  x.m.clear();for(unsigned projection=0;projection<2;++projection){integrated::Matrix m{};m.type=iq3::Type::IQ2_S;m.w=x.table[projection];m.x=x.x;m.y=x.reference_y[projection];m.rows=N;m.columns=K;m.experts=E;m.count=T;m.span=N;m.routes=x.routes;m.status=x.reference_status[projection];m.workspace=x.workspace;x.m.push_back(m);}
  x.bindings={};x.bindings.error=x.reference_error;x.bindings.active=x.active;x.bindings.position=x.position;x.bindings.capacity=4096;x.bindings.indirect=true;
 }
 void reference(){for(auto&r:rows){auto half=r.p[19]==ptr(halfcache)?halfcache:other_halfcache;auto result=p58ag::expert(d,r.m,r.bindings,half,true);need(d.wait(result.last,std::chrono::seconds(1))&&d.complete(result.last),"selected M1 completion");}need(d.in_flight()==0,"selected M1 inflight");d.retire_completed_events();}
 std::vector<uint8_t>output(bool reference){std::vector<uint8_t>out;for(auto&r:rows)for(unsigned projection=0;projection<2;++projection){auto b=bytes(reference?r.reference_y[projection]:r.y[projection]);out.insert(out.end(),b.begin(),b.end());}return out;}
 std::vector<uint8_t>status(bool reference){std::vector<uint8_t>out;for(auto&r:rows){for(unsigned projection=0;projection<2;++projection){auto b=bytes(reference?r.reference_status[projection]:r.status[projection]);out.insert(out.end(),b.begin(),b.end());}auto b=bytes(reference?r.reference_error:r.error);out.insert(out.end(),b.begin(),b.end());}return out;}
 std::pair<std::vector<uint8_t>,std::vector<uint8_t>>oracle(std::array<uint32_t,2>initial){std::vector<uint8_t>out,flags;for(unsigned ri=0;ri<2;++ri){auto&r=rows[ri];auto*routes=static_cast<const iq3::Route*>(ptr(r.routes));auto*x=static_cast<const uint16_t*>(ptr(r.x));auto error=initial[ri];
  for(unsigned projection=0;projection<2;++projection){auto*table=static_cast<const p58::Pointer*>(ptr(r.table[projection]));std::vector<uint16_t>values(N*T);std::array<uint32_t,T>status{};
   for(unsigned slot=0;slot<T;++slot){auto route=routes[slot];bool valid=iq3::valid_route(route,E,N,N);status[slot]=!valid;if(!valid&&*static_cast<const uint32_t*>(ptr(r.active))&&error==0)error=1;
    for(unsigned row=0;row<N;++row){float value=iq3::bits_float(0x7fc00000);if(valid&&row<route.row_count){auto*w=reinterpret_cast<const uint8_t*>(table[route.expert_id].address)+(route.row_begin+row)*RB;value=p49dvirtual::host_row<iq3::Type::IQ2_S,K,8>(w,x);}values[slot*N+row]=iq3::bf16_bits(value);}}
   auto*b=reinterpret_cast<uint8_t*>(values.data());out.insert(out.end(),b,b+values.size()*2);auto*s=reinterpret_cast<uint8_t*>(status.data());flags.insert(flags.end(),s,s+sizeof(status));}
  auto*e=reinterpret_cast<uint8_t*>(&error);flags.insert(flags.end(),e,e+4);
 }return {out,flags};}
 void clear(){for(auto&r:rows){for(unsigned p=0;p<2;++p){std::memset(ptr(r.y[p]),0xa5,N*T*2);std::memset(ptr(r.reference_y[p]),0x5a,N*T*2);std::memset(ptr(r.status[p]),0xa5,T*4);std::memset(ptr(r.reference_status[p]),0x5a,T*4);}}}
 Receipt close(){auto r=d.shutdown(std::chrono::seconds(1));need(r.safe_to_exit&&r.in_flight==0&&r.live_bytes==0,"safe CPU owner teardown");closed=true;return r;}
};
}
int main(){try{
 Fixture f;std::map<std::string,bool>checks;std::vector<std::string>cases;auto pass=[&](std::string n,bool v){need(v,n.c_str());checks[n]=true;};
 // Focused CPU correction checks supplement, never replace, the unchanged M1/scalar byte gates.
 for(auto bits:std::array<std::pair<uint32_t,uint32_t>,4>{{{0x7fc12345,0xffc54321},{0xffc54321,0x7fc12345},{0x7fc12345,0x7fc54321},{0xffc12345,0xffc54321}}}){
  pass("quiet_nan_accumulator_payload_"+std::to_string(bits.first)+"_"+std::to_string(bits.second),std::bit_cast<uint32_t>(p215::accumulate(std::bit_cast<float>(bits.first),std::bit_cast<float>(bits.second)))==bits.first);
 }
 for(auto bits:std::array<std::pair<uint32_t,uint32_t>,6>{{{0x3f800000,0xbf800000},{0x80000000,0x80000000},{0x00000000,0x80000000},{0x7fc12345,0x3f800000},{0x3f800000,0xffc54321},{0x7f800000,0xff800000}}}){
  volatile float a=std::bit_cast<float>(bits.first),b=std::bit_cast<float>(bits.second);float expected=a+b;
  pass("ordinary_accumulation_bits_"+std::to_string(bits.first)+"_"+std::to_string(bits.second),std::bit_cast<uint32_t>(p215::accumulate(a,b))==std::bit_cast<uint32_t>(expected));
 }
 std::array<int,10> identity{0,1,2,3,4,5,6,7,8,9},none{-1,-1,-1,-1,-1,-1,-1,-1,-1,-1};
 auto run=[&](const std::string&name,const std::array<int,10>&expected){
  std::array<uint32_t,2>initial{};for(unsigned r=0;r<2;++r)initial[r]=*static_cast<uint32_t*>(f.ptr(f.rows[r].error));f.clear();
  auto plan=p215::match(f.selected,f.rows[0].p,f.rows[1].p);pass(name+"_exact_original_slot_matching",plan.row0_to_row1==expected);
  uint64_t matched_rows=0,valid_rows=0;unsigned pairs=0;for(unsigned r=0;r<2;++r){auto*routes=static_cast<iq3::Route*>(f.ptr(f.rows[r].routes));for(unsigned slot=0;slot<10;++slot)if(iq3::valid_route(routes[slot],E,N,N))valid_rows+=routes[slot].row_count;}
  for(unsigned i=0;i<10;++i)if(expected[i]>=0){++pairs;matched_rows+=static_cast<iq3::Route*>(f.ptr(f.rows[0].routes))[i].row_count;}
  f.reference();auto control=f.output(true),control_status=f.status(true);auto scalar=f.oracle(initial);pass(name+"_selected_scalar_oracle_exact",control==scalar.first&&control_status==scalar.second);
  p215::Counters stats;p215::run_pair(f.selected,f.rows[0].p,f.rows[1].p,stats,true);auto actual=f.output(false),actual_status=f.status(false);if(actual!=control||actual_status!=control_status){
   size_t first=0;while(first<actual.size()&&actual[first]==control[first])++first;
   std::cerr<<"P215_MISMATCH {\"case\":"<<quote(name)<<",\"candidate_sha256\":"<<quote(sha(actual))<<",\"selected_sha256\":"<<quote(sha(control))<<",\"scalar_sha256\":"<<quote(sha(scalar.first))<<",\"output_equal\":"<<(actual==control?"true":"false")<<",\"status_equal\":"<<(actual_status==control_status?"true":"false");
   if(first<actual.size()){
    size_t element=first/2,row=element/12800,projection=(element%12800)/6400,slot=(element%6400)/640,output_row=element%640;
    auto route=static_cast<iq3::Route*>(f.ptr(f.rows[row].routes))[slot];uint16_t candidate,selected,oracle;
    std::memcpy(&candidate,actual.data()+element*2,2);std::memcpy(&selected,control.data()+element*2,2);std::memcpy(&oracle,scalar.first.data()+element*2,2);
    bool inspect=iq3::valid_route(route,E,N,N)&&output_row<route.row_count;
    std::cerr<<",\"row\":"<<row<<",\"projection\":"<<projection<<",\"slot\":"<<slot<<",\"output_row\":"<<output_row<<",\"route\":["<<route.expert_id<<','<<route.row_begin<<','<<route.row_count<<"],\"candidate_bf16\":"<<candidate<<",\"selected_bf16\":"<<selected<<",\"scalar_bf16\":"<<oracle<<",\"weight_inspected\":"<<(inspect?"true":"false");
    if(inspect){
     auto*table=static_cast<p58::Pointer*>(f.ptr(f.rows[row].table[projection]));auto*w=reinterpret_cast<const uint8_t*>(table[route.expert_id].address)+(route.row_begin+output_row)*RB;
     constexpr auto layout=p49bgemv::layout(iq3::Type::IQ2_S,K);auto*x=static_cast<uint16_t*>(f.ptr(f.rows[row].x));auto*half=static_cast<const float*>(f.rows[row].p[19]);
     std::cerr<<",\"half_scale_bits\":[";for(unsigned b=0;b<10;++b)std::cerr<<(b?",":"")<<p49bgemv::load16(w+layout.halves+2*b);
     std::cerr<<"],\"first_input_bf16\":[";for(unsigned k=0;k<16;++k)std::cerr<<(k?",":"")<<x[k];std::cerr<<']';
     float lanes[4];for(unsigned lane=0;lane<4;++lane)lanes[lane]=p49dvirtual::local_tree<8>(p215::Selected::chains(w,x,lane,half));
     std::cerr<<",\"diagnostic_selected_lane_fp32_bits\":[";for(unsigned lane=0;lane<4;++lane)std::cerr<<(lane?",":"")<<std::bit_cast<uint32_t>(lanes[lane]);std::cerr<<']';
     for(unsigned width=1;width<4;width*=2)for(unsigned lane=0;lane<4;lane+=2*width)lanes[lane]=lanes[lane]+lanes[lane+width];
     p215::Counters diagnostic_stats;auto single=p215::dot(w,x,nullptr,half,diagnostic_stats)[0];
     std::cerr<<",\"diagnostic_selected_fp32_bits\":"<<std::bit_cast<uint32_t>(lanes[0])<<",\"diagnostic_scalar_fp32_bits\":"<<std::bit_cast<uint32_t>(p49dvirtual::host_row<iq3::Type::IQ2_S,K,8>(w,x))<<",\"diagnostic_candidate_single_fp32_bits\":"<<std::bit_cast<uint32_t>(single);
     int partner=-1;if(row==0)partner=plan.row0_to_row1[slot];else for(unsigned i=0;i<10;++i)if(plan.row0_to_row1[i]==int(slot))partner=int(i);
     if(partner>=0){auto values=p215::dot(w,static_cast<uint16_t*>(f.ptr(f.rows[0].x)),static_cast<uint16_t*>(f.ptr(f.rows[1].x)),half,diagnostic_stats);std::cerr<<",\"diagnostic_candidate_paired_fp32_bits\":"<<std::bit_cast<uint32_t>(values[row]);}
    }
   }
   std::cerr<<",\"candidate_status_error_hex\":"<<quote(hex(actual_status))<<",\"selected_status_error_hex\":"<<quote(hex(control_status))<<"}\n";
  }
  pass(name+"_paired_selected_exact",actual==control&&actual_status==control_status);
  pass(name+"_actual_shared_decode_counts",stats.slot_pairs==pairs&&stats.valid_output_rows==valid_rows*2&&stats.shared_decoded_tiles==matched_rows*640&&stats.decoded_tiles==(valid_rows-matched_rows)*640&&stats.independent_decoded_tiles+stats.shared_decoded_tiles==stats.decoded_tiles);
  for(unsigned r=0;r<2;++r)*static_cast<uint32_t*>(f.ptr(f.rows[r].error))=initial[r];p215::Counters unshared;p215::run_pair(f.selected,f.rows[0].p,f.rows[1].p,unshared,false);
  pass(name+"_unshared_exact_and_counted",f.output(false)==actual&&f.status(false)==actual_status&&unshared.slot_pairs==0&&unshared.shared_decoded_tiles==0&&unshared.decoded_tiles==valid_rows*640&&unshared.decoded_tiles-stats.decoded_tiles==stats.shared_decoded_tiles);
  std::ostringstream out;out<<"{\"name\":"<<quote(name)<<",\"passed\":true,\"matched_slots\":[";for(unsigned i=0;i<10;++i)out<<(i?",":"")<<plan.row0_to_row1[i];out<<"],\"routes\":[";for(unsigned r=0;r<2;++r){out<<(r?",":"")<<'[';auto*routes=static_cast<iq3::Route*>(f.ptr(f.rows[r].routes));for(unsigned slot=0;slot<10;++slot)out<<(slot?",":"")<<'['<<routes[slot].expert_id<<','<<routes[slot].row_begin<<','<<routes[slot].row_count<<']';out<<']';}out<<"],\"active\":["<<*static_cast<uint32_t*>(f.ptr(f.rows[0].active))<<','<<*static_cast<uint32_t*>(f.ptr(f.rows[1].active))<<"],\"initial_error\":["<<initial[0]<<','<<initial[1]<<"],\"input_sha256\":["<<quote(sha(f.bytes(f.rows[0].x)))<<','<<quote(sha(f.bytes(f.rows[1].x)))<<"],\"raw_id_overlap\":"<<plan.raw_id_overlap<<",\"tuple_overlap\":"<<plan.tuple_overlap<<",\"slot_pairs\":"<<stats.slot_pairs<<",\"valid_output_rows\":"<<stats.valid_output_rows<<",\"decoded_tiles\":"<<stats.decoded_tiles<<",\"shared_decoded_tiles\":"<<stats.shared_decoded_tiles<<",\"independent_decoded_tiles\":"<<stats.independent_decoded_tiles<<",\"unshared_decoded_tiles\":"<<unshared.decoded_tiles<<",\"bytes\":"<<actual.size()<<",\"selected_sha256\":"<<quote(sha(control))<<",\"scalar_oracle_sha256\":"<<quote(sha(scalar.first))<<",\"paired_sha256\":"<<quote(sha(actual))<<",\"status_error_sha256\":"<<quote(sha(actual_status))<<",\"output_hex\":"<<quote(hex(actual))<<",\"status_error_hex\":"<<quote(hex(actual_status))<<"}";std::cerr<<"P215_CASE_PASS {\"case\":"<<quote(name)<<",\"output_sha256\":"<<quote(sha(actual))<<",\"status_error_sha256\":"<<quote(sha(actual_status))<<",\"decoded_tiles\":"<<stats.decoded_tiles<<",\"shared_decoded_tiles\":"<<stats.shared_decoded_tiles<<"}\n";cases.push_back(out.str());return actual;
 };
 f.reset(N);for(unsigned i=0;i<10;++i)static_cast<iq3::Route*>(f.ptr(f.rows[1].routes))[i].expert_id=i+10;run("disjoint_full",none);
 f.reset(N);for(unsigned i=0;i<10;++i)static_cast<iq3::Route*>(f.ptr(f.rows[1].routes))[i].expert_id=i+5;run("partial_full",{-1,-1,-1,-1,-1,0,1,2,3,4});
 f.reset(N);for(unsigned i=0;i<10;++i)static_cast<iq3::Route*>(f.ptr(f.rows[1].routes))[i].expert_id=9-i;run("permuted_full",{9,8,7,6,5,4,3,2,1,0});
 f.reset(N);std::memcpy(f.ptr(f.rows[1].x),f.ptr(f.rows[0].x),K*2);run("equal_inputs_full_overlap",identity);
 f.reset(3);std::array<unsigned,10> duplicate0{0,0,1,1,2,2,3,3,4,4},duplicate1{4,3,2,1,0,4,3,2,1,0};for(unsigned i=0;i<10;++i){static_cast<iq3::Route*>(f.ptr(f.rows[0].routes))[i].expert_id=duplicate0[i];static_cast<iq3::Route*>(f.ptr(f.rows[1].routes))[i].expert_id=duplicate1[i];}run("permuted_duplicates",{4,9,3,8,2,7,1,6,0,5});
 f.reset(3);static_cast<iq3::Route*>(f.ptr(f.rows[1].routes))[3]={3,1,2};auto mismatch=identity;mismatch[3]=-1;run("same_expert_different_slice",mismatch);
 f.reset(3);static_cast<p58::Pointer*>(f.ptr(f.rows[1].table[0]))[4].address=uint64_t(f.ptr(f.weights[0]))+20*BYTES;mismatch=identity;mismatch[4]=-1;run("same_expert_different_backing",mismatch);
 f.reset(3);static_cast<p58::Pointer*>(f.ptr(f.rows[1].table[1]))[5].generation=2;mismatch=identity;mismatch[5]=-1;run("same_expert_different_generation",mismatch);
 f.reset(3);f.rows[1].p[19]=f.ptr(f.other_halfcache);run("different_halfcache_storage",none);
 for(unsigned mode=0;mode<3;++mode){f.reset(3);for(unsigned r=0;r<2;++r){auto*routes=static_cast<iq3::Route*>(f.ptr(f.rows[r].routes));routes[0]={512,0,3};routes[1]={1,641,1};routes[2]={2,639,2};routes[3]={3,0,0};*static_cast<uint32_t*>(f.ptr(f.rows[r].active))=mode==1?0:1;*static_cast<uint32_t*>(f.ptr(f.rows[r].error))=mode==2?7:0;*static_cast<uint32_t*>(f.ptr(f.rows[r].reference_error))=mode==2?7:0;}mismatch=identity;mismatch[0]=mismatch[1]=mismatch[2]=-1;run(std::array<std::string,3>{"invalid_active","invalid_inactive","invalid_sticky_error"}[mode],mismatch);}
 f.reset(0);run("valid_zero_count",identity);
 f.reset(10);f.fill_weights(0,true);f.fill_weights(1,true);
 for(unsigned projection=0;projection<2;++projection)for(unsigned row=0;row<10;++row){constexpr auto layout=p49bgemv::layout(iq3::Type::IQ2_S,K);auto*w=static_cast<const uint8_t*>(f.ptr(f.weights[projection]))+row*RB;for(unsigned k=0;k<K;k+=8){unsigned block=k/256,i=k%256,q=i/8;p58ag_exp::RawTile tile;tile.a=p49bgemv::load16(w+block*64+q*2);tile.high=w[layout.high+block*8+q/4];tile.scale=w[layout.scales+block*8+i/32];auto half=p49bgemv::load16(w+layout.halves+block*2);float selected[8],oracle[8];p58ag_exp::decode_tile<iq3::Type::IQ2_S>(tile,k,selected,static_cast<const float*>(f.ptr(f.halfcache))[half]);p49dvirtual::decode_iq2<K>(w,k,oracle);for(unsigned j=0;j<8;++j)need(std::bit_cast<uint32_t>(selected[j])==std::bit_cast<uint32_t>(oracle[j]),"isolated exceptional decode bits");}}
 pass("isolated_exceptional_decode_bits",true);run("exceptional_half_scale_signed_zero",identity);f.fill_weights(0,false);f.fill_weights(1,false);
 f.reset(3);auto baseline=run("edge_base",identity);
 f.reset(3);static_cast<uint16_t*>(f.ptr(f.rows[0].x))[1]=iq3::bf16_bits(16.0f);auto changed=run("input_mutation",identity);pass("independent_row_input_mutation_discriminates",!std::equal(baseline.begin(),baseline.begin()+25600,changed.begin())&&std::equal(baseline.begin()+25600,baseline.end(),changed.begin()+25600));
 f.reset(3);constexpr auto layout=p49bgemv::layout(iq3::Type::IQ2_S,K);uint16_t scale=0x3c00;std::memcpy(static_cast<uint8_t*>(f.ptr(f.weights[0]))+layout.halves,&scale,2);auto mutated=run("live_weight_mutation",identity);pass("actual_weight_payload_mutation_discriminates",mutated!=baseline);
 auto untouched=f.output(false);for(auto bad:{0u,639u}){auto selected=f.selected;selected.rows=bad;bool rejected=false;try{p215::Counters c;p215::run_pair(selected,f.rows[0].p,f.rows[1].p,c);}catch(const std::exception&){rejected=true;}pass("unsupported_rows_"+std::to_string(bad)+"_refused_before_writes",rejected&&f.output(false)==untouched);}
 auto receipt=f.close();std::cout<<"{\"schema\":\"packet215.iq2-pair-proof.v1\",\"passed\":true,\"device_executed\":false,\"native_executed\":false,\"model_executed\":false,\"geometry\":{\"columns\":2560,\"rows\":640,\"top\":10,\"expert_table_entries\":512,\"materialized_banks\":21,\"row_bytes\":820},\"scope\":\"standalone HOST_ONLY arithmetic; original selected p58ag operator and separate scalar p49d V8 oracle; unused expert IDs deliberately alias compact synthetic banks; no Engine integration or measured real-route overlap\",\"checks\":{";bool first=true;for(auto&[n,v]:checks){std::cout<<(first?"":",")<<quote(n)<<":true";first=false;}std::cout<<"},\"cases\":[";for(size_t i=0;i<cases.size();++i)std::cout<<(i?",":"")<<cases[i];std::cout<<"],\"owner_receipt\":"<<receipt.json()<<"}\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
