// Write one valid MoE combine result for incumbent-vs-candidate comparison on the same OpenCL CPU device.
#include <sycl/sycl.hpp>
#include "stage2/packet194-expert-diet-engine/native.cpp"
#include <atomic>
#include <cstdio>
#include <random>
#include <vector>
namespace ownrt { std::uint64_t next_handle(){static std::atomic<std::uint64_t> n{1};return n.fetch_add(1);} }
int main(int argc,char**argv){
 if(argc!=2)return 2;sycl::queue q{sycl::device{sycl::cpu_selector_v},sycl::property::queue::in_order{}};
 constexpr unsigned T=4,W=32,E=10,N=T*W,guard=17;std::mt19937 g(1042);std::normal_distribution<float> d(0.f,0.3f);
 std::vector<float>x(T*E*W),prob(T*E),down(N),gate(T),out(N+guard,0x1.2p10f);
 for(auto& v:x)v=d(g);for(auto& v:prob)v=d(g);for(auto& v:down)v=d(g);for(auto& v:gate)v=d(g);
 std::vector<int32_t> active{1},error{0},position{17};
 ng::Args a{};a.p[0]=x.data();a.p[1]=prob.data();a.p[2]=down.data();a.p[3]=gate.data();a.p[4]=out.data();a.p[15]=error.data();a.p[17]=position.data();a.p[18]=active.data();
 ng::Shape s{};s.op=ng::moe_combine;s.tokens=T;s.width=W;s.extra=E;s.capacity=128;s.flags=ng::f32_activations_flag;
 ng::Kernel op(s);op.submit(q,a.p,{}).wait();FILE* f=std::fopen(argv[1],"wb");std::fwrite(out.data(),sizeof(float),out.size(),f);std::fclose(f);return error[0];
}
