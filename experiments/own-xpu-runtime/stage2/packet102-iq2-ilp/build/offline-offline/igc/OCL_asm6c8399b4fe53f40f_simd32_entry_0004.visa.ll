; ------------------------------------------------
; OCL_asm6c8399b4fe53f40f_simd32_entry_0004.visa.ll
; ------------------------------------------------
; Function Attrs: convergent nounwind
define spir_kernel void @_ZTSZZNK4p1026KernelILj4ELb0EE6submitERN4sycl3_V15queueESt4spanIKPvLm18446744073709551615EERKSt6vectorINS3_5eventESaISB_EEENKUlRNS3_7handlerEE_clESH_EUlNS3_7nd_itemILi1EEEE_(ptr byval(%"struct.p39::__generated_Bound") align 8 %0, i32 %1, <8 x i32> %r0, <3 x i32> %globalOffset, i16 %localIdX, i16 %localIdY, i16 %localIdZ, ptr addrspace(2) %constBase, ptr addrspace(1) %globalBase, ptr %privateBase, i64 %const_reg_qword, i64 %const_reg_qword1, i64 %const_reg_qword2, i64 %const_reg_qword3, i64 %const_reg_qword4, i64 %const_reg_qword5, i64 %const_reg_qword6, i64 %const_reg_qword7, i64 %const_reg_qword8, i64 %const_reg_qword9, i64 %const_reg_qword10, i64 %const_reg_qword11, i64 %const_reg_qword12, i64 %const_reg_qword13, i64 %const_reg_qword14, i64 %const_reg_qword15, i64 %const_reg_qword16, i64 %const_reg_qword17, i64 %const_reg_qword18, i64 %const_reg_qword19, i64 %const_reg_qword20, i32 %const_reg_dword, i32 %const_reg_dword21, i32 %const_reg_dword22, i32 %const_reg_dword23, i32 %const_reg_dword24, i32 %bindlessOffset, i32 %bindlessOffset25) #0 {
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
  br i1 %53, label %56, label %._crit_edge44, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 84

._crit_edge44:                                    ; preds = %42
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
  %64 = add i64 %63, 128
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
  br label %.preheader2.preheader, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8790		; visa id: 152

.preheader2.preheader:                            ; preds = %.preheader1.3.1..preheader2.preheader_crit_edge, %56
; BB10 :
  %.sroa.36.0 = phi float [ %99, %56 ], [ %1874, %.preheader1.3.1..preheader2.preheader_crit_edge ]
  %.sroa.31.0 = phi float [ %98, %56 ], [ %1677, %.preheader1.3.1..preheader2.preheader_crit_edge ]
  %.sroa.28.0 = phi float [ %97, %56 ], [ %1466, %.preheader1.3.1..preheader2.preheader_crit_edge ]
  %.sroa.21.0 = phi float [ %96, %56 ], [ %1269, %.preheader1.3.1..preheader2.preheader_crit_edge ]
  %.sroa.18.0 = phi float [ %95, %56 ], [ %1009, %.preheader1.3.1..preheader2.preheader_crit_edge ]
  %.sroa.13.0 = phi float [ %94, %56 ], [ %812, %.preheader1.3.1..preheader2.preheader_crit_edge ]
  %.sroa.10.0 = phi float [ %93, %56 ], [ %601, %.preheader1.3.1..preheader2.preheader_crit_edge ]
  %.sroa.0.0 = phi float [ %92, %56 ], [ %404, %.preheader1.3.1..preheader2.preheader_crit_edge ]
  %112 = phi i32 [ 0, %56 ], [ %1876, %.preheader1.3.1..preheader2.preheader_crit_edge ]
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
  %169 = and i32 %119, 255
  %170 = shl nuw nsw i32 %139, 4		; visa id: 194
  %171 = and i32 %170, 768		; visa id: 195
  %172 = or i32 %169, %171		; visa id: 196
  %173 = shl nuw nsw i32 %172, 3, !spirv.Decorations !8791		; visa id: 197
  %174 = zext i32 %173 to i64		; visa id: 198
  %175 = add i64 %111, %174		; visa id: 199
  %176 = inttoptr i64 %175 to ptr addrspace(1)		; visa id: 200
  %177 = load <2 x i32>, ptr addrspace(1) %176, align 4		; visa id: 200
  %178 = extractelement <2 x i32> %168, i32 0		; visa id: 201
  %179 = extractelement <2 x i32> %168, i32 1		; visa id: 201
  %180 = extractelement <2 x i32> %177, i32 0		; visa id: 201
  %181 = extractelement <2 x i32> %177, i32 1		; visa id: 201
  %182 = bitcast i32 %119 to <4 x i8>
  %183 = extractelement <4 x i8> %182, i32 2
  %184 = shl nuw nsw i32 %139, 2		; visa id: 201
  %185 = and i32 %184, 768
  %186 = zext i8 %183 to i32		; visa id: 202
  %187 = or i32 %186, %185		; visa id: 203
  %188 = shl nuw nsw i32 %187, 3, !spirv.Decorations !8791		; visa id: 204
  %189 = zext i32 %188 to i64		; visa id: 205
  %190 = add i64 %111, %189		; visa id: 206
  %191 = inttoptr i64 %190 to ptr addrspace(1)		; visa id: 207
  %192 = load <2 x i32>, ptr addrspace(1) %191, align 4		; visa id: 207
  %193 = shl nuw i32 %149, 1		; visa id: 208
  %194 = zext i32 %193 to i64		; visa id: 209
  %195 = add i64 %194, %const_reg_qword2		; visa id: 210
  %IntToPtr2 = inttoptr i64 %195 to ptr addrspace(1)		; visa id: 211
  %vCastload = load i32, ptr addrspace(1) %IntToPtr2, align 2		; visa id: 211
  %196 = add i64 %195, 4
  %IntToPtr2323 = inttoptr i64 %196 to ptr addrspace(1)
  %vCastload324 = load i32, ptr addrspace(1) %IntToPtr2323, align 2		; visa id: 212
  %197 = extractelement <2 x i32> %192, i32 0		; visa id: 213
  %198 = extractelement <2 x i32> %192, i32 1		; visa id: 213
  %199 = bitcast i32 %vCastload to <2 x i16>		; visa id: 213
  %200 = bitcast i32 %vCastload324 to <2 x i16>		; visa id: 215
  %201 = extractelement <2 x i16> %199, i32 0		; visa id: 217
  %202 = extractelement <2 x i16> %199, i32 1		; visa id: 217
  %203 = extractelement <2 x i16> %200, i32 0		; visa id: 217
  %204 = extractelement <2 x i16> %200, i32 1		; visa id: 217
  %205 = add i64 %195, 8
  %IntToPtr2325 = inttoptr i64 %205 to ptr addrspace(1)
  %vCastload326 = load i32, ptr addrspace(1) %IntToPtr2325, align 2		; visa id: 217
  %206 = add i64 %195, 12
  %IntToPtr2327 = inttoptr i64 %206 to ptr addrspace(1)
  %vCastload328 = load i32, ptr addrspace(1) %IntToPtr2327, align 2		; visa id: 218
  %207 = bitcast i32 %vCastload326 to <2 x i16>		; visa id: 219
  %208 = bitcast i32 %vCastload328 to <2 x i16>		; visa id: 221
  %209 = extractelement <2 x i16> %207, i32 0		; visa id: 223
  %210 = extractelement <2 x i16> %207, i32 1		; visa id: 223
  %211 = extractelement <2 x i16> %208, i32 0		; visa id: 223
  %212 = extractelement <2 x i16> %208, i32 1		; visa id: 223
  %213 = and i16 %131, 255		; visa id: 223
  %214 = zext i16 %213 to i32		; visa id: 224
  %215 = and i32 %214, 15		; visa id: 225
  %216 = uitofp i32 %215 to float		; visa id: 226
  %217 = fadd float %216, 5.000000e-01		; visa id: 227
  %218 = fmul float %137, %217		; visa id: 228
  %219 = fmul float %218, 2.500000e-01		; visa id: 229
  %220 = bitcast float %219 to i32
  %221 = and i32 %220, 2147483647		; visa id: 230
  %222 = icmp ugt i32 %221, 2139095040
  %223 = or i1 %155, %222		; visa id: 231
  %224 = and i32 %156, 255		; visa id: 233
  br i1 %223, label %232, label %225, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 234

225:                                              ; preds = %.preheader2.preheader
; BB11 :
  %226 = and i32 %118, 256
  %227 = sub nsw i32 0, %224, !spirv.Decorations !8798
  %228 = icmp eq i32 %226, 0		; visa id: 236
  %229 = select i1 %228, i32 %224, i32 %227		; visa id: 238
  %230 = sitofp i32 %229 to float		; visa id: 239
  %231 = fmul float %219, %230		; visa id: 240
  br label %240, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 241

232:                                              ; preds = %.preheader2.preheader
; BB12 :
  %233 = uitofp i32 %224 to float		; visa id: 243
  %234 = fmul float %219, %233		; visa id: 244
  %235 = and i32 %118, 256
  %236 = icmp eq i32 %235, 0		; visa id: 245
  %237 = select i1 %236, i32 1, i32 -1		; visa id: 247
  %238 = sitofp i32 %237 to float		; visa id: 248
  %239 = fmul float %234, %238		; visa id: 249
  br label %240, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 250

240:                                              ; preds = %225, %232
; BB13 :
  %.sroa.069.0 = phi float [ %239, %232 ], [ %231, %225 ]
  %241 = bitcast i32 %156 to <4 x i8>
  %242 = extractelement <4 x i8> %241, i32 1
  %243 = zext i8 %242 to i32		; visa id: 251
  br i1 %223, label %251, label %244, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 252

244:                                              ; preds = %240
; BB14 :
  %245 = and i32 %118, 512
  %246 = sub nsw i32 0, %243, !spirv.Decorations !8798
  %247 = icmp eq i32 %245, 0		; visa id: 254
  %248 = select i1 %247, i32 %243, i32 %246		; visa id: 256
  %249 = sitofp i32 %248 to float		; visa id: 257
  %250 = fmul float %219, %249		; visa id: 258
  br label %259, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 259

251:                                              ; preds = %240
; BB15 :
  %252 = uitofp i32 %243 to float		; visa id: 261
  %253 = fmul float %219, %252		; visa id: 262
  %254 = and i32 %118, 512
  %255 = icmp eq i32 %254, 0		; visa id: 263
  %256 = select i1 %255, i32 1, i32 -1		; visa id: 265
  %257 = sitofp i32 %256 to float		; visa id: 266
  %258 = fmul float %253, %257		; visa id: 267
  br label %259, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 268

259:                                              ; preds = %251, %244
; BB16 :
  %.sroa.40.0 = phi float [ %258, %251 ], [ %250, %244 ]
  %260 = extractelement <4 x i8> %241, i32 2
  %261 = zext i8 %260 to i32		; visa id: 269
  br i1 %223, label %269, label %262, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 270

262:                                              ; preds = %259
; BB17 :
  %263 = and i32 %118, 1024
  %264 = sub nsw i32 0, %261, !spirv.Decorations !8798
  %265 = icmp eq i32 %263, 0		; visa id: 272
  %266 = select i1 %265, i32 %261, i32 %264		; visa id: 274
  %267 = sitofp i32 %266 to float		; visa id: 275
  %268 = fmul float %219, %267		; visa id: 276
  br label %277, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 277

269:                                              ; preds = %259
; BB18 :
  %270 = uitofp i32 %261 to float		; visa id: 279
  %271 = fmul float %219, %270		; visa id: 280
  %272 = and i32 %118, 1024
  %273 = icmp eq i32 %272, 0		; visa id: 281
  %274 = select i1 %273, i32 1, i32 -1		; visa id: 283
  %275 = sitofp i32 %274 to float		; visa id: 284
  %276 = fmul float %271, %275		; visa id: 285
  br label %277, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 286

277:                                              ; preds = %269, %262
; BB19 :
  %.sroa.64.0 = phi float [ %276, %269 ], [ %268, %262 ]
  %278 = lshr i32 %156, 24		; visa id: 287
  br i1 %223, label %286, label %279, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 288

279:                                              ; preds = %277
; BB20 :
  %280 = and i32 %118, 2048
  %281 = sub nsw i32 0, %278, !spirv.Decorations !8798
  %282 = icmp eq i32 %280, 0		; visa id: 290
  %283 = select i1 %282, i32 %278, i32 %281		; visa id: 292
  %284 = sitofp i32 %283 to float		; visa id: 293
  %285 = fmul float %219, %284		; visa id: 294
  br label %294, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 295

286:                                              ; preds = %277
; BB21 :
  %287 = uitofp i32 %278 to float		; visa id: 297
  %288 = fmul float %219, %287		; visa id: 298
  %289 = and i32 %118, 2048
  %290 = icmp eq i32 %289, 0		; visa id: 299
  %291 = select i1 %290, i32 1, i32 -1		; visa id: 301
  %292 = sitofp i32 %291 to float		; visa id: 302
  %293 = fmul float %288, %292		; visa id: 303
  br label %294, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 304

294:                                              ; preds = %286, %279
; BB22 :
  %.sroa.88.0 = phi float [ %293, %286 ], [ %285, %279 ]
  %295 = and i32 %157, 255		; visa id: 305
  br i1 %223, label %303, label %296, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 306

296:                                              ; preds = %294
; BB23 :
  %297 = and i32 %118, 4096
  %298 = sub nsw i32 0, %295, !spirv.Decorations !8798
  %299 = icmp eq i32 %297, 0		; visa id: 308
  %300 = select i1 %299, i32 %295, i32 %298		; visa id: 310
  %301 = sitofp i32 %300 to float		; visa id: 311
  %302 = fmul float %219, %301		; visa id: 312
  br label %311, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 313

303:                                              ; preds = %294
; BB24 :
  %304 = uitofp i32 %295 to float		; visa id: 315
  %305 = fmul float %219, %304		; visa id: 316
  %306 = and i32 %118, 4096
  %307 = icmp eq i32 %306, 0		; visa id: 317
  %308 = select i1 %307, i32 1, i32 -1		; visa id: 319
  %309 = sitofp i32 %308 to float		; visa id: 320
  %310 = fmul float %305, %309		; visa id: 321
  br label %311, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 322

311:                                              ; preds = %303, %296
; BB25 :
  %.sroa.112.0 = phi float [ %310, %303 ], [ %302, %296 ]
  %312 = bitcast i32 %157 to <4 x i8>
  %313 = extractelement <4 x i8> %312, i32 1
  %314 = zext i8 %313 to i32		; visa id: 323
  br i1 %223, label %322, label %315, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 324

315:                                              ; preds = %311
; BB26 :
  %316 = and i32 %118, 8192
  %317 = sub nsw i32 0, %314, !spirv.Decorations !8798
  %318 = icmp eq i32 %316, 0		; visa id: 326
  %319 = select i1 %318, i32 %314, i32 %317		; visa id: 328
  %320 = sitofp i32 %319 to float		; visa id: 329
  %321 = fmul float %219, %320		; visa id: 330
  br label %330, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 331

322:                                              ; preds = %311
; BB27 :
  %323 = uitofp i32 %314 to float		; visa id: 333
  %324 = fmul float %219, %323		; visa id: 334
  %325 = and i32 %118, 8192
  %326 = icmp eq i32 %325, 0		; visa id: 335
  %327 = select i1 %326, i32 1, i32 -1		; visa id: 337
  %328 = sitofp i32 %327 to float		; visa id: 338
  %329 = fmul float %324, %328		; visa id: 339
  br label %330, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 340

330:                                              ; preds = %322, %315
; BB28 :
  %.sroa.136.0 = phi float [ %329, %322 ], [ %321, %315 ]
  %331 = extractelement <4 x i8> %312, i32 2
  %332 = zext i8 %331 to i32		; visa id: 341
  br i1 %223, label %340, label %333, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 342

333:                                              ; preds = %330
; BB29 :
  %334 = and i32 %118, 16384
  %335 = sub nsw i32 0, %332, !spirv.Decorations !8798
  %336 = icmp eq i32 %334, 0		; visa id: 344
  %337 = select i1 %336, i32 %332, i32 %335		; visa id: 346
  %338 = sitofp i32 %337 to float		; visa id: 347
  %339 = fmul float %219, %338		; visa id: 348
  br label %348, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 349

340:                                              ; preds = %330
; BB30 :
  %341 = uitofp i32 %332 to float		; visa id: 351
  %342 = fmul float %219, %341		; visa id: 352
  %343 = and i32 %118, 16384
  %344 = icmp eq i32 %343, 0		; visa id: 353
  %345 = select i1 %344, i32 1, i32 -1		; visa id: 355
  %346 = sitofp i32 %345 to float		; visa id: 356
  %347 = fmul float %342, %346		; visa id: 357
  br label %348, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 358

348:                                              ; preds = %340, %333
; BB31 :
  %.sroa.160.0 = phi float [ %347, %340 ], [ %339, %333 ]
  %349 = lshr i32 %157, 24		; visa id: 359
  br i1 %223, label %357, label %350, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 360

350:                                              ; preds = %348
; BB32 :
  %351 = and i32 %118, 32768
  %352 = sub nsw i32 0, %349, !spirv.Decorations !8798
  %353 = icmp eq i32 %351, 0		; visa id: 362
  %354 = select i1 %353, i32 %349, i32 %352		; visa id: 364
  %355 = sitofp i32 %354 to float		; visa id: 365
  %356 = fmul float %219, %355		; visa id: 366
  br label %.preheader1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 367

357:                                              ; preds = %348
; BB33 :
  %358 = uitofp i32 %349 to float		; visa id: 369
  %359 = fmul float %219, %358		; visa id: 370
  %360 = and i32 %118, 32768
  %361 = icmp eq i32 %360, 0		; visa id: 371
  %362 = select i1 %361, i32 1, i32 -1		; visa id: 373
  %363 = sitofp i32 %362 to float		; visa id: 374
  %364 = fmul float %359, %363		; visa id: 375
  br label %.preheader1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 376

.preheader1:                                      ; preds = %357, %350
; BB34 :
  %.sroa.184.0 = phi float [ %364, %357 ], [ %356, %350 ]
  %365 = zext i16 %201 to i32		; visa id: 377
  %366 = shl nuw i32 %365, 16, !spirv.Decorations !8788		; visa id: 378
  %367 = bitcast i32 %366 to float
  %368 = fmul float %.sroa.069.0, %367		; visa id: 379
  %369 = fadd float %.sroa.0.0, %368		; visa id: 380
  %370 = zext i16 %202 to i32		; visa id: 381
  %371 = shl nuw i32 %370, 16, !spirv.Decorations !8788		; visa id: 382
  %372 = bitcast i32 %371 to float
  %373 = fmul float %.sroa.40.0, %372		; visa id: 383
  %374 = fadd float %369, %373		; visa id: 384
  %375 = zext i16 %203 to i32		; visa id: 385
  %376 = shl nuw i32 %375, 16, !spirv.Decorations !8788		; visa id: 386
  %377 = bitcast i32 %376 to float
  %378 = fmul float %.sroa.64.0, %377		; visa id: 387
  %379 = fadd float %374, %378		; visa id: 388
  %380 = zext i16 %204 to i32		; visa id: 389
  %381 = shl nuw i32 %380, 16, !spirv.Decorations !8788		; visa id: 390
  %382 = bitcast i32 %381 to float
  %383 = fmul float %.sroa.88.0, %382		; visa id: 391
  %384 = fadd float %379, %383		; visa id: 392
  %385 = zext i16 %209 to i32		; visa id: 393
  %386 = shl nuw i32 %385, 16, !spirv.Decorations !8788		; visa id: 394
  %387 = bitcast i32 %386 to float
  %388 = fmul float %.sroa.112.0, %387		; visa id: 395
  %389 = fadd float %384, %388		; visa id: 396
  %390 = zext i16 %210 to i32		; visa id: 397
  %391 = shl nuw i32 %390, 16, !spirv.Decorations !8788		; visa id: 398
  %392 = bitcast i32 %391 to float
  %393 = fmul float %.sroa.136.0, %392		; visa id: 399
  %394 = fadd float %389, %393		; visa id: 400
  %395 = zext i16 %211 to i32		; visa id: 401
  %396 = shl nuw i32 %395, 16, !spirv.Decorations !8788		; visa id: 402
  %397 = bitcast i32 %396 to float
  %398 = fmul float %.sroa.160.0, %397		; visa id: 403
  %399 = fadd float %394, %398		; visa id: 404
  %400 = zext i16 %212 to i32		; visa id: 405
  %401 = shl nuw i32 %400, 16, !spirv.Decorations !8788		; visa id: 406
  %402 = bitcast i32 %401 to float
  %403 = fmul float %.sroa.184.0, %402		; visa id: 407
  %404 = fadd float %399, %403		; visa id: 408
  %405 = or i32 %193, 16		; visa id: 409
  %406 = zext i32 %405 to i64		; visa id: 410
  %407 = add i64 %406, %const_reg_qword2		; visa id: 411
  %IntToPtr2329 = inttoptr i64 %407 to ptr addrspace(1)		; visa id: 412
  %vCastload330 = load i32, ptr addrspace(1) %IntToPtr2329, align 2		; visa id: 412
  %408 = add i64 %407, 4
  %IntToPtr2331 = inttoptr i64 %408 to ptr addrspace(1)
  %vCastload332 = load i32, ptr addrspace(1) %IntToPtr2331, align 2		; visa id: 413
  %409 = add i64 %407, 8
  %IntToPtr2333 = inttoptr i64 %409 to ptr addrspace(1)
  %vCastload334 = load i32, ptr addrspace(1) %IntToPtr2333, align 2		; visa id: 414
  %410 = add i64 %407, 12
  %IntToPtr2335 = inttoptr i64 %410 to ptr addrspace(1)
  %vCastload336 = load i32, ptr addrspace(1) %IntToPtr2335, align 2		; visa id: 415
  %411 = bitcast i32 %vCastload330 to <2 x i16>		; visa id: 416
  %412 = bitcast i32 %vCastload332 to <2 x i16>		; visa id: 418
  %413 = extractelement <2 x i16> %411, i32 0		; visa id: 420
  %414 = extractelement <2 x i16> %411, i32 1		; visa id: 420
  %415 = extractelement <2 x i16> %412, i32 0		; visa id: 420
  %416 = extractelement <2 x i16> %412, i32 1		; visa id: 420
  %417 = bitcast i32 %vCastload334 to <2 x i16>		; visa id: 420
  %418 = bitcast i32 %vCastload336 to <2 x i16>		; visa id: 422
  %419 = extractelement <2 x i16> %417, i32 0		; visa id: 424
  %420 = extractelement <2 x i16> %417, i32 1		; visa id: 424
  %421 = extractelement <2 x i16> %418, i32 0		; visa id: 424
  %422 = extractelement <2 x i16> %418, i32 1		; visa id: 424
  %423 = and i32 %178, 255		; visa id: 424
  br i1 %223, label %431, label %424, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 425

424:                                              ; preds = %.preheader1
; BB35 :
  %425 = and i32 %118, 16777216
  %426 = sub nsw i32 0, %423, !spirv.Decorations !8798
  %427 = icmp eq i32 %425, 0		; visa id: 427
  %428 = select i1 %427, i32 %423, i32 %426		; visa id: 429
  %429 = sitofp i32 %428 to float		; visa id: 430
  %430 = fmul float %219, %429		; visa id: 431
  br label %439, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 432

431:                                              ; preds = %.preheader1
; BB36 :
  %432 = uitofp i32 %423 to float		; visa id: 434
  %433 = fmul float %219, %432		; visa id: 435
  %434 = and i32 %118, 16777216
  %435 = icmp eq i32 %434, 0		; visa id: 436
  %436 = select i1 %435, i32 1, i32 -1		; visa id: 438
  %437 = sitofp i32 %436 to float		; visa id: 439
  %438 = fmul float %433, %437		; visa id: 440
  br label %439, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 441

439:                                              ; preds = %431, %424
; BB37 :
  %.sroa.069.1 = phi float [ %438, %431 ], [ %430, %424 ]
  %440 = bitcast i32 %178 to <4 x i8>
  %441 = extractelement <4 x i8> %440, i32 1
  %442 = zext i8 %441 to i32		; visa id: 442
  br i1 %223, label %450, label %443, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 443

443:                                              ; preds = %439
; BB38 :
  %444 = and i32 %118, 33554432
  %445 = sub nsw i32 0, %442, !spirv.Decorations !8798
  %446 = icmp eq i32 %444, 0		; visa id: 445
  %447 = select i1 %446, i32 %442, i32 %445		; visa id: 447
  %448 = sitofp i32 %447 to float		; visa id: 448
  %449 = fmul float %219, %448		; visa id: 449
  br label %458, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 450

450:                                              ; preds = %439
; BB39 :
  %451 = uitofp i32 %442 to float		; visa id: 452
  %452 = fmul float %219, %451		; visa id: 453
  %453 = and i32 %118, 33554432
  %454 = icmp eq i32 %453, 0		; visa id: 454
  %455 = select i1 %454, i32 1, i32 -1		; visa id: 456
  %456 = sitofp i32 %455 to float		; visa id: 457
  %457 = fmul float %452, %456		; visa id: 458
  br label %458, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 459

458:                                              ; preds = %450, %443
; BB40 :
  %.sroa.40.1 = phi float [ %457, %450 ], [ %449, %443 ]
  %459 = extractelement <4 x i8> %440, i32 2
  %460 = zext i8 %459 to i32		; visa id: 460
  br i1 %223, label %468, label %461, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 461

461:                                              ; preds = %458
; BB41 :
  %462 = and i32 %118, 67108864
  %463 = sub nsw i32 0, %460, !spirv.Decorations !8798
  %464 = icmp eq i32 %462, 0		; visa id: 463
  %465 = select i1 %464, i32 %460, i32 %463		; visa id: 465
  %466 = sitofp i32 %465 to float		; visa id: 466
  %467 = fmul float %219, %466		; visa id: 467
  br label %476, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 468

468:                                              ; preds = %458
; BB42 :
  %469 = uitofp i32 %460 to float		; visa id: 470
  %470 = fmul float %219, %469		; visa id: 471
  %471 = and i32 %118, 67108864
  %472 = icmp eq i32 %471, 0		; visa id: 472
  %473 = select i1 %472, i32 1, i32 -1		; visa id: 474
  %474 = sitofp i32 %473 to float		; visa id: 475
  %475 = fmul float %470, %474		; visa id: 476
  br label %476, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 477

476:                                              ; preds = %468, %461
; BB43 :
  %.sroa.64.1 = phi float [ %475, %468 ], [ %467, %461 ]
  %477 = lshr i32 %178, 24		; visa id: 478
  br i1 %223, label %485, label %478, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 479

478:                                              ; preds = %476
; BB44 :
  %479 = and i32 %118, 134217728
  %480 = sub nsw i32 0, %477, !spirv.Decorations !8798
  %481 = icmp eq i32 %479, 0		; visa id: 481
  %482 = select i1 %481, i32 %477, i32 %480		; visa id: 483
  %483 = sitofp i32 %482 to float		; visa id: 484
  %484 = fmul float %219, %483		; visa id: 485
  br label %493, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 486

485:                                              ; preds = %476
; BB45 :
  %486 = uitofp i32 %477 to float		; visa id: 488
  %487 = fmul float %219, %486		; visa id: 489
  %488 = and i32 %118, 134217728
  %489 = icmp eq i32 %488, 0		; visa id: 490
  %490 = select i1 %489, i32 1, i32 -1		; visa id: 492
  %491 = sitofp i32 %490 to float		; visa id: 493
  %492 = fmul float %487, %491		; visa id: 494
  br label %493, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 495

493:                                              ; preds = %485, %478
; BB46 :
  %.sroa.88.1 = phi float [ %492, %485 ], [ %484, %478 ]
  %494 = and i32 %179, 255		; visa id: 496
  br i1 %223, label %502, label %495, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 497

495:                                              ; preds = %493
; BB47 :
  %496 = and i32 %118, 268435456
  %497 = sub nsw i32 0, %494, !spirv.Decorations !8798
  %498 = icmp eq i32 %496, 0		; visa id: 499
  %499 = select i1 %498, i32 %494, i32 %497		; visa id: 501
  %500 = sitofp i32 %499 to float		; visa id: 502
  %501 = fmul float %219, %500		; visa id: 503
  br label %510, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 504

502:                                              ; preds = %493
; BB48 :
  %503 = uitofp i32 %494 to float		; visa id: 506
  %504 = fmul float %219, %503		; visa id: 507
  %505 = and i32 %118, 268435456
  %506 = icmp eq i32 %505, 0		; visa id: 508
  %507 = select i1 %506, i32 1, i32 -1		; visa id: 510
  %508 = sitofp i32 %507 to float		; visa id: 511
  %509 = fmul float %504, %508		; visa id: 512
  br label %510, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 513

510:                                              ; preds = %502, %495
; BB49 :
  %.sroa.112.1 = phi float [ %509, %502 ], [ %501, %495 ]
  %511 = bitcast i32 %179 to <4 x i8>
  %512 = extractelement <4 x i8> %511, i32 1
  %513 = zext i8 %512 to i32		; visa id: 514
  br i1 %223, label %521, label %514, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 515

514:                                              ; preds = %510
; BB50 :
  %515 = and i32 %118, 536870912
  %516 = sub nsw i32 0, %513, !spirv.Decorations !8798
  %517 = icmp eq i32 %515, 0		; visa id: 517
  %518 = select i1 %517, i32 %513, i32 %516		; visa id: 519
  %519 = sitofp i32 %518 to float		; visa id: 520
  %520 = fmul float %219, %519		; visa id: 521
  br label %529, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 522

521:                                              ; preds = %510
; BB51 :
  %522 = uitofp i32 %513 to float		; visa id: 524
  %523 = fmul float %219, %522		; visa id: 525
  %524 = and i32 %118, 536870912
  %525 = icmp eq i32 %524, 0		; visa id: 526
  %526 = select i1 %525, i32 1, i32 -1		; visa id: 528
  %527 = sitofp i32 %526 to float		; visa id: 529
  %528 = fmul float %523, %527		; visa id: 530
  br label %529, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 531

529:                                              ; preds = %521, %514
; BB52 :
  %.sroa.136.1 = phi float [ %528, %521 ], [ %520, %514 ]
  %530 = extractelement <4 x i8> %511, i32 2
  %531 = zext i8 %530 to i32		; visa id: 532
  br i1 %223, label %539, label %532, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 533

532:                                              ; preds = %529
; BB53 :
  %533 = and i32 %118, 1073741824
  %534 = sub nsw i32 0, %531, !spirv.Decorations !8798
  %535 = icmp eq i32 %533, 0		; visa id: 535
  %536 = select i1 %535, i32 %531, i32 %534		; visa id: 537
  %537 = sitofp i32 %536 to float		; visa id: 538
  %538 = fmul float %219, %537		; visa id: 539
  br label %547, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 540

539:                                              ; preds = %529
; BB54 :
  %540 = uitofp i32 %531 to float		; visa id: 542
  %541 = fmul float %219, %540		; visa id: 543
  %542 = and i32 %118, 1073741824
  %543 = icmp eq i32 %542, 0		; visa id: 544
  %544 = select i1 %543, i32 1, i32 -1		; visa id: 546
  %545 = sitofp i32 %544 to float		; visa id: 547
  %546 = fmul float %541, %545		; visa id: 548
  br label %547, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 549

547:                                              ; preds = %539, %532
; BB55 :
  %.sroa.160.1 = phi float [ %546, %539 ], [ %538, %532 ]
  %548 = lshr i32 %179, 24		; visa id: 550
  br i1 %223, label %555, label %549, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 551

549:                                              ; preds = %547
; BB56 :
  %550 = sub nsw i32 0, %548, !spirv.Decorations !8798
  %551 = icmp slt i32 %118, 0		; visa id: 553
  %552 = select i1 %551, i32 %550, i32 %548		; visa id: 554
  %553 = sitofp i32 %552 to float		; visa id: 555
  %554 = fmul float %219, %553		; visa id: 556
  br label %.preheader1.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 557

555:                                              ; preds = %547
; BB57 :
  %556 = uitofp i32 %548 to float		; visa id: 559
  %557 = fmul float %219, %556		; visa id: 560
  %558 = icmp sgt i32 %118, -1		; visa id: 561
  %559 = select i1 %558, i32 1, i32 -1		; visa id: 562
  %560 = sitofp i32 %559 to float		; visa id: 563
  %561 = fmul float %557, %560		; visa id: 564
  br label %.preheader1.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 565

.preheader1.1:                                    ; preds = %555, %549
; BB58 :
  %.sroa.184.1 = phi float [ %561, %555 ], [ %554, %549 ]
  %562 = zext i16 %413 to i32		; visa id: 566
  %563 = shl nuw i32 %562, 16, !spirv.Decorations !8788		; visa id: 567
  %564 = bitcast i32 %563 to float
  %565 = fmul float %.sroa.069.1, %564		; visa id: 568
  %566 = fadd float %.sroa.10.0, %565		; visa id: 569
  %567 = zext i16 %414 to i32		; visa id: 570
  %568 = shl nuw i32 %567, 16, !spirv.Decorations !8788		; visa id: 571
  %569 = bitcast i32 %568 to float
  %570 = fmul float %.sroa.40.1, %569		; visa id: 572
  %571 = fadd float %566, %570		; visa id: 573
  %572 = zext i16 %415 to i32		; visa id: 574
  %573 = shl nuw i32 %572, 16, !spirv.Decorations !8788		; visa id: 575
  %574 = bitcast i32 %573 to float
  %575 = fmul float %.sroa.64.1, %574		; visa id: 576
  %576 = fadd float %571, %575		; visa id: 577
  %577 = zext i16 %416 to i32		; visa id: 578
  %578 = shl nuw i32 %577, 16, !spirv.Decorations !8788		; visa id: 579
  %579 = bitcast i32 %578 to float
  %580 = fmul float %.sroa.88.1, %579		; visa id: 580
  %581 = fadd float %576, %580		; visa id: 581
  %582 = zext i16 %419 to i32		; visa id: 582
  %583 = shl nuw i32 %582, 16, !spirv.Decorations !8788		; visa id: 583
  %584 = bitcast i32 %583 to float
  %585 = fmul float %.sroa.112.1, %584		; visa id: 584
  %586 = fadd float %581, %585		; visa id: 585
  %587 = zext i16 %420 to i32		; visa id: 586
  %588 = shl nuw i32 %587, 16, !spirv.Decorations !8788		; visa id: 587
  %589 = bitcast i32 %588 to float
  %590 = fmul float %.sroa.136.1, %589		; visa id: 588
  %591 = fadd float %586, %590		; visa id: 589
  %592 = zext i16 %421 to i32		; visa id: 590
  %593 = shl nuw i32 %592, 16, !spirv.Decorations !8788		; visa id: 591
  %594 = bitcast i32 %593 to float
  %595 = fmul float %.sroa.160.1, %594		; visa id: 592
  %596 = fadd float %591, %595		; visa id: 593
  %597 = zext i16 %422 to i32		; visa id: 594
  %598 = shl nuw i32 %597, 16, !spirv.Decorations !8788		; visa id: 595
  %599 = bitcast i32 %598 to float
  %600 = fmul float %.sroa.184.1, %599		; visa id: 596
  %601 = fadd float %596, %600		; visa id: 597
  %602 = or i32 %193, 32		; visa id: 598
  %603 = zext i32 %602 to i64		; visa id: 599
  %604 = add i64 %603, %const_reg_qword2		; visa id: 600
  %IntToPtr2337 = inttoptr i64 %604 to ptr addrspace(1)		; visa id: 601
  %vCastload338 = load i32, ptr addrspace(1) %IntToPtr2337, align 2		; visa id: 601
  %605 = add i64 %604, 4
  %IntToPtr2339 = inttoptr i64 %605 to ptr addrspace(1)
  %vCastload340 = load i32, ptr addrspace(1) %IntToPtr2339, align 2		; visa id: 602
  %606 = add i64 %604, 8
  %IntToPtr2341 = inttoptr i64 %606 to ptr addrspace(1)
  %vCastload342 = load i32, ptr addrspace(1) %IntToPtr2341, align 2		; visa id: 603
  %607 = add i64 %604, 12
  %IntToPtr2343 = inttoptr i64 %607 to ptr addrspace(1)
  %vCastload344 = load i32, ptr addrspace(1) %IntToPtr2343, align 2		; visa id: 604
  %608 = bitcast i32 %vCastload338 to <2 x i16>		; visa id: 605
  %609 = bitcast i32 %vCastload340 to <2 x i16>		; visa id: 607
  %610 = extractelement <2 x i16> %608, i32 0		; visa id: 609
  %611 = extractelement <2 x i16> %608, i32 1		; visa id: 609
  %612 = extractelement <2 x i16> %609, i32 0		; visa id: 609
  %613 = extractelement <2 x i16> %609, i32 1		; visa id: 609
  %614 = bitcast i32 %vCastload342 to <2 x i16>		; visa id: 609
  %615 = bitcast i32 %vCastload344 to <2 x i16>		; visa id: 611
  %616 = extractelement <2 x i16> %614, i32 0		; visa id: 613
  %617 = extractelement <2 x i16> %614, i32 1		; visa id: 613
  %618 = extractelement <2 x i16> %615, i32 0		; visa id: 613
  %619 = extractelement <2 x i16> %615, i32 1		; visa id: 613
  %620 = lshr i32 %214, 4		; visa id: 613
  %621 = uitofp i32 %620 to float		; visa id: 614
  %622 = fadd float %621, 5.000000e-01		; visa id: 615
  %623 = fmul float %137, %622		; visa id: 616
  %624 = fmul float %623, 2.500000e-01		; visa id: 617
  %625 = bitcast float %624 to i32
  %626 = and i32 %625, 2147483647		; visa id: 618
  %627 = icmp ugt i32 %626, 2139095040
  %628 = fcmp oeq float %152, 0x7FF0000000000000		; visa id: 619
  %629 = fcmp une float %152, %152
  %630 = or i1 %629, %628		; visa id: 620
  %631 = or i1 %630, %627		; visa id: 622
  %632 = and i32 %180, 255		; visa id: 624
  br i1 %631, label %640, label %633, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 625

633:                                              ; preds = %.preheader1.1
; BB59 :
  %634 = and i32 %119, 256
  %635 = sub nsw i32 0, %632, !spirv.Decorations !8798
  %636 = icmp eq i32 %634, 0		; visa id: 627
  %637 = select i1 %636, i32 %632, i32 %635		; visa id: 629
  %638 = sitofp i32 %637 to float		; visa id: 630
  %639 = fmul float %624, %638		; visa id: 631
  br label %648, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 632

640:                                              ; preds = %.preheader1.1
; BB60 :
  %641 = uitofp i32 %632 to float		; visa id: 634
  %642 = fmul float %624, %641		; visa id: 635
  %643 = and i32 %119, 256
  %644 = icmp eq i32 %643, 0		; visa id: 636
  %645 = select i1 %644, i32 1, i32 -1		; visa id: 638
  %646 = sitofp i32 %645 to float		; visa id: 639
  %647 = fmul float %642, %646		; visa id: 640
  br label %648, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 641

648:                                              ; preds = %640, %633
; BB61 :
  %.sroa.069.2 = phi float [ %647, %640 ], [ %639, %633 ]
  %649 = bitcast i32 %180 to <4 x i8>
  %650 = extractelement <4 x i8> %649, i32 1
  %651 = zext i8 %650 to i32		; visa id: 642
  br i1 %631, label %659, label %652, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 643

652:                                              ; preds = %648
; BB62 :
  %653 = and i32 %119, 512
  %654 = sub nsw i32 0, %651, !spirv.Decorations !8798
  %655 = icmp eq i32 %653, 0		; visa id: 645
  %656 = select i1 %655, i32 %651, i32 %654		; visa id: 647
  %657 = sitofp i32 %656 to float		; visa id: 648
  %658 = fmul float %624, %657		; visa id: 649
  br label %667, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 650

659:                                              ; preds = %648
; BB63 :
  %660 = uitofp i32 %651 to float		; visa id: 652
  %661 = fmul float %624, %660		; visa id: 653
  %662 = and i32 %119, 512
  %663 = icmp eq i32 %662, 0		; visa id: 654
  %664 = select i1 %663, i32 1, i32 -1		; visa id: 656
  %665 = sitofp i32 %664 to float		; visa id: 657
  %666 = fmul float %661, %665		; visa id: 658
  br label %667, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 659

667:                                              ; preds = %659, %652
; BB64 :
  %.sroa.40.2 = phi float [ %666, %659 ], [ %658, %652 ]
  %668 = extractelement <4 x i8> %649, i32 2
  %669 = zext i8 %668 to i32		; visa id: 660
  br i1 %631, label %677, label %670, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 661

670:                                              ; preds = %667
; BB65 :
  %671 = and i32 %119, 1024
  %672 = sub nsw i32 0, %669, !spirv.Decorations !8798
  %673 = icmp eq i32 %671, 0		; visa id: 663
  %674 = select i1 %673, i32 %669, i32 %672		; visa id: 665
  %675 = sitofp i32 %674 to float		; visa id: 666
  %676 = fmul float %624, %675		; visa id: 667
  br label %685, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 668

677:                                              ; preds = %667
; BB66 :
  %678 = uitofp i32 %669 to float		; visa id: 670
  %679 = fmul float %624, %678		; visa id: 671
  %680 = and i32 %119, 1024
  %681 = icmp eq i32 %680, 0		; visa id: 672
  %682 = select i1 %681, i32 1, i32 -1		; visa id: 674
  %683 = sitofp i32 %682 to float		; visa id: 675
  %684 = fmul float %679, %683		; visa id: 676
  br label %685, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 677

685:                                              ; preds = %677, %670
; BB67 :
  %.sroa.64.2 = phi float [ %684, %677 ], [ %676, %670 ]
  %686 = lshr i32 %180, 24		; visa id: 678
  br i1 %631, label %694, label %687, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 679

687:                                              ; preds = %685
; BB68 :
  %688 = and i32 %119, 2048
  %689 = sub nsw i32 0, %686, !spirv.Decorations !8798
  %690 = icmp eq i32 %688, 0		; visa id: 681
  %691 = select i1 %690, i32 %686, i32 %689		; visa id: 683
  %692 = sitofp i32 %691 to float		; visa id: 684
  %693 = fmul float %624, %692		; visa id: 685
  br label %702, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 686

694:                                              ; preds = %685
; BB69 :
  %695 = uitofp i32 %686 to float		; visa id: 688
  %696 = fmul float %624, %695		; visa id: 689
  %697 = and i32 %119, 2048
  %698 = icmp eq i32 %697, 0		; visa id: 690
  %699 = select i1 %698, i32 1, i32 -1		; visa id: 692
  %700 = sitofp i32 %699 to float		; visa id: 693
  %701 = fmul float %696, %700		; visa id: 694
  br label %702, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 695

702:                                              ; preds = %694, %687
; BB70 :
  %.sroa.88.2 = phi float [ %701, %694 ], [ %693, %687 ]
  %703 = and i32 %181, 255		; visa id: 696
  br i1 %631, label %711, label %704, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 697

704:                                              ; preds = %702
; BB71 :
  %705 = and i32 %119, 4096
  %706 = sub nsw i32 0, %703, !spirv.Decorations !8798
  %707 = icmp eq i32 %705, 0		; visa id: 699
  %708 = select i1 %707, i32 %703, i32 %706		; visa id: 701
  %709 = sitofp i32 %708 to float		; visa id: 702
  %710 = fmul float %624, %709		; visa id: 703
  br label %719, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 704

711:                                              ; preds = %702
; BB72 :
  %712 = uitofp i32 %703 to float		; visa id: 706
  %713 = fmul float %624, %712		; visa id: 707
  %714 = and i32 %119, 4096
  %715 = icmp eq i32 %714, 0		; visa id: 708
  %716 = select i1 %715, i32 1, i32 -1		; visa id: 710
  %717 = sitofp i32 %716 to float		; visa id: 711
  %718 = fmul float %713, %717		; visa id: 712
  br label %719, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 713

719:                                              ; preds = %711, %704
; BB73 :
  %.sroa.112.2 = phi float [ %718, %711 ], [ %710, %704 ]
  %720 = bitcast i32 %181 to <4 x i8>
  %721 = extractelement <4 x i8> %720, i32 1
  %722 = zext i8 %721 to i32		; visa id: 714
  br i1 %631, label %730, label %723, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 715

723:                                              ; preds = %719
; BB74 :
  %724 = and i32 %119, 8192
  %725 = sub nsw i32 0, %722, !spirv.Decorations !8798
  %726 = icmp eq i32 %724, 0		; visa id: 717
  %727 = select i1 %726, i32 %722, i32 %725		; visa id: 719
  %728 = sitofp i32 %727 to float		; visa id: 720
  %729 = fmul float %624, %728		; visa id: 721
  br label %738, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 722

730:                                              ; preds = %719
; BB75 :
  %731 = uitofp i32 %722 to float		; visa id: 724
  %732 = fmul float %624, %731		; visa id: 725
  %733 = and i32 %119, 8192
  %734 = icmp eq i32 %733, 0		; visa id: 726
  %735 = select i1 %734, i32 1, i32 -1		; visa id: 728
  %736 = sitofp i32 %735 to float		; visa id: 729
  %737 = fmul float %732, %736		; visa id: 730
  br label %738, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 731

738:                                              ; preds = %730, %723
; BB76 :
  %.sroa.136.2 = phi float [ %737, %730 ], [ %729, %723 ]
  %739 = extractelement <4 x i8> %720, i32 2
  %740 = zext i8 %739 to i32		; visa id: 732
  br i1 %631, label %748, label %741, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 733

741:                                              ; preds = %738
; BB77 :
  %742 = and i32 %119, 16384
  %743 = sub nsw i32 0, %740, !spirv.Decorations !8798
  %744 = icmp eq i32 %742, 0		; visa id: 735
  %745 = select i1 %744, i32 %740, i32 %743		; visa id: 737
  %746 = sitofp i32 %745 to float		; visa id: 738
  %747 = fmul float %624, %746		; visa id: 739
  br label %756, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 740

748:                                              ; preds = %738
; BB78 :
  %749 = uitofp i32 %740 to float		; visa id: 742
  %750 = fmul float %624, %749		; visa id: 743
  %751 = and i32 %119, 16384
  %752 = icmp eq i32 %751, 0		; visa id: 744
  %753 = select i1 %752, i32 1, i32 -1		; visa id: 746
  %754 = sitofp i32 %753 to float		; visa id: 747
  %755 = fmul float %750, %754		; visa id: 748
  br label %756, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 749

756:                                              ; preds = %748, %741
; BB79 :
  %.sroa.160.2 = phi float [ %755, %748 ], [ %747, %741 ]
  %757 = lshr i32 %181, 24		; visa id: 750
  br i1 %631, label %765, label %758, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 751

758:                                              ; preds = %756
; BB80 :
  %759 = and i32 %119, 32768
  %760 = sub nsw i32 0, %757, !spirv.Decorations !8798
  %761 = icmp eq i32 %759, 0		; visa id: 753
  %762 = select i1 %761, i32 %757, i32 %760		; visa id: 755
  %763 = sitofp i32 %762 to float		; visa id: 756
  %764 = fmul float %624, %763		; visa id: 757
  br label %.preheader1.2, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 758

765:                                              ; preds = %756
; BB81 :
  %766 = uitofp i32 %757 to float		; visa id: 760
  %767 = fmul float %624, %766		; visa id: 761
  %768 = and i32 %119, 32768
  %769 = icmp eq i32 %768, 0		; visa id: 762
  %770 = select i1 %769, i32 1, i32 -1		; visa id: 764
  %771 = sitofp i32 %770 to float		; visa id: 765
  %772 = fmul float %767, %771		; visa id: 766
  br label %.preheader1.2, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 767

.preheader1.2:                                    ; preds = %765, %758
; BB82 :
  %.sroa.184.2 = phi float [ %772, %765 ], [ %764, %758 ]
  %773 = zext i16 %610 to i32		; visa id: 768
  %774 = shl nuw i32 %773, 16, !spirv.Decorations !8788		; visa id: 769
  %775 = bitcast i32 %774 to float
  %776 = fmul float %.sroa.069.2, %775		; visa id: 770
  %777 = fadd float %.sroa.13.0, %776		; visa id: 771
  %778 = zext i16 %611 to i32		; visa id: 772
  %779 = shl nuw i32 %778, 16, !spirv.Decorations !8788		; visa id: 773
  %780 = bitcast i32 %779 to float
  %781 = fmul float %.sroa.40.2, %780		; visa id: 774
  %782 = fadd float %777, %781		; visa id: 775
  %783 = zext i16 %612 to i32		; visa id: 776
  %784 = shl nuw i32 %783, 16, !spirv.Decorations !8788		; visa id: 777
  %785 = bitcast i32 %784 to float
  %786 = fmul float %.sroa.64.2, %785		; visa id: 778
  %787 = fadd float %782, %786		; visa id: 779
  %788 = zext i16 %613 to i32		; visa id: 780
  %789 = shl nuw i32 %788, 16, !spirv.Decorations !8788		; visa id: 781
  %790 = bitcast i32 %789 to float
  %791 = fmul float %.sroa.88.2, %790		; visa id: 782
  %792 = fadd float %787, %791		; visa id: 783
  %793 = zext i16 %616 to i32		; visa id: 784
  %794 = shl nuw i32 %793, 16, !spirv.Decorations !8788		; visa id: 785
  %795 = bitcast i32 %794 to float
  %796 = fmul float %.sroa.112.2, %795		; visa id: 786
  %797 = fadd float %792, %796		; visa id: 787
  %798 = zext i16 %617 to i32		; visa id: 788
  %799 = shl nuw i32 %798, 16, !spirv.Decorations !8788		; visa id: 789
  %800 = bitcast i32 %799 to float
  %801 = fmul float %.sroa.136.2, %800		; visa id: 790
  %802 = fadd float %797, %801		; visa id: 791
  %803 = zext i16 %618 to i32		; visa id: 792
  %804 = shl nuw i32 %803, 16, !spirv.Decorations !8788		; visa id: 793
  %805 = bitcast i32 %804 to float
  %806 = fmul float %.sroa.160.2, %805		; visa id: 794
  %807 = fadd float %802, %806		; visa id: 795
  %808 = zext i16 %619 to i32		; visa id: 796
  %809 = shl nuw i32 %808, 16, !spirv.Decorations !8788		; visa id: 797
  %810 = bitcast i32 %809 to float
  %811 = fmul float %.sroa.184.2, %810		; visa id: 798
  %812 = fadd float %807, %811		; visa id: 799
  %813 = or i32 %193, 48		; visa id: 800
  %814 = zext i32 %813 to i64		; visa id: 801
  %815 = add i64 %814, %const_reg_qword2		; visa id: 802
  %IntToPtr2345 = inttoptr i64 %815 to ptr addrspace(1)		; visa id: 803
  %vCastload346 = load i32, ptr addrspace(1) %IntToPtr2345, align 2		; visa id: 803
  %816 = add i64 %815, 4
  %IntToPtr2347 = inttoptr i64 %816 to ptr addrspace(1)
  %vCastload348 = load i32, ptr addrspace(1) %IntToPtr2347, align 2		; visa id: 804
  %817 = add i64 %815, 8
  %IntToPtr2349 = inttoptr i64 %817 to ptr addrspace(1)
  %vCastload350 = load i32, ptr addrspace(1) %IntToPtr2349, align 2		; visa id: 805
  %818 = add i64 %815, 12
  %IntToPtr2351 = inttoptr i64 %818 to ptr addrspace(1)
  %vCastload352 = load i32, ptr addrspace(1) %IntToPtr2351, align 2		; visa id: 806
  %819 = bitcast i32 %vCastload346 to <2 x i16>		; visa id: 807
  %820 = bitcast i32 %vCastload348 to <2 x i16>		; visa id: 809
  %821 = extractelement <2 x i16> %819, i32 0		; visa id: 811
  %822 = extractelement <2 x i16> %819, i32 1		; visa id: 811
  %823 = extractelement <2 x i16> %820, i32 0		; visa id: 811
  %824 = extractelement <2 x i16> %820, i32 1		; visa id: 811
  %825 = bitcast i32 %vCastload350 to <2 x i16>		; visa id: 811
  %826 = bitcast i32 %vCastload352 to <2 x i16>		; visa id: 813
  %827 = extractelement <2 x i16> %825, i32 0		; visa id: 815
  %828 = extractelement <2 x i16> %825, i32 1		; visa id: 815
  %829 = extractelement <2 x i16> %826, i32 0		; visa id: 815
  %830 = extractelement <2 x i16> %826, i32 1		; visa id: 815
  %831 = and i32 %197, 255		; visa id: 815
  br i1 %631, label %839, label %832, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 816

832:                                              ; preds = %.preheader1.2
; BB83 :
  %833 = and i32 %119, 16777216
  %834 = sub nsw i32 0, %831, !spirv.Decorations !8798
  %835 = icmp eq i32 %833, 0		; visa id: 818
  %836 = select i1 %835, i32 %831, i32 %834		; visa id: 820
  %837 = sitofp i32 %836 to float		; visa id: 821
  %838 = fmul float %624, %837		; visa id: 822
  br label %847, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 823

839:                                              ; preds = %.preheader1.2
; BB84 :
  %840 = uitofp i32 %831 to float		; visa id: 825
  %841 = fmul float %624, %840		; visa id: 826
  %842 = and i32 %119, 16777216
  %843 = icmp eq i32 %842, 0		; visa id: 827
  %844 = select i1 %843, i32 1, i32 -1		; visa id: 829
  %845 = sitofp i32 %844 to float		; visa id: 830
  %846 = fmul float %841, %845		; visa id: 831
  br label %847, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 832

847:                                              ; preds = %839, %832
; BB85 :
  %.sroa.069.3 = phi float [ %846, %839 ], [ %838, %832 ]
  %848 = bitcast i32 %197 to <4 x i8>
  %849 = extractelement <4 x i8> %848, i32 1
  %850 = zext i8 %849 to i32		; visa id: 833
  br i1 %631, label %858, label %851, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 834

851:                                              ; preds = %847
; BB86 :
  %852 = and i32 %119, 33554432
  %853 = sub nsw i32 0, %850, !spirv.Decorations !8798
  %854 = icmp eq i32 %852, 0		; visa id: 836
  %855 = select i1 %854, i32 %850, i32 %853		; visa id: 838
  %856 = sitofp i32 %855 to float		; visa id: 839
  %857 = fmul float %624, %856		; visa id: 840
  br label %866, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 841

858:                                              ; preds = %847
; BB87 :
  %859 = uitofp i32 %850 to float		; visa id: 843
  %860 = fmul float %624, %859		; visa id: 844
  %861 = and i32 %119, 33554432
  %862 = icmp eq i32 %861, 0		; visa id: 845
  %863 = select i1 %862, i32 1, i32 -1		; visa id: 847
  %864 = sitofp i32 %863 to float		; visa id: 848
  %865 = fmul float %860, %864		; visa id: 849
  br label %866, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 850

866:                                              ; preds = %858, %851
; BB88 :
  %.sroa.40.3 = phi float [ %865, %858 ], [ %857, %851 ]
  %867 = extractelement <4 x i8> %848, i32 2
  %868 = zext i8 %867 to i32		; visa id: 851
  br i1 %631, label %876, label %869, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 852

869:                                              ; preds = %866
; BB89 :
  %870 = and i32 %119, 67108864
  %871 = sub nsw i32 0, %868, !spirv.Decorations !8798
  %872 = icmp eq i32 %870, 0		; visa id: 854
  %873 = select i1 %872, i32 %868, i32 %871		; visa id: 856
  %874 = sitofp i32 %873 to float		; visa id: 857
  %875 = fmul float %624, %874		; visa id: 858
  br label %884, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 859

876:                                              ; preds = %866
; BB90 :
  %877 = uitofp i32 %868 to float		; visa id: 861
  %878 = fmul float %624, %877		; visa id: 862
  %879 = and i32 %119, 67108864
  %880 = icmp eq i32 %879, 0		; visa id: 863
  %881 = select i1 %880, i32 1, i32 -1		; visa id: 865
  %882 = sitofp i32 %881 to float		; visa id: 866
  %883 = fmul float %878, %882		; visa id: 867
  br label %884, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 868

884:                                              ; preds = %876, %869
; BB91 :
  %.sroa.64.3 = phi float [ %883, %876 ], [ %875, %869 ]
  %885 = lshr i32 %197, 24		; visa id: 869
  br i1 %631, label %893, label %886, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 870

886:                                              ; preds = %884
; BB92 :
  %887 = and i32 %119, 134217728
  %888 = sub nsw i32 0, %885, !spirv.Decorations !8798
  %889 = icmp eq i32 %887, 0		; visa id: 872
  %890 = select i1 %889, i32 %885, i32 %888		; visa id: 874
  %891 = sitofp i32 %890 to float		; visa id: 875
  %892 = fmul float %624, %891		; visa id: 876
  br label %901, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 877

893:                                              ; preds = %884
; BB93 :
  %894 = uitofp i32 %885 to float		; visa id: 879
  %895 = fmul float %624, %894		; visa id: 880
  %896 = and i32 %119, 134217728
  %897 = icmp eq i32 %896, 0		; visa id: 881
  %898 = select i1 %897, i32 1, i32 -1		; visa id: 883
  %899 = sitofp i32 %898 to float		; visa id: 884
  %900 = fmul float %895, %899		; visa id: 885
  br label %901, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 886

901:                                              ; preds = %893, %886
; BB94 :
  %.sroa.88.3 = phi float [ %900, %893 ], [ %892, %886 ]
  %902 = and i32 %198, 255		; visa id: 887
  br i1 %631, label %910, label %903, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 888

903:                                              ; preds = %901
; BB95 :
  %904 = and i32 %119, 268435456
  %905 = sub nsw i32 0, %902, !spirv.Decorations !8798
  %906 = icmp eq i32 %904, 0		; visa id: 890
  %907 = select i1 %906, i32 %902, i32 %905		; visa id: 892
  %908 = sitofp i32 %907 to float		; visa id: 893
  %909 = fmul float %624, %908		; visa id: 894
  br label %918, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 895

910:                                              ; preds = %901
; BB96 :
  %911 = uitofp i32 %902 to float		; visa id: 897
  %912 = fmul float %624, %911		; visa id: 898
  %913 = and i32 %119, 268435456
  %914 = icmp eq i32 %913, 0		; visa id: 899
  %915 = select i1 %914, i32 1, i32 -1		; visa id: 901
  %916 = sitofp i32 %915 to float		; visa id: 902
  %917 = fmul float %912, %916		; visa id: 903
  br label %918, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 904

918:                                              ; preds = %910, %903
; BB97 :
  %.sroa.112.3 = phi float [ %917, %910 ], [ %909, %903 ]
  %919 = bitcast i32 %198 to <4 x i8>
  %920 = extractelement <4 x i8> %919, i32 1
  %921 = zext i8 %920 to i32		; visa id: 905
  br i1 %631, label %929, label %922, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 906

922:                                              ; preds = %918
; BB98 :
  %923 = and i32 %119, 536870912
  %924 = sub nsw i32 0, %921, !spirv.Decorations !8798
  %925 = icmp eq i32 %923, 0		; visa id: 908
  %926 = select i1 %925, i32 %921, i32 %924		; visa id: 910
  %927 = sitofp i32 %926 to float		; visa id: 911
  %928 = fmul float %624, %927		; visa id: 912
  br label %937, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 913

929:                                              ; preds = %918
; BB99 :
  %930 = uitofp i32 %921 to float		; visa id: 915
  %931 = fmul float %624, %930		; visa id: 916
  %932 = and i32 %119, 536870912
  %933 = icmp eq i32 %932, 0		; visa id: 917
  %934 = select i1 %933, i32 1, i32 -1		; visa id: 919
  %935 = sitofp i32 %934 to float		; visa id: 920
  %936 = fmul float %931, %935		; visa id: 921
  br label %937, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 922

937:                                              ; preds = %929, %922
; BB100 :
  %.sroa.136.3 = phi float [ %936, %929 ], [ %928, %922 ]
  %938 = extractelement <4 x i8> %919, i32 2
  %939 = zext i8 %938 to i32		; visa id: 923
  br i1 %631, label %947, label %940, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 924

940:                                              ; preds = %937
; BB101 :
  %941 = and i32 %119, 1073741824
  %942 = sub nsw i32 0, %939, !spirv.Decorations !8798
  %943 = icmp eq i32 %941, 0		; visa id: 926
  %944 = select i1 %943, i32 %939, i32 %942		; visa id: 928
  %945 = sitofp i32 %944 to float		; visa id: 929
  %946 = fmul float %624, %945		; visa id: 930
  br label %955, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 931

947:                                              ; preds = %937
; BB102 :
  %948 = uitofp i32 %939 to float		; visa id: 933
  %949 = fmul float %624, %948		; visa id: 934
  %950 = and i32 %119, 1073741824
  %951 = icmp eq i32 %950, 0		; visa id: 935
  %952 = select i1 %951, i32 1, i32 -1		; visa id: 937
  %953 = sitofp i32 %952 to float		; visa id: 938
  %954 = fmul float %949, %953		; visa id: 939
  br label %955, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 940

955:                                              ; preds = %947, %940
; BB103 :
  %.sroa.160.3 = phi float [ %954, %947 ], [ %946, %940 ]
  %956 = lshr i32 %198, 24		; visa id: 941
  br i1 %631, label %963, label %957, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 942

957:                                              ; preds = %955
; BB104 :
  %958 = sub nsw i32 0, %956, !spirv.Decorations !8798
  %959 = icmp slt i32 %119, 0		; visa id: 944
  %960 = select i1 %959, i32 %958, i32 %956		; visa id: 945
  %961 = sitofp i32 %960 to float		; visa id: 946
  %962 = fmul float %624, %961		; visa id: 947
  br label %.preheader1.3, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 948

963:                                              ; preds = %955
; BB105 :
  %964 = uitofp i32 %956 to float		; visa id: 950
  %965 = fmul float %624, %964		; visa id: 951
  %966 = icmp sgt i32 %119, -1		; visa id: 952
  %967 = select i1 %966, i32 1, i32 -1		; visa id: 953
  %968 = sitofp i32 %967 to float		; visa id: 954
  %969 = fmul float %965, %968		; visa id: 955
  br label %.preheader1.3, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 956

.preheader1.3:                                    ; preds = %963, %957
; BB106 :
  %.sroa.184.3 = phi float [ %969, %963 ], [ %962, %957 ]
  %970 = zext i16 %821 to i32		; visa id: 957
  %971 = shl nuw i32 %970, 16, !spirv.Decorations !8788		; visa id: 958
  %972 = bitcast i32 %971 to float
  %973 = fmul float %.sroa.069.3, %972		; visa id: 959
  %974 = fadd float %.sroa.18.0, %973		; visa id: 960
  %975 = zext i16 %822 to i32		; visa id: 961
  %976 = shl nuw i32 %975, 16, !spirv.Decorations !8788		; visa id: 962
  %977 = bitcast i32 %976 to float
  %978 = fmul float %.sroa.40.3, %977		; visa id: 963
  %979 = fadd float %974, %978		; visa id: 964
  %980 = zext i16 %823 to i32		; visa id: 965
  %981 = shl nuw i32 %980, 16, !spirv.Decorations !8788		; visa id: 966
  %982 = bitcast i32 %981 to float
  %983 = fmul float %.sroa.64.3, %982		; visa id: 967
  %984 = fadd float %979, %983		; visa id: 968
  %985 = zext i16 %824 to i32		; visa id: 969
  %986 = shl nuw i32 %985, 16, !spirv.Decorations !8788		; visa id: 970
  %987 = bitcast i32 %986 to float
  %988 = fmul float %.sroa.88.3, %987		; visa id: 971
  %989 = fadd float %984, %988		; visa id: 972
  %990 = zext i16 %827 to i32		; visa id: 973
  %991 = shl nuw i32 %990, 16, !spirv.Decorations !8788		; visa id: 974
  %992 = bitcast i32 %991 to float
  %993 = fmul float %.sroa.112.3, %992		; visa id: 975
  %994 = fadd float %989, %993		; visa id: 976
  %995 = zext i16 %828 to i32		; visa id: 977
  %996 = shl nuw i32 %995, 16, !spirv.Decorations !8788		; visa id: 978
  %997 = bitcast i32 %996 to float
  %998 = fmul float %.sroa.136.3, %997		; visa id: 979
  %999 = fadd float %994, %998		; visa id: 980
  %1000 = zext i16 %829 to i32		; visa id: 981
  %1001 = shl nuw i32 %1000, 16, !spirv.Decorations !8788		; visa id: 982
  %1002 = bitcast i32 %1001 to float
  %1003 = fmul float %.sroa.160.3, %1002		; visa id: 983
  %1004 = fadd float %999, %1003		; visa id: 984
  %1005 = zext i16 %830 to i32		; visa id: 985
  %1006 = shl nuw i32 %1005, 16, !spirv.Decorations !8788		; visa id: 986
  %1007 = bitcast i32 %1006 to float
  %1008 = fmul float %.sroa.184.3, %1007		; visa id: 987
  %1009 = fadd float %1004, %1008		; visa id: 988
  %1010 = lshr i16 %131, 8		; visa id: 989
  %1011 = and i32 %120, 255
  %1012 = and i32 %139, 768		; visa id: 990
  %1013 = or i32 %1011, %1012		; visa id: 991
  %1014 = shl nuw nsw i32 %1013, 3, !spirv.Decorations !8791		; visa id: 992
  %1015 = zext i32 %1014 to i64		; visa id: 993
  %1016 = add i64 %111, %1015		; visa id: 994
  %1017 = inttoptr i64 %1016 to ptr addrspace(1)		; visa id: 995
  %1018 = load <2 x i32>, ptr addrspace(1) %1017, align 4		; visa id: 995
  %1019 = bitcast i32 %120 to <4 x i8>
  %1020 = extractelement <4 x i8> %1019, i32 2
  %1021 = lshr i32 %139, 2		; visa id: 996
  %1022 = and i32 %1021, 768
  %1023 = zext i8 %1020 to i32		; visa id: 997
  %1024 = or i32 %1023, %1022		; visa id: 998
  %1025 = shl nuw nsw i32 %1024, 3, !spirv.Decorations !8791		; visa id: 999
  %1026 = zext i32 %1025 to i64		; visa id: 1000
  %1027 = add i64 %111, %1026		; visa id: 1001
  %1028 = inttoptr i64 %1027 to ptr addrspace(1)		; visa id: 1002
  %1029 = load <2 x i32>, ptr addrspace(1) %1028, align 4		; visa id: 1002
  %1030 = extractelement <2 x i32> %1018, i32 0		; visa id: 1003
  %1031 = extractelement <2 x i32> %1018, i32 1		; visa id: 1003
  %1032 = extractelement <2 x i32> %1029, i32 0		; visa id: 1003
  %1033 = extractelement <2 x i32> %1029, i32 1		; visa id: 1003
  %1034 = and i32 %121, 255
  %1035 = lshr i32 %139, 4		; visa id: 1003
  %1036 = and i32 %1035, 768		; visa id: 1004
  %1037 = or i32 %1034, %1036		; visa id: 1005
  %1038 = shl nuw nsw i32 %1037, 3, !spirv.Decorations !8791		; visa id: 1006
  %1039 = zext i32 %1038 to i64		; visa id: 1007
  %1040 = add i64 %111, %1039		; visa id: 1008
  %1041 = inttoptr i64 %1040 to ptr addrspace(1)		; visa id: 1009
  %1042 = load <2 x i32>, ptr addrspace(1) %1041, align 4		; visa id: 1009
  %1043 = bitcast i32 %121 to <4 x i8>
  %1044 = extractelement <4 x i8> %1043, i32 2
  %1045 = lshr i32 %139, 6		; visa id: 1010
  %1046 = and i32 %1045, 768
  %1047 = zext i8 %1044 to i32		; visa id: 1011
  %1048 = or i32 %1047, %1046		; visa id: 1012
  %1049 = shl nuw nsw i32 %1048, 3, !spirv.Decorations !8791		; visa id: 1013
  %1050 = zext i32 %1049 to i64		; visa id: 1014
  %1051 = add i64 %111, %1050		; visa id: 1015
  %1052 = inttoptr i64 %1051 to ptr addrspace(1)		; visa id: 1016
  %1053 = load <2 x i32>, ptr addrspace(1) %1052, align 4		; visa id: 1016
  %1054 = extractelement <2 x i32> %1042, i32 0		; visa id: 1017
  %1055 = extractelement <2 x i32> %1042, i32 1		; visa id: 1017
  %1056 = extractelement <2 x i32> %1053, i32 0		; visa id: 1017
  %1057 = extractelement <2 x i32> %1053, i32 1		; visa id: 1017
  %1058 = or i32 %193, 64		; visa id: 1017
  %1059 = zext i32 %1058 to i64		; visa id: 1018
  %1060 = add i64 %1059, %const_reg_qword2		; visa id: 1019
  %IntToPtr2353 = inttoptr i64 %1060 to ptr addrspace(1)		; visa id: 1020
  %vCastload354 = load i32, ptr addrspace(1) %IntToPtr2353, align 2		; visa id: 1020
  %1061 = add i64 %1060, 4
  %IntToPtr2355 = inttoptr i64 %1061 to ptr addrspace(1)
  %vCastload356 = load i32, ptr addrspace(1) %IntToPtr2355, align 2		; visa id: 1021
  %1062 = add i64 %1060, 8
  %IntToPtr2357 = inttoptr i64 %1062 to ptr addrspace(1)
  %vCastload358 = load i32, ptr addrspace(1) %IntToPtr2357, align 2		; visa id: 1022
  %1063 = add i64 %1060, 12
  %IntToPtr2359 = inttoptr i64 %1063 to ptr addrspace(1)
  %vCastload360 = load i32, ptr addrspace(1) %IntToPtr2359, align 2		; visa id: 1023
  %1064 = bitcast i32 %vCastload354 to <2 x i16>		; visa id: 1024
  %1065 = bitcast i32 %vCastload356 to <2 x i16>		; visa id: 1026
  %1066 = extractelement <2 x i16> %1064, i32 0		; visa id: 1028
  %1067 = extractelement <2 x i16> %1064, i32 1		; visa id: 1028
  %1068 = extractelement <2 x i16> %1065, i32 0		; visa id: 1028
  %1069 = extractelement <2 x i16> %1065, i32 1		; visa id: 1028
  %1070 = bitcast i32 %vCastload358 to <2 x i16>		; visa id: 1028
  %1071 = bitcast i32 %vCastload360 to <2 x i16>		; visa id: 1030
  %1072 = extractelement <2 x i16> %1070, i32 0		; visa id: 1032
  %1073 = extractelement <2 x i16> %1070, i32 1		; visa id: 1032
  %1074 = extractelement <2 x i16> %1071, i32 0		; visa id: 1032
  %1075 = extractelement <2 x i16> %1071, i32 1		; visa id: 1032
  %1076 = zext i16 %1010 to i32		; visa id: 1032
  %1077 = and i32 %1076, 15		; visa id: 1033
  %1078 = uitofp i32 %1077 to float		; visa id: 1034
  %1079 = fadd float %1078, 5.000000e-01		; visa id: 1035
  %1080 = fmul float %137, %1079		; visa id: 1036
  %1081 = fmul float %1080, 2.500000e-01		; visa id: 1037
  %1082 = bitcast float %1081 to i32
  %1083 = and i32 %1082, 2147483647		; visa id: 1038
  %1084 = icmp ugt i32 %1083, 2139095040
  %1085 = fcmp oeq float %152, 0x7FF0000000000000		; visa id: 1039
  %1086 = fcmp une float %152, %152
  %1087 = or i1 %1086, %1085		; visa id: 1040
  %1088 = or i1 %1087, %1084		; visa id: 1042
  %1089 = and i32 %1030, 255		; visa id: 1044
  br i1 %1088, label %1097, label %1090, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1045

1090:                                             ; preds = %.preheader1.3
; BB107 :
  %1091 = and i32 %120, 256
  %1092 = sub nsw i32 0, %1089, !spirv.Decorations !8798
  %1093 = icmp eq i32 %1091, 0		; visa id: 1047
  %1094 = select i1 %1093, i32 %1089, i32 %1092		; visa id: 1049
  %1095 = sitofp i32 %1094 to float		; visa id: 1050
  %1096 = fmul float %1081, %1095		; visa id: 1051
  br label %1105, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1052

1097:                                             ; preds = %.preheader1.3
; BB108 :
  %1098 = uitofp i32 %1089 to float		; visa id: 1054
  %1099 = fmul float %1081, %1098		; visa id: 1055
  %1100 = and i32 %120, 256
  %1101 = icmp eq i32 %1100, 0		; visa id: 1056
  %1102 = select i1 %1101, i32 1, i32 -1		; visa id: 1058
  %1103 = sitofp i32 %1102 to float		; visa id: 1059
  %1104 = fmul float %1099, %1103		; visa id: 1060
  br label %1105, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1061

1105:                                             ; preds = %1097, %1090
; BB109 :
  %.sroa.069.4 = phi float [ %1104, %1097 ], [ %1096, %1090 ]
  %1106 = bitcast i32 %1030 to <4 x i8>
  %1107 = extractelement <4 x i8> %1106, i32 1
  %1108 = zext i8 %1107 to i32		; visa id: 1062
  br i1 %1088, label %1116, label %1109, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1063

1109:                                             ; preds = %1105
; BB110 :
  %1110 = and i32 %120, 512
  %1111 = sub nsw i32 0, %1108, !spirv.Decorations !8798
  %1112 = icmp eq i32 %1110, 0		; visa id: 1065
  %1113 = select i1 %1112, i32 %1108, i32 %1111		; visa id: 1067
  %1114 = sitofp i32 %1113 to float		; visa id: 1068
  %1115 = fmul float %1081, %1114		; visa id: 1069
  br label %1124, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1070

1116:                                             ; preds = %1105
; BB111 :
  %1117 = uitofp i32 %1108 to float		; visa id: 1072
  %1118 = fmul float %1081, %1117		; visa id: 1073
  %1119 = and i32 %120, 512
  %1120 = icmp eq i32 %1119, 0		; visa id: 1074
  %1121 = select i1 %1120, i32 1, i32 -1		; visa id: 1076
  %1122 = sitofp i32 %1121 to float		; visa id: 1077
  %1123 = fmul float %1118, %1122		; visa id: 1078
  br label %1124, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1079

1124:                                             ; preds = %1116, %1109
; BB112 :
  %.sroa.40.4 = phi float [ %1123, %1116 ], [ %1115, %1109 ]
  %1125 = extractelement <4 x i8> %1106, i32 2
  %1126 = zext i8 %1125 to i32		; visa id: 1080
  br i1 %1088, label %1134, label %1127, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1081

1127:                                             ; preds = %1124
; BB113 :
  %1128 = and i32 %120, 1024
  %1129 = sub nsw i32 0, %1126, !spirv.Decorations !8798
  %1130 = icmp eq i32 %1128, 0		; visa id: 1083
  %1131 = select i1 %1130, i32 %1126, i32 %1129		; visa id: 1085
  %1132 = sitofp i32 %1131 to float		; visa id: 1086
  %1133 = fmul float %1081, %1132		; visa id: 1087
  br label %1142, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1088

1134:                                             ; preds = %1124
; BB114 :
  %1135 = uitofp i32 %1126 to float		; visa id: 1090
  %1136 = fmul float %1081, %1135		; visa id: 1091
  %1137 = and i32 %120, 1024
  %1138 = icmp eq i32 %1137, 0		; visa id: 1092
  %1139 = select i1 %1138, i32 1, i32 -1		; visa id: 1094
  %1140 = sitofp i32 %1139 to float		; visa id: 1095
  %1141 = fmul float %1136, %1140		; visa id: 1096
  br label %1142, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1097

1142:                                             ; preds = %1134, %1127
; BB115 :
  %.sroa.64.4 = phi float [ %1141, %1134 ], [ %1133, %1127 ]
  %1143 = lshr i32 %1030, 24		; visa id: 1098
  br i1 %1088, label %1151, label %1144, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1099

1144:                                             ; preds = %1142
; BB116 :
  %1145 = and i32 %120, 2048
  %1146 = sub nsw i32 0, %1143, !spirv.Decorations !8798
  %1147 = icmp eq i32 %1145, 0		; visa id: 1101
  %1148 = select i1 %1147, i32 %1143, i32 %1146		; visa id: 1103
  %1149 = sitofp i32 %1148 to float		; visa id: 1104
  %1150 = fmul float %1081, %1149		; visa id: 1105
  br label %1159, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1106

1151:                                             ; preds = %1142
; BB117 :
  %1152 = uitofp i32 %1143 to float		; visa id: 1108
  %1153 = fmul float %1081, %1152		; visa id: 1109
  %1154 = and i32 %120, 2048
  %1155 = icmp eq i32 %1154, 0		; visa id: 1110
  %1156 = select i1 %1155, i32 1, i32 -1		; visa id: 1112
  %1157 = sitofp i32 %1156 to float		; visa id: 1113
  %1158 = fmul float %1153, %1157		; visa id: 1114
  br label %1159, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1115

1159:                                             ; preds = %1151, %1144
; BB118 :
  %.sroa.88.4 = phi float [ %1158, %1151 ], [ %1150, %1144 ]
  %1160 = and i32 %1031, 255		; visa id: 1116
  br i1 %1088, label %1168, label %1161, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1117

1161:                                             ; preds = %1159
; BB119 :
  %1162 = and i32 %120, 4096
  %1163 = sub nsw i32 0, %1160, !spirv.Decorations !8798
  %1164 = icmp eq i32 %1162, 0		; visa id: 1119
  %1165 = select i1 %1164, i32 %1160, i32 %1163		; visa id: 1121
  %1166 = sitofp i32 %1165 to float		; visa id: 1122
  %1167 = fmul float %1081, %1166		; visa id: 1123
  br label %1176, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1124

1168:                                             ; preds = %1159
; BB120 :
  %1169 = uitofp i32 %1160 to float		; visa id: 1126
  %1170 = fmul float %1081, %1169		; visa id: 1127
  %1171 = and i32 %120, 4096
  %1172 = icmp eq i32 %1171, 0		; visa id: 1128
  %1173 = select i1 %1172, i32 1, i32 -1		; visa id: 1130
  %1174 = sitofp i32 %1173 to float		; visa id: 1131
  %1175 = fmul float %1170, %1174		; visa id: 1132
  br label %1176, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1133

1176:                                             ; preds = %1168, %1161
; BB121 :
  %.sroa.112.4 = phi float [ %1175, %1168 ], [ %1167, %1161 ]
  %1177 = bitcast i32 %1031 to <4 x i8>
  %1178 = extractelement <4 x i8> %1177, i32 1
  %1179 = zext i8 %1178 to i32		; visa id: 1134
  br i1 %1088, label %1187, label %1180, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1135

1180:                                             ; preds = %1176
; BB122 :
  %1181 = and i32 %120, 8192
  %1182 = sub nsw i32 0, %1179, !spirv.Decorations !8798
  %1183 = icmp eq i32 %1181, 0		; visa id: 1137
  %1184 = select i1 %1183, i32 %1179, i32 %1182		; visa id: 1139
  %1185 = sitofp i32 %1184 to float		; visa id: 1140
  %1186 = fmul float %1081, %1185		; visa id: 1141
  br label %1195, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1142

1187:                                             ; preds = %1176
; BB123 :
  %1188 = uitofp i32 %1179 to float		; visa id: 1144
  %1189 = fmul float %1081, %1188		; visa id: 1145
  %1190 = and i32 %120, 8192
  %1191 = icmp eq i32 %1190, 0		; visa id: 1146
  %1192 = select i1 %1191, i32 1, i32 -1		; visa id: 1148
  %1193 = sitofp i32 %1192 to float		; visa id: 1149
  %1194 = fmul float %1189, %1193		; visa id: 1150
  br label %1195, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1151

1195:                                             ; preds = %1187, %1180
; BB124 :
  %.sroa.136.4 = phi float [ %1194, %1187 ], [ %1186, %1180 ]
  %1196 = extractelement <4 x i8> %1177, i32 2
  %1197 = zext i8 %1196 to i32		; visa id: 1152
  br i1 %1088, label %1205, label %1198, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1153

1198:                                             ; preds = %1195
; BB125 :
  %1199 = and i32 %120, 16384
  %1200 = sub nsw i32 0, %1197, !spirv.Decorations !8798
  %1201 = icmp eq i32 %1199, 0		; visa id: 1155
  %1202 = select i1 %1201, i32 %1197, i32 %1200		; visa id: 1157
  %1203 = sitofp i32 %1202 to float		; visa id: 1158
  %1204 = fmul float %1081, %1203		; visa id: 1159
  br label %1213, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1160

1205:                                             ; preds = %1195
; BB126 :
  %1206 = uitofp i32 %1197 to float		; visa id: 1162
  %1207 = fmul float %1081, %1206		; visa id: 1163
  %1208 = and i32 %120, 16384
  %1209 = icmp eq i32 %1208, 0		; visa id: 1164
  %1210 = select i1 %1209, i32 1, i32 -1		; visa id: 1166
  %1211 = sitofp i32 %1210 to float		; visa id: 1167
  %1212 = fmul float %1207, %1211		; visa id: 1168
  br label %1213, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1169

1213:                                             ; preds = %1205, %1198
; BB127 :
  %.sroa.160.4 = phi float [ %1212, %1205 ], [ %1204, %1198 ]
  %1214 = lshr i32 %1031, 24		; visa id: 1170
  br i1 %1088, label %1222, label %1215, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1171

1215:                                             ; preds = %1213
; BB128 :
  %1216 = and i32 %120, 32768
  %1217 = sub nsw i32 0, %1214, !spirv.Decorations !8798
  %1218 = icmp eq i32 %1216, 0		; visa id: 1173
  %1219 = select i1 %1218, i32 %1214, i32 %1217		; visa id: 1175
  %1220 = sitofp i32 %1219 to float		; visa id: 1176
  %1221 = fmul float %1081, %1220		; visa id: 1177
  br label %.preheader1.153, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1178

1222:                                             ; preds = %1213
; BB129 :
  %1223 = uitofp i32 %1214 to float		; visa id: 1180
  %1224 = fmul float %1081, %1223		; visa id: 1181
  %1225 = and i32 %120, 32768
  %1226 = icmp eq i32 %1225, 0		; visa id: 1182
  %1227 = select i1 %1226, i32 1, i32 -1		; visa id: 1184
  %1228 = sitofp i32 %1227 to float		; visa id: 1185
  %1229 = fmul float %1224, %1228		; visa id: 1186
  br label %.preheader1.153, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1187

.preheader1.153:                                  ; preds = %1222, %1215
; BB130 :
  %.sroa.184.4 = phi float [ %1229, %1222 ], [ %1221, %1215 ]
  %1230 = zext i16 %1066 to i32		; visa id: 1188
  %1231 = shl nuw i32 %1230, 16, !spirv.Decorations !8788		; visa id: 1189
  %1232 = bitcast i32 %1231 to float
  %1233 = fmul float %.sroa.069.4, %1232		; visa id: 1190
  %1234 = fadd float %.sroa.21.0, %1233		; visa id: 1191
  %1235 = zext i16 %1067 to i32		; visa id: 1192
  %1236 = shl nuw i32 %1235, 16, !spirv.Decorations !8788		; visa id: 1193
  %1237 = bitcast i32 %1236 to float
  %1238 = fmul float %.sroa.40.4, %1237		; visa id: 1194
  %1239 = fadd float %1234, %1238		; visa id: 1195
  %1240 = zext i16 %1068 to i32		; visa id: 1196
  %1241 = shl nuw i32 %1240, 16, !spirv.Decorations !8788		; visa id: 1197
  %1242 = bitcast i32 %1241 to float
  %1243 = fmul float %.sroa.64.4, %1242		; visa id: 1198
  %1244 = fadd float %1239, %1243		; visa id: 1199
  %1245 = zext i16 %1069 to i32		; visa id: 1200
  %1246 = shl nuw i32 %1245, 16, !spirv.Decorations !8788		; visa id: 1201
  %1247 = bitcast i32 %1246 to float
  %1248 = fmul float %.sroa.88.4, %1247		; visa id: 1202
  %1249 = fadd float %1244, %1248		; visa id: 1203
  %1250 = zext i16 %1072 to i32		; visa id: 1204
  %1251 = shl nuw i32 %1250, 16, !spirv.Decorations !8788		; visa id: 1205
  %1252 = bitcast i32 %1251 to float
  %1253 = fmul float %.sroa.112.4, %1252		; visa id: 1206
  %1254 = fadd float %1249, %1253		; visa id: 1207
  %1255 = zext i16 %1073 to i32		; visa id: 1208
  %1256 = shl nuw i32 %1255, 16, !spirv.Decorations !8788		; visa id: 1209
  %1257 = bitcast i32 %1256 to float
  %1258 = fmul float %.sroa.136.4, %1257		; visa id: 1210
  %1259 = fadd float %1254, %1258		; visa id: 1211
  %1260 = zext i16 %1074 to i32		; visa id: 1212
  %1261 = shl nuw i32 %1260, 16, !spirv.Decorations !8788		; visa id: 1213
  %1262 = bitcast i32 %1261 to float
  %1263 = fmul float %.sroa.160.4, %1262		; visa id: 1214
  %1264 = fadd float %1259, %1263		; visa id: 1215
  %1265 = zext i16 %1075 to i32		; visa id: 1216
  %1266 = shl nuw i32 %1265, 16, !spirv.Decorations !8788		; visa id: 1217
  %1267 = bitcast i32 %1266 to float
  %1268 = fmul float %.sroa.184.4, %1267		; visa id: 1218
  %1269 = fadd float %1264, %1268		; visa id: 1219
  %1270 = or i32 %193, 80		; visa id: 1220
  %1271 = zext i32 %1270 to i64		; visa id: 1221
  %1272 = add i64 %1271, %const_reg_qword2		; visa id: 1222
  %IntToPtr2361 = inttoptr i64 %1272 to ptr addrspace(1)		; visa id: 1223
  %vCastload362 = load i32, ptr addrspace(1) %IntToPtr2361, align 2		; visa id: 1223
  %1273 = add i64 %1272, 4
  %IntToPtr2363 = inttoptr i64 %1273 to ptr addrspace(1)
  %vCastload364 = load i32, ptr addrspace(1) %IntToPtr2363, align 2		; visa id: 1224
  %1274 = add i64 %1272, 8
  %IntToPtr2365 = inttoptr i64 %1274 to ptr addrspace(1)
  %vCastload366 = load i32, ptr addrspace(1) %IntToPtr2365, align 2		; visa id: 1225
  %1275 = add i64 %1272, 12
  %IntToPtr2367 = inttoptr i64 %1275 to ptr addrspace(1)
  %vCastload368 = load i32, ptr addrspace(1) %IntToPtr2367, align 2		; visa id: 1226
  %1276 = bitcast i32 %vCastload362 to <2 x i16>		; visa id: 1227
  %1277 = bitcast i32 %vCastload364 to <2 x i16>		; visa id: 1229
  %1278 = extractelement <2 x i16> %1276, i32 0		; visa id: 1231
  %1279 = extractelement <2 x i16> %1276, i32 1		; visa id: 1231
  %1280 = extractelement <2 x i16> %1277, i32 0		; visa id: 1231
  %1281 = extractelement <2 x i16> %1277, i32 1		; visa id: 1231
  %1282 = bitcast i32 %vCastload366 to <2 x i16>		; visa id: 1231
  %1283 = bitcast i32 %vCastload368 to <2 x i16>		; visa id: 1233
  %1284 = extractelement <2 x i16> %1282, i32 0		; visa id: 1235
  %1285 = extractelement <2 x i16> %1282, i32 1		; visa id: 1235
  %1286 = extractelement <2 x i16> %1283, i32 0		; visa id: 1235
  %1287 = extractelement <2 x i16> %1283, i32 1		; visa id: 1235
  %1288 = and i32 %1032, 255		; visa id: 1235
  br i1 %1088, label %1296, label %1289, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1236

1289:                                             ; preds = %.preheader1.153
; BB131 :
  %1290 = and i32 %120, 16777216
  %1291 = sub nsw i32 0, %1288, !spirv.Decorations !8798
  %1292 = icmp eq i32 %1290, 0		; visa id: 1238
  %1293 = select i1 %1292, i32 %1288, i32 %1291		; visa id: 1240
  %1294 = sitofp i32 %1293 to float		; visa id: 1241
  %1295 = fmul float %1081, %1294		; visa id: 1242
  br label %1304, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1243

1296:                                             ; preds = %.preheader1.153
; BB132 :
  %1297 = uitofp i32 %1288 to float		; visa id: 1245
  %1298 = fmul float %1081, %1297		; visa id: 1246
  %1299 = and i32 %120, 16777216
  %1300 = icmp eq i32 %1299, 0		; visa id: 1247
  %1301 = select i1 %1300, i32 1, i32 -1		; visa id: 1249
  %1302 = sitofp i32 %1301 to float		; visa id: 1250
  %1303 = fmul float %1298, %1302		; visa id: 1251
  br label %1304, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1252

1304:                                             ; preds = %1296, %1289
; BB133 :
  %.sroa.069.5 = phi float [ %1303, %1296 ], [ %1295, %1289 ]
  %1305 = bitcast i32 %1032 to <4 x i8>
  %1306 = extractelement <4 x i8> %1305, i32 1
  %1307 = zext i8 %1306 to i32		; visa id: 1253
  br i1 %1088, label %1315, label %1308, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1254

1308:                                             ; preds = %1304
; BB134 :
  %1309 = and i32 %120, 33554432
  %1310 = sub nsw i32 0, %1307, !spirv.Decorations !8798
  %1311 = icmp eq i32 %1309, 0		; visa id: 1256
  %1312 = select i1 %1311, i32 %1307, i32 %1310		; visa id: 1258
  %1313 = sitofp i32 %1312 to float		; visa id: 1259
  %1314 = fmul float %1081, %1313		; visa id: 1260
  br label %1323, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1261

1315:                                             ; preds = %1304
; BB135 :
  %1316 = uitofp i32 %1307 to float		; visa id: 1263
  %1317 = fmul float %1081, %1316		; visa id: 1264
  %1318 = and i32 %120, 33554432
  %1319 = icmp eq i32 %1318, 0		; visa id: 1265
  %1320 = select i1 %1319, i32 1, i32 -1		; visa id: 1267
  %1321 = sitofp i32 %1320 to float		; visa id: 1268
  %1322 = fmul float %1317, %1321		; visa id: 1269
  br label %1323, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1270

1323:                                             ; preds = %1315, %1308
; BB136 :
  %.sroa.40.5 = phi float [ %1322, %1315 ], [ %1314, %1308 ]
  %1324 = extractelement <4 x i8> %1305, i32 2
  %1325 = zext i8 %1324 to i32		; visa id: 1271
  br i1 %1088, label %1333, label %1326, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1272

1326:                                             ; preds = %1323
; BB137 :
  %1327 = and i32 %120, 67108864
  %1328 = sub nsw i32 0, %1325, !spirv.Decorations !8798
  %1329 = icmp eq i32 %1327, 0		; visa id: 1274
  %1330 = select i1 %1329, i32 %1325, i32 %1328		; visa id: 1276
  %1331 = sitofp i32 %1330 to float		; visa id: 1277
  %1332 = fmul float %1081, %1331		; visa id: 1278
  br label %1341, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1279

1333:                                             ; preds = %1323
; BB138 :
  %1334 = uitofp i32 %1325 to float		; visa id: 1281
  %1335 = fmul float %1081, %1334		; visa id: 1282
  %1336 = and i32 %120, 67108864
  %1337 = icmp eq i32 %1336, 0		; visa id: 1283
  %1338 = select i1 %1337, i32 1, i32 -1		; visa id: 1285
  %1339 = sitofp i32 %1338 to float		; visa id: 1286
  %1340 = fmul float %1335, %1339		; visa id: 1287
  br label %1341, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1288

1341:                                             ; preds = %1333, %1326
; BB139 :
  %.sroa.64.5 = phi float [ %1340, %1333 ], [ %1332, %1326 ]
  %1342 = lshr i32 %1032, 24		; visa id: 1289
  br i1 %1088, label %1350, label %1343, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1290

1343:                                             ; preds = %1341
; BB140 :
  %1344 = and i32 %120, 134217728
  %1345 = sub nsw i32 0, %1342, !spirv.Decorations !8798
  %1346 = icmp eq i32 %1344, 0		; visa id: 1292
  %1347 = select i1 %1346, i32 %1342, i32 %1345		; visa id: 1294
  %1348 = sitofp i32 %1347 to float		; visa id: 1295
  %1349 = fmul float %1081, %1348		; visa id: 1296
  br label %1358, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1297

1350:                                             ; preds = %1341
; BB141 :
  %1351 = uitofp i32 %1342 to float		; visa id: 1299
  %1352 = fmul float %1081, %1351		; visa id: 1300
  %1353 = and i32 %120, 134217728
  %1354 = icmp eq i32 %1353, 0		; visa id: 1301
  %1355 = select i1 %1354, i32 1, i32 -1		; visa id: 1303
  %1356 = sitofp i32 %1355 to float		; visa id: 1304
  %1357 = fmul float %1352, %1356		; visa id: 1305
  br label %1358, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1306

1358:                                             ; preds = %1350, %1343
; BB142 :
  %.sroa.88.5 = phi float [ %1357, %1350 ], [ %1349, %1343 ]
  %1359 = and i32 %1033, 255		; visa id: 1307
  br i1 %1088, label %1367, label %1360, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1308

1360:                                             ; preds = %1358
; BB143 :
  %1361 = and i32 %120, 268435456
  %1362 = sub nsw i32 0, %1359, !spirv.Decorations !8798
  %1363 = icmp eq i32 %1361, 0		; visa id: 1310
  %1364 = select i1 %1363, i32 %1359, i32 %1362		; visa id: 1312
  %1365 = sitofp i32 %1364 to float		; visa id: 1313
  %1366 = fmul float %1081, %1365		; visa id: 1314
  br label %1375, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1315

1367:                                             ; preds = %1358
; BB144 :
  %1368 = uitofp i32 %1359 to float		; visa id: 1317
  %1369 = fmul float %1081, %1368		; visa id: 1318
  %1370 = and i32 %120, 268435456
  %1371 = icmp eq i32 %1370, 0		; visa id: 1319
  %1372 = select i1 %1371, i32 1, i32 -1		; visa id: 1321
  %1373 = sitofp i32 %1372 to float		; visa id: 1322
  %1374 = fmul float %1369, %1373		; visa id: 1323
  br label %1375, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1324

1375:                                             ; preds = %1367, %1360
; BB145 :
  %.sroa.112.5 = phi float [ %1374, %1367 ], [ %1366, %1360 ]
  %1376 = bitcast i32 %1033 to <4 x i8>
  %1377 = extractelement <4 x i8> %1376, i32 1
  %1378 = zext i8 %1377 to i32		; visa id: 1325
  br i1 %1088, label %1386, label %1379, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1326

1379:                                             ; preds = %1375
; BB146 :
  %1380 = and i32 %120, 536870912
  %1381 = sub nsw i32 0, %1378, !spirv.Decorations !8798
  %1382 = icmp eq i32 %1380, 0		; visa id: 1328
  %1383 = select i1 %1382, i32 %1378, i32 %1381		; visa id: 1330
  %1384 = sitofp i32 %1383 to float		; visa id: 1331
  %1385 = fmul float %1081, %1384		; visa id: 1332
  br label %1394, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1333

1386:                                             ; preds = %1375
; BB147 :
  %1387 = uitofp i32 %1378 to float		; visa id: 1335
  %1388 = fmul float %1081, %1387		; visa id: 1336
  %1389 = and i32 %120, 536870912
  %1390 = icmp eq i32 %1389, 0		; visa id: 1337
  %1391 = select i1 %1390, i32 1, i32 -1		; visa id: 1339
  %1392 = sitofp i32 %1391 to float		; visa id: 1340
  %1393 = fmul float %1388, %1392		; visa id: 1341
  br label %1394, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1342

1394:                                             ; preds = %1386, %1379
; BB148 :
  %.sroa.136.5 = phi float [ %1393, %1386 ], [ %1385, %1379 ]
  %1395 = extractelement <4 x i8> %1376, i32 2
  %1396 = zext i8 %1395 to i32		; visa id: 1343
  br i1 %1088, label %1404, label %1397, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1344

1397:                                             ; preds = %1394
; BB149 :
  %1398 = and i32 %120, 1073741824
  %1399 = sub nsw i32 0, %1396, !spirv.Decorations !8798
  %1400 = icmp eq i32 %1398, 0		; visa id: 1346
  %1401 = select i1 %1400, i32 %1396, i32 %1399		; visa id: 1348
  %1402 = sitofp i32 %1401 to float		; visa id: 1349
  %1403 = fmul float %1081, %1402		; visa id: 1350
  br label %1412, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1351

1404:                                             ; preds = %1394
; BB150 :
  %1405 = uitofp i32 %1396 to float		; visa id: 1353
  %1406 = fmul float %1081, %1405		; visa id: 1354
  %1407 = and i32 %120, 1073741824
  %1408 = icmp eq i32 %1407, 0		; visa id: 1355
  %1409 = select i1 %1408, i32 1, i32 -1		; visa id: 1357
  %1410 = sitofp i32 %1409 to float		; visa id: 1358
  %1411 = fmul float %1406, %1410		; visa id: 1359
  br label %1412, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1360

1412:                                             ; preds = %1404, %1397
; BB151 :
  %.sroa.160.5 = phi float [ %1411, %1404 ], [ %1403, %1397 ]
  %1413 = lshr i32 %1033, 24		; visa id: 1361
  br i1 %1088, label %1420, label %1414, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1362

1414:                                             ; preds = %1412
; BB152 :
  %1415 = sub nsw i32 0, %1413, !spirv.Decorations !8798
  %1416 = icmp slt i32 %120, 0		; visa id: 1364
  %1417 = select i1 %1416, i32 %1415, i32 %1413		; visa id: 1365
  %1418 = sitofp i32 %1417 to float		; visa id: 1366
  %1419 = fmul float %1081, %1418		; visa id: 1367
  br label %.preheader1.1.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1368

1420:                                             ; preds = %1412
; BB153 :
  %1421 = uitofp i32 %1413 to float		; visa id: 1370
  %1422 = fmul float %1081, %1421		; visa id: 1371
  %1423 = icmp sgt i32 %120, -1		; visa id: 1372
  %1424 = select i1 %1423, i32 1, i32 -1		; visa id: 1373
  %1425 = sitofp i32 %1424 to float		; visa id: 1374
  %1426 = fmul float %1422, %1425		; visa id: 1375
  br label %.preheader1.1.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1376

.preheader1.1.1:                                  ; preds = %1420, %1414
; BB154 :
  %.sroa.184.5 = phi float [ %1426, %1420 ], [ %1419, %1414 ]
  %1427 = zext i16 %1278 to i32		; visa id: 1377
  %1428 = shl nuw i32 %1427, 16, !spirv.Decorations !8788		; visa id: 1378
  %1429 = bitcast i32 %1428 to float
  %1430 = fmul float %.sroa.069.5, %1429		; visa id: 1379
  %1431 = fadd float %.sroa.28.0, %1430		; visa id: 1380
  %1432 = zext i16 %1279 to i32		; visa id: 1381
  %1433 = shl nuw i32 %1432, 16, !spirv.Decorations !8788		; visa id: 1382
  %1434 = bitcast i32 %1433 to float
  %1435 = fmul float %.sroa.40.5, %1434		; visa id: 1383
  %1436 = fadd float %1431, %1435		; visa id: 1384
  %1437 = zext i16 %1280 to i32		; visa id: 1385
  %1438 = shl nuw i32 %1437, 16, !spirv.Decorations !8788		; visa id: 1386
  %1439 = bitcast i32 %1438 to float
  %1440 = fmul float %.sroa.64.5, %1439		; visa id: 1387
  %1441 = fadd float %1436, %1440		; visa id: 1388
  %1442 = zext i16 %1281 to i32		; visa id: 1389
  %1443 = shl nuw i32 %1442, 16, !spirv.Decorations !8788		; visa id: 1390
  %1444 = bitcast i32 %1443 to float
  %1445 = fmul float %.sroa.88.5, %1444		; visa id: 1391
  %1446 = fadd float %1441, %1445		; visa id: 1392
  %1447 = zext i16 %1284 to i32		; visa id: 1393
  %1448 = shl nuw i32 %1447, 16, !spirv.Decorations !8788		; visa id: 1394
  %1449 = bitcast i32 %1448 to float
  %1450 = fmul float %.sroa.112.5, %1449		; visa id: 1395
  %1451 = fadd float %1446, %1450		; visa id: 1396
  %1452 = zext i16 %1285 to i32		; visa id: 1397
  %1453 = shl nuw i32 %1452, 16, !spirv.Decorations !8788		; visa id: 1398
  %1454 = bitcast i32 %1453 to float
  %1455 = fmul float %.sroa.136.5, %1454		; visa id: 1399
  %1456 = fadd float %1451, %1455		; visa id: 1400
  %1457 = zext i16 %1286 to i32		; visa id: 1401
  %1458 = shl nuw i32 %1457, 16, !spirv.Decorations !8788		; visa id: 1402
  %1459 = bitcast i32 %1458 to float
  %1460 = fmul float %.sroa.160.5, %1459		; visa id: 1403
  %1461 = fadd float %1456, %1460		; visa id: 1404
  %1462 = zext i16 %1287 to i32		; visa id: 1405
  %1463 = shl nuw i32 %1462, 16, !spirv.Decorations !8788		; visa id: 1406
  %1464 = bitcast i32 %1463 to float
  %1465 = fmul float %.sroa.184.5, %1464		; visa id: 1407
  %1466 = fadd float %1461, %1465		; visa id: 1408
  %1467 = or i32 %193, 96		; visa id: 1409
  %1468 = zext i32 %1467 to i64		; visa id: 1410
  %1469 = add i64 %1468, %const_reg_qword2		; visa id: 1411
  %IntToPtr2369 = inttoptr i64 %1469 to ptr addrspace(1)		; visa id: 1412
  %vCastload370 = load i32, ptr addrspace(1) %IntToPtr2369, align 2		; visa id: 1412
  %1470 = add i64 %1469, 4
  %IntToPtr2371 = inttoptr i64 %1470 to ptr addrspace(1)
  %vCastload372 = load i32, ptr addrspace(1) %IntToPtr2371, align 2		; visa id: 1413
  %1471 = add i64 %1469, 8
  %IntToPtr2373 = inttoptr i64 %1471 to ptr addrspace(1)
  %vCastload374 = load i32, ptr addrspace(1) %IntToPtr2373, align 2		; visa id: 1414
  %1472 = add i64 %1469, 12
  %IntToPtr2375 = inttoptr i64 %1472 to ptr addrspace(1)
  %vCastload376 = load i32, ptr addrspace(1) %IntToPtr2375, align 2		; visa id: 1415
  %1473 = bitcast i32 %vCastload370 to <2 x i16>		; visa id: 1416
  %1474 = bitcast i32 %vCastload372 to <2 x i16>		; visa id: 1418
  %1475 = extractelement <2 x i16> %1473, i32 0		; visa id: 1420
  %1476 = extractelement <2 x i16> %1473, i32 1		; visa id: 1420
  %1477 = extractelement <2 x i16> %1474, i32 0		; visa id: 1420
  %1478 = extractelement <2 x i16> %1474, i32 1		; visa id: 1420
  %1479 = bitcast i32 %vCastload374 to <2 x i16>		; visa id: 1420
  %1480 = bitcast i32 %vCastload376 to <2 x i16>		; visa id: 1422
  %1481 = extractelement <2 x i16> %1479, i32 0		; visa id: 1424
  %1482 = extractelement <2 x i16> %1479, i32 1		; visa id: 1424
  %1483 = extractelement <2 x i16> %1480, i32 0		; visa id: 1424
  %1484 = extractelement <2 x i16> %1480, i32 1		; visa id: 1424
  %1485 = lshr i32 %1076, 4		; visa id: 1424
  %1486 = uitofp i32 %1485 to float		; visa id: 1425
  %1487 = fadd float %1486, 5.000000e-01		; visa id: 1426
  %1488 = fmul float %137, %1487		; visa id: 1427
  %1489 = fmul float %1488, 2.500000e-01		; visa id: 1428
  %1490 = bitcast float %1489 to i32
  %1491 = and i32 %1490, 2147483647		; visa id: 1429
  %1492 = icmp ugt i32 %1491, 2139095040
  %1493 = fcmp oeq float %152, 0x7FF0000000000000		; visa id: 1430
  %1494 = fcmp une float %152, %152
  %1495 = or i1 %1494, %1493		; visa id: 1431
  %1496 = or i1 %1495, %1492		; visa id: 1433
  %1497 = and i32 %1054, 255		; visa id: 1435
  br i1 %1496, label %1505, label %1498, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1436

1498:                                             ; preds = %.preheader1.1.1
; BB155 :
  %1499 = and i32 %121, 256
  %1500 = sub nsw i32 0, %1497, !spirv.Decorations !8798
  %1501 = icmp eq i32 %1499, 0		; visa id: 1438
  %1502 = select i1 %1501, i32 %1497, i32 %1500		; visa id: 1440
  %1503 = sitofp i32 %1502 to float		; visa id: 1441
  %1504 = fmul float %1489, %1503		; visa id: 1442
  br label %1513, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1443

1505:                                             ; preds = %.preheader1.1.1
; BB156 :
  %1506 = uitofp i32 %1497 to float		; visa id: 1445
  %1507 = fmul float %1489, %1506		; visa id: 1446
  %1508 = and i32 %121, 256
  %1509 = icmp eq i32 %1508, 0		; visa id: 1447
  %1510 = select i1 %1509, i32 1, i32 -1		; visa id: 1449
  %1511 = sitofp i32 %1510 to float		; visa id: 1450
  %1512 = fmul float %1507, %1511		; visa id: 1451
  br label %1513, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1452

1513:                                             ; preds = %1505, %1498
; BB157 :
  %.sroa.069.6 = phi float [ %1512, %1505 ], [ %1504, %1498 ]
  %1514 = bitcast i32 %1054 to <4 x i8>
  %1515 = extractelement <4 x i8> %1514, i32 1
  %1516 = zext i8 %1515 to i32		; visa id: 1453
  br i1 %1496, label %1524, label %1517, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1454

1517:                                             ; preds = %1513
; BB158 :
  %1518 = and i32 %121, 512
  %1519 = sub nsw i32 0, %1516, !spirv.Decorations !8798
  %1520 = icmp eq i32 %1518, 0		; visa id: 1456
  %1521 = select i1 %1520, i32 %1516, i32 %1519		; visa id: 1458
  %1522 = sitofp i32 %1521 to float		; visa id: 1459
  %1523 = fmul float %1489, %1522		; visa id: 1460
  br label %1532, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1461

1524:                                             ; preds = %1513
; BB159 :
  %1525 = uitofp i32 %1516 to float		; visa id: 1463
  %1526 = fmul float %1489, %1525		; visa id: 1464
  %1527 = and i32 %121, 512
  %1528 = icmp eq i32 %1527, 0		; visa id: 1465
  %1529 = select i1 %1528, i32 1, i32 -1		; visa id: 1467
  %1530 = sitofp i32 %1529 to float		; visa id: 1468
  %1531 = fmul float %1526, %1530		; visa id: 1469
  br label %1532, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1470

1532:                                             ; preds = %1524, %1517
; BB160 :
  %.sroa.40.6 = phi float [ %1531, %1524 ], [ %1523, %1517 ]
  %1533 = extractelement <4 x i8> %1514, i32 2
  %1534 = zext i8 %1533 to i32		; visa id: 1471
  br i1 %1496, label %1542, label %1535, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1472

1535:                                             ; preds = %1532
; BB161 :
  %1536 = and i32 %121, 1024
  %1537 = sub nsw i32 0, %1534, !spirv.Decorations !8798
  %1538 = icmp eq i32 %1536, 0		; visa id: 1474
  %1539 = select i1 %1538, i32 %1534, i32 %1537		; visa id: 1476
  %1540 = sitofp i32 %1539 to float		; visa id: 1477
  %1541 = fmul float %1489, %1540		; visa id: 1478
  br label %1550, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1479

1542:                                             ; preds = %1532
; BB162 :
  %1543 = uitofp i32 %1534 to float		; visa id: 1481
  %1544 = fmul float %1489, %1543		; visa id: 1482
  %1545 = and i32 %121, 1024
  %1546 = icmp eq i32 %1545, 0		; visa id: 1483
  %1547 = select i1 %1546, i32 1, i32 -1		; visa id: 1485
  %1548 = sitofp i32 %1547 to float		; visa id: 1486
  %1549 = fmul float %1544, %1548		; visa id: 1487
  br label %1550, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1488

1550:                                             ; preds = %1542, %1535
; BB163 :
  %.sroa.64.6 = phi float [ %1549, %1542 ], [ %1541, %1535 ]
  %1551 = lshr i32 %1054, 24		; visa id: 1489
  br i1 %1496, label %1559, label %1552, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1490

1552:                                             ; preds = %1550
; BB164 :
  %1553 = and i32 %121, 2048
  %1554 = sub nsw i32 0, %1551, !spirv.Decorations !8798
  %1555 = icmp eq i32 %1553, 0		; visa id: 1492
  %1556 = select i1 %1555, i32 %1551, i32 %1554		; visa id: 1494
  %1557 = sitofp i32 %1556 to float		; visa id: 1495
  %1558 = fmul float %1489, %1557		; visa id: 1496
  br label %1567, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1497

1559:                                             ; preds = %1550
; BB165 :
  %1560 = uitofp i32 %1551 to float		; visa id: 1499
  %1561 = fmul float %1489, %1560		; visa id: 1500
  %1562 = and i32 %121, 2048
  %1563 = icmp eq i32 %1562, 0		; visa id: 1501
  %1564 = select i1 %1563, i32 1, i32 -1		; visa id: 1503
  %1565 = sitofp i32 %1564 to float		; visa id: 1504
  %1566 = fmul float %1561, %1565		; visa id: 1505
  br label %1567, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1506

1567:                                             ; preds = %1559, %1552
; BB166 :
  %.sroa.88.6 = phi float [ %1566, %1559 ], [ %1558, %1552 ]
  %1568 = and i32 %1055, 255		; visa id: 1507
  br i1 %1496, label %1576, label %1569, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1508

1569:                                             ; preds = %1567
; BB167 :
  %1570 = and i32 %121, 4096
  %1571 = sub nsw i32 0, %1568, !spirv.Decorations !8798
  %1572 = icmp eq i32 %1570, 0		; visa id: 1510
  %1573 = select i1 %1572, i32 %1568, i32 %1571		; visa id: 1512
  %1574 = sitofp i32 %1573 to float		; visa id: 1513
  %1575 = fmul float %1489, %1574		; visa id: 1514
  br label %1584, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1515

1576:                                             ; preds = %1567
; BB168 :
  %1577 = uitofp i32 %1568 to float		; visa id: 1517
  %1578 = fmul float %1489, %1577		; visa id: 1518
  %1579 = and i32 %121, 4096
  %1580 = icmp eq i32 %1579, 0		; visa id: 1519
  %1581 = select i1 %1580, i32 1, i32 -1		; visa id: 1521
  %1582 = sitofp i32 %1581 to float		; visa id: 1522
  %1583 = fmul float %1578, %1582		; visa id: 1523
  br label %1584, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1524

1584:                                             ; preds = %1576, %1569
; BB169 :
  %.sroa.112.6 = phi float [ %1583, %1576 ], [ %1575, %1569 ]
  %1585 = bitcast i32 %1055 to <4 x i8>
  %1586 = extractelement <4 x i8> %1585, i32 1
  %1587 = zext i8 %1586 to i32		; visa id: 1525
  br i1 %1496, label %1595, label %1588, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1526

1588:                                             ; preds = %1584
; BB170 :
  %1589 = and i32 %121, 8192
  %1590 = sub nsw i32 0, %1587, !spirv.Decorations !8798
  %1591 = icmp eq i32 %1589, 0		; visa id: 1528
  %1592 = select i1 %1591, i32 %1587, i32 %1590		; visa id: 1530
  %1593 = sitofp i32 %1592 to float		; visa id: 1531
  %1594 = fmul float %1489, %1593		; visa id: 1532
  br label %1603, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1533

1595:                                             ; preds = %1584
; BB171 :
  %1596 = uitofp i32 %1587 to float		; visa id: 1535
  %1597 = fmul float %1489, %1596		; visa id: 1536
  %1598 = and i32 %121, 8192
  %1599 = icmp eq i32 %1598, 0		; visa id: 1537
  %1600 = select i1 %1599, i32 1, i32 -1		; visa id: 1539
  %1601 = sitofp i32 %1600 to float		; visa id: 1540
  %1602 = fmul float %1597, %1601		; visa id: 1541
  br label %1603, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1542

1603:                                             ; preds = %1595, %1588
; BB172 :
  %.sroa.136.6 = phi float [ %1602, %1595 ], [ %1594, %1588 ]
  %1604 = extractelement <4 x i8> %1585, i32 2
  %1605 = zext i8 %1604 to i32		; visa id: 1543
  br i1 %1496, label %1613, label %1606, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1544

1606:                                             ; preds = %1603
; BB173 :
  %1607 = and i32 %121, 16384
  %1608 = sub nsw i32 0, %1605, !spirv.Decorations !8798
  %1609 = icmp eq i32 %1607, 0		; visa id: 1546
  %1610 = select i1 %1609, i32 %1605, i32 %1608		; visa id: 1548
  %1611 = sitofp i32 %1610 to float		; visa id: 1549
  %1612 = fmul float %1489, %1611		; visa id: 1550
  br label %1621, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1551

1613:                                             ; preds = %1603
; BB174 :
  %1614 = uitofp i32 %1605 to float		; visa id: 1553
  %1615 = fmul float %1489, %1614		; visa id: 1554
  %1616 = and i32 %121, 16384
  %1617 = icmp eq i32 %1616, 0		; visa id: 1555
  %1618 = select i1 %1617, i32 1, i32 -1		; visa id: 1557
  %1619 = sitofp i32 %1618 to float		; visa id: 1558
  %1620 = fmul float %1615, %1619		; visa id: 1559
  br label %1621, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1560

1621:                                             ; preds = %1613, %1606
; BB175 :
  %.sroa.160.6 = phi float [ %1620, %1613 ], [ %1612, %1606 ]
  %1622 = lshr i32 %1055, 24		; visa id: 1561
  br i1 %1496, label %1630, label %1623, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1562

1623:                                             ; preds = %1621
; BB176 :
  %1624 = and i32 %121, 32768
  %1625 = sub nsw i32 0, %1622, !spirv.Decorations !8798
  %1626 = icmp eq i32 %1624, 0		; visa id: 1564
  %1627 = select i1 %1626, i32 %1622, i32 %1625		; visa id: 1566
  %1628 = sitofp i32 %1627 to float		; visa id: 1567
  %1629 = fmul float %1489, %1628		; visa id: 1568
  br label %.preheader1.2.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1569

1630:                                             ; preds = %1621
; BB177 :
  %1631 = uitofp i32 %1622 to float		; visa id: 1571
  %1632 = fmul float %1489, %1631		; visa id: 1572
  %1633 = and i32 %121, 32768
  %1634 = icmp eq i32 %1633, 0		; visa id: 1573
  %1635 = select i1 %1634, i32 1, i32 -1		; visa id: 1575
  %1636 = sitofp i32 %1635 to float		; visa id: 1576
  %1637 = fmul float %1632, %1636		; visa id: 1577
  br label %.preheader1.2.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1578

.preheader1.2.1:                                  ; preds = %1630, %1623
; BB178 :
  %.sroa.184.6 = phi float [ %1637, %1630 ], [ %1629, %1623 ]
  %1638 = zext i16 %1475 to i32		; visa id: 1579
  %1639 = shl nuw i32 %1638, 16, !spirv.Decorations !8788		; visa id: 1580
  %1640 = bitcast i32 %1639 to float
  %1641 = fmul float %.sroa.069.6, %1640		; visa id: 1581
  %1642 = fadd float %.sroa.31.0, %1641		; visa id: 1582
  %1643 = zext i16 %1476 to i32		; visa id: 1583
  %1644 = shl nuw i32 %1643, 16, !spirv.Decorations !8788		; visa id: 1584
  %1645 = bitcast i32 %1644 to float
  %1646 = fmul float %.sroa.40.6, %1645		; visa id: 1585
  %1647 = fadd float %1642, %1646		; visa id: 1586
  %1648 = zext i16 %1477 to i32		; visa id: 1587
  %1649 = shl nuw i32 %1648, 16, !spirv.Decorations !8788		; visa id: 1588
  %1650 = bitcast i32 %1649 to float
  %1651 = fmul float %.sroa.64.6, %1650		; visa id: 1589
  %1652 = fadd float %1647, %1651		; visa id: 1590
  %1653 = zext i16 %1478 to i32		; visa id: 1591
  %1654 = shl nuw i32 %1653, 16, !spirv.Decorations !8788		; visa id: 1592
  %1655 = bitcast i32 %1654 to float
  %1656 = fmul float %.sroa.88.6, %1655		; visa id: 1593
  %1657 = fadd float %1652, %1656		; visa id: 1594
  %1658 = zext i16 %1481 to i32		; visa id: 1595
  %1659 = shl nuw i32 %1658, 16, !spirv.Decorations !8788		; visa id: 1596
  %1660 = bitcast i32 %1659 to float
  %1661 = fmul float %.sroa.112.6, %1660		; visa id: 1597
  %1662 = fadd float %1657, %1661		; visa id: 1598
  %1663 = zext i16 %1482 to i32		; visa id: 1599
  %1664 = shl nuw i32 %1663, 16, !spirv.Decorations !8788		; visa id: 1600
  %1665 = bitcast i32 %1664 to float
  %1666 = fmul float %.sroa.136.6, %1665		; visa id: 1601
  %1667 = fadd float %1662, %1666		; visa id: 1602
  %1668 = zext i16 %1483 to i32		; visa id: 1603
  %1669 = shl nuw i32 %1668, 16, !spirv.Decorations !8788		; visa id: 1604
  %1670 = bitcast i32 %1669 to float
  %1671 = fmul float %.sroa.160.6, %1670		; visa id: 1605
  %1672 = fadd float %1667, %1671		; visa id: 1606
  %1673 = zext i16 %1484 to i32		; visa id: 1607
  %1674 = shl nuw i32 %1673, 16, !spirv.Decorations !8788		; visa id: 1608
  %1675 = bitcast i32 %1674 to float
  %1676 = fmul float %.sroa.184.6, %1675		; visa id: 1609
  %1677 = fadd float %1672, %1676		; visa id: 1610
  %1678 = or i32 %193, 112		; visa id: 1611
  %1679 = zext i32 %1678 to i64		; visa id: 1612
  %1680 = add i64 %1679, %const_reg_qword2		; visa id: 1613
  %IntToPtr2377 = inttoptr i64 %1680 to ptr addrspace(1)		; visa id: 1614
  %vCastload378 = load i32, ptr addrspace(1) %IntToPtr2377, align 2		; visa id: 1614
  %1681 = add i64 %1680, 4
  %IntToPtr2379 = inttoptr i64 %1681 to ptr addrspace(1)
  %vCastload380 = load i32, ptr addrspace(1) %IntToPtr2379, align 2		; visa id: 1615
  %1682 = add i64 %1680, 8
  %IntToPtr2381 = inttoptr i64 %1682 to ptr addrspace(1)
  %vCastload382 = load i32, ptr addrspace(1) %IntToPtr2381, align 2		; visa id: 1616
  %1683 = add i64 %1680, 12
  %IntToPtr2383 = inttoptr i64 %1683 to ptr addrspace(1)
  %vCastload384 = load i32, ptr addrspace(1) %IntToPtr2383, align 2		; visa id: 1617
  %1684 = bitcast i32 %vCastload378 to <2 x i16>		; visa id: 1618
  %1685 = bitcast i32 %vCastload380 to <2 x i16>		; visa id: 1620
  %1686 = extractelement <2 x i16> %1684, i32 0		; visa id: 1622
  %1687 = extractelement <2 x i16> %1684, i32 1		; visa id: 1622
  %1688 = extractelement <2 x i16> %1685, i32 0		; visa id: 1622
  %1689 = extractelement <2 x i16> %1685, i32 1		; visa id: 1622
  %1690 = bitcast i32 %vCastload382 to <2 x i16>		; visa id: 1622
  %1691 = bitcast i32 %vCastload384 to <2 x i16>		; visa id: 1624
  %1692 = extractelement <2 x i16> %1690, i32 0		; visa id: 1626
  %1693 = extractelement <2 x i16> %1690, i32 1		; visa id: 1626
  %1694 = extractelement <2 x i16> %1691, i32 0		; visa id: 1626
  %1695 = extractelement <2 x i16> %1691, i32 1		; visa id: 1626
  %1696 = and i32 %1056, 255		; visa id: 1626
  br i1 %1496, label %1704, label %1697, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1627

1697:                                             ; preds = %.preheader1.2.1
; BB179 :
  %1698 = and i32 %121, 16777216
  %1699 = sub nsw i32 0, %1696, !spirv.Decorations !8798
  %1700 = icmp eq i32 %1698, 0		; visa id: 1629
  %1701 = select i1 %1700, i32 %1696, i32 %1699		; visa id: 1631
  %1702 = sitofp i32 %1701 to float		; visa id: 1632
  %1703 = fmul float %1489, %1702		; visa id: 1633
  br label %1712, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1634

1704:                                             ; preds = %.preheader1.2.1
; BB180 :
  %1705 = uitofp i32 %1696 to float		; visa id: 1636
  %1706 = fmul float %1489, %1705		; visa id: 1637
  %1707 = and i32 %121, 16777216
  %1708 = icmp eq i32 %1707, 0		; visa id: 1638
  %1709 = select i1 %1708, i32 1, i32 -1		; visa id: 1640
  %1710 = sitofp i32 %1709 to float		; visa id: 1641
  %1711 = fmul float %1706, %1710		; visa id: 1642
  br label %1712, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1643

1712:                                             ; preds = %1704, %1697
; BB181 :
  %.sroa.069.7 = phi float [ %1711, %1704 ], [ %1703, %1697 ]
  %1713 = bitcast i32 %1056 to <4 x i8>
  %1714 = extractelement <4 x i8> %1713, i32 1
  %1715 = zext i8 %1714 to i32		; visa id: 1644
  br i1 %1496, label %1723, label %1716, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1645

1716:                                             ; preds = %1712
; BB182 :
  %1717 = and i32 %121, 33554432
  %1718 = sub nsw i32 0, %1715, !spirv.Decorations !8798
  %1719 = icmp eq i32 %1717, 0		; visa id: 1647
  %1720 = select i1 %1719, i32 %1715, i32 %1718		; visa id: 1649
  %1721 = sitofp i32 %1720 to float		; visa id: 1650
  %1722 = fmul float %1489, %1721		; visa id: 1651
  br label %1731, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1652

1723:                                             ; preds = %1712
; BB183 :
  %1724 = uitofp i32 %1715 to float		; visa id: 1654
  %1725 = fmul float %1489, %1724		; visa id: 1655
  %1726 = and i32 %121, 33554432
  %1727 = icmp eq i32 %1726, 0		; visa id: 1656
  %1728 = select i1 %1727, i32 1, i32 -1		; visa id: 1658
  %1729 = sitofp i32 %1728 to float		; visa id: 1659
  %1730 = fmul float %1725, %1729		; visa id: 1660
  br label %1731, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1661

1731:                                             ; preds = %1723, %1716
; BB184 :
  %.sroa.40.7 = phi float [ %1730, %1723 ], [ %1722, %1716 ]
  %1732 = extractelement <4 x i8> %1713, i32 2
  %1733 = zext i8 %1732 to i32		; visa id: 1662
  br i1 %1496, label %1741, label %1734, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1663

1734:                                             ; preds = %1731
; BB185 :
  %1735 = and i32 %121, 67108864
  %1736 = sub nsw i32 0, %1733, !spirv.Decorations !8798
  %1737 = icmp eq i32 %1735, 0		; visa id: 1665
  %1738 = select i1 %1737, i32 %1733, i32 %1736		; visa id: 1667
  %1739 = sitofp i32 %1738 to float		; visa id: 1668
  %1740 = fmul float %1489, %1739		; visa id: 1669
  br label %1749, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1670

1741:                                             ; preds = %1731
; BB186 :
  %1742 = uitofp i32 %1733 to float		; visa id: 1672
  %1743 = fmul float %1489, %1742		; visa id: 1673
  %1744 = and i32 %121, 67108864
  %1745 = icmp eq i32 %1744, 0		; visa id: 1674
  %1746 = select i1 %1745, i32 1, i32 -1		; visa id: 1676
  %1747 = sitofp i32 %1746 to float		; visa id: 1677
  %1748 = fmul float %1743, %1747		; visa id: 1678
  br label %1749, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1679

1749:                                             ; preds = %1741, %1734
; BB187 :
  %.sroa.64.7 = phi float [ %1748, %1741 ], [ %1740, %1734 ]
  %1750 = lshr i32 %1056, 24		; visa id: 1680
  br i1 %1496, label %1758, label %1751, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1681

1751:                                             ; preds = %1749
; BB188 :
  %1752 = and i32 %121, 134217728
  %1753 = sub nsw i32 0, %1750, !spirv.Decorations !8798
  %1754 = icmp eq i32 %1752, 0		; visa id: 1683
  %1755 = select i1 %1754, i32 %1750, i32 %1753		; visa id: 1685
  %1756 = sitofp i32 %1755 to float		; visa id: 1686
  %1757 = fmul float %1489, %1756		; visa id: 1687
  br label %1766, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1688

1758:                                             ; preds = %1749
; BB189 :
  %1759 = uitofp i32 %1750 to float		; visa id: 1690
  %1760 = fmul float %1489, %1759		; visa id: 1691
  %1761 = and i32 %121, 134217728
  %1762 = icmp eq i32 %1761, 0		; visa id: 1692
  %1763 = select i1 %1762, i32 1, i32 -1		; visa id: 1694
  %1764 = sitofp i32 %1763 to float		; visa id: 1695
  %1765 = fmul float %1760, %1764		; visa id: 1696
  br label %1766, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1697

1766:                                             ; preds = %1758, %1751
; BB190 :
  %.sroa.88.7 = phi float [ %1765, %1758 ], [ %1757, %1751 ]
  %1767 = and i32 %1057, 255		; visa id: 1698
  br i1 %1496, label %1775, label %1768, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1699

1768:                                             ; preds = %1766
; BB191 :
  %1769 = and i32 %121, 268435456
  %1770 = sub nsw i32 0, %1767, !spirv.Decorations !8798
  %1771 = icmp eq i32 %1769, 0		; visa id: 1701
  %1772 = select i1 %1771, i32 %1767, i32 %1770		; visa id: 1703
  %1773 = sitofp i32 %1772 to float		; visa id: 1704
  %1774 = fmul float %1489, %1773		; visa id: 1705
  br label %1783, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1706

1775:                                             ; preds = %1766
; BB192 :
  %1776 = uitofp i32 %1767 to float		; visa id: 1708
  %1777 = fmul float %1489, %1776		; visa id: 1709
  %1778 = and i32 %121, 268435456
  %1779 = icmp eq i32 %1778, 0		; visa id: 1710
  %1780 = select i1 %1779, i32 1, i32 -1		; visa id: 1712
  %1781 = sitofp i32 %1780 to float		; visa id: 1713
  %1782 = fmul float %1777, %1781		; visa id: 1714
  br label %1783, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1715

1783:                                             ; preds = %1775, %1768
; BB193 :
  %.sroa.112.7 = phi float [ %1782, %1775 ], [ %1774, %1768 ]
  %1784 = bitcast i32 %1057 to <4 x i8>
  %1785 = extractelement <4 x i8> %1784, i32 1
  %1786 = zext i8 %1785 to i32		; visa id: 1716
  br i1 %1496, label %1794, label %1787, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1717

1787:                                             ; preds = %1783
; BB194 :
  %1788 = and i32 %121, 536870912
  %1789 = sub nsw i32 0, %1786, !spirv.Decorations !8798
  %1790 = icmp eq i32 %1788, 0		; visa id: 1719
  %1791 = select i1 %1790, i32 %1786, i32 %1789		; visa id: 1721
  %1792 = sitofp i32 %1791 to float		; visa id: 1722
  %1793 = fmul float %1489, %1792		; visa id: 1723
  br label %1802, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1724

1794:                                             ; preds = %1783
; BB195 :
  %1795 = uitofp i32 %1786 to float		; visa id: 1726
  %1796 = fmul float %1489, %1795		; visa id: 1727
  %1797 = and i32 %121, 536870912
  %1798 = icmp eq i32 %1797, 0		; visa id: 1728
  %1799 = select i1 %1798, i32 1, i32 -1		; visa id: 1730
  %1800 = sitofp i32 %1799 to float		; visa id: 1731
  %1801 = fmul float %1796, %1800		; visa id: 1732
  br label %1802, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1733

1802:                                             ; preds = %1794, %1787
; BB196 :
  %.sroa.136.7 = phi float [ %1801, %1794 ], [ %1793, %1787 ]
  %1803 = extractelement <4 x i8> %1784, i32 2
  %1804 = zext i8 %1803 to i32		; visa id: 1734
  br i1 %1496, label %1812, label %1805, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1735

1805:                                             ; preds = %1802
; BB197 :
  %1806 = and i32 %121, 1073741824
  %1807 = sub nsw i32 0, %1804, !spirv.Decorations !8798
  %1808 = icmp eq i32 %1806, 0		; visa id: 1737
  %1809 = select i1 %1808, i32 %1804, i32 %1807		; visa id: 1739
  %1810 = sitofp i32 %1809 to float		; visa id: 1740
  %1811 = fmul float %1489, %1810		; visa id: 1741
  br label %1820, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1742

1812:                                             ; preds = %1802
; BB198 :
  %1813 = uitofp i32 %1804 to float		; visa id: 1744
  %1814 = fmul float %1489, %1813		; visa id: 1745
  %1815 = and i32 %121, 1073741824
  %1816 = icmp eq i32 %1815, 0		; visa id: 1746
  %1817 = select i1 %1816, i32 1, i32 -1		; visa id: 1748
  %1818 = sitofp i32 %1817 to float		; visa id: 1749
  %1819 = fmul float %1814, %1818		; visa id: 1750
  br label %1820, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1751

1820:                                             ; preds = %1812, %1805
; BB199 :
  %.sroa.160.7 = phi float [ %1819, %1812 ], [ %1811, %1805 ]
  %1821 = lshr i32 %1057, 24		; visa id: 1752
  br i1 %1496, label %1828, label %1822, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1753

1822:                                             ; preds = %1820
; BB200 :
  %1823 = sub nsw i32 0, %1821, !spirv.Decorations !8798
  %1824 = icmp slt i32 %121, 0		; visa id: 1755
  %1825 = select i1 %1824, i32 %1823, i32 %1821		; visa id: 1756
  %1826 = sitofp i32 %1825 to float		; visa id: 1757
  %1827 = fmul float %1489, %1826		; visa id: 1758
  br label %.preheader1.3.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1759

1828:                                             ; preds = %1820
; BB201 :
  %1829 = uitofp i32 %1821 to float		; visa id: 1761
  %1830 = fmul float %1489, %1829		; visa id: 1762
  %1831 = icmp sgt i32 %121, -1		; visa id: 1763
  %1832 = select i1 %1831, i32 1, i32 -1		; visa id: 1764
  %1833 = sitofp i32 %1832 to float		; visa id: 1765
  %1834 = fmul float %1830, %1833		; visa id: 1766
  br label %.preheader1.3.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1767

.preheader1.3.1:                                  ; preds = %1828, %1822
; BB202 :
  %.sroa.184.7 = phi float [ %1834, %1828 ], [ %1827, %1822 ]
  %1835 = zext i16 %1686 to i32		; visa id: 1768
  %1836 = shl nuw i32 %1835, 16, !spirv.Decorations !8788		; visa id: 1769
  %1837 = bitcast i32 %1836 to float
  %1838 = fmul float %.sroa.069.7, %1837		; visa id: 1770
  %1839 = fadd float %.sroa.36.0, %1838		; visa id: 1771
  %1840 = zext i16 %1687 to i32		; visa id: 1772
  %1841 = shl nuw i32 %1840, 16, !spirv.Decorations !8788		; visa id: 1773
  %1842 = bitcast i32 %1841 to float
  %1843 = fmul float %.sroa.40.7, %1842		; visa id: 1774
  %1844 = fadd float %1839, %1843		; visa id: 1775
  %1845 = zext i16 %1688 to i32		; visa id: 1776
  %1846 = shl nuw i32 %1845, 16, !spirv.Decorations !8788		; visa id: 1777
  %1847 = bitcast i32 %1846 to float
  %1848 = fmul float %.sroa.64.7, %1847		; visa id: 1778
  %1849 = fadd float %1844, %1848		; visa id: 1779
  %1850 = zext i16 %1689 to i32		; visa id: 1780
  %1851 = shl nuw i32 %1850, 16, !spirv.Decorations !8788		; visa id: 1781
  %1852 = bitcast i32 %1851 to float
  %1853 = fmul float %.sroa.88.7, %1852		; visa id: 1782
  %1854 = fadd float %1849, %1853		; visa id: 1783
  %1855 = zext i16 %1692 to i32		; visa id: 1784
  %1856 = shl nuw i32 %1855, 16, !spirv.Decorations !8788		; visa id: 1785
  %1857 = bitcast i32 %1856 to float
  %1858 = fmul float %.sroa.112.7, %1857		; visa id: 1786
  %1859 = fadd float %1854, %1858		; visa id: 1787
  %1860 = zext i16 %1693 to i32		; visa id: 1788
  %1861 = shl nuw i32 %1860, 16, !spirv.Decorations !8788		; visa id: 1789
  %1862 = bitcast i32 %1861 to float
  %1863 = fmul float %.sroa.136.7, %1862		; visa id: 1790
  %1864 = fadd float %1859, %1863		; visa id: 1791
  %1865 = zext i16 %1694 to i32		; visa id: 1792
  %1866 = shl nuw i32 %1865, 16, !spirv.Decorations !8788		; visa id: 1793
  %1867 = bitcast i32 %1866 to float
  %1868 = fmul float %.sroa.160.7, %1867		; visa id: 1794
  %1869 = fadd float %1864, %1868		; visa id: 1795
  %1870 = zext i16 %1695 to i32		; visa id: 1796
  %1871 = shl nuw i32 %1870, 16, !spirv.Decorations !8788		; visa id: 1797
  %1872 = bitcast i32 %1871 to float
  %1873 = fmul float %.sroa.184.7, %1872		; visa id: 1798
  %1874 = fadd float %1869, %1873		; visa id: 1799
  %1875 = icmp ult i32 %112, 9		; visa id: 1800
  br i1 %1875, label %.preheader1.3.1..preheader2.preheader_crit_edge, label %.preheader.preheader, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1801

.preheader1.3.1..preheader2.preheader_crit_edge:  ; preds = %.preheader1.3.1
; BB203 :
  %1876 = add nuw nsw i32 %112, 1, !spirv.Decorations !8791		; visa id: 1803
  br label %.preheader2.preheader, !stats.blockFrequency.digits !8799, !stats.blockFrequency.scale !8797		; visa id: 1804

.preheader.preheader:                             ; preds = %.preheader1.3.1
; BB204 :
  %.lcssa391 = phi float [ %1874, %.preheader1.3.1 ]
  %.lcssa390 = phi float [ %1677, %.preheader1.3.1 ]
  %.lcssa389 = phi float [ %1466, %.preheader1.3.1 ]
  %.lcssa388 = phi float [ %1269, %.preheader1.3.1 ]
  %.lcssa387 = phi float [ %1009, %.preheader1.3.1 ]
  %.lcssa386 = phi float [ %812, %.preheader1.3.1 ]
  %.lcssa385 = phi float [ %601, %.preheader1.3.1 ]
  %.lcssa = phi float [ %404, %.preheader1.3.1 ]
  %1877 = fadd float %.lcssa, %.lcssa385		; visa id: 1806
  %1878 = fadd float %.lcssa386, %.lcssa387		; visa id: 1807
  %1879 = fadd float %.lcssa388, %.lcssa389		; visa id: 1808
  %1880 = fadd float %.lcssa390, %.lcssa391		; visa id: 1809
  %1881 = fadd float %1877, %1878		; visa id: 1810
  %1882 = fadd float %1879, %1880		; visa id: 1811
  %1883 = fadd float %1881, %1882		; visa id: 1812
  br label %._crit_edge, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8790		; visa id: 1815

._crit_edge:                                      ; preds = %.._crit_edge_crit_edge, %precompiled_u32divrem_sp.exit.._crit_edge_crit_edge, %._crit_edge44, %.preheader.preheader
; BB205 :
  %1884 = phi i32 [ -1, %.preheader.preheader ], [ 0, %._crit_edge44 ], [ 0, %precompiled_u32divrem_sp.exit.._crit_edge_crit_edge ], [ 0, %.._crit_edge_crit_edge ]
  %1885 = phi i32 [ 0, %.preheader.preheader ], [ %55, %._crit_edge44 ], [ -1, %precompiled_u32divrem_sp.exit.._crit_edge_crit_edge ], [ -1, %.._crit_edge_crit_edge ]
  %1886 = phi float [ %1883, %.preheader.preheader ], [ 0.000000e+00, %._crit_edge44 ], [ 0.000000e+00, %precompiled_u32divrem_sp.exit.._crit_edge_crit_edge ], [ 0.000000e+00, %.._crit_edge_crit_edge ]
  %1887 = add nuw nsw i32 %simdLaneId, 1		; visa id: 1816
  %1888 = and i32 %1887, 31		; visa id: 1817
  %simdShuffle = call float @llvm.genx.GenISA.WaveShuffleIndex.f32(float %1886, i32 %1888, i32 0)		; visa id: 1818
  %1889 = and i32 %simdLaneId, 1
  %1890 = icmp eq i32 %1889, 0		; visa id: 1825
  %1891 = select i1 %1890, float %simdShuffle, float -0.000000e+00		; visa id: 1827
  %1892 = fadd float %1886, %1891		; visa id: 1828
  %1893 = add nuw nsw i32 %simdLaneId, 2		; visa id: 1829
  %1894 = and i32 %1893, 31		; visa id: 1830
  %simdShuffle.1 = call float @llvm.genx.GenISA.WaveShuffleIndex.f32(float %1892, i32 %1894, i32 0)		; visa id: 1831
  %1895 = icmp ne i32 %4, 0		; visa id: 1838
  %1896 = or i1 %24, %1895		; visa id: 1839
  br i1 %1896, label %._crit_edge.._crit_edge47_crit_edge, label %1897, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8782		; visa id: 1841

._crit_edge.._crit_edge47_crit_edge:              ; preds = %._crit_edge
; BB:
  br label %._crit_edge47, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787

1897:                                             ; preds = %._crit_edge
; BB207 :
  %1898 = icmp eq i32 %4, 0		; visa id: 1843
  %1899 = select i1 %1898, float %simdShuffle.1, float -0.000000e+00		; visa id: 1844
  %1900 = fadd float %1892, %1899		; visa id: 1845
  %1901 = bitcast float %1900 to i32
  %1902 = icmp ne i32 %1884, 0		; visa id: 1846
  %1903 = select i1 %1902, i32 %1901, i32 2143289344		; visa id: 1847
  %1904 = and i32 %1903, 2147483647		; visa id: 1848
  %1905 = icmp ugt i32 %1904, 2139095040		; visa id: 1849
  br i1 %1905, label %1913, label %1906, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 1850

1906:                                             ; preds = %1897
; BB208 :
  %1907 = lshr i32 %1903, 16		; visa id: 1852
  %1908 = and i32 %1907, 1		; visa id: 1853
  %1909 = add i32 %1903, %1908
  %1910 = add i32 %1909, 32767		; visa id: 1854
  %1911 = lshr i32 %1910, 16		; visa id: 1855
  %1912 = trunc i32 %1911 to i16		; visa id: 1856
  br label %1917, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 1857

1913:                                             ; preds = %1897
; BB209 :
  %1914 = lshr i32 %1903, 16		; visa id: 1859
  %1915 = trunc i32 %1914 to i16		; visa id: 1860
  %1916 = or i16 %1915, 64		; visa id: 1861
  br label %1917, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 1862

1917:                                             ; preds = %1906, %1913
; BB210 :
  %1918 = phi i16 [ %1916, %1913 ], [ %1912, %1906 ]
  %1919 = bitcast i64 %const_reg_qword12 to <2 x i32>		; visa id: 1863
  %1920 = extractelement <2 x i32> %1919, i32 0		; visa id: 1864
  %1921 = extractelement <2 x i32> %1919, i32 1		; visa id: 1864
  %1922 = bitcast i64 %const_reg_qword13 to <2 x i32>		; visa id: 1864
  %1923 = extractelement <2 x i32> %1922, i32 0		; visa id: 1865
  %1924 = extractelement <2 x i32> %1922, i32 1		; visa id: 1865
  %1925 = icmp ult i16 %localIdX, 32		; visa id: 1865
  %1926 = select i1 %1925, i32 %1920, i32 %1923		; visa id: 1866
  %1927 = select i1 %1925, i32 %1921, i32 %1924		; visa id: 1867
  %1928 = insertelement <2 x i32> undef, i32 %1926, i32 0		; visa id: 1868
  %1929 = insertelement <2 x i32> %1928, i32 %1927, i32 1		; visa id: 1869
  %1930 = bitcast <2 x i32> %1929 to i64		; visa id: 1870
  %1931 = zext i32 %7 to i64		; visa id: 1874
  %1932 = shl nuw nsw i64 %1931, 1		; visa id: 1875
  %1933 = add i64 %1930, %1932		; visa id: 1876
  %1934 = inttoptr i64 %1933 to ptr addrspace(4)		; visa id: 1877
  %1935 = addrspacecast ptr addrspace(4) %1934 to ptr addrspace(1)		; visa id: 1877
  store i16 %1918, ptr addrspace(1) %1935, align 2		; visa id: 1878
  %1936 = icmp eq i32 %7, %23		; visa id: 1880
  br i1 %1936, label %1937, label %.._crit_edge47_crit_edge, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 1881

.._crit_edge47_crit_edge:                         ; preds = %1917
; BB:
  br label %._crit_edge47, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784

1937:                                             ; preds = %1917
; BB212 :
  %1938 = bitcast i64 %const_reg_qword17 to <2 x i32>		; visa id: 1883
  %1939 = extractelement <2 x i32> %1938, i32 0		; visa id: 1884
  %1940 = extractelement <2 x i32> %1938, i32 1		; visa id: 1884
  %1941 = bitcast i64 %const_reg_qword18 to <2 x i32>		; visa id: 1884
  %1942 = extractelement <2 x i32> %1941, i32 0		; visa id: 1885
  %1943 = extractelement <2 x i32> %1941, i32 1		; visa id: 1885
  %1944 = icmp ne i32 %1885, 0		; visa id: 1885
  %1945 = sext i1 %1944 to i32		; visa id: 1886
  %1946 = sub i32 0, %1945		; visa id: 1887
  %1947 = select i1 %1925, i32 %1939, i32 %1942		; visa id: 1888
  %1948 = select i1 %1925, i32 %1940, i32 %1943		; visa id: 1889
  %1949 = insertelement <2 x i32> undef, i32 %1947, i32 0		; visa id: 1890
  %1950 = insertelement <2 x i32> %1949, i32 %1948, i32 1		; visa id: 1891
  %1951 = bitcast <2 x i32> %1950 to i64		; visa id: 1892
  %1952 = zext i32 %retval.0.i to i64		; visa id: 1896
  %1953 = shl nuw nsw i64 %1952, 2		; visa id: 1897
  %1954 = add i64 %1951, %1953		; visa id: 1898
  %1955 = inttoptr i64 %1954 to ptr addrspace(4)		; visa id: 1899
  %1956 = addrspacecast ptr addrspace(4) %1955 to ptr addrspace(1)		; visa id: 1899
  store i32 %1946, ptr addrspace(1) %1956, align 4		; visa id: 1900
  br i1 %1944, label %1957, label %.._crit_edge47_crit_edge321, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 1901

.._crit_edge47_crit_edge321:                      ; preds = %1937
; BB:
  br label %._crit_edge47, !stats.blockFrequency.digits !8800, !stats.blockFrequency.scale !8801

1957:                                             ; preds = %1937
; BB214 :
  %1958 = inttoptr i64 %const_reg_qword20 to ptr addrspace(4)		; visa id: 1903
  %1959 = addrspacecast ptr addrspace(4) %1958 to ptr addrspace(1)		; visa id: 1903
  %1960 = load i32, ptr addrspace(1) %1959, align 4		; visa id: 1904
  %1961 = icmp eq i32 %1960, 0		; visa id: 1905
  br i1 %1961, label %.._crit_edge47_crit_edge322, label %1962, !stats.blockFrequency.digits !8802, !stats.blockFrequency.scale !8803		; visa id: 1906

.._crit_edge47_crit_edge322:                      ; preds = %1957
; BB:
  br label %._crit_edge47, !stats.blockFrequency.digits !8804, !stats.blockFrequency.scale !8801

1962:                                             ; preds = %1957
; BB216 :
  %1963 = inttoptr i64 %const_reg_qword19 to ptr addrspace(4)		; visa id: 1908
  %1964 = addrspacecast ptr addrspace(4) %1963 to ptr addrspace(1)		; visa id: 1908
  %1965 = call i32 @llvm.genx.GenISA.icmpxchgatomicrawA64.i32.p1.p1(ptr addrspace(1) %1964, ptr addrspace(1) %1964, i32 0, i32 1)		; visa id: 1909
  br label %._crit_edge47, !stats.blockFrequency.digits !8805, !stats.blockFrequency.scale !8801		; visa id: 1914

._crit_edge47:                                    ; preds = %.._crit_edge47_crit_edge322, %.._crit_edge47_crit_edge321, %.._crit_edge47_crit_edge, %._crit_edge.._crit_edge47_crit_edge, %1962
; BB217 :
  ret void, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8782		; visa id: 1915
}
