// CPU-device bitwise test (OpenCL CPU, GPU blocked) of OWNRT_DRAFT_ATTN_OUT: one subgroup executes the
// incumbent Dense<K,false,false,1,4> partitions and reductions sequentially. Compare all outputs and sentinel tails.
#include <sycl/sycl.hpp>
#include "stage2/packet194-expert-diet-engine/p59_draft.hpp"
#include <atomic>
#include <cstdio>
#include <random>
#include <vector>
namespace ownrt { std::uint64_t next_handle(){static std::atomic<std::uint64_t> n{1};return n.fetch_add(1);} }
int main(){
 sycl::queue q{sycl::device{sycl::cpu_selector_v},sycl::property::queue::in_order{}};
 std::printf("device: %s\n",q.get_device().get_info<sycl::info::device::name>().c_str());
 constexpr unsigned K=6144,rows=37,guard=8;std::mt19937 g(59);std::normal_distribution<float> nd(0.f,0.05f),xd(0.f,1.f);
 std::vector<uint16_t> w(size_t(rows)*K),x(K),inject(4),ry(rows+guard,0xbeef),rout(4*rows+guard,0xbeef);
 for(auto& v:w)v=iq3::bf16_bits(nd(g));for(auto& v:x)v=iq3::bf16_bits(xd(g));for(auto& v:inject)v=iq3::bf16_bits(xd(g));
 for(unsigned i=0;i<4*rows;++i)rout[i]=iq3::bf16_bits(nd(g));
 w[7]=0x7fc0;w[size_t(K)+9]=0xff80; // row-local NaN and infinity; all other rows retain finite arithmetic
 p59::Bound hb{reinterpret_cast<const uint8_t*>(w.data()),nullptr,x.data(),ry.data(),nullptr,rout.data(),nullptr,inject.data(),nullptr,nullptr,nullptr,rows,1,1,p59::attention};
 const std::vector<uint16_t> rout_init=rout;
 for(unsigned row=0;row<rows;++row){float parts[4]{};
  for(unsigned part=0;part<4;++part){float s[32];for(unsigned l=0;l<32;++l)s[l]=p59::Dense<K,false,false,1,4>::chain(reinterpret_cast<const uint8_t*>(w.data()+size_t(row)*K),x.data(),l,part);
   for(unsigned width=1;width<32;width*=2)for(unsigned l=0;l<32;l+=2*width)s[l]=s[l]+s[l+width];parts[part]=s[0];}
  parts[0]=parts[0]+parts[1];parts[2]=parts[2]+parts[3];parts[0]=parts[0]+parts[2];p59::Dense<K,false,false,1,4>::output(hb,row,true,parts[0],0.f);}
 auto* dw=sycl::malloc_device<uint16_t>(w.size(),q);auto* dx=sycl::malloc_device<uint16_t>(x.size(),q);auto* dy=sycl::malloc_device<uint16_t>(ry.size(),q);
 auto* dout=sycl::malloc_device<uint16_t>(rout.size(),q);auto* din=sycl::malloc_device<uint16_t>(inject.size(),q);
 q.memcpy(dw,w.data(),w.size()*2).wait();q.memcpy(dx,x.data(),x.size()*2).wait();q.memcpy(dy,ry.data(),ry.size()*2).wait();
 q.memcpy(dout,rout_init.data(),rout_init.size()*2).wait();q.memcpy(din,inject.data(),inject.size()*2).wait();
 p59::DenseSplit4OneSubgroup<K> op;op.a.rows=rows;op.a.columns=K;op.a.batch=1;op.a.experts=1;op.a.tail=p59::attention;
 std::vector<void*> ptrs{dw,dw,dx,dy,dy,dx,dy,dy,dout,dx,din};op.submit(q,ptrs,{}).wait();
 std::vector<uint16_t> gy(ry.size()),gout(rout.size());q.memcpy(gy.data(),dy,gy.size()*2).wait();q.memcpy(gout.data(),dout,gout.size()*2).wait();
 size_t bad=0,compared=0;for(size_t i=0;i<gy.size();++i){bad+=gy[i]!=ry[i];++compared;}for(size_t i=0;i<gout.size();++i){bad+=gout[i]!=rout[i];++compared;}
 std::printf("  attention split4: outputs/sentinels %zu, mismatches %zu %s\n",compared,bad,bad?"FAIL":"ok");
 for(void* p:{(void*)dw,(void*)dx,(void*)dy,(void*)dout,(void*)din})sycl::free(p,q);
 std::printf("%s\n",bad?"FAILED":"ALL PASSED");return bad!=0;
}
