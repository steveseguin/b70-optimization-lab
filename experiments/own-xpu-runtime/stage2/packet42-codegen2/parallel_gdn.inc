inline float lane_tree(sycl::sub_group sg,float v){
 unsigned lane=sg.get_local_linear_id();
 for(unsigned stride=1;stride<32;stride*=2){float right=sycl::select_from_group(sg,v,sycl::id<1>((lane+stride)%32));if(lane%(2*stride)==0)v=v+right;}
 return sycl::select_from_group(sg,v,sycl::id<1>(0));
}
template<int Flags> inline void gdn_device(ng::Shape s,ng::Args a,sycl::nd_item<1> it){
 auto sg=it.get_sub_group();int lane=sg.get_local_linear_id(),g=it.get_group_linear_id();
 Guard t;int blocked=lane==0?int(!a.i(18)[0]||t.error(a)):0;
 if(sycl::select_from_group(sg,blocked,sycl::id<1>(0)))return;
 int pos=a.i(17)[0];if(pos<0||pos>s.capacity-1){if(g==0&&lane==0)t.fail(a);return;}
 int h=g/128,j=g%128,key=(Flags&4)?h%16:h/3,state=g*128;
 for(int r=0;r<1;++r){int qb=r*10240+key*128,kb=qb+2048;float q[4],k[4],v[4],qs=0.f,ks=0.f;
  for(int z=0;z<4;++z){q[z]=a.b(0,qb+4*lane+z);k[z]=a.b(0,kb+4*lane+z);qs=qs+q[z]*q[z];ks=ks+k[z]*k[z];}
  float qn=detmath::sqrt(lane_tree(sg,qs)+1e-6f),kn=detmath::sqrt(lane_tree(sg,ks)+1e-6f);
  float gate=a.b(1,r*48+h)+a.weight(4,h,Flags),sp=gate<20.f?detmath::log(1.f+detmath::exp(gate)):gate,av=(Flags&2)?a.f(3)[h]:-detmath::exp(a.weight(3,h,Flags));
  float decay=detmath::exp(av*sp),pred=0.f;
  for(int z=0;z<4;++z){q[z]=(q[z]/qn)/detmath::sqrt(float(128));k[z]=k[z]/kn;v[z]=a.b(r?7:5,state+4*lane+z)*decay;pred=pred+v[z]*k[z];}
  pred=lane_tree(sg,pred);float delta=(a.b(0,r*10240+4096+h*128+j)-pred)*ng::sigmoid(a.b(2,r*48+h)),y=0.f;
  for(int z=0;z<4;++z){v[z]=v[z]+delta*k[z];y=y+v[z]*q[z];}
  y=lane_tree(sg,y);if(lane==0)a.put(6,(r*48+h)*128+j,y);
  for(int z=0;z<4;++z)a.put(7,state+4*lane+z,v[z]);
  // Next token reads the BF16-rounded state, including when input/output alias.
  // Single token: no later state read exists in this kernel.
 }
}
