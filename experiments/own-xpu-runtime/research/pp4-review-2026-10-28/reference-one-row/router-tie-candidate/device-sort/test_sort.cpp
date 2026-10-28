#include "reference_sort.hpp"
#include "stage2/packet194-expert-diet-engine/specialised.hpp"
#include <algorithm>
#include <array>
#include <bit>
#include <cassert>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <numeric>
#include <random>
#include <string>
#include <vector>

namespace rr=router_reference_sort;
using Scores=std::array<float,512>;
static int cases=0, forced_cases=0, actual_cases=0, natural_fallbacks=0, maximum_pending=0;
static void need(bool value,const std::string& why) { if(!value) throw std::runtime_error(why); }
template<class T> T load(const std::filesystem::path& path) {
    T out{};
    std::ifstream f(path,std::ios::binary);
    f.read(reinterpret_cast<char*>(out.data()),sizeof(out));
    need(f.gcount()==sizeof(out)&&f.peek()==EOF,"exact fixture extent: "+path.string());
    return out;
}
static void check(const Scores& score,int n,const std::string& label,int forced_depth=-1) {
    std::array<int,514> storage;
    storage.fill(-777);
    std::vector<int> reference(n);
    std::iota(reference.begin(),reference.end(),0);
    const auto before=[&](int a,int b){return score[a]>score[b];};
    if(forced_depth<0) std::sort(reference.begin(),reference.end(),before);
    else {
        auto compare=__gnu_cxx::__ops::__iter_comp_iter(before);
        std::__introsort_loop(reference.begin(),reference.end(),forced_depth,compare);
        std::__final_insertion_sort(reference.begin(),reference.end(),compare);
    }
    rr::Counts counts;
    bool ok=forced_depth<0 ? rr::sort_indices(score.data(),storage.data()+1,n,&counts)
                           : rr::sort_with_depth(score.data(),storage.data()+1,n,forced_depth,&counts);
    need(ok,"candidate admission: "+label);
    need(storage.front()==-777 && storage[n+1]==-777,"canaries: "+label);
    if(!std::equal(reference.begin(),reference.end(),storage.begin()+1)) {
        auto at=std::mismatch(reference.begin(),reference.end(),storage.begin()+1).first-reference.begin();
        throw std::runtime_error("permutation mismatch "+label+" slot="+std::to_string(at));
    }
    maximum_pending=std::max(maximum_pending,counts.maximum_pending);
    if(forced_depth<0) { ++cases; natural_fallbacks+=counts.heap_fallbacks; }
    else { ++forced_cases; if(n>16 && !forced_depth) need(counts.heap_fallbacks==1,"forced heap covered"); }
}
static Scores host_probabilities(const Scores& input) {
    ng::Shape shape; shape.op=ng::route_gather; shape.width=512; shape.extra=10;
    shape.flags=ng::f32_activations_flag; shape.capacity=4096;
    ng::Args args; args.f32=true;
    int32_t error=0,position=177,active=1;
    args.p[0]=const_cast<float*>(input.data()); args.p[15]=&error;
    args.p[17]=&position; args.p[18]=&active;
    std::vector<float> scratch(specialised::scratch_floats(shape));
    auto stage=[&]<int S>() {
        for(size_t i=0;i<specialised::work_items(shape,S);++i)
            specialised::body<ng::route_gather,S>(shape,args,i,scratch.data(),specialised::HostGuard{});
    };
    stage.template operator()<0>(); stage.template operator()<1>(); stage.template operator()<2>();
    need(!error,"production host probability replay");
    Scores out;
    std::copy_n(scratch.data()+2*((512+31)/32)+512,512,out.begin());
    return out;
}
int main(int argc,char** argv) {
    try {
        need(argc==5,"native extracts, native same-input replay, CPU same-input replay, CPU ON captures");
        std::mt19937 random(0x117b70);
        for(int n=0;n<=512;++n) {
            for(int pattern=0;pattern<10;++pattern) {
                Scores score{};
                for(int i=0;i<n;++i) {
                    switch(pattern) {
                    case 0: score[i]=1.f; break;
                    case 1: score[i]=(i&1)?-0.f:0.f; break;
                    case 2: score[i]=float(i); break;
                    case 3: score[i]=float(n-i); break;
                    case 4: score[i]=float(std::min(i,n-1-i)); break;
                    case 5: score[i]=float(i%7); break;
                    case 6: score[i]=float((i/5)%13); break;
                    case 7: score[i]=float(i<n/2 ? 2*i+1 : 2*(i-n/2)); break;
                    case 8: score[i]=(i%2)?1.f:std::nextafter(1.f,2.f); break;
                    default: score[i]=(i%3)?std::numeric_limits<float>::denorm_min():0.f; break;
                    }
                }
                check(score,n,"structured-"+std::to_string(pattern)+"-n"+std::to_string(n));
            }
        }
        for(int trial=0;trial<24000;++trial) {
            const int n=(trial%3)?512:int(random()%513);
            Scores score{};
            for(int i=0;i<n;++i) {
                switch(trial%6) {
                case 0: score[i]=float(int(random()%9)-4); break;
                case 1: score[i]=float(random()%257)*0.00001f; break;
                case 2: score[i]=std::bit_cast<float>(uint32_t(0x3f800000u+(random()%2048))); break;
                case 3: score[i]=float(int(random()))/2147483648.f; break;
                case 4: score[i]=(random()%3)?0.f:-0.f; break;
                default: score[i]=float(random()%17)*std::numeric_limits<float>::denorm_min(); break;
                }
            }
            check(score,n,"random-"+std::to_string(trial));
            if(trial<2000) check(score,n,"forced-heap-"+std::to_string(trial),trial%3);
        }
        // Median-of-three killer variants exercise the ordinary depth budget too.
        for(int shift=0;shift<512;++shift) {
            Scores score{};
            for(int i=0;i<512;++i) {
                const int k=(i+shift)%512;
                score[i]=float(k<256 ? ((k&1)?k+256:k+1) : 2*(k-256)+2);
            }
            check(score,512,"killer-"+std::to_string(shift));
            std::reverse(score.begin(),score.end());
            check(score,512,"killer-reverse-"+std::to_string(shift));
        }
        for(int layer=0;layer<48;++layer) {
            auto scores=load<Scores>(std::filesystem::path(argv[1])/("blk."+std::to_string(layer)+".router.bin"));
            check(scores,512,"native-raw-"+std::to_string(layer)); ++actual_cases;
            check(host_probabilities(scores),512,"native-host-prob-"+std::to_string(layer)); ++actual_cases;
            char name[80]; std::snprintf(name,sizeof(name),"layer-%02d-probabilities.f32",layer);
            check(load<Scores>(std::filesystem::path(argv[4])/name),512,"actual-cpu-prob-"+std::to_string(layer)); ++actual_cases;
        }
        for(int arg=2;arg<=3;++arg) {
            const auto base=std::filesystem::path(argv[arg]);
            const auto expected=load<std::array<int32_t,10>>(base/"ggml-ids.i32");
            for(const char* name: {"native-probs.f32","ggml-probs.f32"}) {
                const Scores probabilities=load<Scores>(base/name);
                check(probabilities,512,std::string("real-ggml-")+name); ++actual_cases;
                std::array<int,512> candidate;
                need(rr::sort_indices(probabilities.data(),candidate.data(),512),"actual probability admission");
                need(std::equal(expected.begin(),expected.end(),candidate.begin()),"actual saved real-ggml top10");
            }
        }
        // Invalid inputs cannot publish even a partial permutation.
        std::array<int,512> output; output.fill(12345); Scores valid{};
        need(!rr::sort_indices(valid.data(),output.data(),513),"oversize rejected");
        need(!rr::sort_indices(valid.data(),output.data(),-1),"negative size rejected");
        need(!rr::sort_indices(nullptr,output.data(),1),"null rejected");
        for(float bad:{std::numeric_limits<float>::infinity(),-std::numeric_limits<float>::infinity(),std::numeric_limits<float>::quiet_NaN()}) {
            Scores value{}; value[73]=bad;
            need(!rr::sort_indices(value.data(),output.data(),512),"nonfinite rejected");
        }
        need(std::all_of(output.begin(),output.end(),[](int i){return i==12345;}),"refusal does not write output");
        need(natural_fallbacks>0,"natural heap fallback must be covered");
        std::cout<<"{\"passed\":true,\"full_permutation_cases\":"<<cases
                 <<",\"forced_depth_cases\":"<<forced_cases<<",\"actual_cases\":"<<actual_cases
                 <<",\"natural_heap_fallbacks\":"<<natural_fallbacks
                 <<",\"maximum_pending_frames\":"<<maximum_pending
                 <<",\"invalid_input_cases\":6,\"gpu_executed\":false}\n";
    } catch(const std::exception& error) {
        std::cerr<<error.what()<<'\n'; return 1;
    }
}
