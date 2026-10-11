// CPU screening only: never link SYCL or execute a device program.
#ifndef HOST_ONLY
#error This timing probe must be HOST_ONLY
#endif
#define main fixture_runner_main
#ifdef TIMING_V1
#include "../packet15-nongemv/runner.cpp"
#else
#include "runner.cpp"
#endif
#undef main
#include <chrono>
int main(int argc,char**argv){
 if(argc!=3)return 2;
 std::ofstream out(argv[2]);require(bool(out),"timing output open");
 std::vector<float> scratch(ng::reference::scratch_floats);
 for(int repeat=0;repeat<3;++repeat){
  std::ifstream list(fs::path(argv[1])/"cases.txt");require(bool(list),"case list open");std::string name;
  while(list>>name){Fixture f(fs::path(argv[1])/name);auto args=f.args();
   for(int r=0;r<f.s.tokens;++r){auto start=std::chrono::steady_clock::now();
    ng::reference::row(f.s,args,r,scratch.data());
    double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
    out<<"{\"case\":\""<<name<<"\",\"repeat\":"<<repeat<<",\"row\":"<<r<<",\"seconds\":"<<seconds<<"}\n";
   }
  }
 }
 return !out;
}
