// This translation unit emits expert kernels only. Built as separate AOT DSOs.
// Rename all kernel namespaces for the normal control to prevent SYCL kernel-ID
// and ELF weak-symbol coalescing between the default and LARGE device images.
#ifdef P115_NORMAL
#define p90exp p115normal90
#define p100 p115normal100
#define p49dvirtual p115normal49
#define P115_ENTRY normal
#else
#define p90exp p115large90
#define p100 p115large100
#define p49dvirtual p115large49
#define P115_ENTRY large
#endif
#include "kernels/candidates.hpp"
#include "expert_image.hpp"
namespace p115_image {
template<class K>sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d,unsigned rows,unsigned count,unsigned experts) {
    K k;k.rows=rows;k.count=count;k.experts=experts;return k.submit(q,p,d);
}
sycl::event P115_ENTRY(unsigned arm,bool down,sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d,unsigned rows,unsigned count,unsigned experts) {
    if(down){
#ifndef P115_NORMAL
        if(arm==2)return submit<p115down::Kernel<>>(q,p,d,rows,count,experts);
#endif
        return submit<p100::Kernel<2>>(q,p,d,rows,count,experts);
    }
#ifndef P115_NORMAL
    if(arm==1)return submit<p115e3::Kernel<>>(q,p,d,rows,count,experts);
    if(arm==3)return submit<p102::Kernel<2,true>>(q,p,d,rows,count,experts);
    if(arm==4)return submit<p115e5::Kernel<>>(q,p,d,rows,count,experts);
#endif
    return submit<p90exp::Kernel<iq3::Type::IQ2_S,2560,64,false,true>>(q,p,d,rows,count,experts);
}
}
