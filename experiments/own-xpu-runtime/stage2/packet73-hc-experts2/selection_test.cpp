#include "p49d_submit.hpp"
#include <iostream>
int main(int argc,char**argv){try{
 if(argc!=4)throw std::invalid_argument("selection path and expected HC/expert choices required");
 p49d::Selection s;s.load(argv[1]);
 if(s.choices.at("hc_gate")!=argv[2]||s.choices.at("experts")!=argv[3]||s.choices.at("miss")!="batch")throw std::invalid_argument("packet73 selection lost");
 if(s.draft.at("fuse_hc_a_low")!="packet59"||s.draft.at("fuse_hc_f_mix")!="packet59")throw std::invalid_argument("draft HC lost");
 std::cout<<"selection PASS\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
