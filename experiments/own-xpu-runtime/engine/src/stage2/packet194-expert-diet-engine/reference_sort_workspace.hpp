#pragma once
#include "reference_sort.hpp"
// Identical control flow to sort_with_depth, with explicit caller-owned frames.
// The supplied frame array must have maximum_depth entries and not alias indices.
namespace router_reference_sort {
inline bool sort_workspace(const float* score,int* index,int count,int depth,Frame* pending) {
    if(count<0 || count>capacity || depth<0 || depth>maximum_depth) return false;
    if(count && (!score || !index || !pending)) return false;
    constexpr float finite_max=3.40282346638528859812e38f;
    for(int i=0;i<count;++i)
        if(!(score[i]<=finite_max && score[i]>=-finite_max)) return false;
    for(int i=0;i<count;++i) index[i]=i;
    if(count<2) return true;
    int used=0,first=0,last=count;
    for(;;) {
        while(last-first>insertion_limit) {
            if(!depth) { heap_sort(score,index,first,last); break; }
            --depth;
            const int cut=split(score,index,first,last);
            if(cut<=first || cut>=last || used==maximum_depth) return false;
            pending[used++]={first,cut,depth};
            first=cut;
        }
        if(!used) break;
        const Frame next=pending[--used];
        first=next.first;last=next.last;depth=next.depth;
    }
    insertion_finish(score,index,count);
    return true;
}
inline bool sort_indices_workspace(const float* score,int* index,int count,Frame* frames) {
    if(count<0 || count>capacity) return false;
    int log=0;
    for(int n=count;n>1;n>>=1) ++log;
    return sort_workspace(score,index,count,2*log,frames);
}
}
