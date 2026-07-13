#include "mmvq.hpp"
#include <sycl/ext/intel/esimd.hpp>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <random>
#include <vector>

namespace esimd = sycl::ext::intel::esimd;
namespace xmx = sycl::ext::intel::esimd::xmx;

template<int M> class slm_joint2_kernel;
template<int M> class prod_quant_kernel_v3;
template<int M> class joint_quant_kernel_v3;

static double event_us(const sycl::event & e) {
    return double(e.get_profiling_info<sycl::info::event_profiling::command_end>() -
                  e.get_profiling_info<sycl::info::event_profiling::command_start>()) / 1000.0;
}

static double median(std::vector<double> v) {
    std::sort(v.begin(), v.end());
    return v[v.size()/2];
}

struct q8_meta_v3 { float d; float sum; };

template<int M>
sycl::event quant_prod(sycl::queue & q, const float * x, int8_t * out, int k) {
    const int kb = k/32;
    return q.submit([&](sycl::handler & h) {
        h.parallel_for<prod_quant_kernel_v3<M>>(
            sycl::nd_range<1>(M*kb*32, 32), [=](sycl::nd_item<1> it)
            [[sycl::reqd_sub_group_size(32)]] {
                int b=it.get_group(0), r=b/kb, ki=b%kb, l=it.get_local_id(0);
                float v=x[size_t(r)*k+ki*32+l];
                float a=sycl::reduce_over_group(it.get_sub_group(),sycl::fabs(v),sycl::maximum<float>());
                float sum=sycl::reduce_over_group(it.get_sub_group(),v,sycl::plus<float>());
                float d=a ? a/127.f : 0.f;
                out[size_t(r)*(k+kb*4)+ki*32+l]=d ? int8_t(sycl::round(v/d)) : 0;
                if(l==0) *reinterpret_cast<sycl::half2 *>(out+size_t(r)*(k+kb*4)+k+ki*4)=
                    sycl::half2(sycl::half(d),sycl::half(sum));
            });
    });
}

template<int M>
sycl::event quant_joint(sycl::queue & q, const int8_t * canonical, int8_t * out, int k) {
    const int kb=k/32;
    return q.submit([&](sycl::handler & h) {
        h.parallel_for<joint_quant_kernel_v3<M>>(
            sycl::nd_range<1>(M*kb*32,32), [=](sycl::nd_item<1> it)
            [[sycl::reqd_sub_group_size(32)]] {
                int b=it.get_group(0),r=b/kb,ki=b%kb,l=it.get_local_id(0);
                int qi=int(canonical[size_t(r)*(k+kb*4)+ki*32+l]);
                out[(size_t(ki)*M+r)*32+l]=int8_t(qi);
                if(l==0) {
                    auto ds=*reinterpret_cast<const sycl::half2 *>(
                        canonical+size_t(r)*(k+kb*4)+k+ki*4);
                    reinterpret_cast<q8_meta_v3 *>(out+size_t(k)*M)[ki*M+r]=
                        {float(ds[0]),float(ds[1])};
                }
            });
    });
}

// One work-group owns two adjacent N16 tiles. Eight ESIMD work-items split K,
// stage only their 2*M*16 FP32 accumulators in SLM, then work-item zero reduces
// and writes final output. This retains the production comparator's exact pack
// while removing both the global partial buffer and the reduction kernel.
template<int M>
sycl::event slm_joint2(sycl::queue & q, const uint8_t * w, const int8_t * a,
                       float * o, int k, int n) {
    constexpr int S=8;
    constexpr int J=2;
    constexpr int SLM_FLOATS=S*J*M*16;
    const int kb=k/32, nt=n/16, jt=(nt+J-1)/J;
    const size_t qb=size_t(k)*n/2;
    auto * ws=reinterpret_cast<const sycl::half *>(w+qb);
    auto * as=reinterpret_cast<const q8_meta_v3 *>(a+size_t(k)*M);
    return q.submit([&](sycl::handler & h) {
        h.parallel_for<slm_joint2_kernel<M>>(
            sycl::nd_range<2>(sycl::range<2>(jt,S),sycl::range<2>(1,S)),
            [=](sycl::nd_item<2> it) [[intel::sycl_explicit_simd]] {
                esimd::slm_init<SLM_FLOATS*sizeof(float)>();
                const int pair=int(it.get_group(0));
                const int s=int(it.get_local_id(1));
                const int t0=pair*J;
                const int b0=kb*s/S,b1=kb*(s+1)/S;
                esimd::simd<float,M*J*16> acc(0.f);
                for(int b=b0;b<b1;++b) {
                    esimd::simd<uint32_t,M*8> av;
                    av.copy_from(reinterpret_cast<const uint32_t *>(a)+size_t(b)*M*8);
                    for(int j=0;j<J;++j) {
                        const int t=t0+j;
                        if(t>=nt) continue;
                        esimd::simd<uint32_t,64> bv;
                        bv.copy_from(reinterpret_cast<const uint32_t *>(w)+(size_t(b)*nt+t)*64);
                        esimd::simd<int32_t,M*16> d;
                        if constexpr(M<=8) {
                            d=xmx::dpas<8,M,int32_t,uint32_t,uint32_t,
                                xmx::dpas_argument_type::u4,xmx::dpas_argument_type::s8>(bv,av);
                        } else {
                            esimd::simd<uint32_t,64> av0=av.template select<64,1>(0);
                            esimd::simd<uint32_t,(M-8)*8> av1=av.template select<(M-8)*8,1>(64);
                            d.template select<128,1>(0)=xmx::dpas<8,8,int32_t,uint32_t,uint32_t,
                                xmx::dpas_argument_type::u4,xmx::dpas_argument_type::s8>(bv,av0);
                            d.template select<(M-8)*16,1>(128)=xmx::dpas<8,M-8,int32_t,uint32_t,uint32_t,
                                xmx::dpas_argument_type::u4,xmx::dpas_argument_type::s8>(bv,av1);
                        }
                        esimd::simd<sycl::half,16> wh;
                        wh.copy_from(ws+size_t(b)*n+t*16);
                        auto wf=esimd::convert<float>(wh);
                        for(int r=0;r<M;++r) {
                            esimd::simd<int32_t,16> di=d.template select<16,1>(r*16);
                            auto term=(esimd::convert<float>(di)*as[b*M+r].d-8.f*as[b*M+r].sum)*wf;
                            acc.template select<16,1>((j*M+r)*16)+=term;
                        }
                    }
                }
                for(int j=0;j<J;++j) for(int r=0;r<M;++r) {
                    const uint32_t off=uint32_t((((s*J+j)*M+r)*16)*sizeof(float));
                    esimd::slm_block_store<float,16>(off,acc.template select<16,1>((j*M+r)*16));
                }
                esimd::barrier();
                if(s==0) {
                    for(int j=0;j<J;++j) {
                        const int t=t0+j;
                        if(t>=nt) continue;
                        for(int r=0;r<M;++r) {
                            esimd::simd<float,16> sum(0.f);
#pragma unroll
                            for(int p=0;p<S;++p) {
                                const uint32_t off=uint32_t((((p*J+j)*M+r)*16)*sizeof(float));
                                sum+=esimd::slm_block_load<float,16>(off);
                            }
                            sum.copy_to(o+size_t(r)*n+t*16);
                        }
                    }
                }
            });
    });
}

template<int M>
int run(int k,int n,int iters) {
    sycl::queue q{sycl::gpu_selector_v,sycl::property_list{
        sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}}};
    int kb=k/32,nt=n/16;
    size_t qb=size_t(k)*n/2,wb=qb+size_t(kb)*n*2;
    std::mt19937 g(0xb70);
    std::uniform_int_distribution<int> q4(-8,7);
    std::uniform_real_distribution<float> fv(-2,2),sc(.0005,.08);
    std::vector<uint8_t> pw(wb,0),aw(wb,0);
    std::vector<float> x(size_t(M)*k);
    for(auto & v:x) v=fv(g);
    auto * pd=reinterpret_cast<sycl::half *>(pw.data()+qb);
    auto * ad=reinterpret_cast<sycl::half *>(aw.data()+qb);
    for(int b=0;b<kb;++b) for(int t=0;t<nt;++t) for(int ni=0;ni<16;++ni) {
        int row=t*16+ni; float ds=sc(g); pd[size_t(b)*n+row]=ds; ad[size_t(row)*kb+b]=ds;
        for(int ki=0;ki<32;++ki) {
            uint8_t sv=uint8_t(q4(g))&15;
            uint8_t bv=sv^8;
            size_t nib=(((size_t(b)*nt+t)*4+ki/8)*16+ni)*8+ki%8;
            pw[nib/2]|=bv<<(4*(nib&1));
            int si=row*kb+b;
            uint8_t & z=aw[size_t(si)*16+(ki&15)]; z|=bv<<(4*(ki/16));
        }
    }
    auto * dw=sycl::malloc_device<uint8_t>(wb,q);
    auto * daw=sycl::malloc_device<uint8_t>(wb,q);
    auto * dx=sycl::malloc_device<float>(x.size(),q);
    auto * dqp=sycl::malloc_device<int8_t>(size_t(M)*(k+kb*4),q);
    auto * dqj=sycl::malloc_device<int8_t>(size_t(M)*k+size_t(M)*kb*sizeof(q8_meta_v3),q);
    auto * op=sycl::malloc_device<float>(size_t(M)*n,q);
    auto * oj=sycl::malloc_device<float>(size_t(M)*n,q);
    q.memcpy(dw,pw.data(),wb); q.memcpy(daw,aw.data(),wb);
    q.memcpy(dx,x.data(),x.size()*4).wait();

    quant_prod<M>(q,dx,dqp,k).wait();
    ggml_sycl_bench_reorder_q4_0_ncols(daw,dqp,op,k,n,M,k+kb*4,n,&q).wait();
    quant_joint<M>(q,dqp,dqj,k).wait(); slm_joint2<M>(q,dw,dqj,oj,k,n).wait();
    std::vector<float> hp(size_t(M)*n),hj(hp.size());
    q.memcpy(hp.data(),op,hp.size()*4).wait(); q.memcpy(hj.data(),oj,hj.size()*4).wait();
    float md=0,mrel=0; size_t mdi=0; double mse=0;
    for(size_t i=0;i<hp.size();++i) {
        float delta=std::fabs(hp[i]-hj[i]);
        if(delta>md) { md=delta; mdi=i; }
        mrel=std::max(mrel,delta/std::max(1.f,std::fabs(hp[i])));
        mse+=double(delta)*delta;
    }

    std::vector<int8_t> hqp(size_t(M)*(k+kb*4)); q.memcpy(hqp.data(),dqp,hqp.size()).wait();
    std::vector<int8_t> hqj(size_t(M)*k+size_t(M)*kb*sizeof(q8_meta_v3));
    q.memcpy(hqj.data(),dqj,hqj.size()).wait();
    float meta_err=0,d_meta_err=0,sum_meta_err=0; int quant_err=0;
    auto * hm=reinterpret_cast<const q8_meta_v3 *>(hqj.data()+size_t(M)*k);
    for(int r=0;r<M;++r) for(int b=0;b<kb;++b) {
        auto ds=*reinterpret_cast<const sycl::half2 *>(hqp.data()+size_t(r)*(k+kb*4)+k+b*4);
        d_meta_err=std::max(d_meta_err,std::fabs(hm[b*M+r].d-float(ds[0])));
        sum_meta_err=std::max(sum_meta_err,std::fabs(hm[b*M+r].sum-float(ds[1])));
        meta_err=std::max(d_meta_err,sum_meta_err);
        for(int l=0;l<32;++l) quant_err=std::max(quant_err,std::abs(
            int(hqj[(size_t(b)*M+r)*32+l])-int(hqp[size_t(r)*(k+kb*4)+b*32+l])));
    }
    float ep=0,ej=0,epp=0,ejp=0;
    for(int r=0;r<M;++r) for(int row=0;row<std::min(n,64);++row) {
        float ref=0,ref_prod=0;
        for(int b=0;b<kb;++b) {
            auto ds=*reinterpret_cast<const sycl::half2 *>(hqp.data()+size_t(r)*(k+kb*4)+k+b*4);
            float adx=float(ds[0]),sumx=float(ds[1]),wdx=float(ad[size_t(row)*kb+b]); int dot=0,udot=0;
            for(int ki=0;ki<32;++ki) {
                uint8_t z=aw[size_t(row*kb+b)*16+(ki&15)];
                int wv=int((z>>(4*(ki/16)))&15)-8;
                dot+=wv*int(hqp[size_t(r)*(k+kb*4)+b*32+ki]);
                udot+=(wv+8)*int(hqp[size_t(r)*(k+kb*4)+b*32+ki]);
            }
            ref+=dot*adx*wdx;
            ref_prod+=wdx*(udot*adx-8.f*sumx);
        }
        ep=std::max(ep,std::fabs(hp[size_t(r)*n+row]-ref));
        ej=std::max(ej,std::fabs(hj[size_t(r)*n+row]-ref));
        epp=std::max(epp,std::fabs(hp[size_t(r)*n+row]-ref_prod));
        ejp=std::max(ejp,std::fabs(hj[size_t(r)*n+row]-ref_prod));
    }

    std::vector<double> pk,jk,pq,jq,pt,jt;
    for(int i=0;i<iters;++i) {
        auto b=std::chrono::steady_clock::now(); auto qe=quant_prod<M>(q,dx,dqp,k);
        auto ke=ggml_sycl_bench_reorder_q4_0_ncols(daw,dqp,op,k,n,M,k+kb*4,n,&q); ke.wait();
        auto e=std::chrono::steady_clock::now(); pq.push_back(event_us(qe)); pk.push_back(event_us(ke));
        pt.push_back(std::chrono::duration<double,std::micro>(e-b).count());
        b=std::chrono::steady_clock::now(); auto qc=quant_prod<M>(q,dx,dqp,k);
        auto qj=quant_joint<M>(q,dqp,dqj,k);
        auto je=slm_joint2<M>(q,dw,dqj,oj,k,n); je.wait(); e=std::chrono::steady_clock::now();
        jq.push_back(event_us(qc)+event_us(qj)); jk.push_back(event_us(je));
        jt.push_back(std::chrono::duration<double,std::micro>(e-b).count());
    }
    double pkm=median(pk),jkm=median(jk),ptm=median(pt),jtm=median(jt);
    std::cout<<"M="<<M<<" K="<<k<<" N="<<n<<" max_abs="<<md
             <<" max_rel="<<mrel<<" rms_delta="<<std::sqrt(mse/hp.size())
             <<" max_at="<<mdi<<" prod_at_max="<<hp[mdi]<<" slm_at_max="<<hj[mdi]
             <<" prod_cpu_abs="<<ep<<" slm_cpu_abs="<<ej
             <<" prod_formula_abs="<<epp<<" slm_formula_abs="<<ejp
             <<" meta_abs="<<meta_err
             <<" d_meta_abs="<<d_meta_err<<" sum_meta_abs="<<sum_meta_err
             <<" quant_int_abs="<<quant_err
             <<" prod_quant_us="<<median(pq)<<" slm_quant_us="<<median(jq)
             <<" prod_kernel_us="<<pkm<<" slm_joint2_kernel_us="<<jkm
             <<" kernel_speedup="<<pkm/jkm<<" prod_total_wall_us="<<ptm
             <<" slm_total_wall_us="<<jtm<<" total_speedup="<<ptm/jtm
             <<" gate="<<((md<.05f&&ptm/jtm>=1.5)?"PASS":"FAIL")<<"\n";
    for(void * p:{(void*)dw,(void*)daw,(void*)dx,(void*)dqp,(void*)dqj,(void*)op,(void*)oj}) sycl::free(p,q);
    return(md<.05f&&ptm/jtm>=1.5)?0:3;
}

int main(int c,char ** v) {
    int m=c>1?atoi(v[1]):6,k=c>2?atoi(v[2]):5120,n=c>3?atoi(v[3]):5120,it=c>4?atoi(v[4]):30;
    switch(m) {
        case 4:return run<4>(k,n,it); case 6:return run<6>(k,n,it); case 8:return run<8>(k,n,it);
        case 9:return run<9>(k,n,it); case 16:return run<16>(k,n,it);
        default:std::cerr<<"M must be one of 4, 6, 8, 9, 16\n";return 64;
    }
}
