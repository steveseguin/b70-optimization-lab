// Original benchmark workload; this is not a model kernel.
#pragma OPENCL FP_CONTRACT OFF
__kernel void bench(__global ushort *p0, __global ushort *p1, __global ushort *p2, __global ushort *p3, __global ushort *p4, __global ushort *p5, __global ushort *p6, __global ushort *p7, __global ushort *p8, __global ushort *p9, __global ushort *p10, __global ushort *p11, __global ushort *p12, __global ushort *p13, __global ushort *p14, __global ushort *p15, __global ushort *p16) {
 size_t j=get_global_id(0); if(j>=2560)return;
 __global ushort* a[17]={p0,p1,p2,p3,p4,p5,p6,p7,p8,p9,p10,p11,p12,p13,p14,p15,p16};
 uint state=((__global uint*)p16)[0]; uint kind=((__global uint*)p16)[1];
 float sign=(state&1)?-1.0f:1.0f;
 float x=as_float(((uint)p0[j])<<16);
 if(kind==0){for(int k=1;k<16;k++)x=x+sign*as_float(((uint)a[k][j])<<16);}
 else {for(int k=0;k<32;k++)x=x+sign*as_float(((uint)p1[(j+k)%2560])<<16)*as_float(((uint)p2[k])<<16);}

 uint bits=as_uint(x); p0[j]=(ushort)((bits+0x7fff+((bits>>16)&1))>>16);
}
