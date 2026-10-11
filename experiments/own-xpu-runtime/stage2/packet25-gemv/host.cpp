#include "review_gates.hpp"
#include "timing_loop.hpp"
#include "exactness.hpp"
#include <iostream>
#include <fstream>
#include <map>
using namespace p25;
int main(int argc,char**argv){try{
 verify_dispatch();auto exceptional_tests=gate_tests();auto mock_tests=mock_timing_gate();auto review=independent_review_gates();std::map<std::string,size_t> counts;uint64_t digest=1469598103934665603ull,fp_digest=digest,bf_digest=digest,total=0;
 for(Type t:{Type::IQ2_S,Type::IQ3_S,Type::IQ3_XXS,Type::IQ4_NL,Type::Q6_K,Type::Q8_0})
 for(unsigned k:{32u,96u,256u,640u,768u,2560u,6144u,10240u}){if(k%layout(t).elements)continue;
 for(unsigned special=0;special<2;++special){auto packed=seed_weights(t,k,0,special),peer=seed_weights(t,k,937,special);
 auto expandedw=expanded::expand(t,packed.data(),packed.size(),k),expandedp=expanded::expand(t,peer.data(),peer.size(),k);auto ds=half_scales(t,packed),pds=half_scales(t,peer);
 size_t rb=k/layout(t).elements*layout(t).bytes,erb=expanded::row_bytes(t,k),blocks=k/layout(t).elements;
 for(unsigned mode=0;mode<4;++mode){auto x=inputs(k,1,mode);for(unsigned split:{1u,4u})for(unsigned r=0;r<5;++r){bool pair=expert(t)&&t!=Type::IQ4_NL;
 std::array<float,2> ref{};ref[0]=reference(t,packed.data()+r*rb,x.data(),k,split);if(pair)ref[1]=reference(t,peer.data()+r*rb,x.data(),k,split);
 auto oracle=result(ref);std::array<float,2> control{};for(unsigned p=0;p<(pair?2u:1u);++p){auto& src=p?peer:packed;auto& ex=p?expandedp:expandedw;
 control[p]=integrated::arithmetic::row(t,(expert(t)?src.data()+r*rb:ex.data()+r*erb),x.data(),k,expert(t)?(split==4?4:2):(split==4?7:6));}
 if(!equal(oracle,result(control)))throw std::runtime_error("current/reference mismatch t="+std::to_string(unsigned(t))+" k="+std::to_string(k)+" mode="+std::to_string(mode)+" special="+std::to_string(special));
 for(auto c:candidates(t)){bool fallback=false;
 auto got=checked_host_dispatch(t,c,packed.data()+r*rb,peer.data()+r*rb,expandedw.data()+r*erb,expandedp.data()+r*erb,x.data(),ds.data()+r*blocks,pds.data()+r*blocks,k,split,pair,&fallback);
 auto actual=result(got);if(!equal(actual,oracle)){std::cerr<<"mismatch "<<name(c)<<" type="<<unsigned(t)<<" k="<<k<<" special="<<special<<" mode="<<mode<<" row="<<r<<" split="<<split<<" got="<<std::hex<<actual.fp[0]<<","<<actual.fp[1]<<" expected="<<oracle.fp[0]<<","<<oracle.fp[1]<<std::dec<<"\n";return 1;}
 for(auto v:actual.fp){digest^=v;digest*=1099511628211ull;fp_digest^=v;fp_digest*=1099511628211ull;}for(auto v:actual.bf){digest^=v;digest*=1099511628211ull;bf_digest^=v;bf_digest*=1099511628211ull;}++counts[std::to_string(unsigned(t))+"/"+name(c)];++total;
 }
 }}}
 }
 // Enumerate actual group/sub mapping, require complete, unique row/partial writes.
 size_t mapping=0;for(auto s:shapes)for(unsigned rows:{1u,3u,5u,639u,640u,641u,s.rows})for(auto c:candidates(s.type)){
 auto rpg=rows_per_group(c,s.split),wg=local_size(c,s.split);std::vector<unsigned> writes(size_t(rows)*s.count),partials(size_t(rows)*s.count*s.split);
 size_t groups=(writes.size()+rpg-1)/rpg;
 for(size_t g=0;g<groups;++g)for(unsigned sub=0;sub<wg/32;++sub){unsigned rr=sub/s.split,p=sub%s.split;size_t row=g*rpg+rr;if(rr>=rpg||row>=writes.size())continue;++partials[row*s.split+p];if(p==0)++writes[row];}
 for(auto v:writes)if(v!=1)throw std::runtime_error("row writer multiplicity");for(auto v:partials)if(v!=1)throw std::runtime_error("partial writer multiplicity");++mapping;
 }
 Shape failed{"boundary","fixture",Type::IQ2_S,5,256,10,1,1,true};
 auto failed_x=inputs(256,10,3);auto failed_host=expected(failed,seed_weights(Type::IQ2_S,256,0,1),seed_weights(Type::IQ2_S,256,937,1),failed_x);
 std::ostream* out=&std::cout;std::ofstream file;if(argc==2){file.open(argv[1]);out=&file;}
 *out<<"{\"g1_a_element14_host_bits\":";result_bits(*out,failed_host[14]);*out<<",\"g1_a_element14_input_prefix_bf16\":[";for(unsigned i=0;i<12;++i)*out<<(i?",":"")<<hex_bits(failed_x[2*256+i],4);*out<<"],\"passed\":true,\"device_executed\":false,\"comparisons\":"<<total<<",\"exceptional_gate_tests\":"<<exceptional_tests<<",\"mock_timing_tests\":"<<mock_tests<<",\"isolated_decoded_values\":"<<review.decoded_values<<",\"independent_finite_rows\":"<<review.finite_rows<<",\"routed_rows\":"<<review.routed_rows<<",\"mapping_cases\":"<<mapping<<",\"digest\":\""<<std::hex<<digest<<"\",\"fp_digest\":\""<<fp_digest<<"\",\"bf_digest\":\""<<bf_digest<<std::dec<<"\",\"families\":{";bool comma=false;for(auto [key,count]:counts){*out<<(comma?",":"")<<"\""<<key<<"\":"<<count;comma=true;}*out<<"}}\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
