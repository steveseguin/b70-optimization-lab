; ------------------------------------------------
; OCL_asm6c8399b4fe53f40f_simd32_entry_0007.visa.ll
; ------------------------------------------------
; Function Attrs: convergent nounwind
define spir_kernel void @_ZTSZZNK4p1026KernelILj4ELb1EE6submitERN4sycl3_V15queueESt4spanIKPvLm18446744073709551615EERKSt6vectorINS3_5eventESaISB_EEENKUlRNS3_7handlerEE_clESH_EUlNS3_7nd_itemILi1EEEE_(ptr byval(%"struct.p39::__generated_Bound") align 8 %0, i32 %1, <8 x i32> %r0, <3 x i32> %globalOffset, i16 %localIdX, i16 %localIdY, i16 %localIdZ, ptr addrspace(2) %constBase, ptr addrspace(1) %globalBase, ptr %privateBase, i64 %const_reg_qword, i64 %const_reg_qword1, i64 %const_reg_qword2, i64 %const_reg_qword3, i64 %const_reg_qword4, i64 %const_reg_qword5, i64 %const_reg_qword6, i64 %const_reg_qword7, i64 %const_reg_qword8, i64 %const_reg_qword9, i64 %const_reg_qword10, i64 %const_reg_qword11, i64 %const_reg_qword12, i64 %const_reg_qword13, i64 %const_reg_qword14, i64 %const_reg_qword15, i64 %const_reg_qword16, i64 %const_reg_qword17, i64 %const_reg_qword18, i64 %const_reg_qword19, i64 %const_reg_qword20, i32 %const_reg_dword, i32 %const_reg_dword21, i32 %const_reg_dword22, i32 %const_reg_dword23, i32 %const_reg_dword24, i32 %bindlessOffset, i32 %bindlessOffset25) #0 {
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
  br i1 %48, label %.._crit_edge43_crit_edge, label %49, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 67

.._crit_edge43_crit_edge:                         ; preds = %32
; BB5 :
  br label %._crit_edge43, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 73

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
  br i1 %60, label %63, label %._crit_edge44, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 85

._crit_edge44:                                    ; preds = %49
; BB7 :
  %61 = xor i1 %58, true		; visa id: 87
  %62 = sext i1 %61 to i32		; visa id: 88
  br label %._crit_edge43, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8790		; visa id: 92

63:                                               ; preds = %49
; BB8 :
  %64 = ptrtoint ptr addrspace(2) %constBase to i64		; visa id: 94
  %65 = add i64 %64, 372
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
  br label %._crit_edge45, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8790		; visa id: 151

._crit_edge45:                                    ; preds = %.preheader.3.1.._crit_edge45_crit_edge, %63
; BB9 :
  %.sroa.35.0 = phi float [ %101, %63 ], [ %3296, %.preheader.3.1.._crit_edge45_crit_edge ]
  %.sroa.33.0 = phi float [ %100, %63 ], [ %2943, %.preheader.3.1.._crit_edge45_crit_edge ]
  %.sroa.31.0 = phi float [ %99, %63 ], [ %2565, %.preheader.3.1.._crit_edge45_crit_edge ]
  %.sroa.29.0 = phi float [ %98, %63 ], [ %2212, %.preheader.3.1.._crit_edge45_crit_edge ]
  %.sroa.27.0 = phi float [ %97, %63 ], [ %1736, %.preheader.3.1.._crit_edge45_crit_edge ]
  %.sroa.25.0 = phi float [ %96, %63 ], [ %1383, %.preheader.3.1.._crit_edge45_crit_edge ]
  %.sroa.23.0 = phi float [ %95, %63 ], [ %1005, %.preheader.3.1.._crit_edge45_crit_edge ]
  %.sroa.20.0 = phi float [ %94, %63 ], [ %652, %.preheader.3.1.._crit_edge45_crit_edge ]
  %.sroa.18.0 = phi float [ %93, %63 ], [ %3141, %.preheader.3.1.._crit_edge45_crit_edge ]
  %.sroa.16.0 = phi float [ %92, %63 ], [ %2777, %.preheader.3.1.._crit_edge45_crit_edge ]
  %.sroa.14.0 = phi float [ %91, %63 ], [ %2410, %.preheader.3.1.._crit_edge45_crit_edge ]
  %.sroa.12.0 = phi float [ %90, %63 ], [ %2045, %.preheader.3.1.._crit_edge45_crit_edge ]
  %.sroa.10.0 = phi float [ %89, %63 ], [ %1581, %.preheader.3.1.._crit_edge45_crit_edge ]
  %.sroa.8.0 = phi float [ %88, %63 ], [ %1217, %.preheader.3.1.._crit_edge45_crit_edge ]
  %.sroa.6.0 = phi float [ %87, %63 ], [ %850, %.preheader.3.1.._crit_edge45_crit_edge ]
  %.sroa.0.0 = phi float [ %86, %63 ], [ %475, %.preheader.3.1.._crit_edge45_crit_edge ]
  %114 = phi i32 [ 0, %63 ], [ %3298, %.preheader.3.1.._crit_edge45_crit_edge ]
  %115 = shl nuw nsw i32 %114, 6, !spirv.Decorations !8791		; visa id: 152
  %116 = shl nuw nsw i32 %114, 3, !spirv.Decorations !8791		; visa id: 153
  %117 = shl nuw nsw i32 %114, 2, !spirv.Decorations !8791		; visa id: 154
  %118 = zext i32 %115 to i64		; visa id: 155
  %sink_646 = shl nuw nsw i32 %6, 4, !spirv.Decorations !8791		; visa id: 156
  %sink_645 = zext i32 %sink_646 to i64		; visa id: 157
  %sink_644 = add i64 %103, %sink_645		; visa id: 158
  %119 = add i64 %sink_644, %118		; visa id: 159
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
  %sink_641 = add i64 %103, 800		; visa id: 172
  %136 = add i64 %sink_641, %135		; visa id: 173
  %137 = inttoptr i64 %136 to ptr addrspace(4)		; visa id: 174
  %138 = addrspacecast ptr addrspace(4) %137 to ptr addrspace(1)		; visa id: 174
  %139 = load float, ptr addrspace(1) %138, align 4, !noalias !8793		; visa id: 175
  %sink_643 = add i64 %106, %sink_645		; visa id: 176
  %140 = add i64 %sink_643, %118		; visa id: 177
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
  %sink_640 = add i64 %106, 800		; visa id: 188
  %155 = add i64 %sink_640, %135		; visa id: 189
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
  %sink_642 = shl nuw nsw i32 %6, 6, !spirv.Decorations !8791		; visa id: 201
  %170 = or i32 %169, %sink_642		; visa id: 202
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
  %184 = and i32 %123, 255
  %185 = shl nuw nsw i32 %160, 4		; visa id: 210
  %186 = and i32 %185, 768		; visa id: 211
  %187 = or i32 %184, %186		; visa id: 212
  %188 = shl nuw nsw i32 %187, 3, !spirv.Decorations !8791		; visa id: 213
  %189 = zext i32 %188 to i64		; visa id: 214
  %190 = add i64 %sink_, %189		; visa id: 215
  %191 = inttoptr i64 %190 to ptr addrspace(1)		; visa id: 216
  %192 = load <2 x i32>, ptr addrspace(1) %191, align 4		; visa id: 216
  %193 = extractelement <2 x i32> %183, i32 0		; visa id: 217
  %194 = extractelement <2 x i32> %183, i32 1		; visa id: 217
  %195 = extractelement <2 x i32> %192, i32 0		; visa id: 217
  %196 = extractelement <2 x i32> %192, i32 1		; visa id: 217
  %197 = bitcast i32 %123 to <4 x i8>
  %198 = extractelement <4 x i8> %197, i32 2
  %199 = shl nuw nsw i32 %160, 2		; visa id: 217
  %200 = and i32 %199, 768
  %201 = zext i8 %198 to i32		; visa id: 218
  %202 = or i32 %201, %200		; visa id: 219
  %203 = shl nuw nsw i32 %202, 3, !spirv.Decorations !8791		; visa id: 220
  %204 = zext i32 %203 to i64		; visa id: 221
  %205 = add i64 %sink_, %204		; visa id: 222
  %206 = inttoptr i64 %205 to ptr addrspace(1)		; visa id: 223
  %207 = load <2 x i32>, ptr addrspace(1) %206, align 4		; visa id: 223
  %208 = and i32 %143, 255
  %209 = zext i16 %150 to i32		; visa id: 224
  %210 = shl nuw nsw i32 %209, 8, !spirv.Decorations !8791		; visa id: 225
  %211 = and i32 %210, 768		; visa id: 226
  %212 = or i32 %208, %211		; visa id: 227
  %213 = shl nuw nsw i32 %212, 3, !spirv.Decorations !8791		; visa id: 228
  %214 = zext i32 %213 to i64		; visa id: 229
  %215 = add i64 %sink_, %214		; visa id: 230
  %216 = inttoptr i64 %215 to ptr addrspace(1)		; visa id: 231
  %217 = load <2 x i32>, ptr addrspace(1) %216, align 4		; visa id: 231
  %218 = extractelement <2 x i32> %207, i32 0		; visa id: 232
  %219 = extractelement <2 x i32> %207, i32 1		; visa id: 232
  %220 = extractelement <2 x i32> %217, i32 0		; visa id: 232
  %221 = extractelement <2 x i32> %217, i32 1		; visa id: 232
  %222 = bitcast i32 %143 to <4 x i8>
  %223 = extractelement <4 x i8> %222, i32 2
  %224 = shl nuw nsw i32 %209, 6		; visa id: 232
  %225 = and i32 %224, 768
  %226 = zext i8 %223 to i32		; visa id: 233
  %227 = or i32 %226, %225		; visa id: 234
  %228 = shl nuw nsw i32 %227, 3, !spirv.Decorations !8791		; visa id: 235
  %229 = zext i32 %228 to i64		; visa id: 236
  %230 = add i64 %sink_, %229		; visa id: 237
  %231 = inttoptr i64 %230 to ptr addrspace(1)		; visa id: 238
  %232 = load <2 x i32>, ptr addrspace(1) %231, align 4		; visa id: 238
  %233 = and i32 %144, 255
  %234 = shl nuw nsw i32 %209, 4		; visa id: 239
  %235 = and i32 %234, 768		; visa id: 240
  %236 = or i32 %233, %235		; visa id: 241
  %237 = shl nuw nsw i32 %236, 3, !spirv.Decorations !8791		; visa id: 242
  %238 = zext i32 %237 to i64		; visa id: 243
  %239 = add i64 %sink_, %238		; visa id: 244
  %240 = inttoptr i64 %239 to ptr addrspace(1)		; visa id: 245
  %241 = load <2 x i32>, ptr addrspace(1) %240, align 4		; visa id: 245
  %242 = extractelement <2 x i32> %232, i32 0		; visa id: 246
  %243 = extractelement <2 x i32> %232, i32 1		; visa id: 246
  %244 = extractelement <2 x i32> %241, i32 0		; visa id: 246
  %245 = extractelement <2 x i32> %241, i32 1		; visa id: 246
  %246 = bitcast i32 %144 to <4 x i8>
  %247 = extractelement <4 x i8> %246, i32 2
  %248 = shl nuw nsw i32 %209, 2		; visa id: 246
  %249 = and i32 %248, 768
  %250 = zext i8 %247 to i32		; visa id: 247
  %251 = or i32 %250, %249		; visa id: 248
  %252 = shl nuw nsw i32 %251, 3, !spirv.Decorations !8791		; visa id: 249
  %253 = zext i32 %252 to i64		; visa id: 250
  %254 = add i64 %sink_, %253		; visa id: 251
  %255 = inttoptr i64 %254 to ptr addrspace(1)		; visa id: 252
  %256 = load <2 x i32>, ptr addrspace(1) %255, align 4		; visa id: 252
  %257 = shl nuw i32 %170, 1		; visa id: 253
  %258 = zext i32 %257 to i64		; visa id: 254
  %259 = add i64 %258, %const_reg_qword2		; visa id: 255
  %IntToPtr2 = inttoptr i64 %259 to ptr addrspace(1)		; visa id: 256
  %vCastload = load i32, ptr addrspace(1) %IntToPtr2, align 2		; visa id: 256
  %260 = add i64 %259, 4
  %IntToPtr2578 = inttoptr i64 %260 to ptr addrspace(1)
  %vCastload579 = load i32, ptr addrspace(1) %IntToPtr2578, align 2		; visa id: 257
  %261 = extractelement <2 x i32> %256, i32 0		; visa id: 258
  %262 = extractelement <2 x i32> %256, i32 1		; visa id: 258
  %263 = bitcast i32 %vCastload to <2 x i16>		; visa id: 258
  %264 = bitcast i32 %vCastload579 to <2 x i16>		; visa id: 260
  %265 = extractelement <2 x i16> %263, i32 0		; visa id: 262
  %266 = extractelement <2 x i16> %263, i32 1		; visa id: 262
  %267 = extractelement <2 x i16> %264, i32 0		; visa id: 262
  %268 = extractelement <2 x i16> %264, i32 1		; visa id: 262
  %269 = add i64 %259, 8
  %IntToPtr2580 = inttoptr i64 %269 to ptr addrspace(1)
  %vCastload581 = load i32, ptr addrspace(1) %IntToPtr2580, align 2		; visa id: 262
  %270 = add i64 %259, 12
  %IntToPtr2582 = inttoptr i64 %270 to ptr addrspace(1)
  %vCastload583 = load i32, ptr addrspace(1) %IntToPtr2582, align 2		; visa id: 263
  %271 = bitcast i32 %vCastload581 to <2 x i16>		; visa id: 264
  %272 = bitcast i32 %vCastload583 to <2 x i16>		; visa id: 266
  %273 = extractelement <2 x i16> %271, i32 0		; visa id: 268
  %274 = extractelement <2 x i16> %271, i32 1		; visa id: 268
  %275 = extractelement <2 x i16> %272, i32 0		; visa id: 268
  %276 = extractelement <2 x i16> %272, i32 1		; visa id: 268
  %277 = and i16 %134, 255		; visa id: 268
  %278 = zext i16 %277 to i32		; visa id: 269
  %279 = and i32 %278, 15		; visa id: 270
  %280 = uitofp i32 %279 to float		; visa id: 271
  %281 = fadd float %280, 5.000000e-01		; visa id: 272
  %282 = fmul float %139, %281		; visa id: 273
  %283 = fmul float %282, 2.500000e-01		; visa id: 274
  %284 = bitcast float %139 to i32
  %285 = and i32 %284, 2147483647		; visa id: 275
  %286 = bitcast i32 %285 to float
  %287 = fcmp une float %286, %286
  %288 = fcmp oeq float %286, 0x7FF0000000000000		; visa id: 276
  %289 = or i1 %287, %288		; visa id: 277
  %290 = bitcast float %283 to i32
  %291 = and i32 %290, 2147483647		; visa id: 279
  %292 = icmp ugt i32 %291, 2139095040
  %293 = or i1 %289, %292		; visa id: 280
  %294 = and i32 %171, 255		; visa id: 282
  br i1 %293, label %302, label %295, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 283

295:                                              ; preds = %._crit_edge45
; BB10 :
  %296 = and i32 %122, 256
  %297 = sub nsw i32 0, %294, !spirv.Decorations !8798
  %298 = icmp eq i32 %296, 0		; visa id: 285
  %299 = select i1 %298, i32 %294, i32 %297		; visa id: 287
  %300 = sitofp i32 %299 to float		; visa id: 288
  %301 = fmul float %283, %300		; visa id: 289
  br label %310, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 290

302:                                              ; preds = %._crit_edge45
; BB11 :
  %303 = uitofp i32 %294 to float		; visa id: 292
  %304 = fmul float %283, %303		; visa id: 293
  %305 = and i32 %122, 256
  %306 = icmp eq i32 %305, 0		; visa id: 294
  %307 = select i1 %306, i32 1, i32 -1		; visa id: 296
  %308 = sitofp i32 %307 to float		; visa id: 297
  %309 = fmul float %304, %308		; visa id: 298
  br label %310, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 299

310:                                              ; preds = %295, %302
; BB12 :
  %.sroa.065.0 = phi float [ %309, %302 ], [ %301, %295 ]
  %311 = bitcast i32 %171 to <4 x i8>
  %312 = extractelement <4 x i8> %311, i32 1
  %313 = zext i8 %312 to i32		; visa id: 300
  br i1 %293, label %321, label %314, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 301

314:                                              ; preds = %310
; BB13 :
  %315 = and i32 %122, 512
  %316 = sub nsw i32 0, %313, !spirv.Decorations !8798
  %317 = icmp eq i32 %315, 0		; visa id: 303
  %318 = select i1 %317, i32 %313, i32 %316		; visa id: 305
  %319 = sitofp i32 %318 to float		; visa id: 306
  %320 = fmul float %283, %319		; visa id: 307
  br label %329, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 308

321:                                              ; preds = %310
; BB14 :
  %322 = uitofp i32 %313 to float		; visa id: 310
  %323 = fmul float %283, %322		; visa id: 311
  %324 = and i32 %122, 512
  %325 = icmp eq i32 %324, 0		; visa id: 312
  %326 = select i1 %325, i32 1, i32 -1		; visa id: 314
  %327 = sitofp i32 %326 to float		; visa id: 315
  %328 = fmul float %323, %327		; visa id: 316
  br label %329, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 317

329:                                              ; preds = %321, %314
; BB15 :
  %.sroa.80.0 = phi float [ %328, %321 ], [ %320, %314 ]
  %330 = extractelement <4 x i8> %311, i32 2
  %331 = zext i8 %330 to i32		; visa id: 318
  br i1 %293, label %339, label %332, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 319

332:                                              ; preds = %329
; BB16 :
  %333 = and i32 %122, 1024
  %334 = sub nsw i32 0, %331, !spirv.Decorations !8798
  %335 = icmp eq i32 %333, 0		; visa id: 321
  %336 = select i1 %335, i32 %331, i32 %334		; visa id: 323
  %337 = sitofp i32 %336 to float		; visa id: 324
  %338 = fmul float %283, %337		; visa id: 325
  br label %347, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 326

339:                                              ; preds = %329
; BB17 :
  %340 = uitofp i32 %331 to float		; visa id: 328
  %341 = fmul float %283, %340		; visa id: 329
  %342 = and i32 %122, 1024
  %343 = icmp eq i32 %342, 0		; visa id: 330
  %344 = select i1 %343, i32 1, i32 -1		; visa id: 332
  %345 = sitofp i32 %344 to float		; visa id: 333
  %346 = fmul float %341, %345		; visa id: 334
  br label %347, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 335

347:                                              ; preds = %339, %332
; BB18 :
  %.sroa.128.0 = phi float [ %346, %339 ], [ %338, %332 ]
  %348 = lshr i32 %171, 24		; visa id: 336
  br i1 %293, label %356, label %349, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 337

349:                                              ; preds = %347
; BB19 :
  %350 = and i32 %122, 2048
  %351 = sub nsw i32 0, %348, !spirv.Decorations !8798
  %352 = icmp eq i32 %350, 0		; visa id: 339
  %353 = select i1 %352, i32 %348, i32 %351		; visa id: 341
  %354 = sitofp i32 %353 to float		; visa id: 342
  %355 = fmul float %283, %354		; visa id: 343
  br label %364, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 344

356:                                              ; preds = %347
; BB20 :
  %357 = uitofp i32 %348 to float		; visa id: 346
  %358 = fmul float %283, %357		; visa id: 347
  %359 = and i32 %122, 2048
  %360 = icmp eq i32 %359, 0		; visa id: 348
  %361 = select i1 %360, i32 1, i32 -1		; visa id: 350
  %362 = sitofp i32 %361 to float		; visa id: 351
  %363 = fmul float %358, %362		; visa id: 352
  br label %364, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 353

364:                                              ; preds = %356, %349
; BB21 :
  %.sroa.176.0 = phi float [ %363, %356 ], [ %355, %349 ]
  %365 = and i32 %172, 255		; visa id: 354
  br i1 %293, label %373, label %366, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 355

366:                                              ; preds = %364
; BB22 :
  %367 = and i32 %122, 4096
  %368 = sub nsw i32 0, %365, !spirv.Decorations !8798
  %369 = icmp eq i32 %367, 0		; visa id: 357
  %370 = select i1 %369, i32 %365, i32 %368		; visa id: 359
  %371 = sitofp i32 %370 to float		; visa id: 360
  %372 = fmul float %283, %371		; visa id: 361
  br label %381, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 362

373:                                              ; preds = %364
; BB23 :
  %374 = uitofp i32 %365 to float		; visa id: 364
  %375 = fmul float %283, %374		; visa id: 365
  %376 = and i32 %122, 4096
  %377 = icmp eq i32 %376, 0		; visa id: 366
  %378 = select i1 %377, i32 1, i32 -1		; visa id: 368
  %379 = sitofp i32 %378 to float		; visa id: 369
  %380 = fmul float %375, %379		; visa id: 370
  br label %381, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 371

381:                                              ; preds = %373, %366
; BB24 :
  %.sroa.224.0 = phi float [ %380, %373 ], [ %372, %366 ]
  %382 = bitcast i32 %172 to <4 x i8>
  %383 = extractelement <4 x i8> %382, i32 1
  %384 = zext i8 %383 to i32		; visa id: 372
  br i1 %293, label %392, label %385, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 373

385:                                              ; preds = %381
; BB25 :
  %386 = and i32 %122, 8192
  %387 = sub nsw i32 0, %384, !spirv.Decorations !8798
  %388 = icmp eq i32 %386, 0		; visa id: 375
  %389 = select i1 %388, i32 %384, i32 %387		; visa id: 377
  %390 = sitofp i32 %389 to float		; visa id: 378
  %391 = fmul float %283, %390		; visa id: 379
  br label %400, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 380

392:                                              ; preds = %381
; BB26 :
  %393 = uitofp i32 %384 to float		; visa id: 382
  %394 = fmul float %283, %393		; visa id: 383
  %395 = and i32 %122, 8192
  %396 = icmp eq i32 %395, 0		; visa id: 384
  %397 = select i1 %396, i32 1, i32 -1		; visa id: 386
  %398 = sitofp i32 %397 to float		; visa id: 387
  %399 = fmul float %394, %398		; visa id: 388
  br label %400, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 389

400:                                              ; preds = %392, %385
; BB27 :
  %.sroa.272.0 = phi float [ %399, %392 ], [ %391, %385 ]
  %401 = extractelement <4 x i8> %382, i32 2
  %402 = zext i8 %401 to i32		; visa id: 390
  br i1 %293, label %410, label %403, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 391

403:                                              ; preds = %400
; BB28 :
  %404 = and i32 %122, 16384
  %405 = sub nsw i32 0, %402, !spirv.Decorations !8798
  %406 = icmp eq i32 %404, 0		; visa id: 393
  %407 = select i1 %406, i32 %402, i32 %405		; visa id: 395
  %408 = sitofp i32 %407 to float		; visa id: 396
  %409 = fmul float %283, %408		; visa id: 397
  br label %418, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 398

410:                                              ; preds = %400
; BB29 :
  %411 = uitofp i32 %402 to float		; visa id: 400
  %412 = fmul float %283, %411		; visa id: 401
  %413 = and i32 %122, 16384
  %414 = icmp eq i32 %413, 0		; visa id: 402
  %415 = select i1 %414, i32 1, i32 -1		; visa id: 404
  %416 = sitofp i32 %415 to float		; visa id: 405
  %417 = fmul float %412, %416		; visa id: 406
  br label %418, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 407

418:                                              ; preds = %410, %403
; BB30 :
  %.sroa.320.0 = phi float [ %417, %410 ], [ %409, %403 ]
  %419 = lshr i32 %172, 24		; visa id: 408
  br i1 %293, label %427, label %420, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 409

420:                                              ; preds = %418
; BB31 :
  %421 = and i32 %122, 32768
  %422 = sub nsw i32 0, %419, !spirv.Decorations !8798
  %423 = icmp eq i32 %421, 0		; visa id: 411
  %424 = select i1 %423, i32 %419, i32 %422		; visa id: 413
  %425 = sitofp i32 %424 to float		; visa id: 414
  %426 = fmul float %283, %425		; visa id: 415
  br label %435, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 416

427:                                              ; preds = %418
; BB32 :
  %428 = uitofp i32 %419 to float		; visa id: 418
  %429 = fmul float %283, %428		; visa id: 419
  %430 = and i32 %122, 32768
  %431 = icmp eq i32 %430, 0		; visa id: 420
  %432 = select i1 %431, i32 1, i32 -1		; visa id: 422
  %433 = sitofp i32 %432 to float		; visa id: 423
  %434 = fmul float %429, %433		; visa id: 424
  br label %435, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 425

435:                                              ; preds = %427, %420
; BB33 :
  %.sroa.368.0 = phi float [ %434, %427 ], [ %426, %420 ]
  %436 = zext i16 %265 to i32		; visa id: 426
  %437 = shl nuw i32 %436, 16		; visa id: 427
  %438 = bitcast i32 %437 to float
  %439 = fmul float %.sroa.065.0, %438		; visa id: 428
  %440 = fadd float %.sroa.0.0, %439		; visa id: 429
  %441 = zext i16 %266 to i32		; visa id: 430
  %442 = shl nuw i32 %441, 16		; visa id: 431
  %443 = bitcast i32 %442 to float
  %444 = fmul float %.sroa.80.0, %443		; visa id: 432
  %445 = fadd float %440, %444		; visa id: 433
  %446 = zext i16 %267 to i32		; visa id: 434
  %447 = shl nuw i32 %446, 16		; visa id: 435
  %448 = bitcast i32 %447 to float
  %449 = fmul float %.sroa.128.0, %448		; visa id: 436
  %450 = fadd float %445, %449		; visa id: 437
  %451 = zext i16 %268 to i32		; visa id: 438
  %452 = shl nuw i32 %451, 16		; visa id: 439
  %453 = bitcast i32 %452 to float
  %454 = fmul float %.sroa.176.0, %453		; visa id: 440
  %455 = fadd float %450, %454		; visa id: 441
  %456 = zext i16 %273 to i32		; visa id: 442
  %457 = shl nuw i32 %456, 16		; visa id: 443
  %458 = bitcast i32 %457 to float
  %459 = fmul float %.sroa.224.0, %458		; visa id: 444
  %460 = fadd float %455, %459		; visa id: 445
  %461 = zext i16 %274 to i32		; visa id: 446
  %462 = shl nuw i32 %461, 16		; visa id: 447
  %463 = bitcast i32 %462 to float
  %464 = fmul float %.sroa.272.0, %463		; visa id: 448
  %465 = fadd float %460, %464		; visa id: 449
  %466 = zext i16 %275 to i32		; visa id: 450
  %467 = shl nuw i32 %466, 16		; visa id: 451
  %468 = bitcast i32 %467 to float
  %469 = fmul float %.sroa.320.0, %468		; visa id: 452
  %470 = fadd float %465, %469		; visa id: 453
  %471 = zext i16 %276 to i32		; visa id: 454
  %472 = shl nuw i32 %471, 16		; visa id: 455
  %473 = bitcast i32 %472 to float
  %474 = fmul float %.sroa.368.0, %473		; visa id: 456
  %475 = fadd float %470, %474		; visa id: 457
  %476 = and i16 %154, 255		; visa id: 458
  %477 = zext i16 %476 to i32		; visa id: 459
  %478 = and i32 %477, 15		; visa id: 460
  %479 = uitofp i32 %478 to float		; visa id: 461
  %480 = fadd float %479, 5.000000e-01		; visa id: 462
  %481 = fmul float %158, %480		; visa id: 463
  %482 = fmul float %481, 2.500000e-01		; visa id: 464
  %483 = bitcast float %158 to i32
  %484 = and i32 %483, 2147483647		; visa id: 465
  %485 = bitcast i32 %484 to float
  %486 = fcmp une float %485, %485
  %487 = fcmp oeq float %485, 0x7FF0000000000000		; visa id: 466
  %488 = or i1 %486, %487		; visa id: 467
  %489 = bitcast float %482 to i32
  %490 = and i32 %489, 2147483647		; visa id: 469
  %491 = icmp ugt i32 %490, 2139095040
  %492 = fcmp oeq float %485, 0x7FF0000000000000		; visa id: 470
  %493 = fcmp une float %485, %485
  %494 = or i1 %493, %492		; visa id: 471
  %495 = or i1 %494, %491		; visa id: 473
  %496 = and i32 %220, 255		; visa id: 475
  br i1 %495, label %504, label %497, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 476

497:                                              ; preds = %435
; BB34 :
  %498 = and i32 %143, 256
  %499 = sub nsw i32 0, %496, !spirv.Decorations !8798
  %500 = icmp eq i32 %498, 0		; visa id: 478
  %501 = select i1 %500, i32 %496, i32 %499		; visa id: 480
  %502 = sitofp i32 %501 to float		; visa id: 481
  %503 = fmul float %482, %502		; visa id: 482
  br label %512, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 483

504:                                              ; preds = %435
; BB35 :
  %505 = uitofp i32 %496 to float		; visa id: 485
  %506 = fmul float %482, %505		; visa id: 486
  %507 = and i32 %143, 256
  %508 = icmp eq i32 %507, 0		; visa id: 487
  %509 = select i1 %508, i32 1, i32 -1		; visa id: 489
  %510 = sitofp i32 %509 to float		; visa id: 490
  %511 = fmul float %506, %510		; visa id: 491
  br label %512, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 492

512:                                              ; preds = %504, %497
; BB36 :
  %.sroa.065.1 = phi float [ %511, %504 ], [ %503, %497 ]
  %513 = bitcast i32 %220 to <4 x i8>
  %514 = extractelement <4 x i8> %513, i32 1
  %515 = zext i8 %514 to i32		; visa id: 493
  br i1 %495, label %523, label %516, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 494

516:                                              ; preds = %512
; BB37 :
  %517 = and i32 %143, 512
  %518 = sub nsw i32 0, %515, !spirv.Decorations !8798
  %519 = icmp eq i32 %517, 0		; visa id: 496
  %520 = select i1 %519, i32 %515, i32 %518		; visa id: 498
  %521 = sitofp i32 %520 to float		; visa id: 499
  %522 = fmul float %482, %521		; visa id: 500
  br label %531, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 501

523:                                              ; preds = %512
; BB38 :
  %524 = uitofp i32 %515 to float		; visa id: 503
  %525 = fmul float %482, %524		; visa id: 504
  %526 = and i32 %143, 512
  %527 = icmp eq i32 %526, 0		; visa id: 505
  %528 = select i1 %527, i32 1, i32 -1		; visa id: 507
  %529 = sitofp i32 %528 to float		; visa id: 508
  %530 = fmul float %525, %529		; visa id: 509
  br label %531, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 510

531:                                              ; preds = %523, %516
; BB39 :
  %.sroa.80.1 = phi float [ %530, %523 ], [ %522, %516 ]
  %532 = extractelement <4 x i8> %513, i32 2
  %533 = zext i8 %532 to i32		; visa id: 511
  br i1 %495, label %541, label %534, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 512

534:                                              ; preds = %531
; BB40 :
  %535 = and i32 %143, 1024
  %536 = sub nsw i32 0, %533, !spirv.Decorations !8798
  %537 = icmp eq i32 %535, 0		; visa id: 514
  %538 = select i1 %537, i32 %533, i32 %536		; visa id: 516
  %539 = sitofp i32 %538 to float		; visa id: 517
  %540 = fmul float %482, %539		; visa id: 518
  br label %549, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 519

541:                                              ; preds = %531
; BB41 :
  %542 = uitofp i32 %533 to float		; visa id: 521
  %543 = fmul float %482, %542		; visa id: 522
  %544 = and i32 %143, 1024
  %545 = icmp eq i32 %544, 0		; visa id: 523
  %546 = select i1 %545, i32 1, i32 -1		; visa id: 525
  %547 = sitofp i32 %546 to float		; visa id: 526
  %548 = fmul float %543, %547		; visa id: 527
  br label %549, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 528

549:                                              ; preds = %541, %534
; BB42 :
  %.sroa.128.1 = phi float [ %548, %541 ], [ %540, %534 ]
  %550 = lshr i32 %220, 24		; visa id: 529
  br i1 %495, label %558, label %551, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 530

551:                                              ; preds = %549
; BB43 :
  %552 = and i32 %143, 2048
  %553 = sub nsw i32 0, %550, !spirv.Decorations !8798
  %554 = icmp eq i32 %552, 0		; visa id: 532
  %555 = select i1 %554, i32 %550, i32 %553		; visa id: 534
  %556 = sitofp i32 %555 to float		; visa id: 535
  %557 = fmul float %482, %556		; visa id: 536
  br label %566, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 537

558:                                              ; preds = %549
; BB44 :
  %559 = uitofp i32 %550 to float		; visa id: 539
  %560 = fmul float %482, %559		; visa id: 540
  %561 = and i32 %143, 2048
  %562 = icmp eq i32 %561, 0		; visa id: 541
  %563 = select i1 %562, i32 1, i32 -1		; visa id: 543
  %564 = sitofp i32 %563 to float		; visa id: 544
  %565 = fmul float %560, %564		; visa id: 545
  br label %566, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 546

566:                                              ; preds = %558, %551
; BB45 :
  %.sroa.176.1 = phi float [ %565, %558 ], [ %557, %551 ]
  %567 = and i32 %221, 255		; visa id: 547
  br i1 %495, label %575, label %568, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 548

568:                                              ; preds = %566
; BB46 :
  %569 = and i32 %143, 4096
  %570 = sub nsw i32 0, %567, !spirv.Decorations !8798
  %571 = icmp eq i32 %569, 0		; visa id: 550
  %572 = select i1 %571, i32 %567, i32 %570		; visa id: 552
  %573 = sitofp i32 %572 to float		; visa id: 553
  %574 = fmul float %482, %573		; visa id: 554
  br label %583, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 555

575:                                              ; preds = %566
; BB47 :
  %576 = uitofp i32 %567 to float		; visa id: 557
  %577 = fmul float %482, %576		; visa id: 558
  %578 = and i32 %143, 4096
  %579 = icmp eq i32 %578, 0		; visa id: 559
  %580 = select i1 %579, i32 1, i32 -1		; visa id: 561
  %581 = sitofp i32 %580 to float		; visa id: 562
  %582 = fmul float %577, %581		; visa id: 563
  br label %583, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 564

583:                                              ; preds = %575, %568
; BB48 :
  %.sroa.224.1 = phi float [ %582, %575 ], [ %574, %568 ]
  %584 = bitcast i32 %221 to <4 x i8>
  %585 = extractelement <4 x i8> %584, i32 1
  %586 = zext i8 %585 to i32		; visa id: 565
  br i1 %495, label %594, label %587, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 566

587:                                              ; preds = %583
; BB49 :
  %588 = and i32 %143, 8192
  %589 = sub nsw i32 0, %586, !spirv.Decorations !8798
  %590 = icmp eq i32 %588, 0		; visa id: 568
  %591 = select i1 %590, i32 %586, i32 %589		; visa id: 570
  %592 = sitofp i32 %591 to float		; visa id: 571
  %593 = fmul float %482, %592		; visa id: 572
  br label %602, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 573

594:                                              ; preds = %583
; BB50 :
  %595 = uitofp i32 %586 to float		; visa id: 575
  %596 = fmul float %482, %595		; visa id: 576
  %597 = and i32 %143, 8192
  %598 = icmp eq i32 %597, 0		; visa id: 577
  %599 = select i1 %598, i32 1, i32 -1		; visa id: 579
  %600 = sitofp i32 %599 to float		; visa id: 580
  %601 = fmul float %596, %600		; visa id: 581
  br label %602, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 582

602:                                              ; preds = %594, %587
; BB51 :
  %.sroa.272.1 = phi float [ %601, %594 ], [ %593, %587 ]
  %603 = extractelement <4 x i8> %584, i32 2
  %604 = zext i8 %603 to i32		; visa id: 583
  br i1 %495, label %612, label %605, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 584

605:                                              ; preds = %602
; BB52 :
  %606 = and i32 %143, 16384
  %607 = sub nsw i32 0, %604, !spirv.Decorations !8798
  %608 = icmp eq i32 %606, 0		; visa id: 586
  %609 = select i1 %608, i32 %604, i32 %607		; visa id: 588
  %610 = sitofp i32 %609 to float		; visa id: 589
  %611 = fmul float %482, %610		; visa id: 590
  br label %620, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 591

612:                                              ; preds = %602
; BB53 :
  %613 = uitofp i32 %604 to float		; visa id: 593
  %614 = fmul float %482, %613		; visa id: 594
  %615 = and i32 %143, 16384
  %616 = icmp eq i32 %615, 0		; visa id: 595
  %617 = select i1 %616, i32 1, i32 -1		; visa id: 597
  %618 = sitofp i32 %617 to float		; visa id: 598
  %619 = fmul float %614, %618		; visa id: 599
  br label %620, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 600

620:                                              ; preds = %612, %605
; BB54 :
  %.sroa.320.1 = phi float [ %619, %612 ], [ %611, %605 ]
  %621 = lshr i32 %221, 24		; visa id: 601
  br i1 %495, label %629, label %622, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 602

622:                                              ; preds = %620
; BB55 :
  %623 = and i32 %143, 32768
  %624 = sub nsw i32 0, %621, !spirv.Decorations !8798
  %625 = icmp eq i32 %623, 0		; visa id: 604
  %626 = select i1 %625, i32 %621, i32 %624		; visa id: 606
  %627 = sitofp i32 %626 to float		; visa id: 607
  %628 = fmul float %482, %627		; visa id: 608
  br label %.preheader, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 609

629:                                              ; preds = %620
; BB56 :
  %630 = uitofp i32 %621 to float		; visa id: 611
  %631 = fmul float %482, %630		; visa id: 612
  %632 = and i32 %143, 32768
  %633 = icmp eq i32 %632, 0		; visa id: 613
  %634 = select i1 %633, i32 1, i32 -1		; visa id: 615
  %635 = sitofp i32 %634 to float		; visa id: 616
  %636 = fmul float %631, %635		; visa id: 617
  br label %.preheader, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 618

.preheader:                                       ; preds = %629, %622
; BB57 :
  %.sroa.368.1 = phi float [ %636, %629 ], [ %628, %622 ]
  %637 = fmul float %.sroa.065.1, %438		; visa id: 619
  %638 = fadd float %.sroa.20.0, %637		; visa id: 620
  %639 = fmul float %.sroa.80.1, %443		; visa id: 621
  %640 = fadd float %638, %639		; visa id: 622
  %641 = fmul float %.sroa.128.1, %448		; visa id: 623
  %642 = fadd float %640, %641		; visa id: 624
  %643 = fmul float %.sroa.176.1, %453		; visa id: 625
  %644 = fadd float %642, %643		; visa id: 626
  %645 = fmul float %.sroa.224.1, %458		; visa id: 627
  %646 = fadd float %644, %645		; visa id: 628
  %647 = fmul float %.sroa.272.1, %463		; visa id: 629
  %648 = fadd float %646, %647		; visa id: 630
  %649 = fmul float %.sroa.320.1, %468		; visa id: 631
  %650 = fadd float %648, %649		; visa id: 632
  %651 = fmul float %.sroa.368.1, %473		; visa id: 633
  %652 = fadd float %650, %651		; visa id: 634
  %653 = or i32 %257, 16		; visa id: 635
  %654 = zext i32 %653 to i64		; visa id: 636
  %655 = add i64 %654, %const_reg_qword2		; visa id: 637
  %IntToPtr2584 = inttoptr i64 %655 to ptr addrspace(1)		; visa id: 638
  %vCastload585 = load i32, ptr addrspace(1) %IntToPtr2584, align 2		; visa id: 638
  %656 = add i64 %655, 4
  %IntToPtr2586 = inttoptr i64 %656 to ptr addrspace(1)
  %vCastload587 = load i32, ptr addrspace(1) %IntToPtr2586, align 2		; visa id: 639
  %657 = add i64 %655, 8
  %IntToPtr2588 = inttoptr i64 %657 to ptr addrspace(1)
  %vCastload589 = load i32, ptr addrspace(1) %IntToPtr2588, align 2		; visa id: 640
  %658 = add i64 %655, 12
  %IntToPtr2590 = inttoptr i64 %658 to ptr addrspace(1)
  %vCastload591 = load i32, ptr addrspace(1) %IntToPtr2590, align 2		; visa id: 641
  %659 = bitcast i32 %vCastload585 to <2 x i16>		; visa id: 642
  %660 = bitcast i32 %vCastload587 to <2 x i16>		; visa id: 644
  %661 = extractelement <2 x i16> %659, i32 0		; visa id: 646
  %662 = extractelement <2 x i16> %659, i32 1		; visa id: 646
  %663 = extractelement <2 x i16> %660, i32 0		; visa id: 646
  %664 = extractelement <2 x i16> %660, i32 1		; visa id: 646
  %665 = bitcast i32 %vCastload589 to <2 x i16>		; visa id: 646
  %666 = bitcast i32 %vCastload591 to <2 x i16>		; visa id: 648
  %667 = extractelement <2 x i16> %665, i32 0		; visa id: 650
  %668 = extractelement <2 x i16> %665, i32 1		; visa id: 650
  %669 = extractelement <2 x i16> %666, i32 0		; visa id: 650
  %670 = extractelement <2 x i16> %666, i32 1		; visa id: 650
  %671 = and i32 %193, 255		; visa id: 650
  br i1 %293, label %679, label %672, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 651

672:                                              ; preds = %.preheader
; BB58 :
  %673 = and i32 %122, 16777216
  %674 = sub nsw i32 0, %671, !spirv.Decorations !8798
  %675 = icmp eq i32 %673, 0		; visa id: 653
  %676 = select i1 %675, i32 %671, i32 %674		; visa id: 655
  %677 = sitofp i32 %676 to float		; visa id: 656
  %678 = fmul float %283, %677		; visa id: 657
  br label %687, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 658

679:                                              ; preds = %.preheader
; BB59 :
  %680 = uitofp i32 %671 to float		; visa id: 660
  %681 = fmul float %283, %680		; visa id: 661
  %682 = and i32 %122, 16777216
  %683 = icmp eq i32 %682, 0		; visa id: 662
  %684 = select i1 %683, i32 1, i32 -1		; visa id: 664
  %685 = sitofp i32 %684 to float		; visa id: 665
  %686 = fmul float %681, %685		; visa id: 666
  br label %687, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 667

687:                                              ; preds = %679, %672
; BB60 :
  %.sroa.065.2 = phi float [ %686, %679 ], [ %678, %672 ]
  %688 = bitcast i32 %193 to <4 x i8>
  %689 = extractelement <4 x i8> %688, i32 1
  %690 = zext i8 %689 to i32		; visa id: 668
  br i1 %293, label %698, label %691, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 669

691:                                              ; preds = %687
; BB61 :
  %692 = and i32 %122, 33554432
  %693 = sub nsw i32 0, %690, !spirv.Decorations !8798
  %694 = icmp eq i32 %692, 0		; visa id: 671
  %695 = select i1 %694, i32 %690, i32 %693		; visa id: 673
  %696 = sitofp i32 %695 to float		; visa id: 674
  %697 = fmul float %283, %696		; visa id: 675
  br label %706, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 676

698:                                              ; preds = %687
; BB62 :
  %699 = uitofp i32 %690 to float		; visa id: 678
  %700 = fmul float %283, %699		; visa id: 679
  %701 = and i32 %122, 33554432
  %702 = icmp eq i32 %701, 0		; visa id: 680
  %703 = select i1 %702, i32 1, i32 -1		; visa id: 682
  %704 = sitofp i32 %703 to float		; visa id: 683
  %705 = fmul float %700, %704		; visa id: 684
  br label %706, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 685

706:                                              ; preds = %698, %691
; BB63 :
  %.sroa.80.2 = phi float [ %705, %698 ], [ %697, %691 ]
  %707 = extractelement <4 x i8> %688, i32 2
  %708 = zext i8 %707 to i32		; visa id: 686
  br i1 %293, label %716, label %709, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 687

709:                                              ; preds = %706
; BB64 :
  %710 = and i32 %122, 67108864
  %711 = sub nsw i32 0, %708, !spirv.Decorations !8798
  %712 = icmp eq i32 %710, 0		; visa id: 689
  %713 = select i1 %712, i32 %708, i32 %711		; visa id: 691
  %714 = sitofp i32 %713 to float		; visa id: 692
  %715 = fmul float %283, %714		; visa id: 693
  br label %724, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 694

716:                                              ; preds = %706
; BB65 :
  %717 = uitofp i32 %708 to float		; visa id: 696
  %718 = fmul float %283, %717		; visa id: 697
  %719 = and i32 %122, 67108864
  %720 = icmp eq i32 %719, 0		; visa id: 698
  %721 = select i1 %720, i32 1, i32 -1		; visa id: 700
  %722 = sitofp i32 %721 to float		; visa id: 701
  %723 = fmul float %718, %722		; visa id: 702
  br label %724, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 703

724:                                              ; preds = %716, %709
; BB66 :
  %.sroa.128.2 = phi float [ %723, %716 ], [ %715, %709 ]
  %725 = lshr i32 %193, 24		; visa id: 704
  br i1 %293, label %733, label %726, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 705

726:                                              ; preds = %724
; BB67 :
  %727 = and i32 %122, 134217728
  %728 = sub nsw i32 0, %725, !spirv.Decorations !8798
  %729 = icmp eq i32 %727, 0		; visa id: 707
  %730 = select i1 %729, i32 %725, i32 %728		; visa id: 709
  %731 = sitofp i32 %730 to float		; visa id: 710
  %732 = fmul float %283, %731		; visa id: 711
  br label %741, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 712

733:                                              ; preds = %724
; BB68 :
  %734 = uitofp i32 %725 to float		; visa id: 714
  %735 = fmul float %283, %734		; visa id: 715
  %736 = and i32 %122, 134217728
  %737 = icmp eq i32 %736, 0		; visa id: 716
  %738 = select i1 %737, i32 1, i32 -1		; visa id: 718
  %739 = sitofp i32 %738 to float		; visa id: 719
  %740 = fmul float %735, %739		; visa id: 720
  br label %741, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 721

741:                                              ; preds = %733, %726
; BB69 :
  %.sroa.176.2 = phi float [ %740, %733 ], [ %732, %726 ]
  %742 = and i32 %194, 255		; visa id: 722
  br i1 %293, label %750, label %743, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 723

743:                                              ; preds = %741
; BB70 :
  %744 = and i32 %122, 268435456
  %745 = sub nsw i32 0, %742, !spirv.Decorations !8798
  %746 = icmp eq i32 %744, 0		; visa id: 725
  %747 = select i1 %746, i32 %742, i32 %745		; visa id: 727
  %748 = sitofp i32 %747 to float		; visa id: 728
  %749 = fmul float %283, %748		; visa id: 729
  br label %758, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 730

750:                                              ; preds = %741
; BB71 :
  %751 = uitofp i32 %742 to float		; visa id: 732
  %752 = fmul float %283, %751		; visa id: 733
  %753 = and i32 %122, 268435456
  %754 = icmp eq i32 %753, 0		; visa id: 734
  %755 = select i1 %754, i32 1, i32 -1		; visa id: 736
  %756 = sitofp i32 %755 to float		; visa id: 737
  %757 = fmul float %752, %756		; visa id: 738
  br label %758, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 739

758:                                              ; preds = %750, %743
; BB72 :
  %.sroa.224.2 = phi float [ %757, %750 ], [ %749, %743 ]
  %759 = bitcast i32 %194 to <4 x i8>
  %760 = extractelement <4 x i8> %759, i32 1
  %761 = zext i8 %760 to i32		; visa id: 740
  br i1 %293, label %769, label %762, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 741

762:                                              ; preds = %758
; BB73 :
  %763 = and i32 %122, 536870912
  %764 = sub nsw i32 0, %761, !spirv.Decorations !8798
  %765 = icmp eq i32 %763, 0		; visa id: 743
  %766 = select i1 %765, i32 %761, i32 %764		; visa id: 745
  %767 = sitofp i32 %766 to float		; visa id: 746
  %768 = fmul float %283, %767		; visa id: 747
  br label %777, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 748

769:                                              ; preds = %758
; BB74 :
  %770 = uitofp i32 %761 to float		; visa id: 750
  %771 = fmul float %283, %770		; visa id: 751
  %772 = and i32 %122, 536870912
  %773 = icmp eq i32 %772, 0		; visa id: 752
  %774 = select i1 %773, i32 1, i32 -1		; visa id: 754
  %775 = sitofp i32 %774 to float		; visa id: 755
  %776 = fmul float %771, %775		; visa id: 756
  br label %777, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 757

777:                                              ; preds = %769, %762
; BB75 :
  %.sroa.272.2 = phi float [ %776, %769 ], [ %768, %762 ]
  %778 = extractelement <4 x i8> %759, i32 2
  %779 = zext i8 %778 to i32		; visa id: 758
  br i1 %293, label %787, label %780, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 759

780:                                              ; preds = %777
; BB76 :
  %781 = and i32 %122, 1073741824
  %782 = sub nsw i32 0, %779, !spirv.Decorations !8798
  %783 = icmp eq i32 %781, 0		; visa id: 761
  %784 = select i1 %783, i32 %779, i32 %782		; visa id: 763
  %785 = sitofp i32 %784 to float		; visa id: 764
  %786 = fmul float %283, %785		; visa id: 765
  br label %795, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 766

787:                                              ; preds = %777
; BB77 :
  %788 = uitofp i32 %779 to float		; visa id: 768
  %789 = fmul float %283, %788		; visa id: 769
  %790 = and i32 %122, 1073741824
  %791 = icmp eq i32 %790, 0		; visa id: 770
  %792 = select i1 %791, i32 1, i32 -1		; visa id: 772
  %793 = sitofp i32 %792 to float		; visa id: 773
  %794 = fmul float %789, %793		; visa id: 774
  br label %795, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 775

795:                                              ; preds = %787, %780
; BB78 :
  %.sroa.320.2 = phi float [ %794, %787 ], [ %786, %780 ]
  %796 = lshr i32 %194, 24		; visa id: 776
  br i1 %293, label %803, label %797, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 777

797:                                              ; preds = %795
; BB79 :
  %798 = sub nsw i32 0, %796, !spirv.Decorations !8798
  %799 = icmp slt i32 %122, 0		; visa id: 779
  %800 = select i1 %799, i32 %798, i32 %796		; visa id: 780
  %801 = sitofp i32 %800 to float		; visa id: 781
  %802 = fmul float %283, %801		; visa id: 782
  br label %810, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 783

803:                                              ; preds = %795
; BB80 :
  %804 = uitofp i32 %796 to float		; visa id: 785
  %805 = fmul float %283, %804		; visa id: 786
  %806 = icmp sgt i32 %122, -1		; visa id: 787
  %807 = select i1 %806, i32 1, i32 -1		; visa id: 788
  %808 = sitofp i32 %807 to float		; visa id: 789
  %809 = fmul float %805, %808		; visa id: 790
  br label %810, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 791

810:                                              ; preds = %803, %797
; BB81 :
  %.sroa.368.2 = phi float [ %809, %803 ], [ %802, %797 ]
  %811 = zext i16 %661 to i32		; visa id: 792
  %812 = shl nuw i32 %811, 16		; visa id: 793
  %813 = bitcast i32 %812 to float
  %814 = fmul float %.sroa.065.2, %813		; visa id: 794
  %815 = fadd float %.sroa.6.0, %814		; visa id: 795
  %816 = zext i16 %662 to i32		; visa id: 796
  %817 = shl nuw i32 %816, 16		; visa id: 797
  %818 = bitcast i32 %817 to float
  %819 = fmul float %.sroa.80.2, %818		; visa id: 798
  %820 = fadd float %815, %819		; visa id: 799
  %821 = zext i16 %663 to i32		; visa id: 800
  %822 = shl nuw i32 %821, 16		; visa id: 801
  %823 = bitcast i32 %822 to float
  %824 = fmul float %.sroa.128.2, %823		; visa id: 802
  %825 = fadd float %820, %824		; visa id: 803
  %826 = zext i16 %664 to i32		; visa id: 804
  %827 = shl nuw i32 %826, 16		; visa id: 805
  %828 = bitcast i32 %827 to float
  %829 = fmul float %.sroa.176.2, %828		; visa id: 806
  %830 = fadd float %825, %829		; visa id: 807
  %831 = zext i16 %667 to i32		; visa id: 808
  %832 = shl nuw i32 %831, 16		; visa id: 809
  %833 = bitcast i32 %832 to float
  %834 = fmul float %.sroa.224.2, %833		; visa id: 810
  %835 = fadd float %830, %834		; visa id: 811
  %836 = zext i16 %668 to i32		; visa id: 812
  %837 = shl nuw i32 %836, 16		; visa id: 813
  %838 = bitcast i32 %837 to float
  %839 = fmul float %.sroa.272.2, %838		; visa id: 814
  %840 = fadd float %835, %839		; visa id: 815
  %841 = zext i16 %669 to i32		; visa id: 816
  %842 = shl nuw i32 %841, 16		; visa id: 817
  %843 = bitcast i32 %842 to float
  %844 = fmul float %.sroa.320.2, %843		; visa id: 818
  %845 = fadd float %840, %844		; visa id: 819
  %846 = zext i16 %670 to i32		; visa id: 820
  %847 = shl nuw i32 %846, 16		; visa id: 821
  %848 = bitcast i32 %847 to float
  %849 = fmul float %.sroa.368.2, %848		; visa id: 822
  %850 = fadd float %845, %849		; visa id: 823
  %851 = and i32 %242, 255		; visa id: 824
  br i1 %495, label %859, label %852, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 825

852:                                              ; preds = %810
; BB82 :
  %853 = and i32 %143, 16777216
  %854 = sub nsw i32 0, %851, !spirv.Decorations !8798
  %855 = icmp eq i32 %853, 0		; visa id: 827
  %856 = select i1 %855, i32 %851, i32 %854		; visa id: 829
  %857 = sitofp i32 %856 to float		; visa id: 830
  %858 = fmul float %482, %857		; visa id: 831
  br label %867, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 832

859:                                              ; preds = %810
; BB83 :
  %860 = uitofp i32 %851 to float		; visa id: 834
  %861 = fmul float %482, %860		; visa id: 835
  %862 = and i32 %143, 16777216
  %863 = icmp eq i32 %862, 0		; visa id: 836
  %864 = select i1 %863, i32 1, i32 -1		; visa id: 838
  %865 = sitofp i32 %864 to float		; visa id: 839
  %866 = fmul float %861, %865		; visa id: 840
  br label %867, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 841

867:                                              ; preds = %859, %852
; BB84 :
  %.sroa.065.3 = phi float [ %866, %859 ], [ %858, %852 ]
  %868 = bitcast i32 %242 to <4 x i8>
  %869 = extractelement <4 x i8> %868, i32 1
  %870 = zext i8 %869 to i32		; visa id: 842
  br i1 %495, label %878, label %871, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 843

871:                                              ; preds = %867
; BB85 :
  %872 = and i32 %143, 33554432
  %873 = sub nsw i32 0, %870, !spirv.Decorations !8798
  %874 = icmp eq i32 %872, 0		; visa id: 845
  %875 = select i1 %874, i32 %870, i32 %873		; visa id: 847
  %876 = sitofp i32 %875 to float		; visa id: 848
  %877 = fmul float %482, %876		; visa id: 849
  br label %886, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 850

878:                                              ; preds = %867
; BB86 :
  %879 = uitofp i32 %870 to float		; visa id: 852
  %880 = fmul float %482, %879		; visa id: 853
  %881 = and i32 %143, 33554432
  %882 = icmp eq i32 %881, 0		; visa id: 854
  %883 = select i1 %882, i32 1, i32 -1		; visa id: 856
  %884 = sitofp i32 %883 to float		; visa id: 857
  %885 = fmul float %880, %884		; visa id: 858
  br label %886, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 859

886:                                              ; preds = %878, %871
; BB87 :
  %.sroa.80.3 = phi float [ %885, %878 ], [ %877, %871 ]
  %887 = extractelement <4 x i8> %868, i32 2
  %888 = zext i8 %887 to i32		; visa id: 860
  br i1 %495, label %896, label %889, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 861

889:                                              ; preds = %886
; BB88 :
  %890 = and i32 %143, 67108864
  %891 = sub nsw i32 0, %888, !spirv.Decorations !8798
  %892 = icmp eq i32 %890, 0		; visa id: 863
  %893 = select i1 %892, i32 %888, i32 %891		; visa id: 865
  %894 = sitofp i32 %893 to float		; visa id: 866
  %895 = fmul float %482, %894		; visa id: 867
  br label %904, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 868

896:                                              ; preds = %886
; BB89 :
  %897 = uitofp i32 %888 to float		; visa id: 870
  %898 = fmul float %482, %897		; visa id: 871
  %899 = and i32 %143, 67108864
  %900 = icmp eq i32 %899, 0		; visa id: 872
  %901 = select i1 %900, i32 1, i32 -1		; visa id: 874
  %902 = sitofp i32 %901 to float		; visa id: 875
  %903 = fmul float %898, %902		; visa id: 876
  br label %904, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 877

904:                                              ; preds = %896, %889
; BB90 :
  %.sroa.128.3 = phi float [ %903, %896 ], [ %895, %889 ]
  %905 = lshr i32 %242, 24		; visa id: 878
  br i1 %495, label %913, label %906, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 879

906:                                              ; preds = %904
; BB91 :
  %907 = and i32 %143, 134217728
  %908 = sub nsw i32 0, %905, !spirv.Decorations !8798
  %909 = icmp eq i32 %907, 0		; visa id: 881
  %910 = select i1 %909, i32 %905, i32 %908		; visa id: 883
  %911 = sitofp i32 %910 to float		; visa id: 884
  %912 = fmul float %482, %911		; visa id: 885
  br label %921, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 886

913:                                              ; preds = %904
; BB92 :
  %914 = uitofp i32 %905 to float		; visa id: 888
  %915 = fmul float %482, %914		; visa id: 889
  %916 = and i32 %143, 134217728
  %917 = icmp eq i32 %916, 0		; visa id: 890
  %918 = select i1 %917, i32 1, i32 -1		; visa id: 892
  %919 = sitofp i32 %918 to float		; visa id: 893
  %920 = fmul float %915, %919		; visa id: 894
  br label %921, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 895

921:                                              ; preds = %913, %906
; BB93 :
  %.sroa.176.3 = phi float [ %920, %913 ], [ %912, %906 ]
  %922 = and i32 %243, 255		; visa id: 896
  br i1 %495, label %930, label %923, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 897

923:                                              ; preds = %921
; BB94 :
  %924 = and i32 %143, 268435456
  %925 = sub nsw i32 0, %922, !spirv.Decorations !8798
  %926 = icmp eq i32 %924, 0		; visa id: 899
  %927 = select i1 %926, i32 %922, i32 %925		; visa id: 901
  %928 = sitofp i32 %927 to float		; visa id: 902
  %929 = fmul float %482, %928		; visa id: 903
  br label %938, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 904

930:                                              ; preds = %921
; BB95 :
  %931 = uitofp i32 %922 to float		; visa id: 906
  %932 = fmul float %482, %931		; visa id: 907
  %933 = and i32 %143, 268435456
  %934 = icmp eq i32 %933, 0		; visa id: 908
  %935 = select i1 %934, i32 1, i32 -1		; visa id: 910
  %936 = sitofp i32 %935 to float		; visa id: 911
  %937 = fmul float %932, %936		; visa id: 912
  br label %938, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 913

938:                                              ; preds = %930, %923
; BB96 :
  %.sroa.224.3 = phi float [ %937, %930 ], [ %929, %923 ]
  %939 = bitcast i32 %243 to <4 x i8>
  %940 = extractelement <4 x i8> %939, i32 1
  %941 = zext i8 %940 to i32		; visa id: 914
  br i1 %495, label %949, label %942, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 915

942:                                              ; preds = %938
; BB97 :
  %943 = and i32 %143, 536870912
  %944 = sub nsw i32 0, %941, !spirv.Decorations !8798
  %945 = icmp eq i32 %943, 0		; visa id: 917
  %946 = select i1 %945, i32 %941, i32 %944		; visa id: 919
  %947 = sitofp i32 %946 to float		; visa id: 920
  %948 = fmul float %482, %947		; visa id: 921
  br label %957, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 922

949:                                              ; preds = %938
; BB98 :
  %950 = uitofp i32 %941 to float		; visa id: 924
  %951 = fmul float %482, %950		; visa id: 925
  %952 = and i32 %143, 536870912
  %953 = icmp eq i32 %952, 0		; visa id: 926
  %954 = select i1 %953, i32 1, i32 -1		; visa id: 928
  %955 = sitofp i32 %954 to float		; visa id: 929
  %956 = fmul float %951, %955		; visa id: 930
  br label %957, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 931

957:                                              ; preds = %949, %942
; BB99 :
  %.sroa.272.3 = phi float [ %956, %949 ], [ %948, %942 ]
  %958 = extractelement <4 x i8> %939, i32 2
  %959 = zext i8 %958 to i32		; visa id: 932
  br i1 %495, label %967, label %960, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 933

960:                                              ; preds = %957
; BB100 :
  %961 = and i32 %143, 1073741824
  %962 = sub nsw i32 0, %959, !spirv.Decorations !8798
  %963 = icmp eq i32 %961, 0		; visa id: 935
  %964 = select i1 %963, i32 %959, i32 %962		; visa id: 937
  %965 = sitofp i32 %964 to float		; visa id: 938
  %966 = fmul float %482, %965		; visa id: 939
  br label %975, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 940

967:                                              ; preds = %957
; BB101 :
  %968 = uitofp i32 %959 to float		; visa id: 942
  %969 = fmul float %482, %968		; visa id: 943
  %970 = and i32 %143, 1073741824
  %971 = icmp eq i32 %970, 0		; visa id: 944
  %972 = select i1 %971, i32 1, i32 -1		; visa id: 946
  %973 = sitofp i32 %972 to float		; visa id: 947
  %974 = fmul float %969, %973		; visa id: 948
  br label %975, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 949

975:                                              ; preds = %967, %960
; BB102 :
  %.sroa.320.3 = phi float [ %974, %967 ], [ %966, %960 ]
  %976 = lshr i32 %243, 24		; visa id: 950
  br i1 %495, label %983, label %977, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 951

977:                                              ; preds = %975
; BB103 :
  %978 = sub nsw i32 0, %976, !spirv.Decorations !8798
  %979 = icmp slt i32 %143, 0		; visa id: 953
  %980 = select i1 %979, i32 %978, i32 %976		; visa id: 954
  %981 = sitofp i32 %980 to float		; visa id: 955
  %982 = fmul float %482, %981		; visa id: 956
  br label %.preheader.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 957

983:                                              ; preds = %975
; BB104 :
  %984 = uitofp i32 %976 to float		; visa id: 959
  %985 = fmul float %482, %984		; visa id: 960
  %986 = icmp sgt i32 %143, -1		; visa id: 961
  %987 = select i1 %986, i32 1, i32 -1		; visa id: 962
  %988 = sitofp i32 %987 to float		; visa id: 963
  %989 = fmul float %985, %988		; visa id: 964
  br label %.preheader.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 965

.preheader.1:                                     ; preds = %983, %977
; BB105 :
  %.sroa.368.3 = phi float [ %989, %983 ], [ %982, %977 ]
  %990 = fmul float %.sroa.065.3, %813		; visa id: 966
  %991 = fadd float %.sroa.23.0, %990		; visa id: 967
  %992 = fmul float %.sroa.80.3, %818		; visa id: 968
  %993 = fadd float %991, %992		; visa id: 969
  %994 = fmul float %.sroa.128.3, %823		; visa id: 970
  %995 = fadd float %993, %994		; visa id: 971
  %996 = fmul float %.sroa.176.3, %828		; visa id: 972
  %997 = fadd float %995, %996		; visa id: 973
  %998 = fmul float %.sroa.224.3, %833		; visa id: 974
  %999 = fadd float %997, %998		; visa id: 975
  %1000 = fmul float %.sroa.272.3, %838		; visa id: 976
  %1001 = fadd float %999, %1000		; visa id: 977
  %1002 = fmul float %.sroa.320.3, %843		; visa id: 978
  %1003 = fadd float %1001, %1002		; visa id: 979
  %1004 = fmul float %.sroa.368.3, %848		; visa id: 980
  %1005 = fadd float %1003, %1004		; visa id: 981
  %1006 = or i32 %257, 32		; visa id: 982
  %1007 = zext i32 %1006 to i64		; visa id: 983
  %1008 = add i64 %1007, %const_reg_qword2		; visa id: 984
  %IntToPtr2592 = inttoptr i64 %1008 to ptr addrspace(1)		; visa id: 985
  %vCastload593 = load i32, ptr addrspace(1) %IntToPtr2592, align 2		; visa id: 985
  %1009 = add i64 %1008, 4
  %IntToPtr2594 = inttoptr i64 %1009 to ptr addrspace(1)
  %vCastload595 = load i32, ptr addrspace(1) %IntToPtr2594, align 2		; visa id: 986
  %1010 = add i64 %1008, 8
  %IntToPtr2596 = inttoptr i64 %1010 to ptr addrspace(1)
  %vCastload597 = load i32, ptr addrspace(1) %IntToPtr2596, align 2		; visa id: 987
  %1011 = add i64 %1008, 12
  %IntToPtr2598 = inttoptr i64 %1011 to ptr addrspace(1)
  %vCastload599 = load i32, ptr addrspace(1) %IntToPtr2598, align 2		; visa id: 988
  %1012 = bitcast i32 %vCastload593 to <2 x i16>		; visa id: 989
  %1013 = bitcast i32 %vCastload595 to <2 x i16>		; visa id: 991
  %1014 = extractelement <2 x i16> %1012, i32 0		; visa id: 993
  %1015 = extractelement <2 x i16> %1012, i32 1		; visa id: 993
  %1016 = extractelement <2 x i16> %1013, i32 0		; visa id: 993
  %1017 = extractelement <2 x i16> %1013, i32 1		; visa id: 993
  %1018 = bitcast i32 %vCastload597 to <2 x i16>		; visa id: 993
  %1019 = bitcast i32 %vCastload599 to <2 x i16>		; visa id: 995
  %1020 = extractelement <2 x i16> %1018, i32 0		; visa id: 997
  %1021 = extractelement <2 x i16> %1018, i32 1		; visa id: 997
  %1022 = extractelement <2 x i16> %1019, i32 0		; visa id: 997
  %1023 = extractelement <2 x i16> %1019, i32 1		; visa id: 997
  %1024 = lshr i32 %278, 4		; visa id: 997
  %1025 = uitofp i32 %1024 to float		; visa id: 998
  %1026 = fadd float %1025, 5.000000e-01		; visa id: 999
  %1027 = fmul float %139, %1026		; visa id: 1000
  %1028 = fmul float %1027, 2.500000e-01		; visa id: 1001
  %1029 = bitcast float %1028 to i32
  %1030 = and i32 %1029, 2147483647		; visa id: 1002
  %1031 = icmp ugt i32 %1030, 2139095040
  %1032 = fcmp oeq float %286, 0x7FF0000000000000		; visa id: 1003
  %1033 = fcmp une float %286, %286
  %1034 = or i1 %1033, %1032		; visa id: 1004
  %1035 = or i1 %1034, %1031		; visa id: 1006
  %1036 = and i32 %195, 255		; visa id: 1008
  br i1 %1035, label %1044, label %1037, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1009

1037:                                             ; preds = %.preheader.1
; BB106 :
  %1038 = and i32 %123, 256
  %1039 = sub nsw i32 0, %1036, !spirv.Decorations !8798
  %1040 = icmp eq i32 %1038, 0		; visa id: 1011
  %1041 = select i1 %1040, i32 %1036, i32 %1039		; visa id: 1013
  %1042 = sitofp i32 %1041 to float		; visa id: 1014
  %1043 = fmul float %1028, %1042		; visa id: 1015
  br label %1052, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1016

1044:                                             ; preds = %.preheader.1
; BB107 :
  %1045 = uitofp i32 %1036 to float		; visa id: 1018
  %1046 = fmul float %1028, %1045		; visa id: 1019
  %1047 = and i32 %123, 256
  %1048 = icmp eq i32 %1047, 0		; visa id: 1020
  %1049 = select i1 %1048, i32 1, i32 -1		; visa id: 1022
  %1050 = sitofp i32 %1049 to float		; visa id: 1023
  %1051 = fmul float %1046, %1050		; visa id: 1024
  br label %1052, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1025

1052:                                             ; preds = %1044, %1037
; BB108 :
  %.sroa.065.4 = phi float [ %1051, %1044 ], [ %1043, %1037 ]
  %1053 = bitcast i32 %195 to <4 x i8>
  %1054 = extractelement <4 x i8> %1053, i32 1
  %1055 = zext i8 %1054 to i32		; visa id: 1026
  br i1 %1035, label %1063, label %1056, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1027

1056:                                             ; preds = %1052
; BB109 :
  %1057 = and i32 %123, 512
  %1058 = sub nsw i32 0, %1055, !spirv.Decorations !8798
  %1059 = icmp eq i32 %1057, 0		; visa id: 1029
  %1060 = select i1 %1059, i32 %1055, i32 %1058		; visa id: 1031
  %1061 = sitofp i32 %1060 to float		; visa id: 1032
  %1062 = fmul float %1028, %1061		; visa id: 1033
  br label %1071, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1034

1063:                                             ; preds = %1052
; BB110 :
  %1064 = uitofp i32 %1055 to float		; visa id: 1036
  %1065 = fmul float %1028, %1064		; visa id: 1037
  %1066 = and i32 %123, 512
  %1067 = icmp eq i32 %1066, 0		; visa id: 1038
  %1068 = select i1 %1067, i32 1, i32 -1		; visa id: 1040
  %1069 = sitofp i32 %1068 to float		; visa id: 1041
  %1070 = fmul float %1065, %1069		; visa id: 1042
  br label %1071, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1043

1071:                                             ; preds = %1063, %1056
; BB111 :
  %.sroa.80.4 = phi float [ %1070, %1063 ], [ %1062, %1056 ]
  %1072 = extractelement <4 x i8> %1053, i32 2
  %1073 = zext i8 %1072 to i32		; visa id: 1044
  br i1 %1035, label %1081, label %1074, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1045

1074:                                             ; preds = %1071
; BB112 :
  %1075 = and i32 %123, 1024
  %1076 = sub nsw i32 0, %1073, !spirv.Decorations !8798
  %1077 = icmp eq i32 %1075, 0		; visa id: 1047
  %1078 = select i1 %1077, i32 %1073, i32 %1076		; visa id: 1049
  %1079 = sitofp i32 %1078 to float		; visa id: 1050
  %1080 = fmul float %1028, %1079		; visa id: 1051
  br label %1089, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1052

1081:                                             ; preds = %1071
; BB113 :
  %1082 = uitofp i32 %1073 to float		; visa id: 1054
  %1083 = fmul float %1028, %1082		; visa id: 1055
  %1084 = and i32 %123, 1024
  %1085 = icmp eq i32 %1084, 0		; visa id: 1056
  %1086 = select i1 %1085, i32 1, i32 -1		; visa id: 1058
  %1087 = sitofp i32 %1086 to float		; visa id: 1059
  %1088 = fmul float %1083, %1087		; visa id: 1060
  br label %1089, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1061

1089:                                             ; preds = %1081, %1074
; BB114 :
  %.sroa.128.4 = phi float [ %1088, %1081 ], [ %1080, %1074 ]
  %1090 = lshr i32 %195, 24		; visa id: 1062
  br i1 %1035, label %1098, label %1091, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1063

1091:                                             ; preds = %1089
; BB115 :
  %1092 = and i32 %123, 2048
  %1093 = sub nsw i32 0, %1090, !spirv.Decorations !8798
  %1094 = icmp eq i32 %1092, 0		; visa id: 1065
  %1095 = select i1 %1094, i32 %1090, i32 %1093		; visa id: 1067
  %1096 = sitofp i32 %1095 to float		; visa id: 1068
  %1097 = fmul float %1028, %1096		; visa id: 1069
  br label %1106, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1070

1098:                                             ; preds = %1089
; BB116 :
  %1099 = uitofp i32 %1090 to float		; visa id: 1072
  %1100 = fmul float %1028, %1099		; visa id: 1073
  %1101 = and i32 %123, 2048
  %1102 = icmp eq i32 %1101, 0		; visa id: 1074
  %1103 = select i1 %1102, i32 1, i32 -1		; visa id: 1076
  %1104 = sitofp i32 %1103 to float		; visa id: 1077
  %1105 = fmul float %1100, %1104		; visa id: 1078
  br label %1106, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1079

1106:                                             ; preds = %1098, %1091
; BB117 :
  %.sroa.176.4 = phi float [ %1105, %1098 ], [ %1097, %1091 ]
  %1107 = and i32 %196, 255		; visa id: 1080
  br i1 %1035, label %1115, label %1108, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1081

1108:                                             ; preds = %1106
; BB118 :
  %1109 = and i32 %123, 4096
  %1110 = sub nsw i32 0, %1107, !spirv.Decorations !8798
  %1111 = icmp eq i32 %1109, 0		; visa id: 1083
  %1112 = select i1 %1111, i32 %1107, i32 %1110		; visa id: 1085
  %1113 = sitofp i32 %1112 to float		; visa id: 1086
  %1114 = fmul float %1028, %1113		; visa id: 1087
  br label %1123, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1088

1115:                                             ; preds = %1106
; BB119 :
  %1116 = uitofp i32 %1107 to float		; visa id: 1090
  %1117 = fmul float %1028, %1116		; visa id: 1091
  %1118 = and i32 %123, 4096
  %1119 = icmp eq i32 %1118, 0		; visa id: 1092
  %1120 = select i1 %1119, i32 1, i32 -1		; visa id: 1094
  %1121 = sitofp i32 %1120 to float		; visa id: 1095
  %1122 = fmul float %1117, %1121		; visa id: 1096
  br label %1123, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1097

1123:                                             ; preds = %1115, %1108
; BB120 :
  %.sroa.224.4 = phi float [ %1122, %1115 ], [ %1114, %1108 ]
  %1124 = bitcast i32 %196 to <4 x i8>
  %1125 = extractelement <4 x i8> %1124, i32 1
  %1126 = zext i8 %1125 to i32		; visa id: 1098
  br i1 %1035, label %1134, label %1127, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1099

1127:                                             ; preds = %1123
; BB121 :
  %1128 = and i32 %123, 8192
  %1129 = sub nsw i32 0, %1126, !spirv.Decorations !8798
  %1130 = icmp eq i32 %1128, 0		; visa id: 1101
  %1131 = select i1 %1130, i32 %1126, i32 %1129		; visa id: 1103
  %1132 = sitofp i32 %1131 to float		; visa id: 1104
  %1133 = fmul float %1028, %1132		; visa id: 1105
  br label %1142, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1106

1134:                                             ; preds = %1123
; BB122 :
  %1135 = uitofp i32 %1126 to float		; visa id: 1108
  %1136 = fmul float %1028, %1135		; visa id: 1109
  %1137 = and i32 %123, 8192
  %1138 = icmp eq i32 %1137, 0		; visa id: 1110
  %1139 = select i1 %1138, i32 1, i32 -1		; visa id: 1112
  %1140 = sitofp i32 %1139 to float		; visa id: 1113
  %1141 = fmul float %1136, %1140		; visa id: 1114
  br label %1142, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1115

1142:                                             ; preds = %1134, %1127
; BB123 :
  %.sroa.272.4 = phi float [ %1141, %1134 ], [ %1133, %1127 ]
  %1143 = extractelement <4 x i8> %1124, i32 2
  %1144 = zext i8 %1143 to i32		; visa id: 1116
  br i1 %1035, label %1152, label %1145, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1117

1145:                                             ; preds = %1142
; BB124 :
  %1146 = and i32 %123, 16384
  %1147 = sub nsw i32 0, %1144, !spirv.Decorations !8798
  %1148 = icmp eq i32 %1146, 0		; visa id: 1119
  %1149 = select i1 %1148, i32 %1144, i32 %1147		; visa id: 1121
  %1150 = sitofp i32 %1149 to float		; visa id: 1122
  %1151 = fmul float %1028, %1150		; visa id: 1123
  br label %1160, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1124

1152:                                             ; preds = %1142
; BB125 :
  %1153 = uitofp i32 %1144 to float		; visa id: 1126
  %1154 = fmul float %1028, %1153		; visa id: 1127
  %1155 = and i32 %123, 16384
  %1156 = icmp eq i32 %1155, 0		; visa id: 1128
  %1157 = select i1 %1156, i32 1, i32 -1		; visa id: 1130
  %1158 = sitofp i32 %1157 to float		; visa id: 1131
  %1159 = fmul float %1154, %1158		; visa id: 1132
  br label %1160, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1133

1160:                                             ; preds = %1152, %1145
; BB126 :
  %.sroa.320.4 = phi float [ %1159, %1152 ], [ %1151, %1145 ]
  %1161 = lshr i32 %196, 24		; visa id: 1134
  br i1 %1035, label %1169, label %1162, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1135

1162:                                             ; preds = %1160
; BB127 :
  %1163 = and i32 %123, 32768
  %1164 = sub nsw i32 0, %1161, !spirv.Decorations !8798
  %1165 = icmp eq i32 %1163, 0		; visa id: 1137
  %1166 = select i1 %1165, i32 %1161, i32 %1164		; visa id: 1139
  %1167 = sitofp i32 %1166 to float		; visa id: 1140
  %1168 = fmul float %1028, %1167		; visa id: 1141
  br label %1177, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1142

1169:                                             ; preds = %1160
; BB128 :
  %1170 = uitofp i32 %1161 to float		; visa id: 1144
  %1171 = fmul float %1028, %1170		; visa id: 1145
  %1172 = and i32 %123, 32768
  %1173 = icmp eq i32 %1172, 0		; visa id: 1146
  %1174 = select i1 %1173, i32 1, i32 -1		; visa id: 1148
  %1175 = sitofp i32 %1174 to float		; visa id: 1149
  %1176 = fmul float %1171, %1175		; visa id: 1150
  br label %1177, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1151

1177:                                             ; preds = %1169, %1162
; BB129 :
  %.sroa.368.4 = phi float [ %1176, %1169 ], [ %1168, %1162 ]
  %1178 = zext i16 %1014 to i32		; visa id: 1152
  %1179 = shl nuw i32 %1178, 16		; visa id: 1153
  %1180 = bitcast i32 %1179 to float
  %1181 = fmul float %.sroa.065.4, %1180		; visa id: 1154
  %1182 = fadd float %.sroa.8.0, %1181		; visa id: 1155
  %1183 = zext i16 %1015 to i32		; visa id: 1156
  %1184 = shl nuw i32 %1183, 16		; visa id: 1157
  %1185 = bitcast i32 %1184 to float
  %1186 = fmul float %.sroa.80.4, %1185		; visa id: 1158
  %1187 = fadd float %1182, %1186		; visa id: 1159
  %1188 = zext i16 %1016 to i32		; visa id: 1160
  %1189 = shl nuw i32 %1188, 16		; visa id: 1161
  %1190 = bitcast i32 %1189 to float
  %1191 = fmul float %.sroa.128.4, %1190		; visa id: 1162
  %1192 = fadd float %1187, %1191		; visa id: 1163
  %1193 = zext i16 %1017 to i32		; visa id: 1164
  %1194 = shl nuw i32 %1193, 16		; visa id: 1165
  %1195 = bitcast i32 %1194 to float
  %1196 = fmul float %.sroa.176.4, %1195		; visa id: 1166
  %1197 = fadd float %1192, %1196		; visa id: 1167
  %1198 = zext i16 %1020 to i32		; visa id: 1168
  %1199 = shl nuw i32 %1198, 16		; visa id: 1169
  %1200 = bitcast i32 %1199 to float
  %1201 = fmul float %.sroa.224.4, %1200		; visa id: 1170
  %1202 = fadd float %1197, %1201		; visa id: 1171
  %1203 = zext i16 %1021 to i32		; visa id: 1172
  %1204 = shl nuw i32 %1203, 16		; visa id: 1173
  %1205 = bitcast i32 %1204 to float
  %1206 = fmul float %.sroa.272.4, %1205		; visa id: 1174
  %1207 = fadd float %1202, %1206		; visa id: 1175
  %1208 = zext i16 %1022 to i32		; visa id: 1176
  %1209 = shl nuw i32 %1208, 16		; visa id: 1177
  %1210 = bitcast i32 %1209 to float
  %1211 = fmul float %.sroa.320.4, %1210		; visa id: 1178
  %1212 = fadd float %1207, %1211		; visa id: 1179
  %1213 = zext i16 %1023 to i32		; visa id: 1180
  %1214 = shl nuw i32 %1213, 16		; visa id: 1181
  %1215 = bitcast i32 %1214 to float
  %1216 = fmul float %.sroa.368.4, %1215		; visa id: 1182
  %1217 = fadd float %1212, %1216		; visa id: 1183
  %1218 = lshr i32 %477, 4		; visa id: 1184
  %1219 = uitofp i32 %1218 to float		; visa id: 1185
  %1220 = fadd float %1219, 5.000000e-01		; visa id: 1186
  %1221 = fmul float %158, %1220		; visa id: 1187
  %1222 = fmul float %1221, 2.500000e-01		; visa id: 1188
  %1223 = bitcast float %1222 to i32
  %1224 = and i32 %1223, 2147483647		; visa id: 1189
  %1225 = icmp ugt i32 %1224, 2139095040		; visa id: 1190
  %1226 = or i1 %488, %1225		; visa id: 1191
  %1227 = and i32 %244, 255		; visa id: 1192
  br i1 %1226, label %1235, label %1228, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1193

1228:                                             ; preds = %1177
; BB130 :
  %1229 = and i32 %144, 256
  %1230 = sub nsw i32 0, %1227, !spirv.Decorations !8798
  %1231 = icmp eq i32 %1229, 0		; visa id: 1195
  %1232 = select i1 %1231, i32 %1227, i32 %1230		; visa id: 1197
  %1233 = sitofp i32 %1232 to float		; visa id: 1198
  %1234 = fmul float %1222, %1233		; visa id: 1199
  br label %1243, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1200

1235:                                             ; preds = %1177
; BB131 :
  %1236 = uitofp i32 %1227 to float		; visa id: 1202
  %1237 = fmul float %1222, %1236		; visa id: 1203
  %1238 = and i32 %144, 256
  %1239 = icmp eq i32 %1238, 0		; visa id: 1204
  %1240 = select i1 %1239, i32 1, i32 -1		; visa id: 1206
  %1241 = sitofp i32 %1240 to float		; visa id: 1207
  %1242 = fmul float %1237, %1241		; visa id: 1208
  br label %1243, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1209

1243:                                             ; preds = %1235, %1228
; BB132 :
  %.sroa.065.5 = phi float [ %1242, %1235 ], [ %1234, %1228 ]
  %1244 = bitcast i32 %244 to <4 x i8>
  %1245 = extractelement <4 x i8> %1244, i32 1
  %1246 = zext i8 %1245 to i32		; visa id: 1210
  br i1 %1226, label %1254, label %1247, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1211

1247:                                             ; preds = %1243
; BB133 :
  %1248 = and i32 %144, 512
  %1249 = sub nsw i32 0, %1246, !spirv.Decorations !8798
  %1250 = icmp eq i32 %1248, 0		; visa id: 1213
  %1251 = select i1 %1250, i32 %1246, i32 %1249		; visa id: 1215
  %1252 = sitofp i32 %1251 to float		; visa id: 1216
  %1253 = fmul float %1222, %1252		; visa id: 1217
  br label %1262, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1218

1254:                                             ; preds = %1243
; BB134 :
  %1255 = uitofp i32 %1246 to float		; visa id: 1220
  %1256 = fmul float %1222, %1255		; visa id: 1221
  %1257 = and i32 %144, 512
  %1258 = icmp eq i32 %1257, 0		; visa id: 1222
  %1259 = select i1 %1258, i32 1, i32 -1		; visa id: 1224
  %1260 = sitofp i32 %1259 to float		; visa id: 1225
  %1261 = fmul float %1256, %1260		; visa id: 1226
  br label %1262, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1227

1262:                                             ; preds = %1254, %1247
; BB135 :
  %.sroa.80.5 = phi float [ %1261, %1254 ], [ %1253, %1247 ]
  %1263 = extractelement <4 x i8> %1244, i32 2
  %1264 = zext i8 %1263 to i32		; visa id: 1228
  br i1 %1226, label %1272, label %1265, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1229

1265:                                             ; preds = %1262
; BB136 :
  %1266 = and i32 %144, 1024
  %1267 = sub nsw i32 0, %1264, !spirv.Decorations !8798
  %1268 = icmp eq i32 %1266, 0		; visa id: 1231
  %1269 = select i1 %1268, i32 %1264, i32 %1267		; visa id: 1233
  %1270 = sitofp i32 %1269 to float		; visa id: 1234
  %1271 = fmul float %1222, %1270		; visa id: 1235
  br label %1280, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1236

1272:                                             ; preds = %1262
; BB137 :
  %1273 = uitofp i32 %1264 to float		; visa id: 1238
  %1274 = fmul float %1222, %1273		; visa id: 1239
  %1275 = and i32 %144, 1024
  %1276 = icmp eq i32 %1275, 0		; visa id: 1240
  %1277 = select i1 %1276, i32 1, i32 -1		; visa id: 1242
  %1278 = sitofp i32 %1277 to float		; visa id: 1243
  %1279 = fmul float %1274, %1278		; visa id: 1244
  br label %1280, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1245

1280:                                             ; preds = %1272, %1265
; BB138 :
  %.sroa.128.5 = phi float [ %1279, %1272 ], [ %1271, %1265 ]
  %1281 = lshr i32 %244, 24		; visa id: 1246
  br i1 %1226, label %1289, label %1282, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1247

1282:                                             ; preds = %1280
; BB139 :
  %1283 = and i32 %144, 2048
  %1284 = sub nsw i32 0, %1281, !spirv.Decorations !8798
  %1285 = icmp eq i32 %1283, 0		; visa id: 1249
  %1286 = select i1 %1285, i32 %1281, i32 %1284		; visa id: 1251
  %1287 = sitofp i32 %1286 to float		; visa id: 1252
  %1288 = fmul float %1222, %1287		; visa id: 1253
  br label %1297, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1254

1289:                                             ; preds = %1280
; BB140 :
  %1290 = uitofp i32 %1281 to float		; visa id: 1256
  %1291 = fmul float %1222, %1290		; visa id: 1257
  %1292 = and i32 %144, 2048
  %1293 = icmp eq i32 %1292, 0		; visa id: 1258
  %1294 = select i1 %1293, i32 1, i32 -1		; visa id: 1260
  %1295 = sitofp i32 %1294 to float		; visa id: 1261
  %1296 = fmul float %1291, %1295		; visa id: 1262
  br label %1297, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1263

1297:                                             ; preds = %1289, %1282
; BB141 :
  %.sroa.176.5 = phi float [ %1296, %1289 ], [ %1288, %1282 ]
  %1298 = and i32 %245, 255		; visa id: 1264
  br i1 %1226, label %1306, label %1299, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1265

1299:                                             ; preds = %1297
; BB142 :
  %1300 = and i32 %144, 4096
  %1301 = sub nsw i32 0, %1298, !spirv.Decorations !8798
  %1302 = icmp eq i32 %1300, 0		; visa id: 1267
  %1303 = select i1 %1302, i32 %1298, i32 %1301		; visa id: 1269
  %1304 = sitofp i32 %1303 to float		; visa id: 1270
  %1305 = fmul float %1222, %1304		; visa id: 1271
  br label %1314, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1272

1306:                                             ; preds = %1297
; BB143 :
  %1307 = uitofp i32 %1298 to float		; visa id: 1274
  %1308 = fmul float %1222, %1307		; visa id: 1275
  %1309 = and i32 %144, 4096
  %1310 = icmp eq i32 %1309, 0		; visa id: 1276
  %1311 = select i1 %1310, i32 1, i32 -1		; visa id: 1278
  %1312 = sitofp i32 %1311 to float		; visa id: 1279
  %1313 = fmul float %1308, %1312		; visa id: 1280
  br label %1314, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1281

1314:                                             ; preds = %1306, %1299
; BB144 :
  %.sroa.224.5 = phi float [ %1313, %1306 ], [ %1305, %1299 ]
  %1315 = bitcast i32 %245 to <4 x i8>
  %1316 = extractelement <4 x i8> %1315, i32 1
  %1317 = zext i8 %1316 to i32		; visa id: 1282
  br i1 %1226, label %1325, label %1318, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1283

1318:                                             ; preds = %1314
; BB145 :
  %1319 = and i32 %144, 8192
  %1320 = sub nsw i32 0, %1317, !spirv.Decorations !8798
  %1321 = icmp eq i32 %1319, 0		; visa id: 1285
  %1322 = select i1 %1321, i32 %1317, i32 %1320		; visa id: 1287
  %1323 = sitofp i32 %1322 to float		; visa id: 1288
  %1324 = fmul float %1222, %1323		; visa id: 1289
  br label %1333, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1290

1325:                                             ; preds = %1314
; BB146 :
  %1326 = uitofp i32 %1317 to float		; visa id: 1292
  %1327 = fmul float %1222, %1326		; visa id: 1293
  %1328 = and i32 %144, 8192
  %1329 = icmp eq i32 %1328, 0		; visa id: 1294
  %1330 = select i1 %1329, i32 1, i32 -1		; visa id: 1296
  %1331 = sitofp i32 %1330 to float		; visa id: 1297
  %1332 = fmul float %1327, %1331		; visa id: 1298
  br label %1333, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1299

1333:                                             ; preds = %1325, %1318
; BB147 :
  %.sroa.272.5 = phi float [ %1332, %1325 ], [ %1324, %1318 ]
  %1334 = extractelement <4 x i8> %1315, i32 2
  %1335 = zext i8 %1334 to i32		; visa id: 1300
  br i1 %1226, label %1343, label %1336, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1301

1336:                                             ; preds = %1333
; BB148 :
  %1337 = and i32 %144, 16384
  %1338 = sub nsw i32 0, %1335, !spirv.Decorations !8798
  %1339 = icmp eq i32 %1337, 0		; visa id: 1303
  %1340 = select i1 %1339, i32 %1335, i32 %1338		; visa id: 1305
  %1341 = sitofp i32 %1340 to float		; visa id: 1306
  %1342 = fmul float %1222, %1341		; visa id: 1307
  br label %1351, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1308

1343:                                             ; preds = %1333
; BB149 :
  %1344 = uitofp i32 %1335 to float		; visa id: 1310
  %1345 = fmul float %1222, %1344		; visa id: 1311
  %1346 = and i32 %144, 16384
  %1347 = icmp eq i32 %1346, 0		; visa id: 1312
  %1348 = select i1 %1347, i32 1, i32 -1		; visa id: 1314
  %1349 = sitofp i32 %1348 to float		; visa id: 1315
  %1350 = fmul float %1345, %1349		; visa id: 1316
  br label %1351, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1317

1351:                                             ; preds = %1343, %1336
; BB150 :
  %.sroa.320.5 = phi float [ %1350, %1343 ], [ %1342, %1336 ]
  %1352 = lshr i32 %245, 24		; visa id: 1318
  br i1 %1226, label %1360, label %1353, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1319

1353:                                             ; preds = %1351
; BB151 :
  %1354 = and i32 %144, 32768
  %1355 = sub nsw i32 0, %1352, !spirv.Decorations !8798
  %1356 = icmp eq i32 %1354, 0		; visa id: 1321
  %1357 = select i1 %1356, i32 %1352, i32 %1355		; visa id: 1323
  %1358 = sitofp i32 %1357 to float		; visa id: 1324
  %1359 = fmul float %1222, %1358		; visa id: 1325
  br label %.preheader.2, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1326

1360:                                             ; preds = %1351
; BB152 :
  %1361 = uitofp i32 %1352 to float		; visa id: 1328
  %1362 = fmul float %1222, %1361		; visa id: 1329
  %1363 = and i32 %144, 32768
  %1364 = icmp eq i32 %1363, 0		; visa id: 1330
  %1365 = select i1 %1364, i32 1, i32 -1		; visa id: 1332
  %1366 = sitofp i32 %1365 to float		; visa id: 1333
  %1367 = fmul float %1362, %1366		; visa id: 1334
  br label %.preheader.2, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1335

.preheader.2:                                     ; preds = %1360, %1353
; BB153 :
  %.sroa.368.5 = phi float [ %1367, %1360 ], [ %1359, %1353 ]
  %1368 = fmul float %.sroa.065.5, %1180		; visa id: 1336
  %1369 = fadd float %.sroa.25.0, %1368		; visa id: 1337
  %1370 = fmul float %.sroa.80.5, %1185		; visa id: 1338
  %1371 = fadd float %1369, %1370		; visa id: 1339
  %1372 = fmul float %.sroa.128.5, %1190		; visa id: 1340
  %1373 = fadd float %1371, %1372		; visa id: 1341
  %1374 = fmul float %.sroa.176.5, %1195		; visa id: 1342
  %1375 = fadd float %1373, %1374		; visa id: 1343
  %1376 = fmul float %.sroa.224.5, %1200		; visa id: 1344
  %1377 = fadd float %1375, %1376		; visa id: 1345
  %1378 = fmul float %.sroa.272.5, %1205		; visa id: 1346
  %1379 = fadd float %1377, %1378		; visa id: 1347
  %1380 = fmul float %.sroa.320.5, %1210		; visa id: 1348
  %1381 = fadd float %1379, %1380		; visa id: 1349
  %1382 = fmul float %.sroa.368.5, %1215		; visa id: 1350
  %1383 = fadd float %1381, %1382		; visa id: 1351
  %1384 = or i32 %257, 48		; visa id: 1352
  %1385 = zext i32 %1384 to i64		; visa id: 1353
  %1386 = add i64 %1385, %const_reg_qword2		; visa id: 1354
  %IntToPtr2600 = inttoptr i64 %1386 to ptr addrspace(1)		; visa id: 1355
  %vCastload601 = load i32, ptr addrspace(1) %IntToPtr2600, align 2		; visa id: 1355
  %1387 = add i64 %1386, 4
  %IntToPtr2602 = inttoptr i64 %1387 to ptr addrspace(1)
  %vCastload603 = load i32, ptr addrspace(1) %IntToPtr2602, align 2		; visa id: 1356
  %1388 = add i64 %1386, 8
  %IntToPtr2604 = inttoptr i64 %1388 to ptr addrspace(1)
  %vCastload605 = load i32, ptr addrspace(1) %IntToPtr2604, align 2		; visa id: 1357
  %1389 = add i64 %1386, 12
  %IntToPtr2606 = inttoptr i64 %1389 to ptr addrspace(1)
  %vCastload607 = load i32, ptr addrspace(1) %IntToPtr2606, align 2		; visa id: 1358
  %1390 = bitcast i32 %vCastload601 to <2 x i16>		; visa id: 1359
  %1391 = bitcast i32 %vCastload603 to <2 x i16>		; visa id: 1361
  %1392 = extractelement <2 x i16> %1390, i32 0		; visa id: 1363
  %1393 = extractelement <2 x i16> %1390, i32 1		; visa id: 1363
  %1394 = extractelement <2 x i16> %1391, i32 0		; visa id: 1363
  %1395 = extractelement <2 x i16> %1391, i32 1		; visa id: 1363
  %1396 = bitcast i32 %vCastload605 to <2 x i16>		; visa id: 1363
  %1397 = bitcast i32 %vCastload607 to <2 x i16>		; visa id: 1365
  %1398 = extractelement <2 x i16> %1396, i32 0		; visa id: 1367
  %1399 = extractelement <2 x i16> %1396, i32 1		; visa id: 1367
  %1400 = extractelement <2 x i16> %1397, i32 0		; visa id: 1367
  %1401 = extractelement <2 x i16> %1397, i32 1		; visa id: 1367
  %1402 = and i32 %218, 255		; visa id: 1367
  br i1 %1035, label %1410, label %1403, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1368

1403:                                             ; preds = %.preheader.2
; BB154 :
  %1404 = and i32 %123, 16777216
  %1405 = sub nsw i32 0, %1402, !spirv.Decorations !8798
  %1406 = icmp eq i32 %1404, 0		; visa id: 1370
  %1407 = select i1 %1406, i32 %1402, i32 %1405		; visa id: 1372
  %1408 = sitofp i32 %1407 to float		; visa id: 1373
  %1409 = fmul float %1028, %1408		; visa id: 1374
  br label %1418, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1375

1410:                                             ; preds = %.preheader.2
; BB155 :
  %1411 = uitofp i32 %1402 to float		; visa id: 1377
  %1412 = fmul float %1028, %1411		; visa id: 1378
  %1413 = and i32 %123, 16777216
  %1414 = icmp eq i32 %1413, 0		; visa id: 1379
  %1415 = select i1 %1414, i32 1, i32 -1		; visa id: 1381
  %1416 = sitofp i32 %1415 to float		; visa id: 1382
  %1417 = fmul float %1412, %1416		; visa id: 1383
  br label %1418, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1384

1418:                                             ; preds = %1410, %1403
; BB156 :
  %.sroa.065.6 = phi float [ %1417, %1410 ], [ %1409, %1403 ]
  %1419 = bitcast i32 %218 to <4 x i8>
  %1420 = extractelement <4 x i8> %1419, i32 1
  %1421 = zext i8 %1420 to i32		; visa id: 1385
  br i1 %1035, label %1429, label %1422, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1386

1422:                                             ; preds = %1418
; BB157 :
  %1423 = and i32 %123, 33554432
  %1424 = sub nsw i32 0, %1421, !spirv.Decorations !8798
  %1425 = icmp eq i32 %1423, 0		; visa id: 1388
  %1426 = select i1 %1425, i32 %1421, i32 %1424		; visa id: 1390
  %1427 = sitofp i32 %1426 to float		; visa id: 1391
  %1428 = fmul float %1028, %1427		; visa id: 1392
  br label %1437, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1393

1429:                                             ; preds = %1418
; BB158 :
  %1430 = uitofp i32 %1421 to float		; visa id: 1395
  %1431 = fmul float %1028, %1430		; visa id: 1396
  %1432 = and i32 %123, 33554432
  %1433 = icmp eq i32 %1432, 0		; visa id: 1397
  %1434 = select i1 %1433, i32 1, i32 -1		; visa id: 1399
  %1435 = sitofp i32 %1434 to float		; visa id: 1400
  %1436 = fmul float %1431, %1435		; visa id: 1401
  br label %1437, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1402

1437:                                             ; preds = %1429, %1422
; BB159 :
  %.sroa.80.6 = phi float [ %1436, %1429 ], [ %1428, %1422 ]
  %1438 = extractelement <4 x i8> %1419, i32 2
  %1439 = zext i8 %1438 to i32		; visa id: 1403
  br i1 %1035, label %1447, label %1440, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1404

1440:                                             ; preds = %1437
; BB160 :
  %1441 = and i32 %123, 67108864
  %1442 = sub nsw i32 0, %1439, !spirv.Decorations !8798
  %1443 = icmp eq i32 %1441, 0		; visa id: 1406
  %1444 = select i1 %1443, i32 %1439, i32 %1442		; visa id: 1408
  %1445 = sitofp i32 %1444 to float		; visa id: 1409
  %1446 = fmul float %1028, %1445		; visa id: 1410
  br label %1455, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1411

1447:                                             ; preds = %1437
; BB161 :
  %1448 = uitofp i32 %1439 to float		; visa id: 1413
  %1449 = fmul float %1028, %1448		; visa id: 1414
  %1450 = and i32 %123, 67108864
  %1451 = icmp eq i32 %1450, 0		; visa id: 1415
  %1452 = select i1 %1451, i32 1, i32 -1		; visa id: 1417
  %1453 = sitofp i32 %1452 to float		; visa id: 1418
  %1454 = fmul float %1449, %1453		; visa id: 1419
  br label %1455, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1420

1455:                                             ; preds = %1447, %1440
; BB162 :
  %.sroa.128.6 = phi float [ %1454, %1447 ], [ %1446, %1440 ]
  %1456 = lshr i32 %218, 24		; visa id: 1421
  br i1 %1035, label %1464, label %1457, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1422

1457:                                             ; preds = %1455
; BB163 :
  %1458 = and i32 %123, 134217728
  %1459 = sub nsw i32 0, %1456, !spirv.Decorations !8798
  %1460 = icmp eq i32 %1458, 0		; visa id: 1424
  %1461 = select i1 %1460, i32 %1456, i32 %1459		; visa id: 1426
  %1462 = sitofp i32 %1461 to float		; visa id: 1427
  %1463 = fmul float %1028, %1462		; visa id: 1428
  br label %1472, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1429

1464:                                             ; preds = %1455
; BB164 :
  %1465 = uitofp i32 %1456 to float		; visa id: 1431
  %1466 = fmul float %1028, %1465		; visa id: 1432
  %1467 = and i32 %123, 134217728
  %1468 = icmp eq i32 %1467, 0		; visa id: 1433
  %1469 = select i1 %1468, i32 1, i32 -1		; visa id: 1435
  %1470 = sitofp i32 %1469 to float		; visa id: 1436
  %1471 = fmul float %1466, %1470		; visa id: 1437
  br label %1472, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1438

1472:                                             ; preds = %1464, %1457
; BB165 :
  %.sroa.176.6 = phi float [ %1471, %1464 ], [ %1463, %1457 ]
  %1473 = and i32 %219, 255		; visa id: 1439
  br i1 %1035, label %1481, label %1474, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1440

1474:                                             ; preds = %1472
; BB166 :
  %1475 = and i32 %123, 268435456
  %1476 = sub nsw i32 0, %1473, !spirv.Decorations !8798
  %1477 = icmp eq i32 %1475, 0		; visa id: 1442
  %1478 = select i1 %1477, i32 %1473, i32 %1476		; visa id: 1444
  %1479 = sitofp i32 %1478 to float		; visa id: 1445
  %1480 = fmul float %1028, %1479		; visa id: 1446
  br label %1489, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1447

1481:                                             ; preds = %1472
; BB167 :
  %1482 = uitofp i32 %1473 to float		; visa id: 1449
  %1483 = fmul float %1028, %1482		; visa id: 1450
  %1484 = and i32 %123, 268435456
  %1485 = icmp eq i32 %1484, 0		; visa id: 1451
  %1486 = select i1 %1485, i32 1, i32 -1		; visa id: 1453
  %1487 = sitofp i32 %1486 to float		; visa id: 1454
  %1488 = fmul float %1483, %1487		; visa id: 1455
  br label %1489, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1456

1489:                                             ; preds = %1481, %1474
; BB168 :
  %.sroa.224.6 = phi float [ %1488, %1481 ], [ %1480, %1474 ]
  %1490 = bitcast i32 %219 to <4 x i8>
  %1491 = extractelement <4 x i8> %1490, i32 1
  %1492 = zext i8 %1491 to i32		; visa id: 1457
  br i1 %1035, label %1500, label %1493, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1458

1493:                                             ; preds = %1489
; BB169 :
  %1494 = and i32 %123, 536870912
  %1495 = sub nsw i32 0, %1492, !spirv.Decorations !8798
  %1496 = icmp eq i32 %1494, 0		; visa id: 1460
  %1497 = select i1 %1496, i32 %1492, i32 %1495		; visa id: 1462
  %1498 = sitofp i32 %1497 to float		; visa id: 1463
  %1499 = fmul float %1028, %1498		; visa id: 1464
  br label %1508, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1465

1500:                                             ; preds = %1489
; BB170 :
  %1501 = uitofp i32 %1492 to float		; visa id: 1467
  %1502 = fmul float %1028, %1501		; visa id: 1468
  %1503 = and i32 %123, 536870912
  %1504 = icmp eq i32 %1503, 0		; visa id: 1469
  %1505 = select i1 %1504, i32 1, i32 -1		; visa id: 1471
  %1506 = sitofp i32 %1505 to float		; visa id: 1472
  %1507 = fmul float %1502, %1506		; visa id: 1473
  br label %1508, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1474

1508:                                             ; preds = %1500, %1493
; BB171 :
  %.sroa.272.6 = phi float [ %1507, %1500 ], [ %1499, %1493 ]
  %1509 = extractelement <4 x i8> %1490, i32 2
  %1510 = zext i8 %1509 to i32		; visa id: 1475
  br i1 %1035, label %1518, label %1511, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1476

1511:                                             ; preds = %1508
; BB172 :
  %1512 = and i32 %123, 1073741824
  %1513 = sub nsw i32 0, %1510, !spirv.Decorations !8798
  %1514 = icmp eq i32 %1512, 0		; visa id: 1478
  %1515 = select i1 %1514, i32 %1510, i32 %1513		; visa id: 1480
  %1516 = sitofp i32 %1515 to float		; visa id: 1481
  %1517 = fmul float %1028, %1516		; visa id: 1482
  br label %1526, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1483

1518:                                             ; preds = %1508
; BB173 :
  %1519 = uitofp i32 %1510 to float		; visa id: 1485
  %1520 = fmul float %1028, %1519		; visa id: 1486
  %1521 = and i32 %123, 1073741824
  %1522 = icmp eq i32 %1521, 0		; visa id: 1487
  %1523 = select i1 %1522, i32 1, i32 -1		; visa id: 1489
  %1524 = sitofp i32 %1523 to float		; visa id: 1490
  %1525 = fmul float %1520, %1524		; visa id: 1491
  br label %1526, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1492

1526:                                             ; preds = %1518, %1511
; BB174 :
  %.sroa.320.6 = phi float [ %1525, %1518 ], [ %1517, %1511 ]
  %1527 = lshr i32 %219, 24		; visa id: 1493
  br i1 %1035, label %1534, label %1528, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1494

1528:                                             ; preds = %1526
; BB175 :
  %1529 = sub nsw i32 0, %1527, !spirv.Decorations !8798
  %1530 = icmp slt i32 %123, 0		; visa id: 1496
  %1531 = select i1 %1530, i32 %1529, i32 %1527		; visa id: 1497
  %1532 = sitofp i32 %1531 to float		; visa id: 1498
  %1533 = fmul float %1028, %1532		; visa id: 1499
  br label %1541, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1500

1534:                                             ; preds = %1526
; BB176 :
  %1535 = uitofp i32 %1527 to float		; visa id: 1502
  %1536 = fmul float %1028, %1535		; visa id: 1503
  %1537 = icmp sgt i32 %123, -1		; visa id: 1504
  %1538 = select i1 %1537, i32 1, i32 -1		; visa id: 1505
  %1539 = sitofp i32 %1538 to float		; visa id: 1506
  %1540 = fmul float %1536, %1539		; visa id: 1507
  br label %1541, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1508

1541:                                             ; preds = %1534, %1528
; BB177 :
  %.sroa.368.6 = phi float [ %1540, %1534 ], [ %1533, %1528 ]
  %1542 = zext i16 %1392 to i32		; visa id: 1509
  %1543 = shl nuw i32 %1542, 16		; visa id: 1510
  %1544 = bitcast i32 %1543 to float
  %1545 = fmul float %.sroa.065.6, %1544		; visa id: 1511
  %1546 = fadd float %.sroa.10.0, %1545		; visa id: 1512
  %1547 = zext i16 %1393 to i32		; visa id: 1513
  %1548 = shl nuw i32 %1547, 16		; visa id: 1514
  %1549 = bitcast i32 %1548 to float
  %1550 = fmul float %.sroa.80.6, %1549		; visa id: 1515
  %1551 = fadd float %1546, %1550		; visa id: 1516
  %1552 = zext i16 %1394 to i32		; visa id: 1517
  %1553 = shl nuw i32 %1552, 16		; visa id: 1518
  %1554 = bitcast i32 %1553 to float
  %1555 = fmul float %.sroa.128.6, %1554		; visa id: 1519
  %1556 = fadd float %1551, %1555		; visa id: 1520
  %1557 = zext i16 %1395 to i32		; visa id: 1521
  %1558 = shl nuw i32 %1557, 16		; visa id: 1522
  %1559 = bitcast i32 %1558 to float
  %1560 = fmul float %.sroa.176.6, %1559		; visa id: 1523
  %1561 = fadd float %1556, %1560		; visa id: 1524
  %1562 = zext i16 %1398 to i32		; visa id: 1525
  %1563 = shl nuw i32 %1562, 16		; visa id: 1526
  %1564 = bitcast i32 %1563 to float
  %1565 = fmul float %.sroa.224.6, %1564		; visa id: 1527
  %1566 = fadd float %1561, %1565		; visa id: 1528
  %1567 = zext i16 %1399 to i32		; visa id: 1529
  %1568 = shl nuw i32 %1567, 16		; visa id: 1530
  %1569 = bitcast i32 %1568 to float
  %1570 = fmul float %.sroa.272.6, %1569		; visa id: 1531
  %1571 = fadd float %1566, %1570		; visa id: 1532
  %1572 = zext i16 %1400 to i32		; visa id: 1533
  %1573 = shl nuw i32 %1572, 16		; visa id: 1534
  %1574 = bitcast i32 %1573 to float
  %1575 = fmul float %.sroa.320.6, %1574		; visa id: 1535
  %1576 = fadd float %1571, %1575		; visa id: 1536
  %1577 = zext i16 %1401 to i32		; visa id: 1537
  %1578 = shl nuw i32 %1577, 16		; visa id: 1538
  %1579 = bitcast i32 %1578 to float
  %1580 = fmul float %.sroa.368.6, %1579		; visa id: 1539
  %1581 = fadd float %1576, %1580		; visa id: 1540
  %1582 = and i32 %261, 255		; visa id: 1541
  br i1 %1226, label %1590, label %1583, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1542

1583:                                             ; preds = %1541
; BB178 :
  %1584 = and i32 %144, 16777216
  %1585 = sub nsw i32 0, %1582, !spirv.Decorations !8798
  %1586 = icmp eq i32 %1584, 0		; visa id: 1544
  %1587 = select i1 %1586, i32 %1582, i32 %1585		; visa id: 1546
  %1588 = sitofp i32 %1587 to float		; visa id: 1547
  %1589 = fmul float %1222, %1588		; visa id: 1548
  br label %1598, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1549

1590:                                             ; preds = %1541
; BB179 :
  %1591 = uitofp i32 %1582 to float		; visa id: 1551
  %1592 = fmul float %1222, %1591		; visa id: 1552
  %1593 = and i32 %144, 16777216
  %1594 = icmp eq i32 %1593, 0		; visa id: 1553
  %1595 = select i1 %1594, i32 1, i32 -1		; visa id: 1555
  %1596 = sitofp i32 %1595 to float		; visa id: 1556
  %1597 = fmul float %1592, %1596		; visa id: 1557
  br label %1598, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1558

1598:                                             ; preds = %1590, %1583
; BB180 :
  %.sroa.065.7 = phi float [ %1597, %1590 ], [ %1589, %1583 ]
  %1599 = bitcast i32 %261 to <4 x i8>
  %1600 = extractelement <4 x i8> %1599, i32 1
  %1601 = zext i8 %1600 to i32		; visa id: 1559
  br i1 %1226, label %1609, label %1602, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1560

1602:                                             ; preds = %1598
; BB181 :
  %1603 = and i32 %144, 33554432
  %1604 = sub nsw i32 0, %1601, !spirv.Decorations !8798
  %1605 = icmp eq i32 %1603, 0		; visa id: 1562
  %1606 = select i1 %1605, i32 %1601, i32 %1604		; visa id: 1564
  %1607 = sitofp i32 %1606 to float		; visa id: 1565
  %1608 = fmul float %1222, %1607		; visa id: 1566
  br label %1617, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1567

1609:                                             ; preds = %1598
; BB182 :
  %1610 = uitofp i32 %1601 to float		; visa id: 1569
  %1611 = fmul float %1222, %1610		; visa id: 1570
  %1612 = and i32 %144, 33554432
  %1613 = icmp eq i32 %1612, 0		; visa id: 1571
  %1614 = select i1 %1613, i32 1, i32 -1		; visa id: 1573
  %1615 = sitofp i32 %1614 to float		; visa id: 1574
  %1616 = fmul float %1611, %1615		; visa id: 1575
  br label %1617, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1576

1617:                                             ; preds = %1609, %1602
; BB183 :
  %.sroa.80.7 = phi float [ %1616, %1609 ], [ %1608, %1602 ]
  %1618 = extractelement <4 x i8> %1599, i32 2
  %1619 = zext i8 %1618 to i32		; visa id: 1577
  br i1 %1226, label %1627, label %1620, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1578

1620:                                             ; preds = %1617
; BB184 :
  %1621 = and i32 %144, 67108864
  %1622 = sub nsw i32 0, %1619, !spirv.Decorations !8798
  %1623 = icmp eq i32 %1621, 0		; visa id: 1580
  %1624 = select i1 %1623, i32 %1619, i32 %1622		; visa id: 1582
  %1625 = sitofp i32 %1624 to float		; visa id: 1583
  %1626 = fmul float %1222, %1625		; visa id: 1584
  br label %1635, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1585

1627:                                             ; preds = %1617
; BB185 :
  %1628 = uitofp i32 %1619 to float		; visa id: 1587
  %1629 = fmul float %1222, %1628		; visa id: 1588
  %1630 = and i32 %144, 67108864
  %1631 = icmp eq i32 %1630, 0		; visa id: 1589
  %1632 = select i1 %1631, i32 1, i32 -1		; visa id: 1591
  %1633 = sitofp i32 %1632 to float		; visa id: 1592
  %1634 = fmul float %1629, %1633		; visa id: 1593
  br label %1635, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1594

1635:                                             ; preds = %1627, %1620
; BB186 :
  %.sroa.128.7 = phi float [ %1634, %1627 ], [ %1626, %1620 ]
  %1636 = lshr i32 %261, 24		; visa id: 1595
  br i1 %1226, label %1644, label %1637, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1596

1637:                                             ; preds = %1635
; BB187 :
  %1638 = and i32 %144, 134217728
  %1639 = sub nsw i32 0, %1636, !spirv.Decorations !8798
  %1640 = icmp eq i32 %1638, 0		; visa id: 1598
  %1641 = select i1 %1640, i32 %1636, i32 %1639		; visa id: 1600
  %1642 = sitofp i32 %1641 to float		; visa id: 1601
  %1643 = fmul float %1222, %1642		; visa id: 1602
  br label %1652, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1603

1644:                                             ; preds = %1635
; BB188 :
  %1645 = uitofp i32 %1636 to float		; visa id: 1605
  %1646 = fmul float %1222, %1645		; visa id: 1606
  %1647 = and i32 %144, 134217728
  %1648 = icmp eq i32 %1647, 0		; visa id: 1607
  %1649 = select i1 %1648, i32 1, i32 -1		; visa id: 1609
  %1650 = sitofp i32 %1649 to float		; visa id: 1610
  %1651 = fmul float %1646, %1650		; visa id: 1611
  br label %1652, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1612

1652:                                             ; preds = %1644, %1637
; BB189 :
  %.sroa.176.7 = phi float [ %1651, %1644 ], [ %1643, %1637 ]
  %1653 = and i32 %262, 255		; visa id: 1613
  br i1 %1226, label %1661, label %1654, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1614

1654:                                             ; preds = %1652
; BB190 :
  %1655 = and i32 %144, 268435456
  %1656 = sub nsw i32 0, %1653, !spirv.Decorations !8798
  %1657 = icmp eq i32 %1655, 0		; visa id: 1616
  %1658 = select i1 %1657, i32 %1653, i32 %1656		; visa id: 1618
  %1659 = sitofp i32 %1658 to float		; visa id: 1619
  %1660 = fmul float %1222, %1659		; visa id: 1620
  br label %1669, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1621

1661:                                             ; preds = %1652
; BB191 :
  %1662 = uitofp i32 %1653 to float		; visa id: 1623
  %1663 = fmul float %1222, %1662		; visa id: 1624
  %1664 = and i32 %144, 268435456
  %1665 = icmp eq i32 %1664, 0		; visa id: 1625
  %1666 = select i1 %1665, i32 1, i32 -1		; visa id: 1627
  %1667 = sitofp i32 %1666 to float		; visa id: 1628
  %1668 = fmul float %1663, %1667		; visa id: 1629
  br label %1669, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1630

1669:                                             ; preds = %1661, %1654
; BB192 :
  %.sroa.224.7 = phi float [ %1668, %1661 ], [ %1660, %1654 ]
  %1670 = bitcast i32 %262 to <4 x i8>
  %1671 = extractelement <4 x i8> %1670, i32 1
  %1672 = zext i8 %1671 to i32		; visa id: 1631
  br i1 %1226, label %1680, label %1673, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1632

1673:                                             ; preds = %1669
; BB193 :
  %1674 = and i32 %144, 536870912
  %1675 = sub nsw i32 0, %1672, !spirv.Decorations !8798
  %1676 = icmp eq i32 %1674, 0		; visa id: 1634
  %1677 = select i1 %1676, i32 %1672, i32 %1675		; visa id: 1636
  %1678 = sitofp i32 %1677 to float		; visa id: 1637
  %1679 = fmul float %1222, %1678		; visa id: 1638
  br label %1688, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1639

1680:                                             ; preds = %1669
; BB194 :
  %1681 = uitofp i32 %1672 to float		; visa id: 1641
  %1682 = fmul float %1222, %1681		; visa id: 1642
  %1683 = and i32 %144, 536870912
  %1684 = icmp eq i32 %1683, 0		; visa id: 1643
  %1685 = select i1 %1684, i32 1, i32 -1		; visa id: 1645
  %1686 = sitofp i32 %1685 to float		; visa id: 1646
  %1687 = fmul float %1682, %1686		; visa id: 1647
  br label %1688, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1648

1688:                                             ; preds = %1680, %1673
; BB195 :
  %.sroa.272.7 = phi float [ %1687, %1680 ], [ %1679, %1673 ]
  %1689 = extractelement <4 x i8> %1670, i32 2
  %1690 = zext i8 %1689 to i32		; visa id: 1649
  br i1 %1226, label %1698, label %1691, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1650

1691:                                             ; preds = %1688
; BB196 :
  %1692 = and i32 %144, 1073741824
  %1693 = sub nsw i32 0, %1690, !spirv.Decorations !8798
  %1694 = icmp eq i32 %1692, 0		; visa id: 1652
  %1695 = select i1 %1694, i32 %1690, i32 %1693		; visa id: 1654
  %1696 = sitofp i32 %1695 to float		; visa id: 1655
  %1697 = fmul float %1222, %1696		; visa id: 1656
  br label %1706, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1657

1698:                                             ; preds = %1688
; BB197 :
  %1699 = uitofp i32 %1690 to float		; visa id: 1659
  %1700 = fmul float %1222, %1699		; visa id: 1660
  %1701 = and i32 %144, 1073741824
  %1702 = icmp eq i32 %1701, 0		; visa id: 1661
  %1703 = select i1 %1702, i32 1, i32 -1		; visa id: 1663
  %1704 = sitofp i32 %1703 to float		; visa id: 1664
  %1705 = fmul float %1700, %1704		; visa id: 1665
  br label %1706, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1666

1706:                                             ; preds = %1698, %1691
; BB198 :
  %.sroa.320.7 = phi float [ %1705, %1698 ], [ %1697, %1691 ]
  %1707 = lshr i32 %262, 24		; visa id: 1667
  br i1 %1226, label %1714, label %1708, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1668

1708:                                             ; preds = %1706
; BB199 :
  %1709 = sub nsw i32 0, %1707, !spirv.Decorations !8798
  %1710 = icmp slt i32 %144, 0		; visa id: 1670
  %1711 = select i1 %1710, i32 %1709, i32 %1707		; visa id: 1671
  %1712 = sitofp i32 %1711 to float		; visa id: 1672
  %1713 = fmul float %1222, %1712		; visa id: 1673
  br label %.preheader.3, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1674

1714:                                             ; preds = %1706
; BB200 :
  %1715 = uitofp i32 %1707 to float		; visa id: 1676
  %1716 = fmul float %1222, %1715		; visa id: 1677
  %1717 = icmp sgt i32 %144, -1		; visa id: 1678
  %1718 = select i1 %1717, i32 1, i32 -1		; visa id: 1679
  %1719 = sitofp i32 %1718 to float		; visa id: 1680
  %1720 = fmul float %1716, %1719		; visa id: 1681
  br label %.preheader.3, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1682

.preheader.3:                                     ; preds = %1714, %1708
; BB201 :
  %.sroa.368.7 = phi float [ %1720, %1714 ], [ %1713, %1708 ]
  %1721 = fmul float %.sroa.065.7, %1544		; visa id: 1683
  %1722 = fadd float %.sroa.27.0, %1721		; visa id: 1684
  %1723 = fmul float %.sroa.80.7, %1549		; visa id: 1685
  %1724 = fadd float %1722, %1723		; visa id: 1686
  %1725 = fmul float %.sroa.128.7, %1554		; visa id: 1687
  %1726 = fadd float %1724, %1725		; visa id: 1688
  %1727 = fmul float %.sroa.176.7, %1559		; visa id: 1689
  %1728 = fadd float %1726, %1727		; visa id: 1690
  %1729 = fmul float %.sroa.224.7, %1564		; visa id: 1691
  %1730 = fadd float %1728, %1729		; visa id: 1692
  %1731 = fmul float %.sroa.272.7, %1569		; visa id: 1693
  %1732 = fadd float %1730, %1731		; visa id: 1694
  %1733 = fmul float %.sroa.320.7, %1574		; visa id: 1695
  %1734 = fadd float %1732, %1733		; visa id: 1696
  %1735 = fmul float %.sroa.368.7, %1579		; visa id: 1697
  %1736 = fadd float %1734, %1735		; visa id: 1698
  %1737 = lshr i16 %134, 8		; visa id: 1699
  %1738 = and i32 %124, 255
  %1739 = and i32 %160, 768		; visa id: 1700
  %1740 = or i32 %1738, %1739		; visa id: 1701
  %1741 = shl nuw nsw i32 %1740, 3, !spirv.Decorations !8791		; visa id: 1702
  %1742 = zext i32 %1741 to i64		; visa id: 1703
  %1743 = add i64 %sink_, %1742		; visa id: 1704
  %1744 = inttoptr i64 %1743 to ptr addrspace(1)		; visa id: 1705
  %1745 = load <2 x i32>, ptr addrspace(1) %1744, align 4		; visa id: 1705
  %1746 = bitcast i32 %124 to <4 x i8>
  %1747 = extractelement <4 x i8> %1746, i32 2
  %1748 = lshr i32 %160, 2		; visa id: 1706
  %1749 = and i32 %1748, 768
  %1750 = zext i8 %1747 to i32		; visa id: 1707
  %1751 = or i32 %1750, %1749		; visa id: 1708
  %1752 = shl nuw nsw i32 %1751, 3, !spirv.Decorations !8791		; visa id: 1709
  %1753 = zext i32 %1752 to i64		; visa id: 1710
  %1754 = add i64 %sink_, %1753		; visa id: 1711
  %1755 = inttoptr i64 %1754 to ptr addrspace(1)		; visa id: 1712
  %1756 = load <2 x i32>, ptr addrspace(1) %1755, align 4		; visa id: 1712
  %1757 = extractelement <2 x i32> %1745, i32 0		; visa id: 1713
  %1758 = extractelement <2 x i32> %1745, i32 1		; visa id: 1713
  %1759 = extractelement <2 x i32> %1756, i32 0		; visa id: 1713
  %1760 = extractelement <2 x i32> %1756, i32 1		; visa id: 1713
  %1761 = and i32 %125, 255
  %1762 = lshr i32 %160, 4		; visa id: 1713
  %1763 = and i32 %1762, 768		; visa id: 1714
  %1764 = or i32 %1761, %1763		; visa id: 1715
  %1765 = shl nuw nsw i32 %1764, 3, !spirv.Decorations !8791		; visa id: 1716
  %1766 = zext i32 %1765 to i64		; visa id: 1717
  %1767 = add i64 %sink_, %1766		; visa id: 1718
  %1768 = inttoptr i64 %1767 to ptr addrspace(1)		; visa id: 1719
  %1769 = load <2 x i32>, ptr addrspace(1) %1768, align 4		; visa id: 1719
  %1770 = bitcast i32 %125 to <4 x i8>
  %1771 = extractelement <4 x i8> %1770, i32 2
  %1772 = lshr i32 %160, 6		; visa id: 1720
  %1773 = and i32 %1772, 768
  %1774 = zext i8 %1771 to i32		; visa id: 1721
  %1775 = or i32 %1774, %1773		; visa id: 1722
  %1776 = shl nuw nsw i32 %1775, 3, !spirv.Decorations !8791		; visa id: 1723
  %1777 = zext i32 %1776 to i64		; visa id: 1724
  %1778 = add i64 %sink_, %1777		; visa id: 1725
  %1779 = inttoptr i64 %1778 to ptr addrspace(1)		; visa id: 1726
  %1780 = load <2 x i32>, ptr addrspace(1) %1779, align 4		; visa id: 1726
  %1781 = extractelement <2 x i32> %1769, i32 0		; visa id: 1727
  %1782 = extractelement <2 x i32> %1769, i32 1		; visa id: 1727
  %1783 = extractelement <2 x i32> %1780, i32 0		; visa id: 1727
  %1784 = extractelement <2 x i32> %1780, i32 1		; visa id: 1727
  %1785 = lshr i16 %154, 8		; visa id: 1727
  %1786 = and i32 %145, 255
  %1787 = and i32 %209, 768		; visa id: 1728
  %1788 = or i32 %1786, %1787		; visa id: 1729
  %1789 = shl nuw nsw i32 %1788, 3, !spirv.Decorations !8791		; visa id: 1730
  %1790 = zext i32 %1789 to i64		; visa id: 1731
  %1791 = add i64 %sink_, %1790		; visa id: 1732
  %1792 = inttoptr i64 %1791 to ptr addrspace(1)		; visa id: 1733
  %1793 = load <2 x i32>, ptr addrspace(1) %1792, align 4		; visa id: 1733
  %1794 = bitcast i32 %145 to <4 x i8>
  %1795 = extractelement <4 x i8> %1794, i32 2
  %1796 = lshr i32 %209, 2		; visa id: 1734
  %1797 = and i32 %1796, 768
  %1798 = zext i8 %1795 to i32		; visa id: 1735
  %1799 = or i32 %1798, %1797		; visa id: 1736
  %1800 = shl nuw nsw i32 %1799, 3, !spirv.Decorations !8791		; visa id: 1737
  %1801 = zext i32 %1800 to i64		; visa id: 1738
  %1802 = add i64 %sink_, %1801		; visa id: 1739
  %1803 = inttoptr i64 %1802 to ptr addrspace(1)		; visa id: 1740
  %1804 = load <2 x i32>, ptr addrspace(1) %1803, align 4		; visa id: 1740
  %1805 = extractelement <2 x i32> %1793, i32 0		; visa id: 1741
  %1806 = extractelement <2 x i32> %1793, i32 1		; visa id: 1741
  %1807 = extractelement <2 x i32> %1804, i32 0		; visa id: 1741
  %1808 = extractelement <2 x i32> %1804, i32 1		; visa id: 1741
  %1809 = and i32 %146, 255
  %1810 = lshr i32 %209, 4		; visa id: 1741
  %1811 = and i32 %1810, 768		; visa id: 1742
  %1812 = or i32 %1809, %1811		; visa id: 1743
  %1813 = shl nuw nsw i32 %1812, 3, !spirv.Decorations !8791		; visa id: 1744
  %1814 = zext i32 %1813 to i64		; visa id: 1745
  %1815 = add i64 %sink_, %1814		; visa id: 1746
  %1816 = inttoptr i64 %1815 to ptr addrspace(1)		; visa id: 1747
  %1817 = load <2 x i32>, ptr addrspace(1) %1816, align 4		; visa id: 1747
  %1818 = bitcast i32 %146 to <4 x i8>
  %1819 = extractelement <4 x i8> %1818, i32 2
  %1820 = lshr i32 %209, 6		; visa id: 1748
  %1821 = and i32 %1820, 768
  %1822 = zext i8 %1819 to i32		; visa id: 1749
  %1823 = or i32 %1822, %1821		; visa id: 1750
  %1824 = shl nuw nsw i32 %1823, 3, !spirv.Decorations !8791		; visa id: 1751
  %1825 = zext i32 %1824 to i64		; visa id: 1752
  %1826 = add i64 %sink_, %1825		; visa id: 1753
  %1827 = inttoptr i64 %1826 to ptr addrspace(1)		; visa id: 1754
  %1828 = load <2 x i32>, ptr addrspace(1) %1827, align 4		; visa id: 1754
  %1829 = extractelement <2 x i32> %1817, i32 0		; visa id: 1755
  %1830 = extractelement <2 x i32> %1817, i32 1		; visa id: 1755
  %1831 = extractelement <2 x i32> %1828, i32 0		; visa id: 1755
  %1832 = extractelement <2 x i32> %1828, i32 1		; visa id: 1755
  %1833 = or i32 %257, 64		; visa id: 1755
  %1834 = zext i32 %1833 to i64		; visa id: 1756
  %1835 = add i64 %1834, %const_reg_qword2		; visa id: 1757
  %IntToPtr2608 = inttoptr i64 %1835 to ptr addrspace(1)		; visa id: 1758
  %vCastload609 = load i32, ptr addrspace(1) %IntToPtr2608, align 2		; visa id: 1758
  %1836 = add i64 %1835, 4
  %IntToPtr2610 = inttoptr i64 %1836 to ptr addrspace(1)
  %vCastload611 = load i32, ptr addrspace(1) %IntToPtr2610, align 2		; visa id: 1759
  %1837 = add i64 %1835, 8
  %IntToPtr2612 = inttoptr i64 %1837 to ptr addrspace(1)
  %vCastload613 = load i32, ptr addrspace(1) %IntToPtr2612, align 2		; visa id: 1760
  %1838 = add i64 %1835, 12
  %IntToPtr2614 = inttoptr i64 %1838 to ptr addrspace(1)
  %vCastload615 = load i32, ptr addrspace(1) %IntToPtr2614, align 2		; visa id: 1761
  %1839 = bitcast i32 %vCastload609 to <2 x i16>		; visa id: 1762
  %1840 = bitcast i32 %vCastload611 to <2 x i16>		; visa id: 1764
  %1841 = extractelement <2 x i16> %1839, i32 0		; visa id: 1766
  %1842 = extractelement <2 x i16> %1839, i32 1		; visa id: 1766
  %1843 = extractelement <2 x i16> %1840, i32 0		; visa id: 1766
  %1844 = extractelement <2 x i16> %1840, i32 1		; visa id: 1766
  %1845 = bitcast i32 %vCastload613 to <2 x i16>		; visa id: 1766
  %1846 = bitcast i32 %vCastload615 to <2 x i16>		; visa id: 1768
  %1847 = extractelement <2 x i16> %1845, i32 0		; visa id: 1770
  %1848 = extractelement <2 x i16> %1845, i32 1		; visa id: 1770
  %1849 = extractelement <2 x i16> %1846, i32 0		; visa id: 1770
  %1850 = extractelement <2 x i16> %1846, i32 1		; visa id: 1770
  %1851 = zext i16 %1737 to i32		; visa id: 1770
  %1852 = and i32 %1851, 15		; visa id: 1771
  %1853 = uitofp i32 %1852 to float		; visa id: 1772
  %1854 = fadd float %1853, 5.000000e-01		; visa id: 1773
  %1855 = fmul float %139, %1854		; visa id: 1774
  %1856 = fmul float %1855, 2.500000e-01		; visa id: 1775
  %1857 = bitcast float %1856 to i32
  %1858 = and i32 %1857, 2147483647		; visa id: 1776
  %1859 = icmp ugt i32 %1858, 2139095040
  %1860 = fcmp oeq float %286, 0x7FF0000000000000		; visa id: 1777
  %1861 = fcmp une float %286, %286
  %1862 = or i1 %1861, %1860		; visa id: 1778
  %1863 = or i1 %1862, %1859		; visa id: 1780
  %1864 = and i32 %1757, 255		; visa id: 1782
  br i1 %1863, label %1872, label %1865, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1783

1865:                                             ; preds = %.preheader.3
; BB202 :
  %1866 = and i32 %124, 256
  %1867 = sub nsw i32 0, %1864, !spirv.Decorations !8798
  %1868 = icmp eq i32 %1866, 0		; visa id: 1785
  %1869 = select i1 %1868, i32 %1864, i32 %1867		; visa id: 1787
  %1870 = sitofp i32 %1869 to float		; visa id: 1788
  %1871 = fmul float %1856, %1870		; visa id: 1789
  br label %1880, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1790

1872:                                             ; preds = %.preheader.3
; BB203 :
  %1873 = uitofp i32 %1864 to float		; visa id: 1792
  %1874 = fmul float %1856, %1873		; visa id: 1793
  %1875 = and i32 %124, 256
  %1876 = icmp eq i32 %1875, 0		; visa id: 1794
  %1877 = select i1 %1876, i32 1, i32 -1		; visa id: 1796
  %1878 = sitofp i32 %1877 to float		; visa id: 1797
  %1879 = fmul float %1874, %1878		; visa id: 1798
  br label %1880, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1799

1880:                                             ; preds = %1872, %1865
; BB204 :
  %.sroa.065.8 = phi float [ %1879, %1872 ], [ %1871, %1865 ]
  %1881 = bitcast i32 %1757 to <4 x i8>
  %1882 = extractelement <4 x i8> %1881, i32 1
  %1883 = zext i8 %1882 to i32		; visa id: 1800
  br i1 %1863, label %1891, label %1884, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1801

1884:                                             ; preds = %1880
; BB205 :
  %1885 = and i32 %124, 512
  %1886 = sub nsw i32 0, %1883, !spirv.Decorations !8798
  %1887 = icmp eq i32 %1885, 0		; visa id: 1803
  %1888 = select i1 %1887, i32 %1883, i32 %1886		; visa id: 1805
  %1889 = sitofp i32 %1888 to float		; visa id: 1806
  %1890 = fmul float %1856, %1889		; visa id: 1807
  br label %1899, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1808

1891:                                             ; preds = %1880
; BB206 :
  %1892 = uitofp i32 %1883 to float		; visa id: 1810
  %1893 = fmul float %1856, %1892		; visa id: 1811
  %1894 = and i32 %124, 512
  %1895 = icmp eq i32 %1894, 0		; visa id: 1812
  %1896 = select i1 %1895, i32 1, i32 -1		; visa id: 1814
  %1897 = sitofp i32 %1896 to float		; visa id: 1815
  %1898 = fmul float %1893, %1897		; visa id: 1816
  br label %1899, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1817

1899:                                             ; preds = %1891, %1884
; BB207 :
  %.sroa.80.8 = phi float [ %1898, %1891 ], [ %1890, %1884 ]
  %1900 = extractelement <4 x i8> %1881, i32 2
  %1901 = zext i8 %1900 to i32		; visa id: 1818
  br i1 %1863, label %1909, label %1902, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1819

1902:                                             ; preds = %1899
; BB208 :
  %1903 = and i32 %124, 1024
  %1904 = sub nsw i32 0, %1901, !spirv.Decorations !8798
  %1905 = icmp eq i32 %1903, 0		; visa id: 1821
  %1906 = select i1 %1905, i32 %1901, i32 %1904		; visa id: 1823
  %1907 = sitofp i32 %1906 to float		; visa id: 1824
  %1908 = fmul float %1856, %1907		; visa id: 1825
  br label %1917, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1826

1909:                                             ; preds = %1899
; BB209 :
  %1910 = uitofp i32 %1901 to float		; visa id: 1828
  %1911 = fmul float %1856, %1910		; visa id: 1829
  %1912 = and i32 %124, 1024
  %1913 = icmp eq i32 %1912, 0		; visa id: 1830
  %1914 = select i1 %1913, i32 1, i32 -1		; visa id: 1832
  %1915 = sitofp i32 %1914 to float		; visa id: 1833
  %1916 = fmul float %1911, %1915		; visa id: 1834
  br label %1917, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1835

1917:                                             ; preds = %1909, %1902
; BB210 :
  %.sroa.128.8 = phi float [ %1916, %1909 ], [ %1908, %1902 ]
  %1918 = lshr i32 %1757, 24		; visa id: 1836
  br i1 %1863, label %1926, label %1919, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1837

1919:                                             ; preds = %1917
; BB211 :
  %1920 = and i32 %124, 2048
  %1921 = sub nsw i32 0, %1918, !spirv.Decorations !8798
  %1922 = icmp eq i32 %1920, 0		; visa id: 1839
  %1923 = select i1 %1922, i32 %1918, i32 %1921		; visa id: 1841
  %1924 = sitofp i32 %1923 to float		; visa id: 1842
  %1925 = fmul float %1856, %1924		; visa id: 1843
  br label %1934, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1844

1926:                                             ; preds = %1917
; BB212 :
  %1927 = uitofp i32 %1918 to float		; visa id: 1846
  %1928 = fmul float %1856, %1927		; visa id: 1847
  %1929 = and i32 %124, 2048
  %1930 = icmp eq i32 %1929, 0		; visa id: 1848
  %1931 = select i1 %1930, i32 1, i32 -1		; visa id: 1850
  %1932 = sitofp i32 %1931 to float		; visa id: 1851
  %1933 = fmul float %1928, %1932		; visa id: 1852
  br label %1934, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1853

1934:                                             ; preds = %1926, %1919
; BB213 :
  %.sroa.176.8 = phi float [ %1933, %1926 ], [ %1925, %1919 ]
  %1935 = and i32 %1758, 255		; visa id: 1854
  br i1 %1863, label %1943, label %1936, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1855

1936:                                             ; preds = %1934
; BB214 :
  %1937 = and i32 %124, 4096
  %1938 = sub nsw i32 0, %1935, !spirv.Decorations !8798
  %1939 = icmp eq i32 %1937, 0		; visa id: 1857
  %1940 = select i1 %1939, i32 %1935, i32 %1938		; visa id: 1859
  %1941 = sitofp i32 %1940 to float		; visa id: 1860
  %1942 = fmul float %1856, %1941		; visa id: 1861
  br label %1951, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1862

1943:                                             ; preds = %1934
; BB215 :
  %1944 = uitofp i32 %1935 to float		; visa id: 1864
  %1945 = fmul float %1856, %1944		; visa id: 1865
  %1946 = and i32 %124, 4096
  %1947 = icmp eq i32 %1946, 0		; visa id: 1866
  %1948 = select i1 %1947, i32 1, i32 -1		; visa id: 1868
  %1949 = sitofp i32 %1948 to float		; visa id: 1869
  %1950 = fmul float %1945, %1949		; visa id: 1870
  br label %1951, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1871

1951:                                             ; preds = %1943, %1936
; BB216 :
  %.sroa.224.8 = phi float [ %1950, %1943 ], [ %1942, %1936 ]
  %1952 = bitcast i32 %1758 to <4 x i8>
  %1953 = extractelement <4 x i8> %1952, i32 1
  %1954 = zext i8 %1953 to i32		; visa id: 1872
  br i1 %1863, label %1962, label %1955, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1873

1955:                                             ; preds = %1951
; BB217 :
  %1956 = and i32 %124, 8192
  %1957 = sub nsw i32 0, %1954, !spirv.Decorations !8798
  %1958 = icmp eq i32 %1956, 0		; visa id: 1875
  %1959 = select i1 %1958, i32 %1954, i32 %1957		; visa id: 1877
  %1960 = sitofp i32 %1959 to float		; visa id: 1878
  %1961 = fmul float %1856, %1960		; visa id: 1879
  br label %1970, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1880

1962:                                             ; preds = %1951
; BB218 :
  %1963 = uitofp i32 %1954 to float		; visa id: 1882
  %1964 = fmul float %1856, %1963		; visa id: 1883
  %1965 = and i32 %124, 8192
  %1966 = icmp eq i32 %1965, 0		; visa id: 1884
  %1967 = select i1 %1966, i32 1, i32 -1		; visa id: 1886
  %1968 = sitofp i32 %1967 to float		; visa id: 1887
  %1969 = fmul float %1964, %1968		; visa id: 1888
  br label %1970, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1889

1970:                                             ; preds = %1962, %1955
; BB219 :
  %.sroa.272.8 = phi float [ %1969, %1962 ], [ %1961, %1955 ]
  %1971 = extractelement <4 x i8> %1952, i32 2
  %1972 = zext i8 %1971 to i32		; visa id: 1890
  br i1 %1863, label %1980, label %1973, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1891

1973:                                             ; preds = %1970
; BB220 :
  %1974 = and i32 %124, 16384
  %1975 = sub nsw i32 0, %1972, !spirv.Decorations !8798
  %1976 = icmp eq i32 %1974, 0		; visa id: 1893
  %1977 = select i1 %1976, i32 %1972, i32 %1975		; visa id: 1895
  %1978 = sitofp i32 %1977 to float		; visa id: 1896
  %1979 = fmul float %1856, %1978		; visa id: 1897
  br label %1988, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1898

1980:                                             ; preds = %1970
; BB221 :
  %1981 = uitofp i32 %1972 to float		; visa id: 1900
  %1982 = fmul float %1856, %1981		; visa id: 1901
  %1983 = and i32 %124, 16384
  %1984 = icmp eq i32 %1983, 0		; visa id: 1902
  %1985 = select i1 %1984, i32 1, i32 -1		; visa id: 1904
  %1986 = sitofp i32 %1985 to float		; visa id: 1905
  %1987 = fmul float %1982, %1986		; visa id: 1906
  br label %1988, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1907

1988:                                             ; preds = %1980, %1973
; BB222 :
  %.sroa.320.8 = phi float [ %1987, %1980 ], [ %1979, %1973 ]
  %1989 = lshr i32 %1758, 24		; visa id: 1908
  br i1 %1863, label %1997, label %1990, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1909

1990:                                             ; preds = %1988
; BB223 :
  %1991 = and i32 %124, 32768
  %1992 = sub nsw i32 0, %1989, !spirv.Decorations !8798
  %1993 = icmp eq i32 %1991, 0		; visa id: 1911
  %1994 = select i1 %1993, i32 %1989, i32 %1992		; visa id: 1913
  %1995 = sitofp i32 %1994 to float		; visa id: 1914
  %1996 = fmul float %1856, %1995		; visa id: 1915
  br label %2005, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1916

1997:                                             ; preds = %1988
; BB224 :
  %1998 = uitofp i32 %1989 to float		; visa id: 1918
  %1999 = fmul float %1856, %1998		; visa id: 1919
  %2000 = and i32 %124, 32768
  %2001 = icmp eq i32 %2000, 0		; visa id: 1920
  %2002 = select i1 %2001, i32 1, i32 -1		; visa id: 1922
  %2003 = sitofp i32 %2002 to float		; visa id: 1923
  %2004 = fmul float %1999, %2003		; visa id: 1924
  br label %2005, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1925

2005:                                             ; preds = %1997, %1990
; BB225 :
  %.sroa.368.8 = phi float [ %2004, %1997 ], [ %1996, %1990 ]
  %2006 = zext i16 %1841 to i32		; visa id: 1926
  %2007 = shl nuw i32 %2006, 16		; visa id: 1927
  %2008 = bitcast i32 %2007 to float
  %2009 = fmul float %.sroa.065.8, %2008		; visa id: 1928
  %2010 = fadd float %.sroa.12.0, %2009		; visa id: 1929
  %2011 = zext i16 %1842 to i32		; visa id: 1930
  %2012 = shl nuw i32 %2011, 16		; visa id: 1931
  %2013 = bitcast i32 %2012 to float
  %2014 = fmul float %.sroa.80.8, %2013		; visa id: 1932
  %2015 = fadd float %2010, %2014		; visa id: 1933
  %2016 = zext i16 %1843 to i32		; visa id: 1934
  %2017 = shl nuw i32 %2016, 16		; visa id: 1935
  %2018 = bitcast i32 %2017 to float
  %2019 = fmul float %.sroa.128.8, %2018		; visa id: 1936
  %2020 = fadd float %2015, %2019		; visa id: 1937
  %2021 = zext i16 %1844 to i32		; visa id: 1938
  %2022 = shl nuw i32 %2021, 16		; visa id: 1939
  %2023 = bitcast i32 %2022 to float
  %2024 = fmul float %.sroa.176.8, %2023		; visa id: 1940
  %2025 = fadd float %2020, %2024		; visa id: 1941
  %2026 = zext i16 %1847 to i32		; visa id: 1942
  %2027 = shl nuw i32 %2026, 16		; visa id: 1943
  %2028 = bitcast i32 %2027 to float
  %2029 = fmul float %.sroa.224.8, %2028		; visa id: 1944
  %2030 = fadd float %2025, %2029		; visa id: 1945
  %2031 = zext i16 %1848 to i32		; visa id: 1946
  %2032 = shl nuw i32 %2031, 16		; visa id: 1947
  %2033 = bitcast i32 %2032 to float
  %2034 = fmul float %.sroa.272.8, %2033		; visa id: 1948
  %2035 = fadd float %2030, %2034		; visa id: 1949
  %2036 = zext i16 %1849 to i32		; visa id: 1950
  %2037 = shl nuw i32 %2036, 16		; visa id: 1951
  %2038 = bitcast i32 %2037 to float
  %2039 = fmul float %.sroa.320.8, %2038		; visa id: 1952
  %2040 = fadd float %2035, %2039		; visa id: 1953
  %2041 = zext i16 %1850 to i32		; visa id: 1954
  %2042 = shl nuw i32 %2041, 16		; visa id: 1955
  %2043 = bitcast i32 %2042 to float
  %2044 = fmul float %.sroa.368.8, %2043		; visa id: 1956
  %2045 = fadd float %2040, %2044		; visa id: 1957
  %2046 = zext i16 %1785 to i32		; visa id: 1958
  %2047 = and i32 %2046, 15		; visa id: 1959
  %2048 = uitofp i32 %2047 to float		; visa id: 1960
  %2049 = fadd float %2048, 5.000000e-01		; visa id: 1961
  %2050 = fmul float %158, %2049		; visa id: 1962
  %2051 = fmul float %2050, 2.500000e-01		; visa id: 1963
  %2052 = bitcast float %2051 to i32
  %2053 = and i32 %2052, 2147483647		; visa id: 1964
  %2054 = icmp ugt i32 %2053, 2139095040		; visa id: 1965
  %2055 = or i1 %488, %2054		; visa id: 1966
  %2056 = and i32 %1805, 255		; visa id: 1967
  br i1 %2055, label %2064, label %2057, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1968

2057:                                             ; preds = %2005
; BB226 :
  %2058 = and i32 %145, 256
  %2059 = sub nsw i32 0, %2056, !spirv.Decorations !8798
  %2060 = icmp eq i32 %2058, 0		; visa id: 1970
  %2061 = select i1 %2060, i32 %2056, i32 %2059		; visa id: 1972
  %2062 = sitofp i32 %2061 to float		; visa id: 1973
  %2063 = fmul float %2051, %2062		; visa id: 1974
  br label %2072, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1975

2064:                                             ; preds = %2005
; BB227 :
  %2065 = uitofp i32 %2056 to float		; visa id: 1977
  %2066 = fmul float %2051, %2065		; visa id: 1978
  %2067 = and i32 %145, 256
  %2068 = icmp eq i32 %2067, 0		; visa id: 1979
  %2069 = select i1 %2068, i32 1, i32 -1		; visa id: 1981
  %2070 = sitofp i32 %2069 to float		; visa id: 1982
  %2071 = fmul float %2066, %2070		; visa id: 1983
  br label %2072, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1984

2072:                                             ; preds = %2064, %2057
; BB228 :
  %.sroa.065.9 = phi float [ %2071, %2064 ], [ %2063, %2057 ]
  %2073 = bitcast i32 %1805 to <4 x i8>
  %2074 = extractelement <4 x i8> %2073, i32 1
  %2075 = zext i8 %2074 to i32		; visa id: 1985
  br i1 %2055, label %2083, label %2076, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1986

2076:                                             ; preds = %2072
; BB229 :
  %2077 = and i32 %145, 512
  %2078 = sub nsw i32 0, %2075, !spirv.Decorations !8798
  %2079 = icmp eq i32 %2077, 0		; visa id: 1988
  %2080 = select i1 %2079, i32 %2075, i32 %2078		; visa id: 1990
  %2081 = sitofp i32 %2080 to float		; visa id: 1991
  %2082 = fmul float %2051, %2081		; visa id: 1992
  br label %2091, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1993

2083:                                             ; preds = %2072
; BB230 :
  %2084 = uitofp i32 %2075 to float		; visa id: 1995
  %2085 = fmul float %2051, %2084		; visa id: 1996
  %2086 = and i32 %145, 512
  %2087 = icmp eq i32 %2086, 0		; visa id: 1997
  %2088 = select i1 %2087, i32 1, i32 -1		; visa id: 1999
  %2089 = sitofp i32 %2088 to float		; visa id: 2000
  %2090 = fmul float %2085, %2089		; visa id: 2001
  br label %2091, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2002

2091:                                             ; preds = %2083, %2076
; BB231 :
  %.sroa.80.9 = phi float [ %2090, %2083 ], [ %2082, %2076 ]
  %2092 = extractelement <4 x i8> %2073, i32 2
  %2093 = zext i8 %2092 to i32		; visa id: 2003
  br i1 %2055, label %2101, label %2094, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2004

2094:                                             ; preds = %2091
; BB232 :
  %2095 = and i32 %145, 1024
  %2096 = sub nsw i32 0, %2093, !spirv.Decorations !8798
  %2097 = icmp eq i32 %2095, 0		; visa id: 2006
  %2098 = select i1 %2097, i32 %2093, i32 %2096		; visa id: 2008
  %2099 = sitofp i32 %2098 to float		; visa id: 2009
  %2100 = fmul float %2051, %2099		; visa id: 2010
  br label %2109, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2011

2101:                                             ; preds = %2091
; BB233 :
  %2102 = uitofp i32 %2093 to float		; visa id: 2013
  %2103 = fmul float %2051, %2102		; visa id: 2014
  %2104 = and i32 %145, 1024
  %2105 = icmp eq i32 %2104, 0		; visa id: 2015
  %2106 = select i1 %2105, i32 1, i32 -1		; visa id: 2017
  %2107 = sitofp i32 %2106 to float		; visa id: 2018
  %2108 = fmul float %2103, %2107		; visa id: 2019
  br label %2109, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2020

2109:                                             ; preds = %2101, %2094
; BB234 :
  %.sroa.128.9 = phi float [ %2108, %2101 ], [ %2100, %2094 ]
  %2110 = lshr i32 %1805, 24		; visa id: 2021
  br i1 %2055, label %2118, label %2111, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2022

2111:                                             ; preds = %2109
; BB235 :
  %2112 = and i32 %145, 2048
  %2113 = sub nsw i32 0, %2110, !spirv.Decorations !8798
  %2114 = icmp eq i32 %2112, 0		; visa id: 2024
  %2115 = select i1 %2114, i32 %2110, i32 %2113		; visa id: 2026
  %2116 = sitofp i32 %2115 to float		; visa id: 2027
  %2117 = fmul float %2051, %2116		; visa id: 2028
  br label %2126, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2029

2118:                                             ; preds = %2109
; BB236 :
  %2119 = uitofp i32 %2110 to float		; visa id: 2031
  %2120 = fmul float %2051, %2119		; visa id: 2032
  %2121 = and i32 %145, 2048
  %2122 = icmp eq i32 %2121, 0		; visa id: 2033
  %2123 = select i1 %2122, i32 1, i32 -1		; visa id: 2035
  %2124 = sitofp i32 %2123 to float		; visa id: 2036
  %2125 = fmul float %2120, %2124		; visa id: 2037
  br label %2126, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2038

2126:                                             ; preds = %2118, %2111
; BB237 :
  %.sroa.176.9 = phi float [ %2125, %2118 ], [ %2117, %2111 ]
  %2127 = and i32 %1806, 255		; visa id: 2039
  br i1 %2055, label %2135, label %2128, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2040

2128:                                             ; preds = %2126
; BB238 :
  %2129 = and i32 %145, 4096
  %2130 = sub nsw i32 0, %2127, !spirv.Decorations !8798
  %2131 = icmp eq i32 %2129, 0		; visa id: 2042
  %2132 = select i1 %2131, i32 %2127, i32 %2130		; visa id: 2044
  %2133 = sitofp i32 %2132 to float		; visa id: 2045
  %2134 = fmul float %2051, %2133		; visa id: 2046
  br label %2143, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2047

2135:                                             ; preds = %2126
; BB239 :
  %2136 = uitofp i32 %2127 to float		; visa id: 2049
  %2137 = fmul float %2051, %2136		; visa id: 2050
  %2138 = and i32 %145, 4096
  %2139 = icmp eq i32 %2138, 0		; visa id: 2051
  %2140 = select i1 %2139, i32 1, i32 -1		; visa id: 2053
  %2141 = sitofp i32 %2140 to float		; visa id: 2054
  %2142 = fmul float %2137, %2141		; visa id: 2055
  br label %2143, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2056

2143:                                             ; preds = %2135, %2128
; BB240 :
  %.sroa.224.9 = phi float [ %2142, %2135 ], [ %2134, %2128 ]
  %2144 = bitcast i32 %1806 to <4 x i8>
  %2145 = extractelement <4 x i8> %2144, i32 1
  %2146 = zext i8 %2145 to i32		; visa id: 2057
  br i1 %2055, label %2154, label %2147, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2058

2147:                                             ; preds = %2143
; BB241 :
  %2148 = and i32 %145, 8192
  %2149 = sub nsw i32 0, %2146, !spirv.Decorations !8798
  %2150 = icmp eq i32 %2148, 0		; visa id: 2060
  %2151 = select i1 %2150, i32 %2146, i32 %2149		; visa id: 2062
  %2152 = sitofp i32 %2151 to float		; visa id: 2063
  %2153 = fmul float %2051, %2152		; visa id: 2064
  br label %2162, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2065

2154:                                             ; preds = %2143
; BB242 :
  %2155 = uitofp i32 %2146 to float		; visa id: 2067
  %2156 = fmul float %2051, %2155		; visa id: 2068
  %2157 = and i32 %145, 8192
  %2158 = icmp eq i32 %2157, 0		; visa id: 2069
  %2159 = select i1 %2158, i32 1, i32 -1		; visa id: 2071
  %2160 = sitofp i32 %2159 to float		; visa id: 2072
  %2161 = fmul float %2156, %2160		; visa id: 2073
  br label %2162, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2074

2162:                                             ; preds = %2154, %2147
; BB243 :
  %.sroa.272.9 = phi float [ %2161, %2154 ], [ %2153, %2147 ]
  %2163 = extractelement <4 x i8> %2144, i32 2
  %2164 = zext i8 %2163 to i32		; visa id: 2075
  br i1 %2055, label %2172, label %2165, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2076

2165:                                             ; preds = %2162
; BB244 :
  %2166 = and i32 %145, 16384
  %2167 = sub nsw i32 0, %2164, !spirv.Decorations !8798
  %2168 = icmp eq i32 %2166, 0		; visa id: 2078
  %2169 = select i1 %2168, i32 %2164, i32 %2167		; visa id: 2080
  %2170 = sitofp i32 %2169 to float		; visa id: 2081
  %2171 = fmul float %2051, %2170		; visa id: 2082
  br label %2180, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2083

2172:                                             ; preds = %2162
; BB245 :
  %2173 = uitofp i32 %2164 to float		; visa id: 2085
  %2174 = fmul float %2051, %2173		; visa id: 2086
  %2175 = and i32 %145, 16384
  %2176 = icmp eq i32 %2175, 0		; visa id: 2087
  %2177 = select i1 %2176, i32 1, i32 -1		; visa id: 2089
  %2178 = sitofp i32 %2177 to float		; visa id: 2090
  %2179 = fmul float %2174, %2178		; visa id: 2091
  br label %2180, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2092

2180:                                             ; preds = %2172, %2165
; BB246 :
  %.sroa.320.9 = phi float [ %2179, %2172 ], [ %2171, %2165 ]
  %2181 = lshr i32 %1806, 24		; visa id: 2093
  br i1 %2055, label %2189, label %2182, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2094

2182:                                             ; preds = %2180
; BB247 :
  %2183 = and i32 %145, 32768
  %2184 = sub nsw i32 0, %2181, !spirv.Decorations !8798
  %2185 = icmp eq i32 %2183, 0		; visa id: 2096
  %2186 = select i1 %2185, i32 %2181, i32 %2184		; visa id: 2098
  %2187 = sitofp i32 %2186 to float		; visa id: 2099
  %2188 = fmul float %2051, %2187		; visa id: 2100
  br label %.preheader.153, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2101

2189:                                             ; preds = %2180
; BB248 :
  %2190 = uitofp i32 %2181 to float		; visa id: 2103
  %2191 = fmul float %2051, %2190		; visa id: 2104
  %2192 = and i32 %145, 32768
  %2193 = icmp eq i32 %2192, 0		; visa id: 2105
  %2194 = select i1 %2193, i32 1, i32 -1		; visa id: 2107
  %2195 = sitofp i32 %2194 to float		; visa id: 2108
  %2196 = fmul float %2191, %2195		; visa id: 2109
  br label %.preheader.153, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2110

.preheader.153:                                   ; preds = %2189, %2182
; BB249 :
  %.sroa.368.9 = phi float [ %2196, %2189 ], [ %2188, %2182 ]
  %2197 = fmul float %.sroa.065.9, %2008		; visa id: 2111
  %2198 = fadd float %.sroa.29.0, %2197		; visa id: 2112
  %2199 = fmul float %.sroa.80.9, %2013		; visa id: 2113
  %2200 = fadd float %2198, %2199		; visa id: 2114
  %2201 = fmul float %.sroa.128.9, %2018		; visa id: 2115
  %2202 = fadd float %2200, %2201		; visa id: 2116
  %2203 = fmul float %.sroa.176.9, %2023		; visa id: 2117
  %2204 = fadd float %2202, %2203		; visa id: 2118
  %2205 = fmul float %.sroa.224.9, %2028		; visa id: 2119
  %2206 = fadd float %2204, %2205		; visa id: 2120
  %2207 = fmul float %.sroa.272.9, %2033		; visa id: 2121
  %2208 = fadd float %2206, %2207		; visa id: 2122
  %2209 = fmul float %.sroa.320.9, %2038		; visa id: 2123
  %2210 = fadd float %2208, %2209		; visa id: 2124
  %2211 = fmul float %.sroa.368.9, %2043		; visa id: 2125
  %2212 = fadd float %2210, %2211		; visa id: 2126
  %2213 = or i32 %257, 80		; visa id: 2127
  %2214 = zext i32 %2213 to i64		; visa id: 2128
  %2215 = add i64 %2214, %const_reg_qword2		; visa id: 2129
  %IntToPtr2616 = inttoptr i64 %2215 to ptr addrspace(1)		; visa id: 2130
  %vCastload617 = load i32, ptr addrspace(1) %IntToPtr2616, align 2		; visa id: 2130
  %2216 = add i64 %2215, 4
  %IntToPtr2618 = inttoptr i64 %2216 to ptr addrspace(1)
  %vCastload619 = load i32, ptr addrspace(1) %IntToPtr2618, align 2		; visa id: 2131
  %2217 = add i64 %2215, 8
  %IntToPtr2620 = inttoptr i64 %2217 to ptr addrspace(1)
  %vCastload621 = load i32, ptr addrspace(1) %IntToPtr2620, align 2		; visa id: 2132
  %2218 = add i64 %2215, 12
  %IntToPtr2622 = inttoptr i64 %2218 to ptr addrspace(1)
  %vCastload623 = load i32, ptr addrspace(1) %IntToPtr2622, align 2		; visa id: 2133
  %2219 = bitcast i32 %vCastload617 to <2 x i16>		; visa id: 2134
  %2220 = bitcast i32 %vCastload619 to <2 x i16>		; visa id: 2136
  %2221 = extractelement <2 x i16> %2219, i32 0		; visa id: 2138
  %2222 = extractelement <2 x i16> %2219, i32 1		; visa id: 2138
  %2223 = extractelement <2 x i16> %2220, i32 0		; visa id: 2138
  %2224 = extractelement <2 x i16> %2220, i32 1		; visa id: 2138
  %2225 = bitcast i32 %vCastload621 to <2 x i16>		; visa id: 2138
  %2226 = bitcast i32 %vCastload623 to <2 x i16>		; visa id: 2140
  %2227 = extractelement <2 x i16> %2225, i32 0		; visa id: 2142
  %2228 = extractelement <2 x i16> %2225, i32 1		; visa id: 2142
  %2229 = extractelement <2 x i16> %2226, i32 0		; visa id: 2142
  %2230 = extractelement <2 x i16> %2226, i32 1		; visa id: 2142
  %2231 = and i32 %1759, 255		; visa id: 2142
  br i1 %1863, label %2239, label %2232, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2143

2232:                                             ; preds = %.preheader.153
; BB250 :
  %2233 = and i32 %124, 16777216
  %2234 = sub nsw i32 0, %2231, !spirv.Decorations !8798
  %2235 = icmp eq i32 %2233, 0		; visa id: 2145
  %2236 = select i1 %2235, i32 %2231, i32 %2234		; visa id: 2147
  %2237 = sitofp i32 %2236 to float		; visa id: 2148
  %2238 = fmul float %1856, %2237		; visa id: 2149
  br label %2247, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2150

2239:                                             ; preds = %.preheader.153
; BB251 :
  %2240 = uitofp i32 %2231 to float		; visa id: 2152
  %2241 = fmul float %1856, %2240		; visa id: 2153
  %2242 = and i32 %124, 16777216
  %2243 = icmp eq i32 %2242, 0		; visa id: 2154
  %2244 = select i1 %2243, i32 1, i32 -1		; visa id: 2156
  %2245 = sitofp i32 %2244 to float		; visa id: 2157
  %2246 = fmul float %2241, %2245		; visa id: 2158
  br label %2247, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2159

2247:                                             ; preds = %2239, %2232
; BB252 :
  %.sroa.065.10 = phi float [ %2246, %2239 ], [ %2238, %2232 ]
  %2248 = bitcast i32 %1759 to <4 x i8>
  %2249 = extractelement <4 x i8> %2248, i32 1
  %2250 = zext i8 %2249 to i32		; visa id: 2160
  br i1 %1863, label %2258, label %2251, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2161

2251:                                             ; preds = %2247
; BB253 :
  %2252 = and i32 %124, 33554432
  %2253 = sub nsw i32 0, %2250, !spirv.Decorations !8798
  %2254 = icmp eq i32 %2252, 0		; visa id: 2163
  %2255 = select i1 %2254, i32 %2250, i32 %2253		; visa id: 2165
  %2256 = sitofp i32 %2255 to float		; visa id: 2166
  %2257 = fmul float %1856, %2256		; visa id: 2167
  br label %2266, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2168

2258:                                             ; preds = %2247
; BB254 :
  %2259 = uitofp i32 %2250 to float		; visa id: 2170
  %2260 = fmul float %1856, %2259		; visa id: 2171
  %2261 = and i32 %124, 33554432
  %2262 = icmp eq i32 %2261, 0		; visa id: 2172
  %2263 = select i1 %2262, i32 1, i32 -1		; visa id: 2174
  %2264 = sitofp i32 %2263 to float		; visa id: 2175
  %2265 = fmul float %2260, %2264		; visa id: 2176
  br label %2266, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2177

2266:                                             ; preds = %2258, %2251
; BB255 :
  %.sroa.80.10 = phi float [ %2265, %2258 ], [ %2257, %2251 ]
  %2267 = extractelement <4 x i8> %2248, i32 2
  %2268 = zext i8 %2267 to i32		; visa id: 2178
  br i1 %1863, label %2276, label %2269, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2179

2269:                                             ; preds = %2266
; BB256 :
  %2270 = and i32 %124, 67108864
  %2271 = sub nsw i32 0, %2268, !spirv.Decorations !8798
  %2272 = icmp eq i32 %2270, 0		; visa id: 2181
  %2273 = select i1 %2272, i32 %2268, i32 %2271		; visa id: 2183
  %2274 = sitofp i32 %2273 to float		; visa id: 2184
  %2275 = fmul float %1856, %2274		; visa id: 2185
  br label %2284, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2186

2276:                                             ; preds = %2266
; BB257 :
  %2277 = uitofp i32 %2268 to float		; visa id: 2188
  %2278 = fmul float %1856, %2277		; visa id: 2189
  %2279 = and i32 %124, 67108864
  %2280 = icmp eq i32 %2279, 0		; visa id: 2190
  %2281 = select i1 %2280, i32 1, i32 -1		; visa id: 2192
  %2282 = sitofp i32 %2281 to float		; visa id: 2193
  %2283 = fmul float %2278, %2282		; visa id: 2194
  br label %2284, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2195

2284:                                             ; preds = %2276, %2269
; BB258 :
  %.sroa.128.10 = phi float [ %2283, %2276 ], [ %2275, %2269 ]
  %2285 = lshr i32 %1759, 24		; visa id: 2196
  br i1 %1863, label %2293, label %2286, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2197

2286:                                             ; preds = %2284
; BB259 :
  %2287 = and i32 %124, 134217728
  %2288 = sub nsw i32 0, %2285, !spirv.Decorations !8798
  %2289 = icmp eq i32 %2287, 0		; visa id: 2199
  %2290 = select i1 %2289, i32 %2285, i32 %2288		; visa id: 2201
  %2291 = sitofp i32 %2290 to float		; visa id: 2202
  %2292 = fmul float %1856, %2291		; visa id: 2203
  br label %2301, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2204

2293:                                             ; preds = %2284
; BB260 :
  %2294 = uitofp i32 %2285 to float		; visa id: 2206
  %2295 = fmul float %1856, %2294		; visa id: 2207
  %2296 = and i32 %124, 134217728
  %2297 = icmp eq i32 %2296, 0		; visa id: 2208
  %2298 = select i1 %2297, i32 1, i32 -1		; visa id: 2210
  %2299 = sitofp i32 %2298 to float		; visa id: 2211
  %2300 = fmul float %2295, %2299		; visa id: 2212
  br label %2301, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2213

2301:                                             ; preds = %2293, %2286
; BB261 :
  %.sroa.176.10 = phi float [ %2300, %2293 ], [ %2292, %2286 ]
  %2302 = and i32 %1760, 255		; visa id: 2214
  br i1 %1863, label %2310, label %2303, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2215

2303:                                             ; preds = %2301
; BB262 :
  %2304 = and i32 %124, 268435456
  %2305 = sub nsw i32 0, %2302, !spirv.Decorations !8798
  %2306 = icmp eq i32 %2304, 0		; visa id: 2217
  %2307 = select i1 %2306, i32 %2302, i32 %2305		; visa id: 2219
  %2308 = sitofp i32 %2307 to float		; visa id: 2220
  %2309 = fmul float %1856, %2308		; visa id: 2221
  br label %2318, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2222

2310:                                             ; preds = %2301
; BB263 :
  %2311 = uitofp i32 %2302 to float		; visa id: 2224
  %2312 = fmul float %1856, %2311		; visa id: 2225
  %2313 = and i32 %124, 268435456
  %2314 = icmp eq i32 %2313, 0		; visa id: 2226
  %2315 = select i1 %2314, i32 1, i32 -1		; visa id: 2228
  %2316 = sitofp i32 %2315 to float		; visa id: 2229
  %2317 = fmul float %2312, %2316		; visa id: 2230
  br label %2318, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2231

2318:                                             ; preds = %2310, %2303
; BB264 :
  %.sroa.224.10 = phi float [ %2317, %2310 ], [ %2309, %2303 ]
  %2319 = bitcast i32 %1760 to <4 x i8>
  %2320 = extractelement <4 x i8> %2319, i32 1
  %2321 = zext i8 %2320 to i32		; visa id: 2232
  br i1 %1863, label %2329, label %2322, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2233

2322:                                             ; preds = %2318
; BB265 :
  %2323 = and i32 %124, 536870912
  %2324 = sub nsw i32 0, %2321, !spirv.Decorations !8798
  %2325 = icmp eq i32 %2323, 0		; visa id: 2235
  %2326 = select i1 %2325, i32 %2321, i32 %2324		; visa id: 2237
  %2327 = sitofp i32 %2326 to float		; visa id: 2238
  %2328 = fmul float %1856, %2327		; visa id: 2239
  br label %2337, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2240

2329:                                             ; preds = %2318
; BB266 :
  %2330 = uitofp i32 %2321 to float		; visa id: 2242
  %2331 = fmul float %1856, %2330		; visa id: 2243
  %2332 = and i32 %124, 536870912
  %2333 = icmp eq i32 %2332, 0		; visa id: 2244
  %2334 = select i1 %2333, i32 1, i32 -1		; visa id: 2246
  %2335 = sitofp i32 %2334 to float		; visa id: 2247
  %2336 = fmul float %2331, %2335		; visa id: 2248
  br label %2337, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2249

2337:                                             ; preds = %2329, %2322
; BB267 :
  %.sroa.272.10 = phi float [ %2336, %2329 ], [ %2328, %2322 ]
  %2338 = extractelement <4 x i8> %2319, i32 2
  %2339 = zext i8 %2338 to i32		; visa id: 2250
  br i1 %1863, label %2347, label %2340, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2251

2340:                                             ; preds = %2337
; BB268 :
  %2341 = and i32 %124, 1073741824
  %2342 = sub nsw i32 0, %2339, !spirv.Decorations !8798
  %2343 = icmp eq i32 %2341, 0		; visa id: 2253
  %2344 = select i1 %2343, i32 %2339, i32 %2342		; visa id: 2255
  %2345 = sitofp i32 %2344 to float		; visa id: 2256
  %2346 = fmul float %1856, %2345		; visa id: 2257
  br label %2355, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2258

2347:                                             ; preds = %2337
; BB269 :
  %2348 = uitofp i32 %2339 to float		; visa id: 2260
  %2349 = fmul float %1856, %2348		; visa id: 2261
  %2350 = and i32 %124, 1073741824
  %2351 = icmp eq i32 %2350, 0		; visa id: 2262
  %2352 = select i1 %2351, i32 1, i32 -1		; visa id: 2264
  %2353 = sitofp i32 %2352 to float		; visa id: 2265
  %2354 = fmul float %2349, %2353		; visa id: 2266
  br label %2355, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2267

2355:                                             ; preds = %2347, %2340
; BB270 :
  %.sroa.320.10 = phi float [ %2354, %2347 ], [ %2346, %2340 ]
  %2356 = lshr i32 %1760, 24		; visa id: 2268
  br i1 %1863, label %2363, label %2357, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2269

2357:                                             ; preds = %2355
; BB271 :
  %2358 = sub nsw i32 0, %2356, !spirv.Decorations !8798
  %2359 = icmp slt i32 %124, 0		; visa id: 2271
  %2360 = select i1 %2359, i32 %2358, i32 %2356		; visa id: 2272
  %2361 = sitofp i32 %2360 to float		; visa id: 2273
  %2362 = fmul float %1856, %2361		; visa id: 2274
  br label %2370, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2275

2363:                                             ; preds = %2355
; BB272 :
  %2364 = uitofp i32 %2356 to float		; visa id: 2277
  %2365 = fmul float %1856, %2364		; visa id: 2278
  %2366 = icmp sgt i32 %124, -1		; visa id: 2279
  %2367 = select i1 %2366, i32 1, i32 -1		; visa id: 2280
  %2368 = sitofp i32 %2367 to float		; visa id: 2281
  %2369 = fmul float %2365, %2368		; visa id: 2282
  br label %2370, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2283

2370:                                             ; preds = %2363, %2357
; BB273 :
  %.sroa.368.10 = phi float [ %2369, %2363 ], [ %2362, %2357 ]
  %2371 = zext i16 %2221 to i32		; visa id: 2284
  %2372 = shl nuw i32 %2371, 16		; visa id: 2285
  %2373 = bitcast i32 %2372 to float
  %2374 = fmul float %.sroa.065.10, %2373		; visa id: 2286
  %2375 = fadd float %.sroa.14.0, %2374		; visa id: 2287
  %2376 = zext i16 %2222 to i32		; visa id: 2288
  %2377 = shl nuw i32 %2376, 16		; visa id: 2289
  %2378 = bitcast i32 %2377 to float
  %2379 = fmul float %.sroa.80.10, %2378		; visa id: 2290
  %2380 = fadd float %2375, %2379		; visa id: 2291
  %2381 = zext i16 %2223 to i32		; visa id: 2292
  %2382 = shl nuw i32 %2381, 16		; visa id: 2293
  %2383 = bitcast i32 %2382 to float
  %2384 = fmul float %.sroa.128.10, %2383		; visa id: 2294
  %2385 = fadd float %2380, %2384		; visa id: 2295
  %2386 = zext i16 %2224 to i32		; visa id: 2296
  %2387 = shl nuw i32 %2386, 16		; visa id: 2297
  %2388 = bitcast i32 %2387 to float
  %2389 = fmul float %.sroa.176.10, %2388		; visa id: 2298
  %2390 = fadd float %2385, %2389		; visa id: 2299
  %2391 = zext i16 %2227 to i32		; visa id: 2300
  %2392 = shl nuw i32 %2391, 16		; visa id: 2301
  %2393 = bitcast i32 %2392 to float
  %2394 = fmul float %.sroa.224.10, %2393		; visa id: 2302
  %2395 = fadd float %2390, %2394		; visa id: 2303
  %2396 = zext i16 %2228 to i32		; visa id: 2304
  %2397 = shl nuw i32 %2396, 16		; visa id: 2305
  %2398 = bitcast i32 %2397 to float
  %2399 = fmul float %.sroa.272.10, %2398		; visa id: 2306
  %2400 = fadd float %2395, %2399		; visa id: 2307
  %2401 = zext i16 %2229 to i32		; visa id: 2308
  %2402 = shl nuw i32 %2401, 16		; visa id: 2309
  %2403 = bitcast i32 %2402 to float
  %2404 = fmul float %.sroa.320.10, %2403		; visa id: 2310
  %2405 = fadd float %2400, %2404		; visa id: 2311
  %2406 = zext i16 %2230 to i32		; visa id: 2312
  %2407 = shl nuw i32 %2406, 16		; visa id: 2313
  %2408 = bitcast i32 %2407 to float
  %2409 = fmul float %.sroa.368.10, %2408		; visa id: 2314
  %2410 = fadd float %2405, %2409		; visa id: 2315
  %2411 = and i32 %1807, 255		; visa id: 2316
  br i1 %2055, label %2419, label %2412, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2317

2412:                                             ; preds = %2370
; BB274 :
  %2413 = and i32 %145, 16777216
  %2414 = sub nsw i32 0, %2411, !spirv.Decorations !8798
  %2415 = icmp eq i32 %2413, 0		; visa id: 2319
  %2416 = select i1 %2415, i32 %2411, i32 %2414		; visa id: 2321
  %2417 = sitofp i32 %2416 to float		; visa id: 2322
  %2418 = fmul float %2051, %2417		; visa id: 2323
  br label %2427, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2324

2419:                                             ; preds = %2370
; BB275 :
  %2420 = uitofp i32 %2411 to float		; visa id: 2326
  %2421 = fmul float %2051, %2420		; visa id: 2327
  %2422 = and i32 %145, 16777216
  %2423 = icmp eq i32 %2422, 0		; visa id: 2328
  %2424 = select i1 %2423, i32 1, i32 -1		; visa id: 2330
  %2425 = sitofp i32 %2424 to float		; visa id: 2331
  %2426 = fmul float %2421, %2425		; visa id: 2332
  br label %2427, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2333

2427:                                             ; preds = %2419, %2412
; BB276 :
  %.sroa.065.11 = phi float [ %2426, %2419 ], [ %2418, %2412 ]
  %2428 = bitcast i32 %1807 to <4 x i8>
  %2429 = extractelement <4 x i8> %2428, i32 1
  %2430 = zext i8 %2429 to i32		; visa id: 2334
  br i1 %2055, label %2438, label %2431, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2335

2431:                                             ; preds = %2427
; BB277 :
  %2432 = and i32 %145, 33554432
  %2433 = sub nsw i32 0, %2430, !spirv.Decorations !8798
  %2434 = icmp eq i32 %2432, 0		; visa id: 2337
  %2435 = select i1 %2434, i32 %2430, i32 %2433		; visa id: 2339
  %2436 = sitofp i32 %2435 to float		; visa id: 2340
  %2437 = fmul float %2051, %2436		; visa id: 2341
  br label %2446, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2342

2438:                                             ; preds = %2427
; BB278 :
  %2439 = uitofp i32 %2430 to float		; visa id: 2344
  %2440 = fmul float %2051, %2439		; visa id: 2345
  %2441 = and i32 %145, 33554432
  %2442 = icmp eq i32 %2441, 0		; visa id: 2346
  %2443 = select i1 %2442, i32 1, i32 -1		; visa id: 2348
  %2444 = sitofp i32 %2443 to float		; visa id: 2349
  %2445 = fmul float %2440, %2444		; visa id: 2350
  br label %2446, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2351

2446:                                             ; preds = %2438, %2431
; BB279 :
  %.sroa.80.11 = phi float [ %2445, %2438 ], [ %2437, %2431 ]
  %2447 = extractelement <4 x i8> %2428, i32 2
  %2448 = zext i8 %2447 to i32		; visa id: 2352
  br i1 %2055, label %2456, label %2449, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2353

2449:                                             ; preds = %2446
; BB280 :
  %2450 = and i32 %145, 67108864
  %2451 = sub nsw i32 0, %2448, !spirv.Decorations !8798
  %2452 = icmp eq i32 %2450, 0		; visa id: 2355
  %2453 = select i1 %2452, i32 %2448, i32 %2451		; visa id: 2357
  %2454 = sitofp i32 %2453 to float		; visa id: 2358
  %2455 = fmul float %2051, %2454		; visa id: 2359
  br label %2464, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2360

2456:                                             ; preds = %2446
; BB281 :
  %2457 = uitofp i32 %2448 to float		; visa id: 2362
  %2458 = fmul float %2051, %2457		; visa id: 2363
  %2459 = and i32 %145, 67108864
  %2460 = icmp eq i32 %2459, 0		; visa id: 2364
  %2461 = select i1 %2460, i32 1, i32 -1		; visa id: 2366
  %2462 = sitofp i32 %2461 to float		; visa id: 2367
  %2463 = fmul float %2458, %2462		; visa id: 2368
  br label %2464, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2369

2464:                                             ; preds = %2456, %2449
; BB282 :
  %.sroa.128.11 = phi float [ %2463, %2456 ], [ %2455, %2449 ]
  %2465 = lshr i32 %1807, 24		; visa id: 2370
  br i1 %2055, label %2473, label %2466, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2371

2466:                                             ; preds = %2464
; BB283 :
  %2467 = and i32 %145, 134217728
  %2468 = sub nsw i32 0, %2465, !spirv.Decorations !8798
  %2469 = icmp eq i32 %2467, 0		; visa id: 2373
  %2470 = select i1 %2469, i32 %2465, i32 %2468		; visa id: 2375
  %2471 = sitofp i32 %2470 to float		; visa id: 2376
  %2472 = fmul float %2051, %2471		; visa id: 2377
  br label %2481, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2378

2473:                                             ; preds = %2464
; BB284 :
  %2474 = uitofp i32 %2465 to float		; visa id: 2380
  %2475 = fmul float %2051, %2474		; visa id: 2381
  %2476 = and i32 %145, 134217728
  %2477 = icmp eq i32 %2476, 0		; visa id: 2382
  %2478 = select i1 %2477, i32 1, i32 -1		; visa id: 2384
  %2479 = sitofp i32 %2478 to float		; visa id: 2385
  %2480 = fmul float %2475, %2479		; visa id: 2386
  br label %2481, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2387

2481:                                             ; preds = %2473, %2466
; BB285 :
  %.sroa.176.11 = phi float [ %2480, %2473 ], [ %2472, %2466 ]
  %2482 = and i32 %1808, 255		; visa id: 2388
  br i1 %2055, label %2490, label %2483, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2389

2483:                                             ; preds = %2481
; BB286 :
  %2484 = and i32 %145, 268435456
  %2485 = sub nsw i32 0, %2482, !spirv.Decorations !8798
  %2486 = icmp eq i32 %2484, 0		; visa id: 2391
  %2487 = select i1 %2486, i32 %2482, i32 %2485		; visa id: 2393
  %2488 = sitofp i32 %2487 to float		; visa id: 2394
  %2489 = fmul float %2051, %2488		; visa id: 2395
  br label %2498, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2396

2490:                                             ; preds = %2481
; BB287 :
  %2491 = uitofp i32 %2482 to float		; visa id: 2398
  %2492 = fmul float %2051, %2491		; visa id: 2399
  %2493 = and i32 %145, 268435456
  %2494 = icmp eq i32 %2493, 0		; visa id: 2400
  %2495 = select i1 %2494, i32 1, i32 -1		; visa id: 2402
  %2496 = sitofp i32 %2495 to float		; visa id: 2403
  %2497 = fmul float %2492, %2496		; visa id: 2404
  br label %2498, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2405

2498:                                             ; preds = %2490, %2483
; BB288 :
  %.sroa.224.11 = phi float [ %2497, %2490 ], [ %2489, %2483 ]
  %2499 = bitcast i32 %1808 to <4 x i8>
  %2500 = extractelement <4 x i8> %2499, i32 1
  %2501 = zext i8 %2500 to i32		; visa id: 2406
  br i1 %2055, label %2509, label %2502, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2407

2502:                                             ; preds = %2498
; BB289 :
  %2503 = and i32 %145, 536870912
  %2504 = sub nsw i32 0, %2501, !spirv.Decorations !8798
  %2505 = icmp eq i32 %2503, 0		; visa id: 2409
  %2506 = select i1 %2505, i32 %2501, i32 %2504		; visa id: 2411
  %2507 = sitofp i32 %2506 to float		; visa id: 2412
  %2508 = fmul float %2051, %2507		; visa id: 2413
  br label %2517, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2414

2509:                                             ; preds = %2498
; BB290 :
  %2510 = uitofp i32 %2501 to float		; visa id: 2416
  %2511 = fmul float %2051, %2510		; visa id: 2417
  %2512 = and i32 %145, 536870912
  %2513 = icmp eq i32 %2512, 0		; visa id: 2418
  %2514 = select i1 %2513, i32 1, i32 -1		; visa id: 2420
  %2515 = sitofp i32 %2514 to float		; visa id: 2421
  %2516 = fmul float %2511, %2515		; visa id: 2422
  br label %2517, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2423

2517:                                             ; preds = %2509, %2502
; BB291 :
  %.sroa.272.11 = phi float [ %2516, %2509 ], [ %2508, %2502 ]
  %2518 = extractelement <4 x i8> %2499, i32 2
  %2519 = zext i8 %2518 to i32		; visa id: 2424
  br i1 %2055, label %2527, label %2520, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2425

2520:                                             ; preds = %2517
; BB292 :
  %2521 = and i32 %145, 1073741824
  %2522 = sub nsw i32 0, %2519, !spirv.Decorations !8798
  %2523 = icmp eq i32 %2521, 0		; visa id: 2427
  %2524 = select i1 %2523, i32 %2519, i32 %2522		; visa id: 2429
  %2525 = sitofp i32 %2524 to float		; visa id: 2430
  %2526 = fmul float %2051, %2525		; visa id: 2431
  br label %2535, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2432

2527:                                             ; preds = %2517
; BB293 :
  %2528 = uitofp i32 %2519 to float		; visa id: 2434
  %2529 = fmul float %2051, %2528		; visa id: 2435
  %2530 = and i32 %145, 1073741824
  %2531 = icmp eq i32 %2530, 0		; visa id: 2436
  %2532 = select i1 %2531, i32 1, i32 -1		; visa id: 2438
  %2533 = sitofp i32 %2532 to float		; visa id: 2439
  %2534 = fmul float %2529, %2533		; visa id: 2440
  br label %2535, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2441

2535:                                             ; preds = %2527, %2520
; BB294 :
  %.sroa.320.11 = phi float [ %2534, %2527 ], [ %2526, %2520 ]
  %2536 = lshr i32 %1808, 24		; visa id: 2442
  br i1 %2055, label %2543, label %2537, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2443

2537:                                             ; preds = %2535
; BB295 :
  %2538 = sub nsw i32 0, %2536, !spirv.Decorations !8798
  %2539 = icmp slt i32 %145, 0		; visa id: 2445
  %2540 = select i1 %2539, i32 %2538, i32 %2536		; visa id: 2446
  %2541 = sitofp i32 %2540 to float		; visa id: 2447
  %2542 = fmul float %2051, %2541		; visa id: 2448
  br label %.preheader.1.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2449

2543:                                             ; preds = %2535
; BB296 :
  %2544 = uitofp i32 %2536 to float		; visa id: 2451
  %2545 = fmul float %2051, %2544		; visa id: 2452
  %2546 = icmp sgt i32 %145, -1		; visa id: 2453
  %2547 = select i1 %2546, i32 1, i32 -1		; visa id: 2454
  %2548 = sitofp i32 %2547 to float		; visa id: 2455
  %2549 = fmul float %2545, %2548		; visa id: 2456
  br label %.preheader.1.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2457

.preheader.1.1:                                   ; preds = %2543, %2537
; BB297 :
  %.sroa.368.11 = phi float [ %2549, %2543 ], [ %2542, %2537 ]
  %2550 = fmul float %.sroa.065.11, %2373		; visa id: 2458
  %2551 = fadd float %.sroa.31.0, %2550		; visa id: 2459
  %2552 = fmul float %.sroa.80.11, %2378		; visa id: 2460
  %2553 = fadd float %2551, %2552		; visa id: 2461
  %2554 = fmul float %.sroa.128.11, %2383		; visa id: 2462
  %2555 = fadd float %2553, %2554		; visa id: 2463
  %2556 = fmul float %.sroa.176.11, %2388		; visa id: 2464
  %2557 = fadd float %2555, %2556		; visa id: 2465
  %2558 = fmul float %.sroa.224.11, %2393		; visa id: 2466
  %2559 = fadd float %2557, %2558		; visa id: 2467
  %2560 = fmul float %.sroa.272.11, %2398		; visa id: 2468
  %2561 = fadd float %2559, %2560		; visa id: 2469
  %2562 = fmul float %.sroa.320.11, %2403		; visa id: 2470
  %2563 = fadd float %2561, %2562		; visa id: 2471
  %2564 = fmul float %.sroa.368.11, %2408		; visa id: 2472
  %2565 = fadd float %2563, %2564		; visa id: 2473
  %2566 = or i32 %257, 96		; visa id: 2474
  %2567 = zext i32 %2566 to i64		; visa id: 2475
  %2568 = add i64 %2567, %const_reg_qword2		; visa id: 2476
  %IntToPtr2624 = inttoptr i64 %2568 to ptr addrspace(1)		; visa id: 2477
  %vCastload625 = load i32, ptr addrspace(1) %IntToPtr2624, align 2		; visa id: 2477
  %2569 = add i64 %2568, 4
  %IntToPtr2626 = inttoptr i64 %2569 to ptr addrspace(1)
  %vCastload627 = load i32, ptr addrspace(1) %IntToPtr2626, align 2		; visa id: 2478
  %2570 = add i64 %2568, 8
  %IntToPtr2628 = inttoptr i64 %2570 to ptr addrspace(1)
  %vCastload629 = load i32, ptr addrspace(1) %IntToPtr2628, align 2		; visa id: 2479
  %2571 = add i64 %2568, 12
  %IntToPtr2630 = inttoptr i64 %2571 to ptr addrspace(1)
  %vCastload631 = load i32, ptr addrspace(1) %IntToPtr2630, align 2		; visa id: 2480
  %2572 = bitcast i32 %vCastload625 to <2 x i16>		; visa id: 2481
  %2573 = bitcast i32 %vCastload627 to <2 x i16>		; visa id: 2483
  %2574 = extractelement <2 x i16> %2572, i32 0		; visa id: 2485
  %2575 = extractelement <2 x i16> %2572, i32 1		; visa id: 2485
  %2576 = extractelement <2 x i16> %2573, i32 0		; visa id: 2485
  %2577 = extractelement <2 x i16> %2573, i32 1		; visa id: 2485
  %2578 = bitcast i32 %vCastload629 to <2 x i16>		; visa id: 2485
  %2579 = bitcast i32 %vCastload631 to <2 x i16>		; visa id: 2487
  %2580 = extractelement <2 x i16> %2578, i32 0		; visa id: 2489
  %2581 = extractelement <2 x i16> %2578, i32 1		; visa id: 2489
  %2582 = extractelement <2 x i16> %2579, i32 0		; visa id: 2489
  %2583 = extractelement <2 x i16> %2579, i32 1		; visa id: 2489
  %2584 = lshr i32 %1851, 4		; visa id: 2489
  %2585 = uitofp i32 %2584 to float		; visa id: 2490
  %2586 = fadd float %2585, 5.000000e-01		; visa id: 2491
  %2587 = fmul float %139, %2586		; visa id: 2492
  %2588 = fmul float %2587, 2.500000e-01		; visa id: 2493
  %2589 = bitcast float %2588 to i32
  %2590 = and i32 %2589, 2147483647		; visa id: 2494
  %2591 = icmp ugt i32 %2590, 2139095040
  %2592 = fcmp oeq float %286, 0x7FF0000000000000		; visa id: 2495
  %2593 = fcmp une float %286, %286
  %2594 = or i1 %2593, %2592		; visa id: 2496
  %2595 = or i1 %2594, %2591		; visa id: 2498
  %2596 = and i32 %1781, 255		; visa id: 2500
  br i1 %2595, label %2604, label %2597, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2501

2597:                                             ; preds = %.preheader.1.1
; BB298 :
  %2598 = and i32 %125, 256
  %2599 = sub nsw i32 0, %2596, !spirv.Decorations !8798
  %2600 = icmp eq i32 %2598, 0		; visa id: 2503
  %2601 = select i1 %2600, i32 %2596, i32 %2599		; visa id: 2505
  %2602 = sitofp i32 %2601 to float		; visa id: 2506
  %2603 = fmul float %2588, %2602		; visa id: 2507
  br label %2612, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2508

2604:                                             ; preds = %.preheader.1.1
; BB299 :
  %2605 = uitofp i32 %2596 to float		; visa id: 2510
  %2606 = fmul float %2588, %2605		; visa id: 2511
  %2607 = and i32 %125, 256
  %2608 = icmp eq i32 %2607, 0		; visa id: 2512
  %2609 = select i1 %2608, i32 1, i32 -1		; visa id: 2514
  %2610 = sitofp i32 %2609 to float		; visa id: 2515
  %2611 = fmul float %2606, %2610		; visa id: 2516
  br label %2612, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2517

2612:                                             ; preds = %2604, %2597
; BB300 :
  %.sroa.065.12 = phi float [ %2611, %2604 ], [ %2603, %2597 ]
  %2613 = bitcast i32 %1781 to <4 x i8>
  %2614 = extractelement <4 x i8> %2613, i32 1
  %2615 = zext i8 %2614 to i32		; visa id: 2518
  br i1 %2595, label %2623, label %2616, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2519

2616:                                             ; preds = %2612
; BB301 :
  %2617 = and i32 %125, 512
  %2618 = sub nsw i32 0, %2615, !spirv.Decorations !8798
  %2619 = icmp eq i32 %2617, 0		; visa id: 2521
  %2620 = select i1 %2619, i32 %2615, i32 %2618		; visa id: 2523
  %2621 = sitofp i32 %2620 to float		; visa id: 2524
  %2622 = fmul float %2588, %2621		; visa id: 2525
  br label %2631, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2526

2623:                                             ; preds = %2612
; BB302 :
  %2624 = uitofp i32 %2615 to float		; visa id: 2528
  %2625 = fmul float %2588, %2624		; visa id: 2529
  %2626 = and i32 %125, 512
  %2627 = icmp eq i32 %2626, 0		; visa id: 2530
  %2628 = select i1 %2627, i32 1, i32 -1		; visa id: 2532
  %2629 = sitofp i32 %2628 to float		; visa id: 2533
  %2630 = fmul float %2625, %2629		; visa id: 2534
  br label %2631, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2535

2631:                                             ; preds = %2623, %2616
; BB303 :
  %.sroa.80.12 = phi float [ %2630, %2623 ], [ %2622, %2616 ]
  %2632 = extractelement <4 x i8> %2613, i32 2
  %2633 = zext i8 %2632 to i32		; visa id: 2536
  br i1 %2595, label %2641, label %2634, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2537

2634:                                             ; preds = %2631
; BB304 :
  %2635 = and i32 %125, 1024
  %2636 = sub nsw i32 0, %2633, !spirv.Decorations !8798
  %2637 = icmp eq i32 %2635, 0		; visa id: 2539
  %2638 = select i1 %2637, i32 %2633, i32 %2636		; visa id: 2541
  %2639 = sitofp i32 %2638 to float		; visa id: 2542
  %2640 = fmul float %2588, %2639		; visa id: 2543
  br label %2649, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2544

2641:                                             ; preds = %2631
; BB305 :
  %2642 = uitofp i32 %2633 to float		; visa id: 2546
  %2643 = fmul float %2588, %2642		; visa id: 2547
  %2644 = and i32 %125, 1024
  %2645 = icmp eq i32 %2644, 0		; visa id: 2548
  %2646 = select i1 %2645, i32 1, i32 -1		; visa id: 2550
  %2647 = sitofp i32 %2646 to float		; visa id: 2551
  %2648 = fmul float %2643, %2647		; visa id: 2552
  br label %2649, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2553

2649:                                             ; preds = %2641, %2634
; BB306 :
  %.sroa.128.12 = phi float [ %2648, %2641 ], [ %2640, %2634 ]
  %2650 = lshr i32 %1781, 24		; visa id: 2554
  br i1 %2595, label %2658, label %2651, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2555

2651:                                             ; preds = %2649
; BB307 :
  %2652 = and i32 %125, 2048
  %2653 = sub nsw i32 0, %2650, !spirv.Decorations !8798
  %2654 = icmp eq i32 %2652, 0		; visa id: 2557
  %2655 = select i1 %2654, i32 %2650, i32 %2653		; visa id: 2559
  %2656 = sitofp i32 %2655 to float		; visa id: 2560
  %2657 = fmul float %2588, %2656		; visa id: 2561
  br label %2666, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2562

2658:                                             ; preds = %2649
; BB308 :
  %2659 = uitofp i32 %2650 to float		; visa id: 2564
  %2660 = fmul float %2588, %2659		; visa id: 2565
  %2661 = and i32 %125, 2048
  %2662 = icmp eq i32 %2661, 0		; visa id: 2566
  %2663 = select i1 %2662, i32 1, i32 -1		; visa id: 2568
  %2664 = sitofp i32 %2663 to float		; visa id: 2569
  %2665 = fmul float %2660, %2664		; visa id: 2570
  br label %2666, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2571

2666:                                             ; preds = %2658, %2651
; BB309 :
  %.sroa.176.12 = phi float [ %2665, %2658 ], [ %2657, %2651 ]
  %2667 = and i32 %1782, 255		; visa id: 2572
  br i1 %2595, label %2675, label %2668, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2573

2668:                                             ; preds = %2666
; BB310 :
  %2669 = and i32 %125, 4096
  %2670 = sub nsw i32 0, %2667, !spirv.Decorations !8798
  %2671 = icmp eq i32 %2669, 0		; visa id: 2575
  %2672 = select i1 %2671, i32 %2667, i32 %2670		; visa id: 2577
  %2673 = sitofp i32 %2672 to float		; visa id: 2578
  %2674 = fmul float %2588, %2673		; visa id: 2579
  br label %2683, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2580

2675:                                             ; preds = %2666
; BB311 :
  %2676 = uitofp i32 %2667 to float		; visa id: 2582
  %2677 = fmul float %2588, %2676		; visa id: 2583
  %2678 = and i32 %125, 4096
  %2679 = icmp eq i32 %2678, 0		; visa id: 2584
  %2680 = select i1 %2679, i32 1, i32 -1		; visa id: 2586
  %2681 = sitofp i32 %2680 to float		; visa id: 2587
  %2682 = fmul float %2677, %2681		; visa id: 2588
  br label %2683, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2589

2683:                                             ; preds = %2675, %2668
; BB312 :
  %.sroa.224.12 = phi float [ %2682, %2675 ], [ %2674, %2668 ]
  %2684 = bitcast i32 %1782 to <4 x i8>
  %2685 = extractelement <4 x i8> %2684, i32 1
  %2686 = zext i8 %2685 to i32		; visa id: 2590
  br i1 %2595, label %2694, label %2687, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2591

2687:                                             ; preds = %2683
; BB313 :
  %2688 = and i32 %125, 8192
  %2689 = sub nsw i32 0, %2686, !spirv.Decorations !8798
  %2690 = icmp eq i32 %2688, 0		; visa id: 2593
  %2691 = select i1 %2690, i32 %2686, i32 %2689		; visa id: 2595
  %2692 = sitofp i32 %2691 to float		; visa id: 2596
  %2693 = fmul float %2588, %2692		; visa id: 2597
  br label %2702, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2598

2694:                                             ; preds = %2683
; BB314 :
  %2695 = uitofp i32 %2686 to float		; visa id: 2600
  %2696 = fmul float %2588, %2695		; visa id: 2601
  %2697 = and i32 %125, 8192
  %2698 = icmp eq i32 %2697, 0		; visa id: 2602
  %2699 = select i1 %2698, i32 1, i32 -1		; visa id: 2604
  %2700 = sitofp i32 %2699 to float		; visa id: 2605
  %2701 = fmul float %2696, %2700		; visa id: 2606
  br label %2702, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2607

2702:                                             ; preds = %2694, %2687
; BB315 :
  %.sroa.272.12 = phi float [ %2701, %2694 ], [ %2693, %2687 ]
  %2703 = extractelement <4 x i8> %2684, i32 2
  %2704 = zext i8 %2703 to i32		; visa id: 2608
  br i1 %2595, label %2712, label %2705, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2609

2705:                                             ; preds = %2702
; BB316 :
  %2706 = and i32 %125, 16384
  %2707 = sub nsw i32 0, %2704, !spirv.Decorations !8798
  %2708 = icmp eq i32 %2706, 0		; visa id: 2611
  %2709 = select i1 %2708, i32 %2704, i32 %2707		; visa id: 2613
  %2710 = sitofp i32 %2709 to float		; visa id: 2614
  %2711 = fmul float %2588, %2710		; visa id: 2615
  br label %2720, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2616

2712:                                             ; preds = %2702
; BB317 :
  %2713 = uitofp i32 %2704 to float		; visa id: 2618
  %2714 = fmul float %2588, %2713		; visa id: 2619
  %2715 = and i32 %125, 16384
  %2716 = icmp eq i32 %2715, 0		; visa id: 2620
  %2717 = select i1 %2716, i32 1, i32 -1		; visa id: 2622
  %2718 = sitofp i32 %2717 to float		; visa id: 2623
  %2719 = fmul float %2714, %2718		; visa id: 2624
  br label %2720, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2625

2720:                                             ; preds = %2712, %2705
; BB318 :
  %.sroa.320.12 = phi float [ %2719, %2712 ], [ %2711, %2705 ]
  %2721 = lshr i32 %1782, 24		; visa id: 2626
  br i1 %2595, label %2729, label %2722, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2627

2722:                                             ; preds = %2720
; BB319 :
  %2723 = and i32 %125, 32768
  %2724 = sub nsw i32 0, %2721, !spirv.Decorations !8798
  %2725 = icmp eq i32 %2723, 0		; visa id: 2629
  %2726 = select i1 %2725, i32 %2721, i32 %2724		; visa id: 2631
  %2727 = sitofp i32 %2726 to float		; visa id: 2632
  %2728 = fmul float %2588, %2727		; visa id: 2633
  br label %2737, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2634

2729:                                             ; preds = %2720
; BB320 :
  %2730 = uitofp i32 %2721 to float		; visa id: 2636
  %2731 = fmul float %2588, %2730		; visa id: 2637
  %2732 = and i32 %125, 32768
  %2733 = icmp eq i32 %2732, 0		; visa id: 2638
  %2734 = select i1 %2733, i32 1, i32 -1		; visa id: 2640
  %2735 = sitofp i32 %2734 to float		; visa id: 2641
  %2736 = fmul float %2731, %2735		; visa id: 2642
  br label %2737, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2643

2737:                                             ; preds = %2729, %2722
; BB321 :
  %.sroa.368.12 = phi float [ %2736, %2729 ], [ %2728, %2722 ]
  %2738 = zext i16 %2574 to i32		; visa id: 2644
  %2739 = shl nuw i32 %2738, 16		; visa id: 2645
  %2740 = bitcast i32 %2739 to float
  %2741 = fmul float %.sroa.065.12, %2740		; visa id: 2646
  %2742 = fadd float %.sroa.16.0, %2741		; visa id: 2647
  %2743 = zext i16 %2575 to i32		; visa id: 2648
  %2744 = shl nuw i32 %2743, 16		; visa id: 2649
  %2745 = bitcast i32 %2744 to float
  %2746 = fmul float %.sroa.80.12, %2745		; visa id: 2650
  %2747 = fadd float %2742, %2746		; visa id: 2651
  %2748 = zext i16 %2576 to i32		; visa id: 2652
  %2749 = shl nuw i32 %2748, 16		; visa id: 2653
  %2750 = bitcast i32 %2749 to float
  %2751 = fmul float %.sroa.128.12, %2750		; visa id: 2654
  %2752 = fadd float %2747, %2751		; visa id: 2655
  %2753 = zext i16 %2577 to i32		; visa id: 2656
  %2754 = shl nuw i32 %2753, 16		; visa id: 2657
  %2755 = bitcast i32 %2754 to float
  %2756 = fmul float %.sroa.176.12, %2755		; visa id: 2658
  %2757 = fadd float %2752, %2756		; visa id: 2659
  %2758 = zext i16 %2580 to i32		; visa id: 2660
  %2759 = shl nuw i32 %2758, 16		; visa id: 2661
  %2760 = bitcast i32 %2759 to float
  %2761 = fmul float %.sroa.224.12, %2760		; visa id: 2662
  %2762 = fadd float %2757, %2761		; visa id: 2663
  %2763 = zext i16 %2581 to i32		; visa id: 2664
  %2764 = shl nuw i32 %2763, 16		; visa id: 2665
  %2765 = bitcast i32 %2764 to float
  %2766 = fmul float %.sroa.272.12, %2765		; visa id: 2666
  %2767 = fadd float %2762, %2766		; visa id: 2667
  %2768 = zext i16 %2582 to i32		; visa id: 2668
  %2769 = shl nuw i32 %2768, 16		; visa id: 2669
  %2770 = bitcast i32 %2769 to float
  %2771 = fmul float %.sroa.320.12, %2770		; visa id: 2670
  %2772 = fadd float %2767, %2771		; visa id: 2671
  %2773 = zext i16 %2583 to i32		; visa id: 2672
  %2774 = shl nuw i32 %2773, 16		; visa id: 2673
  %2775 = bitcast i32 %2774 to float
  %2776 = fmul float %.sroa.368.12, %2775		; visa id: 2674
  %2777 = fadd float %2772, %2776		; visa id: 2675
  %2778 = lshr i32 %2046, 4		; visa id: 2676
  %2779 = uitofp i32 %2778 to float		; visa id: 2677
  %2780 = fadd float %2779, 5.000000e-01		; visa id: 2678
  %2781 = fmul float %158, %2780		; visa id: 2679
  %2782 = fmul float %2781, 2.500000e-01		; visa id: 2680
  %2783 = bitcast float %2782 to i32
  %2784 = and i32 %2783, 2147483647		; visa id: 2681
  %2785 = icmp ugt i32 %2784, 2139095040		; visa id: 2682
  %2786 = or i1 %488, %2785		; visa id: 2683
  %2787 = and i32 %1829, 255		; visa id: 2684
  br i1 %2786, label %2795, label %2788, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2685

2788:                                             ; preds = %2737
; BB322 :
  %2789 = and i32 %146, 256
  %2790 = sub nsw i32 0, %2787, !spirv.Decorations !8798
  %2791 = icmp eq i32 %2789, 0		; visa id: 2687
  %2792 = select i1 %2791, i32 %2787, i32 %2790		; visa id: 2689
  %2793 = sitofp i32 %2792 to float		; visa id: 2690
  %2794 = fmul float %2782, %2793		; visa id: 2691
  br label %2803, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2692

2795:                                             ; preds = %2737
; BB323 :
  %2796 = uitofp i32 %2787 to float		; visa id: 2694
  %2797 = fmul float %2782, %2796		; visa id: 2695
  %2798 = and i32 %146, 256
  %2799 = icmp eq i32 %2798, 0		; visa id: 2696
  %2800 = select i1 %2799, i32 1, i32 -1		; visa id: 2698
  %2801 = sitofp i32 %2800 to float		; visa id: 2699
  %2802 = fmul float %2797, %2801		; visa id: 2700
  br label %2803, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2701

2803:                                             ; preds = %2795, %2788
; BB324 :
  %.sroa.065.13 = phi float [ %2802, %2795 ], [ %2794, %2788 ]
  %2804 = bitcast i32 %1829 to <4 x i8>
  %2805 = extractelement <4 x i8> %2804, i32 1
  %2806 = zext i8 %2805 to i32		; visa id: 2702
  br i1 %2786, label %2814, label %2807, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2703

2807:                                             ; preds = %2803
; BB325 :
  %2808 = and i32 %146, 512
  %2809 = sub nsw i32 0, %2806, !spirv.Decorations !8798
  %2810 = icmp eq i32 %2808, 0		; visa id: 2705
  %2811 = select i1 %2810, i32 %2806, i32 %2809		; visa id: 2707
  %2812 = sitofp i32 %2811 to float		; visa id: 2708
  %2813 = fmul float %2782, %2812		; visa id: 2709
  br label %2822, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2710

2814:                                             ; preds = %2803
; BB326 :
  %2815 = uitofp i32 %2806 to float		; visa id: 2712
  %2816 = fmul float %2782, %2815		; visa id: 2713
  %2817 = and i32 %146, 512
  %2818 = icmp eq i32 %2817, 0		; visa id: 2714
  %2819 = select i1 %2818, i32 1, i32 -1		; visa id: 2716
  %2820 = sitofp i32 %2819 to float		; visa id: 2717
  %2821 = fmul float %2816, %2820		; visa id: 2718
  br label %2822, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2719

2822:                                             ; preds = %2814, %2807
; BB327 :
  %.sroa.80.13 = phi float [ %2821, %2814 ], [ %2813, %2807 ]
  %2823 = extractelement <4 x i8> %2804, i32 2
  %2824 = zext i8 %2823 to i32		; visa id: 2720
  br i1 %2786, label %2832, label %2825, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2721

2825:                                             ; preds = %2822
; BB328 :
  %2826 = and i32 %146, 1024
  %2827 = sub nsw i32 0, %2824, !spirv.Decorations !8798
  %2828 = icmp eq i32 %2826, 0		; visa id: 2723
  %2829 = select i1 %2828, i32 %2824, i32 %2827		; visa id: 2725
  %2830 = sitofp i32 %2829 to float		; visa id: 2726
  %2831 = fmul float %2782, %2830		; visa id: 2727
  br label %2840, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2728

2832:                                             ; preds = %2822
; BB329 :
  %2833 = uitofp i32 %2824 to float		; visa id: 2730
  %2834 = fmul float %2782, %2833		; visa id: 2731
  %2835 = and i32 %146, 1024
  %2836 = icmp eq i32 %2835, 0		; visa id: 2732
  %2837 = select i1 %2836, i32 1, i32 -1		; visa id: 2734
  %2838 = sitofp i32 %2837 to float		; visa id: 2735
  %2839 = fmul float %2834, %2838		; visa id: 2736
  br label %2840, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2737

2840:                                             ; preds = %2832, %2825
; BB330 :
  %.sroa.128.13 = phi float [ %2839, %2832 ], [ %2831, %2825 ]
  %2841 = lshr i32 %1829, 24		; visa id: 2738
  br i1 %2786, label %2849, label %2842, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2739

2842:                                             ; preds = %2840
; BB331 :
  %2843 = and i32 %146, 2048
  %2844 = sub nsw i32 0, %2841, !spirv.Decorations !8798
  %2845 = icmp eq i32 %2843, 0		; visa id: 2741
  %2846 = select i1 %2845, i32 %2841, i32 %2844		; visa id: 2743
  %2847 = sitofp i32 %2846 to float		; visa id: 2744
  %2848 = fmul float %2782, %2847		; visa id: 2745
  br label %2857, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2746

2849:                                             ; preds = %2840
; BB332 :
  %2850 = uitofp i32 %2841 to float		; visa id: 2748
  %2851 = fmul float %2782, %2850		; visa id: 2749
  %2852 = and i32 %146, 2048
  %2853 = icmp eq i32 %2852, 0		; visa id: 2750
  %2854 = select i1 %2853, i32 1, i32 -1		; visa id: 2752
  %2855 = sitofp i32 %2854 to float		; visa id: 2753
  %2856 = fmul float %2851, %2855		; visa id: 2754
  br label %2857, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2755

2857:                                             ; preds = %2849, %2842
; BB333 :
  %.sroa.176.13 = phi float [ %2856, %2849 ], [ %2848, %2842 ]
  %2858 = and i32 %1830, 255		; visa id: 2756
  br i1 %2786, label %2866, label %2859, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2757

2859:                                             ; preds = %2857
; BB334 :
  %2860 = and i32 %146, 4096
  %2861 = sub nsw i32 0, %2858, !spirv.Decorations !8798
  %2862 = icmp eq i32 %2860, 0		; visa id: 2759
  %2863 = select i1 %2862, i32 %2858, i32 %2861		; visa id: 2761
  %2864 = sitofp i32 %2863 to float		; visa id: 2762
  %2865 = fmul float %2782, %2864		; visa id: 2763
  br label %2874, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2764

2866:                                             ; preds = %2857
; BB335 :
  %2867 = uitofp i32 %2858 to float		; visa id: 2766
  %2868 = fmul float %2782, %2867		; visa id: 2767
  %2869 = and i32 %146, 4096
  %2870 = icmp eq i32 %2869, 0		; visa id: 2768
  %2871 = select i1 %2870, i32 1, i32 -1		; visa id: 2770
  %2872 = sitofp i32 %2871 to float		; visa id: 2771
  %2873 = fmul float %2868, %2872		; visa id: 2772
  br label %2874, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2773

2874:                                             ; preds = %2866, %2859
; BB336 :
  %.sroa.224.13 = phi float [ %2873, %2866 ], [ %2865, %2859 ]
  %2875 = bitcast i32 %1830 to <4 x i8>
  %2876 = extractelement <4 x i8> %2875, i32 1
  %2877 = zext i8 %2876 to i32		; visa id: 2774
  br i1 %2786, label %2885, label %2878, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2775

2878:                                             ; preds = %2874
; BB337 :
  %2879 = and i32 %146, 8192
  %2880 = sub nsw i32 0, %2877, !spirv.Decorations !8798
  %2881 = icmp eq i32 %2879, 0		; visa id: 2777
  %2882 = select i1 %2881, i32 %2877, i32 %2880		; visa id: 2779
  %2883 = sitofp i32 %2882 to float		; visa id: 2780
  %2884 = fmul float %2782, %2883		; visa id: 2781
  br label %2893, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2782

2885:                                             ; preds = %2874
; BB338 :
  %2886 = uitofp i32 %2877 to float		; visa id: 2784
  %2887 = fmul float %2782, %2886		; visa id: 2785
  %2888 = and i32 %146, 8192
  %2889 = icmp eq i32 %2888, 0		; visa id: 2786
  %2890 = select i1 %2889, i32 1, i32 -1		; visa id: 2788
  %2891 = sitofp i32 %2890 to float		; visa id: 2789
  %2892 = fmul float %2887, %2891		; visa id: 2790
  br label %2893, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2791

2893:                                             ; preds = %2885, %2878
; BB339 :
  %.sroa.272.13 = phi float [ %2892, %2885 ], [ %2884, %2878 ]
  %2894 = extractelement <4 x i8> %2875, i32 2
  %2895 = zext i8 %2894 to i32		; visa id: 2792
  br i1 %2786, label %2903, label %2896, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2793

2896:                                             ; preds = %2893
; BB340 :
  %2897 = and i32 %146, 16384
  %2898 = sub nsw i32 0, %2895, !spirv.Decorations !8798
  %2899 = icmp eq i32 %2897, 0		; visa id: 2795
  %2900 = select i1 %2899, i32 %2895, i32 %2898		; visa id: 2797
  %2901 = sitofp i32 %2900 to float		; visa id: 2798
  %2902 = fmul float %2782, %2901		; visa id: 2799
  br label %2911, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2800

2903:                                             ; preds = %2893
; BB341 :
  %2904 = uitofp i32 %2895 to float		; visa id: 2802
  %2905 = fmul float %2782, %2904		; visa id: 2803
  %2906 = and i32 %146, 16384
  %2907 = icmp eq i32 %2906, 0		; visa id: 2804
  %2908 = select i1 %2907, i32 1, i32 -1		; visa id: 2806
  %2909 = sitofp i32 %2908 to float		; visa id: 2807
  %2910 = fmul float %2905, %2909		; visa id: 2808
  br label %2911, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2809

2911:                                             ; preds = %2903, %2896
; BB342 :
  %.sroa.320.13 = phi float [ %2910, %2903 ], [ %2902, %2896 ]
  %2912 = lshr i32 %1830, 24		; visa id: 2810
  br i1 %2786, label %2920, label %2913, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2811

2913:                                             ; preds = %2911
; BB343 :
  %2914 = and i32 %146, 32768
  %2915 = sub nsw i32 0, %2912, !spirv.Decorations !8798
  %2916 = icmp eq i32 %2914, 0		; visa id: 2813
  %2917 = select i1 %2916, i32 %2912, i32 %2915		; visa id: 2815
  %2918 = sitofp i32 %2917 to float		; visa id: 2816
  %2919 = fmul float %2782, %2918		; visa id: 2817
  br label %.preheader.2.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2818

2920:                                             ; preds = %2911
; BB344 :
  %2921 = uitofp i32 %2912 to float		; visa id: 2820
  %2922 = fmul float %2782, %2921		; visa id: 2821
  %2923 = and i32 %146, 32768
  %2924 = icmp eq i32 %2923, 0		; visa id: 2822
  %2925 = select i1 %2924, i32 1, i32 -1		; visa id: 2824
  %2926 = sitofp i32 %2925 to float		; visa id: 2825
  %2927 = fmul float %2922, %2926		; visa id: 2826
  br label %.preheader.2.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2827

.preheader.2.1:                                   ; preds = %2920, %2913
; BB345 :
  %.sroa.368.13 = phi float [ %2927, %2920 ], [ %2919, %2913 ]
  %2928 = fmul float %.sroa.065.13, %2740		; visa id: 2828
  %2929 = fadd float %.sroa.33.0, %2928		; visa id: 2829
  %2930 = fmul float %.sroa.80.13, %2745		; visa id: 2830
  %2931 = fadd float %2929, %2930		; visa id: 2831
  %2932 = fmul float %.sroa.128.13, %2750		; visa id: 2832
  %2933 = fadd float %2931, %2932		; visa id: 2833
  %2934 = fmul float %.sroa.176.13, %2755		; visa id: 2834
  %2935 = fadd float %2933, %2934		; visa id: 2835
  %2936 = fmul float %.sroa.224.13, %2760		; visa id: 2836
  %2937 = fadd float %2935, %2936		; visa id: 2837
  %2938 = fmul float %.sroa.272.13, %2765		; visa id: 2838
  %2939 = fadd float %2937, %2938		; visa id: 2839
  %2940 = fmul float %.sroa.320.13, %2770		; visa id: 2840
  %2941 = fadd float %2939, %2940		; visa id: 2841
  %2942 = fmul float %.sroa.368.13, %2775		; visa id: 2842
  %2943 = fadd float %2941, %2942		; visa id: 2843
  %2944 = or i32 %257, 112		; visa id: 2844
  %2945 = zext i32 %2944 to i64		; visa id: 2845
  %2946 = add i64 %2945, %const_reg_qword2		; visa id: 2846
  %IntToPtr2632 = inttoptr i64 %2946 to ptr addrspace(1)		; visa id: 2847
  %vCastload633 = load i32, ptr addrspace(1) %IntToPtr2632, align 2		; visa id: 2847
  %2947 = add i64 %2946, 4
  %IntToPtr2634 = inttoptr i64 %2947 to ptr addrspace(1)
  %vCastload635 = load i32, ptr addrspace(1) %IntToPtr2634, align 2		; visa id: 2848
  %2948 = add i64 %2946, 8
  %IntToPtr2636 = inttoptr i64 %2948 to ptr addrspace(1)
  %vCastload637 = load i32, ptr addrspace(1) %IntToPtr2636, align 2		; visa id: 2849
  %2949 = add i64 %2946, 12
  %IntToPtr2638 = inttoptr i64 %2949 to ptr addrspace(1)
  %vCastload639 = load i32, ptr addrspace(1) %IntToPtr2638, align 2		; visa id: 2850
  %2950 = bitcast i32 %vCastload633 to <2 x i16>		; visa id: 2851
  %2951 = bitcast i32 %vCastload635 to <2 x i16>		; visa id: 2853
  %2952 = extractelement <2 x i16> %2950, i32 0		; visa id: 2855
  %2953 = extractelement <2 x i16> %2950, i32 1		; visa id: 2855
  %2954 = extractelement <2 x i16> %2951, i32 0		; visa id: 2855
  %2955 = extractelement <2 x i16> %2951, i32 1		; visa id: 2855
  %2956 = bitcast i32 %vCastload637 to <2 x i16>		; visa id: 2855
  %2957 = bitcast i32 %vCastload639 to <2 x i16>		; visa id: 2857
  %2958 = extractelement <2 x i16> %2956, i32 0		; visa id: 2859
  %2959 = extractelement <2 x i16> %2956, i32 1		; visa id: 2859
  %2960 = extractelement <2 x i16> %2957, i32 0		; visa id: 2859
  %2961 = extractelement <2 x i16> %2957, i32 1		; visa id: 2859
  %2962 = and i32 %1783, 255		; visa id: 2859
  br i1 %2595, label %2970, label %2963, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2860

2963:                                             ; preds = %.preheader.2.1
; BB346 :
  %2964 = and i32 %125, 16777216
  %2965 = sub nsw i32 0, %2962, !spirv.Decorations !8798
  %2966 = icmp eq i32 %2964, 0		; visa id: 2862
  %2967 = select i1 %2966, i32 %2962, i32 %2965		; visa id: 2864
  %2968 = sitofp i32 %2967 to float		; visa id: 2865
  %2969 = fmul float %2588, %2968		; visa id: 2866
  br label %2978, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2867

2970:                                             ; preds = %.preheader.2.1
; BB347 :
  %2971 = uitofp i32 %2962 to float		; visa id: 2869
  %2972 = fmul float %2588, %2971		; visa id: 2870
  %2973 = and i32 %125, 16777216
  %2974 = icmp eq i32 %2973, 0		; visa id: 2871
  %2975 = select i1 %2974, i32 1, i32 -1		; visa id: 2873
  %2976 = sitofp i32 %2975 to float		; visa id: 2874
  %2977 = fmul float %2972, %2976		; visa id: 2875
  br label %2978, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2876

2978:                                             ; preds = %2970, %2963
; BB348 :
  %.sroa.065.14 = phi float [ %2977, %2970 ], [ %2969, %2963 ]
  %2979 = bitcast i32 %1783 to <4 x i8>
  %2980 = extractelement <4 x i8> %2979, i32 1
  %2981 = zext i8 %2980 to i32		; visa id: 2877
  br i1 %2595, label %2989, label %2982, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2878

2982:                                             ; preds = %2978
; BB349 :
  %2983 = and i32 %125, 33554432
  %2984 = sub nsw i32 0, %2981, !spirv.Decorations !8798
  %2985 = icmp eq i32 %2983, 0		; visa id: 2880
  %2986 = select i1 %2985, i32 %2981, i32 %2984		; visa id: 2882
  %2987 = sitofp i32 %2986 to float		; visa id: 2883
  %2988 = fmul float %2588, %2987		; visa id: 2884
  br label %2997, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2885

2989:                                             ; preds = %2978
; BB350 :
  %2990 = uitofp i32 %2981 to float		; visa id: 2887
  %2991 = fmul float %2588, %2990		; visa id: 2888
  %2992 = and i32 %125, 33554432
  %2993 = icmp eq i32 %2992, 0		; visa id: 2889
  %2994 = select i1 %2993, i32 1, i32 -1		; visa id: 2891
  %2995 = sitofp i32 %2994 to float		; visa id: 2892
  %2996 = fmul float %2991, %2995		; visa id: 2893
  br label %2997, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2894

2997:                                             ; preds = %2989, %2982
; BB351 :
  %.sroa.80.14 = phi float [ %2996, %2989 ], [ %2988, %2982 ]
  %2998 = extractelement <4 x i8> %2979, i32 2
  %2999 = zext i8 %2998 to i32		; visa id: 2895
  br i1 %2595, label %3007, label %3000, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2896

3000:                                             ; preds = %2997
; BB352 :
  %3001 = and i32 %125, 67108864
  %3002 = sub nsw i32 0, %2999, !spirv.Decorations !8798
  %3003 = icmp eq i32 %3001, 0		; visa id: 2898
  %3004 = select i1 %3003, i32 %2999, i32 %3002		; visa id: 2900
  %3005 = sitofp i32 %3004 to float		; visa id: 2901
  %3006 = fmul float %2588, %3005		; visa id: 2902
  br label %3015, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2903

3007:                                             ; preds = %2997
; BB353 :
  %3008 = uitofp i32 %2999 to float		; visa id: 2905
  %3009 = fmul float %2588, %3008		; visa id: 2906
  %3010 = and i32 %125, 67108864
  %3011 = icmp eq i32 %3010, 0		; visa id: 2907
  %3012 = select i1 %3011, i32 1, i32 -1		; visa id: 2909
  %3013 = sitofp i32 %3012 to float		; visa id: 2910
  %3014 = fmul float %3009, %3013		; visa id: 2911
  br label %3015, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2912

3015:                                             ; preds = %3007, %3000
; BB354 :
  %.sroa.128.14 = phi float [ %3014, %3007 ], [ %3006, %3000 ]
  %3016 = lshr i32 %1783, 24		; visa id: 2913
  br i1 %2595, label %3024, label %3017, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2914

3017:                                             ; preds = %3015
; BB355 :
  %3018 = and i32 %125, 134217728
  %3019 = sub nsw i32 0, %3016, !spirv.Decorations !8798
  %3020 = icmp eq i32 %3018, 0		; visa id: 2916
  %3021 = select i1 %3020, i32 %3016, i32 %3019		; visa id: 2918
  %3022 = sitofp i32 %3021 to float		; visa id: 2919
  %3023 = fmul float %2588, %3022		; visa id: 2920
  br label %3032, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2921

3024:                                             ; preds = %3015
; BB356 :
  %3025 = uitofp i32 %3016 to float		; visa id: 2923
  %3026 = fmul float %2588, %3025		; visa id: 2924
  %3027 = and i32 %125, 134217728
  %3028 = icmp eq i32 %3027, 0		; visa id: 2925
  %3029 = select i1 %3028, i32 1, i32 -1		; visa id: 2927
  %3030 = sitofp i32 %3029 to float		; visa id: 2928
  %3031 = fmul float %3026, %3030		; visa id: 2929
  br label %3032, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2930

3032:                                             ; preds = %3024, %3017
; BB357 :
  %.sroa.176.14 = phi float [ %3031, %3024 ], [ %3023, %3017 ]
  %3033 = and i32 %1784, 255		; visa id: 2931
  br i1 %2595, label %3041, label %3034, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2932

3034:                                             ; preds = %3032
; BB358 :
  %3035 = and i32 %125, 268435456
  %3036 = sub nsw i32 0, %3033, !spirv.Decorations !8798
  %3037 = icmp eq i32 %3035, 0		; visa id: 2934
  %3038 = select i1 %3037, i32 %3033, i32 %3036		; visa id: 2936
  %3039 = sitofp i32 %3038 to float		; visa id: 2937
  %3040 = fmul float %2588, %3039		; visa id: 2938
  br label %3049, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2939

3041:                                             ; preds = %3032
; BB359 :
  %3042 = uitofp i32 %3033 to float		; visa id: 2941
  %3043 = fmul float %2588, %3042		; visa id: 2942
  %3044 = and i32 %125, 268435456
  %3045 = icmp eq i32 %3044, 0		; visa id: 2943
  %3046 = select i1 %3045, i32 1, i32 -1		; visa id: 2945
  %3047 = sitofp i32 %3046 to float		; visa id: 2946
  %3048 = fmul float %3043, %3047		; visa id: 2947
  br label %3049, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2948

3049:                                             ; preds = %3041, %3034
; BB360 :
  %.sroa.224.14 = phi float [ %3048, %3041 ], [ %3040, %3034 ]
  %3050 = bitcast i32 %1784 to <4 x i8>
  %3051 = extractelement <4 x i8> %3050, i32 1
  %3052 = zext i8 %3051 to i32		; visa id: 2949
  br i1 %2595, label %3060, label %3053, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2950

3053:                                             ; preds = %3049
; BB361 :
  %3054 = and i32 %125, 536870912
  %3055 = sub nsw i32 0, %3052, !spirv.Decorations !8798
  %3056 = icmp eq i32 %3054, 0		; visa id: 2952
  %3057 = select i1 %3056, i32 %3052, i32 %3055		; visa id: 2954
  %3058 = sitofp i32 %3057 to float		; visa id: 2955
  %3059 = fmul float %2588, %3058		; visa id: 2956
  br label %3068, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2957

3060:                                             ; preds = %3049
; BB362 :
  %3061 = uitofp i32 %3052 to float		; visa id: 2959
  %3062 = fmul float %2588, %3061		; visa id: 2960
  %3063 = and i32 %125, 536870912
  %3064 = icmp eq i32 %3063, 0		; visa id: 2961
  %3065 = select i1 %3064, i32 1, i32 -1		; visa id: 2963
  %3066 = sitofp i32 %3065 to float		; visa id: 2964
  %3067 = fmul float %3062, %3066		; visa id: 2965
  br label %3068, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2966

3068:                                             ; preds = %3060, %3053
; BB363 :
  %.sroa.272.14 = phi float [ %3067, %3060 ], [ %3059, %3053 ]
  %3069 = extractelement <4 x i8> %3050, i32 2
  %3070 = zext i8 %3069 to i32		; visa id: 2967
  br i1 %2595, label %3078, label %3071, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2968

3071:                                             ; preds = %3068
; BB364 :
  %3072 = and i32 %125, 1073741824
  %3073 = sub nsw i32 0, %3070, !spirv.Decorations !8798
  %3074 = icmp eq i32 %3072, 0		; visa id: 2970
  %3075 = select i1 %3074, i32 %3070, i32 %3073		; visa id: 2972
  %3076 = sitofp i32 %3075 to float		; visa id: 2973
  %3077 = fmul float %2588, %3076		; visa id: 2974
  br label %3086, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2975

3078:                                             ; preds = %3068
; BB365 :
  %3079 = uitofp i32 %3070 to float		; visa id: 2977
  %3080 = fmul float %2588, %3079		; visa id: 2978
  %3081 = and i32 %125, 1073741824
  %3082 = icmp eq i32 %3081, 0		; visa id: 2979
  %3083 = select i1 %3082, i32 1, i32 -1		; visa id: 2981
  %3084 = sitofp i32 %3083 to float		; visa id: 2982
  %3085 = fmul float %3080, %3084		; visa id: 2983
  br label %3086, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2984

3086:                                             ; preds = %3078, %3071
; BB366 :
  %.sroa.320.14 = phi float [ %3085, %3078 ], [ %3077, %3071 ]
  %3087 = lshr i32 %1784, 24		; visa id: 2985
  br i1 %2595, label %3094, label %3088, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2986

3088:                                             ; preds = %3086
; BB367 :
  %3089 = sub nsw i32 0, %3087, !spirv.Decorations !8798
  %3090 = icmp slt i32 %125, 0		; visa id: 2988
  %3091 = select i1 %3090, i32 %3089, i32 %3087		; visa id: 2989
  %3092 = sitofp i32 %3091 to float		; visa id: 2990
  %3093 = fmul float %2588, %3092		; visa id: 2991
  br label %3101, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2992

3094:                                             ; preds = %3086
; BB368 :
  %3095 = uitofp i32 %3087 to float		; visa id: 2994
  %3096 = fmul float %2588, %3095		; visa id: 2995
  %3097 = icmp sgt i32 %125, -1		; visa id: 2996
  %3098 = select i1 %3097, i32 1, i32 -1		; visa id: 2997
  %3099 = sitofp i32 %3098 to float		; visa id: 2998
  %3100 = fmul float %3096, %3099		; visa id: 2999
  br label %3101, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3000

3101:                                             ; preds = %3094, %3088
; BB369 :
  %.sroa.368.14 = phi float [ %3100, %3094 ], [ %3093, %3088 ]
  %3102 = zext i16 %2952 to i32		; visa id: 3001
  %3103 = shl nuw i32 %3102, 16		; visa id: 3002
  %3104 = bitcast i32 %3103 to float
  %3105 = fmul float %.sroa.065.14, %3104		; visa id: 3003
  %3106 = fadd float %.sroa.18.0, %3105		; visa id: 3004
  %3107 = zext i16 %2953 to i32		; visa id: 3005
  %3108 = shl nuw i32 %3107, 16		; visa id: 3006
  %3109 = bitcast i32 %3108 to float
  %3110 = fmul float %.sroa.80.14, %3109		; visa id: 3007
  %3111 = fadd float %3106, %3110		; visa id: 3008
  %3112 = zext i16 %2954 to i32		; visa id: 3009
  %3113 = shl nuw i32 %3112, 16		; visa id: 3010
  %3114 = bitcast i32 %3113 to float
  %3115 = fmul float %.sroa.128.14, %3114		; visa id: 3011
  %3116 = fadd float %3111, %3115		; visa id: 3012
  %3117 = zext i16 %2955 to i32		; visa id: 3013
  %3118 = shl nuw i32 %3117, 16		; visa id: 3014
  %3119 = bitcast i32 %3118 to float
  %3120 = fmul float %.sroa.176.14, %3119		; visa id: 3015
  %3121 = fadd float %3116, %3120		; visa id: 3016
  %3122 = zext i16 %2958 to i32		; visa id: 3017
  %3123 = shl nuw i32 %3122, 16		; visa id: 3018
  %3124 = bitcast i32 %3123 to float
  %3125 = fmul float %.sroa.224.14, %3124		; visa id: 3019
  %3126 = fadd float %3121, %3125		; visa id: 3020
  %3127 = zext i16 %2959 to i32		; visa id: 3021
  %3128 = shl nuw i32 %3127, 16		; visa id: 3022
  %3129 = bitcast i32 %3128 to float
  %3130 = fmul float %.sroa.272.14, %3129		; visa id: 3023
  %3131 = fadd float %3126, %3130		; visa id: 3024
  %3132 = zext i16 %2960 to i32		; visa id: 3025
  %3133 = shl nuw i32 %3132, 16		; visa id: 3026
  %3134 = bitcast i32 %3133 to float
  %3135 = fmul float %.sroa.320.14, %3134		; visa id: 3027
  %3136 = fadd float %3131, %3135		; visa id: 3028
  %3137 = zext i16 %2961 to i32		; visa id: 3029
  %3138 = shl nuw i32 %3137, 16		; visa id: 3030
  %3139 = bitcast i32 %3138 to float
  %3140 = fmul float %.sroa.368.14, %3139		; visa id: 3031
  %3141 = fadd float %3136, %3140		; visa id: 3032
  %3142 = and i32 %1831, 255		; visa id: 3033
  br i1 %2786, label %3150, label %3143, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3034

3143:                                             ; preds = %3101
; BB370 :
  %3144 = and i32 %146, 16777216
  %3145 = sub nsw i32 0, %3142, !spirv.Decorations !8798
  %3146 = icmp eq i32 %3144, 0		; visa id: 3036
  %3147 = select i1 %3146, i32 %3142, i32 %3145		; visa id: 3038
  %3148 = sitofp i32 %3147 to float		; visa id: 3039
  %3149 = fmul float %2782, %3148		; visa id: 3040
  br label %3158, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3041

3150:                                             ; preds = %3101
; BB371 :
  %3151 = uitofp i32 %3142 to float		; visa id: 3043
  %3152 = fmul float %2782, %3151		; visa id: 3044
  %3153 = and i32 %146, 16777216
  %3154 = icmp eq i32 %3153, 0		; visa id: 3045
  %3155 = select i1 %3154, i32 1, i32 -1		; visa id: 3047
  %3156 = sitofp i32 %3155 to float		; visa id: 3048
  %3157 = fmul float %3152, %3156		; visa id: 3049
  br label %3158, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3050

3158:                                             ; preds = %3150, %3143
; BB372 :
  %.sroa.065.15 = phi float [ %3157, %3150 ], [ %3149, %3143 ]
  %3159 = bitcast i32 %1831 to <4 x i8>
  %3160 = extractelement <4 x i8> %3159, i32 1
  %3161 = zext i8 %3160 to i32		; visa id: 3051
  br i1 %2786, label %3169, label %3162, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3052

3162:                                             ; preds = %3158
; BB373 :
  %3163 = and i32 %146, 33554432
  %3164 = sub nsw i32 0, %3161, !spirv.Decorations !8798
  %3165 = icmp eq i32 %3163, 0		; visa id: 3054
  %3166 = select i1 %3165, i32 %3161, i32 %3164		; visa id: 3056
  %3167 = sitofp i32 %3166 to float		; visa id: 3057
  %3168 = fmul float %2782, %3167		; visa id: 3058
  br label %3177, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3059

3169:                                             ; preds = %3158
; BB374 :
  %3170 = uitofp i32 %3161 to float		; visa id: 3061
  %3171 = fmul float %2782, %3170		; visa id: 3062
  %3172 = and i32 %146, 33554432
  %3173 = icmp eq i32 %3172, 0		; visa id: 3063
  %3174 = select i1 %3173, i32 1, i32 -1		; visa id: 3065
  %3175 = sitofp i32 %3174 to float		; visa id: 3066
  %3176 = fmul float %3171, %3175		; visa id: 3067
  br label %3177, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3068

3177:                                             ; preds = %3169, %3162
; BB375 :
  %.sroa.80.15 = phi float [ %3176, %3169 ], [ %3168, %3162 ]
  %3178 = extractelement <4 x i8> %3159, i32 2
  %3179 = zext i8 %3178 to i32		; visa id: 3069
  br i1 %2786, label %3187, label %3180, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3070

3180:                                             ; preds = %3177
; BB376 :
  %3181 = and i32 %146, 67108864
  %3182 = sub nsw i32 0, %3179, !spirv.Decorations !8798
  %3183 = icmp eq i32 %3181, 0		; visa id: 3072
  %3184 = select i1 %3183, i32 %3179, i32 %3182		; visa id: 3074
  %3185 = sitofp i32 %3184 to float		; visa id: 3075
  %3186 = fmul float %2782, %3185		; visa id: 3076
  br label %3195, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3077

3187:                                             ; preds = %3177
; BB377 :
  %3188 = uitofp i32 %3179 to float		; visa id: 3079
  %3189 = fmul float %2782, %3188		; visa id: 3080
  %3190 = and i32 %146, 67108864
  %3191 = icmp eq i32 %3190, 0		; visa id: 3081
  %3192 = select i1 %3191, i32 1, i32 -1		; visa id: 3083
  %3193 = sitofp i32 %3192 to float		; visa id: 3084
  %3194 = fmul float %3189, %3193		; visa id: 3085
  br label %3195, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3086

3195:                                             ; preds = %3187, %3180
; BB378 :
  %.sroa.128.15 = phi float [ %3194, %3187 ], [ %3186, %3180 ]
  %3196 = lshr i32 %1831, 24		; visa id: 3087
  br i1 %2786, label %3204, label %3197, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3088

3197:                                             ; preds = %3195
; BB379 :
  %3198 = and i32 %146, 134217728
  %3199 = sub nsw i32 0, %3196, !spirv.Decorations !8798
  %3200 = icmp eq i32 %3198, 0		; visa id: 3090
  %3201 = select i1 %3200, i32 %3196, i32 %3199		; visa id: 3092
  %3202 = sitofp i32 %3201 to float		; visa id: 3093
  %3203 = fmul float %2782, %3202		; visa id: 3094
  br label %3212, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3095

3204:                                             ; preds = %3195
; BB380 :
  %3205 = uitofp i32 %3196 to float		; visa id: 3097
  %3206 = fmul float %2782, %3205		; visa id: 3098
  %3207 = and i32 %146, 134217728
  %3208 = icmp eq i32 %3207, 0		; visa id: 3099
  %3209 = select i1 %3208, i32 1, i32 -1		; visa id: 3101
  %3210 = sitofp i32 %3209 to float		; visa id: 3102
  %3211 = fmul float %3206, %3210		; visa id: 3103
  br label %3212, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3104

3212:                                             ; preds = %3204, %3197
; BB381 :
  %.sroa.176.15 = phi float [ %3211, %3204 ], [ %3203, %3197 ]
  %3213 = and i32 %1832, 255		; visa id: 3105
  br i1 %2786, label %3221, label %3214, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3106

3214:                                             ; preds = %3212
; BB382 :
  %3215 = and i32 %146, 268435456
  %3216 = sub nsw i32 0, %3213, !spirv.Decorations !8798
  %3217 = icmp eq i32 %3215, 0		; visa id: 3108
  %3218 = select i1 %3217, i32 %3213, i32 %3216		; visa id: 3110
  %3219 = sitofp i32 %3218 to float		; visa id: 3111
  %3220 = fmul float %2782, %3219		; visa id: 3112
  br label %3229, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3113

3221:                                             ; preds = %3212
; BB383 :
  %3222 = uitofp i32 %3213 to float		; visa id: 3115
  %3223 = fmul float %2782, %3222		; visa id: 3116
  %3224 = and i32 %146, 268435456
  %3225 = icmp eq i32 %3224, 0		; visa id: 3117
  %3226 = select i1 %3225, i32 1, i32 -1		; visa id: 3119
  %3227 = sitofp i32 %3226 to float		; visa id: 3120
  %3228 = fmul float %3223, %3227		; visa id: 3121
  br label %3229, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3122

3229:                                             ; preds = %3221, %3214
; BB384 :
  %.sroa.224.15 = phi float [ %3228, %3221 ], [ %3220, %3214 ]
  %3230 = bitcast i32 %1832 to <4 x i8>
  %3231 = extractelement <4 x i8> %3230, i32 1
  %3232 = zext i8 %3231 to i32		; visa id: 3123
  br i1 %2786, label %3240, label %3233, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3124

3233:                                             ; preds = %3229
; BB385 :
  %3234 = and i32 %146, 536870912
  %3235 = sub nsw i32 0, %3232, !spirv.Decorations !8798
  %3236 = icmp eq i32 %3234, 0		; visa id: 3126
  %3237 = select i1 %3236, i32 %3232, i32 %3235		; visa id: 3128
  %3238 = sitofp i32 %3237 to float		; visa id: 3129
  %3239 = fmul float %2782, %3238		; visa id: 3130
  br label %3248, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3131

3240:                                             ; preds = %3229
; BB386 :
  %3241 = uitofp i32 %3232 to float		; visa id: 3133
  %3242 = fmul float %2782, %3241		; visa id: 3134
  %3243 = and i32 %146, 536870912
  %3244 = icmp eq i32 %3243, 0		; visa id: 3135
  %3245 = select i1 %3244, i32 1, i32 -1		; visa id: 3137
  %3246 = sitofp i32 %3245 to float		; visa id: 3138
  %3247 = fmul float %3242, %3246		; visa id: 3139
  br label %3248, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3140

3248:                                             ; preds = %3240, %3233
; BB387 :
  %.sroa.272.15 = phi float [ %3247, %3240 ], [ %3239, %3233 ]
  %3249 = extractelement <4 x i8> %3230, i32 2
  %3250 = zext i8 %3249 to i32		; visa id: 3141
  br i1 %2786, label %3258, label %3251, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3142

3251:                                             ; preds = %3248
; BB388 :
  %3252 = and i32 %146, 1073741824
  %3253 = sub nsw i32 0, %3250, !spirv.Decorations !8798
  %3254 = icmp eq i32 %3252, 0		; visa id: 3144
  %3255 = select i1 %3254, i32 %3250, i32 %3253		; visa id: 3146
  %3256 = sitofp i32 %3255 to float		; visa id: 3147
  %3257 = fmul float %2782, %3256		; visa id: 3148
  br label %3266, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3149

3258:                                             ; preds = %3248
; BB389 :
  %3259 = uitofp i32 %3250 to float		; visa id: 3151
  %3260 = fmul float %2782, %3259		; visa id: 3152
  %3261 = and i32 %146, 1073741824
  %3262 = icmp eq i32 %3261, 0		; visa id: 3153
  %3263 = select i1 %3262, i32 1, i32 -1		; visa id: 3155
  %3264 = sitofp i32 %3263 to float		; visa id: 3156
  %3265 = fmul float %3260, %3264		; visa id: 3157
  br label %3266, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3158

3266:                                             ; preds = %3258, %3251
; BB390 :
  %.sroa.320.15 = phi float [ %3265, %3258 ], [ %3257, %3251 ]
  %3267 = lshr i32 %1832, 24		; visa id: 3159
  br i1 %2786, label %3274, label %3268, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3160

3268:                                             ; preds = %3266
; BB391 :
  %3269 = sub nsw i32 0, %3267, !spirv.Decorations !8798
  %3270 = icmp slt i32 %146, 0		; visa id: 3162
  %3271 = select i1 %3270, i32 %3269, i32 %3267		; visa id: 3163
  %3272 = sitofp i32 %3271 to float		; visa id: 3164
  %3273 = fmul float %2782, %3272		; visa id: 3165
  br label %.preheader.3.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3166

3274:                                             ; preds = %3266
; BB392 :
  %3275 = uitofp i32 %3267 to float		; visa id: 3168
  %3276 = fmul float %2782, %3275		; visa id: 3169
  %3277 = icmp sgt i32 %146, -1		; visa id: 3170
  %3278 = select i1 %3277, i32 1, i32 -1		; visa id: 3171
  %3279 = sitofp i32 %3278 to float		; visa id: 3172
  %3280 = fmul float %3276, %3279		; visa id: 3173
  br label %.preheader.3.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3174

.preheader.3.1:                                   ; preds = %3274, %3268
; BB393 :
  %.sroa.368.15 = phi float [ %3280, %3274 ], [ %3273, %3268 ]
  %3281 = fmul float %.sroa.065.15, %3104		; visa id: 3175
  %3282 = fadd float %.sroa.35.0, %3281		; visa id: 3176
  %3283 = fmul float %.sroa.80.15, %3109		; visa id: 3177
  %3284 = fadd float %3282, %3283		; visa id: 3178
  %3285 = fmul float %.sroa.128.15, %3114		; visa id: 3179
  %3286 = fadd float %3284, %3285		; visa id: 3180
  %3287 = fmul float %.sroa.176.15, %3119		; visa id: 3181
  %3288 = fadd float %3286, %3287		; visa id: 3182
  %3289 = fmul float %.sroa.224.15, %3124		; visa id: 3183
  %3290 = fadd float %3288, %3289		; visa id: 3184
  %3291 = fmul float %.sroa.272.15, %3129		; visa id: 3185
  %3292 = fadd float %3290, %3291		; visa id: 3186
  %3293 = fmul float %.sroa.320.15, %3134		; visa id: 3187
  %3294 = fadd float %3292, %3293		; visa id: 3188
  %3295 = fmul float %.sroa.368.15, %3139		; visa id: 3189
  %3296 = fadd float %3294, %3295		; visa id: 3190
  %3297 = icmp ult i32 %114, 9		; visa id: 3191
  br i1 %3297, label %.preheader.3.1.._crit_edge45_crit_edge, label %.preheader41, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3192

.preheader.3.1.._crit_edge45_crit_edge:           ; preds = %.preheader.3.1
; BB394 :
  %3298 = add nuw nsw i32 %114, 1, !spirv.Decorations !8791		; visa id: 3194
  br label %._crit_edge45, !stats.blockFrequency.digits !8799, !stats.blockFrequency.scale !8797		; visa id: 3195

.preheader41:                                     ; preds = %.preheader.3.1
; BB395 :
  %.lcssa661 = phi float [ %3296, %.preheader.3.1 ]
  %.lcssa660 = phi float [ %3141, %.preheader.3.1 ]
  %.lcssa659 = phi float [ %2943, %.preheader.3.1 ]
  %.lcssa658 = phi float [ %2777, %.preheader.3.1 ]
  %.lcssa657 = phi float [ %2565, %.preheader.3.1 ]
  %.lcssa656 = phi float [ %2410, %.preheader.3.1 ]
  %.lcssa655 = phi float [ %2212, %.preheader.3.1 ]
  %.lcssa654 = phi float [ %2045, %.preheader.3.1 ]
  %.lcssa653 = phi float [ %1736, %.preheader.3.1 ]
  %.lcssa652 = phi float [ %1581, %.preheader.3.1 ]
  %.lcssa651 = phi float [ %1383, %.preheader.3.1 ]
  %.lcssa650 = phi float [ %1217, %.preheader.3.1 ]
  %.lcssa649 = phi float [ %1005, %.preheader.3.1 ]
  %.lcssa648 = phi float [ %850, %.preheader.3.1 ]
  %.lcssa647 = phi float [ %652, %.preheader.3.1 ]
  %.lcssa = phi float [ %475, %.preheader.3.1 ]
  %3299 = fadd float %.lcssa, %.lcssa648		; visa id: 3197
  %3300 = fadd float %.lcssa650, %.lcssa652		; visa id: 3198
  %3301 = fadd float %.lcssa654, %.lcssa656		; visa id: 3199
  %3302 = fadd float %.lcssa658, %.lcssa660		; visa id: 3200
  %3303 = fadd float %3299, %3300		; visa id: 3201
  %3304 = fadd float %3301, %3302		; visa id: 3202
  %3305 = fadd float %3303, %3304		; visa id: 3203
  %3306 = fadd float %.lcssa647, %.lcssa649		; visa id: 3204
  %3307 = fadd float %.lcssa651, %.lcssa653		; visa id: 3205
  %3308 = fadd float %.lcssa655, %.lcssa657		; visa id: 3206
  %3309 = fadd float %.lcssa659, %.lcssa661		; visa id: 3207
  %3310 = fadd float %3306, %3307		; visa id: 3208
  %3311 = fadd float %3308, %3309		; visa id: 3209
  %3312 = fadd float %3310, %3311		; visa id: 3210
  br label %._crit_edge43, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8790		; visa id: 3213

._crit_edge:                                      ; preds = %precompiled_u32divrem_sp.exit
; BB396 :
  %.pre479 = zext i32 %retval.0.i to i64		; visa id: 3215
  br label %._crit_edge43, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 3220

._crit_edge43:                                    ; preds = %.._crit_edge43_crit_edge, %._crit_edge, %._crit_edge44, %.preheader41
; BB397 :
  %.pre-phi = phi i64 [ %33, %._crit_edge44 ], [ %33, %.preheader41 ], [ %.pre479, %._crit_edge ], [ %33, %.._crit_edge43_crit_edge ]
  %.sroa.7.0 = phi float [ 0.000000e+00, %._crit_edge44 ], [ %3312, %.preheader41 ], [ 0.000000e+00, %._crit_edge ], [ 0.000000e+00, %.._crit_edge43_crit_edge ]
  %.sroa.064.0 = phi float [ 0.000000e+00, %._crit_edge44 ], [ %3305, %.preheader41 ], [ 0.000000e+00, %._crit_edge ], [ 0.000000e+00, %.._crit_edge43_crit_edge ]
  %3313 = phi i32 [ 0, %._crit_edge44 ], [ -1, %.preheader41 ], [ 0, %._crit_edge ], [ 0, %.._crit_edge43_crit_edge ]
  %3314 = phi i32 [ %62, %._crit_edge44 ], [ 0, %.preheader41 ], [ -1, %._crit_edge ], [ -1, %.._crit_edge43_crit_edge ]
  %3315 = icmp ne i32 %3313, 0		; visa id: 3221
  %3316 = icmp ne i32 %6, 0		; visa id: 3222
  %3317 = or i1 %30, %3316		; visa id: 3223
  %3318 = zext i32 %13 to i64		; visa id: 3225
  %3319 = icmp eq i32 %13, %29		; visa id: 3226
  %3320 = icmp ne i32 %3314, 0		; visa id: 3227
  %3321 = sext i1 %3320 to i32		; visa id: 3228
  %3322 = sub i32 0, %3321		; visa id: 3229
  %3323 = addrspacecast ptr addrspace(4) %4 to ptr addrspace(1)		; visa id: 3230
  %3324 = addrspacecast ptr addrspace(4) %5 to ptr addrspace(1)		; visa id: 3231
  %3325 = add nuw nsw i32 %simdLaneId, 1		; visa id: 3232
  %3326 = and i32 %3325, 31		; visa id: 3233
  %simdShuffle = call float @llvm.genx.GenISA.WaveShuffleIndex.f32(float %.sroa.064.0, i32 %3326, i32 0)		; visa id: 3234
  %3327 = and i32 %simdLaneId, 1
  %3328 = icmp eq i32 %3327, 0		; visa id: 3241
  %3329 = select i1 %3328, float %simdShuffle, float -0.000000e+00		; visa id: 3243
  %3330 = fadd float %.sroa.064.0, %3329		; visa id: 3244
  %3331 = add nuw nsw i32 %simdLaneId, 2		; visa id: 3245
  %3332 = and i32 %3331, 31		; visa id: 3246
  %simdShuffle.1 = call float @llvm.genx.GenISA.WaveShuffleIndex.f32(float %3330, i32 %3332, i32 0)		; visa id: 3247
  %3333 = icmp eq i32 %6, 0		; visa id: 3254
  br i1 %3317, label %._crit_edge43.._crit_edge47_crit_edge, label %3334, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8782		; visa id: 3255

._crit_edge43.._crit_edge47_crit_edge:            ; preds = %._crit_edge43
; BB:
  br label %._crit_edge47, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787

3334:                                             ; preds = %._crit_edge43
; BB399 :
  %3335 = select i1 %3333, float %simdShuffle.1, float -0.000000e+00		; visa id: 3257
  %3336 = fadd float %3330, %3335		; visa id: 3258
  %3337 = bitcast float %3336 to i32
  %3338 = select i1 %3315, i32 %3337, i32 2143289344		; visa id: 3259
  %3339 = and i32 %3338, 2147483647		; visa id: 3260
  %3340 = icmp ugt i32 %3339, 2139095040		; visa id: 3261
  br i1 %3340, label %3348, label %3341, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 3262

3341:                                             ; preds = %3334
; BB400 :
  %3342 = lshr i32 %3338, 16		; visa id: 3264
  %3343 = and i32 %3342, 1		; visa id: 3265
  %3344 = add i32 %3338, %3343
  %3345 = add i32 %3344, 32767		; visa id: 3266
  %3346 = lshr i32 %3345, 16		; visa id: 3267
  %3347 = trunc i32 %3346 to i16		; visa id: 3268
  br label %3352, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 3269

3348:                                             ; preds = %3334
; BB401 :
  %3349 = lshr i32 %3338, 16		; visa id: 3271
  %3350 = trunc i32 %3349 to i16		; visa id: 3272
  %3351 = or i16 %3350, 64		; visa id: 3273
  br label %3352, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 3274

3352:                                             ; preds = %3341, %3348
; BB402 :
  %3353 = phi i16 [ %3351, %3348 ], [ %3347, %3341 ]
  %3354 = shl nuw nsw i64 %3318, 1		; visa id: 3275
  %3355 = add i64 %3354, %const_reg_qword12		; visa id: 3276
  %3356 = inttoptr i64 %3355 to ptr addrspace(4)		; visa id: 3277
  %3357 = addrspacecast ptr addrspace(4) %3356 to ptr addrspace(1)		; visa id: 3277
  store i16 %3353, ptr addrspace(1) %3357, align 2		; visa id: 3278
  br i1 %3319, label %3358, label %.._crit_edge47_crit_edge, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 3280

.._crit_edge47_crit_edge:                         ; preds = %3352
; BB:
  br label %._crit_edge47, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784

3358:                                             ; preds = %3352
; BB404 :
  %3359 = shl nuw nsw i64 %.pre-phi, 2		; visa id: 3282
  %3360 = add i64 %3359, %const_reg_qword17		; visa id: 3283
  %3361 = inttoptr i64 %3360 to ptr addrspace(4)		; visa id: 3284
  %3362 = addrspacecast ptr addrspace(4) %3361 to ptr addrspace(1)		; visa id: 3284
  store i32 %3322, ptr addrspace(1) %3362, align 4		; visa id: 3285
  br i1 %3320, label %3363, label %.._crit_edge47_crit_edge574, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 3286

.._crit_edge47_crit_edge574:                      ; preds = %3358
; BB:
  br label %._crit_edge47, !stats.blockFrequency.digits !8800, !stats.blockFrequency.scale !8801

3363:                                             ; preds = %3358
; BB406 :
  %3364 = load i32, ptr addrspace(1) %3324, align 4		; visa id: 3288
  %3365 = icmp eq i32 %3364, 0		; visa id: 3289
  br i1 %3365, label %.._crit_edge47_crit_edge575, label %3366, !stats.blockFrequency.digits !8802, !stats.blockFrequency.scale !8803		; visa id: 3290

.._crit_edge47_crit_edge575:                      ; preds = %3363
; BB:
  br label %._crit_edge47, !stats.blockFrequency.digits !8804, !stats.blockFrequency.scale !8801

3366:                                             ; preds = %3363
; BB408 :
  %3367 = call i32 @llvm.genx.GenISA.icmpxchgatomicrawA64.i32.p1.p1(ptr addrspace(1) %3323, ptr addrspace(1) %3323, i32 0, i32 1)		; visa id: 3292
  br label %._crit_edge47, !stats.blockFrequency.digits !8805, !stats.blockFrequency.scale !8801		; visa id: 3297

._crit_edge47:                                    ; preds = %.._crit_edge47_crit_edge575, %.._crit_edge47_crit_edge574, %.._crit_edge47_crit_edge, %._crit_edge43.._crit_edge47_crit_edge, %3366
; BB409 :
  %simdShuffle.155 = call float @llvm.genx.GenISA.WaveShuffleIndex.f32(float %.sroa.7.0, i32 %3326, i32 0)		; visa id: 3298
  %3368 = select i1 %3328, float %simdShuffle.155, float -0.000000e+00		; visa id: 3305
  %3369 = fadd float %.sroa.7.0, %3368		; visa id: 3306
  %simdShuffle.1.1 = call float @llvm.genx.GenISA.WaveShuffleIndex.f32(float %3369, i32 %3332, i32 0)		; visa id: 3307
  br i1 %3317, label %._crit_edge47.._crit_edge48.1_crit_edge, label %3370, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8782		; visa id: 3314

._crit_edge47.._crit_edge48.1_crit_edge:          ; preds = %._crit_edge47
; BB:
  br label %._crit_edge48.1, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787

3370:                                             ; preds = %._crit_edge47
; BB411 :
  %3371 = select i1 %3333, float %simdShuffle.1.1, float -0.000000e+00		; visa id: 3316
  %3372 = fadd float %3369, %3371		; visa id: 3317
  %3373 = bitcast float %3372 to i32
  %3374 = select i1 %3315, i32 %3373, i32 2143289344		; visa id: 3318
  %3375 = and i32 %3374, 2147483647		; visa id: 3319
  %3376 = icmp ugt i32 %3375, 2139095040		; visa id: 3320
  br i1 %3376, label %3384, label %3377, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 3321

3377:                                             ; preds = %3370
; BB412 :
  %3378 = lshr i32 %3374, 16		; visa id: 3323
  %3379 = and i32 %3378, 1		; visa id: 3324
  %3380 = add i32 %3374, %3379
  %3381 = add i32 %3380, 32767		; visa id: 3325
  %3382 = lshr i32 %3381, 16		; visa id: 3326
  %3383 = trunc i32 %3382 to i16		; visa id: 3327
  br label %3388, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 3328

3384:                                             ; preds = %3370
; BB413 :
  %3385 = lshr i32 %3374, 16		; visa id: 3330
  %3386 = trunc i32 %3385 to i16		; visa id: 3331
  %3387 = or i16 %3386, 64		; visa id: 3332
  br label %3388, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 3333

3388:                                             ; preds = %3384, %3377
; BB414 :
  %3389 = phi i16 [ %3387, %3384 ], [ %3383, %3377 ]
  %3390 = shl nuw nsw i64 %3318, 1		; visa id: 3334
  %3391 = add i64 %3390, %const_reg_qword13		; visa id: 3335
  %3392 = inttoptr i64 %3391 to ptr addrspace(4)		; visa id: 3336
  %3393 = addrspacecast ptr addrspace(4) %3392 to ptr addrspace(1)		; visa id: 3336
  store i16 %3389, ptr addrspace(1) %3393, align 2		; visa id: 3337
  br i1 %3319, label %3394, label %.._crit_edge48.1_crit_edge, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 3339

.._crit_edge48.1_crit_edge:                       ; preds = %3388
; BB:
  br label %._crit_edge48.1, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784

3394:                                             ; preds = %3388
; BB416 :
  %3395 = shl nuw nsw i64 %.pre-phi, 2		; visa id: 3341
  %3396 = add i64 %3395, %const_reg_qword18		; visa id: 3342
  %3397 = inttoptr i64 %3396 to ptr addrspace(4)		; visa id: 3343
  %3398 = addrspacecast ptr addrspace(4) %3397 to ptr addrspace(1)		; visa id: 3343
  store i32 %3322, ptr addrspace(1) %3398, align 4		; visa id: 3344
  br i1 %3320, label %3399, label %.._crit_edge48.1_crit_edge576, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 3345

.._crit_edge48.1_crit_edge576:                    ; preds = %3394
; BB:
  br label %._crit_edge48.1, !stats.blockFrequency.digits !8800, !stats.blockFrequency.scale !8801

3399:                                             ; preds = %3394
; BB418 :
  %3400 = load i32, ptr addrspace(1) %3324, align 4		; visa id: 3347
  %3401 = icmp eq i32 %3400, 0		; visa id: 3348
  br i1 %3401, label %.._crit_edge48.1_crit_edge577, label %3402, !stats.blockFrequency.digits !8802, !stats.blockFrequency.scale !8803		; visa id: 3349

.._crit_edge48.1_crit_edge577:                    ; preds = %3399
; BB:
  br label %._crit_edge48.1, !stats.blockFrequency.digits !8804, !stats.blockFrequency.scale !8801

3402:                                             ; preds = %3399
; BB420 :
  %3403 = call i32 @llvm.genx.GenISA.icmpxchgatomicrawA64.i32.p1.p1(ptr addrspace(1) %3323, ptr addrspace(1) %3323, i32 0, i32 1)		; visa id: 3351
  br label %._crit_edge48.1, !stats.blockFrequency.digits !8805, !stats.blockFrequency.scale !8801		; visa id: 3356

._crit_edge48.1:                                  ; preds = %.._crit_edge48.1_crit_edge577, %.._crit_edge48.1_crit_edge576, %.._crit_edge48.1_crit_edge, %._crit_edge47.._crit_edge48.1_crit_edge, %3402
; BB421 :
  ret void, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8782		; visa id: 3357
}
