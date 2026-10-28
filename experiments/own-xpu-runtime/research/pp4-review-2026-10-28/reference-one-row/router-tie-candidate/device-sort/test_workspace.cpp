#include "reference_sort_workspace.hpp"
#include <algorithm>
#include <array>
#include <fstream>
#include <iostream>
#include <numeric>
#include <random>
#include <stdexcept>
namespace rr=router_reference_sort;
static void need(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
int main(int argc,char** argv){try{
 need(argc==2,"packed probe input required");
 std::ifstream input(argv[1],std::ios::binary);
 std::mt19937 random(0x117b70);int cases=0;
 for(int test=0;test<12512;++test){
  std::array<float,512> scores{};
  int size=512;
  if(test<512){input.read(reinterpret_cast<char*>(scores.data()),2048);need(input.gcount()==2048,"actual input extent");}
  else{size=test%513;for(float& v:scores)v=float(random()%((test%7)?17:100000));}
  std::array<int,514> actual;actual.fill(-777);
  std::array<int,512> expected;std::iota(expected.begin(),expected.end(),0);
  std::array<rr::Frame,20> frames;frames.fill({-777,-777,-777});
  const auto before=[&](int a,int b){return scores[a]>scores[b];};
  if(test%3==0){
   const int depth=test%4;
   auto compare=__gnu_cxx::__ops::__iter_comp_iter(before);
   std::__introsort_loop(expected.begin(),expected.begin()+size,depth,compare);
   std::__final_insertion_sort(expected.begin(),expected.begin()+size,compare);
   need(rr::sort_workspace(scores.data(),actual.data()+1,size,depth,frames.data()+1),"workspace sort");
  }else{
   std::sort(expected.begin(),expected.begin()+size,before);
   need(rr::sort_indices_workspace(scores.data(),actual.data()+1,size,frames.data()+1),"workspace sort");
  }
  need(std::equal(expected.begin(),expected.begin()+size,actual.begin()+1),"full permutation");
  need(actual[0]==-777&&actual[size+1]==-777,"index canaries");
  for(int at:{0,19})need(frames[at].first==-777&&frames[at].last==-777&&frames[at].depth==-777,"frame canaries");
  ++cases;
 }
 need(input.peek()==EOF,"no input tail");
 std::cout<<"{\"passed\":true,\"cases\":"<<cases<<",\"gpu_executed\":false,\"index_and_frame_canaries\":true}\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
