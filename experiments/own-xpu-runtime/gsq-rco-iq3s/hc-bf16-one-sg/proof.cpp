#include "policy.hpp"
#include <array>
#include <iostream>
#include <vector>
size_t checks=0;
void need(bool v,const char*s){++checks;if(!v)throw std::runtime_error(s);}
int main(){try{
 for(size_t rows:{size_t(4),size_t(320)}){
  gsq_hc_one_sg::policy(30u,rows,10240,30u,30u,32,0u);
  std::vector<unsigned>a(rows),b(rows);
  for(size_t group=0;group<(rows+3)/4;++group)for(size_t sg=0;sg<4;++sg){size_t logical=group*4+sg;if(logical<rows)++a[logical];}
  for(size_t group=0;group<rows;++group){size_t logical=group;++b[logical];}
  for(size_t row=0;row<rows;++row){need(a[row]==1&&b[row]==1,"exact row coverage");need(row*20480+20480<=rows*20480,"row extent");need(row*2+2<=rows*2,"output extent");}
  for(size_t row:{size_t(0),rows/2,rows-1})for(size_t lane=0;lane<32;++lane)for(size_t tile=0;tile<40;++tile){
   size_t old_row=(row/4)*4+row%4,new_row=row;
   size_t old_k=lane*8+tile*256,new_k=lane*8+tile*256;
   need(old_row*20480+2*old_k==new_row*20480+2*new_k,"same BF16 vector address");
   need(old_k==new_k&&new_k+8<=10240,"same ordered eight inputs");
  }
  std::array<size_t,7> good{30,rows,10240,30,30,32,0};
  for(size_t i=0;i<good.size();++i){auto bad=good;++bad[i];bool refused=false;try{gsq_hc_one_sg::policy(bad[0],bad[1],bad[2],bad[3],bad[4],unsigned(bad[5]),bad[6]);}catch(const std::invalid_argument&){refused=true;}need(refused,"narrow admission");}
 }
 // Subgroup reduction topology is independent of row/workgroup mapping.
 for(unsigned width=1;width<32;width*=2)for(unsigned lane=0;lane<32;++lane){need((lane+width)%32<32,"tree source lane");need((lane%(2*width)==0)==((lane&(2*width-1))==0),"same active tree roots");}
 std::cout<<"{\"passed\":true,\"checks\":"<<checks<<",\"scope\":\"CPU geometry/address/admission only; unchanged arithmetic body established separately by source identity; no Device\"}\n";
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
