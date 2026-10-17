#pragma once
namespace pipeline::native38 {
// One pending rank0 tile, plus one private future tile. Rank1 verifies the
// current tile while rank0 computes the future tile. No unverified carry is
// copied into canonical state. A first-input miss repairs before rank1 starts.
inline Result run_depth2(Backend&b,const Config&c,const std::string&forced){
 require(c.draft_rank==1&&(c.mode==2||c.mode==3),"depth71 native draft mode");
 Result out;out.start=clock_now();const int length=c.prompt.size();
 auto fixture=[&](int pos){return std::max(0,pos-length+2);};
 auto ordinary=[&](int rank,int token,int pos){return b.call(rank,half,token,pos,fixture(pos));};
 auto valid=[&](int token){return token>=0&&token<c.vocab;};
 auto emit=[&](int token){require(valid(token),"depth71 verified token bounds");out.tokens.push_back(token);out.rows.push_back({token,clock_now()});if(out.rows.size()==1)out.prompt_ms=(out.rows.back().stamp-out.start)*1000;return int(out.tokens.size())>=c.count||std::find(c.eos.begin(),c.eos.end(),token)!=c.eos.end();};
 bool done=false,current=false;int current_first=-1,current_second=-1;
 for(int pos=0;pos<length;++pos){ordinary(0,c.prompt[pos],pos);b.call(0,accept);b.handover();
  if(c.mode==3&&pos)b.call(1,draft,c.prompt[pos],pos,0);
  auto result=ordinary(1,c.prompt[pos],pos);b.call(1,accept);if(pos+1==length)done=emit(result.token);
 }
 int pos=length;
 while(!done){double cycle=clock_now();int token=out.tokens.back(),remaining=c.count-int(out.tokens.size());
  if(current){bool hit=current_first==token;++out.guesses_count;out.guess_sequence.push_back(current_first);(hit?out.hits:out.misses)++;
   out.guesses.push_back({pos,current_first,token,hit,(clock_now()-cycle)*1000});
   if(!hit||remaining<2){b.call(0,15,0);current=false;}
  }
  if(remaining<2){
   if(c.mode==3)b.start(1,16,token,pos,0);
   ordinary(0,token,pos);b.call(0,accept);if(c.mode==3)b.wait(1);b.handover();auto result=ordinary(1,token,pos);b.call(1,accept);done=emit(result.token);++pos;continue;
  }
  int second=current?current_second:-1,next_first=-1,next_second=-1;
  if(c.mode==3){auto d=b.call(1,19,token,pos,1,0,second);second=d.token;next_first=d.reserved[0];next_second=d.reserved[1];}
  else {size_t i=out.tokens.size();if(second<0&&i<c.script.size())second=c.script[i];if(i+1<c.script.size())next_first=c.script[i+1];if(i+2<c.script.size())next_second=c.script[i+2];}
  if(!valid(second)){
   // Disabled/failed draft degrades to an unchanged target row. Provider errors
   // never authorize a guessed output or a restart.
   ordinary(0,token,pos);b.call(0,accept);b.handover();auto result=ordinary(1,token,pos);b.call(1,accept);done=emit(result.token);++pos;continue;
  }
  if(!current){if(forced=="second")second=(second+1)%c.vocab;b.call(0,14,token,pos,fixture(pos),0,second);current=true;current_first=token;current_second=second;}
  bool future=remaining>=4&&valid(next_first)&&valid(next_second);
  if(future&&forced=="first")next_first=(next_first+1)%c.vocab;
  if(future&&forced=="second")next_second=(next_second+1)%c.vocab;
  b.handover();b.start(1,14,token,pos,fixture(pos),0,second);
  if(future)b.start(0,14,next_first,pos+2,fixture(pos+2),1,next_second);
  auto result=b.wait(1);if(future)b.wait(0);
  done=emit(result.token);bool hit=second==result.token;
  ++out.guesses_count;out.guess_sequence.push_back(second);(hit?out.hits:out.misses)++;
  out.guesses.push_back({pos+1,second,result.token,hit,(clock_now()-cycle)*1000});
  if(done||!hit){
   if(future)b.call(0,18);b.call(0,15,1);b.call(1,15,1);current=false;++pos;continue;
  }
  if(c.mode==3)b.call(1,17,second,pos+1,0);
  b.call(1,15,2);b.call(0,15,2);current=future;current_first=next_first;current_second=next_second;
  done=emit(result.reserved[0]);pos+=2;
 }
 if(current)b.call(0,15,0);
 if(c.dumps){b.call(0,dump,0,pos);b.call(1,dump,0,pos);}
 out.end=clock_now();b.call(1,0);return out;
}
}
