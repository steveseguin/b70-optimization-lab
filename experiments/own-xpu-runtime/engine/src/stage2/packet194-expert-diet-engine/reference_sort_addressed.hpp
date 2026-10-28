#pragma once
#include "reference_sort.hpp"
// Research candidate: reproduce the registered GCC 13 libstdc++ sort's *whole*
// index permutation, including its implementation-specific equal-key order.
// Indexed, iterative implementation of the observed median/introsort/insertion/
// heap operations. See PROVENANCE.txt. No runtime integration is implied.
namespace router_reference_sort_addressed {
constexpr int capacity = 512;
constexpr int insertion_limit = 16;
constexpr int maximum_depth = 18; // 2 * floor(log2(512)).
struct Counts { int partitions=0, heap_fallbacks=0, maximum_pending=0; };
using Frame=router_reference_sort::Frame;

template<class IndexPtr> inline void exchange(IndexPtr index, int a, int b) {
    const int saved=index[a]; index[a]=index[b]; index[b]=saved;
}
template<class ScorePtr> inline bool before(ScorePtr score, int a, int b) { return score[a]>score[b]; }

template<class ScorePtr,class IndexPtr> inline int split(ScorePtr score, IndexPtr index, int first, int last) {
    const int a=first+1, b=first+(last-first)/2, c=last-1;
    int chosen;
    if (before(score,index[a],index[b])) {
        if (before(score,index[b],index[c])) chosen=b;
        else chosen=before(score,index[a],index[c])?c:a;
    } else if (before(score,index[a],index[c])) chosen=a;
    else chosen=before(score,index[b],index[c])?c:b;
    exchange(index,first,chosen);
    int left=first+1, right=last;
    for (;;) {
        while (before(score,index[left],index[first])) ++left;
        --right;
        while (before(score,index[first],index[right])) --right;
        if (left>=right) return left;
        exchange(index,left,right);
        ++left;
    }
}

template<class ScorePtr,class IndexPtr> inline void sift(ScorePtr score, IndexPtr index, int first, int hole, int size, int value) {
    const int top=hole;
    int child=hole;
    while (child<(size-1)/2) {
        child=2*(child+1);
        if (before(score,index[first+child],index[first+child-1])) --child;
        index[first+hole]=index[first+child];
        hole=child;
    }
    if ((size&1)==0 && child==(size-2)/2) {
        child=2*(child+1);
        index[first+hole]=index[first+child-1];
        hole=child-1;
    }
    int parent=(hole-1)/2;
    while (hole>top && before(score,index[first+parent],value)) {
        index[first+hole]=index[first+parent];
        hole=parent;
        parent=(hole-1)/2;
    }
    index[first+hole]=value;
}

template<class ScorePtr,class IndexPtr> inline void heap_sort(ScorePtr score, IndexPtr index, int first, int last) {
    const int size=last-first;
    if (size<2) return;
    for (int parent=(size-2)/2;;--parent) {
        sift(score,index,first,parent,size,index[first+parent]);
        if (parent==0) break;
    }
    for (int remaining=size-1; remaining>0; --remaining) {
        const int saved=index[first+remaining];
        index[first+remaining]=index[first];
        sift(score,index,first,0,remaining,saved);
    }
}

// The first partitioned block supplies a sentinel for all later insertion work.
template<class ScorePtr,class IndexPtr> inline void insertion_finish(ScorePtr score, IndexPtr index, int count) {
    const int initial=count<insertion_limit?count:insertion_limit;
    for (int at=1;at<initial;++at) {
        const int value=index[at];
        if (before(score,value,index[0])) {
            for (int j=at;j>0;--j) index[j]=index[j-1];
            index[0]=value;
        } else {
            int hole=at;
            while (before(score,value,index[hole-1])) {
                index[hole]=index[hole-1]; --hole;
            }
            index[hole]=value;
        }
    }
    for (int at=initial;at<count;++at) {
        const int value=index[at];
        int hole=at;
        while (before(score,value,index[hole-1])) {
            index[hole]=index[hole-1]; --hole;
        }
        index[hole]=value;
    }
}


template<class ScorePtr,class IndexPtr,class FramePtr> inline bool sort_workspace(ScorePtr score,IndexPtr index,int count,int depth,FramePtr pending) {
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
            pending[used].first=first;pending[used].last=cut;pending[used].depth=depth;++used;
            first=cut;
        }
        if(!used) break;
        --used;first=pending[used].first;last=pending[used].last;depth=pending[used].depth;
    }
    insertion_finish(score,index,count);
    return true;
}
template<class ScorePtr,class IndexPtr,class FramePtr> inline bool sort_indices_workspace(ScorePtr score,IndexPtr index,int count,FramePtr frames) {
    if(count<0 || count>capacity) return false;
    int log=0;
    for(int n=count;n>1;n>>=1) ++log;
    return sort_workspace(score,index,count,2*log,frames);
}
}
