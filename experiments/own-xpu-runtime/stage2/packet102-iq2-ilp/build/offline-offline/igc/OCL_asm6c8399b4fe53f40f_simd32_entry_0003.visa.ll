; ------------------------------------------------
; OCL_asm6c8399b4fe53f40f_simd32_entry_0003.visa.ll
; ------------------------------------------------
; Function Attrs: convergent nounwind
define spir_kernel void @_ZTSZZNK4p1026KernelILj2ELb0EE6submitERN4sycl3_V15queueESt4spanIKPvLm18446744073709551615EERKSt6vectorINS3_5eventESaISB_EEENKUlRNS3_7handlerEE_clESH_EUlNS3_7nd_itemILi1EEEE_(ptr byval(%"struct.p39::__generated_Bound") align 8 %0, i32 %1, <8 x i32> %r0, <3 x i32> %globalOffset, i16 %localIdX, i16 %localIdY, i16 %localIdZ, ptr addrspace(2) %constBase, ptr addrspace(1) %globalBase, ptr %privateBase, i64 %const_reg_qword, i64 %const_reg_qword1, i64 %const_reg_qword2, i64 %const_reg_qword3, i64 %const_reg_qword4, i64 %const_reg_qword5, i64 %const_reg_qword6, i64 %const_reg_qword7, i64 %const_reg_qword8, i64 %const_reg_qword9, i64 %const_reg_qword10, i64 %const_reg_qword11, i64 %const_reg_qword12, i64 %const_reg_qword13, i64 %const_reg_qword14, i64 %const_reg_qword15, i64 %const_reg_qword16, i64 %const_reg_qword17, i64 %const_reg_qword18, i64 %const_reg_qword19, i64 %const_reg_qword20, i32 %const_reg_dword, i32 %const_reg_dword21, i32 %const_reg_dword22, i32 %const_reg_dword23, i32 %const_reg_dword24, i32 %bindlessOffset, i32 %bindlessOffset25) #0 {
; BB0 :
  %3 = extractelement <8 x i32> %r0, i32 1		; visa id: 2
  %simdLaneId16 = call i16 @llvm.genx.GenISA.simdLaneId()		; visa id: 2
  %simdLaneId = zext i16 %simdLaneId16 to i32		; visa id: 5
  %4 = and i32 %simdLaneId, 3		; visa id: 6
  %5 = shl i32 %3, 3		; visa id: 7
  %6 = lshr i32 %simdLaneId, 2		; visa id: 8
  %7 = or i32 %5, %6		; visa id: 9
  %tobool.i = icmp eq i32 %const_reg_dword21, 0		; visa id: 10
  br i1 %tobool.i, label %.precompiled_u32divrem_sp.exit_crit_edge, label %if.end.i, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8782		; visa id: 11

.precompiled_u32divrem_sp.exit_crit_edge:         ; preds = %2
; BB1 :
  br label %precompiled_u32divrem_sp.exit, !stats.blockFrequency.digits !8783, !stats.blockFrequency.scale !8784		; visa id: 14

if.end.i:                                         ; preds = %2
; BB2 :
  %8 = call float @llvm.genx.GenISA.uitof.rtz.f32.i32(i32 %const_reg_dword21)		; visa id: 16
  %conv.i = fptoui float %8 to i32		; visa id: 18
  %sub.i = sub i32 %const_reg_dword21, %conv.i		; visa id: 19
  %9 = call float @llvm.genx.GenISA.uitof.rtz.f32.i32(i32 %7)		; visa id: 20
  %div.i = fdiv float 1.000000e+00, %8, !fpmath !8785		; visa id: 21
  %10 = call float @llvm.genx.GenISA.fma.rtz.f32.f32.f32.f32(float %div.i, float 0xBE98000000000000, float %div.i)		; visa id: 22
  %11 = call float @llvm.genx.GenISA.mul.rtz.f32.f32.f32(float %9, float %10)		; visa id: 23
  %conv3.i = fptoui float %9 to i32		; visa id: 24
  %sub4.i = sub i32 %7, %conv3.i		; visa id: 25
  %conv8.i = fptoui float %11 to i32		; visa id: 26
  %12 = call float @llvm.genx.GenISA.uitof.rtz.f32.i32(i32 %sub.i)		; visa id: 27
  %13 = call float @llvm.genx.GenISA.uitof.rtz.f32.i32(i32 %sub4.i)		; visa id: 28
  %14 = call float @llvm.genx.GenISA.uitof.rtz.f32.i32(i32 %conv8.i)		; visa id: 29
  %15 = fsub float 0.000000e+00, %8		; visa id: 30
  %16 = call float @llvm.genx.GenISA.fma.rtz.f32.f32.f32.f32(float %15, float %14, float %9)		; visa id: 31
  %17 = fsub float 0.000000e+00, %12		; visa id: 32
  %18 = call float @llvm.genx.GenISA.fma.rtz.f32.f32.f32.f32(float %17, float %14, float %13)		; visa id: 33
  %19 = call float @llvm.genx.GenISA.add.rtz.f32.f32.f32(float %16, float %18)		; visa id: 34
  %20 = call float @llvm.genx.GenISA.mul.rtz.f32.f32.f32(float %10, float %19)		; visa id: 35
  %conv16.i = fptoui float %20 to i32		; visa id: 37
  %add.i = add i32 %conv16.i, %conv8.i		; visa id: 38
  %mul.i = mul i32 %add.i, %const_reg_dword21		; visa id: 39
  %sub17.i = sub i32 %7, %mul.i		; visa id: 40
  %cmp.i = icmp uge i32 %sub17.i, %const_reg_dword21
  %21 = sext i1 %cmp.i to i32		; visa id: 41
  %22 = sub i32 0, %21
  %add19.i = add i32 %add.i, %22		; visa id: 42
  br label %precompiled_u32divrem_sp.exit, !stats.blockFrequency.digits !8786, !stats.blockFrequency.scale !8787		; visa id: 43

precompiled_u32divrem_sp.exit:                    ; preds = %.precompiled_u32divrem_sp.exit_crit_edge, %if.end.i
; BB3 :
  %retval.0.i = phi i32 [ %add19.i, %if.end.i ], [ -1, %.precompiled_u32divrem_sp.exit_crit_edge ]
  %23 = mul i32 %retval.0.i, %const_reg_dword21		; visa id: 44
  %24 = icmp uge i32 %7, %1
  %25 = icmp uge i32 %7, %1		; visa id: 45
  br i1 %25, label %precompiled_u32divrem_sp.exit.._crit_edge_crit_edge, label %26, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8782		; visa id: 46

precompiled_u32divrem_sp.exit.._crit_edge_crit_edge: ; preds = %precompiled_u32divrem_sp.exit
; BB4 :
  br label %._crit_edge, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 51

26:                                               ; preds = %precompiled_u32divrem_sp.exit
; BB5 :
  %27 = call { i32, i32 } @llvm.genx.GenISA.mul.pair(i32 %retval.0.i, i32 0, i32 12, i32 0)
  %28 = extractvalue { i32, i32 } %27, 0
  %29 = extractvalue { i32, i32 } %27, 1
  %30 = insertelement <2 x i32> undef, i32 %28, i32 0
  %31 = insertelement <2 x i32> %30, i32 %29, i32 1
  %32 = bitcast <2 x i32> %31 to i64		; visa id: 53
  %33 = add i64 %32, %const_reg_qword16		; visa id: 61
  %34 = inttoptr i64 %33 to ptr addrspace(4)		; visa id: 62
  %35 = addrspacecast ptr addrspace(4) %34 to ptr addrspace(1)		; visa id: 62
  %36 = load <2 x i32>, ptr addrspace(1) %35, align 4		; visa id: 63
  %37 = extractelement <2 x i32> %36, i32 0		; visa id: 64
  %38 = extractelement <2 x i32> %36, i32 1		; visa id: 64
  %39 = icmp uge i32 %37, %const_reg_dword23
  %40 = icmp ugt i32 %38, %const_reg_dword21		; visa id: 64
  %41 = or i1 %39, %40		; visa id: 65
  br i1 %41, label %.._crit_edge_crit_edge, label %42, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 67

.._crit_edge_crit_edge:                           ; preds = %26
; BB6 :
  br label %._crit_edge, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 72

42:                                               ; preds = %26
; BB7 :
  %43 = sub i32 %7, %23		; visa id: 74
  %44 = add i64 %33, 8		; visa id: 75
  %45 = inttoptr i64 %44 to ptr addrspace(4)		; visa id: 76
  %46 = addrspacecast ptr addrspace(4) %45 to ptr addrspace(1)		; visa id: 76
  %47 = load i32, ptr addrspace(1) %46, align 4		; visa id: 77
  %48 = sub nuw i32 %const_reg_dword21, %38, !spirv.Decorations !8788		; visa id: 78
  %49 = icmp ule i32 %47, %48
  %50 = icmp ule i32 %47, %const_reg_dword21		; visa id: 79
  %51 = and i1 %49, %50		; visa id: 80
  %52 = icmp ult i32 %43, %47		; visa id: 82
  %53 = and i1 %51, %52		; visa id: 83
  br i1 %53, label %56, label %._crit_edge43, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 84

._crit_edge43:                                    ; preds = %42
; BB8 :
  %54 = xor i1 %51, true		; visa id: 86
  %55 = sext i1 %54 to i32		; visa id: 87
  br label %._crit_edge, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8790		; visa id: 90

56:                                               ; preds = %42
; BB9 :
  %57 = bitcast i64 %const_reg_qword to <2 x i32>		; visa id: 92
  %58 = extractelement <2 x i32> %57, i32 0		; visa id: 93
  %59 = extractelement <2 x i32> %57, i32 1		; visa id: 93
  %60 = bitcast i64 %const_reg_qword1 to <2 x i32>		; visa id: 93
  %61 = extractelement <2 x i32> %60, i32 0		; visa id: 94
  %62 = extractelement <2 x i32> %60, i32 1		; visa id: 94
  %63 = ptrtoint ptr addrspace(2) %constBase to i64		; visa id: 94
  %64 = add i64 %63, 64
  %65 = call { i32, i32 } @llvm.genx.GenISA.mul.pair(i32 %37, i32 0, i32 %const_reg_dword21, i32 0)
  %66 = extractvalue { i32, i32 } %65, 0
  %67 = extractvalue { i32, i32 } %65, 1
  %68 = insertelement <2 x i32> undef, i32 %66, i32 0
  %69 = insertelement <2 x i32> %68, i32 %67, i32 1
  %70 = bitcast <2 x i32> %69 to i64		; visa id: 94
  %71 = zext i32 %38 to i64		; visa id: 102
  %72 = add nuw i64 %70, %71, !spirv.Decorations !8788		; visa id: 103
  %73 = zext i32 %43 to i64		; visa id: 104
  %74 = add nuw i64 %72, %73, !spirv.Decorations !8788		; visa id: 105
  %75 = bitcast i64 %74 to <2 x i32>		; visa id: 106
  %76 = extractelement <2 x i32> %75, i32 0		; visa id: 110
  %77 = extractelement <2 x i32> %75, i32 1		; visa id: 110
  %78 = icmp ult i16 %localIdX, 32		; visa id: 110
  %79 = select i1 %78, i32 %58, i32 %61		; visa id: 111
  %80 = select i1 %78, i32 %59, i32 %62		; visa id: 112
  %81 = insertelement <2 x i32> undef, i32 %79, i32 0		; visa id: 113
  %82 = insertelement <2 x i32> %81, i32 %80, i32 1		; visa id: 114
  %83 = bitcast <2 x i32> %82 to i64		; visa id: 115
  %84 = call { i32, i32 } @llvm.genx.GenISA.mul.pair(i32 %76, i32 %77, i32 %const_reg_dword, i32 0)
  %85 = extractvalue { i32, i32 } %84, 0
  %86 = extractvalue { i32, i32 } %84, 1
  %87 = insertelement <2 x i32> undef, i32 %85, i32 0
  %88 = insertelement <2 x i32> %87, i32 %86, i32 1
  %89 = bitcast <2 x i32> %88 to i64		; visa id: 119
  %90 = add i64 %83, %89		; visa id: 127
  %chunkPtr = inttoptr i64 %64 to ptr addrspace(2)
  %91 = load <8 x float>, ptr addrspace(2) %chunkPtr, align 8		; visa id: 128
  %92 = extractelement <8 x float> %91, i32 0		; visa id: 130
  %93 = extractelement <8 x float> %91, i32 1		; visa id: 130
  %94 = extractelement <8 x float> %91, i32 2		; visa id: 130
  %95 = extractelement <8 x float> %91, i32 3		; visa id: 130
  %96 = extractelement <8 x float> %91, i32 4		; visa id: 130
  %97 = extractelement <8 x float> %91, i32 5		; visa id: 130
  %98 = extractelement <8 x float> %91, i32 6		; visa id: 130
  %99 = extractelement <8 x float> %91, i32 7		; visa id: 130
  %100 = shl nuw nsw i32 %4, 4, !spirv.Decorations !8791		; visa id: 130
  %101 = zext i32 %100 to i64		; visa id: 131
  %102 = add i64 %90, %101		; visa id: 132
  %103 = add i64 %90, 640		; visa id: 133
  %104 = shl nuw nsw i32 %4, 1, !spirv.Decorations !8791		; visa id: 134
  %105 = zext i32 %104 to i64		; visa id: 135
  %106 = add i64 %103, %105		; visa id: 136
  %107 = add i64 %90, 720		; visa id: 137
  %108 = add i64 %107, %105		; visa id: 138
  %109 = add i64 %90, 800		; visa id: 139
  %110 = shl nuw nsw i32 %4, 6, !spirv.Decorations !8791		; visa id: 140
  %111 = ptrtoint ptr addrspace(1) %globalBase to i64		; visa id: 141
  br label %.preheader1.preheader, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8790		; visa id: 152

.preheader1.preheader:                            ; preds = %..preheader1.preheader_crit_edge, %56
; BB10 :
  %.sroa.36.0 = phi float [ %99, %56 ], [ %1879, %..preheader1.preheader_crit_edge ]
  %.sroa.31.0 = phi float [ %98, %56 ], [ %1681, %..preheader1.preheader_crit_edge ]
  %.sroa.28.0 = phi float [ %97, %56 ], [ %1445, %..preheader1.preheader_crit_edge ]
  %.sroa.21.0 = phi float [ %96, %56 ], [ %1248, %..preheader1.preheader_crit_edge ]
  %.sroa.18.0 = phi float [ %95, %56 ], [ %1011, %..preheader1.preheader_crit_edge ]
  %.sroa.13.0 = phi float [ %94, %56 ], [ %814, %..preheader1.preheader_crit_edge ]
  %.sroa.10.0 = phi float [ %93, %56 ], [ %578, %..preheader1.preheader_crit_edge ]
  %.sroa.0.0 = phi float [ %92, %56 ], [ %381, %..preheader1.preheader_crit_edge ]
  %112 = phi i32 [ 0, %56 ], [ %1881, %..preheader1.preheader_crit_edge ]
  %113 = shl nuw nsw i32 %112, 6, !spirv.Decorations !8791		; visa id: 153
  %114 = zext i32 %113 to i64		; visa id: 154
  %115 = add i64 %102, %114		; visa id: 155
  %116 = inttoptr i64 %115 to ptr addrspace(4)		; visa id: 156
  %generic_cast_to_ptr = addrspacecast ptr addrspace(4) %116 to ptr addrspace(1)		; visa id: 156
  %117 = load <4 x i32>, ptr addrspace(1) %generic_cast_to_ptr, align 4		; visa id: 157
  %118 = extractelement <4 x i32> %117, i32 0		; visa id: 158
  %119 = extractelement <4 x i32> %117, i32 1		; visa id: 158
  %120 = extractelement <4 x i32> %117, i32 2		; visa id: 158
  %121 = extractelement <4 x i32> %117, i32 3		; visa id: 158
  %122 = shl nuw nsw i32 %112, 3, !spirv.Decorations !8791		; visa id: 158
  %123 = zext i32 %122 to i64		; visa id: 159
  %124 = add i64 %106, %123		; visa id: 160
  %125 = inttoptr i64 %124 to ptr addrspace(4)		; visa id: 161
  %126 = addrspacecast ptr addrspace(4) %125 to ptr addrspace(1)		; visa id: 161
  %127 = load i16, ptr addrspace(1) %126, align 2, !noalias !8793		; visa id: 162
  %128 = add i64 %108, %123		; visa id: 164
  %129 = inttoptr i64 %128 to ptr addrspace(4)		; visa id: 165
  %130 = addrspacecast ptr addrspace(4) %129 to ptr addrspace(1)		; visa id: 165
  %131 = load i16, ptr addrspace(1) %130, align 2, !noalias !8793		; visa id: 166
  %132 = shl nuw nsw i32 %112, 2, !spirv.Decorations !8791		; visa id: 168
  %133 = zext i32 %132 to i64		; visa id: 169
  %134 = add i64 %109, %133		; visa id: 170
  %135 = inttoptr i64 %134 to ptr addrspace(4)		; visa id: 171
  %136 = addrspacecast ptr addrspace(4) %135 to ptr addrspace(1)		; visa id: 171
  %137 = load float, ptr addrspace(1) %136, align 4, !noalias !8793		; visa id: 172
  %138 = and i32 %118, 255
  %139 = zext i16 %127 to i32		; visa id: 173
  %140 = shl nuw nsw i32 %139, 8, !spirv.Decorations !8791		; visa id: 174
  %141 = and i32 %140, 768		; visa id: 175
  %142 = or i32 %138, %141		; visa id: 176
  %143 = shl nuw nsw i32 %142, 3, !spirv.Decorations !8791		; visa id: 177
  %144 = zext i32 %143 to i64		; visa id: 178
  %145 = add i64 %111, %144		; visa id: 179
  %146 = inttoptr i64 %145 to ptr addrspace(1)		; visa id: 180
  %147 = load <2 x i32>, ptr addrspace(1) %146, align 4		; visa id: 180
  %148 = shl nuw nsw i32 %112, 8, !spirv.Decorations !8791		; visa id: 181
  %149 = or i32 %148, %110		; visa id: 182
  %150 = bitcast float %137 to i32
  %151 = and i32 %150, 2147483647		; visa id: 183
  %152 = bitcast i32 %151 to float
  %153 = fcmp une float %152, %152
  %154 = fcmp oeq float %152, 0x7FF0000000000000		; visa id: 184
  %155 = or i1 %153, %154		; visa id: 185
  %156 = extractelement <2 x i32> %147, i32 0		; visa id: 187
  %157 = extractelement <2 x i32> %147, i32 1		; visa id: 187
  %158 = bitcast i32 %118 to <4 x i8>
  %159 = extractelement <4 x i8> %158, i32 2
  %160 = shl nuw nsw i32 %139, 6		; visa id: 187
  %161 = and i32 %160, 768
  %162 = zext i8 %159 to i32		; visa id: 188
  %163 = or i32 %162, %161		; visa id: 189
  %164 = shl nuw nsw i32 %163, 3, !spirv.Decorations !8791		; visa id: 190
  %165 = zext i32 %164 to i64		; visa id: 191
  %166 = add i64 %111, %165		; visa id: 192
  %167 = inttoptr i64 %166 to ptr addrspace(1)		; visa id: 193
  %168 = load <2 x i32>, ptr addrspace(1) %167, align 4		; visa id: 193
  %169 = shl nuw i32 %149, 1		; visa id: 194
  %170 = zext i32 %169 to i64		; visa id: 195
  %171 = add i64 %170, %const_reg_qword2		; visa id: 196
  %IntToPtr2 = inttoptr i64 %171 to ptr addrspace(1)		; visa id: 197
  %vCastload = load i32, ptr addrspace(1) %IntToPtr2, align 2		; visa id: 197
  %172 = add i64 %171, 4
  %IntToPtr2322 = inttoptr i64 %172 to ptr addrspace(1)
  %vCastload323 = load i32, ptr addrspace(1) %IntToPtr2322, align 2		; visa id: 198
  %173 = extractelement <2 x i32> %168, i32 0		; visa id: 199
  %174 = extractelement <2 x i32> %168, i32 1		; visa id: 199
  %175 = bitcast i32 %vCastload to <2 x i16>		; visa id: 199
  %176 = bitcast i32 %vCastload323 to <2 x i16>		; visa id: 201
  %177 = extractelement <2 x i16> %175, i32 0		; visa id: 203
  %178 = extractelement <2 x i16> %175, i32 1		; visa id: 203
  %179 = extractelement <2 x i16> %176, i32 0		; visa id: 203
  %180 = extractelement <2 x i16> %176, i32 1		; visa id: 203
  %181 = add i64 %171, 8
  %IntToPtr2324 = inttoptr i64 %181 to ptr addrspace(1)
  %vCastload325 = load i32, ptr addrspace(1) %IntToPtr2324, align 2		; visa id: 203
  %182 = add i64 %171, 12
  %IntToPtr2326 = inttoptr i64 %182 to ptr addrspace(1)
  %vCastload327 = load i32, ptr addrspace(1) %IntToPtr2326, align 2		; visa id: 204
  %183 = bitcast i32 %vCastload325 to <2 x i16>		; visa id: 205
  %184 = bitcast i32 %vCastload327 to <2 x i16>		; visa id: 207
  %185 = extractelement <2 x i16> %183, i32 0		; visa id: 209
  %186 = extractelement <2 x i16> %183, i32 1		; visa id: 209
  %187 = extractelement <2 x i16> %184, i32 0		; visa id: 209
  %188 = extractelement <2 x i16> %184, i32 1		; visa id: 209
  %189 = and i16 %131, 255		; visa id: 209
  %190 = zext i16 %189 to i32		; visa id: 210
  %191 = and i32 %190, 15		; visa id: 211
  %192 = uitofp i32 %191 to float		; visa id: 212
  %193 = fadd float %192, 5.000000e-01		; visa id: 213
  %194 = fmul float %137, %193		; visa id: 214
  %195 = fmul float %194, 2.500000e-01		; visa id: 215
  %196 = bitcast float %195 to i32
  %197 = and i32 %196, 2147483647		; visa id: 216
  %198 = icmp ugt i32 %197, 2139095040
  %199 = or i1 %155, %198		; visa id: 217
  %200 = and i32 %156, 255		; visa id: 219
  br i1 %199, label %208, label %201, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 220

201:                                              ; preds = %.preheader1.preheader
; BB11 :
  %202 = and i32 %118, 256
  %203 = sub nsw i32 0, %200, !spirv.Decorations !8798
  %204 = icmp eq i32 %202, 0		; visa id: 222
  %205 = select i1 %204, i32 %200, i32 %203		; visa id: 224
  %206 = sitofp i32 %205 to float		; visa id: 225
  %207 = fmul float %195, %206		; visa id: 226
  br label %216, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 227

208:                                              ; preds = %.preheader1.preheader
; BB12 :
  %209 = uitofp i32 %200 to float		; visa id: 229
  %210 = fmul float %195, %209		; visa id: 230
  %211 = and i32 %118, 256
  %212 = icmp eq i32 %211, 0		; visa id: 231
  %213 = select i1 %212, i32 1, i32 -1		; visa id: 233
  %214 = sitofp i32 %213 to float		; visa id: 234
  %215 = fmul float %210, %214		; visa id: 235
  br label %216, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 236

216:                                              ; preds = %201, %208
; BB13 :
  %.sroa.067.0 = phi float [ %215, %208 ], [ %207, %201 ]
  %217 = bitcast i32 %156 to <4 x i8>
  %218 = extractelement <4 x i8> %217, i32 1
  %219 = zext i8 %218 to i32		; visa id: 237
  br i1 %199, label %227, label %220, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 238

220:                                              ; preds = %216
; BB14 :
  %221 = and i32 %118, 512
  %222 = sub nsw i32 0, %219, !spirv.Decorations !8798
  %223 = icmp eq i32 %221, 0		; visa id: 240
  %224 = select i1 %223, i32 %219, i32 %222		; visa id: 242
  %225 = sitofp i32 %224 to float		; visa id: 243
  %226 = fmul float %195, %225		; visa id: 244
  br label %235, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 245

227:                                              ; preds = %216
; BB15 :
  %228 = uitofp i32 %219 to float		; visa id: 247
  %229 = fmul float %195, %228		; visa id: 248
  %230 = and i32 %118, 512
  %231 = icmp eq i32 %230, 0		; visa id: 249
  %232 = select i1 %231, i32 1, i32 -1		; visa id: 251
  %233 = sitofp i32 %232 to float		; visa id: 252
  %234 = fmul float %229, %233		; visa id: 253
  br label %235, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 254

235:                                              ; preds = %227, %220
; BB16 :
  %.sroa.40.0 = phi float [ %234, %227 ], [ %226, %220 ]
  %236 = extractelement <4 x i8> %217, i32 2
  %237 = zext i8 %236 to i32		; visa id: 255
  br i1 %199, label %245, label %238, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 256

238:                                              ; preds = %235
; BB17 :
  %239 = and i32 %118, 1024
  %240 = sub nsw i32 0, %237, !spirv.Decorations !8798
  %241 = icmp eq i32 %239, 0		; visa id: 258
  %242 = select i1 %241, i32 %237, i32 %240		; visa id: 260
  %243 = sitofp i32 %242 to float		; visa id: 261
  %244 = fmul float %195, %243		; visa id: 262
  br label %253, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 263

245:                                              ; preds = %235
; BB18 :
  %246 = uitofp i32 %237 to float		; visa id: 265
  %247 = fmul float %195, %246		; visa id: 266
  %248 = and i32 %118, 1024
  %249 = icmp eq i32 %248, 0		; visa id: 267
  %250 = select i1 %249, i32 1, i32 -1		; visa id: 269
  %251 = sitofp i32 %250 to float		; visa id: 270
  %252 = fmul float %247, %251		; visa id: 271
  br label %253, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 272

253:                                              ; preds = %245, %238
; BB19 :
  %.sroa.64.0 = phi float [ %252, %245 ], [ %244, %238 ]
  %254 = lshr i32 %156, 24		; visa id: 273
  br i1 %199, label %262, label %255, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 274

255:                                              ; preds = %253
; BB20 :
  %256 = and i32 %118, 2048
  %257 = sub nsw i32 0, %254, !spirv.Decorations !8798
  %258 = icmp eq i32 %256, 0		; visa id: 276
  %259 = select i1 %258, i32 %254, i32 %257		; visa id: 278
  %260 = sitofp i32 %259 to float		; visa id: 279
  %261 = fmul float %195, %260		; visa id: 280
  br label %270, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 281

262:                                              ; preds = %253
; BB21 :
  %263 = uitofp i32 %254 to float		; visa id: 283
  %264 = fmul float %195, %263		; visa id: 284
  %265 = and i32 %118, 2048
  %266 = icmp eq i32 %265, 0		; visa id: 285
  %267 = select i1 %266, i32 1, i32 -1		; visa id: 287
  %268 = sitofp i32 %267 to float		; visa id: 288
  %269 = fmul float %264, %268		; visa id: 289
  br label %270, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 290

270:                                              ; preds = %262, %255
; BB22 :
  %.sroa.88.0 = phi float [ %269, %262 ], [ %261, %255 ]
  %271 = and i32 %157, 255		; visa id: 291
  br i1 %199, label %279, label %272, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 292

272:                                              ; preds = %270
; BB23 :
  %273 = and i32 %118, 4096
  %274 = sub nsw i32 0, %271, !spirv.Decorations !8798
  %275 = icmp eq i32 %273, 0		; visa id: 294
  %276 = select i1 %275, i32 %271, i32 %274		; visa id: 296
  %277 = sitofp i32 %276 to float		; visa id: 297
  %278 = fmul float %195, %277		; visa id: 298
  br label %287, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 299

279:                                              ; preds = %270
; BB24 :
  %280 = uitofp i32 %271 to float		; visa id: 301
  %281 = fmul float %195, %280		; visa id: 302
  %282 = and i32 %118, 4096
  %283 = icmp eq i32 %282, 0		; visa id: 303
  %284 = select i1 %283, i32 1, i32 -1		; visa id: 305
  %285 = sitofp i32 %284 to float		; visa id: 306
  %286 = fmul float %281, %285		; visa id: 307
  br label %287, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 308

287:                                              ; preds = %279, %272
; BB25 :
  %.sroa.112.0 = phi float [ %286, %279 ], [ %278, %272 ]
  %288 = bitcast i32 %157 to <4 x i8>
  %289 = extractelement <4 x i8> %288, i32 1
  %290 = zext i8 %289 to i32		; visa id: 309
  br i1 %199, label %298, label %291, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 310

291:                                              ; preds = %287
; BB26 :
  %292 = and i32 %118, 8192
  %293 = sub nsw i32 0, %290, !spirv.Decorations !8798
  %294 = icmp eq i32 %292, 0		; visa id: 312
  %295 = select i1 %294, i32 %290, i32 %293		; visa id: 314
  %296 = sitofp i32 %295 to float		; visa id: 315
  %297 = fmul float %195, %296		; visa id: 316
  br label %306, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 317

298:                                              ; preds = %287
; BB27 :
  %299 = uitofp i32 %290 to float		; visa id: 319
  %300 = fmul float %195, %299		; visa id: 320
  %301 = and i32 %118, 8192
  %302 = icmp eq i32 %301, 0		; visa id: 321
  %303 = select i1 %302, i32 1, i32 -1		; visa id: 323
  %304 = sitofp i32 %303 to float		; visa id: 324
  %305 = fmul float %300, %304		; visa id: 325
  br label %306, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 326

306:                                              ; preds = %298, %291
; BB28 :
  %.sroa.136.0 = phi float [ %305, %298 ], [ %297, %291 ]
  %307 = extractelement <4 x i8> %288, i32 2
  %308 = zext i8 %307 to i32		; visa id: 327
  br i1 %199, label %316, label %309, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 328

309:                                              ; preds = %306
; BB29 :
  %310 = and i32 %118, 16384
  %311 = sub nsw i32 0, %308, !spirv.Decorations !8798
  %312 = icmp eq i32 %310, 0		; visa id: 330
  %313 = select i1 %312, i32 %308, i32 %311		; visa id: 332
  %314 = sitofp i32 %313 to float		; visa id: 333
  %315 = fmul float %195, %314		; visa id: 334
  br label %324, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 335

316:                                              ; preds = %306
; BB30 :
  %317 = uitofp i32 %308 to float		; visa id: 337
  %318 = fmul float %195, %317		; visa id: 338
  %319 = and i32 %118, 16384
  %320 = icmp eq i32 %319, 0		; visa id: 339
  %321 = select i1 %320, i32 1, i32 -1		; visa id: 341
  %322 = sitofp i32 %321 to float		; visa id: 342
  %323 = fmul float %318, %322		; visa id: 343
  br label %324, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 344

324:                                              ; preds = %316, %309
; BB31 :
  %.sroa.160.0 = phi float [ %323, %316 ], [ %315, %309 ]
  %325 = lshr i32 %157, 24		; visa id: 345
  br i1 %199, label %333, label %326, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 346

326:                                              ; preds = %324
; BB32 :
  %327 = and i32 %118, 32768
  %328 = sub nsw i32 0, %325, !spirv.Decorations !8798
  %329 = icmp eq i32 %327, 0		; visa id: 348
  %330 = select i1 %329, i32 %325, i32 %328		; visa id: 350
  %331 = sitofp i32 %330 to float		; visa id: 351
  %332 = fmul float %195, %331		; visa id: 352
  br label %341, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 353

333:                                              ; preds = %324
; BB33 :
  %334 = uitofp i32 %325 to float		; visa id: 355
  %335 = fmul float %195, %334		; visa id: 356
  %336 = and i32 %118, 32768
  %337 = icmp eq i32 %336, 0		; visa id: 357
  %338 = select i1 %337, i32 1, i32 -1		; visa id: 359
  %339 = sitofp i32 %338 to float		; visa id: 360
  %340 = fmul float %335, %339		; visa id: 361
  br label %341, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 362

341:                                              ; preds = %333, %326
; BB34 :
  %.sroa.184.0 = phi float [ %340, %333 ], [ %332, %326 ]
  %342 = zext i16 %177 to i32		; visa id: 363
  %343 = shl nuw i32 %342, 16, !spirv.Decorations !8788		; visa id: 364
  %344 = bitcast i32 %343 to float
  %345 = fmul float %.sroa.067.0, %344		; visa id: 365
  %346 = fadd float %.sroa.0.0, %345		; visa id: 366
  %347 = zext i16 %178 to i32		; visa id: 367
  %348 = shl nuw i32 %347, 16, !spirv.Decorations !8788		; visa id: 368
  %349 = bitcast i32 %348 to float
  %350 = fmul float %.sroa.40.0, %349		; visa id: 369
  %351 = fadd float %346, %350		; visa id: 370
  %352 = zext i16 %179 to i32		; visa id: 371
  %353 = shl nuw i32 %352, 16, !spirv.Decorations !8788		; visa id: 372
  %354 = bitcast i32 %353 to float
  %355 = fmul float %.sroa.64.0, %354		; visa id: 373
  %356 = fadd float %351, %355		; visa id: 374
  %357 = zext i16 %180 to i32		; visa id: 375
  %358 = shl nuw i32 %357, 16, !spirv.Decorations !8788		; visa id: 376
  %359 = bitcast i32 %358 to float
  %360 = fmul float %.sroa.88.0, %359		; visa id: 377
  %361 = fadd float %356, %360		; visa id: 378
  %362 = zext i16 %185 to i32		; visa id: 379
  %363 = shl nuw i32 %362, 16, !spirv.Decorations !8788		; visa id: 380
  %364 = bitcast i32 %363 to float
  %365 = fmul float %.sroa.112.0, %364		; visa id: 381
  %366 = fadd float %361, %365		; visa id: 382
  %367 = zext i16 %186 to i32		; visa id: 383
  %368 = shl nuw i32 %367, 16, !spirv.Decorations !8788		; visa id: 384
  %369 = bitcast i32 %368 to float
  %370 = fmul float %.sroa.136.0, %369		; visa id: 385
  %371 = fadd float %366, %370		; visa id: 386
  %372 = zext i16 %187 to i32		; visa id: 387
  %373 = shl nuw i32 %372, 16, !spirv.Decorations !8788		; visa id: 388
  %374 = bitcast i32 %373 to float
  %375 = fmul float %.sroa.160.0, %374		; visa id: 389
  %376 = fadd float %371, %375		; visa id: 390
  %377 = zext i16 %188 to i32		; visa id: 391
  %378 = shl nuw i32 %377, 16, !spirv.Decorations !8788		; visa id: 392
  %379 = bitcast i32 %378 to float
  %380 = fmul float %.sroa.184.0, %379		; visa id: 393
  %381 = fadd float %376, %380		; visa id: 394
  %382 = or i32 %169, 16		; visa id: 395
  %383 = zext i32 %382 to i64		; visa id: 396
  %384 = add i64 %383, %const_reg_qword2		; visa id: 397
  %IntToPtr2328 = inttoptr i64 %384 to ptr addrspace(1)		; visa id: 398
  %vCastload329 = load i32, ptr addrspace(1) %IntToPtr2328, align 2		; visa id: 398
  %385 = add i64 %384, 4
  %IntToPtr2330 = inttoptr i64 %385 to ptr addrspace(1)
  %vCastload331 = load i32, ptr addrspace(1) %IntToPtr2330, align 2		; visa id: 399
  %386 = add i64 %384, 8
  %IntToPtr2332 = inttoptr i64 %386 to ptr addrspace(1)
  %vCastload333 = load i32, ptr addrspace(1) %IntToPtr2332, align 2		; visa id: 400
  %387 = add i64 %384, 12
  %IntToPtr2334 = inttoptr i64 %387 to ptr addrspace(1)
  %vCastload335 = load i32, ptr addrspace(1) %IntToPtr2334, align 2		; visa id: 401
  %388 = bitcast i32 %vCastload329 to <2 x i16>		; visa id: 402
  %389 = bitcast i32 %vCastload331 to <2 x i16>		; visa id: 404
  %390 = extractelement <2 x i16> %388, i32 0		; visa id: 406
  %391 = extractelement <2 x i16> %388, i32 1		; visa id: 406
  %392 = extractelement <2 x i16> %389, i32 0		; visa id: 406
  %393 = extractelement <2 x i16> %389, i32 1		; visa id: 406
  %394 = bitcast i32 %vCastload333 to <2 x i16>		; visa id: 406
  %395 = bitcast i32 %vCastload335 to <2 x i16>		; visa id: 408
  %396 = extractelement <2 x i16> %394, i32 0		; visa id: 410
  %397 = extractelement <2 x i16> %394, i32 1		; visa id: 410
  %398 = extractelement <2 x i16> %395, i32 0		; visa id: 410
  %399 = extractelement <2 x i16> %395, i32 1		; visa id: 410
  %400 = and i32 %173, 255		; visa id: 410
  br i1 %199, label %408, label %401, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 411

401:                                              ; preds = %341
; BB35 :
  %402 = and i32 %118, 16777216
  %403 = sub nsw i32 0, %400, !spirv.Decorations !8798
  %404 = icmp eq i32 %402, 0		; visa id: 413
  %405 = select i1 %404, i32 %400, i32 %403		; visa id: 415
  %406 = sitofp i32 %405 to float		; visa id: 416
  %407 = fmul float %195, %406		; visa id: 417
  br label %416, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 418

408:                                              ; preds = %341
; BB36 :
  %409 = uitofp i32 %400 to float		; visa id: 420
  %410 = fmul float %195, %409		; visa id: 421
  %411 = and i32 %118, 16777216
  %412 = icmp eq i32 %411, 0		; visa id: 422
  %413 = select i1 %412, i32 1, i32 -1		; visa id: 424
  %414 = sitofp i32 %413 to float		; visa id: 425
  %415 = fmul float %410, %414		; visa id: 426
  br label %416, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 427

416:                                              ; preds = %408, %401
; BB37 :
  %.sroa.067.1 = phi float [ %415, %408 ], [ %407, %401 ]
  %417 = bitcast i32 %173 to <4 x i8>
  %418 = extractelement <4 x i8> %417, i32 1
  %419 = zext i8 %418 to i32		; visa id: 428
  br i1 %199, label %427, label %420, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 429

420:                                              ; preds = %416
; BB38 :
  %421 = and i32 %118, 33554432
  %422 = sub nsw i32 0, %419, !spirv.Decorations !8798
  %423 = icmp eq i32 %421, 0		; visa id: 431
  %424 = select i1 %423, i32 %419, i32 %422		; visa id: 433
  %425 = sitofp i32 %424 to float		; visa id: 434
  %426 = fmul float %195, %425		; visa id: 435
  br label %435, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 436

427:                                              ; preds = %416
; BB39 :
  %428 = uitofp i32 %419 to float		; visa id: 438
  %429 = fmul float %195, %428		; visa id: 439
  %430 = and i32 %118, 33554432
  %431 = icmp eq i32 %430, 0		; visa id: 440
  %432 = select i1 %431, i32 1, i32 -1		; visa id: 442
  %433 = sitofp i32 %432 to float		; visa id: 443
  %434 = fmul float %429, %433		; visa id: 444
  br label %435, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 445

435:                                              ; preds = %427, %420
; BB40 :
  %.sroa.40.1 = phi float [ %434, %427 ], [ %426, %420 ]
  %436 = extractelement <4 x i8> %417, i32 2
  %437 = zext i8 %436 to i32		; visa id: 446
  br i1 %199, label %445, label %438, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 447

438:                                              ; preds = %435
; BB41 :
  %439 = and i32 %118, 67108864
  %440 = sub nsw i32 0, %437, !spirv.Decorations !8798
  %441 = icmp eq i32 %439, 0		; visa id: 449
  %442 = select i1 %441, i32 %437, i32 %440		; visa id: 451
  %443 = sitofp i32 %442 to float		; visa id: 452
  %444 = fmul float %195, %443		; visa id: 453
  br label %453, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 454

445:                                              ; preds = %435
; BB42 :
  %446 = uitofp i32 %437 to float		; visa id: 456
  %447 = fmul float %195, %446		; visa id: 457
  %448 = and i32 %118, 67108864
  %449 = icmp eq i32 %448, 0		; visa id: 458
  %450 = select i1 %449, i32 1, i32 -1		; visa id: 460
  %451 = sitofp i32 %450 to float		; visa id: 461
  %452 = fmul float %447, %451		; visa id: 462
  br label %453, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 463

453:                                              ; preds = %445, %438
; BB43 :
  %.sroa.64.1 = phi float [ %452, %445 ], [ %444, %438 ]
  %454 = lshr i32 %173, 24		; visa id: 464
  br i1 %199, label %462, label %455, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 465

455:                                              ; preds = %453
; BB44 :
  %456 = and i32 %118, 134217728
  %457 = sub nsw i32 0, %454, !spirv.Decorations !8798
  %458 = icmp eq i32 %456, 0		; visa id: 467
  %459 = select i1 %458, i32 %454, i32 %457		; visa id: 469
  %460 = sitofp i32 %459 to float		; visa id: 470
  %461 = fmul float %195, %460		; visa id: 471
  br label %470, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 472

462:                                              ; preds = %453
; BB45 :
  %463 = uitofp i32 %454 to float		; visa id: 474
  %464 = fmul float %195, %463		; visa id: 475
  %465 = and i32 %118, 134217728
  %466 = icmp eq i32 %465, 0		; visa id: 476
  %467 = select i1 %466, i32 1, i32 -1		; visa id: 478
  %468 = sitofp i32 %467 to float		; visa id: 479
  %469 = fmul float %464, %468		; visa id: 480
  br label %470, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 481

470:                                              ; preds = %462, %455
; BB46 :
  %.sroa.88.1 = phi float [ %469, %462 ], [ %461, %455 ]
  %471 = and i32 %174, 255		; visa id: 482
  br i1 %199, label %479, label %472, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 483

472:                                              ; preds = %470
; BB47 :
  %473 = and i32 %118, 268435456
  %474 = sub nsw i32 0, %471, !spirv.Decorations !8798
  %475 = icmp eq i32 %473, 0		; visa id: 485
  %476 = select i1 %475, i32 %471, i32 %474		; visa id: 487
  %477 = sitofp i32 %476 to float		; visa id: 488
  %478 = fmul float %195, %477		; visa id: 489
  br label %487, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 490

479:                                              ; preds = %470
; BB48 :
  %480 = uitofp i32 %471 to float		; visa id: 492
  %481 = fmul float %195, %480		; visa id: 493
  %482 = and i32 %118, 268435456
  %483 = icmp eq i32 %482, 0		; visa id: 494
  %484 = select i1 %483, i32 1, i32 -1		; visa id: 496
  %485 = sitofp i32 %484 to float		; visa id: 497
  %486 = fmul float %481, %485		; visa id: 498
  br label %487, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 499

487:                                              ; preds = %479, %472
; BB49 :
  %.sroa.112.1 = phi float [ %486, %479 ], [ %478, %472 ]
  %488 = bitcast i32 %174 to <4 x i8>
  %489 = extractelement <4 x i8> %488, i32 1
  %490 = zext i8 %489 to i32		; visa id: 500
  br i1 %199, label %498, label %491, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 501

491:                                              ; preds = %487
; BB50 :
  %492 = and i32 %118, 536870912
  %493 = sub nsw i32 0, %490, !spirv.Decorations !8798
  %494 = icmp eq i32 %492, 0		; visa id: 503
  %495 = select i1 %494, i32 %490, i32 %493		; visa id: 505
  %496 = sitofp i32 %495 to float		; visa id: 506
  %497 = fmul float %195, %496		; visa id: 507
  br label %506, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 508

498:                                              ; preds = %487
; BB51 :
  %499 = uitofp i32 %490 to float		; visa id: 510
  %500 = fmul float %195, %499		; visa id: 511
  %501 = and i32 %118, 536870912
  %502 = icmp eq i32 %501, 0		; visa id: 512
  %503 = select i1 %502, i32 1, i32 -1		; visa id: 514
  %504 = sitofp i32 %503 to float		; visa id: 515
  %505 = fmul float %500, %504		; visa id: 516
  br label %506, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 517

506:                                              ; preds = %498, %491
; BB52 :
  %.sroa.136.1 = phi float [ %505, %498 ], [ %497, %491 ]
  %507 = extractelement <4 x i8> %488, i32 2
  %508 = zext i8 %507 to i32		; visa id: 518
  br i1 %199, label %516, label %509, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 519

509:                                              ; preds = %506
; BB53 :
  %510 = and i32 %118, 1073741824
  %511 = sub nsw i32 0, %508, !spirv.Decorations !8798
  %512 = icmp eq i32 %510, 0		; visa id: 521
  %513 = select i1 %512, i32 %508, i32 %511		; visa id: 523
  %514 = sitofp i32 %513 to float		; visa id: 524
  %515 = fmul float %195, %514		; visa id: 525
  br label %524, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 526

516:                                              ; preds = %506
; BB54 :
  %517 = uitofp i32 %508 to float		; visa id: 528
  %518 = fmul float %195, %517		; visa id: 529
  %519 = and i32 %118, 1073741824
  %520 = icmp eq i32 %519, 0		; visa id: 530
  %521 = select i1 %520, i32 1, i32 -1		; visa id: 532
  %522 = sitofp i32 %521 to float		; visa id: 533
  %523 = fmul float %518, %522		; visa id: 534
  br label %524, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 535

524:                                              ; preds = %516, %509
; BB55 :
  %.sroa.160.1 = phi float [ %523, %516 ], [ %515, %509 ]
  %525 = lshr i32 %174, 24		; visa id: 536
  br i1 %199, label %532, label %526, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 537

526:                                              ; preds = %524
; BB56 :
  %527 = sub nsw i32 0, %525, !spirv.Decorations !8798
  %528 = icmp slt i32 %118, 0		; visa id: 539
  %529 = select i1 %528, i32 %527, i32 %525		; visa id: 540
  %530 = sitofp i32 %529 to float		; visa id: 541
  %531 = fmul float %195, %530		; visa id: 542
  br label %._crit_edge44.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 543

532:                                              ; preds = %524
; BB57 :
  %533 = uitofp i32 %525 to float		; visa id: 545
  %534 = fmul float %195, %533		; visa id: 546
  %535 = icmp sgt i32 %118, -1		; visa id: 547
  %536 = select i1 %535, i32 1, i32 -1		; visa id: 548
  %537 = sitofp i32 %536 to float		; visa id: 549
  %538 = fmul float %534, %537		; visa id: 550
  br label %._crit_edge44.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 551

._crit_edge44.1:                                  ; preds = %532, %526
; BB58 :
  %.sroa.184.1 = phi float [ %538, %532 ], [ %531, %526 ]
  %539 = zext i16 %390 to i32		; visa id: 552
  %540 = shl nuw i32 %539, 16, !spirv.Decorations !8788		; visa id: 553
  %541 = bitcast i32 %540 to float
  %542 = fmul float %.sroa.067.1, %541		; visa id: 554
  %543 = fadd float %.sroa.10.0, %542		; visa id: 555
  %544 = zext i16 %391 to i32		; visa id: 556
  %545 = shl nuw i32 %544, 16, !spirv.Decorations !8788		; visa id: 557
  %546 = bitcast i32 %545 to float
  %547 = fmul float %.sroa.40.1, %546		; visa id: 558
  %548 = fadd float %543, %547		; visa id: 559
  %549 = zext i16 %392 to i32		; visa id: 560
  %550 = shl nuw i32 %549, 16, !spirv.Decorations !8788		; visa id: 561
  %551 = bitcast i32 %550 to float
  %552 = fmul float %.sroa.64.1, %551		; visa id: 562
  %553 = fadd float %548, %552		; visa id: 563
  %554 = zext i16 %393 to i32		; visa id: 564
  %555 = shl nuw i32 %554, 16, !spirv.Decorations !8788		; visa id: 565
  %556 = bitcast i32 %555 to float
  %557 = fmul float %.sroa.88.1, %556		; visa id: 566
  %558 = fadd float %553, %557		; visa id: 567
  %559 = zext i16 %396 to i32		; visa id: 568
  %560 = shl nuw i32 %559, 16, !spirv.Decorations !8788		; visa id: 569
  %561 = bitcast i32 %560 to float
  %562 = fmul float %.sroa.112.1, %561		; visa id: 570
  %563 = fadd float %558, %562		; visa id: 571
  %564 = zext i16 %397 to i32		; visa id: 572
  %565 = shl nuw i32 %564, 16, !spirv.Decorations !8788		; visa id: 573
  %566 = bitcast i32 %565 to float
  %567 = fmul float %.sroa.136.1, %566		; visa id: 574
  %568 = fadd float %563, %567		; visa id: 575
  %569 = zext i16 %398 to i32		; visa id: 576
  %570 = shl nuw i32 %569, 16, !spirv.Decorations !8788		; visa id: 577
  %571 = bitcast i32 %570 to float
  %572 = fmul float %.sroa.160.1, %571		; visa id: 578
  %573 = fadd float %568, %572		; visa id: 579
  %574 = zext i16 %399 to i32		; visa id: 580
  %575 = shl nuw i32 %574, 16, !spirv.Decorations !8788		; visa id: 581
  %576 = bitcast i32 %575 to float
  %577 = fmul float %.sroa.184.1, %576		; visa id: 582
  %578 = fadd float %573, %577		; visa id: 583
  %579 = and i32 %119, 255
  %580 = shl nuw nsw i32 %139, 4		; visa id: 584
  %581 = and i32 %580, 768		; visa id: 585
  %582 = or i32 %579, %581		; visa id: 586
  %583 = shl nuw nsw i32 %582, 3, !spirv.Decorations !8791		; visa id: 587
  %584 = zext i32 %583 to i64		; visa id: 588
  %585 = add i64 %111, %584		; visa id: 589
  %586 = inttoptr i64 %585 to ptr addrspace(1)		; visa id: 590
  %587 = load <2 x i32>, ptr addrspace(1) %586, align 4		; visa id: 590
  %588 = bitcast i32 %119 to <4 x i8>
  %589 = extractelement <4 x i8> %588, i32 2
  %590 = shl nuw nsw i32 %139, 2		; visa id: 591
  %591 = and i32 %590, 768
  %592 = zext i8 %589 to i32		; visa id: 592
  %593 = or i32 %592, %591		; visa id: 593
  %594 = shl nuw nsw i32 %593, 3, !spirv.Decorations !8791		; visa id: 594
  %595 = zext i32 %594 to i64		; visa id: 595
  %596 = add i64 %111, %595		; visa id: 596
  %597 = inttoptr i64 %596 to ptr addrspace(1)		; visa id: 597
  %598 = load <2 x i32>, ptr addrspace(1) %597, align 4		; visa id: 597
  %599 = extractelement <2 x i32> %587, i32 0		; visa id: 598
  %600 = extractelement <2 x i32> %587, i32 1		; visa id: 598
  %601 = extractelement <2 x i32> %598, i32 0		; visa id: 598
  %602 = extractelement <2 x i32> %598, i32 1		; visa id: 598
  %603 = or i32 %169, 32		; visa id: 598
  %604 = zext i32 %603 to i64		; visa id: 599
  %605 = add i64 %604, %const_reg_qword2		; visa id: 600
  %IntToPtr2336 = inttoptr i64 %605 to ptr addrspace(1)		; visa id: 601
  %vCastload337 = load i32, ptr addrspace(1) %IntToPtr2336, align 2		; visa id: 601
  %606 = add i64 %605, 4
  %IntToPtr2338 = inttoptr i64 %606 to ptr addrspace(1)
  %vCastload339 = load i32, ptr addrspace(1) %IntToPtr2338, align 2		; visa id: 602
  %607 = add i64 %605, 8
  %IntToPtr2340 = inttoptr i64 %607 to ptr addrspace(1)
  %vCastload341 = load i32, ptr addrspace(1) %IntToPtr2340, align 2		; visa id: 603
  %608 = add i64 %605, 12
  %IntToPtr2342 = inttoptr i64 %608 to ptr addrspace(1)
  %vCastload343 = load i32, ptr addrspace(1) %IntToPtr2342, align 2		; visa id: 604
  %609 = bitcast i32 %vCastload337 to <2 x i16>		; visa id: 605
  %610 = bitcast i32 %vCastload339 to <2 x i16>		; visa id: 607
  %611 = extractelement <2 x i16> %609, i32 0		; visa id: 609
  %612 = extractelement <2 x i16> %609, i32 1		; visa id: 609
  %613 = extractelement <2 x i16> %610, i32 0		; visa id: 609
  %614 = extractelement <2 x i16> %610, i32 1		; visa id: 609
  %615 = bitcast i32 %vCastload341 to <2 x i16>		; visa id: 609
  %616 = bitcast i32 %vCastload343 to <2 x i16>		; visa id: 611
  %617 = extractelement <2 x i16> %615, i32 0		; visa id: 613
  %618 = extractelement <2 x i16> %615, i32 1		; visa id: 613
  %619 = extractelement <2 x i16> %616, i32 0		; visa id: 613
  %620 = extractelement <2 x i16> %616, i32 1		; visa id: 613
  %621 = lshr i32 %190, 4		; visa id: 613
  %622 = uitofp i32 %621 to float		; visa id: 614
  %623 = fadd float %622, 5.000000e-01		; visa id: 615
  %624 = fmul float %137, %623		; visa id: 616
  %625 = fmul float %624, 2.500000e-01		; visa id: 617
  %626 = bitcast float %625 to i32
  %627 = and i32 %626, 2147483647		; visa id: 618
  %628 = icmp ugt i32 %627, 2139095040
  %629 = fcmp oeq float %152, 0x7FF0000000000000		; visa id: 619
  %630 = fcmp une float %152, %152
  %631 = or i1 %630, %629		; visa id: 620
  %632 = or i1 %631, %628		; visa id: 622
  %633 = and i32 %599, 255		; visa id: 624
  br i1 %632, label %641, label %634, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 625

634:                                              ; preds = %._crit_edge44.1
; BB59 :
  %635 = and i32 %119, 256
  %636 = sub nsw i32 0, %633, !spirv.Decorations !8798
  %637 = icmp eq i32 %635, 0		; visa id: 627
  %638 = select i1 %637, i32 %633, i32 %636		; visa id: 629
  %639 = sitofp i32 %638 to float		; visa id: 630
  %640 = fmul float %625, %639		; visa id: 631
  br label %649, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 632

641:                                              ; preds = %._crit_edge44.1
; BB60 :
  %642 = uitofp i32 %633 to float		; visa id: 634
  %643 = fmul float %625, %642		; visa id: 635
  %644 = and i32 %119, 256
  %645 = icmp eq i32 %644, 0		; visa id: 636
  %646 = select i1 %645, i32 1, i32 -1		; visa id: 638
  %647 = sitofp i32 %646 to float		; visa id: 639
  %648 = fmul float %643, %647		; visa id: 640
  br label %649, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 641

649:                                              ; preds = %641, %634
; BB61 :
  %.sroa.067.2 = phi float [ %648, %641 ], [ %640, %634 ]
  %650 = bitcast i32 %599 to <4 x i8>
  %651 = extractelement <4 x i8> %650, i32 1
  %652 = zext i8 %651 to i32		; visa id: 642
  br i1 %632, label %660, label %653, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 643

653:                                              ; preds = %649
; BB62 :
  %654 = and i32 %119, 512
  %655 = sub nsw i32 0, %652, !spirv.Decorations !8798
  %656 = icmp eq i32 %654, 0		; visa id: 645
  %657 = select i1 %656, i32 %652, i32 %655		; visa id: 647
  %658 = sitofp i32 %657 to float		; visa id: 648
  %659 = fmul float %625, %658		; visa id: 649
  br label %668, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 650

660:                                              ; preds = %649
; BB63 :
  %661 = uitofp i32 %652 to float		; visa id: 652
  %662 = fmul float %625, %661		; visa id: 653
  %663 = and i32 %119, 512
  %664 = icmp eq i32 %663, 0		; visa id: 654
  %665 = select i1 %664, i32 1, i32 -1		; visa id: 656
  %666 = sitofp i32 %665 to float		; visa id: 657
  %667 = fmul float %662, %666		; visa id: 658
  br label %668, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 659

668:                                              ; preds = %660, %653
; BB64 :
  %.sroa.40.2 = phi float [ %667, %660 ], [ %659, %653 ]
  %669 = extractelement <4 x i8> %650, i32 2
  %670 = zext i8 %669 to i32		; visa id: 660
  br i1 %632, label %678, label %671, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 661

671:                                              ; preds = %668
; BB65 :
  %672 = and i32 %119, 1024
  %673 = sub nsw i32 0, %670, !spirv.Decorations !8798
  %674 = icmp eq i32 %672, 0		; visa id: 663
  %675 = select i1 %674, i32 %670, i32 %673		; visa id: 665
  %676 = sitofp i32 %675 to float		; visa id: 666
  %677 = fmul float %625, %676		; visa id: 667
  br label %686, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 668

678:                                              ; preds = %668
; BB66 :
  %679 = uitofp i32 %670 to float		; visa id: 670
  %680 = fmul float %625, %679		; visa id: 671
  %681 = and i32 %119, 1024
  %682 = icmp eq i32 %681, 0		; visa id: 672
  %683 = select i1 %682, i32 1, i32 -1		; visa id: 674
  %684 = sitofp i32 %683 to float		; visa id: 675
  %685 = fmul float %680, %684		; visa id: 676
  br label %686, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 677

686:                                              ; preds = %678, %671
; BB67 :
  %.sroa.64.2 = phi float [ %685, %678 ], [ %677, %671 ]
  %687 = lshr i32 %599, 24		; visa id: 678
  br i1 %632, label %695, label %688, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 679

688:                                              ; preds = %686
; BB68 :
  %689 = and i32 %119, 2048
  %690 = sub nsw i32 0, %687, !spirv.Decorations !8798
  %691 = icmp eq i32 %689, 0		; visa id: 681
  %692 = select i1 %691, i32 %687, i32 %690		; visa id: 683
  %693 = sitofp i32 %692 to float		; visa id: 684
  %694 = fmul float %625, %693		; visa id: 685
  br label %703, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 686

695:                                              ; preds = %686
; BB69 :
  %696 = uitofp i32 %687 to float		; visa id: 688
  %697 = fmul float %625, %696		; visa id: 689
  %698 = and i32 %119, 2048
  %699 = icmp eq i32 %698, 0		; visa id: 690
  %700 = select i1 %699, i32 1, i32 -1		; visa id: 692
  %701 = sitofp i32 %700 to float		; visa id: 693
  %702 = fmul float %697, %701		; visa id: 694
  br label %703, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 695

703:                                              ; preds = %695, %688
; BB70 :
  %.sroa.88.2 = phi float [ %702, %695 ], [ %694, %688 ]
  %704 = and i32 %600, 255		; visa id: 696
  br i1 %632, label %712, label %705, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 697

705:                                              ; preds = %703
; BB71 :
  %706 = and i32 %119, 4096
  %707 = sub nsw i32 0, %704, !spirv.Decorations !8798
  %708 = icmp eq i32 %706, 0		; visa id: 699
  %709 = select i1 %708, i32 %704, i32 %707		; visa id: 701
  %710 = sitofp i32 %709 to float		; visa id: 702
  %711 = fmul float %625, %710		; visa id: 703
  br label %720, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 704

712:                                              ; preds = %703
; BB72 :
  %713 = uitofp i32 %704 to float		; visa id: 706
  %714 = fmul float %625, %713		; visa id: 707
  %715 = and i32 %119, 4096
  %716 = icmp eq i32 %715, 0		; visa id: 708
  %717 = select i1 %716, i32 1, i32 -1		; visa id: 710
  %718 = sitofp i32 %717 to float		; visa id: 711
  %719 = fmul float %714, %718		; visa id: 712
  br label %720, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 713

720:                                              ; preds = %712, %705
; BB73 :
  %.sroa.112.2 = phi float [ %719, %712 ], [ %711, %705 ]
  %721 = bitcast i32 %600 to <4 x i8>
  %722 = extractelement <4 x i8> %721, i32 1
  %723 = zext i8 %722 to i32		; visa id: 714
  br i1 %632, label %731, label %724, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 715

724:                                              ; preds = %720
; BB74 :
  %725 = and i32 %119, 8192
  %726 = sub nsw i32 0, %723, !spirv.Decorations !8798
  %727 = icmp eq i32 %725, 0		; visa id: 717
  %728 = select i1 %727, i32 %723, i32 %726		; visa id: 719
  %729 = sitofp i32 %728 to float		; visa id: 720
  %730 = fmul float %625, %729		; visa id: 721
  br label %739, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 722

731:                                              ; preds = %720
; BB75 :
  %732 = uitofp i32 %723 to float		; visa id: 724
  %733 = fmul float %625, %732		; visa id: 725
  %734 = and i32 %119, 8192
  %735 = icmp eq i32 %734, 0		; visa id: 726
  %736 = select i1 %735, i32 1, i32 -1		; visa id: 728
  %737 = sitofp i32 %736 to float		; visa id: 729
  %738 = fmul float %733, %737		; visa id: 730
  br label %739, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 731

739:                                              ; preds = %731, %724
; BB76 :
  %.sroa.136.2 = phi float [ %738, %731 ], [ %730, %724 ]
  %740 = extractelement <4 x i8> %721, i32 2
  %741 = zext i8 %740 to i32		; visa id: 732
  br i1 %632, label %749, label %742, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 733

742:                                              ; preds = %739
; BB77 :
  %743 = and i32 %119, 16384
  %744 = sub nsw i32 0, %741, !spirv.Decorations !8798
  %745 = icmp eq i32 %743, 0		; visa id: 735
  %746 = select i1 %745, i32 %741, i32 %744		; visa id: 737
  %747 = sitofp i32 %746 to float		; visa id: 738
  %748 = fmul float %625, %747		; visa id: 739
  br label %757, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 740

749:                                              ; preds = %739
; BB78 :
  %750 = uitofp i32 %741 to float		; visa id: 742
  %751 = fmul float %625, %750		; visa id: 743
  %752 = and i32 %119, 16384
  %753 = icmp eq i32 %752, 0		; visa id: 744
  %754 = select i1 %753, i32 1, i32 -1		; visa id: 746
  %755 = sitofp i32 %754 to float		; visa id: 747
  %756 = fmul float %751, %755		; visa id: 748
  br label %757, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 749

757:                                              ; preds = %749, %742
; BB79 :
  %.sroa.160.2 = phi float [ %756, %749 ], [ %748, %742 ]
  %758 = lshr i32 %600, 24		; visa id: 750
  br i1 %632, label %766, label %759, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 751

759:                                              ; preds = %757
; BB80 :
  %760 = and i32 %119, 32768
  %761 = sub nsw i32 0, %758, !spirv.Decorations !8798
  %762 = icmp eq i32 %760, 0		; visa id: 753
  %763 = select i1 %762, i32 %758, i32 %761		; visa id: 755
  %764 = sitofp i32 %763 to float		; visa id: 756
  %765 = fmul float %625, %764		; visa id: 757
  br label %774, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 758

766:                                              ; preds = %757
; BB81 :
  %767 = uitofp i32 %758 to float		; visa id: 760
  %768 = fmul float %625, %767		; visa id: 761
  %769 = and i32 %119, 32768
  %770 = icmp eq i32 %769, 0		; visa id: 762
  %771 = select i1 %770, i32 1, i32 -1		; visa id: 764
  %772 = sitofp i32 %771 to float		; visa id: 765
  %773 = fmul float %768, %772		; visa id: 766
  br label %774, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 767

774:                                              ; preds = %766, %759
; BB82 :
  %.sroa.184.2 = phi float [ %773, %766 ], [ %765, %759 ]
  %775 = zext i16 %611 to i32		; visa id: 768
  %776 = shl nuw i32 %775, 16, !spirv.Decorations !8788		; visa id: 769
  %777 = bitcast i32 %776 to float
  %778 = fmul float %.sroa.067.2, %777		; visa id: 770
  %779 = fadd float %.sroa.13.0, %778		; visa id: 771
  %780 = zext i16 %612 to i32		; visa id: 772
  %781 = shl nuw i32 %780, 16, !spirv.Decorations !8788		; visa id: 773
  %782 = bitcast i32 %781 to float
  %783 = fmul float %.sroa.40.2, %782		; visa id: 774
  %784 = fadd float %779, %783		; visa id: 775
  %785 = zext i16 %613 to i32		; visa id: 776
  %786 = shl nuw i32 %785, 16, !spirv.Decorations !8788		; visa id: 777
  %787 = bitcast i32 %786 to float
  %788 = fmul float %.sroa.64.2, %787		; visa id: 778
  %789 = fadd float %784, %788		; visa id: 779
  %790 = zext i16 %614 to i32		; visa id: 780
  %791 = shl nuw i32 %790, 16, !spirv.Decorations !8788		; visa id: 781
  %792 = bitcast i32 %791 to float
  %793 = fmul float %.sroa.88.2, %792		; visa id: 782
  %794 = fadd float %789, %793		; visa id: 783
  %795 = zext i16 %617 to i32		; visa id: 784
  %796 = shl nuw i32 %795, 16, !spirv.Decorations !8788		; visa id: 785
  %797 = bitcast i32 %796 to float
  %798 = fmul float %.sroa.112.2, %797		; visa id: 786
  %799 = fadd float %794, %798		; visa id: 787
  %800 = zext i16 %618 to i32		; visa id: 788
  %801 = shl nuw i32 %800, 16, !spirv.Decorations !8788		; visa id: 789
  %802 = bitcast i32 %801 to float
  %803 = fmul float %.sroa.136.2, %802		; visa id: 790
  %804 = fadd float %799, %803		; visa id: 791
  %805 = zext i16 %619 to i32		; visa id: 792
  %806 = shl nuw i32 %805, 16, !spirv.Decorations !8788		; visa id: 793
  %807 = bitcast i32 %806 to float
  %808 = fmul float %.sroa.160.2, %807		; visa id: 794
  %809 = fadd float %804, %808		; visa id: 795
  %810 = zext i16 %620 to i32		; visa id: 796
  %811 = shl nuw i32 %810, 16, !spirv.Decorations !8788		; visa id: 797
  %812 = bitcast i32 %811 to float
  %813 = fmul float %.sroa.184.2, %812		; visa id: 798
  %814 = fadd float %809, %813		; visa id: 799
  %815 = or i32 %169, 48		; visa id: 800
  %816 = zext i32 %815 to i64		; visa id: 801
  %817 = add i64 %816, %const_reg_qword2		; visa id: 802
  %IntToPtr2344 = inttoptr i64 %817 to ptr addrspace(1)		; visa id: 803
  %vCastload345 = load i32, ptr addrspace(1) %IntToPtr2344, align 2		; visa id: 803
  %818 = add i64 %817, 4
  %IntToPtr2346 = inttoptr i64 %818 to ptr addrspace(1)
  %vCastload347 = load i32, ptr addrspace(1) %IntToPtr2346, align 2		; visa id: 804
  %819 = add i64 %817, 8
  %IntToPtr2348 = inttoptr i64 %819 to ptr addrspace(1)
  %vCastload349 = load i32, ptr addrspace(1) %IntToPtr2348, align 2		; visa id: 805
  %820 = add i64 %817, 12
  %IntToPtr2350 = inttoptr i64 %820 to ptr addrspace(1)
  %vCastload351 = load i32, ptr addrspace(1) %IntToPtr2350, align 2		; visa id: 806
  %821 = bitcast i32 %vCastload345 to <2 x i16>		; visa id: 807
  %822 = bitcast i32 %vCastload347 to <2 x i16>		; visa id: 809
  %823 = extractelement <2 x i16> %821, i32 0		; visa id: 811
  %824 = extractelement <2 x i16> %821, i32 1		; visa id: 811
  %825 = extractelement <2 x i16> %822, i32 0		; visa id: 811
  %826 = extractelement <2 x i16> %822, i32 1		; visa id: 811
  %827 = bitcast i32 %vCastload349 to <2 x i16>		; visa id: 811
  %828 = bitcast i32 %vCastload351 to <2 x i16>		; visa id: 813
  %829 = extractelement <2 x i16> %827, i32 0		; visa id: 815
  %830 = extractelement <2 x i16> %827, i32 1		; visa id: 815
  %831 = extractelement <2 x i16> %828, i32 0		; visa id: 815
  %832 = extractelement <2 x i16> %828, i32 1		; visa id: 815
  %833 = and i32 %601, 255		; visa id: 815
  br i1 %632, label %841, label %834, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 816

834:                                              ; preds = %774
; BB83 :
  %835 = and i32 %119, 16777216
  %836 = sub nsw i32 0, %833, !spirv.Decorations !8798
  %837 = icmp eq i32 %835, 0		; visa id: 818
  %838 = select i1 %837, i32 %833, i32 %836		; visa id: 820
  %839 = sitofp i32 %838 to float		; visa id: 821
  %840 = fmul float %625, %839		; visa id: 822
  br label %849, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 823

841:                                              ; preds = %774
; BB84 :
  %842 = uitofp i32 %833 to float		; visa id: 825
  %843 = fmul float %625, %842		; visa id: 826
  %844 = and i32 %119, 16777216
  %845 = icmp eq i32 %844, 0		; visa id: 827
  %846 = select i1 %845, i32 1, i32 -1		; visa id: 829
  %847 = sitofp i32 %846 to float		; visa id: 830
  %848 = fmul float %843, %847		; visa id: 831
  br label %849, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 832

849:                                              ; preds = %841, %834
; BB85 :
  %.sroa.067.3 = phi float [ %848, %841 ], [ %840, %834 ]
  %850 = bitcast i32 %601 to <4 x i8>
  %851 = extractelement <4 x i8> %850, i32 1
  %852 = zext i8 %851 to i32		; visa id: 833
  br i1 %632, label %860, label %853, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 834

853:                                              ; preds = %849
; BB86 :
  %854 = and i32 %119, 33554432
  %855 = sub nsw i32 0, %852, !spirv.Decorations !8798
  %856 = icmp eq i32 %854, 0		; visa id: 836
  %857 = select i1 %856, i32 %852, i32 %855		; visa id: 838
  %858 = sitofp i32 %857 to float		; visa id: 839
  %859 = fmul float %625, %858		; visa id: 840
  br label %868, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 841

860:                                              ; preds = %849
; BB87 :
  %861 = uitofp i32 %852 to float		; visa id: 843
  %862 = fmul float %625, %861		; visa id: 844
  %863 = and i32 %119, 33554432
  %864 = icmp eq i32 %863, 0		; visa id: 845
  %865 = select i1 %864, i32 1, i32 -1		; visa id: 847
  %866 = sitofp i32 %865 to float		; visa id: 848
  %867 = fmul float %862, %866		; visa id: 849
  br label %868, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 850

868:                                              ; preds = %860, %853
; BB88 :
  %.sroa.40.3 = phi float [ %867, %860 ], [ %859, %853 ]
  %869 = extractelement <4 x i8> %850, i32 2
  %870 = zext i8 %869 to i32		; visa id: 851
  br i1 %632, label %878, label %871, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 852

871:                                              ; preds = %868
; BB89 :
  %872 = and i32 %119, 67108864
  %873 = sub nsw i32 0, %870, !spirv.Decorations !8798
  %874 = icmp eq i32 %872, 0		; visa id: 854
  %875 = select i1 %874, i32 %870, i32 %873		; visa id: 856
  %876 = sitofp i32 %875 to float		; visa id: 857
  %877 = fmul float %625, %876		; visa id: 858
  br label %886, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 859

878:                                              ; preds = %868
; BB90 :
  %879 = uitofp i32 %870 to float		; visa id: 861
  %880 = fmul float %625, %879		; visa id: 862
  %881 = and i32 %119, 67108864
  %882 = icmp eq i32 %881, 0		; visa id: 863
  %883 = select i1 %882, i32 1, i32 -1		; visa id: 865
  %884 = sitofp i32 %883 to float		; visa id: 866
  %885 = fmul float %880, %884		; visa id: 867
  br label %886, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 868

886:                                              ; preds = %878, %871
; BB91 :
  %.sroa.64.3 = phi float [ %885, %878 ], [ %877, %871 ]
  %887 = lshr i32 %601, 24		; visa id: 869
  br i1 %632, label %895, label %888, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 870

888:                                              ; preds = %886
; BB92 :
  %889 = and i32 %119, 134217728
  %890 = sub nsw i32 0, %887, !spirv.Decorations !8798
  %891 = icmp eq i32 %889, 0		; visa id: 872
  %892 = select i1 %891, i32 %887, i32 %890		; visa id: 874
  %893 = sitofp i32 %892 to float		; visa id: 875
  %894 = fmul float %625, %893		; visa id: 876
  br label %903, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 877

895:                                              ; preds = %886
; BB93 :
  %896 = uitofp i32 %887 to float		; visa id: 879
  %897 = fmul float %625, %896		; visa id: 880
  %898 = and i32 %119, 134217728
  %899 = icmp eq i32 %898, 0		; visa id: 881
  %900 = select i1 %899, i32 1, i32 -1		; visa id: 883
  %901 = sitofp i32 %900 to float		; visa id: 884
  %902 = fmul float %897, %901		; visa id: 885
  br label %903, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 886

903:                                              ; preds = %895, %888
; BB94 :
  %.sroa.88.3 = phi float [ %902, %895 ], [ %894, %888 ]
  %904 = and i32 %602, 255		; visa id: 887
  br i1 %632, label %912, label %905, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 888

905:                                              ; preds = %903
; BB95 :
  %906 = and i32 %119, 268435456
  %907 = sub nsw i32 0, %904, !spirv.Decorations !8798
  %908 = icmp eq i32 %906, 0		; visa id: 890
  %909 = select i1 %908, i32 %904, i32 %907		; visa id: 892
  %910 = sitofp i32 %909 to float		; visa id: 893
  %911 = fmul float %625, %910		; visa id: 894
  br label %920, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 895

912:                                              ; preds = %903
; BB96 :
  %913 = uitofp i32 %904 to float		; visa id: 897
  %914 = fmul float %625, %913		; visa id: 898
  %915 = and i32 %119, 268435456
  %916 = icmp eq i32 %915, 0		; visa id: 899
  %917 = select i1 %916, i32 1, i32 -1		; visa id: 901
  %918 = sitofp i32 %917 to float		; visa id: 902
  %919 = fmul float %914, %918		; visa id: 903
  br label %920, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 904

920:                                              ; preds = %912, %905
; BB97 :
  %.sroa.112.3 = phi float [ %919, %912 ], [ %911, %905 ]
  %921 = bitcast i32 %602 to <4 x i8>
  %922 = extractelement <4 x i8> %921, i32 1
  %923 = zext i8 %922 to i32		; visa id: 905
  br i1 %632, label %931, label %924, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 906

924:                                              ; preds = %920
; BB98 :
  %925 = and i32 %119, 536870912
  %926 = sub nsw i32 0, %923, !spirv.Decorations !8798
  %927 = icmp eq i32 %925, 0		; visa id: 908
  %928 = select i1 %927, i32 %923, i32 %926		; visa id: 910
  %929 = sitofp i32 %928 to float		; visa id: 911
  %930 = fmul float %625, %929		; visa id: 912
  br label %939, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 913

931:                                              ; preds = %920
; BB99 :
  %932 = uitofp i32 %923 to float		; visa id: 915
  %933 = fmul float %625, %932		; visa id: 916
  %934 = and i32 %119, 536870912
  %935 = icmp eq i32 %934, 0		; visa id: 917
  %936 = select i1 %935, i32 1, i32 -1		; visa id: 919
  %937 = sitofp i32 %936 to float		; visa id: 920
  %938 = fmul float %933, %937		; visa id: 921
  br label %939, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 922

939:                                              ; preds = %931, %924
; BB100 :
  %.sroa.136.3 = phi float [ %938, %931 ], [ %930, %924 ]
  %940 = extractelement <4 x i8> %921, i32 2
  %941 = zext i8 %940 to i32		; visa id: 923
  br i1 %632, label %949, label %942, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 924

942:                                              ; preds = %939
; BB101 :
  %943 = and i32 %119, 1073741824
  %944 = sub nsw i32 0, %941, !spirv.Decorations !8798
  %945 = icmp eq i32 %943, 0		; visa id: 926
  %946 = select i1 %945, i32 %941, i32 %944		; visa id: 928
  %947 = sitofp i32 %946 to float		; visa id: 929
  %948 = fmul float %625, %947		; visa id: 930
  br label %957, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 931

949:                                              ; preds = %939
; BB102 :
  %950 = uitofp i32 %941 to float		; visa id: 933
  %951 = fmul float %625, %950		; visa id: 934
  %952 = and i32 %119, 1073741824
  %953 = icmp eq i32 %952, 0		; visa id: 935
  %954 = select i1 %953, i32 1, i32 -1		; visa id: 937
  %955 = sitofp i32 %954 to float		; visa id: 938
  %956 = fmul float %951, %955		; visa id: 939
  br label %957, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 940

957:                                              ; preds = %949, %942
; BB103 :
  %.sroa.160.3 = phi float [ %956, %949 ], [ %948, %942 ]
  %958 = lshr i32 %602, 24		; visa id: 941
  br i1 %632, label %965, label %959, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 942

959:                                              ; preds = %957
; BB104 :
  %960 = sub nsw i32 0, %958, !spirv.Decorations !8798
  %961 = icmp slt i32 %119, 0		; visa id: 944
  %962 = select i1 %961, i32 %960, i32 %958		; visa id: 945
  %963 = sitofp i32 %962 to float		; visa id: 946
  %964 = fmul float %625, %963		; visa id: 947
  br label %._crit_edge44.2, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 948

965:                                              ; preds = %957
; BB105 :
  %966 = uitofp i32 %958 to float		; visa id: 950
  %967 = fmul float %625, %966		; visa id: 951
  %968 = icmp sgt i32 %119, -1		; visa id: 952
  %969 = select i1 %968, i32 1, i32 -1		; visa id: 953
  %970 = sitofp i32 %969 to float		; visa id: 954
  %971 = fmul float %967, %970		; visa id: 955
  br label %._crit_edge44.2, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 956

._crit_edge44.2:                                  ; preds = %965, %959
; BB106 :
  %.sroa.184.3 = phi float [ %971, %965 ], [ %964, %959 ]
  %972 = zext i16 %823 to i32		; visa id: 957
  %973 = shl nuw i32 %972, 16, !spirv.Decorations !8788		; visa id: 958
  %974 = bitcast i32 %973 to float
  %975 = fmul float %.sroa.067.3, %974		; visa id: 959
  %976 = fadd float %.sroa.18.0, %975		; visa id: 960
  %977 = zext i16 %824 to i32		; visa id: 961
  %978 = shl nuw i32 %977, 16, !spirv.Decorations !8788		; visa id: 962
  %979 = bitcast i32 %978 to float
  %980 = fmul float %.sroa.40.3, %979		; visa id: 963
  %981 = fadd float %976, %980		; visa id: 964
  %982 = zext i16 %825 to i32		; visa id: 965
  %983 = shl nuw i32 %982, 16, !spirv.Decorations !8788		; visa id: 966
  %984 = bitcast i32 %983 to float
  %985 = fmul float %.sroa.64.3, %984		; visa id: 967
  %986 = fadd float %981, %985		; visa id: 968
  %987 = zext i16 %826 to i32		; visa id: 969
  %988 = shl nuw i32 %987, 16, !spirv.Decorations !8788		; visa id: 970
  %989 = bitcast i32 %988 to float
  %990 = fmul float %.sroa.88.3, %989		; visa id: 971
  %991 = fadd float %986, %990		; visa id: 972
  %992 = zext i16 %829 to i32		; visa id: 973
  %993 = shl nuw i32 %992, 16, !spirv.Decorations !8788		; visa id: 974
  %994 = bitcast i32 %993 to float
  %995 = fmul float %.sroa.112.3, %994		; visa id: 975
  %996 = fadd float %991, %995		; visa id: 976
  %997 = zext i16 %830 to i32		; visa id: 977
  %998 = shl nuw i32 %997, 16, !spirv.Decorations !8788		; visa id: 978
  %999 = bitcast i32 %998 to float
  %1000 = fmul float %.sroa.136.3, %999		; visa id: 979
  %1001 = fadd float %996, %1000		; visa id: 980
  %1002 = zext i16 %831 to i32		; visa id: 981
  %1003 = shl nuw i32 %1002, 16, !spirv.Decorations !8788		; visa id: 982
  %1004 = bitcast i32 %1003 to float
  %1005 = fmul float %.sroa.160.3, %1004		; visa id: 983
  %1006 = fadd float %1001, %1005		; visa id: 984
  %1007 = zext i16 %832 to i32		; visa id: 985
  %1008 = shl nuw i32 %1007, 16, !spirv.Decorations !8788		; visa id: 986
  %1009 = bitcast i32 %1008 to float
  %1010 = fmul float %.sroa.184.3, %1009		; visa id: 987
  %1011 = fadd float %1006, %1010		; visa id: 988
  %1012 = lshr i16 %131, 8		; visa id: 989
  %1013 = and i32 %120, 255
  %1014 = and i32 %139, 768		; visa id: 990
  %1015 = or i32 %1013, %1014		; visa id: 991
  %1016 = shl nuw nsw i32 %1015, 3, !spirv.Decorations !8791		; visa id: 992
  %1017 = zext i32 %1016 to i64		; visa id: 993
  %1018 = add i64 %111, %1017		; visa id: 994
  %1019 = inttoptr i64 %1018 to ptr addrspace(1)		; visa id: 995
  %1020 = load <2 x i32>, ptr addrspace(1) %1019, align 4		; visa id: 995
  %1021 = bitcast i32 %120 to <4 x i8>
  %1022 = extractelement <4 x i8> %1021, i32 2
  %1023 = lshr i32 %139, 2		; visa id: 996
  %1024 = and i32 %1023, 768
  %1025 = zext i8 %1022 to i32		; visa id: 997
  %1026 = or i32 %1025, %1024		; visa id: 998
  %1027 = shl nuw nsw i32 %1026, 3, !spirv.Decorations !8791		; visa id: 999
  %1028 = zext i32 %1027 to i64		; visa id: 1000
  %1029 = add i64 %111, %1028		; visa id: 1001
  %1030 = inttoptr i64 %1029 to ptr addrspace(1)		; visa id: 1002
  %1031 = load <2 x i32>, ptr addrspace(1) %1030, align 4		; visa id: 1002
  %1032 = extractelement <2 x i32> %1020, i32 0		; visa id: 1003
  %1033 = extractelement <2 x i32> %1020, i32 1		; visa id: 1003
  %1034 = extractelement <2 x i32> %1031, i32 0		; visa id: 1003
  %1035 = extractelement <2 x i32> %1031, i32 1		; visa id: 1003
  %1036 = or i32 %169, 64		; visa id: 1003
  %1037 = zext i32 %1036 to i64		; visa id: 1004
  %1038 = add i64 %1037, %const_reg_qword2		; visa id: 1005
  %IntToPtr2352 = inttoptr i64 %1038 to ptr addrspace(1)		; visa id: 1006
  %vCastload353 = load i32, ptr addrspace(1) %IntToPtr2352, align 2		; visa id: 1006
  %1039 = add i64 %1038, 4
  %IntToPtr2354 = inttoptr i64 %1039 to ptr addrspace(1)
  %vCastload355 = load i32, ptr addrspace(1) %IntToPtr2354, align 2		; visa id: 1007
  %1040 = add i64 %1038, 8
  %IntToPtr2356 = inttoptr i64 %1040 to ptr addrspace(1)
  %vCastload357 = load i32, ptr addrspace(1) %IntToPtr2356, align 2		; visa id: 1008
  %1041 = add i64 %1038, 12
  %IntToPtr2358 = inttoptr i64 %1041 to ptr addrspace(1)
  %vCastload359 = load i32, ptr addrspace(1) %IntToPtr2358, align 2		; visa id: 1009
  %1042 = bitcast i32 %vCastload353 to <2 x i16>		; visa id: 1010
  %1043 = bitcast i32 %vCastload355 to <2 x i16>		; visa id: 1012
  %1044 = extractelement <2 x i16> %1042, i32 0		; visa id: 1014
  %1045 = extractelement <2 x i16> %1042, i32 1		; visa id: 1014
  %1046 = extractelement <2 x i16> %1043, i32 0		; visa id: 1014
  %1047 = extractelement <2 x i16> %1043, i32 1		; visa id: 1014
  %1048 = bitcast i32 %vCastload357 to <2 x i16>		; visa id: 1014
  %1049 = bitcast i32 %vCastload359 to <2 x i16>		; visa id: 1016
  %1050 = extractelement <2 x i16> %1048, i32 0		; visa id: 1018
  %1051 = extractelement <2 x i16> %1048, i32 1		; visa id: 1018
  %1052 = extractelement <2 x i16> %1049, i32 0		; visa id: 1018
  %1053 = extractelement <2 x i16> %1049, i32 1		; visa id: 1018
  %1054 = zext i16 %1012 to i32		; visa id: 1018
  %1055 = and i32 %1054, 15		; visa id: 1019
  %1056 = uitofp i32 %1055 to float		; visa id: 1020
  %1057 = fadd float %1056, 5.000000e-01		; visa id: 1021
  %1058 = fmul float %137, %1057		; visa id: 1022
  %1059 = fmul float %1058, 2.500000e-01		; visa id: 1023
  %1060 = bitcast float %1059 to i32
  %1061 = and i32 %1060, 2147483647		; visa id: 1024
  %1062 = icmp ugt i32 %1061, 2139095040
  %1063 = fcmp oeq float %152, 0x7FF0000000000000		; visa id: 1025
  %1064 = fcmp une float %152, %152
  %1065 = or i1 %1064, %1063		; visa id: 1026
  %1066 = or i1 %1065, %1062		; visa id: 1028
  %1067 = and i32 %1032, 255		; visa id: 1030
  br i1 %1066, label %1075, label %1068, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1031

1068:                                             ; preds = %._crit_edge44.2
; BB107 :
  %1069 = and i32 %120, 256
  %1070 = sub nsw i32 0, %1067, !spirv.Decorations !8798
  %1071 = icmp eq i32 %1069, 0		; visa id: 1033
  %1072 = select i1 %1071, i32 %1067, i32 %1070		; visa id: 1035
  %1073 = sitofp i32 %1072 to float		; visa id: 1036
  %1074 = fmul float %1059, %1073		; visa id: 1037
  br label %1083, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1038

1075:                                             ; preds = %._crit_edge44.2
; BB108 :
  %1076 = uitofp i32 %1067 to float		; visa id: 1040
  %1077 = fmul float %1059, %1076		; visa id: 1041
  %1078 = and i32 %120, 256
  %1079 = icmp eq i32 %1078, 0		; visa id: 1042
  %1080 = select i1 %1079, i32 1, i32 -1		; visa id: 1044
  %1081 = sitofp i32 %1080 to float		; visa id: 1045
  %1082 = fmul float %1077, %1081		; visa id: 1046
  br label %1083, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1047

1083:                                             ; preds = %1075, %1068
; BB109 :
  %.sroa.067.4 = phi float [ %1082, %1075 ], [ %1074, %1068 ]
  %1084 = bitcast i32 %1032 to <4 x i8>
  %1085 = extractelement <4 x i8> %1084, i32 1
  %1086 = zext i8 %1085 to i32		; visa id: 1048
  br i1 %1066, label %1094, label %1087, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1049

1087:                                             ; preds = %1083
; BB110 :
  %1088 = and i32 %120, 512
  %1089 = sub nsw i32 0, %1086, !spirv.Decorations !8798
  %1090 = icmp eq i32 %1088, 0		; visa id: 1051
  %1091 = select i1 %1090, i32 %1086, i32 %1089		; visa id: 1053
  %1092 = sitofp i32 %1091 to float		; visa id: 1054
  %1093 = fmul float %1059, %1092		; visa id: 1055
  br label %1102, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1056

1094:                                             ; preds = %1083
; BB111 :
  %1095 = uitofp i32 %1086 to float		; visa id: 1058
  %1096 = fmul float %1059, %1095		; visa id: 1059
  %1097 = and i32 %120, 512
  %1098 = icmp eq i32 %1097, 0		; visa id: 1060
  %1099 = select i1 %1098, i32 1, i32 -1		; visa id: 1062
  %1100 = sitofp i32 %1099 to float		; visa id: 1063
  %1101 = fmul float %1096, %1100		; visa id: 1064
  br label %1102, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1065

1102:                                             ; preds = %1094, %1087
; BB112 :
  %.sroa.40.4 = phi float [ %1101, %1094 ], [ %1093, %1087 ]
  %1103 = extractelement <4 x i8> %1084, i32 2
  %1104 = zext i8 %1103 to i32		; visa id: 1066
  br i1 %1066, label %1112, label %1105, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1067

1105:                                             ; preds = %1102
; BB113 :
  %1106 = and i32 %120, 1024
  %1107 = sub nsw i32 0, %1104, !spirv.Decorations !8798
  %1108 = icmp eq i32 %1106, 0		; visa id: 1069
  %1109 = select i1 %1108, i32 %1104, i32 %1107		; visa id: 1071
  %1110 = sitofp i32 %1109 to float		; visa id: 1072
  %1111 = fmul float %1059, %1110		; visa id: 1073
  br label %1120, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1074

1112:                                             ; preds = %1102
; BB114 :
  %1113 = uitofp i32 %1104 to float		; visa id: 1076
  %1114 = fmul float %1059, %1113		; visa id: 1077
  %1115 = and i32 %120, 1024
  %1116 = icmp eq i32 %1115, 0		; visa id: 1078
  %1117 = select i1 %1116, i32 1, i32 -1		; visa id: 1080
  %1118 = sitofp i32 %1117 to float		; visa id: 1081
  %1119 = fmul float %1114, %1118		; visa id: 1082
  br label %1120, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1083

1120:                                             ; preds = %1112, %1105
; BB115 :
  %.sroa.64.4 = phi float [ %1119, %1112 ], [ %1111, %1105 ]
  %1121 = lshr i32 %1032, 24		; visa id: 1084
  br i1 %1066, label %1129, label %1122, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1085

1122:                                             ; preds = %1120
; BB116 :
  %1123 = and i32 %120, 2048
  %1124 = sub nsw i32 0, %1121, !spirv.Decorations !8798
  %1125 = icmp eq i32 %1123, 0		; visa id: 1087
  %1126 = select i1 %1125, i32 %1121, i32 %1124		; visa id: 1089
  %1127 = sitofp i32 %1126 to float		; visa id: 1090
  %1128 = fmul float %1059, %1127		; visa id: 1091
  br label %1137, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1092

1129:                                             ; preds = %1120
; BB117 :
  %1130 = uitofp i32 %1121 to float		; visa id: 1094
  %1131 = fmul float %1059, %1130		; visa id: 1095
  %1132 = and i32 %120, 2048
  %1133 = icmp eq i32 %1132, 0		; visa id: 1096
  %1134 = select i1 %1133, i32 1, i32 -1		; visa id: 1098
  %1135 = sitofp i32 %1134 to float		; visa id: 1099
  %1136 = fmul float %1131, %1135		; visa id: 1100
  br label %1137, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1101

1137:                                             ; preds = %1129, %1122
; BB118 :
  %.sroa.88.4 = phi float [ %1136, %1129 ], [ %1128, %1122 ]
  %1138 = and i32 %1033, 255		; visa id: 1102
  br i1 %1066, label %1146, label %1139, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1103

1139:                                             ; preds = %1137
; BB119 :
  %1140 = and i32 %120, 4096
  %1141 = sub nsw i32 0, %1138, !spirv.Decorations !8798
  %1142 = icmp eq i32 %1140, 0		; visa id: 1105
  %1143 = select i1 %1142, i32 %1138, i32 %1141		; visa id: 1107
  %1144 = sitofp i32 %1143 to float		; visa id: 1108
  %1145 = fmul float %1059, %1144		; visa id: 1109
  br label %1154, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1110

1146:                                             ; preds = %1137
; BB120 :
  %1147 = uitofp i32 %1138 to float		; visa id: 1112
  %1148 = fmul float %1059, %1147		; visa id: 1113
  %1149 = and i32 %120, 4096
  %1150 = icmp eq i32 %1149, 0		; visa id: 1114
  %1151 = select i1 %1150, i32 1, i32 -1		; visa id: 1116
  %1152 = sitofp i32 %1151 to float		; visa id: 1117
  %1153 = fmul float %1148, %1152		; visa id: 1118
  br label %1154, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1119

1154:                                             ; preds = %1146, %1139
; BB121 :
  %.sroa.112.4 = phi float [ %1153, %1146 ], [ %1145, %1139 ]
  %1155 = bitcast i32 %1033 to <4 x i8>
  %1156 = extractelement <4 x i8> %1155, i32 1
  %1157 = zext i8 %1156 to i32		; visa id: 1120
  br i1 %1066, label %1165, label %1158, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1121

1158:                                             ; preds = %1154
; BB122 :
  %1159 = and i32 %120, 8192
  %1160 = sub nsw i32 0, %1157, !spirv.Decorations !8798
  %1161 = icmp eq i32 %1159, 0		; visa id: 1123
  %1162 = select i1 %1161, i32 %1157, i32 %1160		; visa id: 1125
  %1163 = sitofp i32 %1162 to float		; visa id: 1126
  %1164 = fmul float %1059, %1163		; visa id: 1127
  br label %1173, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1128

1165:                                             ; preds = %1154
; BB123 :
  %1166 = uitofp i32 %1157 to float		; visa id: 1130
  %1167 = fmul float %1059, %1166		; visa id: 1131
  %1168 = and i32 %120, 8192
  %1169 = icmp eq i32 %1168, 0		; visa id: 1132
  %1170 = select i1 %1169, i32 1, i32 -1		; visa id: 1134
  %1171 = sitofp i32 %1170 to float		; visa id: 1135
  %1172 = fmul float %1167, %1171		; visa id: 1136
  br label %1173, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1137

1173:                                             ; preds = %1165, %1158
; BB124 :
  %.sroa.136.4 = phi float [ %1172, %1165 ], [ %1164, %1158 ]
  %1174 = extractelement <4 x i8> %1155, i32 2
  %1175 = zext i8 %1174 to i32		; visa id: 1138
  br i1 %1066, label %1183, label %1176, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1139

1176:                                             ; preds = %1173
; BB125 :
  %1177 = and i32 %120, 16384
  %1178 = sub nsw i32 0, %1175, !spirv.Decorations !8798
  %1179 = icmp eq i32 %1177, 0		; visa id: 1141
  %1180 = select i1 %1179, i32 %1175, i32 %1178		; visa id: 1143
  %1181 = sitofp i32 %1180 to float		; visa id: 1144
  %1182 = fmul float %1059, %1181		; visa id: 1145
  br label %1191, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1146

1183:                                             ; preds = %1173
; BB126 :
  %1184 = uitofp i32 %1175 to float		; visa id: 1148
  %1185 = fmul float %1059, %1184		; visa id: 1149
  %1186 = and i32 %120, 16384
  %1187 = icmp eq i32 %1186, 0		; visa id: 1150
  %1188 = select i1 %1187, i32 1, i32 -1		; visa id: 1152
  %1189 = sitofp i32 %1188 to float		; visa id: 1153
  %1190 = fmul float %1185, %1189		; visa id: 1154
  br label %1191, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1155

1191:                                             ; preds = %1183, %1176
; BB127 :
  %.sroa.160.4 = phi float [ %1190, %1183 ], [ %1182, %1176 ]
  %1192 = lshr i32 %1033, 24		; visa id: 1156
  br i1 %1066, label %1200, label %1193, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1157

1193:                                             ; preds = %1191
; BB128 :
  %1194 = and i32 %120, 32768
  %1195 = sub nsw i32 0, %1192, !spirv.Decorations !8798
  %1196 = icmp eq i32 %1194, 0		; visa id: 1159
  %1197 = select i1 %1196, i32 %1192, i32 %1195		; visa id: 1161
  %1198 = sitofp i32 %1197 to float		; visa id: 1162
  %1199 = fmul float %1059, %1198		; visa id: 1163
  br label %1208, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1164

1200:                                             ; preds = %1191
; BB129 :
  %1201 = uitofp i32 %1192 to float		; visa id: 1166
  %1202 = fmul float %1059, %1201		; visa id: 1167
  %1203 = and i32 %120, 32768
  %1204 = icmp eq i32 %1203, 0		; visa id: 1168
  %1205 = select i1 %1204, i32 1, i32 -1		; visa id: 1170
  %1206 = sitofp i32 %1205 to float		; visa id: 1171
  %1207 = fmul float %1202, %1206		; visa id: 1172
  br label %1208, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1173

1208:                                             ; preds = %1200, %1193
; BB130 :
  %.sroa.184.4 = phi float [ %1207, %1200 ], [ %1199, %1193 ]
  %1209 = zext i16 %1044 to i32		; visa id: 1174
  %1210 = shl nuw i32 %1209, 16, !spirv.Decorations !8788		; visa id: 1175
  %1211 = bitcast i32 %1210 to float
  %1212 = fmul float %.sroa.067.4, %1211		; visa id: 1176
  %1213 = fadd float %.sroa.21.0, %1212		; visa id: 1177
  %1214 = zext i16 %1045 to i32		; visa id: 1178
  %1215 = shl nuw i32 %1214, 16, !spirv.Decorations !8788		; visa id: 1179
  %1216 = bitcast i32 %1215 to float
  %1217 = fmul float %.sroa.40.4, %1216		; visa id: 1180
  %1218 = fadd float %1213, %1217		; visa id: 1181
  %1219 = zext i16 %1046 to i32		; visa id: 1182
  %1220 = shl nuw i32 %1219, 16, !spirv.Decorations !8788		; visa id: 1183
  %1221 = bitcast i32 %1220 to float
  %1222 = fmul float %.sroa.64.4, %1221		; visa id: 1184
  %1223 = fadd float %1218, %1222		; visa id: 1185
  %1224 = zext i16 %1047 to i32		; visa id: 1186
  %1225 = shl nuw i32 %1224, 16, !spirv.Decorations !8788		; visa id: 1187
  %1226 = bitcast i32 %1225 to float
  %1227 = fmul float %.sroa.88.4, %1226		; visa id: 1188
  %1228 = fadd float %1223, %1227		; visa id: 1189
  %1229 = zext i16 %1050 to i32		; visa id: 1190
  %1230 = shl nuw i32 %1229, 16, !spirv.Decorations !8788		; visa id: 1191
  %1231 = bitcast i32 %1230 to float
  %1232 = fmul float %.sroa.112.4, %1231		; visa id: 1192
  %1233 = fadd float %1228, %1232		; visa id: 1193
  %1234 = zext i16 %1051 to i32		; visa id: 1194
  %1235 = shl nuw i32 %1234, 16, !spirv.Decorations !8788		; visa id: 1195
  %1236 = bitcast i32 %1235 to float
  %1237 = fmul float %.sroa.136.4, %1236		; visa id: 1196
  %1238 = fadd float %1233, %1237		; visa id: 1197
  %1239 = zext i16 %1052 to i32		; visa id: 1198
  %1240 = shl nuw i32 %1239, 16, !spirv.Decorations !8788		; visa id: 1199
  %1241 = bitcast i32 %1240 to float
  %1242 = fmul float %.sroa.160.4, %1241		; visa id: 1200
  %1243 = fadd float %1238, %1242		; visa id: 1201
  %1244 = zext i16 %1053 to i32		; visa id: 1202
  %1245 = shl nuw i32 %1244, 16, !spirv.Decorations !8788		; visa id: 1203
  %1246 = bitcast i32 %1245 to float
  %1247 = fmul float %.sroa.184.4, %1246		; visa id: 1204
  %1248 = fadd float %1243, %1247		; visa id: 1205
  %1249 = or i32 %169, 80		; visa id: 1206
  %1250 = zext i32 %1249 to i64		; visa id: 1207
  %1251 = add i64 %1250, %const_reg_qword2		; visa id: 1208
  %IntToPtr2360 = inttoptr i64 %1251 to ptr addrspace(1)		; visa id: 1209
  %vCastload361 = load i32, ptr addrspace(1) %IntToPtr2360, align 2		; visa id: 1209
  %1252 = add i64 %1251, 4
  %IntToPtr2362 = inttoptr i64 %1252 to ptr addrspace(1)
  %vCastload363 = load i32, ptr addrspace(1) %IntToPtr2362, align 2		; visa id: 1210
  %1253 = add i64 %1251, 8
  %IntToPtr2364 = inttoptr i64 %1253 to ptr addrspace(1)
  %vCastload365 = load i32, ptr addrspace(1) %IntToPtr2364, align 2		; visa id: 1211
  %1254 = add i64 %1251, 12
  %IntToPtr2366 = inttoptr i64 %1254 to ptr addrspace(1)
  %vCastload367 = load i32, ptr addrspace(1) %IntToPtr2366, align 2		; visa id: 1212
  %1255 = bitcast i32 %vCastload361 to <2 x i16>		; visa id: 1213
  %1256 = bitcast i32 %vCastload363 to <2 x i16>		; visa id: 1215
  %1257 = extractelement <2 x i16> %1255, i32 0		; visa id: 1217
  %1258 = extractelement <2 x i16> %1255, i32 1		; visa id: 1217
  %1259 = extractelement <2 x i16> %1256, i32 0		; visa id: 1217
  %1260 = extractelement <2 x i16> %1256, i32 1		; visa id: 1217
  %1261 = bitcast i32 %vCastload365 to <2 x i16>		; visa id: 1217
  %1262 = bitcast i32 %vCastload367 to <2 x i16>		; visa id: 1219
  %1263 = extractelement <2 x i16> %1261, i32 0		; visa id: 1221
  %1264 = extractelement <2 x i16> %1261, i32 1		; visa id: 1221
  %1265 = extractelement <2 x i16> %1262, i32 0		; visa id: 1221
  %1266 = extractelement <2 x i16> %1262, i32 1		; visa id: 1221
  %1267 = and i32 %1034, 255		; visa id: 1221
  br i1 %1066, label %1275, label %1268, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1222

1268:                                             ; preds = %1208
; BB131 :
  %1269 = and i32 %120, 16777216
  %1270 = sub nsw i32 0, %1267, !spirv.Decorations !8798
  %1271 = icmp eq i32 %1269, 0		; visa id: 1224
  %1272 = select i1 %1271, i32 %1267, i32 %1270		; visa id: 1226
  %1273 = sitofp i32 %1272 to float		; visa id: 1227
  %1274 = fmul float %1059, %1273		; visa id: 1228
  br label %1283, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1229

1275:                                             ; preds = %1208
; BB132 :
  %1276 = uitofp i32 %1267 to float		; visa id: 1231
  %1277 = fmul float %1059, %1276		; visa id: 1232
  %1278 = and i32 %120, 16777216
  %1279 = icmp eq i32 %1278, 0		; visa id: 1233
  %1280 = select i1 %1279, i32 1, i32 -1		; visa id: 1235
  %1281 = sitofp i32 %1280 to float		; visa id: 1236
  %1282 = fmul float %1277, %1281		; visa id: 1237
  br label %1283, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1238

1283:                                             ; preds = %1275, %1268
; BB133 :
  %.sroa.067.5 = phi float [ %1282, %1275 ], [ %1274, %1268 ]
  %1284 = bitcast i32 %1034 to <4 x i8>
  %1285 = extractelement <4 x i8> %1284, i32 1
  %1286 = zext i8 %1285 to i32		; visa id: 1239
  br i1 %1066, label %1294, label %1287, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1240

1287:                                             ; preds = %1283
; BB134 :
  %1288 = and i32 %120, 33554432
  %1289 = sub nsw i32 0, %1286, !spirv.Decorations !8798
  %1290 = icmp eq i32 %1288, 0		; visa id: 1242
  %1291 = select i1 %1290, i32 %1286, i32 %1289		; visa id: 1244
  %1292 = sitofp i32 %1291 to float		; visa id: 1245
  %1293 = fmul float %1059, %1292		; visa id: 1246
  br label %1302, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1247

1294:                                             ; preds = %1283
; BB135 :
  %1295 = uitofp i32 %1286 to float		; visa id: 1249
  %1296 = fmul float %1059, %1295		; visa id: 1250
  %1297 = and i32 %120, 33554432
  %1298 = icmp eq i32 %1297, 0		; visa id: 1251
  %1299 = select i1 %1298, i32 1, i32 -1		; visa id: 1253
  %1300 = sitofp i32 %1299 to float		; visa id: 1254
  %1301 = fmul float %1296, %1300		; visa id: 1255
  br label %1302, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1256

1302:                                             ; preds = %1294, %1287
; BB136 :
  %.sroa.40.5 = phi float [ %1301, %1294 ], [ %1293, %1287 ]
  %1303 = extractelement <4 x i8> %1284, i32 2
  %1304 = zext i8 %1303 to i32		; visa id: 1257
  br i1 %1066, label %1312, label %1305, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1258

1305:                                             ; preds = %1302
; BB137 :
  %1306 = and i32 %120, 67108864
  %1307 = sub nsw i32 0, %1304, !spirv.Decorations !8798
  %1308 = icmp eq i32 %1306, 0		; visa id: 1260
  %1309 = select i1 %1308, i32 %1304, i32 %1307		; visa id: 1262
  %1310 = sitofp i32 %1309 to float		; visa id: 1263
  %1311 = fmul float %1059, %1310		; visa id: 1264
  br label %1320, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1265

1312:                                             ; preds = %1302
; BB138 :
  %1313 = uitofp i32 %1304 to float		; visa id: 1267
  %1314 = fmul float %1059, %1313		; visa id: 1268
  %1315 = and i32 %120, 67108864
  %1316 = icmp eq i32 %1315, 0		; visa id: 1269
  %1317 = select i1 %1316, i32 1, i32 -1		; visa id: 1271
  %1318 = sitofp i32 %1317 to float		; visa id: 1272
  %1319 = fmul float %1314, %1318		; visa id: 1273
  br label %1320, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1274

1320:                                             ; preds = %1312, %1305
; BB139 :
  %.sroa.64.5 = phi float [ %1319, %1312 ], [ %1311, %1305 ]
  %1321 = lshr i32 %1034, 24		; visa id: 1275
  br i1 %1066, label %1329, label %1322, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1276

1322:                                             ; preds = %1320
; BB140 :
  %1323 = and i32 %120, 134217728
  %1324 = sub nsw i32 0, %1321, !spirv.Decorations !8798
  %1325 = icmp eq i32 %1323, 0		; visa id: 1278
  %1326 = select i1 %1325, i32 %1321, i32 %1324		; visa id: 1280
  %1327 = sitofp i32 %1326 to float		; visa id: 1281
  %1328 = fmul float %1059, %1327		; visa id: 1282
  br label %1337, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1283

1329:                                             ; preds = %1320
; BB141 :
  %1330 = uitofp i32 %1321 to float		; visa id: 1285
  %1331 = fmul float %1059, %1330		; visa id: 1286
  %1332 = and i32 %120, 134217728
  %1333 = icmp eq i32 %1332, 0		; visa id: 1287
  %1334 = select i1 %1333, i32 1, i32 -1		; visa id: 1289
  %1335 = sitofp i32 %1334 to float		; visa id: 1290
  %1336 = fmul float %1331, %1335		; visa id: 1291
  br label %1337, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1292

1337:                                             ; preds = %1329, %1322
; BB142 :
  %.sroa.88.5 = phi float [ %1336, %1329 ], [ %1328, %1322 ]
  %1338 = and i32 %1035, 255		; visa id: 1293
  br i1 %1066, label %1346, label %1339, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1294

1339:                                             ; preds = %1337
; BB143 :
  %1340 = and i32 %120, 268435456
  %1341 = sub nsw i32 0, %1338, !spirv.Decorations !8798
  %1342 = icmp eq i32 %1340, 0		; visa id: 1296
  %1343 = select i1 %1342, i32 %1338, i32 %1341		; visa id: 1298
  %1344 = sitofp i32 %1343 to float		; visa id: 1299
  %1345 = fmul float %1059, %1344		; visa id: 1300
  br label %1354, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1301

1346:                                             ; preds = %1337
; BB144 :
  %1347 = uitofp i32 %1338 to float		; visa id: 1303
  %1348 = fmul float %1059, %1347		; visa id: 1304
  %1349 = and i32 %120, 268435456
  %1350 = icmp eq i32 %1349, 0		; visa id: 1305
  %1351 = select i1 %1350, i32 1, i32 -1		; visa id: 1307
  %1352 = sitofp i32 %1351 to float		; visa id: 1308
  %1353 = fmul float %1348, %1352		; visa id: 1309
  br label %1354, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1310

1354:                                             ; preds = %1346, %1339
; BB145 :
  %.sroa.112.5 = phi float [ %1353, %1346 ], [ %1345, %1339 ]
  %1355 = bitcast i32 %1035 to <4 x i8>
  %1356 = extractelement <4 x i8> %1355, i32 1
  %1357 = zext i8 %1356 to i32		; visa id: 1311
  br i1 %1066, label %1365, label %1358, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1312

1358:                                             ; preds = %1354
; BB146 :
  %1359 = and i32 %120, 536870912
  %1360 = sub nsw i32 0, %1357, !spirv.Decorations !8798
  %1361 = icmp eq i32 %1359, 0		; visa id: 1314
  %1362 = select i1 %1361, i32 %1357, i32 %1360		; visa id: 1316
  %1363 = sitofp i32 %1362 to float		; visa id: 1317
  %1364 = fmul float %1059, %1363		; visa id: 1318
  br label %1373, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1319

1365:                                             ; preds = %1354
; BB147 :
  %1366 = uitofp i32 %1357 to float		; visa id: 1321
  %1367 = fmul float %1059, %1366		; visa id: 1322
  %1368 = and i32 %120, 536870912
  %1369 = icmp eq i32 %1368, 0		; visa id: 1323
  %1370 = select i1 %1369, i32 1, i32 -1		; visa id: 1325
  %1371 = sitofp i32 %1370 to float		; visa id: 1326
  %1372 = fmul float %1367, %1371		; visa id: 1327
  br label %1373, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1328

1373:                                             ; preds = %1365, %1358
; BB148 :
  %.sroa.136.5 = phi float [ %1372, %1365 ], [ %1364, %1358 ]
  %1374 = extractelement <4 x i8> %1355, i32 2
  %1375 = zext i8 %1374 to i32		; visa id: 1329
  br i1 %1066, label %1383, label %1376, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1330

1376:                                             ; preds = %1373
; BB149 :
  %1377 = and i32 %120, 1073741824
  %1378 = sub nsw i32 0, %1375, !spirv.Decorations !8798
  %1379 = icmp eq i32 %1377, 0		; visa id: 1332
  %1380 = select i1 %1379, i32 %1375, i32 %1378		; visa id: 1334
  %1381 = sitofp i32 %1380 to float		; visa id: 1335
  %1382 = fmul float %1059, %1381		; visa id: 1336
  br label %1391, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1337

1383:                                             ; preds = %1373
; BB150 :
  %1384 = uitofp i32 %1375 to float		; visa id: 1339
  %1385 = fmul float %1059, %1384		; visa id: 1340
  %1386 = and i32 %120, 1073741824
  %1387 = icmp eq i32 %1386, 0		; visa id: 1341
  %1388 = select i1 %1387, i32 1, i32 -1		; visa id: 1343
  %1389 = sitofp i32 %1388 to float		; visa id: 1344
  %1390 = fmul float %1385, %1389		; visa id: 1345
  br label %1391, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1346

1391:                                             ; preds = %1383, %1376
; BB151 :
  %.sroa.160.5 = phi float [ %1390, %1383 ], [ %1382, %1376 ]
  %1392 = lshr i32 %1035, 24		; visa id: 1347
  br i1 %1066, label %1399, label %1393, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1348

1393:                                             ; preds = %1391
; BB152 :
  %1394 = sub nsw i32 0, %1392, !spirv.Decorations !8798
  %1395 = icmp slt i32 %120, 0		; visa id: 1350
  %1396 = select i1 %1395, i32 %1394, i32 %1392		; visa id: 1351
  %1397 = sitofp i32 %1396 to float		; visa id: 1352
  %1398 = fmul float %1059, %1397		; visa id: 1353
  br label %._crit_edge44.3, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1354

1399:                                             ; preds = %1391
; BB153 :
  %1400 = uitofp i32 %1392 to float		; visa id: 1356
  %1401 = fmul float %1059, %1400		; visa id: 1357
  %1402 = icmp sgt i32 %120, -1		; visa id: 1358
  %1403 = select i1 %1402, i32 1, i32 -1		; visa id: 1359
  %1404 = sitofp i32 %1403 to float		; visa id: 1360
  %1405 = fmul float %1401, %1404		; visa id: 1361
  br label %._crit_edge44.3, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1362

._crit_edge44.3:                                  ; preds = %1399, %1393
; BB154 :
  %.sroa.184.5 = phi float [ %1405, %1399 ], [ %1398, %1393 ]
  %1406 = zext i16 %1257 to i32		; visa id: 1363
  %1407 = shl nuw i32 %1406, 16, !spirv.Decorations !8788		; visa id: 1364
  %1408 = bitcast i32 %1407 to float
  %1409 = fmul float %.sroa.067.5, %1408		; visa id: 1365
  %1410 = fadd float %.sroa.28.0, %1409		; visa id: 1366
  %1411 = zext i16 %1258 to i32		; visa id: 1367
  %1412 = shl nuw i32 %1411, 16, !spirv.Decorations !8788		; visa id: 1368
  %1413 = bitcast i32 %1412 to float
  %1414 = fmul float %.sroa.40.5, %1413		; visa id: 1369
  %1415 = fadd float %1410, %1414		; visa id: 1370
  %1416 = zext i16 %1259 to i32		; visa id: 1371
  %1417 = shl nuw i32 %1416, 16, !spirv.Decorations !8788		; visa id: 1372
  %1418 = bitcast i32 %1417 to float
  %1419 = fmul float %.sroa.64.5, %1418		; visa id: 1373
  %1420 = fadd float %1415, %1419		; visa id: 1374
  %1421 = zext i16 %1260 to i32		; visa id: 1375
  %1422 = shl nuw i32 %1421, 16, !spirv.Decorations !8788		; visa id: 1376
  %1423 = bitcast i32 %1422 to float
  %1424 = fmul float %.sroa.88.5, %1423		; visa id: 1377
  %1425 = fadd float %1420, %1424		; visa id: 1378
  %1426 = zext i16 %1263 to i32		; visa id: 1379
  %1427 = shl nuw i32 %1426, 16, !spirv.Decorations !8788		; visa id: 1380
  %1428 = bitcast i32 %1427 to float
  %1429 = fmul float %.sroa.112.5, %1428		; visa id: 1381
  %1430 = fadd float %1425, %1429		; visa id: 1382
  %1431 = zext i16 %1264 to i32		; visa id: 1383
  %1432 = shl nuw i32 %1431, 16, !spirv.Decorations !8788		; visa id: 1384
  %1433 = bitcast i32 %1432 to float
  %1434 = fmul float %.sroa.136.5, %1433		; visa id: 1385
  %1435 = fadd float %1430, %1434		; visa id: 1386
  %1436 = zext i16 %1265 to i32		; visa id: 1387
  %1437 = shl nuw i32 %1436, 16, !spirv.Decorations !8788		; visa id: 1388
  %1438 = bitcast i32 %1437 to float
  %1439 = fmul float %.sroa.160.5, %1438		; visa id: 1389
  %1440 = fadd float %1435, %1439		; visa id: 1390
  %1441 = zext i16 %1266 to i32		; visa id: 1391
  %1442 = shl nuw i32 %1441, 16, !spirv.Decorations !8788		; visa id: 1392
  %1443 = bitcast i32 %1442 to float
  %1444 = fmul float %.sroa.184.5, %1443		; visa id: 1393
  %1445 = fadd float %1440, %1444		; visa id: 1394
  %1446 = and i32 %121, 255
  %1447 = lshr i32 %139, 4		; visa id: 1395
  %1448 = and i32 %1447, 768		; visa id: 1396
  %1449 = or i32 %1446, %1448		; visa id: 1397
  %1450 = shl nuw nsw i32 %1449, 3, !spirv.Decorations !8791		; visa id: 1398
  %1451 = zext i32 %1450 to i64		; visa id: 1399
  %1452 = add i64 %111, %1451		; visa id: 1400
  %1453 = inttoptr i64 %1452 to ptr addrspace(1)		; visa id: 1401
  %1454 = load <2 x i32>, ptr addrspace(1) %1453, align 4		; visa id: 1401
  %1455 = bitcast i32 %121 to <4 x i8>
  %1456 = extractelement <4 x i8> %1455, i32 2
  %1457 = lshr i32 %139, 6		; visa id: 1402
  %1458 = and i32 %1457, 768
  %1459 = zext i8 %1456 to i32		; visa id: 1403
  %1460 = or i32 %1459, %1458		; visa id: 1404
  %1461 = shl nuw nsw i32 %1460, 3, !spirv.Decorations !8791		; visa id: 1405
  %1462 = zext i32 %1461 to i64		; visa id: 1406
  %1463 = add i64 %111, %1462		; visa id: 1407
  %1464 = inttoptr i64 %1463 to ptr addrspace(1)		; visa id: 1408
  %1465 = load <2 x i32>, ptr addrspace(1) %1464, align 4		; visa id: 1408
  %1466 = extractelement <2 x i32> %1454, i32 0		; visa id: 1409
  %1467 = extractelement <2 x i32> %1454, i32 1		; visa id: 1409
  %1468 = extractelement <2 x i32> %1465, i32 0		; visa id: 1409
  %1469 = extractelement <2 x i32> %1465, i32 1		; visa id: 1409
  %1470 = or i32 %169, 96		; visa id: 1409
  %1471 = zext i32 %1470 to i64		; visa id: 1410
  %1472 = add i64 %1471, %const_reg_qword2		; visa id: 1411
  %IntToPtr2368 = inttoptr i64 %1472 to ptr addrspace(1)		; visa id: 1412
  %vCastload369 = load i32, ptr addrspace(1) %IntToPtr2368, align 2		; visa id: 1412
  %1473 = add i64 %1472, 4
  %IntToPtr2370 = inttoptr i64 %1473 to ptr addrspace(1)
  %vCastload371 = load i32, ptr addrspace(1) %IntToPtr2370, align 2		; visa id: 1413
  %1474 = add i64 %1472, 8
  %IntToPtr2372 = inttoptr i64 %1474 to ptr addrspace(1)
  %vCastload373 = load i32, ptr addrspace(1) %IntToPtr2372, align 2		; visa id: 1414
  %1475 = add i64 %1472, 12
  %IntToPtr2374 = inttoptr i64 %1475 to ptr addrspace(1)
  %vCastload375 = load i32, ptr addrspace(1) %IntToPtr2374, align 2		; visa id: 1415
  %1476 = bitcast i32 %vCastload369 to <2 x i16>		; visa id: 1416
  %1477 = bitcast i32 %vCastload371 to <2 x i16>		; visa id: 1418
  %1478 = extractelement <2 x i16> %1476, i32 0		; visa id: 1420
  %1479 = extractelement <2 x i16> %1476, i32 1		; visa id: 1420
  %1480 = extractelement <2 x i16> %1477, i32 0		; visa id: 1420
  %1481 = extractelement <2 x i16> %1477, i32 1		; visa id: 1420
  %1482 = bitcast i32 %vCastload373 to <2 x i16>		; visa id: 1420
  %1483 = bitcast i32 %vCastload375 to <2 x i16>		; visa id: 1422
  %1484 = extractelement <2 x i16> %1482, i32 0		; visa id: 1424
  %1485 = extractelement <2 x i16> %1482, i32 1		; visa id: 1424
  %1486 = extractelement <2 x i16> %1483, i32 0		; visa id: 1424
  %1487 = extractelement <2 x i16> %1483, i32 1		; visa id: 1424
  %1488 = lshr i32 %1054, 4		; visa id: 1424
  %1489 = uitofp i32 %1488 to float		; visa id: 1425
  %1490 = fadd float %1489, 5.000000e-01		; visa id: 1426
  %1491 = fmul float %137, %1490		; visa id: 1427
  %1492 = fmul float %1491, 2.500000e-01		; visa id: 1428
  %1493 = bitcast float %1492 to i32
  %1494 = and i32 %1493, 2147483647		; visa id: 1429
  %1495 = icmp ugt i32 %1494, 2139095040
  %1496 = fcmp oeq float %152, 0x7FF0000000000000		; visa id: 1430
  %1497 = fcmp une float %152, %152
  %1498 = or i1 %1497, %1496		; visa id: 1431
  %1499 = or i1 %1498, %1495		; visa id: 1433
  %1500 = and i32 %1466, 255		; visa id: 1435
  br i1 %1499, label %1508, label %1501, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1436

1501:                                             ; preds = %._crit_edge44.3
; BB155 :
  %1502 = and i32 %121, 256
  %1503 = sub nsw i32 0, %1500, !spirv.Decorations !8798
  %1504 = icmp eq i32 %1502, 0		; visa id: 1438
  %1505 = select i1 %1504, i32 %1500, i32 %1503		; visa id: 1440
  %1506 = sitofp i32 %1505 to float		; visa id: 1441
  %1507 = fmul float %1492, %1506		; visa id: 1442
  br label %1516, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1443

1508:                                             ; preds = %._crit_edge44.3
; BB156 :
  %1509 = uitofp i32 %1500 to float		; visa id: 1445
  %1510 = fmul float %1492, %1509		; visa id: 1446
  %1511 = and i32 %121, 256
  %1512 = icmp eq i32 %1511, 0		; visa id: 1447
  %1513 = select i1 %1512, i32 1, i32 -1		; visa id: 1449
  %1514 = sitofp i32 %1513 to float		; visa id: 1450
  %1515 = fmul float %1510, %1514		; visa id: 1451
  br label %1516, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1452

1516:                                             ; preds = %1508, %1501
; BB157 :
  %.sroa.067.6 = phi float [ %1515, %1508 ], [ %1507, %1501 ]
  %1517 = bitcast i32 %1466 to <4 x i8>
  %1518 = extractelement <4 x i8> %1517, i32 1
  %1519 = zext i8 %1518 to i32		; visa id: 1453
  br i1 %1499, label %1527, label %1520, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1454

1520:                                             ; preds = %1516
; BB158 :
  %1521 = and i32 %121, 512
  %1522 = sub nsw i32 0, %1519, !spirv.Decorations !8798
  %1523 = icmp eq i32 %1521, 0		; visa id: 1456
  %1524 = select i1 %1523, i32 %1519, i32 %1522		; visa id: 1458
  %1525 = sitofp i32 %1524 to float		; visa id: 1459
  %1526 = fmul float %1492, %1525		; visa id: 1460
  br label %1535, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1461

1527:                                             ; preds = %1516
; BB159 :
  %1528 = uitofp i32 %1519 to float		; visa id: 1463
  %1529 = fmul float %1492, %1528		; visa id: 1464
  %1530 = and i32 %121, 512
  %1531 = icmp eq i32 %1530, 0		; visa id: 1465
  %1532 = select i1 %1531, i32 1, i32 -1		; visa id: 1467
  %1533 = sitofp i32 %1532 to float		; visa id: 1468
  %1534 = fmul float %1529, %1533		; visa id: 1469
  br label %1535, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1470

1535:                                             ; preds = %1527, %1520
; BB160 :
  %.sroa.40.6 = phi float [ %1534, %1527 ], [ %1526, %1520 ]
  %1536 = extractelement <4 x i8> %1517, i32 2
  %1537 = zext i8 %1536 to i32		; visa id: 1471
  br i1 %1499, label %1545, label %1538, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1472

1538:                                             ; preds = %1535
; BB161 :
  %1539 = and i32 %121, 1024
  %1540 = sub nsw i32 0, %1537, !spirv.Decorations !8798
  %1541 = icmp eq i32 %1539, 0		; visa id: 1474
  %1542 = select i1 %1541, i32 %1537, i32 %1540		; visa id: 1476
  %1543 = sitofp i32 %1542 to float		; visa id: 1477
  %1544 = fmul float %1492, %1543		; visa id: 1478
  br label %1553, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1479

1545:                                             ; preds = %1535
; BB162 :
  %1546 = uitofp i32 %1537 to float		; visa id: 1481
  %1547 = fmul float %1492, %1546		; visa id: 1482
  %1548 = and i32 %121, 1024
  %1549 = icmp eq i32 %1548, 0		; visa id: 1483
  %1550 = select i1 %1549, i32 1, i32 -1		; visa id: 1485
  %1551 = sitofp i32 %1550 to float		; visa id: 1486
  %1552 = fmul float %1547, %1551		; visa id: 1487
  br label %1553, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1488

1553:                                             ; preds = %1545, %1538
; BB163 :
  %.sroa.64.6 = phi float [ %1552, %1545 ], [ %1544, %1538 ]
  %1554 = lshr i32 %1466, 24		; visa id: 1489
  br i1 %1499, label %1562, label %1555, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1490

1555:                                             ; preds = %1553
; BB164 :
  %1556 = and i32 %121, 2048
  %1557 = sub nsw i32 0, %1554, !spirv.Decorations !8798
  %1558 = icmp eq i32 %1556, 0		; visa id: 1492
  %1559 = select i1 %1558, i32 %1554, i32 %1557		; visa id: 1494
  %1560 = sitofp i32 %1559 to float		; visa id: 1495
  %1561 = fmul float %1492, %1560		; visa id: 1496
  br label %1570, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1497

1562:                                             ; preds = %1553
; BB165 :
  %1563 = uitofp i32 %1554 to float		; visa id: 1499
  %1564 = fmul float %1492, %1563		; visa id: 1500
  %1565 = and i32 %121, 2048
  %1566 = icmp eq i32 %1565, 0		; visa id: 1501
  %1567 = select i1 %1566, i32 1, i32 -1		; visa id: 1503
  %1568 = sitofp i32 %1567 to float		; visa id: 1504
  %1569 = fmul float %1564, %1568		; visa id: 1505
  br label %1570, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1506

1570:                                             ; preds = %1562, %1555
; BB166 :
  %.sroa.88.6 = phi float [ %1569, %1562 ], [ %1561, %1555 ]
  %1571 = and i32 %1467, 255		; visa id: 1507
  br i1 %1499, label %1579, label %1572, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1508

1572:                                             ; preds = %1570
; BB167 :
  %1573 = and i32 %121, 4096
  %1574 = sub nsw i32 0, %1571, !spirv.Decorations !8798
  %1575 = icmp eq i32 %1573, 0		; visa id: 1510
  %1576 = select i1 %1575, i32 %1571, i32 %1574		; visa id: 1512
  %1577 = sitofp i32 %1576 to float		; visa id: 1513
  %1578 = fmul float %1492, %1577		; visa id: 1514
  br label %1587, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1515

1579:                                             ; preds = %1570
; BB168 :
  %1580 = uitofp i32 %1571 to float		; visa id: 1517
  %1581 = fmul float %1492, %1580		; visa id: 1518
  %1582 = and i32 %121, 4096
  %1583 = icmp eq i32 %1582, 0		; visa id: 1519
  %1584 = select i1 %1583, i32 1, i32 -1		; visa id: 1521
  %1585 = sitofp i32 %1584 to float		; visa id: 1522
  %1586 = fmul float %1581, %1585		; visa id: 1523
  br label %1587, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1524

1587:                                             ; preds = %1579, %1572
; BB169 :
  %.sroa.112.6 = phi float [ %1586, %1579 ], [ %1578, %1572 ]
  %1588 = bitcast i32 %1467 to <4 x i8>
  %1589 = extractelement <4 x i8> %1588, i32 1
  %1590 = zext i8 %1589 to i32		; visa id: 1525
  br i1 %1499, label %1598, label %1591, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1526

1591:                                             ; preds = %1587
; BB170 :
  %1592 = and i32 %121, 8192
  %1593 = sub nsw i32 0, %1590, !spirv.Decorations !8798
  %1594 = icmp eq i32 %1592, 0		; visa id: 1528
  %1595 = select i1 %1594, i32 %1590, i32 %1593		; visa id: 1530
  %1596 = sitofp i32 %1595 to float		; visa id: 1531
  %1597 = fmul float %1492, %1596		; visa id: 1532
  br label %1606, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1533

1598:                                             ; preds = %1587
; BB171 :
  %1599 = uitofp i32 %1590 to float		; visa id: 1535
  %1600 = fmul float %1492, %1599		; visa id: 1536
  %1601 = and i32 %121, 8192
  %1602 = icmp eq i32 %1601, 0		; visa id: 1537
  %1603 = select i1 %1602, i32 1, i32 -1		; visa id: 1539
  %1604 = sitofp i32 %1603 to float		; visa id: 1540
  %1605 = fmul float %1600, %1604		; visa id: 1541
  br label %1606, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1542

1606:                                             ; preds = %1598, %1591
; BB172 :
  %.sroa.136.6 = phi float [ %1605, %1598 ], [ %1597, %1591 ]
  %1607 = extractelement <4 x i8> %1588, i32 2
  %1608 = zext i8 %1607 to i32		; visa id: 1543
  br i1 %1499, label %1616, label %1609, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1544

1609:                                             ; preds = %1606
; BB173 :
  %1610 = and i32 %121, 16384
  %1611 = sub nsw i32 0, %1608, !spirv.Decorations !8798
  %1612 = icmp eq i32 %1610, 0		; visa id: 1546
  %1613 = select i1 %1612, i32 %1608, i32 %1611		; visa id: 1548
  %1614 = sitofp i32 %1613 to float		; visa id: 1549
  %1615 = fmul float %1492, %1614		; visa id: 1550
  br label %1624, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1551

1616:                                             ; preds = %1606
; BB174 :
  %1617 = uitofp i32 %1608 to float		; visa id: 1553
  %1618 = fmul float %1492, %1617		; visa id: 1554
  %1619 = and i32 %121, 16384
  %1620 = icmp eq i32 %1619, 0		; visa id: 1555
  %1621 = select i1 %1620, i32 1, i32 -1		; visa id: 1557
  %1622 = sitofp i32 %1621 to float		; visa id: 1558
  %1623 = fmul float %1618, %1622		; visa id: 1559
  br label %1624, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1560

1624:                                             ; preds = %1616, %1609
; BB175 :
  %.sroa.160.6 = phi float [ %1623, %1616 ], [ %1615, %1609 ]
  %1625 = lshr i32 %1467, 24		; visa id: 1561
  br i1 %1499, label %1633, label %1626, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1562

1626:                                             ; preds = %1624
; BB176 :
  %1627 = and i32 %121, 32768
  %1628 = sub nsw i32 0, %1625, !spirv.Decorations !8798
  %1629 = icmp eq i32 %1627, 0		; visa id: 1564
  %1630 = select i1 %1629, i32 %1625, i32 %1628		; visa id: 1566
  %1631 = sitofp i32 %1630 to float		; visa id: 1567
  %1632 = fmul float %1492, %1631		; visa id: 1568
  br label %1641, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1569

1633:                                             ; preds = %1624
; BB177 :
  %1634 = uitofp i32 %1625 to float		; visa id: 1571
  %1635 = fmul float %1492, %1634		; visa id: 1572
  %1636 = and i32 %121, 32768
  %1637 = icmp eq i32 %1636, 0		; visa id: 1573
  %1638 = select i1 %1637, i32 1, i32 -1		; visa id: 1575
  %1639 = sitofp i32 %1638 to float		; visa id: 1576
  %1640 = fmul float %1635, %1639		; visa id: 1577
  br label %1641, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1578

1641:                                             ; preds = %1633, %1626
; BB178 :
  %.sroa.184.6 = phi float [ %1640, %1633 ], [ %1632, %1626 ]
  %1642 = zext i16 %1478 to i32		; visa id: 1579
  %1643 = shl nuw i32 %1642, 16, !spirv.Decorations !8788		; visa id: 1580
  %1644 = bitcast i32 %1643 to float
  %1645 = fmul float %.sroa.067.6, %1644		; visa id: 1581
  %1646 = fadd float %.sroa.31.0, %1645		; visa id: 1582
  %1647 = zext i16 %1479 to i32		; visa id: 1583
  %1648 = shl nuw i32 %1647, 16, !spirv.Decorations !8788		; visa id: 1584
  %1649 = bitcast i32 %1648 to float
  %1650 = fmul float %.sroa.40.6, %1649		; visa id: 1585
  %1651 = fadd float %1646, %1650		; visa id: 1586
  %1652 = zext i16 %1480 to i32		; visa id: 1587
  %1653 = shl nuw i32 %1652, 16, !spirv.Decorations !8788		; visa id: 1588
  %1654 = bitcast i32 %1653 to float
  %1655 = fmul float %.sroa.64.6, %1654		; visa id: 1589
  %1656 = fadd float %1651, %1655		; visa id: 1590
  %1657 = zext i16 %1481 to i32		; visa id: 1591
  %1658 = shl nuw i32 %1657, 16, !spirv.Decorations !8788		; visa id: 1592
  %1659 = bitcast i32 %1658 to float
  %1660 = fmul float %.sroa.88.6, %1659		; visa id: 1593
  %1661 = fadd float %1656, %1660		; visa id: 1594
  %1662 = zext i16 %1484 to i32		; visa id: 1595
  %1663 = shl nuw i32 %1662, 16, !spirv.Decorations !8788		; visa id: 1596
  %1664 = bitcast i32 %1663 to float
  %1665 = fmul float %.sroa.112.6, %1664		; visa id: 1597
  %1666 = fadd float %1661, %1665		; visa id: 1598
  %1667 = zext i16 %1485 to i32		; visa id: 1599
  %1668 = shl nuw i32 %1667, 16, !spirv.Decorations !8788		; visa id: 1600
  %1669 = bitcast i32 %1668 to float
  %1670 = fmul float %.sroa.136.6, %1669		; visa id: 1601
  %1671 = fadd float %1666, %1670		; visa id: 1602
  %1672 = zext i16 %1486 to i32		; visa id: 1603
  %1673 = shl nuw i32 %1672, 16, !spirv.Decorations !8788		; visa id: 1604
  %1674 = bitcast i32 %1673 to float
  %1675 = fmul float %.sroa.160.6, %1674		; visa id: 1605
  %1676 = fadd float %1671, %1675		; visa id: 1606
  %1677 = zext i16 %1487 to i32		; visa id: 1607
  %1678 = shl nuw i32 %1677, 16, !spirv.Decorations !8788		; visa id: 1608
  %1679 = bitcast i32 %1678 to float
  %1680 = fmul float %.sroa.184.6, %1679		; visa id: 1609
  %1681 = fadd float %1676, %1680		; visa id: 1610
  %1682 = or i32 %169, 112		; visa id: 1611
  %1683 = zext i32 %1682 to i64		; visa id: 1612
  %1684 = add i64 %1683, %const_reg_qword2		; visa id: 1613
  %IntToPtr2376 = inttoptr i64 %1684 to ptr addrspace(1)		; visa id: 1614
  %vCastload377 = load i32, ptr addrspace(1) %IntToPtr2376, align 2		; visa id: 1614
  %1685 = add i64 %1684, 4
  %IntToPtr2378 = inttoptr i64 %1685 to ptr addrspace(1)
  %vCastload379 = load i32, ptr addrspace(1) %IntToPtr2378, align 2		; visa id: 1615
  %1686 = add i64 %1684, 8
  %IntToPtr2380 = inttoptr i64 %1686 to ptr addrspace(1)
  %vCastload381 = load i32, ptr addrspace(1) %IntToPtr2380, align 2		; visa id: 1616
  %1687 = add i64 %1684, 12
  %IntToPtr2382 = inttoptr i64 %1687 to ptr addrspace(1)
  %vCastload383 = load i32, ptr addrspace(1) %IntToPtr2382, align 2		; visa id: 1617
  %1688 = bitcast i32 %vCastload377 to <2 x i16>		; visa id: 1618
  %1689 = bitcast i32 %vCastload379 to <2 x i16>		; visa id: 1620
  %1690 = extractelement <2 x i16> %1688, i32 0		; visa id: 1622
  %1691 = extractelement <2 x i16> %1688, i32 1		; visa id: 1622
  %1692 = extractelement <2 x i16> %1689, i32 0		; visa id: 1622
  %1693 = extractelement <2 x i16> %1689, i32 1		; visa id: 1622
  %1694 = bitcast i32 %vCastload381 to <2 x i16>		; visa id: 1622
  %1695 = bitcast i32 %vCastload383 to <2 x i16>		; visa id: 1624
  %1696 = extractelement <2 x i16> %1694, i32 0		; visa id: 1626
  %1697 = extractelement <2 x i16> %1694, i32 1		; visa id: 1626
  %1698 = extractelement <2 x i16> %1695, i32 0		; visa id: 1626
  %1699 = extractelement <2 x i16> %1695, i32 1		; visa id: 1626
  %1700 = and i32 %1468, 255		; visa id: 1626
  br i1 %1499, label %1708, label %1701, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1627

1701:                                             ; preds = %1641
; BB179 :
  %1702 = and i32 %121, 16777216
  %1703 = sub nsw i32 0, %1700, !spirv.Decorations !8798
  %1704 = icmp eq i32 %1702, 0		; visa id: 1629
  %1705 = select i1 %1704, i32 %1700, i32 %1703		; visa id: 1631
  %1706 = sitofp i32 %1705 to float		; visa id: 1632
  %1707 = fmul float %1492, %1706		; visa id: 1633
  br label %1716, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1634

1708:                                             ; preds = %1641
; BB180 :
  %1709 = uitofp i32 %1700 to float		; visa id: 1636
  %1710 = fmul float %1492, %1709		; visa id: 1637
  %1711 = and i32 %121, 16777216
  %1712 = icmp eq i32 %1711, 0		; visa id: 1638
  %1713 = select i1 %1712, i32 1, i32 -1		; visa id: 1640
  %1714 = sitofp i32 %1713 to float		; visa id: 1641
  %1715 = fmul float %1710, %1714		; visa id: 1642
  br label %1716, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1643

1716:                                             ; preds = %1708, %1701
; BB181 :
  %.sroa.067.7 = phi float [ %1715, %1708 ], [ %1707, %1701 ]
  %1717 = bitcast i32 %1468 to <4 x i8>
  %1718 = extractelement <4 x i8> %1717, i32 1
  %1719 = zext i8 %1718 to i32		; visa id: 1644
  br i1 %1499, label %1727, label %1720, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1645

1720:                                             ; preds = %1716
; BB182 :
  %1721 = and i32 %121, 33554432
  %1722 = sub nsw i32 0, %1719, !spirv.Decorations !8798
  %1723 = icmp eq i32 %1721, 0		; visa id: 1647
  %1724 = select i1 %1723, i32 %1719, i32 %1722		; visa id: 1649
  %1725 = sitofp i32 %1724 to float		; visa id: 1650
  %1726 = fmul float %1492, %1725		; visa id: 1651
  br label %1735, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1652

1727:                                             ; preds = %1716
; BB183 :
  %1728 = uitofp i32 %1719 to float		; visa id: 1654
  %1729 = fmul float %1492, %1728		; visa id: 1655
  %1730 = and i32 %121, 33554432
  %1731 = icmp eq i32 %1730, 0		; visa id: 1656
  %1732 = select i1 %1731, i32 1, i32 -1		; visa id: 1658
  %1733 = sitofp i32 %1732 to float		; visa id: 1659
  %1734 = fmul float %1729, %1733		; visa id: 1660
  br label %1735, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1661

1735:                                             ; preds = %1727, %1720
; BB184 :
  %.sroa.40.7 = phi float [ %1734, %1727 ], [ %1726, %1720 ]
  %1736 = extractelement <4 x i8> %1717, i32 2
  %1737 = zext i8 %1736 to i32		; visa id: 1662
  br i1 %1499, label %1745, label %1738, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1663

1738:                                             ; preds = %1735
; BB185 :
  %1739 = and i32 %121, 67108864
  %1740 = sub nsw i32 0, %1737, !spirv.Decorations !8798
  %1741 = icmp eq i32 %1739, 0		; visa id: 1665
  %1742 = select i1 %1741, i32 %1737, i32 %1740		; visa id: 1667
  %1743 = sitofp i32 %1742 to float		; visa id: 1668
  %1744 = fmul float %1492, %1743		; visa id: 1669
  br label %1753, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1670

1745:                                             ; preds = %1735
; BB186 :
  %1746 = uitofp i32 %1737 to float		; visa id: 1672
  %1747 = fmul float %1492, %1746		; visa id: 1673
  %1748 = and i32 %121, 67108864
  %1749 = icmp eq i32 %1748, 0		; visa id: 1674
  %1750 = select i1 %1749, i32 1, i32 -1		; visa id: 1676
  %1751 = sitofp i32 %1750 to float		; visa id: 1677
  %1752 = fmul float %1747, %1751		; visa id: 1678
  br label %1753, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1679

1753:                                             ; preds = %1745, %1738
; BB187 :
  %.sroa.64.7 = phi float [ %1752, %1745 ], [ %1744, %1738 ]
  %1754 = lshr i32 %1468, 24		; visa id: 1680
  br i1 %1499, label %1762, label %1755, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1681

1755:                                             ; preds = %1753
; BB188 :
  %1756 = and i32 %121, 134217728
  %1757 = sub nsw i32 0, %1754, !spirv.Decorations !8798
  %1758 = icmp eq i32 %1756, 0		; visa id: 1683
  %1759 = select i1 %1758, i32 %1754, i32 %1757		; visa id: 1685
  %1760 = sitofp i32 %1759 to float		; visa id: 1686
  %1761 = fmul float %1492, %1760		; visa id: 1687
  br label %1770, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1688

1762:                                             ; preds = %1753
; BB189 :
  %1763 = uitofp i32 %1754 to float		; visa id: 1690
  %1764 = fmul float %1492, %1763		; visa id: 1691
  %1765 = and i32 %121, 134217728
  %1766 = icmp eq i32 %1765, 0		; visa id: 1692
  %1767 = select i1 %1766, i32 1, i32 -1		; visa id: 1694
  %1768 = sitofp i32 %1767 to float		; visa id: 1695
  %1769 = fmul float %1764, %1768		; visa id: 1696
  br label %1770, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1697

1770:                                             ; preds = %1762, %1755
; BB190 :
  %.sroa.88.7 = phi float [ %1769, %1762 ], [ %1761, %1755 ]
  %1771 = and i32 %1469, 255		; visa id: 1698
  br i1 %1499, label %1779, label %1772, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1699

1772:                                             ; preds = %1770
; BB191 :
  %1773 = and i32 %121, 268435456
  %1774 = sub nsw i32 0, %1771, !spirv.Decorations !8798
  %1775 = icmp eq i32 %1773, 0		; visa id: 1701
  %1776 = select i1 %1775, i32 %1771, i32 %1774		; visa id: 1703
  %1777 = sitofp i32 %1776 to float		; visa id: 1704
  %1778 = fmul float %1492, %1777		; visa id: 1705
  br label %1787, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1706

1779:                                             ; preds = %1770
; BB192 :
  %1780 = uitofp i32 %1771 to float		; visa id: 1708
  %1781 = fmul float %1492, %1780		; visa id: 1709
  %1782 = and i32 %121, 268435456
  %1783 = icmp eq i32 %1782, 0		; visa id: 1710
  %1784 = select i1 %1783, i32 1, i32 -1		; visa id: 1712
  %1785 = sitofp i32 %1784 to float		; visa id: 1713
  %1786 = fmul float %1781, %1785		; visa id: 1714
  br label %1787, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1715

1787:                                             ; preds = %1779, %1772
; BB193 :
  %.sroa.112.7 = phi float [ %1786, %1779 ], [ %1778, %1772 ]
  %1788 = bitcast i32 %1469 to <4 x i8>
  %1789 = extractelement <4 x i8> %1788, i32 1
  %1790 = zext i8 %1789 to i32		; visa id: 1716
  br i1 %1499, label %1798, label %1791, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1717

1791:                                             ; preds = %1787
; BB194 :
  %1792 = and i32 %121, 536870912
  %1793 = sub nsw i32 0, %1790, !spirv.Decorations !8798
  %1794 = icmp eq i32 %1792, 0		; visa id: 1719
  %1795 = select i1 %1794, i32 %1790, i32 %1793		; visa id: 1721
  %1796 = sitofp i32 %1795 to float		; visa id: 1722
  %1797 = fmul float %1492, %1796		; visa id: 1723
  br label %1806, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1724

1798:                                             ; preds = %1787
; BB195 :
  %1799 = uitofp i32 %1790 to float		; visa id: 1726
  %1800 = fmul float %1492, %1799		; visa id: 1727
  %1801 = and i32 %121, 536870912
  %1802 = icmp eq i32 %1801, 0		; visa id: 1728
  %1803 = select i1 %1802, i32 1, i32 -1		; visa id: 1730
  %1804 = sitofp i32 %1803 to float		; visa id: 1731
  %1805 = fmul float %1800, %1804		; visa id: 1732
  br label %1806, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1733

1806:                                             ; preds = %1798, %1791
; BB196 :
  %.sroa.136.7 = phi float [ %1805, %1798 ], [ %1797, %1791 ]
  %1807 = extractelement <4 x i8> %1788, i32 2
  %1808 = zext i8 %1807 to i32		; visa id: 1734
  br i1 %1499, label %1816, label %1809, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1735

1809:                                             ; preds = %1806
; BB197 :
  %1810 = and i32 %121, 1073741824
  %1811 = sub nsw i32 0, %1808, !spirv.Decorations !8798
  %1812 = icmp eq i32 %1810, 0		; visa id: 1737
  %1813 = select i1 %1812, i32 %1808, i32 %1811		; visa id: 1739
  %1814 = sitofp i32 %1813 to float		; visa id: 1740
  %1815 = fmul float %1492, %1814		; visa id: 1741
  br label %1824, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1742

1816:                                             ; preds = %1806
; BB198 :
  %1817 = uitofp i32 %1808 to float		; visa id: 1744
  %1818 = fmul float %1492, %1817		; visa id: 1745
  %1819 = and i32 %121, 1073741824
  %1820 = icmp eq i32 %1819, 0		; visa id: 1746
  %1821 = select i1 %1820, i32 1, i32 -1		; visa id: 1748
  %1822 = sitofp i32 %1821 to float		; visa id: 1749
  %1823 = fmul float %1818, %1822		; visa id: 1750
  br label %1824, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1751

1824:                                             ; preds = %1816, %1809
; BB199 :
  %.sroa.160.7 = phi float [ %1823, %1816 ], [ %1815, %1809 ]
  %1825 = lshr i32 %1469, 24		; visa id: 1752
  br i1 %1499, label %1832, label %1826, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1753

1826:                                             ; preds = %1824
; BB200 :
  %1827 = sub nsw i32 0, %1825, !spirv.Decorations !8798
  %1828 = icmp slt i32 %121, 0		; visa id: 1755
  %1829 = select i1 %1828, i32 %1827, i32 %1825		; visa id: 1756
  %1830 = sitofp i32 %1829 to float		; visa id: 1757
  %1831 = fmul float %1492, %1830		; visa id: 1758
  br label %1839, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1759

1832:                                             ; preds = %1824
; BB201 :
  %1833 = uitofp i32 %1825 to float		; visa id: 1761
  %1834 = fmul float %1492, %1833		; visa id: 1762
  %1835 = icmp sgt i32 %121, -1		; visa id: 1763
  %1836 = select i1 %1835, i32 1, i32 -1		; visa id: 1764
  %1837 = sitofp i32 %1836 to float		; visa id: 1765
  %1838 = fmul float %1834, %1837		; visa id: 1766
  br label %1839, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1767

1839:                                             ; preds = %1832, %1826
; BB202 :
  %.sroa.184.7 = phi float [ %1838, %1832 ], [ %1831, %1826 ]
  %1840 = zext i16 %1690 to i32		; visa id: 1768
  %1841 = shl nuw i32 %1840, 16, !spirv.Decorations !8788		; visa id: 1769
  %1842 = bitcast i32 %1841 to float
  %1843 = fmul float %.sroa.067.7, %1842		; visa id: 1770
  %1844 = fadd float %.sroa.36.0, %1843		; visa id: 1771
  %1845 = zext i16 %1691 to i32		; visa id: 1772
  %1846 = shl nuw i32 %1845, 16, !spirv.Decorations !8788		; visa id: 1773
  %1847 = bitcast i32 %1846 to float
  %1848 = fmul float %.sroa.40.7, %1847		; visa id: 1774
  %1849 = fadd float %1844, %1848		; visa id: 1775
  %1850 = zext i16 %1692 to i32		; visa id: 1776
  %1851 = shl nuw i32 %1850, 16, !spirv.Decorations !8788		; visa id: 1777
  %1852 = bitcast i32 %1851 to float
  %1853 = fmul float %.sroa.64.7, %1852		; visa id: 1778
  %1854 = fadd float %1849, %1853		; visa id: 1779
  %1855 = zext i16 %1693 to i32		; visa id: 1780
  %1856 = shl nuw i32 %1855, 16, !spirv.Decorations !8788		; visa id: 1781
  %1857 = bitcast i32 %1856 to float
  %1858 = fmul float %.sroa.88.7, %1857		; visa id: 1782
  %1859 = fadd float %1854, %1858		; visa id: 1783
  %1860 = zext i16 %1696 to i32		; visa id: 1784
  %1861 = shl nuw i32 %1860, 16, !spirv.Decorations !8788		; visa id: 1785
  %1862 = bitcast i32 %1861 to float
  %1863 = fmul float %.sroa.112.7, %1862		; visa id: 1786
  %1864 = fadd float %1859, %1863		; visa id: 1787
  %1865 = zext i16 %1697 to i32		; visa id: 1788
  %1866 = shl nuw i32 %1865, 16, !spirv.Decorations !8788		; visa id: 1789
  %1867 = bitcast i32 %1866 to float
  %1868 = fmul float %.sroa.136.7, %1867		; visa id: 1790
  %1869 = fadd float %1864, %1868		; visa id: 1791
  %1870 = zext i16 %1698 to i32		; visa id: 1792
  %1871 = shl nuw i32 %1870, 16, !spirv.Decorations !8788		; visa id: 1793
  %1872 = bitcast i32 %1871 to float
  %1873 = fmul float %.sroa.160.7, %1872		; visa id: 1794
  %1874 = fadd float %1869, %1873		; visa id: 1795
  %1875 = zext i16 %1699 to i32		; visa id: 1796
  %1876 = shl nuw i32 %1875, 16, !spirv.Decorations !8788		; visa id: 1797
  %1877 = bitcast i32 %1876 to float
  %1878 = fmul float %.sroa.184.7, %1877		; visa id: 1798
  %1879 = fadd float %1874, %1878		; visa id: 1799
  %1880 = icmp ult i32 %112, 9		; visa id: 1800
  br i1 %1880, label %..preheader1.preheader_crit_edge, label %.preheader.preheader, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1801

..preheader1.preheader_crit_edge:                 ; preds = %1839
; BB203 :
  %1881 = add nuw nsw i32 %112, 1, !spirv.Decorations !8791		; visa id: 1803
  br label %.preheader1.preheader, !stats.blockFrequency.digits !8799, !stats.blockFrequency.scale !8797		; visa id: 1804

.preheader.preheader:                             ; preds = %1839
; BB204 :
  %.lcssa390 = phi float [ %1879, %1839 ]
  %.lcssa389 = phi float [ %1681, %1839 ]
  %.lcssa388 = phi float [ %1445, %1839 ]
  %.lcssa387 = phi float [ %1248, %1839 ]
  %.lcssa386 = phi float [ %1011, %1839 ]
  %.lcssa385 = phi float [ %814, %1839 ]
  %.lcssa384 = phi float [ %578, %1839 ]
  %.lcssa = phi float [ %381, %1839 ]
  %1882 = fadd float %.lcssa, %.lcssa384		; visa id: 1806
  %1883 = fadd float %.lcssa385, %.lcssa386		; visa id: 1807
  %1884 = fadd float %.lcssa387, %.lcssa388		; visa id: 1808
  %1885 = fadd float %.lcssa389, %.lcssa390		; visa id: 1809
  %1886 = fadd float %1882, %1883		; visa id: 1810
  %1887 = fadd float %1884, %1885		; visa id: 1811
  %1888 = fadd float %1886, %1887		; visa id: 1812
  br label %._crit_edge, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8790		; visa id: 1815

._crit_edge:                                      ; preds = %.._crit_edge_crit_edge, %precompiled_u32divrem_sp.exit.._crit_edge_crit_edge, %._crit_edge43, %.preheader.preheader
; BB205 :
  %1889 = phi i32 [ -1, %.preheader.preheader ], [ 0, %._crit_edge43 ], [ 0, %precompiled_u32divrem_sp.exit.._crit_edge_crit_edge ], [ 0, %.._crit_edge_crit_edge ]
  %1890 = phi i32 [ 0, %.preheader.preheader ], [ %55, %._crit_edge43 ], [ -1, %precompiled_u32divrem_sp.exit.._crit_edge_crit_edge ], [ -1, %.._crit_edge_crit_edge ]
  %1891 = phi float [ %1888, %.preheader.preheader ], [ 0.000000e+00, %._crit_edge43 ], [ 0.000000e+00, %precompiled_u32divrem_sp.exit.._crit_edge_crit_edge ], [ 0.000000e+00, %.._crit_edge_crit_edge ]
  %1892 = add nuw nsw i32 %simdLaneId, 1		; visa id: 1816
  %1893 = and i32 %1892, 31		; visa id: 1817
  %simdShuffle = call float @llvm.genx.GenISA.WaveShuffleIndex.f32(float %1891, i32 %1893, i32 0)		; visa id: 1818
  %1894 = and i32 %simdLaneId, 1
  %1895 = icmp eq i32 %1894, 0		; visa id: 1825
  %1896 = select i1 %1895, float %simdShuffle, float -0.000000e+00		; visa id: 1827
  %1897 = fadd float %1891, %1896		; visa id: 1828
  %1898 = add nuw nsw i32 %simdLaneId, 2		; visa id: 1829
  %1899 = and i32 %1898, 31		; visa id: 1830
  %simdShuffle.1 = call float @llvm.genx.GenISA.WaveShuffleIndex.f32(float %1897, i32 %1899, i32 0)		; visa id: 1831
  %1900 = icmp ne i32 %4, 0		; visa id: 1838
  %1901 = or i1 %24, %1900		; visa id: 1839
  br i1 %1901, label %._crit_edge.._crit_edge46_crit_edge, label %1902, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8782		; visa id: 1841

._crit_edge.._crit_edge46_crit_edge:              ; preds = %._crit_edge
; BB:
  br label %._crit_edge46, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787

1902:                                             ; preds = %._crit_edge
; BB207 :
  %1903 = icmp eq i32 %4, 0		; visa id: 1843
  %1904 = select i1 %1903, float %simdShuffle.1, float -0.000000e+00		; visa id: 1844
  %1905 = fadd float %1897, %1904		; visa id: 1845
  %1906 = bitcast float %1905 to i32
  %1907 = icmp ne i32 %1889, 0		; visa id: 1846
  %1908 = select i1 %1907, i32 %1906, i32 2143289344		; visa id: 1847
  %1909 = and i32 %1908, 2147483647		; visa id: 1848
  %1910 = icmp ugt i32 %1909, 2139095040		; visa id: 1849
  br i1 %1910, label %1918, label %1911, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 1850

1911:                                             ; preds = %1902
; BB208 :
  %1912 = lshr i32 %1908, 16		; visa id: 1852
  %1913 = and i32 %1912, 1		; visa id: 1853
  %1914 = add i32 %1908, %1913
  %1915 = add i32 %1914, 32767		; visa id: 1854
  %1916 = lshr i32 %1915, 16		; visa id: 1855
  %1917 = trunc i32 %1916 to i16		; visa id: 1856
  br label %1922, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 1857

1918:                                             ; preds = %1902
; BB209 :
  %1919 = lshr i32 %1908, 16		; visa id: 1859
  %1920 = trunc i32 %1919 to i16		; visa id: 1860
  %1921 = or i16 %1920, 64		; visa id: 1861
  br label %1922, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 1862

1922:                                             ; preds = %1911, %1918
; BB210 :
  %1923 = phi i16 [ %1921, %1918 ], [ %1917, %1911 ]
  %1924 = bitcast i64 %const_reg_qword12 to <2 x i32>		; visa id: 1863
  %1925 = extractelement <2 x i32> %1924, i32 0		; visa id: 1864
  %1926 = extractelement <2 x i32> %1924, i32 1		; visa id: 1864
  %1927 = bitcast i64 %const_reg_qword13 to <2 x i32>		; visa id: 1864
  %1928 = extractelement <2 x i32> %1927, i32 0		; visa id: 1865
  %1929 = extractelement <2 x i32> %1927, i32 1		; visa id: 1865
  %1930 = icmp ult i16 %localIdX, 32		; visa id: 1865
  %1931 = select i1 %1930, i32 %1925, i32 %1928		; visa id: 1866
  %1932 = select i1 %1930, i32 %1926, i32 %1929		; visa id: 1867
  %1933 = insertelement <2 x i32> undef, i32 %1931, i32 0		; visa id: 1868
  %1934 = insertelement <2 x i32> %1933, i32 %1932, i32 1		; visa id: 1869
  %1935 = bitcast <2 x i32> %1934 to i64		; visa id: 1870
  %1936 = zext i32 %7 to i64		; visa id: 1874
  %1937 = shl nuw nsw i64 %1936, 1		; visa id: 1875
  %1938 = add i64 %1935, %1937		; visa id: 1876
  %1939 = inttoptr i64 %1938 to ptr addrspace(4)		; visa id: 1877
  %1940 = addrspacecast ptr addrspace(4) %1939 to ptr addrspace(1)		; visa id: 1877
  store i16 %1923, ptr addrspace(1) %1940, align 2		; visa id: 1878
  %1941 = icmp eq i32 %7, %23		; visa id: 1880
  br i1 %1941, label %1942, label %.._crit_edge46_crit_edge, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 1881

.._crit_edge46_crit_edge:                         ; preds = %1922
; BB:
  br label %._crit_edge46, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784

1942:                                             ; preds = %1922
; BB212 :
  %1943 = bitcast i64 %const_reg_qword17 to <2 x i32>		; visa id: 1883
  %1944 = extractelement <2 x i32> %1943, i32 0		; visa id: 1884
  %1945 = extractelement <2 x i32> %1943, i32 1		; visa id: 1884
  %1946 = bitcast i64 %const_reg_qword18 to <2 x i32>		; visa id: 1884
  %1947 = extractelement <2 x i32> %1946, i32 0		; visa id: 1885
  %1948 = extractelement <2 x i32> %1946, i32 1		; visa id: 1885
  %1949 = icmp ne i32 %1890, 0		; visa id: 1885
  %1950 = sext i1 %1949 to i32		; visa id: 1886
  %1951 = sub i32 0, %1950		; visa id: 1887
  %1952 = select i1 %1930, i32 %1944, i32 %1947		; visa id: 1888
  %1953 = select i1 %1930, i32 %1945, i32 %1948		; visa id: 1889
  %1954 = insertelement <2 x i32> undef, i32 %1952, i32 0		; visa id: 1890
  %1955 = insertelement <2 x i32> %1954, i32 %1953, i32 1		; visa id: 1891
  %1956 = bitcast <2 x i32> %1955 to i64		; visa id: 1892
  %1957 = zext i32 %retval.0.i to i64		; visa id: 1896
  %1958 = shl nuw nsw i64 %1957, 2		; visa id: 1897
  %1959 = add i64 %1956, %1958		; visa id: 1898
  %1960 = inttoptr i64 %1959 to ptr addrspace(4)		; visa id: 1899
  %1961 = addrspacecast ptr addrspace(4) %1960 to ptr addrspace(1)		; visa id: 1899
  store i32 %1951, ptr addrspace(1) %1961, align 4		; visa id: 1900
  br i1 %1949, label %1962, label %.._crit_edge46_crit_edge320, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 1901

.._crit_edge46_crit_edge320:                      ; preds = %1942
; BB:
  br label %._crit_edge46, !stats.blockFrequency.digits !8800, !stats.blockFrequency.scale !8801

1962:                                             ; preds = %1942
; BB214 :
  %1963 = inttoptr i64 %const_reg_qword20 to ptr addrspace(4)		; visa id: 1903
  %1964 = addrspacecast ptr addrspace(4) %1963 to ptr addrspace(1)		; visa id: 1903
  %1965 = load i32, ptr addrspace(1) %1964, align 4		; visa id: 1904
  %1966 = icmp eq i32 %1965, 0		; visa id: 1905
  br i1 %1966, label %.._crit_edge46_crit_edge321, label %1967, !stats.blockFrequency.digits !8802, !stats.blockFrequency.scale !8803		; visa id: 1906

.._crit_edge46_crit_edge321:                      ; preds = %1962
; BB:
  br label %._crit_edge46, !stats.blockFrequency.digits !8804, !stats.blockFrequency.scale !8801

1967:                                             ; preds = %1962
; BB216 :
  %1968 = inttoptr i64 %const_reg_qword19 to ptr addrspace(4)		; visa id: 1908
  %1969 = addrspacecast ptr addrspace(4) %1968 to ptr addrspace(1)		; visa id: 1908
  %1970 = call i32 @llvm.genx.GenISA.icmpxchgatomicrawA64.i32.p1.p1(ptr addrspace(1) %1969, ptr addrspace(1) %1969, i32 0, i32 1)		; visa id: 1909
  br label %._crit_edge46, !stats.blockFrequency.digits !8805, !stats.blockFrequency.scale !8801		; visa id: 1914

._crit_edge46:                                    ; preds = %.._crit_edge46_crit_edge321, %.._crit_edge46_crit_edge320, %.._crit_edge46_crit_edge, %._crit_edge.._crit_edge46_crit_edge, %1967
; BB217 :
  ret void, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8782		; visa id: 1915
}
