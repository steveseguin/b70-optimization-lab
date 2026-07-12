#include "mmvq.hpp"
#include <sycl/ext/intel/esimd.hpp>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <random>
#include <vector>

namespace esimd=sycl::ext::intel::esimd; namespace xmx=sycl::ext::intel::esimd::xmx;
template<int M> class joint_kernel; template<int M> class reduce_kernel;
template<int M> class prod_quant_kernel; template<int M> class joint_quant_kernel;

static double us(const sycl::event&e){return double(e.get_profiling_info<sycl::info::event_profiling::command_end>()-e.get_profiling_info<sycl::info::event_profiling::command_start>())/1000.;}
static double med(std::vector<double> v){std::sort(v.begin(),v.end());return v[v.size()/2];}

template<int M> sycl::event quant_prod(sycl::queue&q,const float*x,int8_t*out,int k){
 const int kb=k/32; return q.submit([&](sycl::handler&h){h.parallel_for<prod_quant_kernel<M>>(sycl::nd_range<1>(M*kb*32,32),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
  int b=it.get_group(0),r=b/kb,ki=b%kb,l=it.get_local_id(0);float v=x[size_t(r)*k+ki*32+l],a=sycl::reduce_over_group(it.get_sub_group(),sycl::fabs(v),sycl::maximum<float>()),sum=sycl::reduce_over_group(it.get_sub_group(),v,sycl::plus<float>()),d=a? a/127.f:0.f;
  out[size_t(r)*(k+kb*4)+ki*32+l]=d?int8_t(sycl::round(v/d)):0;if(l==0)*reinterpret_cast<sycl::half2*>(out+size_t(r)*(k+kb*4)+k+ki*4)=sycl::half2(sycl::half(d),sycl::half(sum)); });});}
template<int M> sycl::event quant_joint(sycl::queue&q,const float*x,int8_t*out,int k){
 const int kb=k/32; return q.submit([&](sycl::handler&h){h.parallel_for<joint_quant_kernel<M>>(sycl::nd_range<1>(M*kb*32,32),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
  int b=it.get_group(0),r=b/kb,ki=b%kb,l=it.get_local_id(0);float v=x[size_t(r)*k+ki*32+l],a=sycl::reduce_over_group(it.get_sub_group(),sycl::fabs(v),sycl::maximum<float>()),sum=sycl::reduce_over_group(it.get_sub_group(),v,sycl::plus<float>()),d=a?a/127.f:0.f;
  int qi=d?int(sycl::round(v/d)):0;out[(size_t(ki)*M+r)*32+l]=int8_t(qi);int qsum=sycl::reduce_over_group(it.get_sub_group(),qi,sycl::plus<int>());if(l==0){float hd=float(sycl::half(d)),hs=float(sycl::half(sum));reinterpret_cast<sycl::float2*>(out+size_t(k)*M)[ki*M+r]=sycl::float2(hd,8.f*(qsum*hd-hs));} });});}

template<int M> std::pair<sycl::event,sycl::event> joint(sycl::queue&q,const uint8_t*w,const int8_t*a,float*p,float*o,int k,int n){
 constexpr int S=8;int kb=k/32,nt=n/16,jt=(nt+1)/2;size_t qb=size_t(k)*n/2;auto*ws=reinterpret_cast<const sycl::half*>(w+qb);auto*as=reinterpret_cast<const sycl::float2*>(a+size_t(k)*M);
 auto c=q.submit([&](sycl::handler&h){h.parallel_for<joint_kernel<M>>(sycl::range<2>(S,jt),[=](sycl::id<2>id)[[intel::sycl_explicit_simd]]{int s=id[0],t0=int(id[1])*2,b0=kb*s/S,b1=kb*(s+1)/S;esimd::simd<float,M*32>acc(0);
  for(int b=b0;b<b1;++b){esimd::simd<uint32_t,M*8>av;av.copy_from(reinterpret_cast<const uint32_t*>(a)+size_t(b)*M*8);for(int j=0;j<2;++j){int t=t0+j;if(t>=nt)continue;esimd::simd<uint32_t,64>bv;bv.copy_from(reinterpret_cast<const uint32_t*>(w)+(size_t(b)*nt+t)*64);auto d=xmx::dpas<8,M,int32_t,uint32_t,uint32_t,xmx::dpas_argument_type::s4,xmx::dpas_argument_type::s8>(bv,av);esimd::simd<sycl::half,16>wh;wh.copy_from(ws+size_t(b)*n+t*16);auto wf=esimd::convert<float>(wh);for(int r=0;r<M;++r){esimd::simd<int32_t,16>di=d.template select<16,1>(r*16);acc.template select<16,1>((j*M+r)*16)+=(esimd::convert<float>(di)*as[b*M+r].x()+as[b*M+r].y())*wf;}}}
  for(int j=0;j<2;++j){int t=t0+j;if(t>=nt)continue;for(int r=0;r<M;++r){esimd::simd<float,16>v=acc.template select<16,1>((j*M+r)*16);v.copy_to(p+(size_t(s)*M+r)*n+t*16);}} });});
 auto red=q.submit([&](sycl::handler&h){h.depends_on(c);h.parallel_for<reduce_kernel<M>>(sycl::range<2>(M,n),[=](sycl::id<2>id){float v=0;for(int s=0;s<S;++s)v+=p[(size_t(s)*M+id[0])*n+id[1]];o[size_t(id[0])*n+id[1]]=v;});});return{c,red};}

template<int M> int run(int k,int n,int iters){sycl::queue q{sycl::gpu_selector_v,sycl::property_list{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}}};int kb=k/32,nt=n/16;size_t qb=size_t(k)*n/2,wb=qb+size_t(kb)*n*2,pqb=size_t(n)*kb*16;
 std::mt19937 g(0xb70);std::uniform_int_distribution<int>q4(-8,7);std::uniform_real_distribution<float>fv(-2,2),sc(.0005,.08);std::vector<uint8_t>pw(wb,0),aw(wb,0);std::vector<float>x(size_t(M)*k);for(auto&v:x)v=fv(g);
 auto*pd=reinterpret_cast<sycl::half*>(pw.data()+qb);auto*ad=reinterpret_cast<sycl::half*>(aw.data()+qb);
 for(int b=0;b<kb;++b)for(int t=0;t<nt;++t)for(int ni=0;ni<16;++ni){int row=t*16+ni;float ds=sc(g);pd[size_t(b)*n+row]=ds;ad[size_t(row)*kb+b]=ds;for(int ki=0;ki<32;++ki){uint8_t sv=uint8_t(q4(g))&15;size_t nib=(((size_t(b)*nt+t)*4+ki/8)*16+ni)*8+ki%8;pw[nib/2]|=sv<<(4*(nib&1));uint8_t bv=sv^8;int si=row*kb+b;uint8_t&z=aw[size_t(si)*16+(ki&15)];z|=bv<<(4*(ki/16));}}
 auto*dw=sycl::malloc_device<uint8_t>(wb,q);auto*daw=sycl::malloc_device<uint8_t>(wb,q);auto*dx=sycl::malloc_device<float>(x.size(),q);auto*dqp=sycl::malloc_device<int8_t>(size_t(M)*(k+kb*4),q);auto*dqj=sycl::malloc_device<int8_t>(size_t(M)*k+size_t(M)*kb*8,q);auto*op=sycl::malloc_device<float>(size_t(M)*n,q);auto*oj=sycl::malloc_device<float>(size_t(M)*n,q);auto*part=sycl::malloc_device<float>(size_t(8)*M*n,q);q.memcpy(dw,pw.data(),wb);q.memcpy(daw,aw.data(),wb);q.memcpy(dx,x.data(),x.size()*4).wait();
 quant_prod<M>(q,dx,dqp,k).wait();auto pe=ggml_sycl_bench_reorder_q4_0_ncols(daw,dqp,op,k,n,M,k+kb*4,n,&q);pe.wait();quant_joint<M>(q,dx,dqj,k).wait();joint<M>(q,dw,dqj,part,oj,k,n).second.wait();std::vector<float>hp(size_t(M)*n),hj(hp.size());q.memcpy(hp.data(),op,hp.size()*4).wait();q.memcpy(hj.data(),oj,hj.size()*4).wait();float md=0;for(size_t i=0;i<hp.size();++i)md=std::max(md,std::fabs(hp[i]-hj[i]));
 std::vector<int8_t>hqp(size_t(M)*(k+kb*4));q.memcpy(hqp.data(),dqp,hqp.size()).wait();float ep=0,ej=0;for(int r=0;r<M;++r)for(int row=0;row<std::min(n,64);++row){float ref=0;for(int b=0;b<kb;++b){auto ds=*reinterpret_cast<const sycl::half2*>(hqp.data()+size_t(r)*(k+kb*4)+k+b*4);float adx=float(ds[0]),wdx=float(ad[size_t(row)*kb+b]);int dot=0;for(int ki=0;ki<32;++ki){uint8_t z=aw[size_t(row*kb+b)*16+(ki&15)];int wv=int((z>>(4*(ki/16)))&15)-8;dot+=wv*int(hqp[size_t(r)*(k+kb*4)+b*32+ki]);}ref+=dot*adx*wdx;}ep=std::max(ep,std::fabs(hp[size_t(r)*n+row]-ref));ej=std::max(ej,std::fabs(hj[size_t(r)*n+row]-ref));}
 std::vector<double>pk,jk,pq,jq,pt,jtms;for(int i=0;i<iters;++i){auto b=std::chrono::steady_clock::now();auto qe=quant_prod<M>(q,dx,dqp,k);auto ke=ggml_sycl_bench_reorder_q4_0_ncols(daw,dqp,op,k,n,M,k+kb*4,n,&q);ke.wait();auto e=std::chrono::steady_clock::now();pq.push_back(us(qe));pk.push_back(us(ke));pt.push_back(std::chrono::duration<double,std::micro>(e-b).count());b=std::chrono::steady_clock::now();auto qj=quant_joint<M>(q,dx,dqj,k);auto je=joint<M>(q,dw,dqj,part,oj,k,n);je.second.wait();e=std::chrono::steady_clock::now();jq.push_back(us(qj));jk.push_back(us(je.first)+us(je.second));jtms.push_back(std::chrono::duration<double,std::micro>(e-b).count());}
 double pkm=med(pk),jkm=med(jk),ptm=med(pt),jtm=med(jtms);std::cout<<"M="<<M<<" K="<<k<<" N="<<n<<" max_abs="<<md<<" prod_cpu_abs="<<ep<<" joint_cpu_abs="<<ej<<" prod_quant_us="<<med(pq)<<" joint_quant_us="<<med(jq)<<" prod_kernel_us="<<pkm<<" joint_kernel_reduce_us="<<jkm<<" kernel_speedup="<<pkm/jkm<<" prod_total_wall_us="<<ptm<<" joint_total_wall_us="<<jtm<<" total_speedup="<<ptm/jtm<<" gate="<<((md<.05f&&ptm/jtm>=1.5)?"PASS":"FAIL")<<"\n";
 for(void*p:{(void*)dw,(void*)daw,(void*)dx,(void*)dqp,(void*)dqj,(void*)op,(void*)oj,(void*)part})sycl::free(p,q);return(md<.05f&&ptm/jtm>=1.5)?0:3;}
int main(int c,char**v){int m=c>1?atoi(v[1]):4,k=c>2?atoi(v[2]):5120,n=c>3?atoi(v[3]):5120,it=c>4?atoi(v[4]):30;return m==4?run<4>(k,n,it):run<8>(k,n,it);}
