; ------------------------------------------------
; OCL_asm6c8399b4fe53f40f_simd32_entry_0006.visa.ll
; ------------------------------------------------
; Function Attrs: convergent nounwind
define spir_kernel void @_ZTSZZNK4p1026KernelILj2ELb1EE6submitERN4sycl3_V15queueESt4spanIKPvLm18446744073709551615EERKSt6vectorINS3_5eventESaISB_EEENKUlRNS3_7handlerEE_clESH_EUlNS3_7nd_itemILi1EEEE_(ptr byval(%"struct.p39::__generated_Bound") align 8 %0, i32 %1, <8 x i32> %r0, <3 x i32> %globalOffset, i16 %localIdX, i16 %localIdY, i16 %localIdZ, ptr addrspace(2) %constBase, ptr addrspace(1) %globalBase, ptr %privateBase, i64 %const_reg_qword, i64 %const_reg_qword1, i64 %const_reg_qword2, i64 %const_reg_qword3, i64 %const_reg_qword4, i64 %const_reg_qword5, i64 %const_reg_qword6, i64 %const_reg_qword7, i64 %const_reg_qword8, i64 %const_reg_qword9, i64 %const_reg_qword10, i64 %const_reg_qword11, i64 %const_reg_qword12, i64 %const_reg_qword13, i64 %const_reg_qword14, i64 %const_reg_qword15, i64 %const_reg_qword16, i64 %const_reg_qword17, i64 %const_reg_qword18, i64 %const_reg_qword19, i64 %const_reg_qword20, i32 %const_reg_dword, i32 %const_reg_dword21, i32 %const_reg_dword22, i32 %const_reg_dword23, i32 %const_reg_dword24, i32 %bindlessOffset, i32 %bindlessOffset25) #0 {
; BB0 :
  %3 = extractelement <8 x i32> %r0, i32 1		; visa id: 2
  %4 = inttoptr i64 %const_reg_qword19 to ptr addrspace(4)		; visa id: 2
  %5 = inttoptr i64 %const_reg_qword20 to ptr addrspace(4)		; visa id: 2
  %simdLaneId16 = call i16 @llvm.genx.GenISA.simdLaneId()		; visa id: 2
  %simdLaneId = zext i16 %simdLaneId16 to i32		; visa id: 5
  %6 = and i32 %simdLaneId, 3		; visa id: 6
  %7 = shl i32 %3, 4		; visa id: 7
  %8 = lshr i16 %localIdX, 2		; visa id: 8
  %9 = and i16 %8, 16376		; visa id: 9
  %10 = zext i16 %9 to i32		; visa id: 10
  %11 = add i32 %7, %10		; visa id: 11
  %12 = lshr i32 %simdLaneId, 2		; visa id: 12
  %13 = or i32 %11, %12		; visa id: 13
  %tobool.i = icmp eq i32 %const_reg_dword21, 0		; visa id: 14
  br i1 %tobool.i, label %.precompiled_u32divrem_sp.exit_crit_edge, label %if.end.i, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8782		; visa id: 15

.precompiled_u32divrem_sp.exit_crit_edge:         ; preds = %2
; BB1 :
  br label %precompiled_u32divrem_sp.exit, !stats.blockFrequency.digits !8783, !stats.blockFrequency.scale !8784		; visa id: 18

if.end.i:                                         ; preds = %2
; BB2 :
  %14 = call float @llvm.genx.GenISA.uitof.rtz.f32.i32(i32 %const_reg_dword21)		; visa id: 20
  %conv.i = fptoui float %14 to i32		; visa id: 22
  %sub.i = sub i32 %const_reg_dword21, %conv.i		; visa id: 23
  %15 = call float @llvm.genx.GenISA.uitof.rtz.f32.i32(i32 %13)		; visa id: 24
  %div.i = fdiv float 1.000000e+00, %14, !fpmath !8785		; visa id: 25
  %16 = call float @llvm.genx.GenISA.fma.rtz.f32.f32.f32.f32(float %div.i, float 0xBE98000000000000, float %div.i)		; visa id: 26
  %17 = call float @llvm.genx.GenISA.mul.rtz.f32.f32.f32(float %15, float %16)		; visa id: 27
  %conv3.i = fptoui float %15 to i32		; visa id: 28
  %sub4.i = sub i32 %13, %conv3.i		; visa id: 29
  %conv8.i = fptoui float %17 to i32		; visa id: 30
  %18 = call float @llvm.genx.GenISA.uitof.rtz.f32.i32(i32 %sub.i)		; visa id: 31
  %19 = call float @llvm.genx.GenISA.uitof.rtz.f32.i32(i32 %sub4.i)		; visa id: 32
  %20 = call float @llvm.genx.GenISA.uitof.rtz.f32.i32(i32 %conv8.i)		; visa id: 33
  %21 = fsub float 0.000000e+00, %14		; visa id: 34
  %22 = call float @llvm.genx.GenISA.fma.rtz.f32.f32.f32.f32(float %21, float %20, float %15)		; visa id: 35
  %23 = fsub float 0.000000e+00, %18		; visa id: 36
  %24 = call float @llvm.genx.GenISA.fma.rtz.f32.f32.f32.f32(float %23, float %20, float %19)		; visa id: 37
  %25 = call float @llvm.genx.GenISA.add.rtz.f32.f32.f32(float %22, float %24)		; visa id: 38
  %26 = call float @llvm.genx.GenISA.mul.rtz.f32.f32.f32(float %16, float %25)		; visa id: 39
  %conv16.i = fptoui float %26 to i32		; visa id: 41
  %add.i = add i32 %conv16.i, %conv8.i		; visa id: 42
  %mul.i = mul i32 %add.i, %const_reg_dword21		; visa id: 43
  %sub17.i = sub i32 %13, %mul.i		; visa id: 44
  %cmp.i = icmp uge i32 %sub17.i, %const_reg_dword21
  %27 = sext i1 %cmp.i to i32		; visa id: 45
  %28 = sub i32 0, %27
  %add19.i = add i32 %add.i, %28		; visa id: 46
  br label %precompiled_u32divrem_sp.exit, !stats.blockFrequency.digits !8786, !stats.blockFrequency.scale !8787		; visa id: 47

precompiled_u32divrem_sp.exit:                    ; preds = %.precompiled_u32divrem_sp.exit_crit_edge, %if.end.i
; BB3 :
  %retval.0.i = phi i32 [ %add19.i, %if.end.i ], [ -1, %.precompiled_u32divrem_sp.exit_crit_edge ]
  %29 = mul i32 %retval.0.i, %const_reg_dword21		; visa id: 48
  %30 = icmp uge i32 %13, %1
  %31 = icmp uge i32 %13, %1		; visa id: 49
  br i1 %31, label %._crit_edge, label %32, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8782		; visa id: 50

32:                                               ; preds = %precompiled_u32divrem_sp.exit
; BB4 :
  %33 = zext i32 %retval.0.i to i64		; visa id: 52
  %34 = call { i32, i32 } @llvm.genx.GenISA.mul.pair(i32 %retval.0.i, i32 0, i32 12, i32 0)
  %35 = extractvalue { i32, i32 } %34, 0
  %36 = extractvalue { i32, i32 } %34, 1
  %37 = insertelement <2 x i32> undef, i32 %35, i32 0
  %38 = insertelement <2 x i32> %37, i32 %36, i32 1
  %39 = bitcast <2 x i32> %38 to i64		; visa id: 53
  %40 = add i64 %39, %const_reg_qword16		; visa id: 61
  %41 = inttoptr i64 %40 to ptr addrspace(4)		; visa id: 62
  %42 = addrspacecast ptr addrspace(4) %41 to ptr addrspace(1)		; visa id: 62
  %43 = load <2 x i32>, ptr addrspace(1) %42, align 4		; visa id: 63
  %44 = extractelement <2 x i32> %43, i32 0		; visa id: 64
  %45 = extractelement <2 x i32> %43, i32 1		; visa id: 64
  %46 = icmp uge i32 %44, %const_reg_dword23
  %47 = icmp ugt i32 %45, %const_reg_dword21		; visa id: 64
  %48 = or i1 %46, %47		; visa id: 65
  br i1 %48, label %.._crit_edge41_crit_edge, label %49, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 67

.._crit_edge41_crit_edge:                         ; preds = %32
; BB5 :
  br label %._crit_edge41, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 73

49:                                               ; preds = %32
; BB6 :
  %50 = sub i32 %13, %29		; visa id: 75
  %51 = add i64 %40, 8		; visa id: 76
  %52 = inttoptr i64 %51 to ptr addrspace(4)		; visa id: 77
  %53 = addrspacecast ptr addrspace(4) %52 to ptr addrspace(1)		; visa id: 77
  %54 = load i32, ptr addrspace(1) %53, align 4		; visa id: 78
  %55 = sub nuw i32 %const_reg_dword21, %45, !spirv.Decorations !8788		; visa id: 79
  %56 = icmp ule i32 %54, %55
  %57 = icmp ule i32 %54, %const_reg_dword21		; visa id: 80
  %58 = and i1 %56, %57		; visa id: 81
  %59 = icmp ult i32 %50, %54		; visa id: 83
  %60 = and i1 %58, %59		; visa id: 84
  br i1 %60, label %63, label %._crit_edge42, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 85

._crit_edge42:                                    ; preds = %49
; BB7 :
  %61 = xor i1 %58, true		; visa id: 87
  %62 = sext i1 %61 to i32		; visa id: 88
  br label %._crit_edge41, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8790		; visa id: 92

63:                                               ; preds = %49
; BB8 :
  %64 = ptrtoint ptr addrspace(2) %constBase to i64		; visa id: 94
  %65 = add i64 %64, 280
  %66 = call { i32, i32 } @llvm.genx.GenISA.mul.pair(i32 %44, i32 0, i32 %const_reg_dword21, i32 0)
  %67 = extractvalue { i32, i32 } %66, 0
  %68 = extractvalue { i32, i32 } %66, 1
  %69 = insertelement <2 x i32> undef, i32 %67, i32 0
  %70 = insertelement <2 x i32> %69, i32 %68, i32 1
  %71 = bitcast <2 x i32> %70 to i64		; visa id: 94
  %72 = zext i32 %45 to i64		; visa id: 102
  %73 = add nuw i64 %71, %72, !spirv.Decorations !8788		; visa id: 103
  %74 = zext i32 %50 to i64		; visa id: 104
  %75 = add nuw i64 %73, %74, !spirv.Decorations !8788		; visa id: 105
  %76 = bitcast i64 %75 to <2 x i32>		; visa id: 106
  %77 = extractelement <2 x i32> %76, i32 0		; visa id: 110
  %78 = extractelement <2 x i32> %76, i32 1		; visa id: 110
  %79 = call { i32, i32 } @llvm.genx.GenISA.mul.pair(i32 %77, i32 %78, i32 %const_reg_dword, i32 0)
  %80 = extractvalue { i32, i32 } %79, 0
  %81 = extractvalue { i32, i32 } %79, 1
  %82 = insertelement <2 x i32> undef, i32 %80, i32 0
  %83 = insertelement <2 x i32> %82, i32 %81, i32 1
  %84 = bitcast <2 x i32> %83 to i64		; visa id: 110
  %chunkPtr = inttoptr i64 %65 to ptr addrspace(2)
  %85 = load <16 x float>, ptr addrspace(2) %chunkPtr, align 4		; visa id: 118
  %86 = extractelement <16 x float> %85, i32 0		; visa id: 120
  %87 = extractelement <16 x float> %85, i32 1		; visa id: 120
  %88 = extractelement <16 x float> %85, i32 2		; visa id: 120
  %89 = extractelement <16 x float> %85, i32 3		; visa id: 120
  %90 = extractelement <16 x float> %85, i32 4		; visa id: 120
  %91 = extractelement <16 x float> %85, i32 5		; visa id: 120
  %92 = extractelement <16 x float> %85, i32 6		; visa id: 120
  %93 = extractelement <16 x float> %85, i32 7		; visa id: 120
  %94 = extractelement <16 x float> %85, i32 8		; visa id: 120
  %95 = extractelement <16 x float> %85, i32 9		; visa id: 120
  %96 = extractelement <16 x float> %85, i32 10		; visa id: 120
  %97 = extractelement <16 x float> %85, i32 11		; visa id: 120
  %98 = extractelement <16 x float> %85, i32 12		; visa id: 120
  %99 = extractelement <16 x float> %85, i32 13		; visa id: 120
  %100 = extractelement <16 x float> %85, i32 14		; visa id: 120
  %101 = extractelement <16 x float> %85, i32 15		; visa id: 120
  %102 = shl nuw nsw i32 %6, 1, !spirv.Decorations !8791		; visa id: 120
  %103 = add i64 %84, %const_reg_qword		; visa id: 121
  %104 = add i64 %103, 640		; visa id: 122
  %105 = add i64 %103, 720		; visa id: 123
  %106 = add i64 %84, %const_reg_qword1		; visa id: 124
  %107 = add i64 %106, 640		; visa id: 125
  %108 = add i64 %106, 720		; visa id: 126
  %109 = zext i32 %102 to i64		; visa id: 127
  %110 = add i64 %104, %109		; visa id: 128
  %111 = add i64 %105, %109		; visa id: 129
  %112 = add i64 %107, %109		; visa id: 130
  %113 = add i64 %108, %109		; visa id: 131
  br label %._crit_edge43, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8790		; visa id: 151

._crit_edge43:                                    ; preds = %.._crit_edge43_crit_edge, %63
; BB9 :
  %.sroa.35.0 = phi float [ %101, %63 ], [ %3301, %.._crit_edge43_crit_edge ]
  %.sroa.33.0 = phi float [ %100, %63 ], [ %2947, %.._crit_edge43_crit_edge ]
  %.sroa.31.0 = phi float [ %99, %63 ], [ %2520, %.._crit_edge43_crit_edge ]
  %.sroa.29.0 = phi float [ %98, %63 ], [ %2167, %.._crit_edge43_crit_edge ]
  %.sroa.27.0 = phi float [ %97, %63 ], [ %1738, %.._crit_edge43_crit_edge ]
  %.sroa.25.0 = phi float [ %96, %63 ], [ %1385, %.._crit_edge43_crit_edge ]
  %.sroa.23.0 = phi float [ %95, %63 ], [ %958, %.._crit_edge43_crit_edge ]
  %.sroa.20.0 = phi float [ %94, %63 ], [ %605, %.._crit_edge43_crit_edge ]
  %.sroa.18.0 = phi float [ %93, %63 ], [ %3145, %.._crit_edge43_crit_edge ]
  %.sroa.16.0 = phi float [ %92, %63 ], [ %2780, %.._crit_edge43_crit_edge ]
  %.sroa.14.0 = phi float [ %91, %63 ], [ %2365, %.._crit_edge43_crit_edge ]
  %.sroa.12.0 = phi float [ %90, %63 ], [ %1999, %.._crit_edge43_crit_edge ]
  %.sroa.10.0 = phi float [ %89, %63 ], [ %1583, %.._crit_edge43_crit_edge ]
  %.sroa.8.0 = phi float [ %88, %63 ], [ %1218, %.._crit_edge43_crit_edge ]
  %.sroa.6.0 = phi float [ %87, %63 ], [ %803, %.._crit_edge43_crit_edge ]
  %.sroa.0.0 = phi float [ %86, %63 ], [ %427, %.._crit_edge43_crit_edge ]
  %114 = phi i32 [ 0, %63 ], [ %3303, %.._crit_edge43_crit_edge ]
  %115 = shl nuw nsw i32 %114, 6, !spirv.Decorations !8791		; visa id: 152
  %116 = shl nuw nsw i32 %114, 3, !spirv.Decorations !8791		; visa id: 153
  %117 = shl nuw nsw i32 %114, 2, !spirv.Decorations !8791		; visa id: 154
  %118 = zext i32 %115 to i64		; visa id: 155
  %sink_650 = shl nuw nsw i32 %6, 4, !spirv.Decorations !8791		; visa id: 156
  %sink_649 = zext i32 %sink_650 to i64		; visa id: 157
  %sink_648 = add i64 %103, %sink_649		; visa id: 158
  %119 = add i64 %sink_648, %118		; visa id: 159
  %120 = inttoptr i64 %119 to ptr addrspace(4)		; visa id: 160
  %generic_cast_to_ptr = addrspacecast ptr addrspace(4) %120 to ptr addrspace(1)		; visa id: 160
  %121 = load <4 x i32>, ptr addrspace(1) %generic_cast_to_ptr, align 4		; visa id: 161
  %122 = extractelement <4 x i32> %121, i32 0		; visa id: 162
  %123 = extractelement <4 x i32> %121, i32 1		; visa id: 162
  %124 = extractelement <4 x i32> %121, i32 2		; visa id: 162
  %125 = extractelement <4 x i32> %121, i32 3		; visa id: 162
  %126 = zext i32 %116 to i64		; visa id: 162
  %127 = add i64 %110, %126		; visa id: 163
  %128 = inttoptr i64 %127 to ptr addrspace(4)		; visa id: 164
  %129 = addrspacecast ptr addrspace(4) %128 to ptr addrspace(1)		; visa id: 164
  %130 = load i16, ptr addrspace(1) %129, align 2, !noalias !8793		; visa id: 165
  %131 = add i64 %111, %126		; visa id: 167
  %132 = inttoptr i64 %131 to ptr addrspace(4)		; visa id: 168
  %133 = addrspacecast ptr addrspace(4) %132 to ptr addrspace(1)		; visa id: 168
  %134 = load i16, ptr addrspace(1) %133, align 2, !noalias !8793		; visa id: 169
  %135 = zext i32 %117 to i64		; visa id: 171
  %sink_645 = add i64 %103, 800		; visa id: 172
  %136 = add i64 %sink_645, %135		; visa id: 173
  %137 = inttoptr i64 %136 to ptr addrspace(4)		; visa id: 174
  %138 = addrspacecast ptr addrspace(4) %137 to ptr addrspace(1)		; visa id: 174
  %139 = load float, ptr addrspace(1) %138, align 4, !noalias !8793		; visa id: 175
  %sink_647 = add i64 %106, %sink_649		; visa id: 176
  %140 = add i64 %sink_647, %118		; visa id: 177
  %141 = inttoptr i64 %140 to ptr addrspace(4)		; visa id: 178
  %generic_cast_to_ptr.1 = addrspacecast ptr addrspace(4) %141 to ptr addrspace(1)		; visa id: 178
  %142 = load <4 x i32>, ptr addrspace(1) %generic_cast_to_ptr.1, align 4		; visa id: 179
  %143 = extractelement <4 x i32> %142, i32 0		; visa id: 180
  %144 = extractelement <4 x i32> %142, i32 1		; visa id: 180
  %145 = extractelement <4 x i32> %142, i32 2		; visa id: 180
  %146 = extractelement <4 x i32> %142, i32 3		; visa id: 180
  %147 = add i64 %112, %126		; visa id: 180
  %148 = inttoptr i64 %147 to ptr addrspace(4)		; visa id: 181
  %149 = addrspacecast ptr addrspace(4) %148 to ptr addrspace(1)		; visa id: 181
  %150 = load i16, ptr addrspace(1) %149, align 2, !noalias !8793		; visa id: 182
  %151 = add i64 %113, %126		; visa id: 184
  %152 = inttoptr i64 %151 to ptr addrspace(4)		; visa id: 185
  %153 = addrspacecast ptr addrspace(4) %152 to ptr addrspace(1)		; visa id: 185
  %154 = load i16, ptr addrspace(1) %153, align 2, !noalias !8793		; visa id: 186
  %sink_644 = add i64 %106, 800		; visa id: 188
  %155 = add i64 %sink_644, %135		; visa id: 189
  %156 = inttoptr i64 %155 to ptr addrspace(4)		; visa id: 190
  %157 = addrspacecast ptr addrspace(4) %156 to ptr addrspace(1)		; visa id: 190
  %158 = load float, ptr addrspace(1) %157, align 4, !noalias !8793		; visa id: 191
  %159 = and i32 %122, 255
  %160 = zext i16 %130 to i32		; visa id: 192
  %161 = shl nuw nsw i32 %160, 8, !spirv.Decorations !8791		; visa id: 193
  %162 = and i32 %161, 768		; visa id: 194
  %163 = or i32 %159, %162		; visa id: 195
  %164 = shl nuw nsw i32 %163, 3, !spirv.Decorations !8791		; visa id: 196
  %165 = zext i32 %164 to i64		; visa id: 197
  %sink_ = ptrtoint ptr addrspace(1) %globalBase to i64		; visa id: 198
  %166 = add i64 %sink_, %165		; visa id: 198
  %167 = inttoptr i64 %166 to ptr addrspace(1)		; visa id: 199
  %168 = load <2 x i32>, ptr addrspace(1) %167, align 4		; visa id: 199
  %169 = shl nuw nsw i32 %114, 8, !spirv.Decorations !8791		; visa id: 200
  %sink_646 = shl nuw nsw i32 %6, 6, !spirv.Decorations !8791		; visa id: 201
  %170 = or i32 %169, %sink_646		; visa id: 202
  %171 = extractelement <2 x i32> %168, i32 0		; visa id: 203
  %172 = extractelement <2 x i32> %168, i32 1		; visa id: 203
  %173 = bitcast i32 %122 to <4 x i8>
  %174 = extractelement <4 x i8> %173, i32 2
  %175 = shl nuw nsw i32 %160, 6		; visa id: 203
  %176 = and i32 %175, 768
  %177 = zext i8 %174 to i32		; visa id: 204
  %178 = or i32 %177, %176		; visa id: 205
  %179 = shl nuw nsw i32 %178, 3, !spirv.Decorations !8791		; visa id: 206
  %180 = zext i32 %179 to i64		; visa id: 207
  %181 = add i64 %sink_, %180		; visa id: 208
  %182 = inttoptr i64 %181 to ptr addrspace(1)		; visa id: 209
  %183 = load <2 x i32>, ptr addrspace(1) %182, align 4		; visa id: 209
  %184 = and i32 %143, 255
  %185 = zext i16 %150 to i32		; visa id: 210
  %186 = shl nuw nsw i32 %185, 8, !spirv.Decorations !8791		; visa id: 211
  %187 = and i32 %186, 768		; visa id: 212
  %188 = or i32 %184, %187		; visa id: 213
  %189 = shl nuw nsw i32 %188, 3, !spirv.Decorations !8791		; visa id: 214
  %190 = zext i32 %189 to i64		; visa id: 215
  %191 = add i64 %sink_, %190		; visa id: 216
  %192 = inttoptr i64 %191 to ptr addrspace(1)		; visa id: 217
  %193 = load <2 x i32>, ptr addrspace(1) %192, align 4		; visa id: 217
  %194 = extractelement <2 x i32> %183, i32 0		; visa id: 218
  %195 = extractelement <2 x i32> %183, i32 1		; visa id: 218
  %196 = extractelement <2 x i32> %193, i32 0		; visa id: 218
  %197 = extractelement <2 x i32> %193, i32 1		; visa id: 218
  %198 = bitcast i32 %143 to <4 x i8>
  %199 = extractelement <4 x i8> %198, i32 2
  %200 = shl nuw nsw i32 %185, 6		; visa id: 218
  %201 = and i32 %200, 768
  %202 = zext i8 %199 to i32		; visa id: 219
  %203 = or i32 %202, %201		; visa id: 220
  %204 = shl nuw nsw i32 %203, 3, !spirv.Decorations !8791		; visa id: 221
  %205 = zext i32 %204 to i64		; visa id: 222
  %206 = add i64 %sink_, %205		; visa id: 223
  %207 = inttoptr i64 %206 to ptr addrspace(1)		; visa id: 224
  %208 = load <2 x i32>, ptr addrspace(1) %207, align 4		; visa id: 224
  %209 = shl nuw i32 %170, 1		; visa id: 225
  %210 = zext i32 %209 to i64		; visa id: 226
  %211 = add i64 %210, %const_reg_qword2		; visa id: 227
  %IntToPtr2 = inttoptr i64 %211 to ptr addrspace(1)		; visa id: 228
  %vCastload = load i32, ptr addrspace(1) %IntToPtr2, align 2		; visa id: 228
  %212 = add i64 %211, 4
  %IntToPtr2582 = inttoptr i64 %212 to ptr addrspace(1)
  %vCastload583 = load i32, ptr addrspace(1) %IntToPtr2582, align 2		; visa id: 229
  %213 = extractelement <2 x i32> %208, i32 0		; visa id: 230
  %214 = extractelement <2 x i32> %208, i32 1		; visa id: 230
  %215 = bitcast i32 %vCastload to <2 x i16>		; visa id: 230
  %216 = bitcast i32 %vCastload583 to <2 x i16>		; visa id: 232
  %217 = extractelement <2 x i16> %215, i32 0		; visa id: 234
  %218 = extractelement <2 x i16> %215, i32 1		; visa id: 234
  %219 = extractelement <2 x i16> %216, i32 0		; visa id: 234
  %220 = extractelement <2 x i16> %216, i32 1		; visa id: 234
  %221 = add i64 %211, 8
  %IntToPtr2584 = inttoptr i64 %221 to ptr addrspace(1)
  %vCastload585 = load i32, ptr addrspace(1) %IntToPtr2584, align 2		; visa id: 234
  %222 = add i64 %211, 12
  %IntToPtr2586 = inttoptr i64 %222 to ptr addrspace(1)
  %vCastload587 = load i32, ptr addrspace(1) %IntToPtr2586, align 2		; visa id: 235
  %223 = bitcast i32 %vCastload585 to <2 x i16>		; visa id: 236
  %224 = bitcast i32 %vCastload587 to <2 x i16>		; visa id: 238
  %225 = extractelement <2 x i16> %223, i32 0		; visa id: 240
  %226 = extractelement <2 x i16> %223, i32 1		; visa id: 240
  %227 = extractelement <2 x i16> %224, i32 0		; visa id: 240
  %228 = extractelement <2 x i16> %224, i32 1		; visa id: 240
  %229 = and i16 %134, 255		; visa id: 240
  %230 = zext i16 %229 to i32		; visa id: 241
  %231 = and i32 %230, 15		; visa id: 242
  %232 = uitofp i32 %231 to float		; visa id: 243
  %233 = fadd float %232, 5.000000e-01		; visa id: 244
  %234 = fmul float %139, %233		; visa id: 245
  %235 = fmul float %234, 2.500000e-01		; visa id: 246
  %236 = bitcast float %139 to i32
  %237 = and i32 %236, 2147483647		; visa id: 247
  %238 = bitcast i32 %237 to float
  %239 = fcmp une float %238, %238
  %240 = fcmp oeq float %238, 0x7FF0000000000000		; visa id: 248
  %241 = or i1 %239, %240		; visa id: 249
  %242 = bitcast float %235 to i32
  %243 = and i32 %242, 2147483647		; visa id: 251
  %244 = icmp ugt i32 %243, 2139095040
  %245 = or i1 %241, %244		; visa id: 252
  %246 = and i32 %171, 255		; visa id: 254
  br i1 %245, label %254, label %247, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 255

247:                                              ; preds = %._crit_edge43
; BB10 :
  %248 = and i32 %122, 256
  %249 = sub nsw i32 0, %246, !spirv.Decorations !8798
  %250 = icmp eq i32 %248, 0		; visa id: 257
  %251 = select i1 %250, i32 %246, i32 %249		; visa id: 259
  %252 = sitofp i32 %251 to float		; visa id: 260
  %253 = fmul float %235, %252		; visa id: 261
  br label %262, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 262

254:                                              ; preds = %._crit_edge43
; BB11 :
  %255 = uitofp i32 %246 to float		; visa id: 264
  %256 = fmul float %235, %255		; visa id: 265
  %257 = and i32 %122, 256
  %258 = icmp eq i32 %257, 0		; visa id: 266
  %259 = select i1 %258, i32 1, i32 -1		; visa id: 268
  %260 = sitofp i32 %259 to float		; visa id: 269
  %261 = fmul float %256, %260		; visa id: 270
  br label %262, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 271

262:                                              ; preds = %247, %254
; BB12 :
  %.sroa.062.0 = phi float [ %261, %254 ], [ %253, %247 ]
  %263 = bitcast i32 %171 to <4 x i8>
  %264 = extractelement <4 x i8> %263, i32 1
  %265 = zext i8 %264 to i32		; visa id: 272
  br i1 %245, label %273, label %266, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 273

266:                                              ; preds = %262
; BB13 :
  %267 = and i32 %122, 512
  %268 = sub nsw i32 0, %265, !spirv.Decorations !8798
  %269 = icmp eq i32 %267, 0		; visa id: 275
  %270 = select i1 %269, i32 %265, i32 %268		; visa id: 277
  %271 = sitofp i32 %270 to float		; visa id: 278
  %272 = fmul float %235, %271		; visa id: 279
  br label %281, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 280

273:                                              ; preds = %262
; BB14 :
  %274 = uitofp i32 %265 to float		; visa id: 282
  %275 = fmul float %235, %274		; visa id: 283
  %276 = and i32 %122, 512
  %277 = icmp eq i32 %276, 0		; visa id: 284
  %278 = select i1 %277, i32 1, i32 -1		; visa id: 286
  %279 = sitofp i32 %278 to float		; visa id: 287
  %280 = fmul float %275, %279		; visa id: 288
  br label %281, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 289

281:                                              ; preds = %273, %266
; BB15 :
  %.sroa.80.0 = phi float [ %280, %273 ], [ %272, %266 ]
  %282 = extractelement <4 x i8> %263, i32 2
  %283 = zext i8 %282 to i32		; visa id: 290
  br i1 %245, label %291, label %284, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 291

284:                                              ; preds = %281
; BB16 :
  %285 = and i32 %122, 1024
  %286 = sub nsw i32 0, %283, !spirv.Decorations !8798
  %287 = icmp eq i32 %285, 0		; visa id: 293
  %288 = select i1 %287, i32 %283, i32 %286		; visa id: 295
  %289 = sitofp i32 %288 to float		; visa id: 296
  %290 = fmul float %235, %289		; visa id: 297
  br label %299, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 298

291:                                              ; preds = %281
; BB17 :
  %292 = uitofp i32 %283 to float		; visa id: 300
  %293 = fmul float %235, %292		; visa id: 301
  %294 = and i32 %122, 1024
  %295 = icmp eq i32 %294, 0		; visa id: 302
  %296 = select i1 %295, i32 1, i32 -1		; visa id: 304
  %297 = sitofp i32 %296 to float		; visa id: 305
  %298 = fmul float %293, %297		; visa id: 306
  br label %299, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 307

299:                                              ; preds = %291, %284
; BB18 :
  %.sroa.128.0 = phi float [ %298, %291 ], [ %290, %284 ]
  %300 = lshr i32 %171, 24		; visa id: 308
  br i1 %245, label %308, label %301, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 309

301:                                              ; preds = %299
; BB19 :
  %302 = and i32 %122, 2048
  %303 = sub nsw i32 0, %300, !spirv.Decorations !8798
  %304 = icmp eq i32 %302, 0		; visa id: 311
  %305 = select i1 %304, i32 %300, i32 %303		; visa id: 313
  %306 = sitofp i32 %305 to float		; visa id: 314
  %307 = fmul float %235, %306		; visa id: 315
  br label %316, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 316

308:                                              ; preds = %299
; BB20 :
  %309 = uitofp i32 %300 to float		; visa id: 318
  %310 = fmul float %235, %309		; visa id: 319
  %311 = and i32 %122, 2048
  %312 = icmp eq i32 %311, 0		; visa id: 320
  %313 = select i1 %312, i32 1, i32 -1		; visa id: 322
  %314 = sitofp i32 %313 to float		; visa id: 323
  %315 = fmul float %310, %314		; visa id: 324
  br label %316, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 325

316:                                              ; preds = %308, %301
; BB21 :
  %.sroa.176.0 = phi float [ %315, %308 ], [ %307, %301 ]
  %317 = and i32 %172, 255		; visa id: 326
  br i1 %245, label %325, label %318, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 327

318:                                              ; preds = %316
; BB22 :
  %319 = and i32 %122, 4096
  %320 = sub nsw i32 0, %317, !spirv.Decorations !8798
  %321 = icmp eq i32 %319, 0		; visa id: 329
  %322 = select i1 %321, i32 %317, i32 %320		; visa id: 331
  %323 = sitofp i32 %322 to float		; visa id: 332
  %324 = fmul float %235, %323		; visa id: 333
  br label %333, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 334

325:                                              ; preds = %316
; BB23 :
  %326 = uitofp i32 %317 to float		; visa id: 336
  %327 = fmul float %235, %326		; visa id: 337
  %328 = and i32 %122, 4096
  %329 = icmp eq i32 %328, 0		; visa id: 338
  %330 = select i1 %329, i32 1, i32 -1		; visa id: 340
  %331 = sitofp i32 %330 to float		; visa id: 341
  %332 = fmul float %327, %331		; visa id: 342
  br label %333, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 343

333:                                              ; preds = %325, %318
; BB24 :
  %.sroa.224.0 = phi float [ %332, %325 ], [ %324, %318 ]
  %334 = bitcast i32 %172 to <4 x i8>
  %335 = extractelement <4 x i8> %334, i32 1
  %336 = zext i8 %335 to i32		; visa id: 344
  br i1 %245, label %344, label %337, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 345

337:                                              ; preds = %333
; BB25 :
  %338 = and i32 %122, 8192
  %339 = sub nsw i32 0, %336, !spirv.Decorations !8798
  %340 = icmp eq i32 %338, 0		; visa id: 347
  %341 = select i1 %340, i32 %336, i32 %339		; visa id: 349
  %342 = sitofp i32 %341 to float		; visa id: 350
  %343 = fmul float %235, %342		; visa id: 351
  br label %352, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 352

344:                                              ; preds = %333
; BB26 :
  %345 = uitofp i32 %336 to float		; visa id: 354
  %346 = fmul float %235, %345		; visa id: 355
  %347 = and i32 %122, 8192
  %348 = icmp eq i32 %347, 0		; visa id: 356
  %349 = select i1 %348, i32 1, i32 -1		; visa id: 358
  %350 = sitofp i32 %349 to float		; visa id: 359
  %351 = fmul float %346, %350		; visa id: 360
  br label %352, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 361

352:                                              ; preds = %344, %337
; BB27 :
  %.sroa.272.0 = phi float [ %351, %344 ], [ %343, %337 ]
  %353 = extractelement <4 x i8> %334, i32 2
  %354 = zext i8 %353 to i32		; visa id: 362
  br i1 %245, label %362, label %355, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 363

355:                                              ; preds = %352
; BB28 :
  %356 = and i32 %122, 16384
  %357 = sub nsw i32 0, %354, !spirv.Decorations !8798
  %358 = icmp eq i32 %356, 0		; visa id: 365
  %359 = select i1 %358, i32 %354, i32 %357		; visa id: 367
  %360 = sitofp i32 %359 to float		; visa id: 368
  %361 = fmul float %235, %360		; visa id: 369
  br label %370, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 370

362:                                              ; preds = %352
; BB29 :
  %363 = uitofp i32 %354 to float		; visa id: 372
  %364 = fmul float %235, %363		; visa id: 373
  %365 = and i32 %122, 16384
  %366 = icmp eq i32 %365, 0		; visa id: 374
  %367 = select i1 %366, i32 1, i32 -1		; visa id: 376
  %368 = sitofp i32 %367 to float		; visa id: 377
  %369 = fmul float %364, %368		; visa id: 378
  br label %370, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 379

370:                                              ; preds = %362, %355
; BB30 :
  %.sroa.320.0 = phi float [ %369, %362 ], [ %361, %355 ]
  %371 = lshr i32 %172, 24		; visa id: 380
  br i1 %245, label %379, label %372, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 381

372:                                              ; preds = %370
; BB31 :
  %373 = and i32 %122, 32768
  %374 = sub nsw i32 0, %371, !spirv.Decorations !8798
  %375 = icmp eq i32 %373, 0		; visa id: 383
  %376 = select i1 %375, i32 %371, i32 %374		; visa id: 385
  %377 = sitofp i32 %376 to float		; visa id: 386
  %378 = fmul float %235, %377		; visa id: 387
  br label %387, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 388

379:                                              ; preds = %370
; BB32 :
  %380 = uitofp i32 %371 to float		; visa id: 390
  %381 = fmul float %235, %380		; visa id: 391
  %382 = and i32 %122, 32768
  %383 = icmp eq i32 %382, 0		; visa id: 392
  %384 = select i1 %383, i32 1, i32 -1		; visa id: 394
  %385 = sitofp i32 %384 to float		; visa id: 395
  %386 = fmul float %381, %385		; visa id: 396
  br label %387, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 397

387:                                              ; preds = %379, %372
; BB33 :
  %.sroa.368.0 = phi float [ %386, %379 ], [ %378, %372 ]
  %388 = zext i16 %217 to i32		; visa id: 398
  %389 = shl nuw i32 %388, 16		; visa id: 399
  %390 = bitcast i32 %389 to float
  %391 = fmul float %.sroa.062.0, %390		; visa id: 400
  %392 = fadd float %.sroa.0.0, %391		; visa id: 401
  %393 = zext i16 %218 to i32		; visa id: 402
  %394 = shl nuw i32 %393, 16		; visa id: 403
  %395 = bitcast i32 %394 to float
  %396 = fmul float %.sroa.80.0, %395		; visa id: 404
  %397 = fadd float %392, %396		; visa id: 405
  %398 = zext i16 %219 to i32		; visa id: 406
  %399 = shl nuw i32 %398, 16		; visa id: 407
  %400 = bitcast i32 %399 to float
  %401 = fmul float %.sroa.128.0, %400		; visa id: 408
  %402 = fadd float %397, %401		; visa id: 409
  %403 = zext i16 %220 to i32		; visa id: 410
  %404 = shl nuw i32 %403, 16		; visa id: 411
  %405 = bitcast i32 %404 to float
  %406 = fmul float %.sroa.176.0, %405		; visa id: 412
  %407 = fadd float %402, %406		; visa id: 413
  %408 = zext i16 %225 to i32		; visa id: 414
  %409 = shl nuw i32 %408, 16		; visa id: 415
  %410 = bitcast i32 %409 to float
  %411 = fmul float %.sroa.224.0, %410		; visa id: 416
  %412 = fadd float %407, %411		; visa id: 417
  %413 = zext i16 %226 to i32		; visa id: 418
  %414 = shl nuw i32 %413, 16		; visa id: 419
  %415 = bitcast i32 %414 to float
  %416 = fmul float %.sroa.272.0, %415		; visa id: 420
  %417 = fadd float %412, %416		; visa id: 421
  %418 = zext i16 %227 to i32		; visa id: 422
  %419 = shl nuw i32 %418, 16		; visa id: 423
  %420 = bitcast i32 %419 to float
  %421 = fmul float %.sroa.320.0, %420		; visa id: 424
  %422 = fadd float %417, %421		; visa id: 425
  %423 = zext i16 %228 to i32		; visa id: 426
  %424 = shl nuw i32 %423, 16		; visa id: 427
  %425 = bitcast i32 %424 to float
  %426 = fmul float %.sroa.368.0, %425		; visa id: 428
  %427 = fadd float %422, %426		; visa id: 429
  %428 = and i16 %154, 255		; visa id: 430
  %429 = zext i16 %428 to i32		; visa id: 431
  %430 = and i32 %429, 15		; visa id: 432
  %431 = uitofp i32 %430 to float		; visa id: 433
  %432 = fadd float %431, 5.000000e-01		; visa id: 434
  %433 = fmul float %158, %432		; visa id: 435
  %434 = fmul float %433, 2.500000e-01		; visa id: 436
  %435 = bitcast float %158 to i32
  %436 = and i32 %435, 2147483647		; visa id: 437
  %437 = bitcast i32 %436 to float
  %438 = fcmp une float %437, %437
  %439 = fcmp oeq float %437, 0x7FF0000000000000		; visa id: 438
  %440 = or i1 %438, %439		; visa id: 439
  %441 = bitcast float %434 to i32
  %442 = and i32 %441, 2147483647		; visa id: 441
  %443 = icmp ugt i32 %442, 2139095040
  %444 = fcmp oeq float %437, 0x7FF0000000000000		; visa id: 442
  %445 = fcmp une float %437, %437
  %446 = or i1 %445, %444		; visa id: 443
  %447 = or i1 %446, %443		; visa id: 445
  %448 = and i32 %196, 255		; visa id: 447
  br i1 %447, label %456, label %449, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 448

449:                                              ; preds = %387
; BB34 :
  %450 = and i32 %143, 256
  %451 = sub nsw i32 0, %448, !spirv.Decorations !8798
  %452 = icmp eq i32 %450, 0		; visa id: 450
  %453 = select i1 %452, i32 %448, i32 %451		; visa id: 452
  %454 = sitofp i32 %453 to float		; visa id: 453
  %455 = fmul float %434, %454		; visa id: 454
  br label %464, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 455

456:                                              ; preds = %387
; BB35 :
  %457 = uitofp i32 %448 to float		; visa id: 457
  %458 = fmul float %434, %457		; visa id: 458
  %459 = and i32 %143, 256
  %460 = icmp eq i32 %459, 0		; visa id: 459
  %461 = select i1 %460, i32 1, i32 -1		; visa id: 461
  %462 = sitofp i32 %461 to float		; visa id: 462
  %463 = fmul float %458, %462		; visa id: 463
  br label %464, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 464

464:                                              ; preds = %456, %449
; BB36 :
  %.sroa.062.1 = phi float [ %463, %456 ], [ %455, %449 ]
  %465 = bitcast i32 %196 to <4 x i8>
  %466 = extractelement <4 x i8> %465, i32 1
  %467 = zext i8 %466 to i32		; visa id: 465
  br i1 %447, label %475, label %468, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 466

468:                                              ; preds = %464
; BB37 :
  %469 = and i32 %143, 512
  %470 = sub nsw i32 0, %467, !spirv.Decorations !8798
  %471 = icmp eq i32 %469, 0		; visa id: 468
  %472 = select i1 %471, i32 %467, i32 %470		; visa id: 470
  %473 = sitofp i32 %472 to float		; visa id: 471
  %474 = fmul float %434, %473		; visa id: 472
  br label %483, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 473

475:                                              ; preds = %464
; BB38 :
  %476 = uitofp i32 %467 to float		; visa id: 475
  %477 = fmul float %434, %476		; visa id: 476
  %478 = and i32 %143, 512
  %479 = icmp eq i32 %478, 0		; visa id: 477
  %480 = select i1 %479, i32 1, i32 -1		; visa id: 479
  %481 = sitofp i32 %480 to float		; visa id: 480
  %482 = fmul float %477, %481		; visa id: 481
  br label %483, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 482

483:                                              ; preds = %475, %468
; BB39 :
  %.sroa.80.1 = phi float [ %482, %475 ], [ %474, %468 ]
  %484 = extractelement <4 x i8> %465, i32 2
  %485 = zext i8 %484 to i32		; visa id: 483
  br i1 %447, label %493, label %486, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 484

486:                                              ; preds = %483
; BB40 :
  %487 = and i32 %143, 1024
  %488 = sub nsw i32 0, %485, !spirv.Decorations !8798
  %489 = icmp eq i32 %487, 0		; visa id: 486
  %490 = select i1 %489, i32 %485, i32 %488		; visa id: 488
  %491 = sitofp i32 %490 to float		; visa id: 489
  %492 = fmul float %434, %491		; visa id: 490
  br label %501, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 491

493:                                              ; preds = %483
; BB41 :
  %494 = uitofp i32 %485 to float		; visa id: 493
  %495 = fmul float %434, %494		; visa id: 494
  %496 = and i32 %143, 1024
  %497 = icmp eq i32 %496, 0		; visa id: 495
  %498 = select i1 %497, i32 1, i32 -1		; visa id: 497
  %499 = sitofp i32 %498 to float		; visa id: 498
  %500 = fmul float %495, %499		; visa id: 499
  br label %501, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 500

501:                                              ; preds = %493, %486
; BB42 :
  %.sroa.128.1 = phi float [ %500, %493 ], [ %492, %486 ]
  %502 = lshr i32 %196, 24		; visa id: 501
  br i1 %447, label %510, label %503, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 502

503:                                              ; preds = %501
; BB43 :
  %504 = and i32 %143, 2048
  %505 = sub nsw i32 0, %502, !spirv.Decorations !8798
  %506 = icmp eq i32 %504, 0		; visa id: 504
  %507 = select i1 %506, i32 %502, i32 %505		; visa id: 506
  %508 = sitofp i32 %507 to float		; visa id: 507
  %509 = fmul float %434, %508		; visa id: 508
  br label %518, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 509

510:                                              ; preds = %501
; BB44 :
  %511 = uitofp i32 %502 to float		; visa id: 511
  %512 = fmul float %434, %511		; visa id: 512
  %513 = and i32 %143, 2048
  %514 = icmp eq i32 %513, 0		; visa id: 513
  %515 = select i1 %514, i32 1, i32 -1		; visa id: 515
  %516 = sitofp i32 %515 to float		; visa id: 516
  %517 = fmul float %512, %516		; visa id: 517
  br label %518, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 518

518:                                              ; preds = %510, %503
; BB45 :
  %.sroa.176.1 = phi float [ %517, %510 ], [ %509, %503 ]
  %519 = and i32 %197, 255		; visa id: 519
  br i1 %447, label %527, label %520, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 520

520:                                              ; preds = %518
; BB46 :
  %521 = and i32 %143, 4096
  %522 = sub nsw i32 0, %519, !spirv.Decorations !8798
  %523 = icmp eq i32 %521, 0		; visa id: 522
  %524 = select i1 %523, i32 %519, i32 %522		; visa id: 524
  %525 = sitofp i32 %524 to float		; visa id: 525
  %526 = fmul float %434, %525		; visa id: 526
  br label %535, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 527

527:                                              ; preds = %518
; BB47 :
  %528 = uitofp i32 %519 to float		; visa id: 529
  %529 = fmul float %434, %528		; visa id: 530
  %530 = and i32 %143, 4096
  %531 = icmp eq i32 %530, 0		; visa id: 531
  %532 = select i1 %531, i32 1, i32 -1		; visa id: 533
  %533 = sitofp i32 %532 to float		; visa id: 534
  %534 = fmul float %529, %533		; visa id: 535
  br label %535, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 536

535:                                              ; preds = %527, %520
; BB48 :
  %.sroa.224.1 = phi float [ %534, %527 ], [ %526, %520 ]
  %536 = bitcast i32 %197 to <4 x i8>
  %537 = extractelement <4 x i8> %536, i32 1
  %538 = zext i8 %537 to i32		; visa id: 537
  br i1 %447, label %546, label %539, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 538

539:                                              ; preds = %535
; BB49 :
  %540 = and i32 %143, 8192
  %541 = sub nsw i32 0, %538, !spirv.Decorations !8798
  %542 = icmp eq i32 %540, 0		; visa id: 540
  %543 = select i1 %542, i32 %538, i32 %541		; visa id: 542
  %544 = sitofp i32 %543 to float		; visa id: 543
  %545 = fmul float %434, %544		; visa id: 544
  br label %554, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 545

546:                                              ; preds = %535
; BB50 :
  %547 = uitofp i32 %538 to float		; visa id: 547
  %548 = fmul float %434, %547		; visa id: 548
  %549 = and i32 %143, 8192
  %550 = icmp eq i32 %549, 0		; visa id: 549
  %551 = select i1 %550, i32 1, i32 -1		; visa id: 551
  %552 = sitofp i32 %551 to float		; visa id: 552
  %553 = fmul float %548, %552		; visa id: 553
  br label %554, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 554

554:                                              ; preds = %546, %539
; BB51 :
  %.sroa.272.1 = phi float [ %553, %546 ], [ %545, %539 ]
  %555 = extractelement <4 x i8> %536, i32 2
  %556 = zext i8 %555 to i32		; visa id: 555
  br i1 %447, label %564, label %557, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 556

557:                                              ; preds = %554
; BB52 :
  %558 = and i32 %143, 16384
  %559 = sub nsw i32 0, %556, !spirv.Decorations !8798
  %560 = icmp eq i32 %558, 0		; visa id: 558
  %561 = select i1 %560, i32 %556, i32 %559		; visa id: 560
  %562 = sitofp i32 %561 to float		; visa id: 561
  %563 = fmul float %434, %562		; visa id: 562
  br label %572, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 563

564:                                              ; preds = %554
; BB53 :
  %565 = uitofp i32 %556 to float		; visa id: 565
  %566 = fmul float %434, %565		; visa id: 566
  %567 = and i32 %143, 16384
  %568 = icmp eq i32 %567, 0		; visa id: 567
  %569 = select i1 %568, i32 1, i32 -1		; visa id: 569
  %570 = sitofp i32 %569 to float		; visa id: 570
  %571 = fmul float %566, %570		; visa id: 571
  br label %572, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 572

572:                                              ; preds = %564, %557
; BB54 :
  %.sroa.320.1 = phi float [ %571, %564 ], [ %563, %557 ]
  %573 = lshr i32 %197, 24		; visa id: 573
  br i1 %447, label %581, label %574, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 574

574:                                              ; preds = %572
; BB55 :
  %575 = and i32 %143, 32768
  %576 = sub nsw i32 0, %573, !spirv.Decorations !8798
  %577 = icmp eq i32 %575, 0		; visa id: 576
  %578 = select i1 %577, i32 %573, i32 %576		; visa id: 578
  %579 = sitofp i32 %578 to float		; visa id: 579
  %580 = fmul float %434, %579		; visa id: 580
  br label %589, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 581

581:                                              ; preds = %572
; BB56 :
  %582 = uitofp i32 %573 to float		; visa id: 583
  %583 = fmul float %434, %582		; visa id: 584
  %584 = and i32 %143, 32768
  %585 = icmp eq i32 %584, 0		; visa id: 585
  %586 = select i1 %585, i32 1, i32 -1		; visa id: 587
  %587 = sitofp i32 %586 to float		; visa id: 588
  %588 = fmul float %583, %587		; visa id: 589
  br label %589, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 590

589:                                              ; preds = %581, %574
; BB57 :
  %.sroa.368.1 = phi float [ %588, %581 ], [ %580, %574 ]
  %590 = fmul float %.sroa.062.1, %390		; visa id: 591
  %591 = fadd float %.sroa.20.0, %590		; visa id: 592
  %592 = fmul float %.sroa.80.1, %395		; visa id: 593
  %593 = fadd float %591, %592		; visa id: 594
  %594 = fmul float %.sroa.128.1, %400		; visa id: 595
  %595 = fadd float %593, %594		; visa id: 596
  %596 = fmul float %.sroa.176.1, %405		; visa id: 597
  %597 = fadd float %595, %596		; visa id: 598
  %598 = fmul float %.sroa.224.1, %410		; visa id: 599
  %599 = fadd float %597, %598		; visa id: 600
  %600 = fmul float %.sroa.272.1, %415		; visa id: 601
  %601 = fadd float %599, %600		; visa id: 602
  %602 = fmul float %.sroa.320.1, %420		; visa id: 603
  %603 = fadd float %601, %602		; visa id: 604
  %604 = fmul float %.sroa.368.1, %425		; visa id: 605
  %605 = fadd float %603, %604		; visa id: 606
  %606 = or i32 %209, 16		; visa id: 607
  %607 = zext i32 %606 to i64		; visa id: 608
  %608 = add i64 %607, %const_reg_qword2		; visa id: 609
  %IntToPtr2588 = inttoptr i64 %608 to ptr addrspace(1)		; visa id: 610
  %vCastload589 = load i32, ptr addrspace(1) %IntToPtr2588, align 2		; visa id: 610
  %609 = add i64 %608, 4
  %IntToPtr2590 = inttoptr i64 %609 to ptr addrspace(1)
  %vCastload591 = load i32, ptr addrspace(1) %IntToPtr2590, align 2		; visa id: 611
  %610 = add i64 %608, 8
  %IntToPtr2592 = inttoptr i64 %610 to ptr addrspace(1)
  %vCastload593 = load i32, ptr addrspace(1) %IntToPtr2592, align 2		; visa id: 612
  %611 = add i64 %608, 12
  %IntToPtr2594 = inttoptr i64 %611 to ptr addrspace(1)
  %vCastload595 = load i32, ptr addrspace(1) %IntToPtr2594, align 2		; visa id: 613
  %612 = bitcast i32 %vCastload589 to <2 x i16>		; visa id: 614
  %613 = bitcast i32 %vCastload591 to <2 x i16>		; visa id: 616
  %614 = extractelement <2 x i16> %612, i32 0		; visa id: 618
  %615 = extractelement <2 x i16> %612, i32 1		; visa id: 618
  %616 = extractelement <2 x i16> %613, i32 0		; visa id: 618
  %617 = extractelement <2 x i16> %613, i32 1		; visa id: 618
  %618 = bitcast i32 %vCastload593 to <2 x i16>		; visa id: 618
  %619 = bitcast i32 %vCastload595 to <2 x i16>		; visa id: 620
  %620 = extractelement <2 x i16> %618, i32 0		; visa id: 622
  %621 = extractelement <2 x i16> %618, i32 1		; visa id: 622
  %622 = extractelement <2 x i16> %619, i32 0		; visa id: 622
  %623 = extractelement <2 x i16> %619, i32 1		; visa id: 622
  %624 = and i32 %194, 255		; visa id: 622
  br i1 %245, label %632, label %625, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 623

625:                                              ; preds = %589
; BB58 :
  %626 = and i32 %122, 16777216
  %627 = sub nsw i32 0, %624, !spirv.Decorations !8798
  %628 = icmp eq i32 %626, 0		; visa id: 625
  %629 = select i1 %628, i32 %624, i32 %627		; visa id: 627
  %630 = sitofp i32 %629 to float		; visa id: 628
  %631 = fmul float %235, %630		; visa id: 629
  br label %640, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 630

632:                                              ; preds = %589
; BB59 :
  %633 = uitofp i32 %624 to float		; visa id: 632
  %634 = fmul float %235, %633		; visa id: 633
  %635 = and i32 %122, 16777216
  %636 = icmp eq i32 %635, 0		; visa id: 634
  %637 = select i1 %636, i32 1, i32 -1		; visa id: 636
  %638 = sitofp i32 %637 to float		; visa id: 637
  %639 = fmul float %634, %638		; visa id: 638
  br label %640, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 639

640:                                              ; preds = %632, %625
; BB60 :
  %.sroa.062.2 = phi float [ %639, %632 ], [ %631, %625 ]
  %641 = bitcast i32 %194 to <4 x i8>
  %642 = extractelement <4 x i8> %641, i32 1
  %643 = zext i8 %642 to i32		; visa id: 640
  br i1 %245, label %651, label %644, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 641

644:                                              ; preds = %640
; BB61 :
  %645 = and i32 %122, 33554432
  %646 = sub nsw i32 0, %643, !spirv.Decorations !8798
  %647 = icmp eq i32 %645, 0		; visa id: 643
  %648 = select i1 %647, i32 %643, i32 %646		; visa id: 645
  %649 = sitofp i32 %648 to float		; visa id: 646
  %650 = fmul float %235, %649		; visa id: 647
  br label %659, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 648

651:                                              ; preds = %640
; BB62 :
  %652 = uitofp i32 %643 to float		; visa id: 650
  %653 = fmul float %235, %652		; visa id: 651
  %654 = and i32 %122, 33554432
  %655 = icmp eq i32 %654, 0		; visa id: 652
  %656 = select i1 %655, i32 1, i32 -1		; visa id: 654
  %657 = sitofp i32 %656 to float		; visa id: 655
  %658 = fmul float %653, %657		; visa id: 656
  br label %659, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 657

659:                                              ; preds = %651, %644
; BB63 :
  %.sroa.80.2 = phi float [ %658, %651 ], [ %650, %644 ]
  %660 = extractelement <4 x i8> %641, i32 2
  %661 = zext i8 %660 to i32		; visa id: 658
  br i1 %245, label %669, label %662, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 659

662:                                              ; preds = %659
; BB64 :
  %663 = and i32 %122, 67108864
  %664 = sub nsw i32 0, %661, !spirv.Decorations !8798
  %665 = icmp eq i32 %663, 0		; visa id: 661
  %666 = select i1 %665, i32 %661, i32 %664		; visa id: 663
  %667 = sitofp i32 %666 to float		; visa id: 664
  %668 = fmul float %235, %667		; visa id: 665
  br label %677, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 666

669:                                              ; preds = %659
; BB65 :
  %670 = uitofp i32 %661 to float		; visa id: 668
  %671 = fmul float %235, %670		; visa id: 669
  %672 = and i32 %122, 67108864
  %673 = icmp eq i32 %672, 0		; visa id: 670
  %674 = select i1 %673, i32 1, i32 -1		; visa id: 672
  %675 = sitofp i32 %674 to float		; visa id: 673
  %676 = fmul float %671, %675		; visa id: 674
  br label %677, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 675

677:                                              ; preds = %669, %662
; BB66 :
  %.sroa.128.2 = phi float [ %676, %669 ], [ %668, %662 ]
  %678 = lshr i32 %194, 24		; visa id: 676
  br i1 %245, label %686, label %679, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 677

679:                                              ; preds = %677
; BB67 :
  %680 = and i32 %122, 134217728
  %681 = sub nsw i32 0, %678, !spirv.Decorations !8798
  %682 = icmp eq i32 %680, 0		; visa id: 679
  %683 = select i1 %682, i32 %678, i32 %681		; visa id: 681
  %684 = sitofp i32 %683 to float		; visa id: 682
  %685 = fmul float %235, %684		; visa id: 683
  br label %694, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 684

686:                                              ; preds = %677
; BB68 :
  %687 = uitofp i32 %678 to float		; visa id: 686
  %688 = fmul float %235, %687		; visa id: 687
  %689 = and i32 %122, 134217728
  %690 = icmp eq i32 %689, 0		; visa id: 688
  %691 = select i1 %690, i32 1, i32 -1		; visa id: 690
  %692 = sitofp i32 %691 to float		; visa id: 691
  %693 = fmul float %688, %692		; visa id: 692
  br label %694, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 693

694:                                              ; preds = %686, %679
; BB69 :
  %.sroa.176.2 = phi float [ %693, %686 ], [ %685, %679 ]
  %695 = and i32 %195, 255		; visa id: 694
  br i1 %245, label %703, label %696, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 695

696:                                              ; preds = %694
; BB70 :
  %697 = and i32 %122, 268435456
  %698 = sub nsw i32 0, %695, !spirv.Decorations !8798
  %699 = icmp eq i32 %697, 0		; visa id: 697
  %700 = select i1 %699, i32 %695, i32 %698		; visa id: 699
  %701 = sitofp i32 %700 to float		; visa id: 700
  %702 = fmul float %235, %701		; visa id: 701
  br label %711, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 702

703:                                              ; preds = %694
; BB71 :
  %704 = uitofp i32 %695 to float		; visa id: 704
  %705 = fmul float %235, %704		; visa id: 705
  %706 = and i32 %122, 268435456
  %707 = icmp eq i32 %706, 0		; visa id: 706
  %708 = select i1 %707, i32 1, i32 -1		; visa id: 708
  %709 = sitofp i32 %708 to float		; visa id: 709
  %710 = fmul float %705, %709		; visa id: 710
  br label %711, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 711

711:                                              ; preds = %703, %696
; BB72 :
  %.sroa.224.2 = phi float [ %710, %703 ], [ %702, %696 ]
  %712 = bitcast i32 %195 to <4 x i8>
  %713 = extractelement <4 x i8> %712, i32 1
  %714 = zext i8 %713 to i32		; visa id: 712
  br i1 %245, label %722, label %715, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 713

715:                                              ; preds = %711
; BB73 :
  %716 = and i32 %122, 536870912
  %717 = sub nsw i32 0, %714, !spirv.Decorations !8798
  %718 = icmp eq i32 %716, 0		; visa id: 715
  %719 = select i1 %718, i32 %714, i32 %717		; visa id: 717
  %720 = sitofp i32 %719 to float		; visa id: 718
  %721 = fmul float %235, %720		; visa id: 719
  br label %730, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 720

722:                                              ; preds = %711
; BB74 :
  %723 = uitofp i32 %714 to float		; visa id: 722
  %724 = fmul float %235, %723		; visa id: 723
  %725 = and i32 %122, 536870912
  %726 = icmp eq i32 %725, 0		; visa id: 724
  %727 = select i1 %726, i32 1, i32 -1		; visa id: 726
  %728 = sitofp i32 %727 to float		; visa id: 727
  %729 = fmul float %724, %728		; visa id: 728
  br label %730, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 729

730:                                              ; preds = %722, %715
; BB75 :
  %.sroa.272.2 = phi float [ %729, %722 ], [ %721, %715 ]
  %731 = extractelement <4 x i8> %712, i32 2
  %732 = zext i8 %731 to i32		; visa id: 730
  br i1 %245, label %740, label %733, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 731

733:                                              ; preds = %730
; BB76 :
  %734 = and i32 %122, 1073741824
  %735 = sub nsw i32 0, %732, !spirv.Decorations !8798
  %736 = icmp eq i32 %734, 0		; visa id: 733
  %737 = select i1 %736, i32 %732, i32 %735		; visa id: 735
  %738 = sitofp i32 %737 to float		; visa id: 736
  %739 = fmul float %235, %738		; visa id: 737
  br label %748, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 738

740:                                              ; preds = %730
; BB77 :
  %741 = uitofp i32 %732 to float		; visa id: 740
  %742 = fmul float %235, %741		; visa id: 741
  %743 = and i32 %122, 1073741824
  %744 = icmp eq i32 %743, 0		; visa id: 742
  %745 = select i1 %744, i32 1, i32 -1		; visa id: 744
  %746 = sitofp i32 %745 to float		; visa id: 745
  %747 = fmul float %742, %746		; visa id: 746
  br label %748, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 747

748:                                              ; preds = %740, %733
; BB78 :
  %.sroa.320.2 = phi float [ %747, %740 ], [ %739, %733 ]
  %749 = lshr i32 %195, 24		; visa id: 748
  br i1 %245, label %756, label %750, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 749

750:                                              ; preds = %748
; BB79 :
  %751 = sub nsw i32 0, %749, !spirv.Decorations !8798
  %752 = icmp slt i32 %122, 0		; visa id: 751
  %753 = select i1 %752, i32 %751, i32 %749		; visa id: 752
  %754 = sitofp i32 %753 to float		; visa id: 753
  %755 = fmul float %235, %754		; visa id: 754
  br label %763, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 755

756:                                              ; preds = %748
; BB80 :
  %757 = uitofp i32 %749 to float		; visa id: 757
  %758 = fmul float %235, %757		; visa id: 758
  %759 = icmp sgt i32 %122, -1		; visa id: 759
  %760 = select i1 %759, i32 1, i32 -1		; visa id: 760
  %761 = sitofp i32 %760 to float		; visa id: 761
  %762 = fmul float %758, %761		; visa id: 762
  br label %763, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 763

763:                                              ; preds = %756, %750
; BB81 :
  %.sroa.368.2 = phi float [ %762, %756 ], [ %755, %750 ]
  %764 = zext i16 %614 to i32		; visa id: 764
  %765 = shl nuw i32 %764, 16		; visa id: 765
  %766 = bitcast i32 %765 to float
  %767 = fmul float %.sroa.062.2, %766		; visa id: 766
  %768 = fadd float %.sroa.6.0, %767		; visa id: 767
  %769 = zext i16 %615 to i32		; visa id: 768
  %770 = shl nuw i32 %769, 16		; visa id: 769
  %771 = bitcast i32 %770 to float
  %772 = fmul float %.sroa.80.2, %771		; visa id: 770
  %773 = fadd float %768, %772		; visa id: 771
  %774 = zext i16 %616 to i32		; visa id: 772
  %775 = shl nuw i32 %774, 16		; visa id: 773
  %776 = bitcast i32 %775 to float
  %777 = fmul float %.sroa.128.2, %776		; visa id: 774
  %778 = fadd float %773, %777		; visa id: 775
  %779 = zext i16 %617 to i32		; visa id: 776
  %780 = shl nuw i32 %779, 16		; visa id: 777
  %781 = bitcast i32 %780 to float
  %782 = fmul float %.sroa.176.2, %781		; visa id: 778
  %783 = fadd float %778, %782		; visa id: 779
  %784 = zext i16 %620 to i32		; visa id: 780
  %785 = shl nuw i32 %784, 16		; visa id: 781
  %786 = bitcast i32 %785 to float
  %787 = fmul float %.sroa.224.2, %786		; visa id: 782
  %788 = fadd float %783, %787		; visa id: 783
  %789 = zext i16 %621 to i32		; visa id: 784
  %790 = shl nuw i32 %789, 16		; visa id: 785
  %791 = bitcast i32 %790 to float
  %792 = fmul float %.sroa.272.2, %791		; visa id: 786
  %793 = fadd float %788, %792		; visa id: 787
  %794 = zext i16 %622 to i32		; visa id: 788
  %795 = shl nuw i32 %794, 16		; visa id: 789
  %796 = bitcast i32 %795 to float
  %797 = fmul float %.sroa.320.2, %796		; visa id: 790
  %798 = fadd float %793, %797		; visa id: 791
  %799 = zext i16 %623 to i32		; visa id: 792
  %800 = shl nuw i32 %799, 16		; visa id: 793
  %801 = bitcast i32 %800 to float
  %802 = fmul float %.sroa.368.2, %801		; visa id: 794
  %803 = fadd float %798, %802		; visa id: 795
  %804 = and i32 %213, 255		; visa id: 796
  br i1 %447, label %812, label %805, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 797

805:                                              ; preds = %763
; BB82 :
  %806 = and i32 %143, 16777216
  %807 = sub nsw i32 0, %804, !spirv.Decorations !8798
  %808 = icmp eq i32 %806, 0		; visa id: 799
  %809 = select i1 %808, i32 %804, i32 %807		; visa id: 801
  %810 = sitofp i32 %809 to float		; visa id: 802
  %811 = fmul float %434, %810		; visa id: 803
  br label %820, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 804

812:                                              ; preds = %763
; BB83 :
  %813 = uitofp i32 %804 to float		; visa id: 806
  %814 = fmul float %434, %813		; visa id: 807
  %815 = and i32 %143, 16777216
  %816 = icmp eq i32 %815, 0		; visa id: 808
  %817 = select i1 %816, i32 1, i32 -1		; visa id: 810
  %818 = sitofp i32 %817 to float		; visa id: 811
  %819 = fmul float %814, %818		; visa id: 812
  br label %820, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 813

820:                                              ; preds = %812, %805
; BB84 :
  %.sroa.062.3 = phi float [ %819, %812 ], [ %811, %805 ]
  %821 = bitcast i32 %213 to <4 x i8>
  %822 = extractelement <4 x i8> %821, i32 1
  %823 = zext i8 %822 to i32		; visa id: 814
  br i1 %447, label %831, label %824, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 815

824:                                              ; preds = %820
; BB85 :
  %825 = and i32 %143, 33554432
  %826 = sub nsw i32 0, %823, !spirv.Decorations !8798
  %827 = icmp eq i32 %825, 0		; visa id: 817
  %828 = select i1 %827, i32 %823, i32 %826		; visa id: 819
  %829 = sitofp i32 %828 to float		; visa id: 820
  %830 = fmul float %434, %829		; visa id: 821
  br label %839, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 822

831:                                              ; preds = %820
; BB86 :
  %832 = uitofp i32 %823 to float		; visa id: 824
  %833 = fmul float %434, %832		; visa id: 825
  %834 = and i32 %143, 33554432
  %835 = icmp eq i32 %834, 0		; visa id: 826
  %836 = select i1 %835, i32 1, i32 -1		; visa id: 828
  %837 = sitofp i32 %836 to float		; visa id: 829
  %838 = fmul float %833, %837		; visa id: 830
  br label %839, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 831

839:                                              ; preds = %831, %824
; BB87 :
  %.sroa.80.3 = phi float [ %838, %831 ], [ %830, %824 ]
  %840 = extractelement <4 x i8> %821, i32 2
  %841 = zext i8 %840 to i32		; visa id: 832
  br i1 %447, label %849, label %842, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 833

842:                                              ; preds = %839
; BB88 :
  %843 = and i32 %143, 67108864
  %844 = sub nsw i32 0, %841, !spirv.Decorations !8798
  %845 = icmp eq i32 %843, 0		; visa id: 835
  %846 = select i1 %845, i32 %841, i32 %844		; visa id: 837
  %847 = sitofp i32 %846 to float		; visa id: 838
  %848 = fmul float %434, %847		; visa id: 839
  br label %857, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 840

849:                                              ; preds = %839
; BB89 :
  %850 = uitofp i32 %841 to float		; visa id: 842
  %851 = fmul float %434, %850		; visa id: 843
  %852 = and i32 %143, 67108864
  %853 = icmp eq i32 %852, 0		; visa id: 844
  %854 = select i1 %853, i32 1, i32 -1		; visa id: 846
  %855 = sitofp i32 %854 to float		; visa id: 847
  %856 = fmul float %851, %855		; visa id: 848
  br label %857, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 849

857:                                              ; preds = %849, %842
; BB90 :
  %.sroa.128.3 = phi float [ %856, %849 ], [ %848, %842 ]
  %858 = lshr i32 %213, 24		; visa id: 850
  br i1 %447, label %866, label %859, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 851

859:                                              ; preds = %857
; BB91 :
  %860 = and i32 %143, 134217728
  %861 = sub nsw i32 0, %858, !spirv.Decorations !8798
  %862 = icmp eq i32 %860, 0		; visa id: 853
  %863 = select i1 %862, i32 %858, i32 %861		; visa id: 855
  %864 = sitofp i32 %863 to float		; visa id: 856
  %865 = fmul float %434, %864		; visa id: 857
  br label %874, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 858

866:                                              ; preds = %857
; BB92 :
  %867 = uitofp i32 %858 to float		; visa id: 860
  %868 = fmul float %434, %867		; visa id: 861
  %869 = and i32 %143, 134217728
  %870 = icmp eq i32 %869, 0		; visa id: 862
  %871 = select i1 %870, i32 1, i32 -1		; visa id: 864
  %872 = sitofp i32 %871 to float		; visa id: 865
  %873 = fmul float %868, %872		; visa id: 866
  br label %874, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 867

874:                                              ; preds = %866, %859
; BB93 :
  %.sroa.176.3 = phi float [ %873, %866 ], [ %865, %859 ]
  %875 = and i32 %214, 255		; visa id: 868
  br i1 %447, label %883, label %876, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 869

876:                                              ; preds = %874
; BB94 :
  %877 = and i32 %143, 268435456
  %878 = sub nsw i32 0, %875, !spirv.Decorations !8798
  %879 = icmp eq i32 %877, 0		; visa id: 871
  %880 = select i1 %879, i32 %875, i32 %878		; visa id: 873
  %881 = sitofp i32 %880 to float		; visa id: 874
  %882 = fmul float %434, %881		; visa id: 875
  br label %891, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 876

883:                                              ; preds = %874
; BB95 :
  %884 = uitofp i32 %875 to float		; visa id: 878
  %885 = fmul float %434, %884		; visa id: 879
  %886 = and i32 %143, 268435456
  %887 = icmp eq i32 %886, 0		; visa id: 880
  %888 = select i1 %887, i32 1, i32 -1		; visa id: 882
  %889 = sitofp i32 %888 to float		; visa id: 883
  %890 = fmul float %885, %889		; visa id: 884
  br label %891, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 885

891:                                              ; preds = %883, %876
; BB96 :
  %.sroa.224.3 = phi float [ %890, %883 ], [ %882, %876 ]
  %892 = bitcast i32 %214 to <4 x i8>
  %893 = extractelement <4 x i8> %892, i32 1
  %894 = zext i8 %893 to i32		; visa id: 886
  br i1 %447, label %902, label %895, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 887

895:                                              ; preds = %891
; BB97 :
  %896 = and i32 %143, 536870912
  %897 = sub nsw i32 0, %894, !spirv.Decorations !8798
  %898 = icmp eq i32 %896, 0		; visa id: 889
  %899 = select i1 %898, i32 %894, i32 %897		; visa id: 891
  %900 = sitofp i32 %899 to float		; visa id: 892
  %901 = fmul float %434, %900		; visa id: 893
  br label %910, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 894

902:                                              ; preds = %891
; BB98 :
  %903 = uitofp i32 %894 to float		; visa id: 896
  %904 = fmul float %434, %903		; visa id: 897
  %905 = and i32 %143, 536870912
  %906 = icmp eq i32 %905, 0		; visa id: 898
  %907 = select i1 %906, i32 1, i32 -1		; visa id: 900
  %908 = sitofp i32 %907 to float		; visa id: 901
  %909 = fmul float %904, %908		; visa id: 902
  br label %910, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 903

910:                                              ; preds = %902, %895
; BB99 :
  %.sroa.272.3 = phi float [ %909, %902 ], [ %901, %895 ]
  %911 = extractelement <4 x i8> %892, i32 2
  %912 = zext i8 %911 to i32		; visa id: 904
  br i1 %447, label %920, label %913, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 905

913:                                              ; preds = %910
; BB100 :
  %914 = and i32 %143, 1073741824
  %915 = sub nsw i32 0, %912, !spirv.Decorations !8798
  %916 = icmp eq i32 %914, 0		; visa id: 907
  %917 = select i1 %916, i32 %912, i32 %915		; visa id: 909
  %918 = sitofp i32 %917 to float		; visa id: 910
  %919 = fmul float %434, %918		; visa id: 911
  br label %928, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 912

920:                                              ; preds = %910
; BB101 :
  %921 = uitofp i32 %912 to float		; visa id: 914
  %922 = fmul float %434, %921		; visa id: 915
  %923 = and i32 %143, 1073741824
  %924 = icmp eq i32 %923, 0		; visa id: 916
  %925 = select i1 %924, i32 1, i32 -1		; visa id: 918
  %926 = sitofp i32 %925 to float		; visa id: 919
  %927 = fmul float %922, %926		; visa id: 920
  br label %928, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 921

928:                                              ; preds = %920, %913
; BB102 :
  %.sroa.320.3 = phi float [ %927, %920 ], [ %919, %913 ]
  %929 = lshr i32 %214, 24		; visa id: 922
  br i1 %447, label %936, label %930, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 923

930:                                              ; preds = %928
; BB103 :
  %931 = sub nsw i32 0, %929, !spirv.Decorations !8798
  %932 = icmp slt i32 %143, 0		; visa id: 925
  %933 = select i1 %932, i32 %931, i32 %929		; visa id: 926
  %934 = sitofp i32 %933 to float		; visa id: 927
  %935 = fmul float %434, %934		; visa id: 928
  br label %._crit_edge43.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 929

936:                                              ; preds = %928
; BB104 :
  %937 = uitofp i32 %929 to float		; visa id: 931
  %938 = fmul float %434, %937		; visa id: 932
  %939 = icmp sgt i32 %143, -1		; visa id: 933
  %940 = select i1 %939, i32 1, i32 -1		; visa id: 934
  %941 = sitofp i32 %940 to float		; visa id: 935
  %942 = fmul float %938, %941		; visa id: 936
  br label %._crit_edge43.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 937

._crit_edge43.1:                                  ; preds = %936, %930
; BB105 :
  %.sroa.368.3 = phi float [ %942, %936 ], [ %935, %930 ]
  %943 = fmul float %.sroa.062.3, %766		; visa id: 938
  %944 = fadd float %.sroa.23.0, %943		; visa id: 939
  %945 = fmul float %.sroa.80.3, %771		; visa id: 940
  %946 = fadd float %944, %945		; visa id: 941
  %947 = fmul float %.sroa.128.3, %776		; visa id: 942
  %948 = fadd float %946, %947		; visa id: 943
  %949 = fmul float %.sroa.176.3, %781		; visa id: 944
  %950 = fadd float %948, %949		; visa id: 945
  %951 = fmul float %.sroa.224.3, %786		; visa id: 946
  %952 = fadd float %950, %951		; visa id: 947
  %953 = fmul float %.sroa.272.3, %791		; visa id: 948
  %954 = fadd float %952, %953		; visa id: 949
  %955 = fmul float %.sroa.320.3, %796		; visa id: 950
  %956 = fadd float %954, %955		; visa id: 951
  %957 = fmul float %.sroa.368.3, %801		; visa id: 952
  %958 = fadd float %956, %957		; visa id: 953
  %959 = and i32 %123, 255
  %960 = shl nuw nsw i32 %160, 4		; visa id: 954
  %961 = and i32 %960, 768		; visa id: 955
  %962 = or i32 %959, %961		; visa id: 956
  %963 = shl nuw nsw i32 %962, 3, !spirv.Decorations !8791		; visa id: 957
  %964 = zext i32 %963 to i64		; visa id: 958
  %965 = add i64 %sink_, %964		; visa id: 959
  %966 = inttoptr i64 %965 to ptr addrspace(1)		; visa id: 960
  %967 = load <2 x i32>, ptr addrspace(1) %966, align 4		; visa id: 960
  %968 = bitcast i32 %123 to <4 x i8>
  %969 = extractelement <4 x i8> %968, i32 2
  %970 = shl nuw nsw i32 %160, 2		; visa id: 961
  %971 = and i32 %970, 768
  %972 = zext i8 %969 to i32		; visa id: 962
  %973 = or i32 %972, %971		; visa id: 963
  %974 = shl nuw nsw i32 %973, 3, !spirv.Decorations !8791		; visa id: 964
  %975 = zext i32 %974 to i64		; visa id: 965
  %976 = add i64 %sink_, %975		; visa id: 966
  %977 = inttoptr i64 %976 to ptr addrspace(1)		; visa id: 967
  %978 = load <2 x i32>, ptr addrspace(1) %977, align 4		; visa id: 967
  %979 = extractelement <2 x i32> %967, i32 0		; visa id: 968
  %980 = extractelement <2 x i32> %967, i32 1		; visa id: 968
  %981 = extractelement <2 x i32> %978, i32 0		; visa id: 968
  %982 = extractelement <2 x i32> %978, i32 1		; visa id: 968
  %983 = and i32 %144, 255
  %984 = shl nuw nsw i32 %185, 4		; visa id: 968
  %985 = and i32 %984, 768		; visa id: 969
  %986 = or i32 %983, %985		; visa id: 970
  %987 = shl nuw nsw i32 %986, 3, !spirv.Decorations !8791		; visa id: 971
  %988 = zext i32 %987 to i64		; visa id: 972
  %989 = add i64 %sink_, %988		; visa id: 973
  %990 = inttoptr i64 %989 to ptr addrspace(1)		; visa id: 974
  %991 = load <2 x i32>, ptr addrspace(1) %990, align 4		; visa id: 974
  %992 = bitcast i32 %144 to <4 x i8>
  %993 = extractelement <4 x i8> %992, i32 2
  %994 = shl nuw nsw i32 %185, 2		; visa id: 975
  %995 = and i32 %994, 768
  %996 = zext i8 %993 to i32		; visa id: 976
  %997 = or i32 %996, %995		; visa id: 977
  %998 = shl nuw nsw i32 %997, 3, !spirv.Decorations !8791		; visa id: 978
  %999 = zext i32 %998 to i64		; visa id: 979
  %1000 = add i64 %sink_, %999		; visa id: 980
  %1001 = inttoptr i64 %1000 to ptr addrspace(1)		; visa id: 981
  %1002 = load <2 x i32>, ptr addrspace(1) %1001, align 4		; visa id: 981
  %1003 = extractelement <2 x i32> %991, i32 0		; visa id: 982
  %1004 = extractelement <2 x i32> %991, i32 1		; visa id: 982
  %1005 = extractelement <2 x i32> %1002, i32 0		; visa id: 982
  %1006 = extractelement <2 x i32> %1002, i32 1		; visa id: 982
  %1007 = or i32 %209, 32		; visa id: 982
  %1008 = zext i32 %1007 to i64		; visa id: 983
  %1009 = add i64 %1008, %const_reg_qword2		; visa id: 984
  %IntToPtr2596 = inttoptr i64 %1009 to ptr addrspace(1)		; visa id: 985
  %vCastload597 = load i32, ptr addrspace(1) %IntToPtr2596, align 2		; visa id: 985
  %1010 = add i64 %1009, 4
  %IntToPtr2598 = inttoptr i64 %1010 to ptr addrspace(1)
  %vCastload599 = load i32, ptr addrspace(1) %IntToPtr2598, align 2		; visa id: 986
  %1011 = add i64 %1009, 8
  %IntToPtr2600 = inttoptr i64 %1011 to ptr addrspace(1)
  %vCastload601 = load i32, ptr addrspace(1) %IntToPtr2600, align 2		; visa id: 987
  %1012 = add i64 %1009, 12
  %IntToPtr2602 = inttoptr i64 %1012 to ptr addrspace(1)
  %vCastload603 = load i32, ptr addrspace(1) %IntToPtr2602, align 2		; visa id: 988
  %1013 = bitcast i32 %vCastload597 to <2 x i16>		; visa id: 989
  %1014 = bitcast i32 %vCastload599 to <2 x i16>		; visa id: 991
  %1015 = extractelement <2 x i16> %1013, i32 0		; visa id: 993
  %1016 = extractelement <2 x i16> %1013, i32 1		; visa id: 993
  %1017 = extractelement <2 x i16> %1014, i32 0		; visa id: 993
  %1018 = extractelement <2 x i16> %1014, i32 1		; visa id: 993
  %1019 = bitcast i32 %vCastload601 to <2 x i16>		; visa id: 993
  %1020 = bitcast i32 %vCastload603 to <2 x i16>		; visa id: 995
  %1021 = extractelement <2 x i16> %1019, i32 0		; visa id: 997
  %1022 = extractelement <2 x i16> %1019, i32 1		; visa id: 997
  %1023 = extractelement <2 x i16> %1020, i32 0		; visa id: 997
  %1024 = extractelement <2 x i16> %1020, i32 1		; visa id: 997
  %1025 = lshr i32 %230, 4		; visa id: 997
  %1026 = uitofp i32 %1025 to float		; visa id: 998
  %1027 = fadd float %1026, 5.000000e-01		; visa id: 999
  %1028 = fmul float %139, %1027		; visa id: 1000
  %1029 = fmul float %1028, 2.500000e-01		; visa id: 1001
  %1030 = bitcast float %1029 to i32
  %1031 = and i32 %1030, 2147483647		; visa id: 1002
  %1032 = icmp ugt i32 %1031, 2139095040
  %1033 = fcmp oeq float %238, 0x7FF0000000000000		; visa id: 1003
  %1034 = fcmp une float %238, %238
  %1035 = or i1 %1034, %1033		; visa id: 1004
  %1036 = or i1 %1035, %1032		; visa id: 1006
  %1037 = and i32 %979, 255		; visa id: 1008
  br i1 %1036, label %1045, label %1038, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1009

1038:                                             ; preds = %._crit_edge43.1
; BB106 :
  %1039 = and i32 %123, 256
  %1040 = sub nsw i32 0, %1037, !spirv.Decorations !8798
  %1041 = icmp eq i32 %1039, 0		; visa id: 1011
  %1042 = select i1 %1041, i32 %1037, i32 %1040		; visa id: 1013
  %1043 = sitofp i32 %1042 to float		; visa id: 1014
  %1044 = fmul float %1029, %1043		; visa id: 1015
  br label %1053, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1016

1045:                                             ; preds = %._crit_edge43.1
; BB107 :
  %1046 = uitofp i32 %1037 to float		; visa id: 1018
  %1047 = fmul float %1029, %1046		; visa id: 1019
  %1048 = and i32 %123, 256
  %1049 = icmp eq i32 %1048, 0		; visa id: 1020
  %1050 = select i1 %1049, i32 1, i32 -1		; visa id: 1022
  %1051 = sitofp i32 %1050 to float		; visa id: 1023
  %1052 = fmul float %1047, %1051		; visa id: 1024
  br label %1053, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1025

1053:                                             ; preds = %1045, %1038
; BB108 :
  %.sroa.062.4 = phi float [ %1052, %1045 ], [ %1044, %1038 ]
  %1054 = bitcast i32 %979 to <4 x i8>
  %1055 = extractelement <4 x i8> %1054, i32 1
  %1056 = zext i8 %1055 to i32		; visa id: 1026
  br i1 %1036, label %1064, label %1057, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1027

1057:                                             ; preds = %1053
; BB109 :
  %1058 = and i32 %123, 512
  %1059 = sub nsw i32 0, %1056, !spirv.Decorations !8798
  %1060 = icmp eq i32 %1058, 0		; visa id: 1029
  %1061 = select i1 %1060, i32 %1056, i32 %1059		; visa id: 1031
  %1062 = sitofp i32 %1061 to float		; visa id: 1032
  %1063 = fmul float %1029, %1062		; visa id: 1033
  br label %1072, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1034

1064:                                             ; preds = %1053
; BB110 :
  %1065 = uitofp i32 %1056 to float		; visa id: 1036
  %1066 = fmul float %1029, %1065		; visa id: 1037
  %1067 = and i32 %123, 512
  %1068 = icmp eq i32 %1067, 0		; visa id: 1038
  %1069 = select i1 %1068, i32 1, i32 -1		; visa id: 1040
  %1070 = sitofp i32 %1069 to float		; visa id: 1041
  %1071 = fmul float %1066, %1070		; visa id: 1042
  br label %1072, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1043

1072:                                             ; preds = %1064, %1057
; BB111 :
  %.sroa.80.4 = phi float [ %1071, %1064 ], [ %1063, %1057 ]
  %1073 = extractelement <4 x i8> %1054, i32 2
  %1074 = zext i8 %1073 to i32		; visa id: 1044
  br i1 %1036, label %1082, label %1075, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1045

1075:                                             ; preds = %1072
; BB112 :
  %1076 = and i32 %123, 1024
  %1077 = sub nsw i32 0, %1074, !spirv.Decorations !8798
  %1078 = icmp eq i32 %1076, 0		; visa id: 1047
  %1079 = select i1 %1078, i32 %1074, i32 %1077		; visa id: 1049
  %1080 = sitofp i32 %1079 to float		; visa id: 1050
  %1081 = fmul float %1029, %1080		; visa id: 1051
  br label %1090, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1052

1082:                                             ; preds = %1072
; BB113 :
  %1083 = uitofp i32 %1074 to float		; visa id: 1054
  %1084 = fmul float %1029, %1083		; visa id: 1055
  %1085 = and i32 %123, 1024
  %1086 = icmp eq i32 %1085, 0		; visa id: 1056
  %1087 = select i1 %1086, i32 1, i32 -1		; visa id: 1058
  %1088 = sitofp i32 %1087 to float		; visa id: 1059
  %1089 = fmul float %1084, %1088		; visa id: 1060
  br label %1090, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1061

1090:                                             ; preds = %1082, %1075
; BB114 :
  %.sroa.128.4 = phi float [ %1089, %1082 ], [ %1081, %1075 ]
  %1091 = lshr i32 %979, 24		; visa id: 1062
  br i1 %1036, label %1099, label %1092, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1063

1092:                                             ; preds = %1090
; BB115 :
  %1093 = and i32 %123, 2048
  %1094 = sub nsw i32 0, %1091, !spirv.Decorations !8798
  %1095 = icmp eq i32 %1093, 0		; visa id: 1065
  %1096 = select i1 %1095, i32 %1091, i32 %1094		; visa id: 1067
  %1097 = sitofp i32 %1096 to float		; visa id: 1068
  %1098 = fmul float %1029, %1097		; visa id: 1069
  br label %1107, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1070

1099:                                             ; preds = %1090
; BB116 :
  %1100 = uitofp i32 %1091 to float		; visa id: 1072
  %1101 = fmul float %1029, %1100		; visa id: 1073
  %1102 = and i32 %123, 2048
  %1103 = icmp eq i32 %1102, 0		; visa id: 1074
  %1104 = select i1 %1103, i32 1, i32 -1		; visa id: 1076
  %1105 = sitofp i32 %1104 to float		; visa id: 1077
  %1106 = fmul float %1101, %1105		; visa id: 1078
  br label %1107, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1079

1107:                                             ; preds = %1099, %1092
; BB117 :
  %.sroa.176.4 = phi float [ %1106, %1099 ], [ %1098, %1092 ]
  %1108 = and i32 %980, 255		; visa id: 1080
  br i1 %1036, label %1116, label %1109, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1081

1109:                                             ; preds = %1107
; BB118 :
  %1110 = and i32 %123, 4096
  %1111 = sub nsw i32 0, %1108, !spirv.Decorations !8798
  %1112 = icmp eq i32 %1110, 0		; visa id: 1083
  %1113 = select i1 %1112, i32 %1108, i32 %1111		; visa id: 1085
  %1114 = sitofp i32 %1113 to float		; visa id: 1086
  %1115 = fmul float %1029, %1114		; visa id: 1087
  br label %1124, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1088

1116:                                             ; preds = %1107
; BB119 :
  %1117 = uitofp i32 %1108 to float		; visa id: 1090
  %1118 = fmul float %1029, %1117		; visa id: 1091
  %1119 = and i32 %123, 4096
  %1120 = icmp eq i32 %1119, 0		; visa id: 1092
  %1121 = select i1 %1120, i32 1, i32 -1		; visa id: 1094
  %1122 = sitofp i32 %1121 to float		; visa id: 1095
  %1123 = fmul float %1118, %1122		; visa id: 1096
  br label %1124, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1097

1124:                                             ; preds = %1116, %1109
; BB120 :
  %.sroa.224.4 = phi float [ %1123, %1116 ], [ %1115, %1109 ]
  %1125 = bitcast i32 %980 to <4 x i8>
  %1126 = extractelement <4 x i8> %1125, i32 1
  %1127 = zext i8 %1126 to i32		; visa id: 1098
  br i1 %1036, label %1135, label %1128, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1099

1128:                                             ; preds = %1124
; BB121 :
  %1129 = and i32 %123, 8192
  %1130 = sub nsw i32 0, %1127, !spirv.Decorations !8798
  %1131 = icmp eq i32 %1129, 0		; visa id: 1101
  %1132 = select i1 %1131, i32 %1127, i32 %1130		; visa id: 1103
  %1133 = sitofp i32 %1132 to float		; visa id: 1104
  %1134 = fmul float %1029, %1133		; visa id: 1105
  br label %1143, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1106

1135:                                             ; preds = %1124
; BB122 :
  %1136 = uitofp i32 %1127 to float		; visa id: 1108
  %1137 = fmul float %1029, %1136		; visa id: 1109
  %1138 = and i32 %123, 8192
  %1139 = icmp eq i32 %1138, 0		; visa id: 1110
  %1140 = select i1 %1139, i32 1, i32 -1		; visa id: 1112
  %1141 = sitofp i32 %1140 to float		; visa id: 1113
  %1142 = fmul float %1137, %1141		; visa id: 1114
  br label %1143, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1115

1143:                                             ; preds = %1135, %1128
; BB123 :
  %.sroa.272.4 = phi float [ %1142, %1135 ], [ %1134, %1128 ]
  %1144 = extractelement <4 x i8> %1125, i32 2
  %1145 = zext i8 %1144 to i32		; visa id: 1116
  br i1 %1036, label %1153, label %1146, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1117

1146:                                             ; preds = %1143
; BB124 :
  %1147 = and i32 %123, 16384
  %1148 = sub nsw i32 0, %1145, !spirv.Decorations !8798
  %1149 = icmp eq i32 %1147, 0		; visa id: 1119
  %1150 = select i1 %1149, i32 %1145, i32 %1148		; visa id: 1121
  %1151 = sitofp i32 %1150 to float		; visa id: 1122
  %1152 = fmul float %1029, %1151		; visa id: 1123
  br label %1161, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1124

1153:                                             ; preds = %1143
; BB125 :
  %1154 = uitofp i32 %1145 to float		; visa id: 1126
  %1155 = fmul float %1029, %1154		; visa id: 1127
  %1156 = and i32 %123, 16384
  %1157 = icmp eq i32 %1156, 0		; visa id: 1128
  %1158 = select i1 %1157, i32 1, i32 -1		; visa id: 1130
  %1159 = sitofp i32 %1158 to float		; visa id: 1131
  %1160 = fmul float %1155, %1159		; visa id: 1132
  br label %1161, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1133

1161:                                             ; preds = %1153, %1146
; BB126 :
  %.sroa.320.4 = phi float [ %1160, %1153 ], [ %1152, %1146 ]
  %1162 = lshr i32 %980, 24		; visa id: 1134
  br i1 %1036, label %1170, label %1163, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1135

1163:                                             ; preds = %1161
; BB127 :
  %1164 = and i32 %123, 32768
  %1165 = sub nsw i32 0, %1162, !spirv.Decorations !8798
  %1166 = icmp eq i32 %1164, 0		; visa id: 1137
  %1167 = select i1 %1166, i32 %1162, i32 %1165		; visa id: 1139
  %1168 = sitofp i32 %1167 to float		; visa id: 1140
  %1169 = fmul float %1029, %1168		; visa id: 1141
  br label %1178, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1142

1170:                                             ; preds = %1161
; BB128 :
  %1171 = uitofp i32 %1162 to float		; visa id: 1144
  %1172 = fmul float %1029, %1171		; visa id: 1145
  %1173 = and i32 %123, 32768
  %1174 = icmp eq i32 %1173, 0		; visa id: 1146
  %1175 = select i1 %1174, i32 1, i32 -1		; visa id: 1148
  %1176 = sitofp i32 %1175 to float		; visa id: 1149
  %1177 = fmul float %1172, %1176		; visa id: 1150
  br label %1178, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1151

1178:                                             ; preds = %1170, %1163
; BB129 :
  %.sroa.368.4 = phi float [ %1177, %1170 ], [ %1169, %1163 ]
  %1179 = zext i16 %1015 to i32		; visa id: 1152
  %1180 = shl nuw i32 %1179, 16		; visa id: 1153
  %1181 = bitcast i32 %1180 to float
  %1182 = fmul float %.sroa.062.4, %1181		; visa id: 1154
  %1183 = fadd float %.sroa.8.0, %1182		; visa id: 1155
  %1184 = zext i16 %1016 to i32		; visa id: 1156
  %1185 = shl nuw i32 %1184, 16		; visa id: 1157
  %1186 = bitcast i32 %1185 to float
  %1187 = fmul float %.sroa.80.4, %1186		; visa id: 1158
  %1188 = fadd float %1183, %1187		; visa id: 1159
  %1189 = zext i16 %1017 to i32		; visa id: 1160
  %1190 = shl nuw i32 %1189, 16		; visa id: 1161
  %1191 = bitcast i32 %1190 to float
  %1192 = fmul float %.sroa.128.4, %1191		; visa id: 1162
  %1193 = fadd float %1188, %1192		; visa id: 1163
  %1194 = zext i16 %1018 to i32		; visa id: 1164
  %1195 = shl nuw i32 %1194, 16		; visa id: 1165
  %1196 = bitcast i32 %1195 to float
  %1197 = fmul float %.sroa.176.4, %1196		; visa id: 1166
  %1198 = fadd float %1193, %1197		; visa id: 1167
  %1199 = zext i16 %1021 to i32		; visa id: 1168
  %1200 = shl nuw i32 %1199, 16		; visa id: 1169
  %1201 = bitcast i32 %1200 to float
  %1202 = fmul float %.sroa.224.4, %1201		; visa id: 1170
  %1203 = fadd float %1198, %1202		; visa id: 1171
  %1204 = zext i16 %1022 to i32		; visa id: 1172
  %1205 = shl nuw i32 %1204, 16		; visa id: 1173
  %1206 = bitcast i32 %1205 to float
  %1207 = fmul float %.sroa.272.4, %1206		; visa id: 1174
  %1208 = fadd float %1203, %1207		; visa id: 1175
  %1209 = zext i16 %1023 to i32		; visa id: 1176
  %1210 = shl nuw i32 %1209, 16		; visa id: 1177
  %1211 = bitcast i32 %1210 to float
  %1212 = fmul float %.sroa.320.4, %1211		; visa id: 1178
  %1213 = fadd float %1208, %1212		; visa id: 1179
  %1214 = zext i16 %1024 to i32		; visa id: 1180
  %1215 = shl nuw i32 %1214, 16		; visa id: 1181
  %1216 = bitcast i32 %1215 to float
  %1217 = fmul float %.sroa.368.4, %1216		; visa id: 1182
  %1218 = fadd float %1213, %1217		; visa id: 1183
  %1219 = lshr i32 %429, 4		; visa id: 1184
  %1220 = uitofp i32 %1219 to float		; visa id: 1185
  %1221 = fadd float %1220, 5.000000e-01		; visa id: 1186
  %1222 = fmul float %158, %1221		; visa id: 1187
  %1223 = fmul float %1222, 2.500000e-01		; visa id: 1188
  %1224 = bitcast float %1223 to i32
  %1225 = and i32 %1224, 2147483647		; visa id: 1189
  %1226 = icmp ugt i32 %1225, 2139095040		; visa id: 1190
  %1227 = or i1 %440, %1226		; visa id: 1191
  %1228 = and i32 %1003, 255		; visa id: 1192
  br i1 %1227, label %1236, label %1229, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1193

1229:                                             ; preds = %1178
; BB130 :
  %1230 = and i32 %144, 256
  %1231 = sub nsw i32 0, %1228, !spirv.Decorations !8798
  %1232 = icmp eq i32 %1230, 0		; visa id: 1195
  %1233 = select i1 %1232, i32 %1228, i32 %1231		; visa id: 1197
  %1234 = sitofp i32 %1233 to float		; visa id: 1198
  %1235 = fmul float %1223, %1234		; visa id: 1199
  br label %1244, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1200

1236:                                             ; preds = %1178
; BB131 :
  %1237 = uitofp i32 %1228 to float		; visa id: 1202
  %1238 = fmul float %1223, %1237		; visa id: 1203
  %1239 = and i32 %144, 256
  %1240 = icmp eq i32 %1239, 0		; visa id: 1204
  %1241 = select i1 %1240, i32 1, i32 -1		; visa id: 1206
  %1242 = sitofp i32 %1241 to float		; visa id: 1207
  %1243 = fmul float %1238, %1242		; visa id: 1208
  br label %1244, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1209

1244:                                             ; preds = %1236, %1229
; BB132 :
  %.sroa.062.5 = phi float [ %1243, %1236 ], [ %1235, %1229 ]
  %1245 = bitcast i32 %1003 to <4 x i8>
  %1246 = extractelement <4 x i8> %1245, i32 1
  %1247 = zext i8 %1246 to i32		; visa id: 1210
  br i1 %1227, label %1255, label %1248, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1211

1248:                                             ; preds = %1244
; BB133 :
  %1249 = and i32 %144, 512
  %1250 = sub nsw i32 0, %1247, !spirv.Decorations !8798
  %1251 = icmp eq i32 %1249, 0		; visa id: 1213
  %1252 = select i1 %1251, i32 %1247, i32 %1250		; visa id: 1215
  %1253 = sitofp i32 %1252 to float		; visa id: 1216
  %1254 = fmul float %1223, %1253		; visa id: 1217
  br label %1263, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1218

1255:                                             ; preds = %1244
; BB134 :
  %1256 = uitofp i32 %1247 to float		; visa id: 1220
  %1257 = fmul float %1223, %1256		; visa id: 1221
  %1258 = and i32 %144, 512
  %1259 = icmp eq i32 %1258, 0		; visa id: 1222
  %1260 = select i1 %1259, i32 1, i32 -1		; visa id: 1224
  %1261 = sitofp i32 %1260 to float		; visa id: 1225
  %1262 = fmul float %1257, %1261		; visa id: 1226
  br label %1263, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1227

1263:                                             ; preds = %1255, %1248
; BB135 :
  %.sroa.80.5 = phi float [ %1262, %1255 ], [ %1254, %1248 ]
  %1264 = extractelement <4 x i8> %1245, i32 2
  %1265 = zext i8 %1264 to i32		; visa id: 1228
  br i1 %1227, label %1273, label %1266, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1229

1266:                                             ; preds = %1263
; BB136 :
  %1267 = and i32 %144, 1024
  %1268 = sub nsw i32 0, %1265, !spirv.Decorations !8798
  %1269 = icmp eq i32 %1267, 0		; visa id: 1231
  %1270 = select i1 %1269, i32 %1265, i32 %1268		; visa id: 1233
  %1271 = sitofp i32 %1270 to float		; visa id: 1234
  %1272 = fmul float %1223, %1271		; visa id: 1235
  br label %1281, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1236

1273:                                             ; preds = %1263
; BB137 :
  %1274 = uitofp i32 %1265 to float		; visa id: 1238
  %1275 = fmul float %1223, %1274		; visa id: 1239
  %1276 = and i32 %144, 1024
  %1277 = icmp eq i32 %1276, 0		; visa id: 1240
  %1278 = select i1 %1277, i32 1, i32 -1		; visa id: 1242
  %1279 = sitofp i32 %1278 to float		; visa id: 1243
  %1280 = fmul float %1275, %1279		; visa id: 1244
  br label %1281, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1245

1281:                                             ; preds = %1273, %1266
; BB138 :
  %.sroa.128.5 = phi float [ %1280, %1273 ], [ %1272, %1266 ]
  %1282 = lshr i32 %1003, 24		; visa id: 1246
  br i1 %1227, label %1290, label %1283, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1247

1283:                                             ; preds = %1281
; BB139 :
  %1284 = and i32 %144, 2048
  %1285 = sub nsw i32 0, %1282, !spirv.Decorations !8798
  %1286 = icmp eq i32 %1284, 0		; visa id: 1249
  %1287 = select i1 %1286, i32 %1282, i32 %1285		; visa id: 1251
  %1288 = sitofp i32 %1287 to float		; visa id: 1252
  %1289 = fmul float %1223, %1288		; visa id: 1253
  br label %1298, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1254

1290:                                             ; preds = %1281
; BB140 :
  %1291 = uitofp i32 %1282 to float		; visa id: 1256
  %1292 = fmul float %1223, %1291		; visa id: 1257
  %1293 = and i32 %144, 2048
  %1294 = icmp eq i32 %1293, 0		; visa id: 1258
  %1295 = select i1 %1294, i32 1, i32 -1		; visa id: 1260
  %1296 = sitofp i32 %1295 to float		; visa id: 1261
  %1297 = fmul float %1292, %1296		; visa id: 1262
  br label %1298, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1263

1298:                                             ; preds = %1290, %1283
; BB141 :
  %.sroa.176.5 = phi float [ %1297, %1290 ], [ %1289, %1283 ]
  %1299 = and i32 %1004, 255		; visa id: 1264
  br i1 %1227, label %1307, label %1300, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1265

1300:                                             ; preds = %1298
; BB142 :
  %1301 = and i32 %144, 4096
  %1302 = sub nsw i32 0, %1299, !spirv.Decorations !8798
  %1303 = icmp eq i32 %1301, 0		; visa id: 1267
  %1304 = select i1 %1303, i32 %1299, i32 %1302		; visa id: 1269
  %1305 = sitofp i32 %1304 to float		; visa id: 1270
  %1306 = fmul float %1223, %1305		; visa id: 1271
  br label %1315, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1272

1307:                                             ; preds = %1298
; BB143 :
  %1308 = uitofp i32 %1299 to float		; visa id: 1274
  %1309 = fmul float %1223, %1308		; visa id: 1275
  %1310 = and i32 %144, 4096
  %1311 = icmp eq i32 %1310, 0		; visa id: 1276
  %1312 = select i1 %1311, i32 1, i32 -1		; visa id: 1278
  %1313 = sitofp i32 %1312 to float		; visa id: 1279
  %1314 = fmul float %1309, %1313		; visa id: 1280
  br label %1315, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1281

1315:                                             ; preds = %1307, %1300
; BB144 :
  %.sroa.224.5 = phi float [ %1314, %1307 ], [ %1306, %1300 ]
  %1316 = bitcast i32 %1004 to <4 x i8>
  %1317 = extractelement <4 x i8> %1316, i32 1
  %1318 = zext i8 %1317 to i32		; visa id: 1282
  br i1 %1227, label %1326, label %1319, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1283

1319:                                             ; preds = %1315
; BB145 :
  %1320 = and i32 %144, 8192
  %1321 = sub nsw i32 0, %1318, !spirv.Decorations !8798
  %1322 = icmp eq i32 %1320, 0		; visa id: 1285
  %1323 = select i1 %1322, i32 %1318, i32 %1321		; visa id: 1287
  %1324 = sitofp i32 %1323 to float		; visa id: 1288
  %1325 = fmul float %1223, %1324		; visa id: 1289
  br label %1334, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1290

1326:                                             ; preds = %1315
; BB146 :
  %1327 = uitofp i32 %1318 to float		; visa id: 1292
  %1328 = fmul float %1223, %1327		; visa id: 1293
  %1329 = and i32 %144, 8192
  %1330 = icmp eq i32 %1329, 0		; visa id: 1294
  %1331 = select i1 %1330, i32 1, i32 -1		; visa id: 1296
  %1332 = sitofp i32 %1331 to float		; visa id: 1297
  %1333 = fmul float %1328, %1332		; visa id: 1298
  br label %1334, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1299

1334:                                             ; preds = %1326, %1319
; BB147 :
  %.sroa.272.5 = phi float [ %1333, %1326 ], [ %1325, %1319 ]
  %1335 = extractelement <4 x i8> %1316, i32 2
  %1336 = zext i8 %1335 to i32		; visa id: 1300
  br i1 %1227, label %1344, label %1337, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1301

1337:                                             ; preds = %1334
; BB148 :
  %1338 = and i32 %144, 16384
  %1339 = sub nsw i32 0, %1336, !spirv.Decorations !8798
  %1340 = icmp eq i32 %1338, 0		; visa id: 1303
  %1341 = select i1 %1340, i32 %1336, i32 %1339		; visa id: 1305
  %1342 = sitofp i32 %1341 to float		; visa id: 1306
  %1343 = fmul float %1223, %1342		; visa id: 1307
  br label %1352, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1308

1344:                                             ; preds = %1334
; BB149 :
  %1345 = uitofp i32 %1336 to float		; visa id: 1310
  %1346 = fmul float %1223, %1345		; visa id: 1311
  %1347 = and i32 %144, 16384
  %1348 = icmp eq i32 %1347, 0		; visa id: 1312
  %1349 = select i1 %1348, i32 1, i32 -1		; visa id: 1314
  %1350 = sitofp i32 %1349 to float		; visa id: 1315
  %1351 = fmul float %1346, %1350		; visa id: 1316
  br label %1352, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1317

1352:                                             ; preds = %1344, %1337
; BB150 :
  %.sroa.320.5 = phi float [ %1351, %1344 ], [ %1343, %1337 ]
  %1353 = lshr i32 %1004, 24		; visa id: 1318
  br i1 %1227, label %1361, label %1354, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1319

1354:                                             ; preds = %1352
; BB151 :
  %1355 = and i32 %144, 32768
  %1356 = sub nsw i32 0, %1353, !spirv.Decorations !8798
  %1357 = icmp eq i32 %1355, 0		; visa id: 1321
  %1358 = select i1 %1357, i32 %1353, i32 %1356		; visa id: 1323
  %1359 = sitofp i32 %1358 to float		; visa id: 1324
  %1360 = fmul float %1223, %1359		; visa id: 1325
  br label %1369, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1326

1361:                                             ; preds = %1352
; BB152 :
  %1362 = uitofp i32 %1353 to float		; visa id: 1328
  %1363 = fmul float %1223, %1362		; visa id: 1329
  %1364 = and i32 %144, 32768
  %1365 = icmp eq i32 %1364, 0		; visa id: 1330
  %1366 = select i1 %1365, i32 1, i32 -1		; visa id: 1332
  %1367 = sitofp i32 %1366 to float		; visa id: 1333
  %1368 = fmul float %1363, %1367		; visa id: 1334
  br label %1369, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1335

1369:                                             ; preds = %1361, %1354
; BB153 :
  %.sroa.368.5 = phi float [ %1368, %1361 ], [ %1360, %1354 ]
  %1370 = fmul float %.sroa.062.5, %1181		; visa id: 1336
  %1371 = fadd float %.sroa.25.0, %1370		; visa id: 1337
  %1372 = fmul float %.sroa.80.5, %1186		; visa id: 1338
  %1373 = fadd float %1371, %1372		; visa id: 1339
  %1374 = fmul float %.sroa.128.5, %1191		; visa id: 1340
  %1375 = fadd float %1373, %1374		; visa id: 1341
  %1376 = fmul float %.sroa.176.5, %1196		; visa id: 1342
  %1377 = fadd float %1375, %1376		; visa id: 1343
  %1378 = fmul float %.sroa.224.5, %1201		; visa id: 1344
  %1379 = fadd float %1377, %1378		; visa id: 1345
  %1380 = fmul float %.sroa.272.5, %1206		; visa id: 1346
  %1381 = fadd float %1379, %1380		; visa id: 1347
  %1382 = fmul float %.sroa.320.5, %1211		; visa id: 1348
  %1383 = fadd float %1381, %1382		; visa id: 1349
  %1384 = fmul float %.sroa.368.5, %1216		; visa id: 1350
  %1385 = fadd float %1383, %1384		; visa id: 1351
  %1386 = or i32 %209, 48		; visa id: 1352
  %1387 = zext i32 %1386 to i64		; visa id: 1353
  %1388 = add i64 %1387, %const_reg_qword2		; visa id: 1354
  %IntToPtr2604 = inttoptr i64 %1388 to ptr addrspace(1)		; visa id: 1355
  %vCastload605 = load i32, ptr addrspace(1) %IntToPtr2604, align 2		; visa id: 1355
  %1389 = add i64 %1388, 4
  %IntToPtr2606 = inttoptr i64 %1389 to ptr addrspace(1)
  %vCastload607 = load i32, ptr addrspace(1) %IntToPtr2606, align 2		; visa id: 1356
  %1390 = add i64 %1388, 8
  %IntToPtr2608 = inttoptr i64 %1390 to ptr addrspace(1)
  %vCastload609 = load i32, ptr addrspace(1) %IntToPtr2608, align 2		; visa id: 1357
  %1391 = add i64 %1388, 12
  %IntToPtr2610 = inttoptr i64 %1391 to ptr addrspace(1)
  %vCastload611 = load i32, ptr addrspace(1) %IntToPtr2610, align 2		; visa id: 1358
  %1392 = bitcast i32 %vCastload605 to <2 x i16>		; visa id: 1359
  %1393 = bitcast i32 %vCastload607 to <2 x i16>		; visa id: 1361
  %1394 = extractelement <2 x i16> %1392, i32 0		; visa id: 1363
  %1395 = extractelement <2 x i16> %1392, i32 1		; visa id: 1363
  %1396 = extractelement <2 x i16> %1393, i32 0		; visa id: 1363
  %1397 = extractelement <2 x i16> %1393, i32 1		; visa id: 1363
  %1398 = bitcast i32 %vCastload609 to <2 x i16>		; visa id: 1363
  %1399 = bitcast i32 %vCastload611 to <2 x i16>		; visa id: 1365
  %1400 = extractelement <2 x i16> %1398, i32 0		; visa id: 1367
  %1401 = extractelement <2 x i16> %1398, i32 1		; visa id: 1367
  %1402 = extractelement <2 x i16> %1399, i32 0		; visa id: 1367
  %1403 = extractelement <2 x i16> %1399, i32 1		; visa id: 1367
  %1404 = and i32 %981, 255		; visa id: 1367
  br i1 %1036, label %1412, label %1405, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1368

1405:                                             ; preds = %1369
; BB154 :
  %1406 = and i32 %123, 16777216
  %1407 = sub nsw i32 0, %1404, !spirv.Decorations !8798
  %1408 = icmp eq i32 %1406, 0		; visa id: 1370
  %1409 = select i1 %1408, i32 %1404, i32 %1407		; visa id: 1372
  %1410 = sitofp i32 %1409 to float		; visa id: 1373
  %1411 = fmul float %1029, %1410		; visa id: 1374
  br label %1420, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1375

1412:                                             ; preds = %1369
; BB155 :
  %1413 = uitofp i32 %1404 to float		; visa id: 1377
  %1414 = fmul float %1029, %1413		; visa id: 1378
  %1415 = and i32 %123, 16777216
  %1416 = icmp eq i32 %1415, 0		; visa id: 1379
  %1417 = select i1 %1416, i32 1, i32 -1		; visa id: 1381
  %1418 = sitofp i32 %1417 to float		; visa id: 1382
  %1419 = fmul float %1414, %1418		; visa id: 1383
  br label %1420, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1384

1420:                                             ; preds = %1412, %1405
; BB156 :
  %.sroa.062.6 = phi float [ %1419, %1412 ], [ %1411, %1405 ]
  %1421 = bitcast i32 %981 to <4 x i8>
  %1422 = extractelement <4 x i8> %1421, i32 1
  %1423 = zext i8 %1422 to i32		; visa id: 1385
  br i1 %1036, label %1431, label %1424, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1386

1424:                                             ; preds = %1420
; BB157 :
  %1425 = and i32 %123, 33554432
  %1426 = sub nsw i32 0, %1423, !spirv.Decorations !8798
  %1427 = icmp eq i32 %1425, 0		; visa id: 1388
  %1428 = select i1 %1427, i32 %1423, i32 %1426		; visa id: 1390
  %1429 = sitofp i32 %1428 to float		; visa id: 1391
  %1430 = fmul float %1029, %1429		; visa id: 1392
  br label %1439, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1393

1431:                                             ; preds = %1420
; BB158 :
  %1432 = uitofp i32 %1423 to float		; visa id: 1395
  %1433 = fmul float %1029, %1432		; visa id: 1396
  %1434 = and i32 %123, 33554432
  %1435 = icmp eq i32 %1434, 0		; visa id: 1397
  %1436 = select i1 %1435, i32 1, i32 -1		; visa id: 1399
  %1437 = sitofp i32 %1436 to float		; visa id: 1400
  %1438 = fmul float %1433, %1437		; visa id: 1401
  br label %1439, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1402

1439:                                             ; preds = %1431, %1424
; BB159 :
  %.sroa.80.6 = phi float [ %1438, %1431 ], [ %1430, %1424 ]
  %1440 = extractelement <4 x i8> %1421, i32 2
  %1441 = zext i8 %1440 to i32		; visa id: 1403
  br i1 %1036, label %1449, label %1442, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1404

1442:                                             ; preds = %1439
; BB160 :
  %1443 = and i32 %123, 67108864
  %1444 = sub nsw i32 0, %1441, !spirv.Decorations !8798
  %1445 = icmp eq i32 %1443, 0		; visa id: 1406
  %1446 = select i1 %1445, i32 %1441, i32 %1444		; visa id: 1408
  %1447 = sitofp i32 %1446 to float		; visa id: 1409
  %1448 = fmul float %1029, %1447		; visa id: 1410
  br label %1457, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1411

1449:                                             ; preds = %1439
; BB161 :
  %1450 = uitofp i32 %1441 to float		; visa id: 1413
  %1451 = fmul float %1029, %1450		; visa id: 1414
  %1452 = and i32 %123, 67108864
  %1453 = icmp eq i32 %1452, 0		; visa id: 1415
  %1454 = select i1 %1453, i32 1, i32 -1		; visa id: 1417
  %1455 = sitofp i32 %1454 to float		; visa id: 1418
  %1456 = fmul float %1451, %1455		; visa id: 1419
  br label %1457, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1420

1457:                                             ; preds = %1449, %1442
; BB162 :
  %.sroa.128.6 = phi float [ %1456, %1449 ], [ %1448, %1442 ]
  %1458 = lshr i32 %981, 24		; visa id: 1421
  br i1 %1036, label %1466, label %1459, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1422

1459:                                             ; preds = %1457
; BB163 :
  %1460 = and i32 %123, 134217728
  %1461 = sub nsw i32 0, %1458, !spirv.Decorations !8798
  %1462 = icmp eq i32 %1460, 0		; visa id: 1424
  %1463 = select i1 %1462, i32 %1458, i32 %1461		; visa id: 1426
  %1464 = sitofp i32 %1463 to float		; visa id: 1427
  %1465 = fmul float %1029, %1464		; visa id: 1428
  br label %1474, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1429

1466:                                             ; preds = %1457
; BB164 :
  %1467 = uitofp i32 %1458 to float		; visa id: 1431
  %1468 = fmul float %1029, %1467		; visa id: 1432
  %1469 = and i32 %123, 134217728
  %1470 = icmp eq i32 %1469, 0		; visa id: 1433
  %1471 = select i1 %1470, i32 1, i32 -1		; visa id: 1435
  %1472 = sitofp i32 %1471 to float		; visa id: 1436
  %1473 = fmul float %1468, %1472		; visa id: 1437
  br label %1474, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1438

1474:                                             ; preds = %1466, %1459
; BB165 :
  %.sroa.176.6 = phi float [ %1473, %1466 ], [ %1465, %1459 ]
  %1475 = and i32 %982, 255		; visa id: 1439
  br i1 %1036, label %1483, label %1476, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1440

1476:                                             ; preds = %1474
; BB166 :
  %1477 = and i32 %123, 268435456
  %1478 = sub nsw i32 0, %1475, !spirv.Decorations !8798
  %1479 = icmp eq i32 %1477, 0		; visa id: 1442
  %1480 = select i1 %1479, i32 %1475, i32 %1478		; visa id: 1444
  %1481 = sitofp i32 %1480 to float		; visa id: 1445
  %1482 = fmul float %1029, %1481		; visa id: 1446
  br label %1491, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1447

1483:                                             ; preds = %1474
; BB167 :
  %1484 = uitofp i32 %1475 to float		; visa id: 1449
  %1485 = fmul float %1029, %1484		; visa id: 1450
  %1486 = and i32 %123, 268435456
  %1487 = icmp eq i32 %1486, 0		; visa id: 1451
  %1488 = select i1 %1487, i32 1, i32 -1		; visa id: 1453
  %1489 = sitofp i32 %1488 to float		; visa id: 1454
  %1490 = fmul float %1485, %1489		; visa id: 1455
  br label %1491, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1456

1491:                                             ; preds = %1483, %1476
; BB168 :
  %.sroa.224.6 = phi float [ %1490, %1483 ], [ %1482, %1476 ]
  %1492 = bitcast i32 %982 to <4 x i8>
  %1493 = extractelement <4 x i8> %1492, i32 1
  %1494 = zext i8 %1493 to i32		; visa id: 1457
  br i1 %1036, label %1502, label %1495, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1458

1495:                                             ; preds = %1491
; BB169 :
  %1496 = and i32 %123, 536870912
  %1497 = sub nsw i32 0, %1494, !spirv.Decorations !8798
  %1498 = icmp eq i32 %1496, 0		; visa id: 1460
  %1499 = select i1 %1498, i32 %1494, i32 %1497		; visa id: 1462
  %1500 = sitofp i32 %1499 to float		; visa id: 1463
  %1501 = fmul float %1029, %1500		; visa id: 1464
  br label %1510, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1465

1502:                                             ; preds = %1491
; BB170 :
  %1503 = uitofp i32 %1494 to float		; visa id: 1467
  %1504 = fmul float %1029, %1503		; visa id: 1468
  %1505 = and i32 %123, 536870912
  %1506 = icmp eq i32 %1505, 0		; visa id: 1469
  %1507 = select i1 %1506, i32 1, i32 -1		; visa id: 1471
  %1508 = sitofp i32 %1507 to float		; visa id: 1472
  %1509 = fmul float %1504, %1508		; visa id: 1473
  br label %1510, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1474

1510:                                             ; preds = %1502, %1495
; BB171 :
  %.sroa.272.6 = phi float [ %1509, %1502 ], [ %1501, %1495 ]
  %1511 = extractelement <4 x i8> %1492, i32 2
  %1512 = zext i8 %1511 to i32		; visa id: 1475
  br i1 %1036, label %1520, label %1513, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1476

1513:                                             ; preds = %1510
; BB172 :
  %1514 = and i32 %123, 1073741824
  %1515 = sub nsw i32 0, %1512, !spirv.Decorations !8798
  %1516 = icmp eq i32 %1514, 0		; visa id: 1478
  %1517 = select i1 %1516, i32 %1512, i32 %1515		; visa id: 1480
  %1518 = sitofp i32 %1517 to float		; visa id: 1481
  %1519 = fmul float %1029, %1518		; visa id: 1482
  br label %1528, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1483

1520:                                             ; preds = %1510
; BB173 :
  %1521 = uitofp i32 %1512 to float		; visa id: 1485
  %1522 = fmul float %1029, %1521		; visa id: 1486
  %1523 = and i32 %123, 1073741824
  %1524 = icmp eq i32 %1523, 0		; visa id: 1487
  %1525 = select i1 %1524, i32 1, i32 -1		; visa id: 1489
  %1526 = sitofp i32 %1525 to float		; visa id: 1490
  %1527 = fmul float %1522, %1526		; visa id: 1491
  br label %1528, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1492

1528:                                             ; preds = %1520, %1513
; BB174 :
  %.sroa.320.6 = phi float [ %1527, %1520 ], [ %1519, %1513 ]
  %1529 = lshr i32 %982, 24		; visa id: 1493
  br i1 %1036, label %1536, label %1530, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1494

1530:                                             ; preds = %1528
; BB175 :
  %1531 = sub nsw i32 0, %1529, !spirv.Decorations !8798
  %1532 = icmp slt i32 %123, 0		; visa id: 1496
  %1533 = select i1 %1532, i32 %1531, i32 %1529		; visa id: 1497
  %1534 = sitofp i32 %1533 to float		; visa id: 1498
  %1535 = fmul float %1029, %1534		; visa id: 1499
  br label %1543, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1500

1536:                                             ; preds = %1528
; BB176 :
  %1537 = uitofp i32 %1529 to float		; visa id: 1502
  %1538 = fmul float %1029, %1537		; visa id: 1503
  %1539 = icmp sgt i32 %123, -1		; visa id: 1504
  %1540 = select i1 %1539, i32 1, i32 -1		; visa id: 1505
  %1541 = sitofp i32 %1540 to float		; visa id: 1506
  %1542 = fmul float %1538, %1541		; visa id: 1507
  br label %1543, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1508

1543:                                             ; preds = %1536, %1530
; BB177 :
  %.sroa.368.6 = phi float [ %1542, %1536 ], [ %1535, %1530 ]
  %1544 = zext i16 %1394 to i32		; visa id: 1509
  %1545 = shl nuw i32 %1544, 16		; visa id: 1510
  %1546 = bitcast i32 %1545 to float
  %1547 = fmul float %.sroa.062.6, %1546		; visa id: 1511
  %1548 = fadd float %.sroa.10.0, %1547		; visa id: 1512
  %1549 = zext i16 %1395 to i32		; visa id: 1513
  %1550 = shl nuw i32 %1549, 16		; visa id: 1514
  %1551 = bitcast i32 %1550 to float
  %1552 = fmul float %.sroa.80.6, %1551		; visa id: 1515
  %1553 = fadd float %1548, %1552		; visa id: 1516
  %1554 = zext i16 %1396 to i32		; visa id: 1517
  %1555 = shl nuw i32 %1554, 16		; visa id: 1518
  %1556 = bitcast i32 %1555 to float
  %1557 = fmul float %.sroa.128.6, %1556		; visa id: 1519
  %1558 = fadd float %1553, %1557		; visa id: 1520
  %1559 = zext i16 %1397 to i32		; visa id: 1521
  %1560 = shl nuw i32 %1559, 16		; visa id: 1522
  %1561 = bitcast i32 %1560 to float
  %1562 = fmul float %.sroa.176.6, %1561		; visa id: 1523
  %1563 = fadd float %1558, %1562		; visa id: 1524
  %1564 = zext i16 %1400 to i32		; visa id: 1525
  %1565 = shl nuw i32 %1564, 16		; visa id: 1526
  %1566 = bitcast i32 %1565 to float
  %1567 = fmul float %.sroa.224.6, %1566		; visa id: 1527
  %1568 = fadd float %1563, %1567		; visa id: 1528
  %1569 = zext i16 %1401 to i32		; visa id: 1529
  %1570 = shl nuw i32 %1569, 16		; visa id: 1530
  %1571 = bitcast i32 %1570 to float
  %1572 = fmul float %.sroa.272.6, %1571		; visa id: 1531
  %1573 = fadd float %1568, %1572		; visa id: 1532
  %1574 = zext i16 %1402 to i32		; visa id: 1533
  %1575 = shl nuw i32 %1574, 16		; visa id: 1534
  %1576 = bitcast i32 %1575 to float
  %1577 = fmul float %.sroa.320.6, %1576		; visa id: 1535
  %1578 = fadd float %1573, %1577		; visa id: 1536
  %1579 = zext i16 %1403 to i32		; visa id: 1537
  %1580 = shl nuw i32 %1579, 16		; visa id: 1538
  %1581 = bitcast i32 %1580 to float
  %1582 = fmul float %.sroa.368.6, %1581		; visa id: 1539
  %1583 = fadd float %1578, %1582		; visa id: 1540
  %1584 = and i32 %1005, 255		; visa id: 1541
  br i1 %1227, label %1592, label %1585, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1542

1585:                                             ; preds = %1543
; BB178 :
  %1586 = and i32 %144, 16777216
  %1587 = sub nsw i32 0, %1584, !spirv.Decorations !8798
  %1588 = icmp eq i32 %1586, 0		; visa id: 1544
  %1589 = select i1 %1588, i32 %1584, i32 %1587		; visa id: 1546
  %1590 = sitofp i32 %1589 to float		; visa id: 1547
  %1591 = fmul float %1223, %1590		; visa id: 1548
  br label %1600, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1549

1592:                                             ; preds = %1543
; BB179 :
  %1593 = uitofp i32 %1584 to float		; visa id: 1551
  %1594 = fmul float %1223, %1593		; visa id: 1552
  %1595 = and i32 %144, 16777216
  %1596 = icmp eq i32 %1595, 0		; visa id: 1553
  %1597 = select i1 %1596, i32 1, i32 -1		; visa id: 1555
  %1598 = sitofp i32 %1597 to float		; visa id: 1556
  %1599 = fmul float %1594, %1598		; visa id: 1557
  br label %1600, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1558

1600:                                             ; preds = %1592, %1585
; BB180 :
  %.sroa.062.7 = phi float [ %1599, %1592 ], [ %1591, %1585 ]
  %1601 = bitcast i32 %1005 to <4 x i8>
  %1602 = extractelement <4 x i8> %1601, i32 1
  %1603 = zext i8 %1602 to i32		; visa id: 1559
  br i1 %1227, label %1611, label %1604, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1560

1604:                                             ; preds = %1600
; BB181 :
  %1605 = and i32 %144, 33554432
  %1606 = sub nsw i32 0, %1603, !spirv.Decorations !8798
  %1607 = icmp eq i32 %1605, 0		; visa id: 1562
  %1608 = select i1 %1607, i32 %1603, i32 %1606		; visa id: 1564
  %1609 = sitofp i32 %1608 to float		; visa id: 1565
  %1610 = fmul float %1223, %1609		; visa id: 1566
  br label %1619, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1567

1611:                                             ; preds = %1600
; BB182 :
  %1612 = uitofp i32 %1603 to float		; visa id: 1569
  %1613 = fmul float %1223, %1612		; visa id: 1570
  %1614 = and i32 %144, 33554432
  %1615 = icmp eq i32 %1614, 0		; visa id: 1571
  %1616 = select i1 %1615, i32 1, i32 -1		; visa id: 1573
  %1617 = sitofp i32 %1616 to float		; visa id: 1574
  %1618 = fmul float %1613, %1617		; visa id: 1575
  br label %1619, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1576

1619:                                             ; preds = %1611, %1604
; BB183 :
  %.sroa.80.7 = phi float [ %1618, %1611 ], [ %1610, %1604 ]
  %1620 = extractelement <4 x i8> %1601, i32 2
  %1621 = zext i8 %1620 to i32		; visa id: 1577
  br i1 %1227, label %1629, label %1622, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1578

1622:                                             ; preds = %1619
; BB184 :
  %1623 = and i32 %144, 67108864
  %1624 = sub nsw i32 0, %1621, !spirv.Decorations !8798
  %1625 = icmp eq i32 %1623, 0		; visa id: 1580
  %1626 = select i1 %1625, i32 %1621, i32 %1624		; visa id: 1582
  %1627 = sitofp i32 %1626 to float		; visa id: 1583
  %1628 = fmul float %1223, %1627		; visa id: 1584
  br label %1637, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1585

1629:                                             ; preds = %1619
; BB185 :
  %1630 = uitofp i32 %1621 to float		; visa id: 1587
  %1631 = fmul float %1223, %1630		; visa id: 1588
  %1632 = and i32 %144, 67108864
  %1633 = icmp eq i32 %1632, 0		; visa id: 1589
  %1634 = select i1 %1633, i32 1, i32 -1		; visa id: 1591
  %1635 = sitofp i32 %1634 to float		; visa id: 1592
  %1636 = fmul float %1631, %1635		; visa id: 1593
  br label %1637, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1594

1637:                                             ; preds = %1629, %1622
; BB186 :
  %.sroa.128.7 = phi float [ %1636, %1629 ], [ %1628, %1622 ]
  %1638 = lshr i32 %1005, 24		; visa id: 1595
  br i1 %1227, label %1646, label %1639, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1596

1639:                                             ; preds = %1637
; BB187 :
  %1640 = and i32 %144, 134217728
  %1641 = sub nsw i32 0, %1638, !spirv.Decorations !8798
  %1642 = icmp eq i32 %1640, 0		; visa id: 1598
  %1643 = select i1 %1642, i32 %1638, i32 %1641		; visa id: 1600
  %1644 = sitofp i32 %1643 to float		; visa id: 1601
  %1645 = fmul float %1223, %1644		; visa id: 1602
  br label %1654, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1603

1646:                                             ; preds = %1637
; BB188 :
  %1647 = uitofp i32 %1638 to float		; visa id: 1605
  %1648 = fmul float %1223, %1647		; visa id: 1606
  %1649 = and i32 %144, 134217728
  %1650 = icmp eq i32 %1649, 0		; visa id: 1607
  %1651 = select i1 %1650, i32 1, i32 -1		; visa id: 1609
  %1652 = sitofp i32 %1651 to float		; visa id: 1610
  %1653 = fmul float %1648, %1652		; visa id: 1611
  br label %1654, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1612

1654:                                             ; preds = %1646, %1639
; BB189 :
  %.sroa.176.7 = phi float [ %1653, %1646 ], [ %1645, %1639 ]
  %1655 = and i32 %1006, 255		; visa id: 1613
  br i1 %1227, label %1663, label %1656, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1614

1656:                                             ; preds = %1654
; BB190 :
  %1657 = and i32 %144, 268435456
  %1658 = sub nsw i32 0, %1655, !spirv.Decorations !8798
  %1659 = icmp eq i32 %1657, 0		; visa id: 1616
  %1660 = select i1 %1659, i32 %1655, i32 %1658		; visa id: 1618
  %1661 = sitofp i32 %1660 to float		; visa id: 1619
  %1662 = fmul float %1223, %1661		; visa id: 1620
  br label %1671, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1621

1663:                                             ; preds = %1654
; BB191 :
  %1664 = uitofp i32 %1655 to float		; visa id: 1623
  %1665 = fmul float %1223, %1664		; visa id: 1624
  %1666 = and i32 %144, 268435456
  %1667 = icmp eq i32 %1666, 0		; visa id: 1625
  %1668 = select i1 %1667, i32 1, i32 -1		; visa id: 1627
  %1669 = sitofp i32 %1668 to float		; visa id: 1628
  %1670 = fmul float %1665, %1669		; visa id: 1629
  br label %1671, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1630

1671:                                             ; preds = %1663, %1656
; BB192 :
  %.sroa.224.7 = phi float [ %1670, %1663 ], [ %1662, %1656 ]
  %1672 = bitcast i32 %1006 to <4 x i8>
  %1673 = extractelement <4 x i8> %1672, i32 1
  %1674 = zext i8 %1673 to i32		; visa id: 1631
  br i1 %1227, label %1682, label %1675, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1632

1675:                                             ; preds = %1671
; BB193 :
  %1676 = and i32 %144, 536870912
  %1677 = sub nsw i32 0, %1674, !spirv.Decorations !8798
  %1678 = icmp eq i32 %1676, 0		; visa id: 1634
  %1679 = select i1 %1678, i32 %1674, i32 %1677		; visa id: 1636
  %1680 = sitofp i32 %1679 to float		; visa id: 1637
  %1681 = fmul float %1223, %1680		; visa id: 1638
  br label %1690, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1639

1682:                                             ; preds = %1671
; BB194 :
  %1683 = uitofp i32 %1674 to float		; visa id: 1641
  %1684 = fmul float %1223, %1683		; visa id: 1642
  %1685 = and i32 %144, 536870912
  %1686 = icmp eq i32 %1685, 0		; visa id: 1643
  %1687 = select i1 %1686, i32 1, i32 -1		; visa id: 1645
  %1688 = sitofp i32 %1687 to float		; visa id: 1646
  %1689 = fmul float %1684, %1688		; visa id: 1647
  br label %1690, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1648

1690:                                             ; preds = %1682, %1675
; BB195 :
  %.sroa.272.7 = phi float [ %1689, %1682 ], [ %1681, %1675 ]
  %1691 = extractelement <4 x i8> %1672, i32 2
  %1692 = zext i8 %1691 to i32		; visa id: 1649
  br i1 %1227, label %1700, label %1693, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1650

1693:                                             ; preds = %1690
; BB196 :
  %1694 = and i32 %144, 1073741824
  %1695 = sub nsw i32 0, %1692, !spirv.Decorations !8798
  %1696 = icmp eq i32 %1694, 0		; visa id: 1652
  %1697 = select i1 %1696, i32 %1692, i32 %1695		; visa id: 1654
  %1698 = sitofp i32 %1697 to float		; visa id: 1655
  %1699 = fmul float %1223, %1698		; visa id: 1656
  br label %1708, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1657

1700:                                             ; preds = %1690
; BB197 :
  %1701 = uitofp i32 %1692 to float		; visa id: 1659
  %1702 = fmul float %1223, %1701		; visa id: 1660
  %1703 = and i32 %144, 1073741824
  %1704 = icmp eq i32 %1703, 0		; visa id: 1661
  %1705 = select i1 %1704, i32 1, i32 -1		; visa id: 1663
  %1706 = sitofp i32 %1705 to float		; visa id: 1664
  %1707 = fmul float %1702, %1706		; visa id: 1665
  br label %1708, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1666

1708:                                             ; preds = %1700, %1693
; BB198 :
  %.sroa.320.7 = phi float [ %1707, %1700 ], [ %1699, %1693 ]
  %1709 = lshr i32 %1006, 24		; visa id: 1667
  br i1 %1227, label %1716, label %1710, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1668

1710:                                             ; preds = %1708
; BB199 :
  %1711 = sub nsw i32 0, %1709, !spirv.Decorations !8798
  %1712 = icmp slt i32 %144, 0		; visa id: 1670
  %1713 = select i1 %1712, i32 %1711, i32 %1709		; visa id: 1671
  %1714 = sitofp i32 %1713 to float		; visa id: 1672
  %1715 = fmul float %1223, %1714		; visa id: 1673
  br label %._crit_edge43.2, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1674

1716:                                             ; preds = %1708
; BB200 :
  %1717 = uitofp i32 %1709 to float		; visa id: 1676
  %1718 = fmul float %1223, %1717		; visa id: 1677
  %1719 = icmp sgt i32 %144, -1		; visa id: 1678
  %1720 = select i1 %1719, i32 1, i32 -1		; visa id: 1679
  %1721 = sitofp i32 %1720 to float		; visa id: 1680
  %1722 = fmul float %1718, %1721		; visa id: 1681
  br label %._crit_edge43.2, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1682

._crit_edge43.2:                                  ; preds = %1716, %1710
; BB201 :
  %.sroa.368.7 = phi float [ %1722, %1716 ], [ %1715, %1710 ]
  %1723 = fmul float %.sroa.062.7, %1546		; visa id: 1683
  %1724 = fadd float %.sroa.27.0, %1723		; visa id: 1684
  %1725 = fmul float %.sroa.80.7, %1551		; visa id: 1685
  %1726 = fadd float %1724, %1725		; visa id: 1686
  %1727 = fmul float %.sroa.128.7, %1556		; visa id: 1687
  %1728 = fadd float %1726, %1727		; visa id: 1688
  %1729 = fmul float %.sroa.176.7, %1561		; visa id: 1689
  %1730 = fadd float %1728, %1729		; visa id: 1690
  %1731 = fmul float %.sroa.224.7, %1566		; visa id: 1691
  %1732 = fadd float %1730, %1731		; visa id: 1692
  %1733 = fmul float %.sroa.272.7, %1571		; visa id: 1693
  %1734 = fadd float %1732, %1733		; visa id: 1694
  %1735 = fmul float %.sroa.320.7, %1576		; visa id: 1695
  %1736 = fadd float %1734, %1735		; visa id: 1696
  %1737 = fmul float %.sroa.368.7, %1581		; visa id: 1697
  %1738 = fadd float %1736, %1737		; visa id: 1698
  %1739 = lshr i16 %134, 8		; visa id: 1699
  %1740 = and i32 %124, 255
  %1741 = and i32 %160, 768		; visa id: 1700
  %1742 = or i32 %1740, %1741		; visa id: 1701
  %1743 = shl nuw nsw i32 %1742, 3, !spirv.Decorations !8791		; visa id: 1702
  %1744 = zext i32 %1743 to i64		; visa id: 1703
  %1745 = add i64 %sink_, %1744		; visa id: 1704
  %1746 = inttoptr i64 %1745 to ptr addrspace(1)		; visa id: 1705
  %1747 = load <2 x i32>, ptr addrspace(1) %1746, align 4		; visa id: 1705
  %1748 = bitcast i32 %124 to <4 x i8>
  %1749 = extractelement <4 x i8> %1748, i32 2
  %1750 = lshr i32 %160, 2		; visa id: 1706
  %1751 = and i32 %1750, 768
  %1752 = zext i8 %1749 to i32		; visa id: 1707
  %1753 = or i32 %1752, %1751		; visa id: 1708
  %1754 = shl nuw nsw i32 %1753, 3, !spirv.Decorations !8791		; visa id: 1709
  %1755 = zext i32 %1754 to i64		; visa id: 1710
  %1756 = add i64 %sink_, %1755		; visa id: 1711
  %1757 = inttoptr i64 %1756 to ptr addrspace(1)		; visa id: 1712
  %1758 = load <2 x i32>, ptr addrspace(1) %1757, align 4		; visa id: 1712
  %1759 = extractelement <2 x i32> %1747, i32 0		; visa id: 1713
  %1760 = extractelement <2 x i32> %1747, i32 1		; visa id: 1713
  %1761 = extractelement <2 x i32> %1758, i32 0		; visa id: 1713
  %1762 = extractelement <2 x i32> %1758, i32 1		; visa id: 1713
  %1763 = lshr i16 %154, 8		; visa id: 1713
  %1764 = and i32 %145, 255
  %1765 = and i32 %185, 768		; visa id: 1714
  %1766 = or i32 %1764, %1765		; visa id: 1715
  %1767 = shl nuw nsw i32 %1766, 3, !spirv.Decorations !8791		; visa id: 1716
  %1768 = zext i32 %1767 to i64		; visa id: 1717
  %1769 = add i64 %sink_, %1768		; visa id: 1718
  %1770 = inttoptr i64 %1769 to ptr addrspace(1)		; visa id: 1719
  %1771 = load <2 x i32>, ptr addrspace(1) %1770, align 4		; visa id: 1719
  %1772 = bitcast i32 %145 to <4 x i8>
  %1773 = extractelement <4 x i8> %1772, i32 2
  %1774 = lshr i32 %185, 2		; visa id: 1720
  %1775 = and i32 %1774, 768
  %1776 = zext i8 %1773 to i32		; visa id: 1721
  %1777 = or i32 %1776, %1775		; visa id: 1722
  %1778 = shl nuw nsw i32 %1777, 3, !spirv.Decorations !8791		; visa id: 1723
  %1779 = zext i32 %1778 to i64		; visa id: 1724
  %1780 = add i64 %sink_, %1779		; visa id: 1725
  %1781 = inttoptr i64 %1780 to ptr addrspace(1)		; visa id: 1726
  %1782 = load <2 x i32>, ptr addrspace(1) %1781, align 4		; visa id: 1726
  %1783 = extractelement <2 x i32> %1771, i32 0		; visa id: 1727
  %1784 = extractelement <2 x i32> %1771, i32 1		; visa id: 1727
  %1785 = extractelement <2 x i32> %1782, i32 0		; visa id: 1727
  %1786 = extractelement <2 x i32> %1782, i32 1		; visa id: 1727
  %1787 = or i32 %209, 64		; visa id: 1727
  %1788 = zext i32 %1787 to i64		; visa id: 1728
  %1789 = add i64 %1788, %const_reg_qword2		; visa id: 1729
  %IntToPtr2612 = inttoptr i64 %1789 to ptr addrspace(1)		; visa id: 1730
  %vCastload613 = load i32, ptr addrspace(1) %IntToPtr2612, align 2		; visa id: 1730
  %1790 = add i64 %1789, 4
  %IntToPtr2614 = inttoptr i64 %1790 to ptr addrspace(1)
  %vCastload615 = load i32, ptr addrspace(1) %IntToPtr2614, align 2		; visa id: 1731
  %1791 = add i64 %1789, 8
  %IntToPtr2616 = inttoptr i64 %1791 to ptr addrspace(1)
  %vCastload617 = load i32, ptr addrspace(1) %IntToPtr2616, align 2		; visa id: 1732
  %1792 = add i64 %1789, 12
  %IntToPtr2618 = inttoptr i64 %1792 to ptr addrspace(1)
  %vCastload619 = load i32, ptr addrspace(1) %IntToPtr2618, align 2		; visa id: 1733
  %1793 = bitcast i32 %vCastload613 to <2 x i16>		; visa id: 1734
  %1794 = bitcast i32 %vCastload615 to <2 x i16>		; visa id: 1736
  %1795 = extractelement <2 x i16> %1793, i32 0		; visa id: 1738
  %1796 = extractelement <2 x i16> %1793, i32 1		; visa id: 1738
  %1797 = extractelement <2 x i16> %1794, i32 0		; visa id: 1738
  %1798 = extractelement <2 x i16> %1794, i32 1		; visa id: 1738
  %1799 = bitcast i32 %vCastload617 to <2 x i16>		; visa id: 1738
  %1800 = bitcast i32 %vCastload619 to <2 x i16>		; visa id: 1740
  %1801 = extractelement <2 x i16> %1799, i32 0		; visa id: 1742
  %1802 = extractelement <2 x i16> %1799, i32 1		; visa id: 1742
  %1803 = extractelement <2 x i16> %1800, i32 0		; visa id: 1742
  %1804 = extractelement <2 x i16> %1800, i32 1		; visa id: 1742
  %1805 = zext i16 %1739 to i32		; visa id: 1742
  %1806 = and i32 %1805, 15		; visa id: 1743
  %1807 = uitofp i32 %1806 to float		; visa id: 1744
  %1808 = fadd float %1807, 5.000000e-01		; visa id: 1745
  %1809 = fmul float %139, %1808		; visa id: 1746
  %1810 = fmul float %1809, 2.500000e-01		; visa id: 1747
  %1811 = bitcast float %1810 to i32
  %1812 = and i32 %1811, 2147483647		; visa id: 1748
  %1813 = icmp ugt i32 %1812, 2139095040
  %1814 = fcmp oeq float %238, 0x7FF0000000000000		; visa id: 1749
  %1815 = fcmp une float %238, %238
  %1816 = or i1 %1815, %1814		; visa id: 1750
  %1817 = or i1 %1816, %1813		; visa id: 1752
  %1818 = and i32 %1759, 255		; visa id: 1754
  br i1 %1817, label %1826, label %1819, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1755

1819:                                             ; preds = %._crit_edge43.2
; BB202 :
  %1820 = and i32 %124, 256
  %1821 = sub nsw i32 0, %1818, !spirv.Decorations !8798
  %1822 = icmp eq i32 %1820, 0		; visa id: 1757
  %1823 = select i1 %1822, i32 %1818, i32 %1821		; visa id: 1759
  %1824 = sitofp i32 %1823 to float		; visa id: 1760
  %1825 = fmul float %1810, %1824		; visa id: 1761
  br label %1834, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1762

1826:                                             ; preds = %._crit_edge43.2
; BB203 :
  %1827 = uitofp i32 %1818 to float		; visa id: 1764
  %1828 = fmul float %1810, %1827		; visa id: 1765
  %1829 = and i32 %124, 256
  %1830 = icmp eq i32 %1829, 0		; visa id: 1766
  %1831 = select i1 %1830, i32 1, i32 -1		; visa id: 1768
  %1832 = sitofp i32 %1831 to float		; visa id: 1769
  %1833 = fmul float %1828, %1832		; visa id: 1770
  br label %1834, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1771

1834:                                             ; preds = %1826, %1819
; BB204 :
  %.sroa.062.8 = phi float [ %1833, %1826 ], [ %1825, %1819 ]
  %1835 = bitcast i32 %1759 to <4 x i8>
  %1836 = extractelement <4 x i8> %1835, i32 1
  %1837 = zext i8 %1836 to i32		; visa id: 1772
  br i1 %1817, label %1845, label %1838, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1773

1838:                                             ; preds = %1834
; BB205 :
  %1839 = and i32 %124, 512
  %1840 = sub nsw i32 0, %1837, !spirv.Decorations !8798
  %1841 = icmp eq i32 %1839, 0		; visa id: 1775
  %1842 = select i1 %1841, i32 %1837, i32 %1840		; visa id: 1777
  %1843 = sitofp i32 %1842 to float		; visa id: 1778
  %1844 = fmul float %1810, %1843		; visa id: 1779
  br label %1853, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1780

1845:                                             ; preds = %1834
; BB206 :
  %1846 = uitofp i32 %1837 to float		; visa id: 1782
  %1847 = fmul float %1810, %1846		; visa id: 1783
  %1848 = and i32 %124, 512
  %1849 = icmp eq i32 %1848, 0		; visa id: 1784
  %1850 = select i1 %1849, i32 1, i32 -1		; visa id: 1786
  %1851 = sitofp i32 %1850 to float		; visa id: 1787
  %1852 = fmul float %1847, %1851		; visa id: 1788
  br label %1853, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1789

1853:                                             ; preds = %1845, %1838
; BB207 :
  %.sroa.80.8 = phi float [ %1852, %1845 ], [ %1844, %1838 ]
  %1854 = extractelement <4 x i8> %1835, i32 2
  %1855 = zext i8 %1854 to i32		; visa id: 1790
  br i1 %1817, label %1863, label %1856, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1791

1856:                                             ; preds = %1853
; BB208 :
  %1857 = and i32 %124, 1024
  %1858 = sub nsw i32 0, %1855, !spirv.Decorations !8798
  %1859 = icmp eq i32 %1857, 0		; visa id: 1793
  %1860 = select i1 %1859, i32 %1855, i32 %1858		; visa id: 1795
  %1861 = sitofp i32 %1860 to float		; visa id: 1796
  %1862 = fmul float %1810, %1861		; visa id: 1797
  br label %1871, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1798

1863:                                             ; preds = %1853
; BB209 :
  %1864 = uitofp i32 %1855 to float		; visa id: 1800
  %1865 = fmul float %1810, %1864		; visa id: 1801
  %1866 = and i32 %124, 1024
  %1867 = icmp eq i32 %1866, 0		; visa id: 1802
  %1868 = select i1 %1867, i32 1, i32 -1		; visa id: 1804
  %1869 = sitofp i32 %1868 to float		; visa id: 1805
  %1870 = fmul float %1865, %1869		; visa id: 1806
  br label %1871, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1807

1871:                                             ; preds = %1863, %1856
; BB210 :
  %.sroa.128.8 = phi float [ %1870, %1863 ], [ %1862, %1856 ]
  %1872 = lshr i32 %1759, 24		; visa id: 1808
  br i1 %1817, label %1880, label %1873, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1809

1873:                                             ; preds = %1871
; BB211 :
  %1874 = and i32 %124, 2048
  %1875 = sub nsw i32 0, %1872, !spirv.Decorations !8798
  %1876 = icmp eq i32 %1874, 0		; visa id: 1811
  %1877 = select i1 %1876, i32 %1872, i32 %1875		; visa id: 1813
  %1878 = sitofp i32 %1877 to float		; visa id: 1814
  %1879 = fmul float %1810, %1878		; visa id: 1815
  br label %1888, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1816

1880:                                             ; preds = %1871
; BB212 :
  %1881 = uitofp i32 %1872 to float		; visa id: 1818
  %1882 = fmul float %1810, %1881		; visa id: 1819
  %1883 = and i32 %124, 2048
  %1884 = icmp eq i32 %1883, 0		; visa id: 1820
  %1885 = select i1 %1884, i32 1, i32 -1		; visa id: 1822
  %1886 = sitofp i32 %1885 to float		; visa id: 1823
  %1887 = fmul float %1882, %1886		; visa id: 1824
  br label %1888, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1825

1888:                                             ; preds = %1880, %1873
; BB213 :
  %.sroa.176.8 = phi float [ %1887, %1880 ], [ %1879, %1873 ]
  %1889 = and i32 %1760, 255		; visa id: 1826
  br i1 %1817, label %1897, label %1890, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1827

1890:                                             ; preds = %1888
; BB214 :
  %1891 = and i32 %124, 4096
  %1892 = sub nsw i32 0, %1889, !spirv.Decorations !8798
  %1893 = icmp eq i32 %1891, 0		; visa id: 1829
  %1894 = select i1 %1893, i32 %1889, i32 %1892		; visa id: 1831
  %1895 = sitofp i32 %1894 to float		; visa id: 1832
  %1896 = fmul float %1810, %1895		; visa id: 1833
  br label %1905, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1834

1897:                                             ; preds = %1888
; BB215 :
  %1898 = uitofp i32 %1889 to float		; visa id: 1836
  %1899 = fmul float %1810, %1898		; visa id: 1837
  %1900 = and i32 %124, 4096
  %1901 = icmp eq i32 %1900, 0		; visa id: 1838
  %1902 = select i1 %1901, i32 1, i32 -1		; visa id: 1840
  %1903 = sitofp i32 %1902 to float		; visa id: 1841
  %1904 = fmul float %1899, %1903		; visa id: 1842
  br label %1905, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1843

1905:                                             ; preds = %1897, %1890
; BB216 :
  %.sroa.224.8 = phi float [ %1904, %1897 ], [ %1896, %1890 ]
  %1906 = bitcast i32 %1760 to <4 x i8>
  %1907 = extractelement <4 x i8> %1906, i32 1
  %1908 = zext i8 %1907 to i32		; visa id: 1844
  br i1 %1817, label %1916, label %1909, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1845

1909:                                             ; preds = %1905
; BB217 :
  %1910 = and i32 %124, 8192
  %1911 = sub nsw i32 0, %1908, !spirv.Decorations !8798
  %1912 = icmp eq i32 %1910, 0		; visa id: 1847
  %1913 = select i1 %1912, i32 %1908, i32 %1911		; visa id: 1849
  %1914 = sitofp i32 %1913 to float		; visa id: 1850
  %1915 = fmul float %1810, %1914		; visa id: 1851
  br label %1924, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1852

1916:                                             ; preds = %1905
; BB218 :
  %1917 = uitofp i32 %1908 to float		; visa id: 1854
  %1918 = fmul float %1810, %1917		; visa id: 1855
  %1919 = and i32 %124, 8192
  %1920 = icmp eq i32 %1919, 0		; visa id: 1856
  %1921 = select i1 %1920, i32 1, i32 -1		; visa id: 1858
  %1922 = sitofp i32 %1921 to float		; visa id: 1859
  %1923 = fmul float %1918, %1922		; visa id: 1860
  br label %1924, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1861

1924:                                             ; preds = %1916, %1909
; BB219 :
  %.sroa.272.8 = phi float [ %1923, %1916 ], [ %1915, %1909 ]
  %1925 = extractelement <4 x i8> %1906, i32 2
  %1926 = zext i8 %1925 to i32		; visa id: 1862
  br i1 %1817, label %1934, label %1927, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1863

1927:                                             ; preds = %1924
; BB220 :
  %1928 = and i32 %124, 16384
  %1929 = sub nsw i32 0, %1926, !spirv.Decorations !8798
  %1930 = icmp eq i32 %1928, 0		; visa id: 1865
  %1931 = select i1 %1930, i32 %1926, i32 %1929		; visa id: 1867
  %1932 = sitofp i32 %1931 to float		; visa id: 1868
  %1933 = fmul float %1810, %1932		; visa id: 1869
  br label %1942, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1870

1934:                                             ; preds = %1924
; BB221 :
  %1935 = uitofp i32 %1926 to float		; visa id: 1872
  %1936 = fmul float %1810, %1935		; visa id: 1873
  %1937 = and i32 %124, 16384
  %1938 = icmp eq i32 %1937, 0		; visa id: 1874
  %1939 = select i1 %1938, i32 1, i32 -1		; visa id: 1876
  %1940 = sitofp i32 %1939 to float		; visa id: 1877
  %1941 = fmul float %1936, %1940		; visa id: 1878
  br label %1942, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1879

1942:                                             ; preds = %1934, %1927
; BB222 :
  %.sroa.320.8 = phi float [ %1941, %1934 ], [ %1933, %1927 ]
  %1943 = lshr i32 %1760, 24		; visa id: 1880
  br i1 %1817, label %1951, label %1944, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1881

1944:                                             ; preds = %1942
; BB223 :
  %1945 = and i32 %124, 32768
  %1946 = sub nsw i32 0, %1943, !spirv.Decorations !8798
  %1947 = icmp eq i32 %1945, 0		; visa id: 1883
  %1948 = select i1 %1947, i32 %1943, i32 %1946		; visa id: 1885
  %1949 = sitofp i32 %1948 to float		; visa id: 1886
  %1950 = fmul float %1810, %1949		; visa id: 1887
  br label %1959, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1888

1951:                                             ; preds = %1942
; BB224 :
  %1952 = uitofp i32 %1943 to float		; visa id: 1890
  %1953 = fmul float %1810, %1952		; visa id: 1891
  %1954 = and i32 %124, 32768
  %1955 = icmp eq i32 %1954, 0		; visa id: 1892
  %1956 = select i1 %1955, i32 1, i32 -1		; visa id: 1894
  %1957 = sitofp i32 %1956 to float		; visa id: 1895
  %1958 = fmul float %1953, %1957		; visa id: 1896
  br label %1959, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1897

1959:                                             ; preds = %1951, %1944
; BB225 :
  %.sroa.368.8 = phi float [ %1958, %1951 ], [ %1950, %1944 ]
  %1960 = zext i16 %1795 to i32		; visa id: 1898
  %1961 = shl nuw i32 %1960, 16		; visa id: 1899
  %1962 = bitcast i32 %1961 to float
  %1963 = fmul float %.sroa.062.8, %1962		; visa id: 1900
  %1964 = fadd float %.sroa.12.0, %1963		; visa id: 1901
  %1965 = zext i16 %1796 to i32		; visa id: 1902
  %1966 = shl nuw i32 %1965, 16		; visa id: 1903
  %1967 = bitcast i32 %1966 to float
  %1968 = fmul float %.sroa.80.8, %1967		; visa id: 1904
  %1969 = fadd float %1964, %1968		; visa id: 1905
  %1970 = zext i16 %1797 to i32		; visa id: 1906
  %1971 = shl nuw i32 %1970, 16		; visa id: 1907
  %1972 = bitcast i32 %1971 to float
  %1973 = fmul float %.sroa.128.8, %1972		; visa id: 1908
  %1974 = fadd float %1969, %1973		; visa id: 1909
  %1975 = zext i16 %1798 to i32		; visa id: 1910
  %1976 = shl nuw i32 %1975, 16		; visa id: 1911
  %1977 = bitcast i32 %1976 to float
  %1978 = fmul float %.sroa.176.8, %1977		; visa id: 1912
  %1979 = fadd float %1974, %1978		; visa id: 1913
  %1980 = zext i16 %1801 to i32		; visa id: 1914
  %1981 = shl nuw i32 %1980, 16		; visa id: 1915
  %1982 = bitcast i32 %1981 to float
  %1983 = fmul float %.sroa.224.8, %1982		; visa id: 1916
  %1984 = fadd float %1979, %1983		; visa id: 1917
  %1985 = zext i16 %1802 to i32		; visa id: 1918
  %1986 = shl nuw i32 %1985, 16		; visa id: 1919
  %1987 = bitcast i32 %1986 to float
  %1988 = fmul float %.sroa.272.8, %1987		; visa id: 1920
  %1989 = fadd float %1984, %1988		; visa id: 1921
  %1990 = zext i16 %1803 to i32		; visa id: 1922
  %1991 = shl nuw i32 %1990, 16		; visa id: 1923
  %1992 = bitcast i32 %1991 to float
  %1993 = fmul float %.sroa.320.8, %1992		; visa id: 1924
  %1994 = fadd float %1989, %1993		; visa id: 1925
  %1995 = zext i16 %1804 to i32		; visa id: 1926
  %1996 = shl nuw i32 %1995, 16		; visa id: 1927
  %1997 = bitcast i32 %1996 to float
  %1998 = fmul float %.sroa.368.8, %1997		; visa id: 1928
  %1999 = fadd float %1994, %1998		; visa id: 1929
  %2000 = zext i16 %1763 to i32		; visa id: 1930
  %2001 = and i32 %2000, 15		; visa id: 1931
  %2002 = uitofp i32 %2001 to float		; visa id: 1932
  %2003 = fadd float %2002, 5.000000e-01		; visa id: 1933
  %2004 = fmul float %158, %2003		; visa id: 1934
  %2005 = fmul float %2004, 2.500000e-01		; visa id: 1935
  %2006 = bitcast float %2005 to i32
  %2007 = and i32 %2006, 2147483647		; visa id: 1936
  %2008 = icmp ugt i32 %2007, 2139095040		; visa id: 1937
  %2009 = or i1 %440, %2008		; visa id: 1938
  %2010 = and i32 %1783, 255		; visa id: 1939
  br i1 %2009, label %2018, label %2011, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1940

2011:                                             ; preds = %1959
; BB226 :
  %2012 = and i32 %145, 256
  %2013 = sub nsw i32 0, %2010, !spirv.Decorations !8798
  %2014 = icmp eq i32 %2012, 0		; visa id: 1942
  %2015 = select i1 %2014, i32 %2010, i32 %2013		; visa id: 1944
  %2016 = sitofp i32 %2015 to float		; visa id: 1945
  %2017 = fmul float %2005, %2016		; visa id: 1946
  br label %2026, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1947

2018:                                             ; preds = %1959
; BB227 :
  %2019 = uitofp i32 %2010 to float		; visa id: 1949
  %2020 = fmul float %2005, %2019		; visa id: 1950
  %2021 = and i32 %145, 256
  %2022 = icmp eq i32 %2021, 0		; visa id: 1951
  %2023 = select i1 %2022, i32 1, i32 -1		; visa id: 1953
  %2024 = sitofp i32 %2023 to float		; visa id: 1954
  %2025 = fmul float %2020, %2024		; visa id: 1955
  br label %2026, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1956

2026:                                             ; preds = %2018, %2011
; BB228 :
  %.sroa.062.9 = phi float [ %2025, %2018 ], [ %2017, %2011 ]
  %2027 = bitcast i32 %1783 to <4 x i8>
  %2028 = extractelement <4 x i8> %2027, i32 1
  %2029 = zext i8 %2028 to i32		; visa id: 1957
  br i1 %2009, label %2037, label %2030, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1958

2030:                                             ; preds = %2026
; BB229 :
  %2031 = and i32 %145, 512
  %2032 = sub nsw i32 0, %2029, !spirv.Decorations !8798
  %2033 = icmp eq i32 %2031, 0		; visa id: 1960
  %2034 = select i1 %2033, i32 %2029, i32 %2032		; visa id: 1962
  %2035 = sitofp i32 %2034 to float		; visa id: 1963
  %2036 = fmul float %2005, %2035		; visa id: 1964
  br label %2045, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1965

2037:                                             ; preds = %2026
; BB230 :
  %2038 = uitofp i32 %2029 to float		; visa id: 1967
  %2039 = fmul float %2005, %2038		; visa id: 1968
  %2040 = and i32 %145, 512
  %2041 = icmp eq i32 %2040, 0		; visa id: 1969
  %2042 = select i1 %2041, i32 1, i32 -1		; visa id: 1971
  %2043 = sitofp i32 %2042 to float		; visa id: 1972
  %2044 = fmul float %2039, %2043		; visa id: 1973
  br label %2045, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1974

2045:                                             ; preds = %2037, %2030
; BB231 :
  %.sroa.80.9 = phi float [ %2044, %2037 ], [ %2036, %2030 ]
  %2046 = extractelement <4 x i8> %2027, i32 2
  %2047 = zext i8 %2046 to i32		; visa id: 1975
  br i1 %2009, label %2055, label %2048, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1976

2048:                                             ; preds = %2045
; BB232 :
  %2049 = and i32 %145, 1024
  %2050 = sub nsw i32 0, %2047, !spirv.Decorations !8798
  %2051 = icmp eq i32 %2049, 0		; visa id: 1978
  %2052 = select i1 %2051, i32 %2047, i32 %2050		; visa id: 1980
  %2053 = sitofp i32 %2052 to float		; visa id: 1981
  %2054 = fmul float %2005, %2053		; visa id: 1982
  br label %2063, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1983

2055:                                             ; preds = %2045
; BB233 :
  %2056 = uitofp i32 %2047 to float		; visa id: 1985
  %2057 = fmul float %2005, %2056		; visa id: 1986
  %2058 = and i32 %145, 1024
  %2059 = icmp eq i32 %2058, 0		; visa id: 1987
  %2060 = select i1 %2059, i32 1, i32 -1		; visa id: 1989
  %2061 = sitofp i32 %2060 to float		; visa id: 1990
  %2062 = fmul float %2057, %2061		; visa id: 1991
  br label %2063, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1992

2063:                                             ; preds = %2055, %2048
; BB234 :
  %.sroa.128.9 = phi float [ %2062, %2055 ], [ %2054, %2048 ]
  %2064 = lshr i32 %1783, 24		; visa id: 1993
  br i1 %2009, label %2072, label %2065, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1994

2065:                                             ; preds = %2063
; BB235 :
  %2066 = and i32 %145, 2048
  %2067 = sub nsw i32 0, %2064, !spirv.Decorations !8798
  %2068 = icmp eq i32 %2066, 0		; visa id: 1996
  %2069 = select i1 %2068, i32 %2064, i32 %2067		; visa id: 1998
  %2070 = sitofp i32 %2069 to float		; visa id: 1999
  %2071 = fmul float %2005, %2070		; visa id: 2000
  br label %2080, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2001

2072:                                             ; preds = %2063
; BB236 :
  %2073 = uitofp i32 %2064 to float		; visa id: 2003
  %2074 = fmul float %2005, %2073		; visa id: 2004
  %2075 = and i32 %145, 2048
  %2076 = icmp eq i32 %2075, 0		; visa id: 2005
  %2077 = select i1 %2076, i32 1, i32 -1		; visa id: 2007
  %2078 = sitofp i32 %2077 to float		; visa id: 2008
  %2079 = fmul float %2074, %2078		; visa id: 2009
  br label %2080, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2010

2080:                                             ; preds = %2072, %2065
; BB237 :
  %.sroa.176.9 = phi float [ %2079, %2072 ], [ %2071, %2065 ]
  %2081 = and i32 %1784, 255		; visa id: 2011
  br i1 %2009, label %2089, label %2082, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2012

2082:                                             ; preds = %2080
; BB238 :
  %2083 = and i32 %145, 4096
  %2084 = sub nsw i32 0, %2081, !spirv.Decorations !8798
  %2085 = icmp eq i32 %2083, 0		; visa id: 2014
  %2086 = select i1 %2085, i32 %2081, i32 %2084		; visa id: 2016
  %2087 = sitofp i32 %2086 to float		; visa id: 2017
  %2088 = fmul float %2005, %2087		; visa id: 2018
  br label %2097, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2019

2089:                                             ; preds = %2080
; BB239 :
  %2090 = uitofp i32 %2081 to float		; visa id: 2021
  %2091 = fmul float %2005, %2090		; visa id: 2022
  %2092 = and i32 %145, 4096
  %2093 = icmp eq i32 %2092, 0		; visa id: 2023
  %2094 = select i1 %2093, i32 1, i32 -1		; visa id: 2025
  %2095 = sitofp i32 %2094 to float		; visa id: 2026
  %2096 = fmul float %2091, %2095		; visa id: 2027
  br label %2097, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2028

2097:                                             ; preds = %2089, %2082
; BB240 :
  %.sroa.224.9 = phi float [ %2096, %2089 ], [ %2088, %2082 ]
  %2098 = bitcast i32 %1784 to <4 x i8>
  %2099 = extractelement <4 x i8> %2098, i32 1
  %2100 = zext i8 %2099 to i32		; visa id: 2029
  br i1 %2009, label %2108, label %2101, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2030

2101:                                             ; preds = %2097
; BB241 :
  %2102 = and i32 %145, 8192
  %2103 = sub nsw i32 0, %2100, !spirv.Decorations !8798
  %2104 = icmp eq i32 %2102, 0		; visa id: 2032
  %2105 = select i1 %2104, i32 %2100, i32 %2103		; visa id: 2034
  %2106 = sitofp i32 %2105 to float		; visa id: 2035
  %2107 = fmul float %2005, %2106		; visa id: 2036
  br label %2116, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2037

2108:                                             ; preds = %2097
; BB242 :
  %2109 = uitofp i32 %2100 to float		; visa id: 2039
  %2110 = fmul float %2005, %2109		; visa id: 2040
  %2111 = and i32 %145, 8192
  %2112 = icmp eq i32 %2111, 0		; visa id: 2041
  %2113 = select i1 %2112, i32 1, i32 -1		; visa id: 2043
  %2114 = sitofp i32 %2113 to float		; visa id: 2044
  %2115 = fmul float %2110, %2114		; visa id: 2045
  br label %2116, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2046

2116:                                             ; preds = %2108, %2101
; BB243 :
  %.sroa.272.9 = phi float [ %2115, %2108 ], [ %2107, %2101 ]
  %2117 = extractelement <4 x i8> %2098, i32 2
  %2118 = zext i8 %2117 to i32		; visa id: 2047
  br i1 %2009, label %2126, label %2119, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2048

2119:                                             ; preds = %2116
; BB244 :
  %2120 = and i32 %145, 16384
  %2121 = sub nsw i32 0, %2118, !spirv.Decorations !8798
  %2122 = icmp eq i32 %2120, 0		; visa id: 2050
  %2123 = select i1 %2122, i32 %2118, i32 %2121		; visa id: 2052
  %2124 = sitofp i32 %2123 to float		; visa id: 2053
  %2125 = fmul float %2005, %2124		; visa id: 2054
  br label %2134, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2055

2126:                                             ; preds = %2116
; BB245 :
  %2127 = uitofp i32 %2118 to float		; visa id: 2057
  %2128 = fmul float %2005, %2127		; visa id: 2058
  %2129 = and i32 %145, 16384
  %2130 = icmp eq i32 %2129, 0		; visa id: 2059
  %2131 = select i1 %2130, i32 1, i32 -1		; visa id: 2061
  %2132 = sitofp i32 %2131 to float		; visa id: 2062
  %2133 = fmul float %2128, %2132		; visa id: 2063
  br label %2134, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2064

2134:                                             ; preds = %2126, %2119
; BB246 :
  %.sroa.320.9 = phi float [ %2133, %2126 ], [ %2125, %2119 ]
  %2135 = lshr i32 %1784, 24		; visa id: 2065
  br i1 %2009, label %2143, label %2136, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2066

2136:                                             ; preds = %2134
; BB247 :
  %2137 = and i32 %145, 32768
  %2138 = sub nsw i32 0, %2135, !spirv.Decorations !8798
  %2139 = icmp eq i32 %2137, 0		; visa id: 2068
  %2140 = select i1 %2139, i32 %2135, i32 %2138		; visa id: 2070
  %2141 = sitofp i32 %2140 to float		; visa id: 2071
  %2142 = fmul float %2005, %2141		; visa id: 2072
  br label %2151, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2073

2143:                                             ; preds = %2134
; BB248 :
  %2144 = uitofp i32 %2135 to float		; visa id: 2075
  %2145 = fmul float %2005, %2144		; visa id: 2076
  %2146 = and i32 %145, 32768
  %2147 = icmp eq i32 %2146, 0		; visa id: 2077
  %2148 = select i1 %2147, i32 1, i32 -1		; visa id: 2079
  %2149 = sitofp i32 %2148 to float		; visa id: 2080
  %2150 = fmul float %2145, %2149		; visa id: 2081
  br label %2151, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2082

2151:                                             ; preds = %2143, %2136
; BB249 :
  %.sroa.368.9 = phi float [ %2150, %2143 ], [ %2142, %2136 ]
  %2152 = fmul float %.sroa.062.9, %1962		; visa id: 2083
  %2153 = fadd float %.sroa.29.0, %2152		; visa id: 2084
  %2154 = fmul float %.sroa.80.9, %1967		; visa id: 2085
  %2155 = fadd float %2153, %2154		; visa id: 2086
  %2156 = fmul float %.sroa.128.9, %1972		; visa id: 2087
  %2157 = fadd float %2155, %2156		; visa id: 2088
  %2158 = fmul float %.sroa.176.9, %1977		; visa id: 2089
  %2159 = fadd float %2157, %2158		; visa id: 2090
  %2160 = fmul float %.sroa.224.9, %1982		; visa id: 2091
  %2161 = fadd float %2159, %2160		; visa id: 2092
  %2162 = fmul float %.sroa.272.9, %1987		; visa id: 2093
  %2163 = fadd float %2161, %2162		; visa id: 2094
  %2164 = fmul float %.sroa.320.9, %1992		; visa id: 2095
  %2165 = fadd float %2163, %2164		; visa id: 2096
  %2166 = fmul float %.sroa.368.9, %1997		; visa id: 2097
  %2167 = fadd float %2165, %2166		; visa id: 2098
  %2168 = or i32 %209, 80		; visa id: 2099
  %2169 = zext i32 %2168 to i64		; visa id: 2100
  %2170 = add i64 %2169, %const_reg_qword2		; visa id: 2101
  %IntToPtr2620 = inttoptr i64 %2170 to ptr addrspace(1)		; visa id: 2102
  %vCastload621 = load i32, ptr addrspace(1) %IntToPtr2620, align 2		; visa id: 2102
  %2171 = add i64 %2170, 4
  %IntToPtr2622 = inttoptr i64 %2171 to ptr addrspace(1)
  %vCastload623 = load i32, ptr addrspace(1) %IntToPtr2622, align 2		; visa id: 2103
  %2172 = add i64 %2170, 8
  %IntToPtr2624 = inttoptr i64 %2172 to ptr addrspace(1)
  %vCastload625 = load i32, ptr addrspace(1) %IntToPtr2624, align 2		; visa id: 2104
  %2173 = add i64 %2170, 12
  %IntToPtr2626 = inttoptr i64 %2173 to ptr addrspace(1)
  %vCastload627 = load i32, ptr addrspace(1) %IntToPtr2626, align 2		; visa id: 2105
  %2174 = bitcast i32 %vCastload621 to <2 x i16>		; visa id: 2106
  %2175 = bitcast i32 %vCastload623 to <2 x i16>		; visa id: 2108
  %2176 = extractelement <2 x i16> %2174, i32 0		; visa id: 2110
  %2177 = extractelement <2 x i16> %2174, i32 1		; visa id: 2110
  %2178 = extractelement <2 x i16> %2175, i32 0		; visa id: 2110
  %2179 = extractelement <2 x i16> %2175, i32 1		; visa id: 2110
  %2180 = bitcast i32 %vCastload625 to <2 x i16>		; visa id: 2110
  %2181 = bitcast i32 %vCastload627 to <2 x i16>		; visa id: 2112
  %2182 = extractelement <2 x i16> %2180, i32 0		; visa id: 2114
  %2183 = extractelement <2 x i16> %2180, i32 1		; visa id: 2114
  %2184 = extractelement <2 x i16> %2181, i32 0		; visa id: 2114
  %2185 = extractelement <2 x i16> %2181, i32 1		; visa id: 2114
  %2186 = and i32 %1761, 255		; visa id: 2114
  br i1 %1817, label %2194, label %2187, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2115

2187:                                             ; preds = %2151
; BB250 :
  %2188 = and i32 %124, 16777216
  %2189 = sub nsw i32 0, %2186, !spirv.Decorations !8798
  %2190 = icmp eq i32 %2188, 0		; visa id: 2117
  %2191 = select i1 %2190, i32 %2186, i32 %2189		; visa id: 2119
  %2192 = sitofp i32 %2191 to float		; visa id: 2120
  %2193 = fmul float %1810, %2192		; visa id: 2121
  br label %2202, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2122

2194:                                             ; preds = %2151
; BB251 :
  %2195 = uitofp i32 %2186 to float		; visa id: 2124
  %2196 = fmul float %1810, %2195		; visa id: 2125
  %2197 = and i32 %124, 16777216
  %2198 = icmp eq i32 %2197, 0		; visa id: 2126
  %2199 = select i1 %2198, i32 1, i32 -1		; visa id: 2128
  %2200 = sitofp i32 %2199 to float		; visa id: 2129
  %2201 = fmul float %2196, %2200		; visa id: 2130
  br label %2202, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2131

2202:                                             ; preds = %2194, %2187
; BB252 :
  %.sroa.062.10 = phi float [ %2201, %2194 ], [ %2193, %2187 ]
  %2203 = bitcast i32 %1761 to <4 x i8>
  %2204 = extractelement <4 x i8> %2203, i32 1
  %2205 = zext i8 %2204 to i32		; visa id: 2132
  br i1 %1817, label %2213, label %2206, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2133

2206:                                             ; preds = %2202
; BB253 :
  %2207 = and i32 %124, 33554432
  %2208 = sub nsw i32 0, %2205, !spirv.Decorations !8798
  %2209 = icmp eq i32 %2207, 0		; visa id: 2135
  %2210 = select i1 %2209, i32 %2205, i32 %2208		; visa id: 2137
  %2211 = sitofp i32 %2210 to float		; visa id: 2138
  %2212 = fmul float %1810, %2211		; visa id: 2139
  br label %2221, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2140

2213:                                             ; preds = %2202
; BB254 :
  %2214 = uitofp i32 %2205 to float		; visa id: 2142
  %2215 = fmul float %1810, %2214		; visa id: 2143
  %2216 = and i32 %124, 33554432
  %2217 = icmp eq i32 %2216, 0		; visa id: 2144
  %2218 = select i1 %2217, i32 1, i32 -1		; visa id: 2146
  %2219 = sitofp i32 %2218 to float		; visa id: 2147
  %2220 = fmul float %2215, %2219		; visa id: 2148
  br label %2221, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2149

2221:                                             ; preds = %2213, %2206
; BB255 :
  %.sroa.80.10 = phi float [ %2220, %2213 ], [ %2212, %2206 ]
  %2222 = extractelement <4 x i8> %2203, i32 2
  %2223 = zext i8 %2222 to i32		; visa id: 2150
  br i1 %1817, label %2231, label %2224, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2151

2224:                                             ; preds = %2221
; BB256 :
  %2225 = and i32 %124, 67108864
  %2226 = sub nsw i32 0, %2223, !spirv.Decorations !8798
  %2227 = icmp eq i32 %2225, 0		; visa id: 2153
  %2228 = select i1 %2227, i32 %2223, i32 %2226		; visa id: 2155
  %2229 = sitofp i32 %2228 to float		; visa id: 2156
  %2230 = fmul float %1810, %2229		; visa id: 2157
  br label %2239, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2158

2231:                                             ; preds = %2221
; BB257 :
  %2232 = uitofp i32 %2223 to float		; visa id: 2160
  %2233 = fmul float %1810, %2232		; visa id: 2161
  %2234 = and i32 %124, 67108864
  %2235 = icmp eq i32 %2234, 0		; visa id: 2162
  %2236 = select i1 %2235, i32 1, i32 -1		; visa id: 2164
  %2237 = sitofp i32 %2236 to float		; visa id: 2165
  %2238 = fmul float %2233, %2237		; visa id: 2166
  br label %2239, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2167

2239:                                             ; preds = %2231, %2224
; BB258 :
  %.sroa.128.10 = phi float [ %2238, %2231 ], [ %2230, %2224 ]
  %2240 = lshr i32 %1761, 24		; visa id: 2168
  br i1 %1817, label %2248, label %2241, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2169

2241:                                             ; preds = %2239
; BB259 :
  %2242 = and i32 %124, 134217728
  %2243 = sub nsw i32 0, %2240, !spirv.Decorations !8798
  %2244 = icmp eq i32 %2242, 0		; visa id: 2171
  %2245 = select i1 %2244, i32 %2240, i32 %2243		; visa id: 2173
  %2246 = sitofp i32 %2245 to float		; visa id: 2174
  %2247 = fmul float %1810, %2246		; visa id: 2175
  br label %2256, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2176

2248:                                             ; preds = %2239
; BB260 :
  %2249 = uitofp i32 %2240 to float		; visa id: 2178
  %2250 = fmul float %1810, %2249		; visa id: 2179
  %2251 = and i32 %124, 134217728
  %2252 = icmp eq i32 %2251, 0		; visa id: 2180
  %2253 = select i1 %2252, i32 1, i32 -1		; visa id: 2182
  %2254 = sitofp i32 %2253 to float		; visa id: 2183
  %2255 = fmul float %2250, %2254		; visa id: 2184
  br label %2256, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2185

2256:                                             ; preds = %2248, %2241
; BB261 :
  %.sroa.176.10 = phi float [ %2255, %2248 ], [ %2247, %2241 ]
  %2257 = and i32 %1762, 255		; visa id: 2186
  br i1 %1817, label %2265, label %2258, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2187

2258:                                             ; preds = %2256
; BB262 :
  %2259 = and i32 %124, 268435456
  %2260 = sub nsw i32 0, %2257, !spirv.Decorations !8798
  %2261 = icmp eq i32 %2259, 0		; visa id: 2189
  %2262 = select i1 %2261, i32 %2257, i32 %2260		; visa id: 2191
  %2263 = sitofp i32 %2262 to float		; visa id: 2192
  %2264 = fmul float %1810, %2263		; visa id: 2193
  br label %2273, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2194

2265:                                             ; preds = %2256
; BB263 :
  %2266 = uitofp i32 %2257 to float		; visa id: 2196
  %2267 = fmul float %1810, %2266		; visa id: 2197
  %2268 = and i32 %124, 268435456
  %2269 = icmp eq i32 %2268, 0		; visa id: 2198
  %2270 = select i1 %2269, i32 1, i32 -1		; visa id: 2200
  %2271 = sitofp i32 %2270 to float		; visa id: 2201
  %2272 = fmul float %2267, %2271		; visa id: 2202
  br label %2273, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2203

2273:                                             ; preds = %2265, %2258
; BB264 :
  %.sroa.224.10 = phi float [ %2272, %2265 ], [ %2264, %2258 ]
  %2274 = bitcast i32 %1762 to <4 x i8>
  %2275 = extractelement <4 x i8> %2274, i32 1
  %2276 = zext i8 %2275 to i32		; visa id: 2204
  br i1 %1817, label %2284, label %2277, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2205

2277:                                             ; preds = %2273
; BB265 :
  %2278 = and i32 %124, 536870912
  %2279 = sub nsw i32 0, %2276, !spirv.Decorations !8798
  %2280 = icmp eq i32 %2278, 0		; visa id: 2207
  %2281 = select i1 %2280, i32 %2276, i32 %2279		; visa id: 2209
  %2282 = sitofp i32 %2281 to float		; visa id: 2210
  %2283 = fmul float %1810, %2282		; visa id: 2211
  br label %2292, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2212

2284:                                             ; preds = %2273
; BB266 :
  %2285 = uitofp i32 %2276 to float		; visa id: 2214
  %2286 = fmul float %1810, %2285		; visa id: 2215
  %2287 = and i32 %124, 536870912
  %2288 = icmp eq i32 %2287, 0		; visa id: 2216
  %2289 = select i1 %2288, i32 1, i32 -1		; visa id: 2218
  %2290 = sitofp i32 %2289 to float		; visa id: 2219
  %2291 = fmul float %2286, %2290		; visa id: 2220
  br label %2292, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2221

2292:                                             ; preds = %2284, %2277
; BB267 :
  %.sroa.272.10 = phi float [ %2291, %2284 ], [ %2283, %2277 ]
  %2293 = extractelement <4 x i8> %2274, i32 2
  %2294 = zext i8 %2293 to i32		; visa id: 2222
  br i1 %1817, label %2302, label %2295, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2223

2295:                                             ; preds = %2292
; BB268 :
  %2296 = and i32 %124, 1073741824
  %2297 = sub nsw i32 0, %2294, !spirv.Decorations !8798
  %2298 = icmp eq i32 %2296, 0		; visa id: 2225
  %2299 = select i1 %2298, i32 %2294, i32 %2297		; visa id: 2227
  %2300 = sitofp i32 %2299 to float		; visa id: 2228
  %2301 = fmul float %1810, %2300		; visa id: 2229
  br label %2310, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2230

2302:                                             ; preds = %2292
; BB269 :
  %2303 = uitofp i32 %2294 to float		; visa id: 2232
  %2304 = fmul float %1810, %2303		; visa id: 2233
  %2305 = and i32 %124, 1073741824
  %2306 = icmp eq i32 %2305, 0		; visa id: 2234
  %2307 = select i1 %2306, i32 1, i32 -1		; visa id: 2236
  %2308 = sitofp i32 %2307 to float		; visa id: 2237
  %2309 = fmul float %2304, %2308		; visa id: 2238
  br label %2310, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2239

2310:                                             ; preds = %2302, %2295
; BB270 :
  %.sroa.320.10 = phi float [ %2309, %2302 ], [ %2301, %2295 ]
  %2311 = lshr i32 %1762, 24		; visa id: 2240
  br i1 %1817, label %2318, label %2312, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2241

2312:                                             ; preds = %2310
; BB271 :
  %2313 = sub nsw i32 0, %2311, !spirv.Decorations !8798
  %2314 = icmp slt i32 %124, 0		; visa id: 2243
  %2315 = select i1 %2314, i32 %2313, i32 %2311		; visa id: 2244
  %2316 = sitofp i32 %2315 to float		; visa id: 2245
  %2317 = fmul float %1810, %2316		; visa id: 2246
  br label %2325, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2247

2318:                                             ; preds = %2310
; BB272 :
  %2319 = uitofp i32 %2311 to float		; visa id: 2249
  %2320 = fmul float %1810, %2319		; visa id: 2250
  %2321 = icmp sgt i32 %124, -1		; visa id: 2251
  %2322 = select i1 %2321, i32 1, i32 -1		; visa id: 2252
  %2323 = sitofp i32 %2322 to float		; visa id: 2253
  %2324 = fmul float %2320, %2323		; visa id: 2254
  br label %2325, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2255

2325:                                             ; preds = %2318, %2312
; BB273 :
  %.sroa.368.10 = phi float [ %2324, %2318 ], [ %2317, %2312 ]
  %2326 = zext i16 %2176 to i32		; visa id: 2256
  %2327 = shl nuw i32 %2326, 16		; visa id: 2257
  %2328 = bitcast i32 %2327 to float
  %2329 = fmul float %.sroa.062.10, %2328		; visa id: 2258
  %2330 = fadd float %.sroa.14.0, %2329		; visa id: 2259
  %2331 = zext i16 %2177 to i32		; visa id: 2260
  %2332 = shl nuw i32 %2331, 16		; visa id: 2261
  %2333 = bitcast i32 %2332 to float
  %2334 = fmul float %.sroa.80.10, %2333		; visa id: 2262
  %2335 = fadd float %2330, %2334		; visa id: 2263
  %2336 = zext i16 %2178 to i32		; visa id: 2264
  %2337 = shl nuw i32 %2336, 16		; visa id: 2265
  %2338 = bitcast i32 %2337 to float
  %2339 = fmul float %.sroa.128.10, %2338		; visa id: 2266
  %2340 = fadd float %2335, %2339		; visa id: 2267
  %2341 = zext i16 %2179 to i32		; visa id: 2268
  %2342 = shl nuw i32 %2341, 16		; visa id: 2269
  %2343 = bitcast i32 %2342 to float
  %2344 = fmul float %.sroa.176.10, %2343		; visa id: 2270
  %2345 = fadd float %2340, %2344		; visa id: 2271
  %2346 = zext i16 %2182 to i32		; visa id: 2272
  %2347 = shl nuw i32 %2346, 16		; visa id: 2273
  %2348 = bitcast i32 %2347 to float
  %2349 = fmul float %.sroa.224.10, %2348		; visa id: 2274
  %2350 = fadd float %2345, %2349		; visa id: 2275
  %2351 = zext i16 %2183 to i32		; visa id: 2276
  %2352 = shl nuw i32 %2351, 16		; visa id: 2277
  %2353 = bitcast i32 %2352 to float
  %2354 = fmul float %.sroa.272.10, %2353		; visa id: 2278
  %2355 = fadd float %2350, %2354		; visa id: 2279
  %2356 = zext i16 %2184 to i32		; visa id: 2280
  %2357 = shl nuw i32 %2356, 16		; visa id: 2281
  %2358 = bitcast i32 %2357 to float
  %2359 = fmul float %.sroa.320.10, %2358		; visa id: 2282
  %2360 = fadd float %2355, %2359		; visa id: 2283
  %2361 = zext i16 %2185 to i32		; visa id: 2284
  %2362 = shl nuw i32 %2361, 16		; visa id: 2285
  %2363 = bitcast i32 %2362 to float
  %2364 = fmul float %.sroa.368.10, %2363		; visa id: 2286
  %2365 = fadd float %2360, %2364		; visa id: 2287
  %2366 = and i32 %1785, 255		; visa id: 2288
  br i1 %2009, label %2374, label %2367, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2289

2367:                                             ; preds = %2325
; BB274 :
  %2368 = and i32 %145, 16777216
  %2369 = sub nsw i32 0, %2366, !spirv.Decorations !8798
  %2370 = icmp eq i32 %2368, 0		; visa id: 2291
  %2371 = select i1 %2370, i32 %2366, i32 %2369		; visa id: 2293
  %2372 = sitofp i32 %2371 to float		; visa id: 2294
  %2373 = fmul float %2005, %2372		; visa id: 2295
  br label %2382, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2296

2374:                                             ; preds = %2325
; BB275 :
  %2375 = uitofp i32 %2366 to float		; visa id: 2298
  %2376 = fmul float %2005, %2375		; visa id: 2299
  %2377 = and i32 %145, 16777216
  %2378 = icmp eq i32 %2377, 0		; visa id: 2300
  %2379 = select i1 %2378, i32 1, i32 -1		; visa id: 2302
  %2380 = sitofp i32 %2379 to float		; visa id: 2303
  %2381 = fmul float %2376, %2380		; visa id: 2304
  br label %2382, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2305

2382:                                             ; preds = %2374, %2367
; BB276 :
  %.sroa.062.11 = phi float [ %2381, %2374 ], [ %2373, %2367 ]
  %2383 = bitcast i32 %1785 to <4 x i8>
  %2384 = extractelement <4 x i8> %2383, i32 1
  %2385 = zext i8 %2384 to i32		; visa id: 2306
  br i1 %2009, label %2393, label %2386, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2307

2386:                                             ; preds = %2382
; BB277 :
  %2387 = and i32 %145, 33554432
  %2388 = sub nsw i32 0, %2385, !spirv.Decorations !8798
  %2389 = icmp eq i32 %2387, 0		; visa id: 2309
  %2390 = select i1 %2389, i32 %2385, i32 %2388		; visa id: 2311
  %2391 = sitofp i32 %2390 to float		; visa id: 2312
  %2392 = fmul float %2005, %2391		; visa id: 2313
  br label %2401, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2314

2393:                                             ; preds = %2382
; BB278 :
  %2394 = uitofp i32 %2385 to float		; visa id: 2316
  %2395 = fmul float %2005, %2394		; visa id: 2317
  %2396 = and i32 %145, 33554432
  %2397 = icmp eq i32 %2396, 0		; visa id: 2318
  %2398 = select i1 %2397, i32 1, i32 -1		; visa id: 2320
  %2399 = sitofp i32 %2398 to float		; visa id: 2321
  %2400 = fmul float %2395, %2399		; visa id: 2322
  br label %2401, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2323

2401:                                             ; preds = %2393, %2386
; BB279 :
  %.sroa.80.11 = phi float [ %2400, %2393 ], [ %2392, %2386 ]
  %2402 = extractelement <4 x i8> %2383, i32 2
  %2403 = zext i8 %2402 to i32		; visa id: 2324
  br i1 %2009, label %2411, label %2404, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2325

2404:                                             ; preds = %2401
; BB280 :
  %2405 = and i32 %145, 67108864
  %2406 = sub nsw i32 0, %2403, !spirv.Decorations !8798
  %2407 = icmp eq i32 %2405, 0		; visa id: 2327
  %2408 = select i1 %2407, i32 %2403, i32 %2406		; visa id: 2329
  %2409 = sitofp i32 %2408 to float		; visa id: 2330
  %2410 = fmul float %2005, %2409		; visa id: 2331
  br label %2419, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2332

2411:                                             ; preds = %2401
; BB281 :
  %2412 = uitofp i32 %2403 to float		; visa id: 2334
  %2413 = fmul float %2005, %2412		; visa id: 2335
  %2414 = and i32 %145, 67108864
  %2415 = icmp eq i32 %2414, 0		; visa id: 2336
  %2416 = select i1 %2415, i32 1, i32 -1		; visa id: 2338
  %2417 = sitofp i32 %2416 to float		; visa id: 2339
  %2418 = fmul float %2413, %2417		; visa id: 2340
  br label %2419, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2341

2419:                                             ; preds = %2411, %2404
; BB282 :
  %.sroa.128.11 = phi float [ %2418, %2411 ], [ %2410, %2404 ]
  %2420 = lshr i32 %1785, 24		; visa id: 2342
  br i1 %2009, label %2428, label %2421, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2343

2421:                                             ; preds = %2419
; BB283 :
  %2422 = and i32 %145, 134217728
  %2423 = sub nsw i32 0, %2420, !spirv.Decorations !8798
  %2424 = icmp eq i32 %2422, 0		; visa id: 2345
  %2425 = select i1 %2424, i32 %2420, i32 %2423		; visa id: 2347
  %2426 = sitofp i32 %2425 to float		; visa id: 2348
  %2427 = fmul float %2005, %2426		; visa id: 2349
  br label %2436, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2350

2428:                                             ; preds = %2419
; BB284 :
  %2429 = uitofp i32 %2420 to float		; visa id: 2352
  %2430 = fmul float %2005, %2429		; visa id: 2353
  %2431 = and i32 %145, 134217728
  %2432 = icmp eq i32 %2431, 0		; visa id: 2354
  %2433 = select i1 %2432, i32 1, i32 -1		; visa id: 2356
  %2434 = sitofp i32 %2433 to float		; visa id: 2357
  %2435 = fmul float %2430, %2434		; visa id: 2358
  br label %2436, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2359

2436:                                             ; preds = %2428, %2421
; BB285 :
  %.sroa.176.11 = phi float [ %2435, %2428 ], [ %2427, %2421 ]
  %2437 = and i32 %1786, 255		; visa id: 2360
  br i1 %2009, label %2445, label %2438, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2361

2438:                                             ; preds = %2436
; BB286 :
  %2439 = and i32 %145, 268435456
  %2440 = sub nsw i32 0, %2437, !spirv.Decorations !8798
  %2441 = icmp eq i32 %2439, 0		; visa id: 2363
  %2442 = select i1 %2441, i32 %2437, i32 %2440		; visa id: 2365
  %2443 = sitofp i32 %2442 to float		; visa id: 2366
  %2444 = fmul float %2005, %2443		; visa id: 2367
  br label %2453, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2368

2445:                                             ; preds = %2436
; BB287 :
  %2446 = uitofp i32 %2437 to float		; visa id: 2370
  %2447 = fmul float %2005, %2446		; visa id: 2371
  %2448 = and i32 %145, 268435456
  %2449 = icmp eq i32 %2448, 0		; visa id: 2372
  %2450 = select i1 %2449, i32 1, i32 -1		; visa id: 2374
  %2451 = sitofp i32 %2450 to float		; visa id: 2375
  %2452 = fmul float %2447, %2451		; visa id: 2376
  br label %2453, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2377

2453:                                             ; preds = %2445, %2438
; BB288 :
  %.sroa.224.11 = phi float [ %2452, %2445 ], [ %2444, %2438 ]
  %2454 = bitcast i32 %1786 to <4 x i8>
  %2455 = extractelement <4 x i8> %2454, i32 1
  %2456 = zext i8 %2455 to i32		; visa id: 2378
  br i1 %2009, label %2464, label %2457, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2379

2457:                                             ; preds = %2453
; BB289 :
  %2458 = and i32 %145, 536870912
  %2459 = sub nsw i32 0, %2456, !spirv.Decorations !8798
  %2460 = icmp eq i32 %2458, 0		; visa id: 2381
  %2461 = select i1 %2460, i32 %2456, i32 %2459		; visa id: 2383
  %2462 = sitofp i32 %2461 to float		; visa id: 2384
  %2463 = fmul float %2005, %2462		; visa id: 2385
  br label %2472, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2386

2464:                                             ; preds = %2453
; BB290 :
  %2465 = uitofp i32 %2456 to float		; visa id: 2388
  %2466 = fmul float %2005, %2465		; visa id: 2389
  %2467 = and i32 %145, 536870912
  %2468 = icmp eq i32 %2467, 0		; visa id: 2390
  %2469 = select i1 %2468, i32 1, i32 -1		; visa id: 2392
  %2470 = sitofp i32 %2469 to float		; visa id: 2393
  %2471 = fmul float %2466, %2470		; visa id: 2394
  br label %2472, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2395

2472:                                             ; preds = %2464, %2457
; BB291 :
  %.sroa.272.11 = phi float [ %2471, %2464 ], [ %2463, %2457 ]
  %2473 = extractelement <4 x i8> %2454, i32 2
  %2474 = zext i8 %2473 to i32		; visa id: 2396
  br i1 %2009, label %2482, label %2475, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2397

2475:                                             ; preds = %2472
; BB292 :
  %2476 = and i32 %145, 1073741824
  %2477 = sub nsw i32 0, %2474, !spirv.Decorations !8798
  %2478 = icmp eq i32 %2476, 0		; visa id: 2399
  %2479 = select i1 %2478, i32 %2474, i32 %2477		; visa id: 2401
  %2480 = sitofp i32 %2479 to float		; visa id: 2402
  %2481 = fmul float %2005, %2480		; visa id: 2403
  br label %2490, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2404

2482:                                             ; preds = %2472
; BB293 :
  %2483 = uitofp i32 %2474 to float		; visa id: 2406
  %2484 = fmul float %2005, %2483		; visa id: 2407
  %2485 = and i32 %145, 1073741824
  %2486 = icmp eq i32 %2485, 0		; visa id: 2408
  %2487 = select i1 %2486, i32 1, i32 -1		; visa id: 2410
  %2488 = sitofp i32 %2487 to float		; visa id: 2411
  %2489 = fmul float %2484, %2488		; visa id: 2412
  br label %2490, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2413

2490:                                             ; preds = %2482, %2475
; BB294 :
  %.sroa.320.11 = phi float [ %2489, %2482 ], [ %2481, %2475 ]
  %2491 = lshr i32 %1786, 24		; visa id: 2414
  br i1 %2009, label %2498, label %2492, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2415

2492:                                             ; preds = %2490
; BB295 :
  %2493 = sub nsw i32 0, %2491, !spirv.Decorations !8798
  %2494 = icmp slt i32 %145, 0		; visa id: 2417
  %2495 = select i1 %2494, i32 %2493, i32 %2491		; visa id: 2418
  %2496 = sitofp i32 %2495 to float		; visa id: 2419
  %2497 = fmul float %2005, %2496		; visa id: 2420
  br label %._crit_edge43.3, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2421

2498:                                             ; preds = %2490
; BB296 :
  %2499 = uitofp i32 %2491 to float		; visa id: 2423
  %2500 = fmul float %2005, %2499		; visa id: 2424
  %2501 = icmp sgt i32 %145, -1		; visa id: 2425
  %2502 = select i1 %2501, i32 1, i32 -1		; visa id: 2426
  %2503 = sitofp i32 %2502 to float		; visa id: 2427
  %2504 = fmul float %2500, %2503		; visa id: 2428
  br label %._crit_edge43.3, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2429

._crit_edge43.3:                                  ; preds = %2498, %2492
; BB297 :
  %.sroa.368.11 = phi float [ %2504, %2498 ], [ %2497, %2492 ]
  %2505 = fmul float %.sroa.062.11, %2328		; visa id: 2430
  %2506 = fadd float %.sroa.31.0, %2505		; visa id: 2431
  %2507 = fmul float %.sroa.80.11, %2333		; visa id: 2432
  %2508 = fadd float %2506, %2507		; visa id: 2433
  %2509 = fmul float %.sroa.128.11, %2338		; visa id: 2434
  %2510 = fadd float %2508, %2509		; visa id: 2435
  %2511 = fmul float %.sroa.176.11, %2343		; visa id: 2436
  %2512 = fadd float %2510, %2511		; visa id: 2437
  %2513 = fmul float %.sroa.224.11, %2348		; visa id: 2438
  %2514 = fadd float %2512, %2513		; visa id: 2439
  %2515 = fmul float %.sroa.272.11, %2353		; visa id: 2440
  %2516 = fadd float %2514, %2515		; visa id: 2441
  %2517 = fmul float %.sroa.320.11, %2358		; visa id: 2442
  %2518 = fadd float %2516, %2517		; visa id: 2443
  %2519 = fmul float %.sroa.368.11, %2363		; visa id: 2444
  %2520 = fadd float %2518, %2519		; visa id: 2445
  %2521 = and i32 %125, 255
  %2522 = lshr i32 %160, 4		; visa id: 2446
  %2523 = and i32 %2522, 768		; visa id: 2447
  %2524 = or i32 %2521, %2523		; visa id: 2448
  %2525 = shl nuw nsw i32 %2524, 3, !spirv.Decorations !8791		; visa id: 2449
  %2526 = zext i32 %2525 to i64		; visa id: 2450
  %2527 = add i64 %sink_, %2526		; visa id: 2451
  %2528 = inttoptr i64 %2527 to ptr addrspace(1)		; visa id: 2452
  %2529 = load <2 x i32>, ptr addrspace(1) %2528, align 4		; visa id: 2452
  %2530 = bitcast i32 %125 to <4 x i8>
  %2531 = extractelement <4 x i8> %2530, i32 2
  %2532 = lshr i32 %160, 6		; visa id: 2453
  %2533 = and i32 %2532, 768
  %2534 = zext i8 %2531 to i32		; visa id: 2454
  %2535 = or i32 %2534, %2533		; visa id: 2455
  %2536 = shl nuw nsw i32 %2535, 3, !spirv.Decorations !8791		; visa id: 2456
  %2537 = zext i32 %2536 to i64		; visa id: 2457
  %2538 = add i64 %sink_, %2537		; visa id: 2458
  %2539 = inttoptr i64 %2538 to ptr addrspace(1)		; visa id: 2459
  %2540 = load <2 x i32>, ptr addrspace(1) %2539, align 4		; visa id: 2459
  %2541 = extractelement <2 x i32> %2529, i32 0		; visa id: 2460
  %2542 = extractelement <2 x i32> %2529, i32 1		; visa id: 2460
  %2543 = extractelement <2 x i32> %2540, i32 0		; visa id: 2460
  %2544 = extractelement <2 x i32> %2540, i32 1		; visa id: 2460
  %2545 = and i32 %146, 255
  %2546 = lshr i32 %185, 4		; visa id: 2460
  %2547 = and i32 %2546, 768		; visa id: 2461
  %2548 = or i32 %2545, %2547		; visa id: 2462
  %2549 = shl nuw nsw i32 %2548, 3, !spirv.Decorations !8791		; visa id: 2463
  %2550 = zext i32 %2549 to i64		; visa id: 2464
  %2551 = add i64 %sink_, %2550		; visa id: 2465
  %2552 = inttoptr i64 %2551 to ptr addrspace(1)		; visa id: 2466
  %2553 = load <2 x i32>, ptr addrspace(1) %2552, align 4		; visa id: 2466
  %2554 = bitcast i32 %146 to <4 x i8>
  %2555 = extractelement <4 x i8> %2554, i32 2
  %2556 = lshr i32 %185, 6		; visa id: 2467
  %2557 = and i32 %2556, 768
  %2558 = zext i8 %2555 to i32		; visa id: 2468
  %2559 = or i32 %2558, %2557		; visa id: 2469
  %2560 = shl nuw nsw i32 %2559, 3, !spirv.Decorations !8791		; visa id: 2470
  %2561 = zext i32 %2560 to i64		; visa id: 2471
  %2562 = add i64 %sink_, %2561		; visa id: 2472
  %2563 = inttoptr i64 %2562 to ptr addrspace(1)		; visa id: 2473
  %2564 = load <2 x i32>, ptr addrspace(1) %2563, align 4		; visa id: 2473
  %2565 = extractelement <2 x i32> %2553, i32 0		; visa id: 2474
  %2566 = extractelement <2 x i32> %2553, i32 1		; visa id: 2474
  %2567 = extractelement <2 x i32> %2564, i32 0		; visa id: 2474
  %2568 = extractelement <2 x i32> %2564, i32 1		; visa id: 2474
  %2569 = or i32 %209, 96		; visa id: 2474
  %2570 = zext i32 %2569 to i64		; visa id: 2475
  %2571 = add i64 %2570, %const_reg_qword2		; visa id: 2476
  %IntToPtr2628 = inttoptr i64 %2571 to ptr addrspace(1)		; visa id: 2477
  %vCastload629 = load i32, ptr addrspace(1) %IntToPtr2628, align 2		; visa id: 2477
  %2572 = add i64 %2571, 4
  %IntToPtr2630 = inttoptr i64 %2572 to ptr addrspace(1)
  %vCastload631 = load i32, ptr addrspace(1) %IntToPtr2630, align 2		; visa id: 2478
  %2573 = add i64 %2571, 8
  %IntToPtr2632 = inttoptr i64 %2573 to ptr addrspace(1)
  %vCastload633 = load i32, ptr addrspace(1) %IntToPtr2632, align 2		; visa id: 2479
  %2574 = add i64 %2571, 12
  %IntToPtr2634 = inttoptr i64 %2574 to ptr addrspace(1)
  %vCastload635 = load i32, ptr addrspace(1) %IntToPtr2634, align 2		; visa id: 2480
  %2575 = bitcast i32 %vCastload629 to <2 x i16>		; visa id: 2481
  %2576 = bitcast i32 %vCastload631 to <2 x i16>		; visa id: 2483
  %2577 = extractelement <2 x i16> %2575, i32 0		; visa id: 2485
  %2578 = extractelement <2 x i16> %2575, i32 1		; visa id: 2485
  %2579 = extractelement <2 x i16> %2576, i32 0		; visa id: 2485
  %2580 = extractelement <2 x i16> %2576, i32 1		; visa id: 2485
  %2581 = bitcast i32 %vCastload633 to <2 x i16>		; visa id: 2485
  %2582 = bitcast i32 %vCastload635 to <2 x i16>		; visa id: 2487
  %2583 = extractelement <2 x i16> %2581, i32 0		; visa id: 2489
  %2584 = extractelement <2 x i16> %2581, i32 1		; visa id: 2489
  %2585 = extractelement <2 x i16> %2582, i32 0		; visa id: 2489
  %2586 = extractelement <2 x i16> %2582, i32 1		; visa id: 2489
  %2587 = lshr i32 %1805, 4		; visa id: 2489
  %2588 = uitofp i32 %2587 to float		; visa id: 2490
  %2589 = fadd float %2588, 5.000000e-01		; visa id: 2491
  %2590 = fmul float %139, %2589		; visa id: 2492
  %2591 = fmul float %2590, 2.500000e-01		; visa id: 2493
  %2592 = bitcast float %2591 to i32
  %2593 = and i32 %2592, 2147483647		; visa id: 2494
  %2594 = icmp ugt i32 %2593, 2139095040
  %2595 = fcmp oeq float %238, 0x7FF0000000000000		; visa id: 2495
  %2596 = fcmp une float %238, %238
  %2597 = or i1 %2596, %2595		; visa id: 2496
  %2598 = or i1 %2597, %2594		; visa id: 2498
  %2599 = and i32 %2541, 255		; visa id: 2500
  br i1 %2598, label %2607, label %2600, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2501

2600:                                             ; preds = %._crit_edge43.3
; BB298 :
  %2601 = and i32 %125, 256
  %2602 = sub nsw i32 0, %2599, !spirv.Decorations !8798
  %2603 = icmp eq i32 %2601, 0		; visa id: 2503
  %2604 = select i1 %2603, i32 %2599, i32 %2602		; visa id: 2505
  %2605 = sitofp i32 %2604 to float		; visa id: 2506
  %2606 = fmul float %2591, %2605		; visa id: 2507
  br label %2615, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2508

2607:                                             ; preds = %._crit_edge43.3
; BB299 :
  %2608 = uitofp i32 %2599 to float		; visa id: 2510
  %2609 = fmul float %2591, %2608		; visa id: 2511
  %2610 = and i32 %125, 256
  %2611 = icmp eq i32 %2610, 0		; visa id: 2512
  %2612 = select i1 %2611, i32 1, i32 -1		; visa id: 2514
  %2613 = sitofp i32 %2612 to float		; visa id: 2515
  %2614 = fmul float %2609, %2613		; visa id: 2516
  br label %2615, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2517

2615:                                             ; preds = %2607, %2600
; BB300 :
  %.sroa.062.12 = phi float [ %2614, %2607 ], [ %2606, %2600 ]
  %2616 = bitcast i32 %2541 to <4 x i8>
  %2617 = extractelement <4 x i8> %2616, i32 1
  %2618 = zext i8 %2617 to i32		; visa id: 2518
  br i1 %2598, label %2626, label %2619, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2519

2619:                                             ; preds = %2615
; BB301 :
  %2620 = and i32 %125, 512
  %2621 = sub nsw i32 0, %2618, !spirv.Decorations !8798
  %2622 = icmp eq i32 %2620, 0		; visa id: 2521
  %2623 = select i1 %2622, i32 %2618, i32 %2621		; visa id: 2523
  %2624 = sitofp i32 %2623 to float		; visa id: 2524
  %2625 = fmul float %2591, %2624		; visa id: 2525
  br label %2634, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2526

2626:                                             ; preds = %2615
; BB302 :
  %2627 = uitofp i32 %2618 to float		; visa id: 2528
  %2628 = fmul float %2591, %2627		; visa id: 2529
  %2629 = and i32 %125, 512
  %2630 = icmp eq i32 %2629, 0		; visa id: 2530
  %2631 = select i1 %2630, i32 1, i32 -1		; visa id: 2532
  %2632 = sitofp i32 %2631 to float		; visa id: 2533
  %2633 = fmul float %2628, %2632		; visa id: 2534
  br label %2634, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2535

2634:                                             ; preds = %2626, %2619
; BB303 :
  %.sroa.80.12 = phi float [ %2633, %2626 ], [ %2625, %2619 ]
  %2635 = extractelement <4 x i8> %2616, i32 2
  %2636 = zext i8 %2635 to i32		; visa id: 2536
  br i1 %2598, label %2644, label %2637, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2537

2637:                                             ; preds = %2634
; BB304 :
  %2638 = and i32 %125, 1024
  %2639 = sub nsw i32 0, %2636, !spirv.Decorations !8798
  %2640 = icmp eq i32 %2638, 0		; visa id: 2539
  %2641 = select i1 %2640, i32 %2636, i32 %2639		; visa id: 2541
  %2642 = sitofp i32 %2641 to float		; visa id: 2542
  %2643 = fmul float %2591, %2642		; visa id: 2543
  br label %2652, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2544

2644:                                             ; preds = %2634
; BB305 :
  %2645 = uitofp i32 %2636 to float		; visa id: 2546
  %2646 = fmul float %2591, %2645		; visa id: 2547
  %2647 = and i32 %125, 1024
  %2648 = icmp eq i32 %2647, 0		; visa id: 2548
  %2649 = select i1 %2648, i32 1, i32 -1		; visa id: 2550
  %2650 = sitofp i32 %2649 to float		; visa id: 2551
  %2651 = fmul float %2646, %2650		; visa id: 2552
  br label %2652, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2553

2652:                                             ; preds = %2644, %2637
; BB306 :
  %.sroa.128.12 = phi float [ %2651, %2644 ], [ %2643, %2637 ]
  %2653 = lshr i32 %2541, 24		; visa id: 2554
  br i1 %2598, label %2661, label %2654, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2555

2654:                                             ; preds = %2652
; BB307 :
  %2655 = and i32 %125, 2048
  %2656 = sub nsw i32 0, %2653, !spirv.Decorations !8798
  %2657 = icmp eq i32 %2655, 0		; visa id: 2557
  %2658 = select i1 %2657, i32 %2653, i32 %2656		; visa id: 2559
  %2659 = sitofp i32 %2658 to float		; visa id: 2560
  %2660 = fmul float %2591, %2659		; visa id: 2561
  br label %2669, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2562

2661:                                             ; preds = %2652
; BB308 :
  %2662 = uitofp i32 %2653 to float		; visa id: 2564
  %2663 = fmul float %2591, %2662		; visa id: 2565
  %2664 = and i32 %125, 2048
  %2665 = icmp eq i32 %2664, 0		; visa id: 2566
  %2666 = select i1 %2665, i32 1, i32 -1		; visa id: 2568
  %2667 = sitofp i32 %2666 to float		; visa id: 2569
  %2668 = fmul float %2663, %2667		; visa id: 2570
  br label %2669, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2571

2669:                                             ; preds = %2661, %2654
; BB309 :
  %.sroa.176.12 = phi float [ %2668, %2661 ], [ %2660, %2654 ]
  %2670 = and i32 %2542, 255		; visa id: 2572
  br i1 %2598, label %2678, label %2671, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2573

2671:                                             ; preds = %2669
; BB310 :
  %2672 = and i32 %125, 4096
  %2673 = sub nsw i32 0, %2670, !spirv.Decorations !8798
  %2674 = icmp eq i32 %2672, 0		; visa id: 2575
  %2675 = select i1 %2674, i32 %2670, i32 %2673		; visa id: 2577
  %2676 = sitofp i32 %2675 to float		; visa id: 2578
  %2677 = fmul float %2591, %2676		; visa id: 2579
  br label %2686, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2580

2678:                                             ; preds = %2669
; BB311 :
  %2679 = uitofp i32 %2670 to float		; visa id: 2582
  %2680 = fmul float %2591, %2679		; visa id: 2583
  %2681 = and i32 %125, 4096
  %2682 = icmp eq i32 %2681, 0		; visa id: 2584
  %2683 = select i1 %2682, i32 1, i32 -1		; visa id: 2586
  %2684 = sitofp i32 %2683 to float		; visa id: 2587
  %2685 = fmul float %2680, %2684		; visa id: 2588
  br label %2686, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2589

2686:                                             ; preds = %2678, %2671
; BB312 :
  %.sroa.224.12 = phi float [ %2685, %2678 ], [ %2677, %2671 ]
  %2687 = bitcast i32 %2542 to <4 x i8>
  %2688 = extractelement <4 x i8> %2687, i32 1
  %2689 = zext i8 %2688 to i32		; visa id: 2590
  br i1 %2598, label %2697, label %2690, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2591

2690:                                             ; preds = %2686
; BB313 :
  %2691 = and i32 %125, 8192
  %2692 = sub nsw i32 0, %2689, !spirv.Decorations !8798
  %2693 = icmp eq i32 %2691, 0		; visa id: 2593
  %2694 = select i1 %2693, i32 %2689, i32 %2692		; visa id: 2595
  %2695 = sitofp i32 %2694 to float		; visa id: 2596
  %2696 = fmul float %2591, %2695		; visa id: 2597
  br label %2705, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2598

2697:                                             ; preds = %2686
; BB314 :
  %2698 = uitofp i32 %2689 to float		; visa id: 2600
  %2699 = fmul float %2591, %2698		; visa id: 2601
  %2700 = and i32 %125, 8192
  %2701 = icmp eq i32 %2700, 0		; visa id: 2602
  %2702 = select i1 %2701, i32 1, i32 -1		; visa id: 2604
  %2703 = sitofp i32 %2702 to float		; visa id: 2605
  %2704 = fmul float %2699, %2703		; visa id: 2606
  br label %2705, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2607

2705:                                             ; preds = %2697, %2690
; BB315 :
  %.sroa.272.12 = phi float [ %2704, %2697 ], [ %2696, %2690 ]
  %2706 = extractelement <4 x i8> %2687, i32 2
  %2707 = zext i8 %2706 to i32		; visa id: 2608
  br i1 %2598, label %2715, label %2708, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2609

2708:                                             ; preds = %2705
; BB316 :
  %2709 = and i32 %125, 16384
  %2710 = sub nsw i32 0, %2707, !spirv.Decorations !8798
  %2711 = icmp eq i32 %2709, 0		; visa id: 2611
  %2712 = select i1 %2711, i32 %2707, i32 %2710		; visa id: 2613
  %2713 = sitofp i32 %2712 to float		; visa id: 2614
  %2714 = fmul float %2591, %2713		; visa id: 2615
  br label %2723, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2616

2715:                                             ; preds = %2705
; BB317 :
  %2716 = uitofp i32 %2707 to float		; visa id: 2618
  %2717 = fmul float %2591, %2716		; visa id: 2619
  %2718 = and i32 %125, 16384
  %2719 = icmp eq i32 %2718, 0		; visa id: 2620
  %2720 = select i1 %2719, i32 1, i32 -1		; visa id: 2622
  %2721 = sitofp i32 %2720 to float		; visa id: 2623
  %2722 = fmul float %2717, %2721		; visa id: 2624
  br label %2723, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2625

2723:                                             ; preds = %2715, %2708
; BB318 :
  %.sroa.320.12 = phi float [ %2722, %2715 ], [ %2714, %2708 ]
  %2724 = lshr i32 %2542, 24		; visa id: 2626
  br i1 %2598, label %2732, label %2725, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2627

2725:                                             ; preds = %2723
; BB319 :
  %2726 = and i32 %125, 32768
  %2727 = sub nsw i32 0, %2724, !spirv.Decorations !8798
  %2728 = icmp eq i32 %2726, 0		; visa id: 2629
  %2729 = select i1 %2728, i32 %2724, i32 %2727		; visa id: 2631
  %2730 = sitofp i32 %2729 to float		; visa id: 2632
  %2731 = fmul float %2591, %2730		; visa id: 2633
  br label %2740, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2634

2732:                                             ; preds = %2723
; BB320 :
  %2733 = uitofp i32 %2724 to float		; visa id: 2636
  %2734 = fmul float %2591, %2733		; visa id: 2637
  %2735 = and i32 %125, 32768
  %2736 = icmp eq i32 %2735, 0		; visa id: 2638
  %2737 = select i1 %2736, i32 1, i32 -1		; visa id: 2640
  %2738 = sitofp i32 %2737 to float		; visa id: 2641
  %2739 = fmul float %2734, %2738		; visa id: 2642
  br label %2740, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2643

2740:                                             ; preds = %2732, %2725
; BB321 :
  %.sroa.368.12 = phi float [ %2739, %2732 ], [ %2731, %2725 ]
  %2741 = zext i16 %2577 to i32		; visa id: 2644
  %2742 = shl nuw i32 %2741, 16		; visa id: 2645
  %2743 = bitcast i32 %2742 to float
  %2744 = fmul float %.sroa.062.12, %2743		; visa id: 2646
  %2745 = fadd float %.sroa.16.0, %2744		; visa id: 2647
  %2746 = zext i16 %2578 to i32		; visa id: 2648
  %2747 = shl nuw i32 %2746, 16		; visa id: 2649
  %2748 = bitcast i32 %2747 to float
  %2749 = fmul float %.sroa.80.12, %2748		; visa id: 2650
  %2750 = fadd float %2745, %2749		; visa id: 2651
  %2751 = zext i16 %2579 to i32		; visa id: 2652
  %2752 = shl nuw i32 %2751, 16		; visa id: 2653
  %2753 = bitcast i32 %2752 to float
  %2754 = fmul float %.sroa.128.12, %2753		; visa id: 2654
  %2755 = fadd float %2750, %2754		; visa id: 2655
  %2756 = zext i16 %2580 to i32		; visa id: 2656
  %2757 = shl nuw i32 %2756, 16		; visa id: 2657
  %2758 = bitcast i32 %2757 to float
  %2759 = fmul float %.sroa.176.12, %2758		; visa id: 2658
  %2760 = fadd float %2755, %2759		; visa id: 2659
  %2761 = zext i16 %2583 to i32		; visa id: 2660
  %2762 = shl nuw i32 %2761, 16		; visa id: 2661
  %2763 = bitcast i32 %2762 to float
  %2764 = fmul float %.sroa.224.12, %2763		; visa id: 2662
  %2765 = fadd float %2760, %2764		; visa id: 2663
  %2766 = zext i16 %2584 to i32		; visa id: 2664
  %2767 = shl nuw i32 %2766, 16		; visa id: 2665
  %2768 = bitcast i32 %2767 to float
  %2769 = fmul float %.sroa.272.12, %2768		; visa id: 2666
  %2770 = fadd float %2765, %2769		; visa id: 2667
  %2771 = zext i16 %2585 to i32		; visa id: 2668
  %2772 = shl nuw i32 %2771, 16		; visa id: 2669
  %2773 = bitcast i32 %2772 to float
  %2774 = fmul float %.sroa.320.12, %2773		; visa id: 2670
  %2775 = fadd float %2770, %2774		; visa id: 2671
  %2776 = zext i16 %2586 to i32		; visa id: 2672
  %2777 = shl nuw i32 %2776, 16		; visa id: 2673
  %2778 = bitcast i32 %2777 to float
  %2779 = fmul float %.sroa.368.12, %2778		; visa id: 2674
  %2780 = fadd float %2775, %2779		; visa id: 2675
  %2781 = lshr i32 %2000, 4		; visa id: 2676
  %2782 = uitofp i32 %2781 to float		; visa id: 2677
  %2783 = fadd float %2782, 5.000000e-01		; visa id: 2678
  %2784 = fmul float %158, %2783		; visa id: 2679
  %2785 = fmul float %2784, 2.500000e-01		; visa id: 2680
  %2786 = bitcast float %2785 to i32
  %2787 = and i32 %2786, 2147483647		; visa id: 2681
  %2788 = icmp ugt i32 %2787, 2139095040		; visa id: 2682
  %2789 = or i1 %440, %2788		; visa id: 2683
  %2790 = and i32 %2565, 255		; visa id: 2684
  br i1 %2789, label %2798, label %2791, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2685

2791:                                             ; preds = %2740
; BB322 :
  %2792 = and i32 %146, 256
  %2793 = sub nsw i32 0, %2790, !spirv.Decorations !8798
  %2794 = icmp eq i32 %2792, 0		; visa id: 2687
  %2795 = select i1 %2794, i32 %2790, i32 %2793		; visa id: 2689
  %2796 = sitofp i32 %2795 to float		; visa id: 2690
  %2797 = fmul float %2785, %2796		; visa id: 2691
  br label %2806, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2692

2798:                                             ; preds = %2740
; BB323 :
  %2799 = uitofp i32 %2790 to float		; visa id: 2694
  %2800 = fmul float %2785, %2799		; visa id: 2695
  %2801 = and i32 %146, 256
  %2802 = icmp eq i32 %2801, 0		; visa id: 2696
  %2803 = select i1 %2802, i32 1, i32 -1		; visa id: 2698
  %2804 = sitofp i32 %2803 to float		; visa id: 2699
  %2805 = fmul float %2800, %2804		; visa id: 2700
  br label %2806, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2701

2806:                                             ; preds = %2798, %2791
; BB324 :
  %.sroa.062.13 = phi float [ %2805, %2798 ], [ %2797, %2791 ]
  %2807 = bitcast i32 %2565 to <4 x i8>
  %2808 = extractelement <4 x i8> %2807, i32 1
  %2809 = zext i8 %2808 to i32		; visa id: 2702
  br i1 %2789, label %2817, label %2810, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2703

2810:                                             ; preds = %2806
; BB325 :
  %2811 = and i32 %146, 512
  %2812 = sub nsw i32 0, %2809, !spirv.Decorations !8798
  %2813 = icmp eq i32 %2811, 0		; visa id: 2705
  %2814 = select i1 %2813, i32 %2809, i32 %2812		; visa id: 2707
  %2815 = sitofp i32 %2814 to float		; visa id: 2708
  %2816 = fmul float %2785, %2815		; visa id: 2709
  br label %2825, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2710

2817:                                             ; preds = %2806
; BB326 :
  %2818 = uitofp i32 %2809 to float		; visa id: 2712
  %2819 = fmul float %2785, %2818		; visa id: 2713
  %2820 = and i32 %146, 512
  %2821 = icmp eq i32 %2820, 0		; visa id: 2714
  %2822 = select i1 %2821, i32 1, i32 -1		; visa id: 2716
  %2823 = sitofp i32 %2822 to float		; visa id: 2717
  %2824 = fmul float %2819, %2823		; visa id: 2718
  br label %2825, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2719

2825:                                             ; preds = %2817, %2810
; BB327 :
  %.sroa.80.13 = phi float [ %2824, %2817 ], [ %2816, %2810 ]
  %2826 = extractelement <4 x i8> %2807, i32 2
  %2827 = zext i8 %2826 to i32		; visa id: 2720
  br i1 %2789, label %2835, label %2828, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2721

2828:                                             ; preds = %2825
; BB328 :
  %2829 = and i32 %146, 1024
  %2830 = sub nsw i32 0, %2827, !spirv.Decorations !8798
  %2831 = icmp eq i32 %2829, 0		; visa id: 2723
  %2832 = select i1 %2831, i32 %2827, i32 %2830		; visa id: 2725
  %2833 = sitofp i32 %2832 to float		; visa id: 2726
  %2834 = fmul float %2785, %2833		; visa id: 2727
  br label %2843, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2728

2835:                                             ; preds = %2825
; BB329 :
  %2836 = uitofp i32 %2827 to float		; visa id: 2730
  %2837 = fmul float %2785, %2836		; visa id: 2731
  %2838 = and i32 %146, 1024
  %2839 = icmp eq i32 %2838, 0		; visa id: 2732
  %2840 = select i1 %2839, i32 1, i32 -1		; visa id: 2734
  %2841 = sitofp i32 %2840 to float		; visa id: 2735
  %2842 = fmul float %2837, %2841		; visa id: 2736
  br label %2843, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2737

2843:                                             ; preds = %2835, %2828
; BB330 :
  %.sroa.128.13 = phi float [ %2842, %2835 ], [ %2834, %2828 ]
  %2844 = lshr i32 %2565, 24		; visa id: 2738
  br i1 %2789, label %2852, label %2845, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2739

2845:                                             ; preds = %2843
; BB331 :
  %2846 = and i32 %146, 2048
  %2847 = sub nsw i32 0, %2844, !spirv.Decorations !8798
  %2848 = icmp eq i32 %2846, 0		; visa id: 2741
  %2849 = select i1 %2848, i32 %2844, i32 %2847		; visa id: 2743
  %2850 = sitofp i32 %2849 to float		; visa id: 2744
  %2851 = fmul float %2785, %2850		; visa id: 2745
  br label %2860, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2746

2852:                                             ; preds = %2843
; BB332 :
  %2853 = uitofp i32 %2844 to float		; visa id: 2748
  %2854 = fmul float %2785, %2853		; visa id: 2749
  %2855 = and i32 %146, 2048
  %2856 = icmp eq i32 %2855, 0		; visa id: 2750
  %2857 = select i1 %2856, i32 1, i32 -1		; visa id: 2752
  %2858 = sitofp i32 %2857 to float		; visa id: 2753
  %2859 = fmul float %2854, %2858		; visa id: 2754
  br label %2860, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2755

2860:                                             ; preds = %2852, %2845
; BB333 :
  %.sroa.176.13 = phi float [ %2859, %2852 ], [ %2851, %2845 ]
  %2861 = and i32 %2566, 255		; visa id: 2756
  br i1 %2789, label %2869, label %2862, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2757

2862:                                             ; preds = %2860
; BB334 :
  %2863 = and i32 %146, 4096
  %2864 = sub nsw i32 0, %2861, !spirv.Decorations !8798
  %2865 = icmp eq i32 %2863, 0		; visa id: 2759
  %2866 = select i1 %2865, i32 %2861, i32 %2864		; visa id: 2761
  %2867 = sitofp i32 %2866 to float		; visa id: 2762
  %2868 = fmul float %2785, %2867		; visa id: 2763
  br label %2877, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2764

2869:                                             ; preds = %2860
; BB335 :
  %2870 = uitofp i32 %2861 to float		; visa id: 2766
  %2871 = fmul float %2785, %2870		; visa id: 2767
  %2872 = and i32 %146, 4096
  %2873 = icmp eq i32 %2872, 0		; visa id: 2768
  %2874 = select i1 %2873, i32 1, i32 -1		; visa id: 2770
  %2875 = sitofp i32 %2874 to float		; visa id: 2771
  %2876 = fmul float %2871, %2875		; visa id: 2772
  br label %2877, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2773

2877:                                             ; preds = %2869, %2862
; BB336 :
  %.sroa.224.13 = phi float [ %2876, %2869 ], [ %2868, %2862 ]
  %2878 = bitcast i32 %2566 to <4 x i8>
  %2879 = extractelement <4 x i8> %2878, i32 1
  %2880 = zext i8 %2879 to i32		; visa id: 2774
  br i1 %2789, label %2888, label %2881, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2775

2881:                                             ; preds = %2877
; BB337 :
  %2882 = and i32 %146, 8192
  %2883 = sub nsw i32 0, %2880, !spirv.Decorations !8798
  %2884 = icmp eq i32 %2882, 0		; visa id: 2777
  %2885 = select i1 %2884, i32 %2880, i32 %2883		; visa id: 2779
  %2886 = sitofp i32 %2885 to float		; visa id: 2780
  %2887 = fmul float %2785, %2886		; visa id: 2781
  br label %2896, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2782

2888:                                             ; preds = %2877
; BB338 :
  %2889 = uitofp i32 %2880 to float		; visa id: 2784
  %2890 = fmul float %2785, %2889		; visa id: 2785
  %2891 = and i32 %146, 8192
  %2892 = icmp eq i32 %2891, 0		; visa id: 2786
  %2893 = select i1 %2892, i32 1, i32 -1		; visa id: 2788
  %2894 = sitofp i32 %2893 to float		; visa id: 2789
  %2895 = fmul float %2890, %2894		; visa id: 2790
  br label %2896, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2791

2896:                                             ; preds = %2888, %2881
; BB339 :
  %.sroa.272.13 = phi float [ %2895, %2888 ], [ %2887, %2881 ]
  %2897 = extractelement <4 x i8> %2878, i32 2
  %2898 = zext i8 %2897 to i32		; visa id: 2792
  br i1 %2789, label %2906, label %2899, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2793

2899:                                             ; preds = %2896
; BB340 :
  %2900 = and i32 %146, 16384
  %2901 = sub nsw i32 0, %2898, !spirv.Decorations !8798
  %2902 = icmp eq i32 %2900, 0		; visa id: 2795
  %2903 = select i1 %2902, i32 %2898, i32 %2901		; visa id: 2797
  %2904 = sitofp i32 %2903 to float		; visa id: 2798
  %2905 = fmul float %2785, %2904		; visa id: 2799
  br label %2914, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2800

2906:                                             ; preds = %2896
; BB341 :
  %2907 = uitofp i32 %2898 to float		; visa id: 2802
  %2908 = fmul float %2785, %2907		; visa id: 2803
  %2909 = and i32 %146, 16384
  %2910 = icmp eq i32 %2909, 0		; visa id: 2804
  %2911 = select i1 %2910, i32 1, i32 -1		; visa id: 2806
  %2912 = sitofp i32 %2911 to float		; visa id: 2807
  %2913 = fmul float %2908, %2912		; visa id: 2808
  br label %2914, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2809

2914:                                             ; preds = %2906, %2899
; BB342 :
  %.sroa.320.13 = phi float [ %2913, %2906 ], [ %2905, %2899 ]
  %2915 = lshr i32 %2566, 24		; visa id: 2810
  br i1 %2789, label %2923, label %2916, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2811

2916:                                             ; preds = %2914
; BB343 :
  %2917 = and i32 %146, 32768
  %2918 = sub nsw i32 0, %2915, !spirv.Decorations !8798
  %2919 = icmp eq i32 %2917, 0		; visa id: 2813
  %2920 = select i1 %2919, i32 %2915, i32 %2918		; visa id: 2815
  %2921 = sitofp i32 %2920 to float		; visa id: 2816
  %2922 = fmul float %2785, %2921		; visa id: 2817
  br label %2931, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2818

2923:                                             ; preds = %2914
; BB344 :
  %2924 = uitofp i32 %2915 to float		; visa id: 2820
  %2925 = fmul float %2785, %2924		; visa id: 2821
  %2926 = and i32 %146, 32768
  %2927 = icmp eq i32 %2926, 0		; visa id: 2822
  %2928 = select i1 %2927, i32 1, i32 -1		; visa id: 2824
  %2929 = sitofp i32 %2928 to float		; visa id: 2825
  %2930 = fmul float %2925, %2929		; visa id: 2826
  br label %2931, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2827

2931:                                             ; preds = %2923, %2916
; BB345 :
  %.sroa.368.13 = phi float [ %2930, %2923 ], [ %2922, %2916 ]
  %2932 = fmul float %.sroa.062.13, %2743		; visa id: 2828
  %2933 = fadd float %.sroa.33.0, %2932		; visa id: 2829
  %2934 = fmul float %.sroa.80.13, %2748		; visa id: 2830
  %2935 = fadd float %2933, %2934		; visa id: 2831
  %2936 = fmul float %.sroa.128.13, %2753		; visa id: 2832
  %2937 = fadd float %2935, %2936		; visa id: 2833
  %2938 = fmul float %.sroa.176.13, %2758		; visa id: 2834
  %2939 = fadd float %2937, %2938		; visa id: 2835
  %2940 = fmul float %.sroa.224.13, %2763		; visa id: 2836
  %2941 = fadd float %2939, %2940		; visa id: 2837
  %2942 = fmul float %.sroa.272.13, %2768		; visa id: 2838
  %2943 = fadd float %2941, %2942		; visa id: 2839
  %2944 = fmul float %.sroa.320.13, %2773		; visa id: 2840
  %2945 = fadd float %2943, %2944		; visa id: 2841
  %2946 = fmul float %.sroa.368.13, %2778		; visa id: 2842
  %2947 = fadd float %2945, %2946		; visa id: 2843
  %2948 = or i32 %209, 112		; visa id: 2844
  %2949 = zext i32 %2948 to i64		; visa id: 2845
  %2950 = add i64 %2949, %const_reg_qword2		; visa id: 2846
  %IntToPtr2636 = inttoptr i64 %2950 to ptr addrspace(1)		; visa id: 2847
  %vCastload637 = load i32, ptr addrspace(1) %IntToPtr2636, align 2		; visa id: 2847
  %2951 = add i64 %2950, 4
  %IntToPtr2638 = inttoptr i64 %2951 to ptr addrspace(1)
  %vCastload639 = load i32, ptr addrspace(1) %IntToPtr2638, align 2		; visa id: 2848
  %2952 = add i64 %2950, 8
  %IntToPtr2640 = inttoptr i64 %2952 to ptr addrspace(1)
  %vCastload641 = load i32, ptr addrspace(1) %IntToPtr2640, align 2		; visa id: 2849
  %2953 = add i64 %2950, 12
  %IntToPtr2642 = inttoptr i64 %2953 to ptr addrspace(1)
  %vCastload643 = load i32, ptr addrspace(1) %IntToPtr2642, align 2		; visa id: 2850
  %2954 = bitcast i32 %vCastload637 to <2 x i16>		; visa id: 2851
  %2955 = bitcast i32 %vCastload639 to <2 x i16>		; visa id: 2853
  %2956 = extractelement <2 x i16> %2954, i32 0		; visa id: 2855
  %2957 = extractelement <2 x i16> %2954, i32 1		; visa id: 2855
  %2958 = extractelement <2 x i16> %2955, i32 0		; visa id: 2855
  %2959 = extractelement <2 x i16> %2955, i32 1		; visa id: 2855
  %2960 = bitcast i32 %vCastload641 to <2 x i16>		; visa id: 2855
  %2961 = bitcast i32 %vCastload643 to <2 x i16>		; visa id: 2857
  %2962 = extractelement <2 x i16> %2960, i32 0		; visa id: 2859
  %2963 = extractelement <2 x i16> %2960, i32 1		; visa id: 2859
  %2964 = extractelement <2 x i16> %2961, i32 0		; visa id: 2859
  %2965 = extractelement <2 x i16> %2961, i32 1		; visa id: 2859
  %2966 = and i32 %2543, 255		; visa id: 2859
  br i1 %2598, label %2974, label %2967, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2860

2967:                                             ; preds = %2931
; BB346 :
  %2968 = and i32 %125, 16777216
  %2969 = sub nsw i32 0, %2966, !spirv.Decorations !8798
  %2970 = icmp eq i32 %2968, 0		; visa id: 2862
  %2971 = select i1 %2970, i32 %2966, i32 %2969		; visa id: 2864
  %2972 = sitofp i32 %2971 to float		; visa id: 2865
  %2973 = fmul float %2591, %2972		; visa id: 2866
  br label %2982, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2867

2974:                                             ; preds = %2931
; BB347 :
  %2975 = uitofp i32 %2966 to float		; visa id: 2869
  %2976 = fmul float %2591, %2975		; visa id: 2870
  %2977 = and i32 %125, 16777216
  %2978 = icmp eq i32 %2977, 0		; visa id: 2871
  %2979 = select i1 %2978, i32 1, i32 -1		; visa id: 2873
  %2980 = sitofp i32 %2979 to float		; visa id: 2874
  %2981 = fmul float %2976, %2980		; visa id: 2875
  br label %2982, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2876

2982:                                             ; preds = %2974, %2967
; BB348 :
  %.sroa.062.14 = phi float [ %2981, %2974 ], [ %2973, %2967 ]
  %2983 = bitcast i32 %2543 to <4 x i8>
  %2984 = extractelement <4 x i8> %2983, i32 1
  %2985 = zext i8 %2984 to i32		; visa id: 2877
  br i1 %2598, label %2993, label %2986, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2878

2986:                                             ; preds = %2982
; BB349 :
  %2987 = and i32 %125, 33554432
  %2988 = sub nsw i32 0, %2985, !spirv.Decorations !8798
  %2989 = icmp eq i32 %2987, 0		; visa id: 2880
  %2990 = select i1 %2989, i32 %2985, i32 %2988		; visa id: 2882
  %2991 = sitofp i32 %2990 to float		; visa id: 2883
  %2992 = fmul float %2591, %2991		; visa id: 2884
  br label %3001, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2885

2993:                                             ; preds = %2982
; BB350 :
  %2994 = uitofp i32 %2985 to float		; visa id: 2887
  %2995 = fmul float %2591, %2994		; visa id: 2888
  %2996 = and i32 %125, 33554432
  %2997 = icmp eq i32 %2996, 0		; visa id: 2889
  %2998 = select i1 %2997, i32 1, i32 -1		; visa id: 2891
  %2999 = sitofp i32 %2998 to float		; visa id: 2892
  %3000 = fmul float %2995, %2999		; visa id: 2893
  br label %3001, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2894

3001:                                             ; preds = %2993, %2986
; BB351 :
  %.sroa.80.14 = phi float [ %3000, %2993 ], [ %2992, %2986 ]
  %3002 = extractelement <4 x i8> %2983, i32 2
  %3003 = zext i8 %3002 to i32		; visa id: 2895
  br i1 %2598, label %3011, label %3004, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2896

3004:                                             ; preds = %3001
; BB352 :
  %3005 = and i32 %125, 67108864
  %3006 = sub nsw i32 0, %3003, !spirv.Decorations !8798
  %3007 = icmp eq i32 %3005, 0		; visa id: 2898
  %3008 = select i1 %3007, i32 %3003, i32 %3006		; visa id: 2900
  %3009 = sitofp i32 %3008 to float		; visa id: 2901
  %3010 = fmul float %2591, %3009		; visa id: 2902
  br label %3019, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2903

3011:                                             ; preds = %3001
; BB353 :
  %3012 = uitofp i32 %3003 to float		; visa id: 2905
  %3013 = fmul float %2591, %3012		; visa id: 2906
  %3014 = and i32 %125, 67108864
  %3015 = icmp eq i32 %3014, 0		; visa id: 2907
  %3016 = select i1 %3015, i32 1, i32 -1		; visa id: 2909
  %3017 = sitofp i32 %3016 to float		; visa id: 2910
  %3018 = fmul float %3013, %3017		; visa id: 2911
  br label %3019, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2912

3019:                                             ; preds = %3011, %3004
; BB354 :
  %.sroa.128.14 = phi float [ %3018, %3011 ], [ %3010, %3004 ]
  %3020 = lshr i32 %2543, 24		; visa id: 2913
  br i1 %2598, label %3028, label %3021, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2914

3021:                                             ; preds = %3019
; BB355 :
  %3022 = and i32 %125, 134217728
  %3023 = sub nsw i32 0, %3020, !spirv.Decorations !8798
  %3024 = icmp eq i32 %3022, 0		; visa id: 2916
  %3025 = select i1 %3024, i32 %3020, i32 %3023		; visa id: 2918
  %3026 = sitofp i32 %3025 to float		; visa id: 2919
  %3027 = fmul float %2591, %3026		; visa id: 2920
  br label %3036, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2921

3028:                                             ; preds = %3019
; BB356 :
  %3029 = uitofp i32 %3020 to float		; visa id: 2923
  %3030 = fmul float %2591, %3029		; visa id: 2924
  %3031 = and i32 %125, 134217728
  %3032 = icmp eq i32 %3031, 0		; visa id: 2925
  %3033 = select i1 %3032, i32 1, i32 -1		; visa id: 2927
  %3034 = sitofp i32 %3033 to float		; visa id: 2928
  %3035 = fmul float %3030, %3034		; visa id: 2929
  br label %3036, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2930

3036:                                             ; preds = %3028, %3021
; BB357 :
  %.sroa.176.14 = phi float [ %3035, %3028 ], [ %3027, %3021 ]
  %3037 = and i32 %2544, 255		; visa id: 2931
  br i1 %2598, label %3045, label %3038, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2932

3038:                                             ; preds = %3036
; BB358 :
  %3039 = and i32 %125, 268435456
  %3040 = sub nsw i32 0, %3037, !spirv.Decorations !8798
  %3041 = icmp eq i32 %3039, 0		; visa id: 2934
  %3042 = select i1 %3041, i32 %3037, i32 %3040		; visa id: 2936
  %3043 = sitofp i32 %3042 to float		; visa id: 2937
  %3044 = fmul float %2591, %3043		; visa id: 2938
  br label %3053, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2939

3045:                                             ; preds = %3036
; BB359 :
  %3046 = uitofp i32 %3037 to float		; visa id: 2941
  %3047 = fmul float %2591, %3046		; visa id: 2942
  %3048 = and i32 %125, 268435456
  %3049 = icmp eq i32 %3048, 0		; visa id: 2943
  %3050 = select i1 %3049, i32 1, i32 -1		; visa id: 2945
  %3051 = sitofp i32 %3050 to float		; visa id: 2946
  %3052 = fmul float %3047, %3051		; visa id: 2947
  br label %3053, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2948

3053:                                             ; preds = %3045, %3038
; BB360 :
  %.sroa.224.14 = phi float [ %3052, %3045 ], [ %3044, %3038 ]
  %3054 = bitcast i32 %2544 to <4 x i8>
  %3055 = extractelement <4 x i8> %3054, i32 1
  %3056 = zext i8 %3055 to i32		; visa id: 2949
  br i1 %2598, label %3064, label %3057, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2950

3057:                                             ; preds = %3053
; BB361 :
  %3058 = and i32 %125, 536870912
  %3059 = sub nsw i32 0, %3056, !spirv.Decorations !8798
  %3060 = icmp eq i32 %3058, 0		; visa id: 2952
  %3061 = select i1 %3060, i32 %3056, i32 %3059		; visa id: 2954
  %3062 = sitofp i32 %3061 to float		; visa id: 2955
  %3063 = fmul float %2591, %3062		; visa id: 2956
  br label %3072, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2957

3064:                                             ; preds = %3053
; BB362 :
  %3065 = uitofp i32 %3056 to float		; visa id: 2959
  %3066 = fmul float %2591, %3065		; visa id: 2960
  %3067 = and i32 %125, 536870912
  %3068 = icmp eq i32 %3067, 0		; visa id: 2961
  %3069 = select i1 %3068, i32 1, i32 -1		; visa id: 2963
  %3070 = sitofp i32 %3069 to float		; visa id: 2964
  %3071 = fmul float %3066, %3070		; visa id: 2965
  br label %3072, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2966

3072:                                             ; preds = %3064, %3057
; BB363 :
  %.sroa.272.14 = phi float [ %3071, %3064 ], [ %3063, %3057 ]
  %3073 = extractelement <4 x i8> %3054, i32 2
  %3074 = zext i8 %3073 to i32		; visa id: 2967
  br i1 %2598, label %3082, label %3075, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2968

3075:                                             ; preds = %3072
; BB364 :
  %3076 = and i32 %125, 1073741824
  %3077 = sub nsw i32 0, %3074, !spirv.Decorations !8798
  %3078 = icmp eq i32 %3076, 0		; visa id: 2970
  %3079 = select i1 %3078, i32 %3074, i32 %3077		; visa id: 2972
  %3080 = sitofp i32 %3079 to float		; visa id: 2973
  %3081 = fmul float %2591, %3080		; visa id: 2974
  br label %3090, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2975

3082:                                             ; preds = %3072
; BB365 :
  %3083 = uitofp i32 %3074 to float		; visa id: 2977
  %3084 = fmul float %2591, %3083		; visa id: 2978
  %3085 = and i32 %125, 1073741824
  %3086 = icmp eq i32 %3085, 0		; visa id: 2979
  %3087 = select i1 %3086, i32 1, i32 -1		; visa id: 2981
  %3088 = sitofp i32 %3087 to float		; visa id: 2982
  %3089 = fmul float %3084, %3088		; visa id: 2983
  br label %3090, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2984

3090:                                             ; preds = %3082, %3075
; BB366 :
  %.sroa.320.14 = phi float [ %3089, %3082 ], [ %3081, %3075 ]
  %3091 = lshr i32 %2544, 24		; visa id: 2985
  br i1 %2598, label %3098, label %3092, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2986

3092:                                             ; preds = %3090
; BB367 :
  %3093 = sub nsw i32 0, %3091, !spirv.Decorations !8798
  %3094 = icmp slt i32 %125, 0		; visa id: 2988
  %3095 = select i1 %3094, i32 %3093, i32 %3091		; visa id: 2989
  %3096 = sitofp i32 %3095 to float		; visa id: 2990
  %3097 = fmul float %2591, %3096		; visa id: 2991
  br label %3105, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2992

3098:                                             ; preds = %3090
; BB368 :
  %3099 = uitofp i32 %3091 to float		; visa id: 2994
  %3100 = fmul float %2591, %3099		; visa id: 2995
  %3101 = icmp sgt i32 %125, -1		; visa id: 2996
  %3102 = select i1 %3101, i32 1, i32 -1		; visa id: 2997
  %3103 = sitofp i32 %3102 to float		; visa id: 2998
  %3104 = fmul float %3100, %3103		; visa id: 2999
  br label %3105, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3000

3105:                                             ; preds = %3098, %3092
; BB369 :
  %.sroa.368.14 = phi float [ %3104, %3098 ], [ %3097, %3092 ]
  %3106 = zext i16 %2956 to i32		; visa id: 3001
  %3107 = shl nuw i32 %3106, 16		; visa id: 3002
  %3108 = bitcast i32 %3107 to float
  %3109 = fmul float %.sroa.062.14, %3108		; visa id: 3003
  %3110 = fadd float %.sroa.18.0, %3109		; visa id: 3004
  %3111 = zext i16 %2957 to i32		; visa id: 3005
  %3112 = shl nuw i32 %3111, 16		; visa id: 3006
  %3113 = bitcast i32 %3112 to float
  %3114 = fmul float %.sroa.80.14, %3113		; visa id: 3007
  %3115 = fadd float %3110, %3114		; visa id: 3008
  %3116 = zext i16 %2958 to i32		; visa id: 3009
  %3117 = shl nuw i32 %3116, 16		; visa id: 3010
  %3118 = bitcast i32 %3117 to float
  %3119 = fmul float %.sroa.128.14, %3118		; visa id: 3011
  %3120 = fadd float %3115, %3119		; visa id: 3012
  %3121 = zext i16 %2959 to i32		; visa id: 3013
  %3122 = shl nuw i32 %3121, 16		; visa id: 3014
  %3123 = bitcast i32 %3122 to float
  %3124 = fmul float %.sroa.176.14, %3123		; visa id: 3015
  %3125 = fadd float %3120, %3124		; visa id: 3016
  %3126 = zext i16 %2962 to i32		; visa id: 3017
  %3127 = shl nuw i32 %3126, 16		; visa id: 3018
  %3128 = bitcast i32 %3127 to float
  %3129 = fmul float %.sroa.224.14, %3128		; visa id: 3019
  %3130 = fadd float %3125, %3129		; visa id: 3020
  %3131 = zext i16 %2963 to i32		; visa id: 3021
  %3132 = shl nuw i32 %3131, 16		; visa id: 3022
  %3133 = bitcast i32 %3132 to float
  %3134 = fmul float %.sroa.272.14, %3133		; visa id: 3023
  %3135 = fadd float %3130, %3134		; visa id: 3024
  %3136 = zext i16 %2964 to i32		; visa id: 3025
  %3137 = shl nuw i32 %3136, 16		; visa id: 3026
  %3138 = bitcast i32 %3137 to float
  %3139 = fmul float %.sroa.320.14, %3138		; visa id: 3027
  %3140 = fadd float %3135, %3139		; visa id: 3028
  %3141 = zext i16 %2965 to i32		; visa id: 3029
  %3142 = shl nuw i32 %3141, 16		; visa id: 3030
  %3143 = bitcast i32 %3142 to float
  %3144 = fmul float %.sroa.368.14, %3143		; visa id: 3031
  %3145 = fadd float %3140, %3144		; visa id: 3032
  %3146 = and i32 %2567, 255		; visa id: 3033
  br i1 %2789, label %3154, label %3147, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3034

3147:                                             ; preds = %3105
; BB370 :
  %3148 = and i32 %146, 16777216
  %3149 = sub nsw i32 0, %3146, !spirv.Decorations !8798
  %3150 = icmp eq i32 %3148, 0		; visa id: 3036
  %3151 = select i1 %3150, i32 %3146, i32 %3149		; visa id: 3038
  %3152 = sitofp i32 %3151 to float		; visa id: 3039
  %3153 = fmul float %2785, %3152		; visa id: 3040
  br label %3162, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3041

3154:                                             ; preds = %3105
; BB371 :
  %3155 = uitofp i32 %3146 to float		; visa id: 3043
  %3156 = fmul float %2785, %3155		; visa id: 3044
  %3157 = and i32 %146, 16777216
  %3158 = icmp eq i32 %3157, 0		; visa id: 3045
  %3159 = select i1 %3158, i32 1, i32 -1		; visa id: 3047
  %3160 = sitofp i32 %3159 to float		; visa id: 3048
  %3161 = fmul float %3156, %3160		; visa id: 3049
  br label %3162, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3050

3162:                                             ; preds = %3154, %3147
; BB372 :
  %.sroa.062.15 = phi float [ %3161, %3154 ], [ %3153, %3147 ]
  %3163 = bitcast i32 %2567 to <4 x i8>
  %3164 = extractelement <4 x i8> %3163, i32 1
  %3165 = zext i8 %3164 to i32		; visa id: 3051
  br i1 %2789, label %3173, label %3166, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3052

3166:                                             ; preds = %3162
; BB373 :
  %3167 = and i32 %146, 33554432
  %3168 = sub nsw i32 0, %3165, !spirv.Decorations !8798
  %3169 = icmp eq i32 %3167, 0		; visa id: 3054
  %3170 = select i1 %3169, i32 %3165, i32 %3168		; visa id: 3056
  %3171 = sitofp i32 %3170 to float		; visa id: 3057
  %3172 = fmul float %2785, %3171		; visa id: 3058
  br label %3181, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3059

3173:                                             ; preds = %3162
; BB374 :
  %3174 = uitofp i32 %3165 to float		; visa id: 3061
  %3175 = fmul float %2785, %3174		; visa id: 3062
  %3176 = and i32 %146, 33554432
  %3177 = icmp eq i32 %3176, 0		; visa id: 3063
  %3178 = select i1 %3177, i32 1, i32 -1		; visa id: 3065
  %3179 = sitofp i32 %3178 to float		; visa id: 3066
  %3180 = fmul float %3175, %3179		; visa id: 3067
  br label %3181, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3068

3181:                                             ; preds = %3173, %3166
; BB375 :
  %.sroa.80.15 = phi float [ %3180, %3173 ], [ %3172, %3166 ]
  %3182 = extractelement <4 x i8> %3163, i32 2
  %3183 = zext i8 %3182 to i32		; visa id: 3069
  br i1 %2789, label %3191, label %3184, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3070

3184:                                             ; preds = %3181
; BB376 :
  %3185 = and i32 %146, 67108864
  %3186 = sub nsw i32 0, %3183, !spirv.Decorations !8798
  %3187 = icmp eq i32 %3185, 0		; visa id: 3072
  %3188 = select i1 %3187, i32 %3183, i32 %3186		; visa id: 3074
  %3189 = sitofp i32 %3188 to float		; visa id: 3075
  %3190 = fmul float %2785, %3189		; visa id: 3076
  br label %3199, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3077

3191:                                             ; preds = %3181
; BB377 :
  %3192 = uitofp i32 %3183 to float		; visa id: 3079
  %3193 = fmul float %2785, %3192		; visa id: 3080
  %3194 = and i32 %146, 67108864
  %3195 = icmp eq i32 %3194, 0		; visa id: 3081
  %3196 = select i1 %3195, i32 1, i32 -1		; visa id: 3083
  %3197 = sitofp i32 %3196 to float		; visa id: 3084
  %3198 = fmul float %3193, %3197		; visa id: 3085
  br label %3199, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3086

3199:                                             ; preds = %3191, %3184
; BB378 :
  %.sroa.128.15 = phi float [ %3198, %3191 ], [ %3190, %3184 ]
  %3200 = lshr i32 %2567, 24		; visa id: 3087
  br i1 %2789, label %3208, label %3201, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3088

3201:                                             ; preds = %3199
; BB379 :
  %3202 = and i32 %146, 134217728
  %3203 = sub nsw i32 0, %3200, !spirv.Decorations !8798
  %3204 = icmp eq i32 %3202, 0		; visa id: 3090
  %3205 = select i1 %3204, i32 %3200, i32 %3203		; visa id: 3092
  %3206 = sitofp i32 %3205 to float		; visa id: 3093
  %3207 = fmul float %2785, %3206		; visa id: 3094
  br label %3216, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3095

3208:                                             ; preds = %3199
; BB380 :
  %3209 = uitofp i32 %3200 to float		; visa id: 3097
  %3210 = fmul float %2785, %3209		; visa id: 3098
  %3211 = and i32 %146, 134217728
  %3212 = icmp eq i32 %3211, 0		; visa id: 3099
  %3213 = select i1 %3212, i32 1, i32 -1		; visa id: 3101
  %3214 = sitofp i32 %3213 to float		; visa id: 3102
  %3215 = fmul float %3210, %3214		; visa id: 3103
  br label %3216, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3104

3216:                                             ; preds = %3208, %3201
; BB381 :
  %.sroa.176.15 = phi float [ %3215, %3208 ], [ %3207, %3201 ]
  %3217 = and i32 %2568, 255		; visa id: 3105
  br i1 %2789, label %3225, label %3218, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3106

3218:                                             ; preds = %3216
; BB382 :
  %3219 = and i32 %146, 268435456
  %3220 = sub nsw i32 0, %3217, !spirv.Decorations !8798
  %3221 = icmp eq i32 %3219, 0		; visa id: 3108
  %3222 = select i1 %3221, i32 %3217, i32 %3220		; visa id: 3110
  %3223 = sitofp i32 %3222 to float		; visa id: 3111
  %3224 = fmul float %2785, %3223		; visa id: 3112
  br label %3233, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3113

3225:                                             ; preds = %3216
; BB383 :
  %3226 = uitofp i32 %3217 to float		; visa id: 3115
  %3227 = fmul float %2785, %3226		; visa id: 3116
  %3228 = and i32 %146, 268435456
  %3229 = icmp eq i32 %3228, 0		; visa id: 3117
  %3230 = select i1 %3229, i32 1, i32 -1		; visa id: 3119
  %3231 = sitofp i32 %3230 to float		; visa id: 3120
  %3232 = fmul float %3227, %3231		; visa id: 3121
  br label %3233, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3122

3233:                                             ; preds = %3225, %3218
; BB384 :
  %.sroa.224.15 = phi float [ %3232, %3225 ], [ %3224, %3218 ]
  %3234 = bitcast i32 %2568 to <4 x i8>
  %3235 = extractelement <4 x i8> %3234, i32 1
  %3236 = zext i8 %3235 to i32		; visa id: 3123
  br i1 %2789, label %3244, label %3237, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3124

3237:                                             ; preds = %3233
; BB385 :
  %3238 = and i32 %146, 536870912
  %3239 = sub nsw i32 0, %3236, !spirv.Decorations !8798
  %3240 = icmp eq i32 %3238, 0		; visa id: 3126
  %3241 = select i1 %3240, i32 %3236, i32 %3239		; visa id: 3128
  %3242 = sitofp i32 %3241 to float		; visa id: 3129
  %3243 = fmul float %2785, %3242		; visa id: 3130
  br label %3252, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3131

3244:                                             ; preds = %3233
; BB386 :
  %3245 = uitofp i32 %3236 to float		; visa id: 3133
  %3246 = fmul float %2785, %3245		; visa id: 3134
  %3247 = and i32 %146, 536870912
  %3248 = icmp eq i32 %3247, 0		; visa id: 3135
  %3249 = select i1 %3248, i32 1, i32 -1		; visa id: 3137
  %3250 = sitofp i32 %3249 to float		; visa id: 3138
  %3251 = fmul float %3246, %3250		; visa id: 3139
  br label %3252, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3140

3252:                                             ; preds = %3244, %3237
; BB387 :
  %.sroa.272.15 = phi float [ %3251, %3244 ], [ %3243, %3237 ]
  %3253 = extractelement <4 x i8> %3234, i32 2
  %3254 = zext i8 %3253 to i32		; visa id: 3141
  br i1 %2789, label %3262, label %3255, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3142

3255:                                             ; preds = %3252
; BB388 :
  %3256 = and i32 %146, 1073741824
  %3257 = sub nsw i32 0, %3254, !spirv.Decorations !8798
  %3258 = icmp eq i32 %3256, 0		; visa id: 3144
  %3259 = select i1 %3258, i32 %3254, i32 %3257		; visa id: 3146
  %3260 = sitofp i32 %3259 to float		; visa id: 3147
  %3261 = fmul float %2785, %3260		; visa id: 3148
  br label %3270, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3149

3262:                                             ; preds = %3252
; BB389 :
  %3263 = uitofp i32 %3254 to float		; visa id: 3151
  %3264 = fmul float %2785, %3263		; visa id: 3152
  %3265 = and i32 %146, 1073741824
  %3266 = icmp eq i32 %3265, 0		; visa id: 3153
  %3267 = select i1 %3266, i32 1, i32 -1		; visa id: 3155
  %3268 = sitofp i32 %3267 to float		; visa id: 3156
  %3269 = fmul float %3264, %3268		; visa id: 3157
  br label %3270, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3158

3270:                                             ; preds = %3262, %3255
; BB390 :
  %.sroa.320.15 = phi float [ %3269, %3262 ], [ %3261, %3255 ]
  %3271 = lshr i32 %2568, 24		; visa id: 3159
  br i1 %2789, label %3278, label %3272, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3160

3272:                                             ; preds = %3270
; BB391 :
  %3273 = sub nsw i32 0, %3271, !spirv.Decorations !8798
  %3274 = icmp slt i32 %146, 0		; visa id: 3162
  %3275 = select i1 %3274, i32 %3273, i32 %3271		; visa id: 3163
  %3276 = sitofp i32 %3275 to float		; visa id: 3164
  %3277 = fmul float %2785, %3276		; visa id: 3165
  br label %3285, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3166

3278:                                             ; preds = %3270
; BB392 :
  %3279 = uitofp i32 %3271 to float		; visa id: 3168
  %3280 = fmul float %2785, %3279		; visa id: 3169
  %3281 = icmp sgt i32 %146, -1		; visa id: 3170
  %3282 = select i1 %3281, i32 1, i32 -1		; visa id: 3171
  %3283 = sitofp i32 %3282 to float		; visa id: 3172
  %3284 = fmul float %3280, %3283		; visa id: 3173
  br label %3285, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3174

3285:                                             ; preds = %3278, %3272
; BB393 :
  %.sroa.368.15 = phi float [ %3284, %3278 ], [ %3277, %3272 ]
  %3286 = fmul float %.sroa.062.15, %3108		; visa id: 3175
  %3287 = fadd float %.sroa.35.0, %3286		; visa id: 3176
  %3288 = fmul float %.sroa.80.15, %3113		; visa id: 3177
  %3289 = fadd float %3287, %3288		; visa id: 3178
  %3290 = fmul float %.sroa.128.15, %3118		; visa id: 3179
  %3291 = fadd float %3289, %3290		; visa id: 3180
  %3292 = fmul float %.sroa.176.15, %3123		; visa id: 3181
  %3293 = fadd float %3291, %3292		; visa id: 3182
  %3294 = fmul float %.sroa.224.15, %3128		; visa id: 3183
  %3295 = fadd float %3293, %3294		; visa id: 3184
  %3296 = fmul float %.sroa.272.15, %3133		; visa id: 3185
  %3297 = fadd float %3295, %3296		; visa id: 3186
  %3298 = fmul float %.sroa.320.15, %3138		; visa id: 3187
  %3299 = fadd float %3297, %3298		; visa id: 3188
  %3300 = fmul float %.sroa.368.15, %3143		; visa id: 3189
  %3301 = fadd float %3299, %3300		; visa id: 3190
  %3302 = icmp ult i32 %114, 9		; visa id: 3191
  br i1 %3302, label %.._crit_edge43_crit_edge, label %.preheader, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3192

.._crit_edge43_crit_edge:                         ; preds = %3285
; BB394 :
  %3303 = add nuw nsw i32 %114, 1, !spirv.Decorations !8791		; visa id: 3194
  br label %._crit_edge43, !stats.blockFrequency.digits !8799, !stats.blockFrequency.scale !8797		; visa id: 3195

.preheader:                                       ; preds = %3285
; BB395 :
  %.lcssa665 = phi float [ %3301, %3285 ]
  %.lcssa664 = phi float [ %3145, %3285 ]
  %.lcssa663 = phi float [ %2947, %3285 ]
  %.lcssa662 = phi float [ %2780, %3285 ]
  %.lcssa661 = phi float [ %2520, %3285 ]
  %.lcssa660 = phi float [ %2365, %3285 ]
  %.lcssa659 = phi float [ %2167, %3285 ]
  %.lcssa658 = phi float [ %1999, %3285 ]
  %.lcssa657 = phi float [ %1738, %3285 ]
  %.lcssa656 = phi float [ %1583, %3285 ]
  %.lcssa655 = phi float [ %1385, %3285 ]
  %.lcssa654 = phi float [ %1218, %3285 ]
  %.lcssa653 = phi float [ %958, %3285 ]
  %.lcssa652 = phi float [ %803, %3285 ]
  %.lcssa651 = phi float [ %605, %3285 ]
  %.lcssa = phi float [ %427, %3285 ]
  %3304 = fadd float %.lcssa, %.lcssa652		; visa id: 3197
  %3305 = fadd float %.lcssa654, %.lcssa656		; visa id: 3198
  %3306 = fadd float %.lcssa658, %.lcssa660		; visa id: 3199
  %3307 = fadd float %.lcssa662, %.lcssa664		; visa id: 3200
  %3308 = fadd float %3304, %3305		; visa id: 3201
  %3309 = fadd float %3306, %3307		; visa id: 3202
  %3310 = fadd float %3308, %3309		; visa id: 3203
  %3311 = fadd float %.lcssa651, %.lcssa653		; visa id: 3204
  %3312 = fadd float %.lcssa655, %.lcssa657		; visa id: 3205
  %3313 = fadd float %.lcssa659, %.lcssa661		; visa id: 3206
  %3314 = fadd float %.lcssa663, %.lcssa665		; visa id: 3207
  %3315 = fadd float %3311, %3312		; visa id: 3208
  %3316 = fadd float %3313, %3314		; visa id: 3209
  %3317 = fadd float %3315, %3316		; visa id: 3210
  br label %._crit_edge41, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8790		; visa id: 3213

._crit_edge:                                      ; preds = %precompiled_u32divrem_sp.exit
; BB396 :
  %.pre483 = zext i32 %retval.0.i to i64		; visa id: 3215
  br label %._crit_edge41, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 3220

._crit_edge41:                                    ; preds = %.._crit_edge41_crit_edge, %._crit_edge, %._crit_edge42, %.preheader
; BB397 :
  %.pre-phi = phi i64 [ %33, %._crit_edge42 ], [ %33, %.preheader ], [ %.pre483, %._crit_edge ], [ %33, %.._crit_edge41_crit_edge ]
  %.sroa.7.0 = phi float [ 0.000000e+00, %._crit_edge42 ], [ %3317, %.preheader ], [ 0.000000e+00, %._crit_edge ], [ 0.000000e+00, %.._crit_edge41_crit_edge ]
  %.sroa.061.0 = phi float [ 0.000000e+00, %._crit_edge42 ], [ %3310, %.preheader ], [ 0.000000e+00, %._crit_edge ], [ 0.000000e+00, %.._crit_edge41_crit_edge ]
  %3318 = phi i32 [ 0, %._crit_edge42 ], [ -1, %.preheader ], [ 0, %._crit_edge ], [ 0, %.._crit_edge41_crit_edge ]
  %3319 = phi i32 [ %62, %._crit_edge42 ], [ 0, %.preheader ], [ -1, %._crit_edge ], [ -1, %.._crit_edge41_crit_edge ]
  %3320 = icmp ne i32 %3318, 0		; visa id: 3221
  %3321 = icmp ne i32 %6, 0		; visa id: 3222
  %3322 = or i1 %30, %3321		; visa id: 3223
  %3323 = zext i32 %13 to i64		; visa id: 3225
  %3324 = icmp eq i32 %13, %29		; visa id: 3226
  %3325 = icmp ne i32 %3319, 0		; visa id: 3227
  %3326 = sext i1 %3325 to i32		; visa id: 3228
  %3327 = sub i32 0, %3326		; visa id: 3229
  %3328 = addrspacecast ptr addrspace(4) %4 to ptr addrspace(1)		; visa id: 3230
  %3329 = addrspacecast ptr addrspace(4) %5 to ptr addrspace(1)		; visa id: 3231
  %3330 = add nuw nsw i32 %simdLaneId, 1		; visa id: 3232
  %3331 = and i32 %3330, 31		; visa id: 3233
  %simdShuffle = call float @llvm.genx.GenISA.WaveShuffleIndex.f32(float %.sroa.061.0, i32 %3331, i32 0)		; visa id: 3234
  %3332 = and i32 %simdLaneId, 1
  %3333 = icmp eq i32 %3332, 0		; visa id: 3241
  %3334 = select i1 %3333, float %simdShuffle, float -0.000000e+00		; visa id: 3243
  %3335 = fadd float %.sroa.061.0, %3334		; visa id: 3244
  %3336 = add nuw nsw i32 %simdLaneId, 2		; visa id: 3245
  %3337 = and i32 %3336, 31		; visa id: 3246
  %simdShuffle.1 = call float @llvm.genx.GenISA.WaveShuffleIndex.f32(float %3335, i32 %3337, i32 0)		; visa id: 3247
  %3338 = icmp eq i32 %6, 0		; visa id: 3254
  br i1 %3322, label %._crit_edge41.._crit_edge45_crit_edge, label %3339, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8782		; visa id: 3255

._crit_edge41.._crit_edge45_crit_edge:            ; preds = %._crit_edge41
; BB:
  br label %._crit_edge45, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787

3339:                                             ; preds = %._crit_edge41
; BB399 :
  %3340 = select i1 %3338, float %simdShuffle.1, float -0.000000e+00		; visa id: 3257
  %3341 = fadd float %3335, %3340		; visa id: 3258
  %3342 = bitcast float %3341 to i32
  %3343 = select i1 %3320, i32 %3342, i32 2143289344		; visa id: 3259
  %3344 = and i32 %3343, 2147483647		; visa id: 3260
  %3345 = icmp ugt i32 %3344, 2139095040		; visa id: 3261
  br i1 %3345, label %3353, label %3346, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 3262

3346:                                             ; preds = %3339
; BB400 :
  %3347 = lshr i32 %3343, 16		; visa id: 3264
  %3348 = and i32 %3347, 1		; visa id: 3265
  %3349 = add i32 %3343, %3348
  %3350 = add i32 %3349, 32767		; visa id: 3266
  %3351 = lshr i32 %3350, 16		; visa id: 3267
  %3352 = trunc i32 %3351 to i16		; visa id: 3268
  br label %3357, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 3269

3353:                                             ; preds = %3339
; BB401 :
  %3354 = lshr i32 %3343, 16		; visa id: 3271
  %3355 = trunc i32 %3354 to i16		; visa id: 3272
  %3356 = or i16 %3355, 64		; visa id: 3273
  br label %3357, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 3274

3357:                                             ; preds = %3346, %3353
; BB402 :
  %3358 = phi i16 [ %3356, %3353 ], [ %3352, %3346 ]
  %3359 = shl nuw nsw i64 %3323, 1		; visa id: 3275
  %3360 = add i64 %3359, %const_reg_qword12		; visa id: 3276
  %3361 = inttoptr i64 %3360 to ptr addrspace(4)		; visa id: 3277
  %3362 = addrspacecast ptr addrspace(4) %3361 to ptr addrspace(1)		; visa id: 3277
  store i16 %3358, ptr addrspace(1) %3362, align 2		; visa id: 3278
  br i1 %3324, label %3363, label %.._crit_edge45_crit_edge, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 3280

.._crit_edge45_crit_edge:                         ; preds = %3357
; BB:
  br label %._crit_edge45, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784

3363:                                             ; preds = %3357
; BB404 :
  %3364 = shl nuw nsw i64 %.pre-phi, 2		; visa id: 3282
  %3365 = add i64 %3364, %const_reg_qword17		; visa id: 3283
  %3366 = inttoptr i64 %3365 to ptr addrspace(4)		; visa id: 3284
  %3367 = addrspacecast ptr addrspace(4) %3366 to ptr addrspace(1)		; visa id: 3284
  store i32 %3327, ptr addrspace(1) %3367, align 4		; visa id: 3285
  br i1 %3325, label %3368, label %.._crit_edge45_crit_edge578, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 3286

.._crit_edge45_crit_edge578:                      ; preds = %3363
; BB:
  br label %._crit_edge45, !stats.blockFrequency.digits !8800, !stats.blockFrequency.scale !8801

3368:                                             ; preds = %3363
; BB406 :
  %3369 = load i32, ptr addrspace(1) %3329, align 4		; visa id: 3288
  %3370 = icmp eq i32 %3369, 0		; visa id: 3289
  br i1 %3370, label %.._crit_edge45_crit_edge579, label %3371, !stats.blockFrequency.digits !8802, !stats.blockFrequency.scale !8803		; visa id: 3290

.._crit_edge45_crit_edge579:                      ; preds = %3368
; BB:
  br label %._crit_edge45, !stats.blockFrequency.digits !8804, !stats.blockFrequency.scale !8801

3371:                                             ; preds = %3368
; BB408 :
  %3372 = call i32 @llvm.genx.GenISA.icmpxchgatomicrawA64.i32.p1.p1(ptr addrspace(1) %3328, ptr addrspace(1) %3328, i32 0, i32 1)		; visa id: 3292
  br label %._crit_edge45, !stats.blockFrequency.digits !8805, !stats.blockFrequency.scale !8801		; visa id: 3297

._crit_edge45:                                    ; preds = %.._crit_edge45_crit_edge579, %.._crit_edge45_crit_edge578, %.._crit_edge45_crit_edge, %._crit_edge41.._crit_edge45_crit_edge, %3371
; BB409 :
  %simdShuffle.152 = call float @llvm.genx.GenISA.WaveShuffleIndex.f32(float %.sroa.7.0, i32 %3331, i32 0)		; visa id: 3298
  %3373 = select i1 %3333, float %simdShuffle.152, float -0.000000e+00		; visa id: 3305
  %3374 = fadd float %.sroa.7.0, %3373		; visa id: 3306
  %simdShuffle.1.1 = call float @llvm.genx.GenISA.WaveShuffleIndex.f32(float %3374, i32 %3337, i32 0)		; visa id: 3307
  br i1 %3322, label %._crit_edge45.._crit_edge46.1_crit_edge, label %3375, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8782		; visa id: 3314

._crit_edge45.._crit_edge46.1_crit_edge:          ; preds = %._crit_edge45
; BB:
  br label %._crit_edge46.1, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787

3375:                                             ; preds = %._crit_edge45
; BB411 :
  %3376 = select i1 %3338, float %simdShuffle.1.1, float -0.000000e+00		; visa id: 3316
  %3377 = fadd float %3374, %3376		; visa id: 3317
  %3378 = bitcast float %3377 to i32
  %3379 = select i1 %3320, i32 %3378, i32 2143289344		; visa id: 3318
  %3380 = and i32 %3379, 2147483647		; visa id: 3319
  %3381 = icmp ugt i32 %3380, 2139095040		; visa id: 3320
  br i1 %3381, label %3389, label %3382, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 3321

3382:                                             ; preds = %3375
; BB412 :
  %3383 = lshr i32 %3379, 16		; visa id: 3323
  %3384 = and i32 %3383, 1		; visa id: 3324
  %3385 = add i32 %3379, %3384
  %3386 = add i32 %3385, 32767		; visa id: 3325
  %3387 = lshr i32 %3386, 16		; visa id: 3326
  %3388 = trunc i32 %3387 to i16		; visa id: 3327
  br label %3393, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 3328

3389:                                             ; preds = %3375
; BB413 :
  %3390 = lshr i32 %3379, 16		; visa id: 3330
  %3391 = trunc i32 %3390 to i16		; visa id: 3331
  %3392 = or i16 %3391, 64		; visa id: 3332
  br label %3393, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 3333

3393:                                             ; preds = %3389, %3382
; BB414 :
  %3394 = phi i16 [ %3392, %3389 ], [ %3388, %3382 ]
  %3395 = shl nuw nsw i64 %3323, 1		; visa id: 3334
  %3396 = add i64 %3395, %const_reg_qword13		; visa id: 3335
  %3397 = inttoptr i64 %3396 to ptr addrspace(4)		; visa id: 3336
  %3398 = addrspacecast ptr addrspace(4) %3397 to ptr addrspace(1)		; visa id: 3336
  store i16 %3394, ptr addrspace(1) %3398, align 2		; visa id: 3337
  br i1 %3324, label %3399, label %.._crit_edge46.1_crit_edge, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 3339

.._crit_edge46.1_crit_edge:                       ; preds = %3393
; BB:
  br label %._crit_edge46.1, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784

3399:                                             ; preds = %3393
; BB416 :
  %3400 = shl nuw nsw i64 %.pre-phi, 2		; visa id: 3341
  %3401 = add i64 %3400, %const_reg_qword18		; visa id: 3342
  %3402 = inttoptr i64 %3401 to ptr addrspace(4)		; visa id: 3343
  %3403 = addrspacecast ptr addrspace(4) %3402 to ptr addrspace(1)		; visa id: 3343
  store i32 %3327, ptr addrspace(1) %3403, align 4		; visa id: 3344
  br i1 %3325, label %3404, label %.._crit_edge46.1_crit_edge580, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 3345

.._crit_edge46.1_crit_edge580:                    ; preds = %3399
; BB:
  br label %._crit_edge46.1, !stats.blockFrequency.digits !8800, !stats.blockFrequency.scale !8801

3404:                                             ; preds = %3399
; BB418 :
  %3405 = load i32, ptr addrspace(1) %3329, align 4		; visa id: 3347
  %3406 = icmp eq i32 %3405, 0		; visa id: 3348
  br i1 %3406, label %.._crit_edge46.1_crit_edge581, label %3407, !stats.blockFrequency.digits !8802, !stats.blockFrequency.scale !8803		; visa id: 3349

.._crit_edge46.1_crit_edge581:                    ; preds = %3404
; BB:
  br label %._crit_edge46.1, !stats.blockFrequency.digits !8804, !stats.blockFrequency.scale !8801

3407:                                             ; preds = %3404
; BB420 :
  %3408 = call i32 @llvm.genx.GenISA.icmpxchgatomicrawA64.i32.p1.p1(ptr addrspace(1) %3328, ptr addrspace(1) %3328, i32 0, i32 1)		; visa id: 3351
  br label %._crit_edge46.1, !stats.blockFrequency.digits !8805, !stats.blockFrequency.scale !8801		; visa id: 3356

._crit_edge46.1:                                  ; preds = %.._crit_edge46.1_crit_edge581, %.._crit_edge46.1_crit_edge580, %.._crit_edge46.1_crit_edge, %._crit_edge45.._crit_edge46.1_crit_edge, %3407
; BB421 :
  ret void, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8782		; visa id: 3357
}
