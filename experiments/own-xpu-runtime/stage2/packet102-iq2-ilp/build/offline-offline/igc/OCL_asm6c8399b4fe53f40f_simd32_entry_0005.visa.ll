; ------------------------------------------------
; OCL_asm6c8399b4fe53f40f_simd32_entry_0005.visa.ll
; ------------------------------------------------
; Function Attrs: convergent nounwind
define spir_kernel void @_ZTSZZNK4p1026KernelILj1ELb1EE6submitERN4sycl3_V15queueESt4spanIKPvLm18446744073709551615EERKSt6vectorINS3_5eventESaISB_EEENKUlRNS3_7handlerEE_clESH_EUlNS3_7nd_itemILi1EEEE_(ptr byval(%"struct.p39::__generated_Bound") align 8 %0, i32 %1, <8 x i32> %r0, <3 x i32> %globalOffset, i16 %localIdX, i16 %localIdY, i16 %localIdZ, ptr addrspace(2) %constBase, ptr addrspace(1) %globalBase, ptr %privateBase, i64 %const_reg_qword, i64 %const_reg_qword1, i64 %const_reg_qword2, i64 %const_reg_qword3, i64 %const_reg_qword4, i64 %const_reg_qword5, i64 %const_reg_qword6, i64 %const_reg_qword7, i64 %const_reg_qword8, i64 %const_reg_qword9, i64 %const_reg_qword10, i64 %const_reg_qword11, i64 %const_reg_qword12, i64 %const_reg_qword13, i64 %const_reg_qword14, i64 %const_reg_qword15, i64 %const_reg_qword16, i64 %const_reg_qword17, i64 %const_reg_qword18, i64 %const_reg_qword19, i64 %const_reg_qword20, i32 %const_reg_dword, i32 %const_reg_dword21, i32 %const_reg_dword22, i32 %const_reg_dword23, i32 %const_reg_dword24, i32 %bindlessOffset, i32 %bindlessOffset25) #0 {
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
  %65 = add i64 %64, 188
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
  %102 = shl nuw nsw i32 %6, 4, !spirv.Decorations !8791		; visa id: 120
  %103 = shl nuw nsw i32 %6, 1, !spirv.Decorations !8791		; visa id: 121
  %104 = shl nuw nsw i32 %6, 6, !spirv.Decorations !8791		; visa id: 122
  %105 = add i64 %84, %const_reg_qword		; visa id: 123
  %106 = add i64 %105, 640		; visa id: 124
  %107 = add i64 %105, 720		; visa id: 125
  %108 = add i64 %105, 800		; visa id: 126
  %109 = add i64 %84, %const_reg_qword1		; visa id: 127
  %110 = add i64 %109, 640		; visa id: 128
  %111 = add i64 %109, 720		; visa id: 129
  %112 = add i64 %109, 800		; visa id: 130
  %113 = zext i32 %102 to i64		; visa id: 131
  %114 = add i64 %105, %113		; visa id: 132
  %115 = zext i32 %103 to i64		; visa id: 133
  %116 = add i64 %106, %115		; visa id: 134
  %117 = add i64 %107, %115		; visa id: 135
  %118 = add i64 %109, %113		; visa id: 136
  %119 = add i64 %110, %115		; visa id: 137
  %120 = add i64 %111, %115		; visa id: 138
  %121 = ptrtoint ptr addrspace(1) %globalBase to i64		; visa id: 139
  br label %._crit_edge43, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8790		; visa id: 158

._crit_edge43:                                    ; preds = %.._crit_edge43_crit_edge, %63
; BB9 :
  %.sroa.35.0 = phi float [ %101, %63 ], [ %3305, %.._crit_edge43_crit_edge ]
  %.sroa.33.0 = phi float [ %100, %63 ], [ %2925, %.._crit_edge43_crit_edge ]
  %.sroa.31.0 = phi float [ %99, %63 ], [ %2525, %.._crit_edge43_crit_edge ]
  %.sroa.29.0 = phi float [ %98, %63 ], [ %2146, %.._crit_edge43_crit_edge ]
  %.sroa.27.0 = phi float [ %97, %63 ], [ %1744, %.._crit_edge43_crit_edge ]
  %.sroa.25.0 = phi float [ %96, %63 ], [ %1365, %.._crit_edge43_crit_edge ]
  %.sroa.23.0 = phi float [ %95, %63 ], [ %965, %.._crit_edge43_crit_edge ]
  %.sroa.20.0 = phi float [ %94, %63 ], [ %586, %.._crit_edge43_crit_edge ]
  %.sroa.18.0 = phi float [ %93, %63 ], [ %3149, %.._crit_edge43_crit_edge ]
  %.sroa.16.0 = phi float [ %92, %63 ], [ %2759, %.._crit_edge43_crit_edge ]
  %.sroa.14.0 = phi float [ %91, %63 ], [ %2370, %.._crit_edge43_crit_edge ]
  %.sroa.12.0 = phi float [ %90, %63 ], [ %1979, %.._crit_edge43_crit_edge ]
  %.sroa.10.0 = phi float [ %89, %63 ], [ %1589, %.._crit_edge43_crit_edge ]
  %.sroa.8.0 = phi float [ %88, %63 ], [ %1199, %.._crit_edge43_crit_edge ]
  %.sroa.6.0 = phi float [ %87, %63 ], [ %810, %.._crit_edge43_crit_edge ]
  %.sroa.0.0 = phi float [ %86, %63 ], [ %409, %.._crit_edge43_crit_edge ]
  %122 = phi i32 [ 0, %63 ], [ %3307, %.._crit_edge43_crit_edge ]
  %123 = shl nuw nsw i32 %122, 6, !spirv.Decorations !8791		; visa id: 159
  %124 = shl nuw nsw i32 %122, 3, !spirv.Decorations !8791		; visa id: 160
  %125 = shl nuw nsw i32 %122, 2, !spirv.Decorations !8791		; visa id: 161
  %126 = zext i32 %123 to i64		; visa id: 162
  %127 = add i64 %114, %126		; visa id: 163
  %128 = inttoptr i64 %127 to ptr addrspace(4)		; visa id: 164
  %generic_cast_to_ptr = addrspacecast ptr addrspace(4) %128 to ptr addrspace(1)		; visa id: 164
  %129 = load <4 x i32>, ptr addrspace(1) %generic_cast_to_ptr, align 4		; visa id: 165
  %130 = extractelement <4 x i32> %129, i32 0		; visa id: 166
  %131 = extractelement <4 x i32> %129, i32 1		; visa id: 166
  %132 = extractelement <4 x i32> %129, i32 2		; visa id: 166
  %133 = extractelement <4 x i32> %129, i32 3		; visa id: 166
  %134 = zext i32 %124 to i64		; visa id: 166
  %135 = add i64 %116, %134		; visa id: 167
  %136 = inttoptr i64 %135 to ptr addrspace(4)		; visa id: 168
  %137 = addrspacecast ptr addrspace(4) %136 to ptr addrspace(1)		; visa id: 168
  %138 = load i16, ptr addrspace(1) %137, align 2, !noalias !8793		; visa id: 169
  %139 = add i64 %117, %134		; visa id: 171
  %140 = inttoptr i64 %139 to ptr addrspace(4)		; visa id: 172
  %141 = addrspacecast ptr addrspace(4) %140 to ptr addrspace(1)		; visa id: 172
  %142 = load i16, ptr addrspace(1) %141, align 2, !noalias !8793		; visa id: 173
  %143 = zext i32 %125 to i64		; visa id: 175
  %144 = add i64 %108, %143		; visa id: 176
  %145 = inttoptr i64 %144 to ptr addrspace(4)		; visa id: 177
  %146 = addrspacecast ptr addrspace(4) %145 to ptr addrspace(1)		; visa id: 177
  %147 = load float, ptr addrspace(1) %146, align 4, !noalias !8793		; visa id: 178
  %148 = add i64 %118, %126		; visa id: 179
  %149 = inttoptr i64 %148 to ptr addrspace(4)		; visa id: 180
  %generic_cast_to_ptr.1 = addrspacecast ptr addrspace(4) %149 to ptr addrspace(1)		; visa id: 180
  %150 = load <4 x i32>, ptr addrspace(1) %generic_cast_to_ptr.1, align 4		; visa id: 181
  %151 = extractelement <4 x i32> %150, i32 0		; visa id: 182
  %152 = extractelement <4 x i32> %150, i32 1		; visa id: 182
  %153 = extractelement <4 x i32> %150, i32 2		; visa id: 182
  %154 = extractelement <4 x i32> %150, i32 3		; visa id: 182
  %155 = add i64 %119, %134		; visa id: 182
  %156 = inttoptr i64 %155 to ptr addrspace(4)		; visa id: 183
  %157 = addrspacecast ptr addrspace(4) %156 to ptr addrspace(1)		; visa id: 183
  %158 = load i16, ptr addrspace(1) %157, align 2, !noalias !8793		; visa id: 184
  %159 = add i64 %120, %134		; visa id: 186
  %160 = inttoptr i64 %159 to ptr addrspace(4)		; visa id: 187
  %161 = addrspacecast ptr addrspace(4) %160 to ptr addrspace(1)		; visa id: 187
  %162 = load i16, ptr addrspace(1) %161, align 2, !noalias !8793		; visa id: 188
  %163 = add i64 %112, %143		; visa id: 190
  %164 = inttoptr i64 %163 to ptr addrspace(4)		; visa id: 191
  %165 = addrspacecast ptr addrspace(4) %164 to ptr addrspace(1)		; visa id: 191
  %166 = load float, ptr addrspace(1) %165, align 4, !noalias !8793		; visa id: 192
  %167 = and i32 %130, 255
  %168 = zext i16 %138 to i32		; visa id: 193
  %169 = shl nuw nsw i32 %168, 8, !spirv.Decorations !8791		; visa id: 194
  %170 = and i32 %169, 768		; visa id: 195
  %171 = or i32 %167, %170		; visa id: 196
  %172 = shl nuw nsw i32 %171, 3, !spirv.Decorations !8791		; visa id: 197
  %173 = zext i32 %172 to i64		; visa id: 198
  %174 = add i64 %121, %173		; visa id: 199
  %175 = inttoptr i64 %174 to ptr addrspace(1)		; visa id: 200
  %176 = load <2 x i32>, ptr addrspace(1) %175, align 4		; visa id: 200
  %177 = shl nuw nsw i32 %122, 8, !spirv.Decorations !8791		; visa id: 201
  %178 = or i32 %177, %104		; visa id: 202
  %179 = extractelement <2 x i32> %176, i32 0		; visa id: 203
  %180 = extractelement <2 x i32> %176, i32 1		; visa id: 203
  %181 = and i32 %151, 255
  %182 = zext i16 %158 to i32		; visa id: 203
  %183 = shl nuw nsw i32 %182, 8, !spirv.Decorations !8791		; visa id: 204
  %184 = and i32 %183, 768		; visa id: 205
  %185 = or i32 %181, %184		; visa id: 206
  %186 = shl nuw nsw i32 %185, 3, !spirv.Decorations !8791		; visa id: 207
  %187 = zext i32 %186 to i64		; visa id: 208
  %188 = add i64 %121, %187		; visa id: 209
  %189 = inttoptr i64 %188 to ptr addrspace(1)		; visa id: 210
  %190 = load <2 x i32>, ptr addrspace(1) %189, align 4		; visa id: 210
  %191 = shl nuw i32 %178, 1		; visa id: 211
  %192 = zext i32 %191 to i64		; visa id: 212
  %193 = add i64 %192, %const_reg_qword2		; visa id: 213
  %IntToPtr2 = inttoptr i64 %193 to ptr addrspace(1)		; visa id: 214
  %vCastload = load i32, ptr addrspace(1) %IntToPtr2, align 2		; visa id: 214
  %194 = add i64 %193, 4
  %IntToPtr2610 = inttoptr i64 %194 to ptr addrspace(1)
  %vCastload611 = load i32, ptr addrspace(1) %IntToPtr2610, align 2		; visa id: 215
  %195 = extractelement <2 x i32> %190, i32 0		; visa id: 216
  %196 = extractelement <2 x i32> %190, i32 1		; visa id: 216
  %197 = bitcast i32 %vCastload to <2 x i16>		; visa id: 216
  %198 = bitcast i32 %vCastload611 to <2 x i16>		; visa id: 218
  %199 = extractelement <2 x i16> %197, i32 0		; visa id: 220
  %200 = extractelement <2 x i16> %197, i32 1		; visa id: 220
  %201 = extractelement <2 x i16> %198, i32 0		; visa id: 220
  %202 = extractelement <2 x i16> %198, i32 1		; visa id: 220
  %203 = add i64 %193, 8
  %IntToPtr2612 = inttoptr i64 %203 to ptr addrspace(1)
  %vCastload613 = load i32, ptr addrspace(1) %IntToPtr2612, align 2		; visa id: 220
  %204 = add i64 %193, 12
  %IntToPtr2614 = inttoptr i64 %204 to ptr addrspace(1)
  %vCastload615 = load i32, ptr addrspace(1) %IntToPtr2614, align 2		; visa id: 221
  %205 = bitcast i32 %vCastload613 to <2 x i16>		; visa id: 222
  %206 = bitcast i32 %vCastload615 to <2 x i16>		; visa id: 224
  %207 = extractelement <2 x i16> %205, i32 0		; visa id: 226
  %208 = extractelement <2 x i16> %205, i32 1		; visa id: 226
  %209 = extractelement <2 x i16> %206, i32 0		; visa id: 226
  %210 = extractelement <2 x i16> %206, i32 1		; visa id: 226
  %211 = and i16 %142, 255		; visa id: 226
  %212 = zext i16 %211 to i32		; visa id: 227
  %213 = and i32 %212, 15		; visa id: 228
  %214 = uitofp i32 %213 to float		; visa id: 229
  %215 = fadd float %214, 5.000000e-01		; visa id: 230
  %216 = fmul float %147, %215		; visa id: 231
  %217 = fmul float %216, 2.500000e-01		; visa id: 232
  %218 = bitcast float %147 to i32
  %219 = and i32 %218, 2147483647		; visa id: 233
  %220 = bitcast i32 %219 to float
  %221 = fcmp une float %220, %220
  %222 = fcmp oeq float %220, 0x7FF0000000000000		; visa id: 234
  %223 = or i1 %221, %222		; visa id: 235
  %224 = bitcast float %217 to i32
  %225 = and i32 %224, 2147483647		; visa id: 237
  %226 = icmp ugt i32 %225, 2139095040
  %227 = or i1 %223, %226		; visa id: 238
  %228 = and i32 %179, 255		; visa id: 240
  br i1 %227, label %236, label %229, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 241

229:                                              ; preds = %._crit_edge43
; BB10 :
  %230 = and i32 %130, 256
  %231 = sub nsw i32 0, %228, !spirv.Decorations !8798
  %232 = icmp eq i32 %230, 0		; visa id: 243
  %233 = select i1 %232, i32 %228, i32 %231		; visa id: 245
  %234 = sitofp i32 %233 to float		; visa id: 246
  %235 = fmul float %217, %234		; visa id: 247
  br label %244, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 248

236:                                              ; preds = %._crit_edge43
; BB11 :
  %237 = uitofp i32 %228 to float		; visa id: 250
  %238 = fmul float %217, %237		; visa id: 251
  %239 = and i32 %130, 256
  %240 = icmp eq i32 %239, 0		; visa id: 252
  %241 = select i1 %240, i32 1, i32 -1		; visa id: 254
  %242 = sitofp i32 %241 to float		; visa id: 255
  %243 = fmul float %238, %242		; visa id: 256
  br label %244, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 257

244:                                              ; preds = %229, %236
; BB12 :
  %.sroa.061.0 = phi float [ %243, %236 ], [ %235, %229 ]
  %245 = bitcast i32 %179 to <4 x i8>
  %246 = extractelement <4 x i8> %245, i32 1
  %247 = zext i8 %246 to i32		; visa id: 258
  br i1 %227, label %255, label %248, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 259

248:                                              ; preds = %244
; BB13 :
  %249 = and i32 %130, 512
  %250 = sub nsw i32 0, %247, !spirv.Decorations !8798
  %251 = icmp eq i32 %249, 0		; visa id: 261
  %252 = select i1 %251, i32 %247, i32 %250		; visa id: 263
  %253 = sitofp i32 %252 to float		; visa id: 264
  %254 = fmul float %217, %253		; visa id: 265
  br label %263, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 266

255:                                              ; preds = %244
; BB14 :
  %256 = uitofp i32 %247 to float		; visa id: 268
  %257 = fmul float %217, %256		; visa id: 269
  %258 = and i32 %130, 512
  %259 = icmp eq i32 %258, 0		; visa id: 270
  %260 = select i1 %259, i32 1, i32 -1		; visa id: 272
  %261 = sitofp i32 %260 to float		; visa id: 273
  %262 = fmul float %257, %261		; visa id: 274
  br label %263, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 275

263:                                              ; preds = %255, %248
; BB15 :
  %.sroa.80.0 = phi float [ %262, %255 ], [ %254, %248 ]
  %264 = extractelement <4 x i8> %245, i32 2
  %265 = zext i8 %264 to i32		; visa id: 276
  br i1 %227, label %273, label %266, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 277

266:                                              ; preds = %263
; BB16 :
  %267 = and i32 %130, 1024
  %268 = sub nsw i32 0, %265, !spirv.Decorations !8798
  %269 = icmp eq i32 %267, 0		; visa id: 279
  %270 = select i1 %269, i32 %265, i32 %268		; visa id: 281
  %271 = sitofp i32 %270 to float		; visa id: 282
  %272 = fmul float %217, %271		; visa id: 283
  br label %281, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 284

273:                                              ; preds = %263
; BB17 :
  %274 = uitofp i32 %265 to float		; visa id: 286
  %275 = fmul float %217, %274		; visa id: 287
  %276 = and i32 %130, 1024
  %277 = icmp eq i32 %276, 0		; visa id: 288
  %278 = select i1 %277, i32 1, i32 -1		; visa id: 290
  %279 = sitofp i32 %278 to float		; visa id: 291
  %280 = fmul float %275, %279		; visa id: 292
  br label %281, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 293

281:                                              ; preds = %273, %266
; BB18 :
  %.sroa.128.0 = phi float [ %280, %273 ], [ %272, %266 ]
  %282 = lshr i32 %179, 24		; visa id: 294
  br i1 %227, label %290, label %283, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 295

283:                                              ; preds = %281
; BB19 :
  %284 = and i32 %130, 2048
  %285 = sub nsw i32 0, %282, !spirv.Decorations !8798
  %286 = icmp eq i32 %284, 0		; visa id: 297
  %287 = select i1 %286, i32 %282, i32 %285		; visa id: 299
  %288 = sitofp i32 %287 to float		; visa id: 300
  %289 = fmul float %217, %288		; visa id: 301
  br label %298, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 302

290:                                              ; preds = %281
; BB20 :
  %291 = uitofp i32 %282 to float		; visa id: 304
  %292 = fmul float %217, %291		; visa id: 305
  %293 = and i32 %130, 2048
  %294 = icmp eq i32 %293, 0		; visa id: 306
  %295 = select i1 %294, i32 1, i32 -1		; visa id: 308
  %296 = sitofp i32 %295 to float		; visa id: 309
  %297 = fmul float %292, %296		; visa id: 310
  br label %298, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 311

298:                                              ; preds = %290, %283
; BB21 :
  %.sroa.176.0 = phi float [ %297, %290 ], [ %289, %283 ]
  %299 = and i32 %180, 255		; visa id: 312
  br i1 %227, label %307, label %300, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 313

300:                                              ; preds = %298
; BB22 :
  %301 = and i32 %130, 4096
  %302 = sub nsw i32 0, %299, !spirv.Decorations !8798
  %303 = icmp eq i32 %301, 0		; visa id: 315
  %304 = select i1 %303, i32 %299, i32 %302		; visa id: 317
  %305 = sitofp i32 %304 to float		; visa id: 318
  %306 = fmul float %217, %305		; visa id: 319
  br label %315, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 320

307:                                              ; preds = %298
; BB23 :
  %308 = uitofp i32 %299 to float		; visa id: 322
  %309 = fmul float %217, %308		; visa id: 323
  %310 = and i32 %130, 4096
  %311 = icmp eq i32 %310, 0		; visa id: 324
  %312 = select i1 %311, i32 1, i32 -1		; visa id: 326
  %313 = sitofp i32 %312 to float		; visa id: 327
  %314 = fmul float %309, %313		; visa id: 328
  br label %315, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 329

315:                                              ; preds = %307, %300
; BB24 :
  %.sroa.224.0 = phi float [ %314, %307 ], [ %306, %300 ]
  %316 = bitcast i32 %180 to <4 x i8>
  %317 = extractelement <4 x i8> %316, i32 1
  %318 = zext i8 %317 to i32		; visa id: 330
  br i1 %227, label %326, label %319, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 331

319:                                              ; preds = %315
; BB25 :
  %320 = and i32 %130, 8192
  %321 = sub nsw i32 0, %318, !spirv.Decorations !8798
  %322 = icmp eq i32 %320, 0		; visa id: 333
  %323 = select i1 %322, i32 %318, i32 %321		; visa id: 335
  %324 = sitofp i32 %323 to float		; visa id: 336
  %325 = fmul float %217, %324		; visa id: 337
  br label %334, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 338

326:                                              ; preds = %315
; BB26 :
  %327 = uitofp i32 %318 to float		; visa id: 340
  %328 = fmul float %217, %327		; visa id: 341
  %329 = and i32 %130, 8192
  %330 = icmp eq i32 %329, 0		; visa id: 342
  %331 = select i1 %330, i32 1, i32 -1		; visa id: 344
  %332 = sitofp i32 %331 to float		; visa id: 345
  %333 = fmul float %328, %332		; visa id: 346
  br label %334, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 347

334:                                              ; preds = %326, %319
; BB27 :
  %.sroa.272.0 = phi float [ %333, %326 ], [ %325, %319 ]
  %335 = extractelement <4 x i8> %316, i32 2
  %336 = zext i8 %335 to i32		; visa id: 348
  br i1 %227, label %344, label %337, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 349

337:                                              ; preds = %334
; BB28 :
  %338 = and i32 %130, 16384
  %339 = sub nsw i32 0, %336, !spirv.Decorations !8798
  %340 = icmp eq i32 %338, 0		; visa id: 351
  %341 = select i1 %340, i32 %336, i32 %339		; visa id: 353
  %342 = sitofp i32 %341 to float		; visa id: 354
  %343 = fmul float %217, %342		; visa id: 355
  br label %352, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 356

344:                                              ; preds = %334
; BB29 :
  %345 = uitofp i32 %336 to float		; visa id: 358
  %346 = fmul float %217, %345		; visa id: 359
  %347 = and i32 %130, 16384
  %348 = icmp eq i32 %347, 0		; visa id: 360
  %349 = select i1 %348, i32 1, i32 -1		; visa id: 362
  %350 = sitofp i32 %349 to float		; visa id: 363
  %351 = fmul float %346, %350		; visa id: 364
  br label %352, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 365

352:                                              ; preds = %344, %337
; BB30 :
  %.sroa.320.0 = phi float [ %351, %344 ], [ %343, %337 ]
  %353 = lshr i32 %180, 24		; visa id: 366
  br i1 %227, label %361, label %354, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 367

354:                                              ; preds = %352
; BB31 :
  %355 = and i32 %130, 32768
  %356 = sub nsw i32 0, %353, !spirv.Decorations !8798
  %357 = icmp eq i32 %355, 0		; visa id: 369
  %358 = select i1 %357, i32 %353, i32 %356		; visa id: 371
  %359 = sitofp i32 %358 to float		; visa id: 372
  %360 = fmul float %217, %359		; visa id: 373
  br label %369, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 374

361:                                              ; preds = %352
; BB32 :
  %362 = uitofp i32 %353 to float		; visa id: 376
  %363 = fmul float %217, %362		; visa id: 377
  %364 = and i32 %130, 32768
  %365 = icmp eq i32 %364, 0		; visa id: 378
  %366 = select i1 %365, i32 1, i32 -1		; visa id: 380
  %367 = sitofp i32 %366 to float		; visa id: 381
  %368 = fmul float %363, %367		; visa id: 382
  br label %369, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 383

369:                                              ; preds = %361, %354
; BB33 :
  %.sroa.368.0 = phi float [ %368, %361 ], [ %360, %354 ]
  %370 = zext i16 %199 to i32		; visa id: 384
  %371 = shl nuw i32 %370, 16		; visa id: 385
  %372 = bitcast i32 %371 to float
  %373 = fmul float %.sroa.061.0, %372		; visa id: 386
  %374 = fadd float %.sroa.0.0, %373		; visa id: 387
  %375 = zext i16 %200 to i32		; visa id: 388
  %376 = shl nuw i32 %375, 16		; visa id: 389
  %377 = bitcast i32 %376 to float
  %378 = fmul float %.sroa.80.0, %377		; visa id: 390
  %379 = fadd float %374, %378		; visa id: 391
  %380 = zext i16 %201 to i32		; visa id: 392
  %381 = shl nuw i32 %380, 16		; visa id: 393
  %382 = bitcast i32 %381 to float
  %383 = fmul float %.sroa.128.0, %382		; visa id: 394
  %384 = fadd float %379, %383		; visa id: 395
  %385 = zext i16 %202 to i32		; visa id: 396
  %386 = shl nuw i32 %385, 16		; visa id: 397
  %387 = bitcast i32 %386 to float
  %388 = fmul float %.sroa.176.0, %387		; visa id: 398
  %389 = fadd float %384, %388		; visa id: 399
  %390 = zext i16 %207 to i32		; visa id: 400
  %391 = shl nuw i32 %390, 16		; visa id: 401
  %392 = bitcast i32 %391 to float
  %393 = fmul float %.sroa.224.0, %392		; visa id: 402
  %394 = fadd float %389, %393		; visa id: 403
  %395 = zext i16 %208 to i32		; visa id: 404
  %396 = shl nuw i32 %395, 16		; visa id: 405
  %397 = bitcast i32 %396 to float
  %398 = fmul float %.sroa.272.0, %397		; visa id: 406
  %399 = fadd float %394, %398		; visa id: 407
  %400 = zext i16 %209 to i32		; visa id: 408
  %401 = shl nuw i32 %400, 16		; visa id: 409
  %402 = bitcast i32 %401 to float
  %403 = fmul float %.sroa.320.0, %402		; visa id: 410
  %404 = fadd float %399, %403		; visa id: 411
  %405 = zext i16 %210 to i32		; visa id: 412
  %406 = shl nuw i32 %405, 16		; visa id: 413
  %407 = bitcast i32 %406 to float
  %408 = fmul float %.sroa.368.0, %407		; visa id: 414
  %409 = fadd float %404, %408		; visa id: 415
  %410 = and i16 %162, 255		; visa id: 416
  %411 = zext i16 %410 to i32		; visa id: 417
  %412 = and i32 %411, 15		; visa id: 418
  %413 = uitofp i32 %412 to float		; visa id: 419
  %414 = fadd float %413, 5.000000e-01		; visa id: 420
  %415 = fmul float %166, %414		; visa id: 421
  %416 = fmul float %415, 2.500000e-01		; visa id: 422
  %417 = bitcast float %166 to i32
  %418 = and i32 %417, 2147483647		; visa id: 423
  %419 = bitcast i32 %418 to float
  %420 = fcmp une float %419, %419
  %421 = fcmp oeq float %419, 0x7FF0000000000000		; visa id: 424
  %422 = or i1 %420, %421		; visa id: 425
  %423 = bitcast float %416 to i32
  %424 = and i32 %423, 2147483647		; visa id: 427
  %425 = icmp ugt i32 %424, 2139095040
  %426 = fcmp oeq float %419, 0x7FF0000000000000		; visa id: 428
  %427 = fcmp une float %419, %419
  %428 = or i1 %427, %426		; visa id: 429
  %429 = or i1 %428, %425		; visa id: 431
  %430 = and i32 %195, 255		; visa id: 433
  br i1 %429, label %438, label %431, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 434

431:                                              ; preds = %369
; BB34 :
  %432 = and i32 %151, 256
  %433 = sub nsw i32 0, %430, !spirv.Decorations !8798
  %434 = icmp eq i32 %432, 0		; visa id: 436
  %435 = select i1 %434, i32 %430, i32 %433		; visa id: 438
  %436 = sitofp i32 %435 to float		; visa id: 439
  %437 = fmul float %416, %436		; visa id: 440
  br label %446, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 441

438:                                              ; preds = %369
; BB35 :
  %439 = uitofp i32 %430 to float		; visa id: 443
  %440 = fmul float %416, %439		; visa id: 444
  %441 = and i32 %151, 256
  %442 = icmp eq i32 %441, 0		; visa id: 445
  %443 = select i1 %442, i32 1, i32 -1		; visa id: 447
  %444 = sitofp i32 %443 to float		; visa id: 448
  %445 = fmul float %440, %444		; visa id: 449
  br label %446, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 450

446:                                              ; preds = %438, %431
; BB36 :
  %.sroa.061.1 = phi float [ %445, %438 ], [ %437, %431 ]
  %447 = bitcast i32 %195 to <4 x i8>
  %448 = extractelement <4 x i8> %447, i32 1
  %449 = zext i8 %448 to i32		; visa id: 451
  br i1 %429, label %457, label %450, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 452

450:                                              ; preds = %446
; BB37 :
  %451 = and i32 %151, 512
  %452 = sub nsw i32 0, %449, !spirv.Decorations !8798
  %453 = icmp eq i32 %451, 0		; visa id: 454
  %454 = select i1 %453, i32 %449, i32 %452		; visa id: 456
  %455 = sitofp i32 %454 to float		; visa id: 457
  %456 = fmul float %416, %455		; visa id: 458
  br label %465, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 459

457:                                              ; preds = %446
; BB38 :
  %458 = uitofp i32 %449 to float		; visa id: 461
  %459 = fmul float %416, %458		; visa id: 462
  %460 = and i32 %151, 512
  %461 = icmp eq i32 %460, 0		; visa id: 463
  %462 = select i1 %461, i32 1, i32 -1		; visa id: 465
  %463 = sitofp i32 %462 to float		; visa id: 466
  %464 = fmul float %459, %463		; visa id: 467
  br label %465, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 468

465:                                              ; preds = %457, %450
; BB39 :
  %.sroa.80.1 = phi float [ %464, %457 ], [ %456, %450 ]
  %466 = extractelement <4 x i8> %447, i32 2
  %467 = zext i8 %466 to i32		; visa id: 469
  br i1 %429, label %475, label %468, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 470

468:                                              ; preds = %465
; BB40 :
  %469 = and i32 %151, 1024
  %470 = sub nsw i32 0, %467, !spirv.Decorations !8798
  %471 = icmp eq i32 %469, 0		; visa id: 472
  %472 = select i1 %471, i32 %467, i32 %470		; visa id: 474
  %473 = sitofp i32 %472 to float		; visa id: 475
  %474 = fmul float %416, %473		; visa id: 476
  br label %483, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 477

475:                                              ; preds = %465
; BB41 :
  %476 = uitofp i32 %467 to float		; visa id: 479
  %477 = fmul float %416, %476		; visa id: 480
  %478 = and i32 %151, 1024
  %479 = icmp eq i32 %478, 0		; visa id: 481
  %480 = select i1 %479, i32 1, i32 -1		; visa id: 483
  %481 = sitofp i32 %480 to float		; visa id: 484
  %482 = fmul float %477, %481		; visa id: 485
  br label %483, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 486

483:                                              ; preds = %475, %468
; BB42 :
  %.sroa.128.1 = phi float [ %482, %475 ], [ %474, %468 ]
  %484 = lshr i32 %195, 24		; visa id: 487
  br i1 %429, label %492, label %485, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 488

485:                                              ; preds = %483
; BB43 :
  %486 = and i32 %151, 2048
  %487 = sub nsw i32 0, %484, !spirv.Decorations !8798
  %488 = icmp eq i32 %486, 0		; visa id: 490
  %489 = select i1 %488, i32 %484, i32 %487		; visa id: 492
  %490 = sitofp i32 %489 to float		; visa id: 493
  %491 = fmul float %416, %490		; visa id: 494
  br label %500, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 495

492:                                              ; preds = %483
; BB44 :
  %493 = uitofp i32 %484 to float		; visa id: 497
  %494 = fmul float %416, %493		; visa id: 498
  %495 = and i32 %151, 2048
  %496 = icmp eq i32 %495, 0		; visa id: 499
  %497 = select i1 %496, i32 1, i32 -1		; visa id: 501
  %498 = sitofp i32 %497 to float		; visa id: 502
  %499 = fmul float %494, %498		; visa id: 503
  br label %500, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 504

500:                                              ; preds = %492, %485
; BB45 :
  %.sroa.176.1 = phi float [ %499, %492 ], [ %491, %485 ]
  %501 = and i32 %196, 255		; visa id: 505
  br i1 %429, label %509, label %502, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 506

502:                                              ; preds = %500
; BB46 :
  %503 = and i32 %151, 4096
  %504 = sub nsw i32 0, %501, !spirv.Decorations !8798
  %505 = icmp eq i32 %503, 0		; visa id: 508
  %506 = select i1 %505, i32 %501, i32 %504		; visa id: 510
  %507 = sitofp i32 %506 to float		; visa id: 511
  %508 = fmul float %416, %507		; visa id: 512
  br label %517, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 513

509:                                              ; preds = %500
; BB47 :
  %510 = uitofp i32 %501 to float		; visa id: 515
  %511 = fmul float %416, %510		; visa id: 516
  %512 = and i32 %151, 4096
  %513 = icmp eq i32 %512, 0		; visa id: 517
  %514 = select i1 %513, i32 1, i32 -1		; visa id: 519
  %515 = sitofp i32 %514 to float		; visa id: 520
  %516 = fmul float %511, %515		; visa id: 521
  br label %517, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 522

517:                                              ; preds = %509, %502
; BB48 :
  %.sroa.224.1 = phi float [ %516, %509 ], [ %508, %502 ]
  %518 = bitcast i32 %196 to <4 x i8>
  %519 = extractelement <4 x i8> %518, i32 1
  %520 = zext i8 %519 to i32		; visa id: 523
  br i1 %429, label %528, label %521, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 524

521:                                              ; preds = %517
; BB49 :
  %522 = and i32 %151, 8192
  %523 = sub nsw i32 0, %520, !spirv.Decorations !8798
  %524 = icmp eq i32 %522, 0		; visa id: 526
  %525 = select i1 %524, i32 %520, i32 %523		; visa id: 528
  %526 = sitofp i32 %525 to float		; visa id: 529
  %527 = fmul float %416, %526		; visa id: 530
  br label %536, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 531

528:                                              ; preds = %517
; BB50 :
  %529 = uitofp i32 %520 to float		; visa id: 533
  %530 = fmul float %416, %529		; visa id: 534
  %531 = and i32 %151, 8192
  %532 = icmp eq i32 %531, 0		; visa id: 535
  %533 = select i1 %532, i32 1, i32 -1		; visa id: 537
  %534 = sitofp i32 %533 to float		; visa id: 538
  %535 = fmul float %530, %534		; visa id: 539
  br label %536, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 540

536:                                              ; preds = %528, %521
; BB51 :
  %.sroa.272.1 = phi float [ %535, %528 ], [ %527, %521 ]
  %537 = extractelement <4 x i8> %518, i32 2
  %538 = zext i8 %537 to i32		; visa id: 541
  br i1 %429, label %546, label %539, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 542

539:                                              ; preds = %536
; BB52 :
  %540 = and i32 %151, 16384
  %541 = sub nsw i32 0, %538, !spirv.Decorations !8798
  %542 = icmp eq i32 %540, 0		; visa id: 544
  %543 = select i1 %542, i32 %538, i32 %541		; visa id: 546
  %544 = sitofp i32 %543 to float		; visa id: 547
  %545 = fmul float %416, %544		; visa id: 548
  br label %554, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 549

546:                                              ; preds = %536
; BB53 :
  %547 = uitofp i32 %538 to float		; visa id: 551
  %548 = fmul float %416, %547		; visa id: 552
  %549 = and i32 %151, 16384
  %550 = icmp eq i32 %549, 0		; visa id: 553
  %551 = select i1 %550, i32 1, i32 -1		; visa id: 555
  %552 = sitofp i32 %551 to float		; visa id: 556
  %553 = fmul float %548, %552		; visa id: 557
  br label %554, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 558

554:                                              ; preds = %546, %539
; BB54 :
  %.sroa.320.1 = phi float [ %553, %546 ], [ %545, %539 ]
  %555 = lshr i32 %196, 24		; visa id: 559
  br i1 %429, label %563, label %556, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 560

556:                                              ; preds = %554
; BB55 :
  %557 = and i32 %151, 32768
  %558 = sub nsw i32 0, %555, !spirv.Decorations !8798
  %559 = icmp eq i32 %557, 0		; visa id: 562
  %560 = select i1 %559, i32 %555, i32 %558		; visa id: 564
  %561 = sitofp i32 %560 to float		; visa id: 565
  %562 = fmul float %416, %561		; visa id: 566
  br label %._crit_edge43.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 567

563:                                              ; preds = %554
; BB56 :
  %564 = uitofp i32 %555 to float		; visa id: 569
  %565 = fmul float %416, %564		; visa id: 570
  %566 = and i32 %151, 32768
  %567 = icmp eq i32 %566, 0		; visa id: 571
  %568 = select i1 %567, i32 1, i32 -1		; visa id: 573
  %569 = sitofp i32 %568 to float		; visa id: 574
  %570 = fmul float %565, %569		; visa id: 575
  br label %._crit_edge43.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 576

._crit_edge43.1:                                  ; preds = %563, %556
; BB57 :
  %.sroa.368.1 = phi float [ %570, %563 ], [ %562, %556 ]
  %571 = fmul float %.sroa.061.1, %372		; visa id: 577
  %572 = fadd float %.sroa.20.0, %571		; visa id: 578
  %573 = fmul float %.sroa.80.1, %377		; visa id: 579
  %574 = fadd float %572, %573		; visa id: 580
  %575 = fmul float %.sroa.128.1, %382		; visa id: 581
  %576 = fadd float %574, %575		; visa id: 582
  %577 = fmul float %.sroa.176.1, %387		; visa id: 583
  %578 = fadd float %576, %577		; visa id: 584
  %579 = fmul float %.sroa.224.1, %392		; visa id: 585
  %580 = fadd float %578, %579		; visa id: 586
  %581 = fmul float %.sroa.272.1, %397		; visa id: 587
  %582 = fadd float %580, %581		; visa id: 588
  %583 = fmul float %.sroa.320.1, %402		; visa id: 589
  %584 = fadd float %582, %583		; visa id: 590
  %585 = fmul float %.sroa.368.1, %407		; visa id: 591
  %586 = fadd float %584, %585		; visa id: 592
  %587 = bitcast i32 %130 to <4 x i8>
  %588 = extractelement <4 x i8> %587, i32 2
  %589 = shl nuw nsw i32 %168, 6		; visa id: 593
  %590 = and i32 %589, 768
  %591 = zext i8 %588 to i32		; visa id: 594
  %592 = or i32 %591, %590		; visa id: 595
  %593 = shl nuw nsw i32 %592, 3, !spirv.Decorations !8791		; visa id: 596
  %594 = zext i32 %593 to i64		; visa id: 597
  %595 = add i64 %121, %594		; visa id: 598
  %596 = inttoptr i64 %595 to ptr addrspace(1)		; visa id: 599
  %597 = load <2 x i32>, ptr addrspace(1) %596, align 4		; visa id: 599
  %598 = bitcast i32 %151 to <4 x i8>
  %599 = extractelement <4 x i8> %598, i32 2
  %600 = shl nuw nsw i32 %182, 6		; visa id: 600
  %601 = and i32 %600, 768
  %602 = zext i8 %599 to i32		; visa id: 601
  %603 = or i32 %602, %601		; visa id: 602
  %604 = shl nuw nsw i32 %603, 3, !spirv.Decorations !8791		; visa id: 603
  %605 = zext i32 %604 to i64		; visa id: 604
  %606 = add i64 %121, %605		; visa id: 605
  %607 = inttoptr i64 %606 to ptr addrspace(1)		; visa id: 606
  %608 = load <2 x i32>, ptr addrspace(1) %607, align 4		; visa id: 606
  %609 = extractelement <2 x i32> %597, i32 0		; visa id: 607
  %610 = extractelement <2 x i32> %597, i32 1		; visa id: 607
  %611 = extractelement <2 x i32> %608, i32 0		; visa id: 607
  %612 = extractelement <2 x i32> %608, i32 1		; visa id: 607
  %613 = or i32 %191, 16		; visa id: 607
  %614 = zext i32 %613 to i64		; visa id: 608
  %615 = add i64 %614, %const_reg_qword2		; visa id: 609
  %IntToPtr2616 = inttoptr i64 %615 to ptr addrspace(1)		; visa id: 610
  %vCastload617 = load i32, ptr addrspace(1) %IntToPtr2616, align 2		; visa id: 610
  %616 = add i64 %615, 4
  %IntToPtr2618 = inttoptr i64 %616 to ptr addrspace(1)
  %vCastload619 = load i32, ptr addrspace(1) %IntToPtr2618, align 2		; visa id: 611
  %617 = add i64 %615, 8
  %IntToPtr2620 = inttoptr i64 %617 to ptr addrspace(1)
  %vCastload621 = load i32, ptr addrspace(1) %IntToPtr2620, align 2		; visa id: 612
  %618 = add i64 %615, 12
  %IntToPtr2622 = inttoptr i64 %618 to ptr addrspace(1)
  %vCastload623 = load i32, ptr addrspace(1) %IntToPtr2622, align 2		; visa id: 613
  %619 = bitcast i32 %vCastload617 to <2 x i16>		; visa id: 614
  %620 = bitcast i32 %vCastload619 to <2 x i16>		; visa id: 616
  %621 = extractelement <2 x i16> %619, i32 0		; visa id: 618
  %622 = extractelement <2 x i16> %619, i32 1		; visa id: 618
  %623 = extractelement <2 x i16> %620, i32 0		; visa id: 618
  %624 = extractelement <2 x i16> %620, i32 1		; visa id: 618
  %625 = bitcast i32 %vCastload621 to <2 x i16>		; visa id: 618
  %626 = bitcast i32 %vCastload623 to <2 x i16>		; visa id: 620
  %627 = extractelement <2 x i16> %625, i32 0		; visa id: 622
  %628 = extractelement <2 x i16> %625, i32 1		; visa id: 622
  %629 = extractelement <2 x i16> %626, i32 0		; visa id: 622
  %630 = extractelement <2 x i16> %626, i32 1		; visa id: 622
  %631 = and i32 %609, 255		; visa id: 622
  br i1 %227, label %639, label %632, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 623

632:                                              ; preds = %._crit_edge43.1
; BB58 :
  %633 = and i32 %130, 16777216
  %634 = sub nsw i32 0, %631, !spirv.Decorations !8798
  %635 = icmp eq i32 %633, 0		; visa id: 625
  %636 = select i1 %635, i32 %631, i32 %634		; visa id: 627
  %637 = sitofp i32 %636 to float		; visa id: 628
  %638 = fmul float %217, %637		; visa id: 629
  br label %647, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 630

639:                                              ; preds = %._crit_edge43.1
; BB59 :
  %640 = uitofp i32 %631 to float		; visa id: 632
  %641 = fmul float %217, %640		; visa id: 633
  %642 = and i32 %130, 16777216
  %643 = icmp eq i32 %642, 0		; visa id: 634
  %644 = select i1 %643, i32 1, i32 -1		; visa id: 636
  %645 = sitofp i32 %644 to float		; visa id: 637
  %646 = fmul float %641, %645		; visa id: 638
  br label %647, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 639

647:                                              ; preds = %639, %632
; BB60 :
  %.sroa.061.2 = phi float [ %646, %639 ], [ %638, %632 ]
  %648 = bitcast i32 %609 to <4 x i8>
  %649 = extractelement <4 x i8> %648, i32 1
  %650 = zext i8 %649 to i32		; visa id: 640
  br i1 %227, label %658, label %651, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 641

651:                                              ; preds = %647
; BB61 :
  %652 = and i32 %130, 33554432
  %653 = sub nsw i32 0, %650, !spirv.Decorations !8798
  %654 = icmp eq i32 %652, 0		; visa id: 643
  %655 = select i1 %654, i32 %650, i32 %653		; visa id: 645
  %656 = sitofp i32 %655 to float		; visa id: 646
  %657 = fmul float %217, %656		; visa id: 647
  br label %666, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 648

658:                                              ; preds = %647
; BB62 :
  %659 = uitofp i32 %650 to float		; visa id: 650
  %660 = fmul float %217, %659		; visa id: 651
  %661 = and i32 %130, 33554432
  %662 = icmp eq i32 %661, 0		; visa id: 652
  %663 = select i1 %662, i32 1, i32 -1		; visa id: 654
  %664 = sitofp i32 %663 to float		; visa id: 655
  %665 = fmul float %660, %664		; visa id: 656
  br label %666, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 657

666:                                              ; preds = %658, %651
; BB63 :
  %.sroa.80.2 = phi float [ %665, %658 ], [ %657, %651 ]
  %667 = extractelement <4 x i8> %648, i32 2
  %668 = zext i8 %667 to i32		; visa id: 658
  br i1 %227, label %676, label %669, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 659

669:                                              ; preds = %666
; BB64 :
  %670 = and i32 %130, 67108864
  %671 = sub nsw i32 0, %668, !spirv.Decorations !8798
  %672 = icmp eq i32 %670, 0		; visa id: 661
  %673 = select i1 %672, i32 %668, i32 %671		; visa id: 663
  %674 = sitofp i32 %673 to float		; visa id: 664
  %675 = fmul float %217, %674		; visa id: 665
  br label %684, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 666

676:                                              ; preds = %666
; BB65 :
  %677 = uitofp i32 %668 to float		; visa id: 668
  %678 = fmul float %217, %677		; visa id: 669
  %679 = and i32 %130, 67108864
  %680 = icmp eq i32 %679, 0		; visa id: 670
  %681 = select i1 %680, i32 1, i32 -1		; visa id: 672
  %682 = sitofp i32 %681 to float		; visa id: 673
  %683 = fmul float %678, %682		; visa id: 674
  br label %684, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 675

684:                                              ; preds = %676, %669
; BB66 :
  %.sroa.128.2 = phi float [ %683, %676 ], [ %675, %669 ]
  %685 = lshr i32 %609, 24		; visa id: 676
  br i1 %227, label %693, label %686, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 677

686:                                              ; preds = %684
; BB67 :
  %687 = and i32 %130, 134217728
  %688 = sub nsw i32 0, %685, !spirv.Decorations !8798
  %689 = icmp eq i32 %687, 0		; visa id: 679
  %690 = select i1 %689, i32 %685, i32 %688		; visa id: 681
  %691 = sitofp i32 %690 to float		; visa id: 682
  %692 = fmul float %217, %691		; visa id: 683
  br label %701, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 684

693:                                              ; preds = %684
; BB68 :
  %694 = uitofp i32 %685 to float		; visa id: 686
  %695 = fmul float %217, %694		; visa id: 687
  %696 = and i32 %130, 134217728
  %697 = icmp eq i32 %696, 0		; visa id: 688
  %698 = select i1 %697, i32 1, i32 -1		; visa id: 690
  %699 = sitofp i32 %698 to float		; visa id: 691
  %700 = fmul float %695, %699		; visa id: 692
  br label %701, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 693

701:                                              ; preds = %693, %686
; BB69 :
  %.sroa.176.2 = phi float [ %700, %693 ], [ %692, %686 ]
  %702 = and i32 %610, 255		; visa id: 694
  br i1 %227, label %710, label %703, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 695

703:                                              ; preds = %701
; BB70 :
  %704 = and i32 %130, 268435456
  %705 = sub nsw i32 0, %702, !spirv.Decorations !8798
  %706 = icmp eq i32 %704, 0		; visa id: 697
  %707 = select i1 %706, i32 %702, i32 %705		; visa id: 699
  %708 = sitofp i32 %707 to float		; visa id: 700
  %709 = fmul float %217, %708		; visa id: 701
  br label %718, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 702

710:                                              ; preds = %701
; BB71 :
  %711 = uitofp i32 %702 to float		; visa id: 704
  %712 = fmul float %217, %711		; visa id: 705
  %713 = and i32 %130, 268435456
  %714 = icmp eq i32 %713, 0		; visa id: 706
  %715 = select i1 %714, i32 1, i32 -1		; visa id: 708
  %716 = sitofp i32 %715 to float		; visa id: 709
  %717 = fmul float %712, %716		; visa id: 710
  br label %718, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 711

718:                                              ; preds = %710, %703
; BB72 :
  %.sroa.224.2 = phi float [ %717, %710 ], [ %709, %703 ]
  %719 = bitcast i32 %610 to <4 x i8>
  %720 = extractelement <4 x i8> %719, i32 1
  %721 = zext i8 %720 to i32		; visa id: 712
  br i1 %227, label %729, label %722, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 713

722:                                              ; preds = %718
; BB73 :
  %723 = and i32 %130, 536870912
  %724 = sub nsw i32 0, %721, !spirv.Decorations !8798
  %725 = icmp eq i32 %723, 0		; visa id: 715
  %726 = select i1 %725, i32 %721, i32 %724		; visa id: 717
  %727 = sitofp i32 %726 to float		; visa id: 718
  %728 = fmul float %217, %727		; visa id: 719
  br label %737, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 720

729:                                              ; preds = %718
; BB74 :
  %730 = uitofp i32 %721 to float		; visa id: 722
  %731 = fmul float %217, %730		; visa id: 723
  %732 = and i32 %130, 536870912
  %733 = icmp eq i32 %732, 0		; visa id: 724
  %734 = select i1 %733, i32 1, i32 -1		; visa id: 726
  %735 = sitofp i32 %734 to float		; visa id: 727
  %736 = fmul float %731, %735		; visa id: 728
  br label %737, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 729

737:                                              ; preds = %729, %722
; BB75 :
  %.sroa.272.2 = phi float [ %736, %729 ], [ %728, %722 ]
  %738 = extractelement <4 x i8> %719, i32 2
  %739 = zext i8 %738 to i32		; visa id: 730
  br i1 %227, label %747, label %740, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 731

740:                                              ; preds = %737
; BB76 :
  %741 = and i32 %130, 1073741824
  %742 = sub nsw i32 0, %739, !spirv.Decorations !8798
  %743 = icmp eq i32 %741, 0		; visa id: 733
  %744 = select i1 %743, i32 %739, i32 %742		; visa id: 735
  %745 = sitofp i32 %744 to float		; visa id: 736
  %746 = fmul float %217, %745		; visa id: 737
  br label %755, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 738

747:                                              ; preds = %737
; BB77 :
  %748 = uitofp i32 %739 to float		; visa id: 740
  %749 = fmul float %217, %748		; visa id: 741
  %750 = and i32 %130, 1073741824
  %751 = icmp eq i32 %750, 0		; visa id: 742
  %752 = select i1 %751, i32 1, i32 -1		; visa id: 744
  %753 = sitofp i32 %752 to float		; visa id: 745
  %754 = fmul float %749, %753		; visa id: 746
  br label %755, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 747

755:                                              ; preds = %747, %740
; BB78 :
  %.sroa.320.2 = phi float [ %754, %747 ], [ %746, %740 ]
  %756 = lshr i32 %610, 24		; visa id: 748
  br i1 %227, label %763, label %757, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 749

757:                                              ; preds = %755
; BB79 :
  %758 = sub nsw i32 0, %756, !spirv.Decorations !8798
  %759 = icmp slt i32 %130, 0		; visa id: 751
  %760 = select i1 %759, i32 %758, i32 %756		; visa id: 752
  %761 = sitofp i32 %760 to float		; visa id: 753
  %762 = fmul float %217, %761		; visa id: 754
  br label %770, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 755

763:                                              ; preds = %755
; BB80 :
  %764 = uitofp i32 %756 to float		; visa id: 757
  %765 = fmul float %217, %764		; visa id: 758
  %766 = icmp sgt i32 %130, -1		; visa id: 759
  %767 = select i1 %766, i32 1, i32 -1		; visa id: 760
  %768 = sitofp i32 %767 to float		; visa id: 761
  %769 = fmul float %765, %768		; visa id: 762
  br label %770, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 763

770:                                              ; preds = %763, %757
; BB81 :
  %.sroa.368.2 = phi float [ %769, %763 ], [ %762, %757 ]
  %771 = zext i16 %621 to i32		; visa id: 764
  %772 = shl nuw i32 %771, 16		; visa id: 765
  %773 = bitcast i32 %772 to float
  %774 = fmul float %.sroa.061.2, %773		; visa id: 766
  %775 = fadd float %.sroa.6.0, %774		; visa id: 767
  %776 = zext i16 %622 to i32		; visa id: 768
  %777 = shl nuw i32 %776, 16		; visa id: 769
  %778 = bitcast i32 %777 to float
  %779 = fmul float %.sroa.80.2, %778		; visa id: 770
  %780 = fadd float %775, %779		; visa id: 771
  %781 = zext i16 %623 to i32		; visa id: 772
  %782 = shl nuw i32 %781, 16		; visa id: 773
  %783 = bitcast i32 %782 to float
  %784 = fmul float %.sroa.128.2, %783		; visa id: 774
  %785 = fadd float %780, %784		; visa id: 775
  %786 = zext i16 %624 to i32		; visa id: 776
  %787 = shl nuw i32 %786, 16		; visa id: 777
  %788 = bitcast i32 %787 to float
  %789 = fmul float %.sroa.176.2, %788		; visa id: 778
  %790 = fadd float %785, %789		; visa id: 779
  %791 = zext i16 %627 to i32		; visa id: 780
  %792 = shl nuw i32 %791, 16		; visa id: 781
  %793 = bitcast i32 %792 to float
  %794 = fmul float %.sroa.224.2, %793		; visa id: 782
  %795 = fadd float %790, %794		; visa id: 783
  %796 = zext i16 %628 to i32		; visa id: 784
  %797 = shl nuw i32 %796, 16		; visa id: 785
  %798 = bitcast i32 %797 to float
  %799 = fmul float %.sroa.272.2, %798		; visa id: 786
  %800 = fadd float %795, %799		; visa id: 787
  %801 = zext i16 %629 to i32		; visa id: 788
  %802 = shl nuw i32 %801, 16		; visa id: 789
  %803 = bitcast i32 %802 to float
  %804 = fmul float %.sroa.320.2, %803		; visa id: 790
  %805 = fadd float %800, %804		; visa id: 791
  %806 = zext i16 %630 to i32		; visa id: 792
  %807 = shl nuw i32 %806, 16		; visa id: 793
  %808 = bitcast i32 %807 to float
  %809 = fmul float %.sroa.368.2, %808		; visa id: 794
  %810 = fadd float %805, %809		; visa id: 795
  %811 = and i32 %611, 255		; visa id: 796
  br i1 %429, label %819, label %812, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 797

812:                                              ; preds = %770
; BB82 :
  %813 = and i32 %151, 16777216
  %814 = sub nsw i32 0, %811, !spirv.Decorations !8798
  %815 = icmp eq i32 %813, 0		; visa id: 799
  %816 = select i1 %815, i32 %811, i32 %814		; visa id: 801
  %817 = sitofp i32 %816 to float		; visa id: 802
  %818 = fmul float %416, %817		; visa id: 803
  br label %827, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 804

819:                                              ; preds = %770
; BB83 :
  %820 = uitofp i32 %811 to float		; visa id: 806
  %821 = fmul float %416, %820		; visa id: 807
  %822 = and i32 %151, 16777216
  %823 = icmp eq i32 %822, 0		; visa id: 808
  %824 = select i1 %823, i32 1, i32 -1		; visa id: 810
  %825 = sitofp i32 %824 to float		; visa id: 811
  %826 = fmul float %821, %825		; visa id: 812
  br label %827, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 813

827:                                              ; preds = %819, %812
; BB84 :
  %.sroa.061.3 = phi float [ %826, %819 ], [ %818, %812 ]
  %828 = bitcast i32 %611 to <4 x i8>
  %829 = extractelement <4 x i8> %828, i32 1
  %830 = zext i8 %829 to i32		; visa id: 814
  br i1 %429, label %838, label %831, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 815

831:                                              ; preds = %827
; BB85 :
  %832 = and i32 %151, 33554432
  %833 = sub nsw i32 0, %830, !spirv.Decorations !8798
  %834 = icmp eq i32 %832, 0		; visa id: 817
  %835 = select i1 %834, i32 %830, i32 %833		; visa id: 819
  %836 = sitofp i32 %835 to float		; visa id: 820
  %837 = fmul float %416, %836		; visa id: 821
  br label %846, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 822

838:                                              ; preds = %827
; BB86 :
  %839 = uitofp i32 %830 to float		; visa id: 824
  %840 = fmul float %416, %839		; visa id: 825
  %841 = and i32 %151, 33554432
  %842 = icmp eq i32 %841, 0		; visa id: 826
  %843 = select i1 %842, i32 1, i32 -1		; visa id: 828
  %844 = sitofp i32 %843 to float		; visa id: 829
  %845 = fmul float %840, %844		; visa id: 830
  br label %846, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 831

846:                                              ; preds = %838, %831
; BB87 :
  %.sroa.80.3 = phi float [ %845, %838 ], [ %837, %831 ]
  %847 = extractelement <4 x i8> %828, i32 2
  %848 = zext i8 %847 to i32		; visa id: 832
  br i1 %429, label %856, label %849, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 833

849:                                              ; preds = %846
; BB88 :
  %850 = and i32 %151, 67108864
  %851 = sub nsw i32 0, %848, !spirv.Decorations !8798
  %852 = icmp eq i32 %850, 0		; visa id: 835
  %853 = select i1 %852, i32 %848, i32 %851		; visa id: 837
  %854 = sitofp i32 %853 to float		; visa id: 838
  %855 = fmul float %416, %854		; visa id: 839
  br label %864, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 840

856:                                              ; preds = %846
; BB89 :
  %857 = uitofp i32 %848 to float		; visa id: 842
  %858 = fmul float %416, %857		; visa id: 843
  %859 = and i32 %151, 67108864
  %860 = icmp eq i32 %859, 0		; visa id: 844
  %861 = select i1 %860, i32 1, i32 -1		; visa id: 846
  %862 = sitofp i32 %861 to float		; visa id: 847
  %863 = fmul float %858, %862		; visa id: 848
  br label %864, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 849

864:                                              ; preds = %856, %849
; BB90 :
  %.sroa.128.3 = phi float [ %863, %856 ], [ %855, %849 ]
  %865 = lshr i32 %611, 24		; visa id: 850
  br i1 %429, label %873, label %866, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 851

866:                                              ; preds = %864
; BB91 :
  %867 = and i32 %151, 134217728
  %868 = sub nsw i32 0, %865, !spirv.Decorations !8798
  %869 = icmp eq i32 %867, 0		; visa id: 853
  %870 = select i1 %869, i32 %865, i32 %868		; visa id: 855
  %871 = sitofp i32 %870 to float		; visa id: 856
  %872 = fmul float %416, %871		; visa id: 857
  br label %881, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 858

873:                                              ; preds = %864
; BB92 :
  %874 = uitofp i32 %865 to float		; visa id: 860
  %875 = fmul float %416, %874		; visa id: 861
  %876 = and i32 %151, 134217728
  %877 = icmp eq i32 %876, 0		; visa id: 862
  %878 = select i1 %877, i32 1, i32 -1		; visa id: 864
  %879 = sitofp i32 %878 to float		; visa id: 865
  %880 = fmul float %875, %879		; visa id: 866
  br label %881, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 867

881:                                              ; preds = %873, %866
; BB93 :
  %.sroa.176.3 = phi float [ %880, %873 ], [ %872, %866 ]
  %882 = and i32 %612, 255		; visa id: 868
  br i1 %429, label %890, label %883, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 869

883:                                              ; preds = %881
; BB94 :
  %884 = and i32 %151, 268435456
  %885 = sub nsw i32 0, %882, !spirv.Decorations !8798
  %886 = icmp eq i32 %884, 0		; visa id: 871
  %887 = select i1 %886, i32 %882, i32 %885		; visa id: 873
  %888 = sitofp i32 %887 to float		; visa id: 874
  %889 = fmul float %416, %888		; visa id: 875
  br label %898, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 876

890:                                              ; preds = %881
; BB95 :
  %891 = uitofp i32 %882 to float		; visa id: 878
  %892 = fmul float %416, %891		; visa id: 879
  %893 = and i32 %151, 268435456
  %894 = icmp eq i32 %893, 0		; visa id: 880
  %895 = select i1 %894, i32 1, i32 -1		; visa id: 882
  %896 = sitofp i32 %895 to float		; visa id: 883
  %897 = fmul float %892, %896		; visa id: 884
  br label %898, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 885

898:                                              ; preds = %890, %883
; BB96 :
  %.sroa.224.3 = phi float [ %897, %890 ], [ %889, %883 ]
  %899 = bitcast i32 %612 to <4 x i8>
  %900 = extractelement <4 x i8> %899, i32 1
  %901 = zext i8 %900 to i32		; visa id: 886
  br i1 %429, label %909, label %902, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 887

902:                                              ; preds = %898
; BB97 :
  %903 = and i32 %151, 536870912
  %904 = sub nsw i32 0, %901, !spirv.Decorations !8798
  %905 = icmp eq i32 %903, 0		; visa id: 889
  %906 = select i1 %905, i32 %901, i32 %904		; visa id: 891
  %907 = sitofp i32 %906 to float		; visa id: 892
  %908 = fmul float %416, %907		; visa id: 893
  br label %917, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 894

909:                                              ; preds = %898
; BB98 :
  %910 = uitofp i32 %901 to float		; visa id: 896
  %911 = fmul float %416, %910		; visa id: 897
  %912 = and i32 %151, 536870912
  %913 = icmp eq i32 %912, 0		; visa id: 898
  %914 = select i1 %913, i32 1, i32 -1		; visa id: 900
  %915 = sitofp i32 %914 to float		; visa id: 901
  %916 = fmul float %911, %915		; visa id: 902
  br label %917, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 903

917:                                              ; preds = %909, %902
; BB99 :
  %.sroa.272.3 = phi float [ %916, %909 ], [ %908, %902 ]
  %918 = extractelement <4 x i8> %899, i32 2
  %919 = zext i8 %918 to i32		; visa id: 904
  br i1 %429, label %927, label %920, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 905

920:                                              ; preds = %917
; BB100 :
  %921 = and i32 %151, 1073741824
  %922 = sub nsw i32 0, %919, !spirv.Decorations !8798
  %923 = icmp eq i32 %921, 0		; visa id: 907
  %924 = select i1 %923, i32 %919, i32 %922		; visa id: 909
  %925 = sitofp i32 %924 to float		; visa id: 910
  %926 = fmul float %416, %925		; visa id: 911
  br label %935, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 912

927:                                              ; preds = %917
; BB101 :
  %928 = uitofp i32 %919 to float		; visa id: 914
  %929 = fmul float %416, %928		; visa id: 915
  %930 = and i32 %151, 1073741824
  %931 = icmp eq i32 %930, 0		; visa id: 916
  %932 = select i1 %931, i32 1, i32 -1		; visa id: 918
  %933 = sitofp i32 %932 to float		; visa id: 919
  %934 = fmul float %929, %933		; visa id: 920
  br label %935, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 921

935:                                              ; preds = %927, %920
; BB102 :
  %.sroa.320.3 = phi float [ %934, %927 ], [ %926, %920 ]
  %936 = lshr i32 %612, 24		; visa id: 922
  br i1 %429, label %943, label %937, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 923

937:                                              ; preds = %935
; BB103 :
  %938 = sub nsw i32 0, %936, !spirv.Decorations !8798
  %939 = icmp slt i32 %151, 0		; visa id: 925
  %940 = select i1 %939, i32 %938, i32 %936		; visa id: 926
  %941 = sitofp i32 %940 to float		; visa id: 927
  %942 = fmul float %416, %941		; visa id: 928
  br label %._crit_edge43.2, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 929

943:                                              ; preds = %935
; BB104 :
  %944 = uitofp i32 %936 to float		; visa id: 931
  %945 = fmul float %416, %944		; visa id: 932
  %946 = icmp sgt i32 %151, -1		; visa id: 933
  %947 = select i1 %946, i32 1, i32 -1		; visa id: 934
  %948 = sitofp i32 %947 to float		; visa id: 935
  %949 = fmul float %945, %948		; visa id: 936
  br label %._crit_edge43.2, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 937

._crit_edge43.2:                                  ; preds = %943, %937
; BB105 :
  %.sroa.368.3 = phi float [ %949, %943 ], [ %942, %937 ]
  %950 = fmul float %.sroa.061.3, %773		; visa id: 938
  %951 = fadd float %.sroa.23.0, %950		; visa id: 939
  %952 = fmul float %.sroa.80.3, %778		; visa id: 940
  %953 = fadd float %951, %952		; visa id: 941
  %954 = fmul float %.sroa.128.3, %783		; visa id: 942
  %955 = fadd float %953, %954		; visa id: 943
  %956 = fmul float %.sroa.176.3, %788		; visa id: 944
  %957 = fadd float %955, %956		; visa id: 945
  %958 = fmul float %.sroa.224.3, %793		; visa id: 946
  %959 = fadd float %957, %958		; visa id: 947
  %960 = fmul float %.sroa.272.3, %798		; visa id: 948
  %961 = fadd float %959, %960		; visa id: 949
  %962 = fmul float %.sroa.320.3, %803		; visa id: 950
  %963 = fadd float %961, %962		; visa id: 951
  %964 = fmul float %.sroa.368.3, %808		; visa id: 952
  %965 = fadd float %963, %964		; visa id: 953
  %966 = and i32 %131, 255
  %967 = shl nuw nsw i32 %168, 4		; visa id: 954
  %968 = and i32 %967, 768		; visa id: 955
  %969 = or i32 %966, %968		; visa id: 956
  %970 = shl nuw nsw i32 %969, 3, !spirv.Decorations !8791		; visa id: 957
  %971 = zext i32 %970 to i64		; visa id: 958
  %972 = add i64 %121, %971		; visa id: 959
  %973 = inttoptr i64 %972 to ptr addrspace(1)		; visa id: 960
  %974 = load <2 x i32>, ptr addrspace(1) %973, align 4		; visa id: 960
  %975 = and i32 %152, 255
  %976 = shl nuw nsw i32 %182, 4		; visa id: 961
  %977 = and i32 %976, 768		; visa id: 962
  %978 = or i32 %975, %977		; visa id: 963
  %979 = shl nuw nsw i32 %978, 3, !spirv.Decorations !8791		; visa id: 964
  %980 = zext i32 %979 to i64		; visa id: 965
  %981 = add i64 %121, %980		; visa id: 966
  %982 = inttoptr i64 %981 to ptr addrspace(1)		; visa id: 967
  %983 = load <2 x i32>, ptr addrspace(1) %982, align 4		; visa id: 967
  %984 = extractelement <2 x i32> %974, i32 0		; visa id: 968
  %985 = extractelement <2 x i32> %974, i32 1		; visa id: 968
  %986 = extractelement <2 x i32> %983, i32 0		; visa id: 968
  %987 = extractelement <2 x i32> %983, i32 1		; visa id: 968
  %988 = or i32 %191, 32		; visa id: 968
  %989 = zext i32 %988 to i64		; visa id: 969
  %990 = add i64 %989, %const_reg_qword2		; visa id: 970
  %IntToPtr2624 = inttoptr i64 %990 to ptr addrspace(1)		; visa id: 971
  %vCastload625 = load i32, ptr addrspace(1) %IntToPtr2624, align 2		; visa id: 971
  %991 = add i64 %990, 4
  %IntToPtr2626 = inttoptr i64 %991 to ptr addrspace(1)
  %vCastload627 = load i32, ptr addrspace(1) %IntToPtr2626, align 2		; visa id: 972
  %992 = add i64 %990, 8
  %IntToPtr2628 = inttoptr i64 %992 to ptr addrspace(1)
  %vCastload629 = load i32, ptr addrspace(1) %IntToPtr2628, align 2		; visa id: 973
  %993 = add i64 %990, 12
  %IntToPtr2630 = inttoptr i64 %993 to ptr addrspace(1)
  %vCastload631 = load i32, ptr addrspace(1) %IntToPtr2630, align 2		; visa id: 974
  %994 = bitcast i32 %vCastload625 to <2 x i16>		; visa id: 975
  %995 = bitcast i32 %vCastload627 to <2 x i16>		; visa id: 977
  %996 = extractelement <2 x i16> %994, i32 0		; visa id: 979
  %997 = extractelement <2 x i16> %994, i32 1		; visa id: 979
  %998 = extractelement <2 x i16> %995, i32 0		; visa id: 979
  %999 = extractelement <2 x i16> %995, i32 1		; visa id: 979
  %1000 = bitcast i32 %vCastload629 to <2 x i16>		; visa id: 979
  %1001 = bitcast i32 %vCastload631 to <2 x i16>		; visa id: 981
  %1002 = extractelement <2 x i16> %1000, i32 0		; visa id: 983
  %1003 = extractelement <2 x i16> %1000, i32 1		; visa id: 983
  %1004 = extractelement <2 x i16> %1001, i32 0		; visa id: 983
  %1005 = extractelement <2 x i16> %1001, i32 1		; visa id: 983
  %1006 = lshr i32 %212, 4		; visa id: 983
  %1007 = uitofp i32 %1006 to float		; visa id: 984
  %1008 = fadd float %1007, 5.000000e-01		; visa id: 985
  %1009 = fmul float %147, %1008		; visa id: 986
  %1010 = fmul float %1009, 2.500000e-01		; visa id: 987
  %1011 = bitcast float %1010 to i32
  %1012 = and i32 %1011, 2147483647		; visa id: 988
  %1013 = icmp ugt i32 %1012, 2139095040
  %1014 = fcmp oeq float %220, 0x7FF0000000000000		; visa id: 989
  %1015 = fcmp une float %220, %220
  %1016 = or i1 %1015, %1014		; visa id: 990
  %1017 = or i1 %1016, %1013		; visa id: 992
  %1018 = and i32 %984, 255		; visa id: 994
  br i1 %1017, label %1026, label %1019, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 995

1019:                                             ; preds = %._crit_edge43.2
; BB106 :
  %1020 = and i32 %131, 256
  %1021 = sub nsw i32 0, %1018, !spirv.Decorations !8798
  %1022 = icmp eq i32 %1020, 0		; visa id: 997
  %1023 = select i1 %1022, i32 %1018, i32 %1021		; visa id: 999
  %1024 = sitofp i32 %1023 to float		; visa id: 1000
  %1025 = fmul float %1010, %1024		; visa id: 1001
  br label %1034, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1002

1026:                                             ; preds = %._crit_edge43.2
; BB107 :
  %1027 = uitofp i32 %1018 to float		; visa id: 1004
  %1028 = fmul float %1010, %1027		; visa id: 1005
  %1029 = and i32 %131, 256
  %1030 = icmp eq i32 %1029, 0		; visa id: 1006
  %1031 = select i1 %1030, i32 1, i32 -1		; visa id: 1008
  %1032 = sitofp i32 %1031 to float		; visa id: 1009
  %1033 = fmul float %1028, %1032		; visa id: 1010
  br label %1034, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1011

1034:                                             ; preds = %1026, %1019
; BB108 :
  %.sroa.061.4 = phi float [ %1033, %1026 ], [ %1025, %1019 ]
  %1035 = bitcast i32 %984 to <4 x i8>
  %1036 = extractelement <4 x i8> %1035, i32 1
  %1037 = zext i8 %1036 to i32		; visa id: 1012
  br i1 %1017, label %1045, label %1038, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1013

1038:                                             ; preds = %1034
; BB109 :
  %1039 = and i32 %131, 512
  %1040 = sub nsw i32 0, %1037, !spirv.Decorations !8798
  %1041 = icmp eq i32 %1039, 0		; visa id: 1015
  %1042 = select i1 %1041, i32 %1037, i32 %1040		; visa id: 1017
  %1043 = sitofp i32 %1042 to float		; visa id: 1018
  %1044 = fmul float %1010, %1043		; visa id: 1019
  br label %1053, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1020

1045:                                             ; preds = %1034
; BB110 :
  %1046 = uitofp i32 %1037 to float		; visa id: 1022
  %1047 = fmul float %1010, %1046		; visa id: 1023
  %1048 = and i32 %131, 512
  %1049 = icmp eq i32 %1048, 0		; visa id: 1024
  %1050 = select i1 %1049, i32 1, i32 -1		; visa id: 1026
  %1051 = sitofp i32 %1050 to float		; visa id: 1027
  %1052 = fmul float %1047, %1051		; visa id: 1028
  br label %1053, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1029

1053:                                             ; preds = %1045, %1038
; BB111 :
  %.sroa.80.4 = phi float [ %1052, %1045 ], [ %1044, %1038 ]
  %1054 = extractelement <4 x i8> %1035, i32 2
  %1055 = zext i8 %1054 to i32		; visa id: 1030
  br i1 %1017, label %1063, label %1056, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1031

1056:                                             ; preds = %1053
; BB112 :
  %1057 = and i32 %131, 1024
  %1058 = sub nsw i32 0, %1055, !spirv.Decorations !8798
  %1059 = icmp eq i32 %1057, 0		; visa id: 1033
  %1060 = select i1 %1059, i32 %1055, i32 %1058		; visa id: 1035
  %1061 = sitofp i32 %1060 to float		; visa id: 1036
  %1062 = fmul float %1010, %1061		; visa id: 1037
  br label %1071, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1038

1063:                                             ; preds = %1053
; BB113 :
  %1064 = uitofp i32 %1055 to float		; visa id: 1040
  %1065 = fmul float %1010, %1064		; visa id: 1041
  %1066 = and i32 %131, 1024
  %1067 = icmp eq i32 %1066, 0		; visa id: 1042
  %1068 = select i1 %1067, i32 1, i32 -1		; visa id: 1044
  %1069 = sitofp i32 %1068 to float		; visa id: 1045
  %1070 = fmul float %1065, %1069		; visa id: 1046
  br label %1071, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1047

1071:                                             ; preds = %1063, %1056
; BB114 :
  %.sroa.128.4 = phi float [ %1070, %1063 ], [ %1062, %1056 ]
  %1072 = lshr i32 %984, 24		; visa id: 1048
  br i1 %1017, label %1080, label %1073, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1049

1073:                                             ; preds = %1071
; BB115 :
  %1074 = and i32 %131, 2048
  %1075 = sub nsw i32 0, %1072, !spirv.Decorations !8798
  %1076 = icmp eq i32 %1074, 0		; visa id: 1051
  %1077 = select i1 %1076, i32 %1072, i32 %1075		; visa id: 1053
  %1078 = sitofp i32 %1077 to float		; visa id: 1054
  %1079 = fmul float %1010, %1078		; visa id: 1055
  br label %1088, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1056

1080:                                             ; preds = %1071
; BB116 :
  %1081 = uitofp i32 %1072 to float		; visa id: 1058
  %1082 = fmul float %1010, %1081		; visa id: 1059
  %1083 = and i32 %131, 2048
  %1084 = icmp eq i32 %1083, 0		; visa id: 1060
  %1085 = select i1 %1084, i32 1, i32 -1		; visa id: 1062
  %1086 = sitofp i32 %1085 to float		; visa id: 1063
  %1087 = fmul float %1082, %1086		; visa id: 1064
  br label %1088, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1065

1088:                                             ; preds = %1080, %1073
; BB117 :
  %.sroa.176.4 = phi float [ %1087, %1080 ], [ %1079, %1073 ]
  %1089 = and i32 %985, 255		; visa id: 1066
  br i1 %1017, label %1097, label %1090, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1067

1090:                                             ; preds = %1088
; BB118 :
  %1091 = and i32 %131, 4096
  %1092 = sub nsw i32 0, %1089, !spirv.Decorations !8798
  %1093 = icmp eq i32 %1091, 0		; visa id: 1069
  %1094 = select i1 %1093, i32 %1089, i32 %1092		; visa id: 1071
  %1095 = sitofp i32 %1094 to float		; visa id: 1072
  %1096 = fmul float %1010, %1095		; visa id: 1073
  br label %1105, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1074

1097:                                             ; preds = %1088
; BB119 :
  %1098 = uitofp i32 %1089 to float		; visa id: 1076
  %1099 = fmul float %1010, %1098		; visa id: 1077
  %1100 = and i32 %131, 4096
  %1101 = icmp eq i32 %1100, 0		; visa id: 1078
  %1102 = select i1 %1101, i32 1, i32 -1		; visa id: 1080
  %1103 = sitofp i32 %1102 to float		; visa id: 1081
  %1104 = fmul float %1099, %1103		; visa id: 1082
  br label %1105, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1083

1105:                                             ; preds = %1097, %1090
; BB120 :
  %.sroa.224.4 = phi float [ %1104, %1097 ], [ %1096, %1090 ]
  %1106 = bitcast i32 %985 to <4 x i8>
  %1107 = extractelement <4 x i8> %1106, i32 1
  %1108 = zext i8 %1107 to i32		; visa id: 1084
  br i1 %1017, label %1116, label %1109, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1085

1109:                                             ; preds = %1105
; BB121 :
  %1110 = and i32 %131, 8192
  %1111 = sub nsw i32 0, %1108, !spirv.Decorations !8798
  %1112 = icmp eq i32 %1110, 0		; visa id: 1087
  %1113 = select i1 %1112, i32 %1108, i32 %1111		; visa id: 1089
  %1114 = sitofp i32 %1113 to float		; visa id: 1090
  %1115 = fmul float %1010, %1114		; visa id: 1091
  br label %1124, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1092

1116:                                             ; preds = %1105
; BB122 :
  %1117 = uitofp i32 %1108 to float		; visa id: 1094
  %1118 = fmul float %1010, %1117		; visa id: 1095
  %1119 = and i32 %131, 8192
  %1120 = icmp eq i32 %1119, 0		; visa id: 1096
  %1121 = select i1 %1120, i32 1, i32 -1		; visa id: 1098
  %1122 = sitofp i32 %1121 to float		; visa id: 1099
  %1123 = fmul float %1118, %1122		; visa id: 1100
  br label %1124, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1101

1124:                                             ; preds = %1116, %1109
; BB123 :
  %.sroa.272.4 = phi float [ %1123, %1116 ], [ %1115, %1109 ]
  %1125 = extractelement <4 x i8> %1106, i32 2
  %1126 = zext i8 %1125 to i32		; visa id: 1102
  br i1 %1017, label %1134, label %1127, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1103

1127:                                             ; preds = %1124
; BB124 :
  %1128 = and i32 %131, 16384
  %1129 = sub nsw i32 0, %1126, !spirv.Decorations !8798
  %1130 = icmp eq i32 %1128, 0		; visa id: 1105
  %1131 = select i1 %1130, i32 %1126, i32 %1129		; visa id: 1107
  %1132 = sitofp i32 %1131 to float		; visa id: 1108
  %1133 = fmul float %1010, %1132		; visa id: 1109
  br label %1142, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1110

1134:                                             ; preds = %1124
; BB125 :
  %1135 = uitofp i32 %1126 to float		; visa id: 1112
  %1136 = fmul float %1010, %1135		; visa id: 1113
  %1137 = and i32 %131, 16384
  %1138 = icmp eq i32 %1137, 0		; visa id: 1114
  %1139 = select i1 %1138, i32 1, i32 -1		; visa id: 1116
  %1140 = sitofp i32 %1139 to float		; visa id: 1117
  %1141 = fmul float %1136, %1140		; visa id: 1118
  br label %1142, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1119

1142:                                             ; preds = %1134, %1127
; BB126 :
  %.sroa.320.4 = phi float [ %1141, %1134 ], [ %1133, %1127 ]
  %1143 = lshr i32 %985, 24		; visa id: 1120
  br i1 %1017, label %1151, label %1144, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1121

1144:                                             ; preds = %1142
; BB127 :
  %1145 = and i32 %131, 32768
  %1146 = sub nsw i32 0, %1143, !spirv.Decorations !8798
  %1147 = icmp eq i32 %1145, 0		; visa id: 1123
  %1148 = select i1 %1147, i32 %1143, i32 %1146		; visa id: 1125
  %1149 = sitofp i32 %1148 to float		; visa id: 1126
  %1150 = fmul float %1010, %1149		; visa id: 1127
  br label %1159, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1128

1151:                                             ; preds = %1142
; BB128 :
  %1152 = uitofp i32 %1143 to float		; visa id: 1130
  %1153 = fmul float %1010, %1152		; visa id: 1131
  %1154 = and i32 %131, 32768
  %1155 = icmp eq i32 %1154, 0		; visa id: 1132
  %1156 = select i1 %1155, i32 1, i32 -1		; visa id: 1134
  %1157 = sitofp i32 %1156 to float		; visa id: 1135
  %1158 = fmul float %1153, %1157		; visa id: 1136
  br label %1159, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1137

1159:                                             ; preds = %1151, %1144
; BB129 :
  %.sroa.368.4 = phi float [ %1158, %1151 ], [ %1150, %1144 ]
  %1160 = zext i16 %996 to i32		; visa id: 1138
  %1161 = shl nuw i32 %1160, 16		; visa id: 1139
  %1162 = bitcast i32 %1161 to float
  %1163 = fmul float %.sroa.061.4, %1162		; visa id: 1140
  %1164 = fadd float %.sroa.8.0, %1163		; visa id: 1141
  %1165 = zext i16 %997 to i32		; visa id: 1142
  %1166 = shl nuw i32 %1165, 16		; visa id: 1143
  %1167 = bitcast i32 %1166 to float
  %1168 = fmul float %.sroa.80.4, %1167		; visa id: 1144
  %1169 = fadd float %1164, %1168		; visa id: 1145
  %1170 = zext i16 %998 to i32		; visa id: 1146
  %1171 = shl nuw i32 %1170, 16		; visa id: 1147
  %1172 = bitcast i32 %1171 to float
  %1173 = fmul float %.sroa.128.4, %1172		; visa id: 1148
  %1174 = fadd float %1169, %1173		; visa id: 1149
  %1175 = zext i16 %999 to i32		; visa id: 1150
  %1176 = shl nuw i32 %1175, 16		; visa id: 1151
  %1177 = bitcast i32 %1176 to float
  %1178 = fmul float %.sroa.176.4, %1177		; visa id: 1152
  %1179 = fadd float %1174, %1178		; visa id: 1153
  %1180 = zext i16 %1002 to i32		; visa id: 1154
  %1181 = shl nuw i32 %1180, 16		; visa id: 1155
  %1182 = bitcast i32 %1181 to float
  %1183 = fmul float %.sroa.224.4, %1182		; visa id: 1156
  %1184 = fadd float %1179, %1183		; visa id: 1157
  %1185 = zext i16 %1003 to i32		; visa id: 1158
  %1186 = shl nuw i32 %1185, 16		; visa id: 1159
  %1187 = bitcast i32 %1186 to float
  %1188 = fmul float %.sroa.272.4, %1187		; visa id: 1160
  %1189 = fadd float %1184, %1188		; visa id: 1161
  %1190 = zext i16 %1004 to i32		; visa id: 1162
  %1191 = shl nuw i32 %1190, 16		; visa id: 1163
  %1192 = bitcast i32 %1191 to float
  %1193 = fmul float %.sroa.320.4, %1192		; visa id: 1164
  %1194 = fadd float %1189, %1193		; visa id: 1165
  %1195 = zext i16 %1005 to i32		; visa id: 1166
  %1196 = shl nuw i32 %1195, 16		; visa id: 1167
  %1197 = bitcast i32 %1196 to float
  %1198 = fmul float %.sroa.368.4, %1197		; visa id: 1168
  %1199 = fadd float %1194, %1198		; visa id: 1169
  %1200 = lshr i32 %411, 4		; visa id: 1170
  %1201 = uitofp i32 %1200 to float		; visa id: 1171
  %1202 = fadd float %1201, 5.000000e-01		; visa id: 1172
  %1203 = fmul float %166, %1202		; visa id: 1173
  %1204 = fmul float %1203, 2.500000e-01		; visa id: 1174
  %1205 = bitcast float %1204 to i32
  %1206 = and i32 %1205, 2147483647		; visa id: 1175
  %1207 = icmp ugt i32 %1206, 2139095040		; visa id: 1176
  %1208 = or i1 %422, %1207		; visa id: 1177
  %1209 = and i32 %986, 255		; visa id: 1178
  br i1 %1208, label %1217, label %1210, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1179

1210:                                             ; preds = %1159
; BB130 :
  %1211 = and i32 %152, 256
  %1212 = sub nsw i32 0, %1209, !spirv.Decorations !8798
  %1213 = icmp eq i32 %1211, 0		; visa id: 1181
  %1214 = select i1 %1213, i32 %1209, i32 %1212		; visa id: 1183
  %1215 = sitofp i32 %1214 to float		; visa id: 1184
  %1216 = fmul float %1204, %1215		; visa id: 1185
  br label %1225, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1186

1217:                                             ; preds = %1159
; BB131 :
  %1218 = uitofp i32 %1209 to float		; visa id: 1188
  %1219 = fmul float %1204, %1218		; visa id: 1189
  %1220 = and i32 %152, 256
  %1221 = icmp eq i32 %1220, 0		; visa id: 1190
  %1222 = select i1 %1221, i32 1, i32 -1		; visa id: 1192
  %1223 = sitofp i32 %1222 to float		; visa id: 1193
  %1224 = fmul float %1219, %1223		; visa id: 1194
  br label %1225, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1195

1225:                                             ; preds = %1217, %1210
; BB132 :
  %.sroa.061.5 = phi float [ %1224, %1217 ], [ %1216, %1210 ]
  %1226 = bitcast i32 %986 to <4 x i8>
  %1227 = extractelement <4 x i8> %1226, i32 1
  %1228 = zext i8 %1227 to i32		; visa id: 1196
  br i1 %1208, label %1236, label %1229, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1197

1229:                                             ; preds = %1225
; BB133 :
  %1230 = and i32 %152, 512
  %1231 = sub nsw i32 0, %1228, !spirv.Decorations !8798
  %1232 = icmp eq i32 %1230, 0		; visa id: 1199
  %1233 = select i1 %1232, i32 %1228, i32 %1231		; visa id: 1201
  %1234 = sitofp i32 %1233 to float		; visa id: 1202
  %1235 = fmul float %1204, %1234		; visa id: 1203
  br label %1244, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1204

1236:                                             ; preds = %1225
; BB134 :
  %1237 = uitofp i32 %1228 to float		; visa id: 1206
  %1238 = fmul float %1204, %1237		; visa id: 1207
  %1239 = and i32 %152, 512
  %1240 = icmp eq i32 %1239, 0		; visa id: 1208
  %1241 = select i1 %1240, i32 1, i32 -1		; visa id: 1210
  %1242 = sitofp i32 %1241 to float		; visa id: 1211
  %1243 = fmul float %1238, %1242		; visa id: 1212
  br label %1244, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1213

1244:                                             ; preds = %1236, %1229
; BB135 :
  %.sroa.80.5 = phi float [ %1243, %1236 ], [ %1235, %1229 ]
  %1245 = extractelement <4 x i8> %1226, i32 2
  %1246 = zext i8 %1245 to i32		; visa id: 1214
  br i1 %1208, label %1254, label %1247, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1215

1247:                                             ; preds = %1244
; BB136 :
  %1248 = and i32 %152, 1024
  %1249 = sub nsw i32 0, %1246, !spirv.Decorations !8798
  %1250 = icmp eq i32 %1248, 0		; visa id: 1217
  %1251 = select i1 %1250, i32 %1246, i32 %1249		; visa id: 1219
  %1252 = sitofp i32 %1251 to float		; visa id: 1220
  %1253 = fmul float %1204, %1252		; visa id: 1221
  br label %1262, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1222

1254:                                             ; preds = %1244
; BB137 :
  %1255 = uitofp i32 %1246 to float		; visa id: 1224
  %1256 = fmul float %1204, %1255		; visa id: 1225
  %1257 = and i32 %152, 1024
  %1258 = icmp eq i32 %1257, 0		; visa id: 1226
  %1259 = select i1 %1258, i32 1, i32 -1		; visa id: 1228
  %1260 = sitofp i32 %1259 to float		; visa id: 1229
  %1261 = fmul float %1256, %1260		; visa id: 1230
  br label %1262, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1231

1262:                                             ; preds = %1254, %1247
; BB138 :
  %.sroa.128.5 = phi float [ %1261, %1254 ], [ %1253, %1247 ]
  %1263 = lshr i32 %986, 24		; visa id: 1232
  br i1 %1208, label %1271, label %1264, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1233

1264:                                             ; preds = %1262
; BB139 :
  %1265 = and i32 %152, 2048
  %1266 = sub nsw i32 0, %1263, !spirv.Decorations !8798
  %1267 = icmp eq i32 %1265, 0		; visa id: 1235
  %1268 = select i1 %1267, i32 %1263, i32 %1266		; visa id: 1237
  %1269 = sitofp i32 %1268 to float		; visa id: 1238
  %1270 = fmul float %1204, %1269		; visa id: 1239
  br label %1279, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1240

1271:                                             ; preds = %1262
; BB140 :
  %1272 = uitofp i32 %1263 to float		; visa id: 1242
  %1273 = fmul float %1204, %1272		; visa id: 1243
  %1274 = and i32 %152, 2048
  %1275 = icmp eq i32 %1274, 0		; visa id: 1244
  %1276 = select i1 %1275, i32 1, i32 -1		; visa id: 1246
  %1277 = sitofp i32 %1276 to float		; visa id: 1247
  %1278 = fmul float %1273, %1277		; visa id: 1248
  br label %1279, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1249

1279:                                             ; preds = %1271, %1264
; BB141 :
  %.sroa.176.5 = phi float [ %1278, %1271 ], [ %1270, %1264 ]
  %1280 = and i32 %987, 255		; visa id: 1250
  br i1 %1208, label %1288, label %1281, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1251

1281:                                             ; preds = %1279
; BB142 :
  %1282 = and i32 %152, 4096
  %1283 = sub nsw i32 0, %1280, !spirv.Decorations !8798
  %1284 = icmp eq i32 %1282, 0		; visa id: 1253
  %1285 = select i1 %1284, i32 %1280, i32 %1283		; visa id: 1255
  %1286 = sitofp i32 %1285 to float		; visa id: 1256
  %1287 = fmul float %1204, %1286		; visa id: 1257
  br label %1296, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1258

1288:                                             ; preds = %1279
; BB143 :
  %1289 = uitofp i32 %1280 to float		; visa id: 1260
  %1290 = fmul float %1204, %1289		; visa id: 1261
  %1291 = and i32 %152, 4096
  %1292 = icmp eq i32 %1291, 0		; visa id: 1262
  %1293 = select i1 %1292, i32 1, i32 -1		; visa id: 1264
  %1294 = sitofp i32 %1293 to float		; visa id: 1265
  %1295 = fmul float %1290, %1294		; visa id: 1266
  br label %1296, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1267

1296:                                             ; preds = %1288, %1281
; BB144 :
  %.sroa.224.5 = phi float [ %1295, %1288 ], [ %1287, %1281 ]
  %1297 = bitcast i32 %987 to <4 x i8>
  %1298 = extractelement <4 x i8> %1297, i32 1
  %1299 = zext i8 %1298 to i32		; visa id: 1268
  br i1 %1208, label %1307, label %1300, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1269

1300:                                             ; preds = %1296
; BB145 :
  %1301 = and i32 %152, 8192
  %1302 = sub nsw i32 0, %1299, !spirv.Decorations !8798
  %1303 = icmp eq i32 %1301, 0		; visa id: 1271
  %1304 = select i1 %1303, i32 %1299, i32 %1302		; visa id: 1273
  %1305 = sitofp i32 %1304 to float		; visa id: 1274
  %1306 = fmul float %1204, %1305		; visa id: 1275
  br label %1315, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1276

1307:                                             ; preds = %1296
; BB146 :
  %1308 = uitofp i32 %1299 to float		; visa id: 1278
  %1309 = fmul float %1204, %1308		; visa id: 1279
  %1310 = and i32 %152, 8192
  %1311 = icmp eq i32 %1310, 0		; visa id: 1280
  %1312 = select i1 %1311, i32 1, i32 -1		; visa id: 1282
  %1313 = sitofp i32 %1312 to float		; visa id: 1283
  %1314 = fmul float %1309, %1313		; visa id: 1284
  br label %1315, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1285

1315:                                             ; preds = %1307, %1300
; BB147 :
  %.sroa.272.5 = phi float [ %1314, %1307 ], [ %1306, %1300 ]
  %1316 = extractelement <4 x i8> %1297, i32 2
  %1317 = zext i8 %1316 to i32		; visa id: 1286
  br i1 %1208, label %1325, label %1318, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1287

1318:                                             ; preds = %1315
; BB148 :
  %1319 = and i32 %152, 16384
  %1320 = sub nsw i32 0, %1317, !spirv.Decorations !8798
  %1321 = icmp eq i32 %1319, 0		; visa id: 1289
  %1322 = select i1 %1321, i32 %1317, i32 %1320		; visa id: 1291
  %1323 = sitofp i32 %1322 to float		; visa id: 1292
  %1324 = fmul float %1204, %1323		; visa id: 1293
  br label %1333, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1294

1325:                                             ; preds = %1315
; BB149 :
  %1326 = uitofp i32 %1317 to float		; visa id: 1296
  %1327 = fmul float %1204, %1326		; visa id: 1297
  %1328 = and i32 %152, 16384
  %1329 = icmp eq i32 %1328, 0		; visa id: 1298
  %1330 = select i1 %1329, i32 1, i32 -1		; visa id: 1300
  %1331 = sitofp i32 %1330 to float		; visa id: 1301
  %1332 = fmul float %1327, %1331		; visa id: 1302
  br label %1333, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1303

1333:                                             ; preds = %1325, %1318
; BB150 :
  %.sroa.320.5 = phi float [ %1332, %1325 ], [ %1324, %1318 ]
  %1334 = lshr i32 %987, 24		; visa id: 1304
  br i1 %1208, label %1342, label %1335, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1305

1335:                                             ; preds = %1333
; BB151 :
  %1336 = and i32 %152, 32768
  %1337 = sub nsw i32 0, %1334, !spirv.Decorations !8798
  %1338 = icmp eq i32 %1336, 0		; visa id: 1307
  %1339 = select i1 %1338, i32 %1334, i32 %1337		; visa id: 1309
  %1340 = sitofp i32 %1339 to float		; visa id: 1310
  %1341 = fmul float %1204, %1340		; visa id: 1311
  br label %._crit_edge43.3, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1312

1342:                                             ; preds = %1333
; BB152 :
  %1343 = uitofp i32 %1334 to float		; visa id: 1314
  %1344 = fmul float %1204, %1343		; visa id: 1315
  %1345 = and i32 %152, 32768
  %1346 = icmp eq i32 %1345, 0		; visa id: 1316
  %1347 = select i1 %1346, i32 1, i32 -1		; visa id: 1318
  %1348 = sitofp i32 %1347 to float		; visa id: 1319
  %1349 = fmul float %1344, %1348		; visa id: 1320
  br label %._crit_edge43.3, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1321

._crit_edge43.3:                                  ; preds = %1342, %1335
; BB153 :
  %.sroa.368.5 = phi float [ %1349, %1342 ], [ %1341, %1335 ]
  %1350 = fmul float %.sroa.061.5, %1162		; visa id: 1322
  %1351 = fadd float %.sroa.25.0, %1350		; visa id: 1323
  %1352 = fmul float %.sroa.80.5, %1167		; visa id: 1324
  %1353 = fadd float %1351, %1352		; visa id: 1325
  %1354 = fmul float %.sroa.128.5, %1172		; visa id: 1326
  %1355 = fadd float %1353, %1354		; visa id: 1327
  %1356 = fmul float %.sroa.176.5, %1177		; visa id: 1328
  %1357 = fadd float %1355, %1356		; visa id: 1329
  %1358 = fmul float %.sroa.224.5, %1182		; visa id: 1330
  %1359 = fadd float %1357, %1358		; visa id: 1331
  %1360 = fmul float %.sroa.272.5, %1187		; visa id: 1332
  %1361 = fadd float %1359, %1360		; visa id: 1333
  %1362 = fmul float %.sroa.320.5, %1192		; visa id: 1334
  %1363 = fadd float %1361, %1362		; visa id: 1335
  %1364 = fmul float %.sroa.368.5, %1197		; visa id: 1336
  %1365 = fadd float %1363, %1364		; visa id: 1337
  %1366 = bitcast i32 %131 to <4 x i8>
  %1367 = extractelement <4 x i8> %1366, i32 2
  %1368 = shl nuw nsw i32 %168, 2		; visa id: 1338
  %1369 = and i32 %1368, 768
  %1370 = zext i8 %1367 to i32		; visa id: 1339
  %1371 = or i32 %1370, %1369		; visa id: 1340
  %1372 = shl nuw nsw i32 %1371, 3, !spirv.Decorations !8791		; visa id: 1341
  %1373 = zext i32 %1372 to i64		; visa id: 1342
  %1374 = add i64 %121, %1373		; visa id: 1343
  %1375 = inttoptr i64 %1374 to ptr addrspace(1)		; visa id: 1344
  %1376 = load <2 x i32>, ptr addrspace(1) %1375, align 4		; visa id: 1344
  %1377 = bitcast i32 %152 to <4 x i8>
  %1378 = extractelement <4 x i8> %1377, i32 2
  %1379 = shl nuw nsw i32 %182, 2		; visa id: 1345
  %1380 = and i32 %1379, 768
  %1381 = zext i8 %1378 to i32		; visa id: 1346
  %1382 = or i32 %1381, %1380		; visa id: 1347
  %1383 = shl nuw nsw i32 %1382, 3, !spirv.Decorations !8791		; visa id: 1348
  %1384 = zext i32 %1383 to i64		; visa id: 1349
  %1385 = add i64 %121, %1384		; visa id: 1350
  %1386 = inttoptr i64 %1385 to ptr addrspace(1)		; visa id: 1351
  %1387 = load <2 x i32>, ptr addrspace(1) %1386, align 4		; visa id: 1351
  %1388 = extractelement <2 x i32> %1376, i32 0		; visa id: 1352
  %1389 = extractelement <2 x i32> %1376, i32 1		; visa id: 1352
  %1390 = extractelement <2 x i32> %1387, i32 0		; visa id: 1352
  %1391 = extractelement <2 x i32> %1387, i32 1		; visa id: 1352
  %1392 = or i32 %191, 48		; visa id: 1352
  %1393 = zext i32 %1392 to i64		; visa id: 1353
  %1394 = add i64 %1393, %const_reg_qword2		; visa id: 1354
  %IntToPtr2632 = inttoptr i64 %1394 to ptr addrspace(1)		; visa id: 1355
  %vCastload633 = load i32, ptr addrspace(1) %IntToPtr2632, align 2		; visa id: 1355
  %1395 = add i64 %1394, 4
  %IntToPtr2634 = inttoptr i64 %1395 to ptr addrspace(1)
  %vCastload635 = load i32, ptr addrspace(1) %IntToPtr2634, align 2		; visa id: 1356
  %1396 = add i64 %1394, 8
  %IntToPtr2636 = inttoptr i64 %1396 to ptr addrspace(1)
  %vCastload637 = load i32, ptr addrspace(1) %IntToPtr2636, align 2		; visa id: 1357
  %1397 = add i64 %1394, 12
  %IntToPtr2638 = inttoptr i64 %1397 to ptr addrspace(1)
  %vCastload639 = load i32, ptr addrspace(1) %IntToPtr2638, align 2		; visa id: 1358
  %1398 = bitcast i32 %vCastload633 to <2 x i16>		; visa id: 1359
  %1399 = bitcast i32 %vCastload635 to <2 x i16>		; visa id: 1361
  %1400 = extractelement <2 x i16> %1398, i32 0		; visa id: 1363
  %1401 = extractelement <2 x i16> %1398, i32 1		; visa id: 1363
  %1402 = extractelement <2 x i16> %1399, i32 0		; visa id: 1363
  %1403 = extractelement <2 x i16> %1399, i32 1		; visa id: 1363
  %1404 = bitcast i32 %vCastload637 to <2 x i16>		; visa id: 1363
  %1405 = bitcast i32 %vCastload639 to <2 x i16>		; visa id: 1365
  %1406 = extractelement <2 x i16> %1404, i32 0		; visa id: 1367
  %1407 = extractelement <2 x i16> %1404, i32 1		; visa id: 1367
  %1408 = extractelement <2 x i16> %1405, i32 0		; visa id: 1367
  %1409 = extractelement <2 x i16> %1405, i32 1		; visa id: 1367
  %1410 = and i32 %1388, 255		; visa id: 1367
  br i1 %1017, label %1418, label %1411, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1368

1411:                                             ; preds = %._crit_edge43.3
; BB154 :
  %1412 = and i32 %131, 16777216
  %1413 = sub nsw i32 0, %1410, !spirv.Decorations !8798
  %1414 = icmp eq i32 %1412, 0		; visa id: 1370
  %1415 = select i1 %1414, i32 %1410, i32 %1413		; visa id: 1372
  %1416 = sitofp i32 %1415 to float		; visa id: 1373
  %1417 = fmul float %1010, %1416		; visa id: 1374
  br label %1426, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1375

1418:                                             ; preds = %._crit_edge43.3
; BB155 :
  %1419 = uitofp i32 %1410 to float		; visa id: 1377
  %1420 = fmul float %1010, %1419		; visa id: 1378
  %1421 = and i32 %131, 16777216
  %1422 = icmp eq i32 %1421, 0		; visa id: 1379
  %1423 = select i1 %1422, i32 1, i32 -1		; visa id: 1381
  %1424 = sitofp i32 %1423 to float		; visa id: 1382
  %1425 = fmul float %1420, %1424		; visa id: 1383
  br label %1426, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1384

1426:                                             ; preds = %1418, %1411
; BB156 :
  %.sroa.061.6 = phi float [ %1425, %1418 ], [ %1417, %1411 ]
  %1427 = bitcast i32 %1388 to <4 x i8>
  %1428 = extractelement <4 x i8> %1427, i32 1
  %1429 = zext i8 %1428 to i32		; visa id: 1385
  br i1 %1017, label %1437, label %1430, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1386

1430:                                             ; preds = %1426
; BB157 :
  %1431 = and i32 %131, 33554432
  %1432 = sub nsw i32 0, %1429, !spirv.Decorations !8798
  %1433 = icmp eq i32 %1431, 0		; visa id: 1388
  %1434 = select i1 %1433, i32 %1429, i32 %1432		; visa id: 1390
  %1435 = sitofp i32 %1434 to float		; visa id: 1391
  %1436 = fmul float %1010, %1435		; visa id: 1392
  br label %1445, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1393

1437:                                             ; preds = %1426
; BB158 :
  %1438 = uitofp i32 %1429 to float		; visa id: 1395
  %1439 = fmul float %1010, %1438		; visa id: 1396
  %1440 = and i32 %131, 33554432
  %1441 = icmp eq i32 %1440, 0		; visa id: 1397
  %1442 = select i1 %1441, i32 1, i32 -1		; visa id: 1399
  %1443 = sitofp i32 %1442 to float		; visa id: 1400
  %1444 = fmul float %1439, %1443		; visa id: 1401
  br label %1445, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1402

1445:                                             ; preds = %1437, %1430
; BB159 :
  %.sroa.80.6 = phi float [ %1444, %1437 ], [ %1436, %1430 ]
  %1446 = extractelement <4 x i8> %1427, i32 2
  %1447 = zext i8 %1446 to i32		; visa id: 1403
  br i1 %1017, label %1455, label %1448, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1404

1448:                                             ; preds = %1445
; BB160 :
  %1449 = and i32 %131, 67108864
  %1450 = sub nsw i32 0, %1447, !spirv.Decorations !8798
  %1451 = icmp eq i32 %1449, 0		; visa id: 1406
  %1452 = select i1 %1451, i32 %1447, i32 %1450		; visa id: 1408
  %1453 = sitofp i32 %1452 to float		; visa id: 1409
  %1454 = fmul float %1010, %1453		; visa id: 1410
  br label %1463, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1411

1455:                                             ; preds = %1445
; BB161 :
  %1456 = uitofp i32 %1447 to float		; visa id: 1413
  %1457 = fmul float %1010, %1456		; visa id: 1414
  %1458 = and i32 %131, 67108864
  %1459 = icmp eq i32 %1458, 0		; visa id: 1415
  %1460 = select i1 %1459, i32 1, i32 -1		; visa id: 1417
  %1461 = sitofp i32 %1460 to float		; visa id: 1418
  %1462 = fmul float %1457, %1461		; visa id: 1419
  br label %1463, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1420

1463:                                             ; preds = %1455, %1448
; BB162 :
  %.sroa.128.6 = phi float [ %1462, %1455 ], [ %1454, %1448 ]
  %1464 = lshr i32 %1388, 24		; visa id: 1421
  br i1 %1017, label %1472, label %1465, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1422

1465:                                             ; preds = %1463
; BB163 :
  %1466 = and i32 %131, 134217728
  %1467 = sub nsw i32 0, %1464, !spirv.Decorations !8798
  %1468 = icmp eq i32 %1466, 0		; visa id: 1424
  %1469 = select i1 %1468, i32 %1464, i32 %1467		; visa id: 1426
  %1470 = sitofp i32 %1469 to float		; visa id: 1427
  %1471 = fmul float %1010, %1470		; visa id: 1428
  br label %1480, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1429

1472:                                             ; preds = %1463
; BB164 :
  %1473 = uitofp i32 %1464 to float		; visa id: 1431
  %1474 = fmul float %1010, %1473		; visa id: 1432
  %1475 = and i32 %131, 134217728
  %1476 = icmp eq i32 %1475, 0		; visa id: 1433
  %1477 = select i1 %1476, i32 1, i32 -1		; visa id: 1435
  %1478 = sitofp i32 %1477 to float		; visa id: 1436
  %1479 = fmul float %1474, %1478		; visa id: 1437
  br label %1480, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1438

1480:                                             ; preds = %1472, %1465
; BB165 :
  %.sroa.176.6 = phi float [ %1479, %1472 ], [ %1471, %1465 ]
  %1481 = and i32 %1389, 255		; visa id: 1439
  br i1 %1017, label %1489, label %1482, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1440

1482:                                             ; preds = %1480
; BB166 :
  %1483 = and i32 %131, 268435456
  %1484 = sub nsw i32 0, %1481, !spirv.Decorations !8798
  %1485 = icmp eq i32 %1483, 0		; visa id: 1442
  %1486 = select i1 %1485, i32 %1481, i32 %1484		; visa id: 1444
  %1487 = sitofp i32 %1486 to float		; visa id: 1445
  %1488 = fmul float %1010, %1487		; visa id: 1446
  br label %1497, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1447

1489:                                             ; preds = %1480
; BB167 :
  %1490 = uitofp i32 %1481 to float		; visa id: 1449
  %1491 = fmul float %1010, %1490		; visa id: 1450
  %1492 = and i32 %131, 268435456
  %1493 = icmp eq i32 %1492, 0		; visa id: 1451
  %1494 = select i1 %1493, i32 1, i32 -1		; visa id: 1453
  %1495 = sitofp i32 %1494 to float		; visa id: 1454
  %1496 = fmul float %1491, %1495		; visa id: 1455
  br label %1497, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1456

1497:                                             ; preds = %1489, %1482
; BB168 :
  %.sroa.224.6 = phi float [ %1496, %1489 ], [ %1488, %1482 ]
  %1498 = bitcast i32 %1389 to <4 x i8>
  %1499 = extractelement <4 x i8> %1498, i32 1
  %1500 = zext i8 %1499 to i32		; visa id: 1457
  br i1 %1017, label %1508, label %1501, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1458

1501:                                             ; preds = %1497
; BB169 :
  %1502 = and i32 %131, 536870912
  %1503 = sub nsw i32 0, %1500, !spirv.Decorations !8798
  %1504 = icmp eq i32 %1502, 0		; visa id: 1460
  %1505 = select i1 %1504, i32 %1500, i32 %1503		; visa id: 1462
  %1506 = sitofp i32 %1505 to float		; visa id: 1463
  %1507 = fmul float %1010, %1506		; visa id: 1464
  br label %1516, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1465

1508:                                             ; preds = %1497
; BB170 :
  %1509 = uitofp i32 %1500 to float		; visa id: 1467
  %1510 = fmul float %1010, %1509		; visa id: 1468
  %1511 = and i32 %131, 536870912
  %1512 = icmp eq i32 %1511, 0		; visa id: 1469
  %1513 = select i1 %1512, i32 1, i32 -1		; visa id: 1471
  %1514 = sitofp i32 %1513 to float		; visa id: 1472
  %1515 = fmul float %1510, %1514		; visa id: 1473
  br label %1516, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1474

1516:                                             ; preds = %1508, %1501
; BB171 :
  %.sroa.272.6 = phi float [ %1515, %1508 ], [ %1507, %1501 ]
  %1517 = extractelement <4 x i8> %1498, i32 2
  %1518 = zext i8 %1517 to i32		; visa id: 1475
  br i1 %1017, label %1526, label %1519, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1476

1519:                                             ; preds = %1516
; BB172 :
  %1520 = and i32 %131, 1073741824
  %1521 = sub nsw i32 0, %1518, !spirv.Decorations !8798
  %1522 = icmp eq i32 %1520, 0		; visa id: 1478
  %1523 = select i1 %1522, i32 %1518, i32 %1521		; visa id: 1480
  %1524 = sitofp i32 %1523 to float		; visa id: 1481
  %1525 = fmul float %1010, %1524		; visa id: 1482
  br label %1534, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1483

1526:                                             ; preds = %1516
; BB173 :
  %1527 = uitofp i32 %1518 to float		; visa id: 1485
  %1528 = fmul float %1010, %1527		; visa id: 1486
  %1529 = and i32 %131, 1073741824
  %1530 = icmp eq i32 %1529, 0		; visa id: 1487
  %1531 = select i1 %1530, i32 1, i32 -1		; visa id: 1489
  %1532 = sitofp i32 %1531 to float		; visa id: 1490
  %1533 = fmul float %1528, %1532		; visa id: 1491
  br label %1534, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1492

1534:                                             ; preds = %1526, %1519
; BB174 :
  %.sroa.320.6 = phi float [ %1533, %1526 ], [ %1525, %1519 ]
  %1535 = lshr i32 %1389, 24		; visa id: 1493
  br i1 %1017, label %1542, label %1536, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1494

1536:                                             ; preds = %1534
; BB175 :
  %1537 = sub nsw i32 0, %1535, !spirv.Decorations !8798
  %1538 = icmp slt i32 %131, 0		; visa id: 1496
  %1539 = select i1 %1538, i32 %1537, i32 %1535		; visa id: 1497
  %1540 = sitofp i32 %1539 to float		; visa id: 1498
  %1541 = fmul float %1010, %1540		; visa id: 1499
  br label %1549, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1500

1542:                                             ; preds = %1534
; BB176 :
  %1543 = uitofp i32 %1535 to float		; visa id: 1502
  %1544 = fmul float %1010, %1543		; visa id: 1503
  %1545 = icmp sgt i32 %131, -1		; visa id: 1504
  %1546 = select i1 %1545, i32 1, i32 -1		; visa id: 1505
  %1547 = sitofp i32 %1546 to float		; visa id: 1506
  %1548 = fmul float %1544, %1547		; visa id: 1507
  br label %1549, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1508

1549:                                             ; preds = %1542, %1536
; BB177 :
  %.sroa.368.6 = phi float [ %1548, %1542 ], [ %1541, %1536 ]
  %1550 = zext i16 %1400 to i32		; visa id: 1509
  %1551 = shl nuw i32 %1550, 16		; visa id: 1510
  %1552 = bitcast i32 %1551 to float
  %1553 = fmul float %.sroa.061.6, %1552		; visa id: 1511
  %1554 = fadd float %.sroa.10.0, %1553		; visa id: 1512
  %1555 = zext i16 %1401 to i32		; visa id: 1513
  %1556 = shl nuw i32 %1555, 16		; visa id: 1514
  %1557 = bitcast i32 %1556 to float
  %1558 = fmul float %.sroa.80.6, %1557		; visa id: 1515
  %1559 = fadd float %1554, %1558		; visa id: 1516
  %1560 = zext i16 %1402 to i32		; visa id: 1517
  %1561 = shl nuw i32 %1560, 16		; visa id: 1518
  %1562 = bitcast i32 %1561 to float
  %1563 = fmul float %.sroa.128.6, %1562		; visa id: 1519
  %1564 = fadd float %1559, %1563		; visa id: 1520
  %1565 = zext i16 %1403 to i32		; visa id: 1521
  %1566 = shl nuw i32 %1565, 16		; visa id: 1522
  %1567 = bitcast i32 %1566 to float
  %1568 = fmul float %.sroa.176.6, %1567		; visa id: 1523
  %1569 = fadd float %1564, %1568		; visa id: 1524
  %1570 = zext i16 %1406 to i32		; visa id: 1525
  %1571 = shl nuw i32 %1570, 16		; visa id: 1526
  %1572 = bitcast i32 %1571 to float
  %1573 = fmul float %.sroa.224.6, %1572		; visa id: 1527
  %1574 = fadd float %1569, %1573		; visa id: 1528
  %1575 = zext i16 %1407 to i32		; visa id: 1529
  %1576 = shl nuw i32 %1575, 16		; visa id: 1530
  %1577 = bitcast i32 %1576 to float
  %1578 = fmul float %.sroa.272.6, %1577		; visa id: 1531
  %1579 = fadd float %1574, %1578		; visa id: 1532
  %1580 = zext i16 %1408 to i32		; visa id: 1533
  %1581 = shl nuw i32 %1580, 16		; visa id: 1534
  %1582 = bitcast i32 %1581 to float
  %1583 = fmul float %.sroa.320.6, %1582		; visa id: 1535
  %1584 = fadd float %1579, %1583		; visa id: 1536
  %1585 = zext i16 %1409 to i32		; visa id: 1537
  %1586 = shl nuw i32 %1585, 16		; visa id: 1538
  %1587 = bitcast i32 %1586 to float
  %1588 = fmul float %.sroa.368.6, %1587		; visa id: 1539
  %1589 = fadd float %1584, %1588		; visa id: 1540
  %1590 = and i32 %1390, 255		; visa id: 1541
  br i1 %1208, label %1598, label %1591, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1542

1591:                                             ; preds = %1549
; BB178 :
  %1592 = and i32 %152, 16777216
  %1593 = sub nsw i32 0, %1590, !spirv.Decorations !8798
  %1594 = icmp eq i32 %1592, 0		; visa id: 1544
  %1595 = select i1 %1594, i32 %1590, i32 %1593		; visa id: 1546
  %1596 = sitofp i32 %1595 to float		; visa id: 1547
  %1597 = fmul float %1204, %1596		; visa id: 1548
  br label %1606, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1549

1598:                                             ; preds = %1549
; BB179 :
  %1599 = uitofp i32 %1590 to float		; visa id: 1551
  %1600 = fmul float %1204, %1599		; visa id: 1552
  %1601 = and i32 %152, 16777216
  %1602 = icmp eq i32 %1601, 0		; visa id: 1553
  %1603 = select i1 %1602, i32 1, i32 -1		; visa id: 1555
  %1604 = sitofp i32 %1603 to float		; visa id: 1556
  %1605 = fmul float %1600, %1604		; visa id: 1557
  br label %1606, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1558

1606:                                             ; preds = %1598, %1591
; BB180 :
  %.sroa.061.7 = phi float [ %1605, %1598 ], [ %1597, %1591 ]
  %1607 = bitcast i32 %1390 to <4 x i8>
  %1608 = extractelement <4 x i8> %1607, i32 1
  %1609 = zext i8 %1608 to i32		; visa id: 1559
  br i1 %1208, label %1617, label %1610, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1560

1610:                                             ; preds = %1606
; BB181 :
  %1611 = and i32 %152, 33554432
  %1612 = sub nsw i32 0, %1609, !spirv.Decorations !8798
  %1613 = icmp eq i32 %1611, 0		; visa id: 1562
  %1614 = select i1 %1613, i32 %1609, i32 %1612		; visa id: 1564
  %1615 = sitofp i32 %1614 to float		; visa id: 1565
  %1616 = fmul float %1204, %1615		; visa id: 1566
  br label %1625, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1567

1617:                                             ; preds = %1606
; BB182 :
  %1618 = uitofp i32 %1609 to float		; visa id: 1569
  %1619 = fmul float %1204, %1618		; visa id: 1570
  %1620 = and i32 %152, 33554432
  %1621 = icmp eq i32 %1620, 0		; visa id: 1571
  %1622 = select i1 %1621, i32 1, i32 -1		; visa id: 1573
  %1623 = sitofp i32 %1622 to float		; visa id: 1574
  %1624 = fmul float %1619, %1623		; visa id: 1575
  br label %1625, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1576

1625:                                             ; preds = %1617, %1610
; BB183 :
  %.sroa.80.7 = phi float [ %1624, %1617 ], [ %1616, %1610 ]
  %1626 = extractelement <4 x i8> %1607, i32 2
  %1627 = zext i8 %1626 to i32		; visa id: 1577
  br i1 %1208, label %1635, label %1628, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1578

1628:                                             ; preds = %1625
; BB184 :
  %1629 = and i32 %152, 67108864
  %1630 = sub nsw i32 0, %1627, !spirv.Decorations !8798
  %1631 = icmp eq i32 %1629, 0		; visa id: 1580
  %1632 = select i1 %1631, i32 %1627, i32 %1630		; visa id: 1582
  %1633 = sitofp i32 %1632 to float		; visa id: 1583
  %1634 = fmul float %1204, %1633		; visa id: 1584
  br label %1643, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1585

1635:                                             ; preds = %1625
; BB185 :
  %1636 = uitofp i32 %1627 to float		; visa id: 1587
  %1637 = fmul float %1204, %1636		; visa id: 1588
  %1638 = and i32 %152, 67108864
  %1639 = icmp eq i32 %1638, 0		; visa id: 1589
  %1640 = select i1 %1639, i32 1, i32 -1		; visa id: 1591
  %1641 = sitofp i32 %1640 to float		; visa id: 1592
  %1642 = fmul float %1637, %1641		; visa id: 1593
  br label %1643, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1594

1643:                                             ; preds = %1635, %1628
; BB186 :
  %.sroa.128.7 = phi float [ %1642, %1635 ], [ %1634, %1628 ]
  %1644 = lshr i32 %1390, 24		; visa id: 1595
  br i1 %1208, label %1652, label %1645, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1596

1645:                                             ; preds = %1643
; BB187 :
  %1646 = and i32 %152, 134217728
  %1647 = sub nsw i32 0, %1644, !spirv.Decorations !8798
  %1648 = icmp eq i32 %1646, 0		; visa id: 1598
  %1649 = select i1 %1648, i32 %1644, i32 %1647		; visa id: 1600
  %1650 = sitofp i32 %1649 to float		; visa id: 1601
  %1651 = fmul float %1204, %1650		; visa id: 1602
  br label %1660, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1603

1652:                                             ; preds = %1643
; BB188 :
  %1653 = uitofp i32 %1644 to float		; visa id: 1605
  %1654 = fmul float %1204, %1653		; visa id: 1606
  %1655 = and i32 %152, 134217728
  %1656 = icmp eq i32 %1655, 0		; visa id: 1607
  %1657 = select i1 %1656, i32 1, i32 -1		; visa id: 1609
  %1658 = sitofp i32 %1657 to float		; visa id: 1610
  %1659 = fmul float %1654, %1658		; visa id: 1611
  br label %1660, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1612

1660:                                             ; preds = %1652, %1645
; BB189 :
  %.sroa.176.7 = phi float [ %1659, %1652 ], [ %1651, %1645 ]
  %1661 = and i32 %1391, 255		; visa id: 1613
  br i1 %1208, label %1669, label %1662, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1614

1662:                                             ; preds = %1660
; BB190 :
  %1663 = and i32 %152, 268435456
  %1664 = sub nsw i32 0, %1661, !spirv.Decorations !8798
  %1665 = icmp eq i32 %1663, 0		; visa id: 1616
  %1666 = select i1 %1665, i32 %1661, i32 %1664		; visa id: 1618
  %1667 = sitofp i32 %1666 to float		; visa id: 1619
  %1668 = fmul float %1204, %1667		; visa id: 1620
  br label %1677, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1621

1669:                                             ; preds = %1660
; BB191 :
  %1670 = uitofp i32 %1661 to float		; visa id: 1623
  %1671 = fmul float %1204, %1670		; visa id: 1624
  %1672 = and i32 %152, 268435456
  %1673 = icmp eq i32 %1672, 0		; visa id: 1625
  %1674 = select i1 %1673, i32 1, i32 -1		; visa id: 1627
  %1675 = sitofp i32 %1674 to float		; visa id: 1628
  %1676 = fmul float %1671, %1675		; visa id: 1629
  br label %1677, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1630

1677:                                             ; preds = %1669, %1662
; BB192 :
  %.sroa.224.7 = phi float [ %1676, %1669 ], [ %1668, %1662 ]
  %1678 = bitcast i32 %1391 to <4 x i8>
  %1679 = extractelement <4 x i8> %1678, i32 1
  %1680 = zext i8 %1679 to i32		; visa id: 1631
  br i1 %1208, label %1688, label %1681, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1632

1681:                                             ; preds = %1677
; BB193 :
  %1682 = and i32 %152, 536870912
  %1683 = sub nsw i32 0, %1680, !spirv.Decorations !8798
  %1684 = icmp eq i32 %1682, 0		; visa id: 1634
  %1685 = select i1 %1684, i32 %1680, i32 %1683		; visa id: 1636
  %1686 = sitofp i32 %1685 to float		; visa id: 1637
  %1687 = fmul float %1204, %1686		; visa id: 1638
  br label %1696, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1639

1688:                                             ; preds = %1677
; BB194 :
  %1689 = uitofp i32 %1680 to float		; visa id: 1641
  %1690 = fmul float %1204, %1689		; visa id: 1642
  %1691 = and i32 %152, 536870912
  %1692 = icmp eq i32 %1691, 0		; visa id: 1643
  %1693 = select i1 %1692, i32 1, i32 -1		; visa id: 1645
  %1694 = sitofp i32 %1693 to float		; visa id: 1646
  %1695 = fmul float %1690, %1694		; visa id: 1647
  br label %1696, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1648

1696:                                             ; preds = %1688, %1681
; BB195 :
  %.sroa.272.7 = phi float [ %1695, %1688 ], [ %1687, %1681 ]
  %1697 = extractelement <4 x i8> %1678, i32 2
  %1698 = zext i8 %1697 to i32		; visa id: 1649
  br i1 %1208, label %1706, label %1699, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1650

1699:                                             ; preds = %1696
; BB196 :
  %1700 = and i32 %152, 1073741824
  %1701 = sub nsw i32 0, %1698, !spirv.Decorations !8798
  %1702 = icmp eq i32 %1700, 0		; visa id: 1652
  %1703 = select i1 %1702, i32 %1698, i32 %1701		; visa id: 1654
  %1704 = sitofp i32 %1703 to float		; visa id: 1655
  %1705 = fmul float %1204, %1704		; visa id: 1656
  br label %1714, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1657

1706:                                             ; preds = %1696
; BB197 :
  %1707 = uitofp i32 %1698 to float		; visa id: 1659
  %1708 = fmul float %1204, %1707		; visa id: 1660
  %1709 = and i32 %152, 1073741824
  %1710 = icmp eq i32 %1709, 0		; visa id: 1661
  %1711 = select i1 %1710, i32 1, i32 -1		; visa id: 1663
  %1712 = sitofp i32 %1711 to float		; visa id: 1664
  %1713 = fmul float %1708, %1712		; visa id: 1665
  br label %1714, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1666

1714:                                             ; preds = %1706, %1699
; BB198 :
  %.sroa.320.7 = phi float [ %1713, %1706 ], [ %1705, %1699 ]
  %1715 = lshr i32 %1391, 24		; visa id: 1667
  br i1 %1208, label %1722, label %1716, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1668

1716:                                             ; preds = %1714
; BB199 :
  %1717 = sub nsw i32 0, %1715, !spirv.Decorations !8798
  %1718 = icmp slt i32 %152, 0		; visa id: 1670
  %1719 = select i1 %1718, i32 %1717, i32 %1715		; visa id: 1671
  %1720 = sitofp i32 %1719 to float		; visa id: 1672
  %1721 = fmul float %1204, %1720		; visa id: 1673
  br label %._crit_edge43.4, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1674

1722:                                             ; preds = %1714
; BB200 :
  %1723 = uitofp i32 %1715 to float		; visa id: 1676
  %1724 = fmul float %1204, %1723		; visa id: 1677
  %1725 = icmp sgt i32 %152, -1		; visa id: 1678
  %1726 = select i1 %1725, i32 1, i32 -1		; visa id: 1679
  %1727 = sitofp i32 %1726 to float		; visa id: 1680
  %1728 = fmul float %1724, %1727		; visa id: 1681
  br label %._crit_edge43.4, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1682

._crit_edge43.4:                                  ; preds = %1722, %1716
; BB201 :
  %.sroa.368.7 = phi float [ %1728, %1722 ], [ %1721, %1716 ]
  %1729 = fmul float %.sroa.061.7, %1552		; visa id: 1683
  %1730 = fadd float %.sroa.27.0, %1729		; visa id: 1684
  %1731 = fmul float %.sroa.80.7, %1557		; visa id: 1685
  %1732 = fadd float %1730, %1731		; visa id: 1686
  %1733 = fmul float %.sroa.128.7, %1562		; visa id: 1687
  %1734 = fadd float %1732, %1733		; visa id: 1688
  %1735 = fmul float %.sroa.176.7, %1567		; visa id: 1689
  %1736 = fadd float %1734, %1735		; visa id: 1690
  %1737 = fmul float %.sroa.224.7, %1572		; visa id: 1691
  %1738 = fadd float %1736, %1737		; visa id: 1692
  %1739 = fmul float %.sroa.272.7, %1577		; visa id: 1693
  %1740 = fadd float %1738, %1739		; visa id: 1694
  %1741 = fmul float %.sroa.320.7, %1582		; visa id: 1695
  %1742 = fadd float %1740, %1741		; visa id: 1696
  %1743 = fmul float %.sroa.368.7, %1587		; visa id: 1697
  %1744 = fadd float %1742, %1743		; visa id: 1698
  %1745 = lshr i16 %142, 8		; visa id: 1699
  %1746 = and i32 %132, 255
  %1747 = and i32 %168, 768		; visa id: 1700
  %1748 = or i32 %1746, %1747		; visa id: 1701
  %1749 = shl nuw nsw i32 %1748, 3, !spirv.Decorations !8791		; visa id: 1702
  %1750 = zext i32 %1749 to i64		; visa id: 1703
  %1751 = add i64 %121, %1750		; visa id: 1704
  %1752 = inttoptr i64 %1751 to ptr addrspace(1)		; visa id: 1705
  %1753 = load <2 x i32>, ptr addrspace(1) %1752, align 4		; visa id: 1705
  %1754 = and i32 %153, 255
  %1755 = and i32 %182, 768		; visa id: 1706
  %1756 = or i32 %1754, %1755		; visa id: 1707
  %1757 = shl nuw nsw i32 %1756, 3, !spirv.Decorations !8791		; visa id: 1708
  %1758 = zext i32 %1757 to i64		; visa id: 1709
  %1759 = add i64 %121, %1758		; visa id: 1710
  %1760 = inttoptr i64 %1759 to ptr addrspace(1)		; visa id: 1711
  %1761 = load <2 x i32>, ptr addrspace(1) %1760, align 4		; visa id: 1711
  %1762 = extractelement <2 x i32> %1753, i32 0		; visa id: 1712
  %1763 = extractelement <2 x i32> %1753, i32 1		; visa id: 1712
  %1764 = lshr i16 %162, 8		; visa id: 1712
  %1765 = extractelement <2 x i32> %1761, i32 0		; visa id: 1713
  %1766 = extractelement <2 x i32> %1761, i32 1		; visa id: 1713
  %1767 = or i32 %191, 64		; visa id: 1713
  %1768 = zext i32 %1767 to i64		; visa id: 1714
  %1769 = add i64 %1768, %const_reg_qword2		; visa id: 1715
  %IntToPtr2640 = inttoptr i64 %1769 to ptr addrspace(1)		; visa id: 1716
  %vCastload641 = load i32, ptr addrspace(1) %IntToPtr2640, align 2		; visa id: 1716
  %1770 = add i64 %1769, 4
  %IntToPtr2642 = inttoptr i64 %1770 to ptr addrspace(1)
  %vCastload643 = load i32, ptr addrspace(1) %IntToPtr2642, align 2		; visa id: 1717
  %1771 = add i64 %1769, 8
  %IntToPtr2644 = inttoptr i64 %1771 to ptr addrspace(1)
  %vCastload645 = load i32, ptr addrspace(1) %IntToPtr2644, align 2		; visa id: 1718
  %1772 = add i64 %1769, 12
  %IntToPtr2646 = inttoptr i64 %1772 to ptr addrspace(1)
  %vCastload647 = load i32, ptr addrspace(1) %IntToPtr2646, align 2		; visa id: 1719
  %1773 = bitcast i32 %vCastload641 to <2 x i16>		; visa id: 1720
  %1774 = bitcast i32 %vCastload643 to <2 x i16>		; visa id: 1722
  %1775 = extractelement <2 x i16> %1773, i32 0		; visa id: 1724
  %1776 = extractelement <2 x i16> %1773, i32 1		; visa id: 1724
  %1777 = extractelement <2 x i16> %1774, i32 0		; visa id: 1724
  %1778 = extractelement <2 x i16> %1774, i32 1		; visa id: 1724
  %1779 = bitcast i32 %vCastload645 to <2 x i16>		; visa id: 1724
  %1780 = bitcast i32 %vCastload647 to <2 x i16>		; visa id: 1726
  %1781 = extractelement <2 x i16> %1779, i32 0		; visa id: 1728
  %1782 = extractelement <2 x i16> %1779, i32 1		; visa id: 1728
  %1783 = extractelement <2 x i16> %1780, i32 0		; visa id: 1728
  %1784 = extractelement <2 x i16> %1780, i32 1		; visa id: 1728
  %1785 = zext i16 %1745 to i32		; visa id: 1728
  %1786 = and i32 %1785, 15		; visa id: 1729
  %1787 = uitofp i32 %1786 to float		; visa id: 1730
  %1788 = fadd float %1787, 5.000000e-01		; visa id: 1731
  %1789 = fmul float %147, %1788		; visa id: 1732
  %1790 = fmul float %1789, 2.500000e-01		; visa id: 1733
  %1791 = bitcast float %1790 to i32
  %1792 = and i32 %1791, 2147483647		; visa id: 1734
  %1793 = icmp ugt i32 %1792, 2139095040
  %1794 = fcmp oeq float %220, 0x7FF0000000000000		; visa id: 1735
  %1795 = fcmp une float %220, %220
  %1796 = or i1 %1795, %1794		; visa id: 1736
  %1797 = or i1 %1796, %1793		; visa id: 1738
  %1798 = and i32 %1762, 255		; visa id: 1740
  br i1 %1797, label %1806, label %1799, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1741

1799:                                             ; preds = %._crit_edge43.4
; BB202 :
  %1800 = and i32 %132, 256
  %1801 = sub nsw i32 0, %1798, !spirv.Decorations !8798
  %1802 = icmp eq i32 %1800, 0		; visa id: 1743
  %1803 = select i1 %1802, i32 %1798, i32 %1801		; visa id: 1745
  %1804 = sitofp i32 %1803 to float		; visa id: 1746
  %1805 = fmul float %1790, %1804		; visa id: 1747
  br label %1814, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1748

1806:                                             ; preds = %._crit_edge43.4
; BB203 :
  %1807 = uitofp i32 %1798 to float		; visa id: 1750
  %1808 = fmul float %1790, %1807		; visa id: 1751
  %1809 = and i32 %132, 256
  %1810 = icmp eq i32 %1809, 0		; visa id: 1752
  %1811 = select i1 %1810, i32 1, i32 -1		; visa id: 1754
  %1812 = sitofp i32 %1811 to float		; visa id: 1755
  %1813 = fmul float %1808, %1812		; visa id: 1756
  br label %1814, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1757

1814:                                             ; preds = %1806, %1799
; BB204 :
  %.sroa.061.8 = phi float [ %1813, %1806 ], [ %1805, %1799 ]
  %1815 = bitcast i32 %1762 to <4 x i8>
  %1816 = extractelement <4 x i8> %1815, i32 1
  %1817 = zext i8 %1816 to i32		; visa id: 1758
  br i1 %1797, label %1825, label %1818, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1759

1818:                                             ; preds = %1814
; BB205 :
  %1819 = and i32 %132, 512
  %1820 = sub nsw i32 0, %1817, !spirv.Decorations !8798
  %1821 = icmp eq i32 %1819, 0		; visa id: 1761
  %1822 = select i1 %1821, i32 %1817, i32 %1820		; visa id: 1763
  %1823 = sitofp i32 %1822 to float		; visa id: 1764
  %1824 = fmul float %1790, %1823		; visa id: 1765
  br label %1833, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1766

1825:                                             ; preds = %1814
; BB206 :
  %1826 = uitofp i32 %1817 to float		; visa id: 1768
  %1827 = fmul float %1790, %1826		; visa id: 1769
  %1828 = and i32 %132, 512
  %1829 = icmp eq i32 %1828, 0		; visa id: 1770
  %1830 = select i1 %1829, i32 1, i32 -1		; visa id: 1772
  %1831 = sitofp i32 %1830 to float		; visa id: 1773
  %1832 = fmul float %1827, %1831		; visa id: 1774
  br label %1833, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1775

1833:                                             ; preds = %1825, %1818
; BB207 :
  %.sroa.80.8 = phi float [ %1832, %1825 ], [ %1824, %1818 ]
  %1834 = extractelement <4 x i8> %1815, i32 2
  %1835 = zext i8 %1834 to i32		; visa id: 1776
  br i1 %1797, label %1843, label %1836, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1777

1836:                                             ; preds = %1833
; BB208 :
  %1837 = and i32 %132, 1024
  %1838 = sub nsw i32 0, %1835, !spirv.Decorations !8798
  %1839 = icmp eq i32 %1837, 0		; visa id: 1779
  %1840 = select i1 %1839, i32 %1835, i32 %1838		; visa id: 1781
  %1841 = sitofp i32 %1840 to float		; visa id: 1782
  %1842 = fmul float %1790, %1841		; visa id: 1783
  br label %1851, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1784

1843:                                             ; preds = %1833
; BB209 :
  %1844 = uitofp i32 %1835 to float		; visa id: 1786
  %1845 = fmul float %1790, %1844		; visa id: 1787
  %1846 = and i32 %132, 1024
  %1847 = icmp eq i32 %1846, 0		; visa id: 1788
  %1848 = select i1 %1847, i32 1, i32 -1		; visa id: 1790
  %1849 = sitofp i32 %1848 to float		; visa id: 1791
  %1850 = fmul float %1845, %1849		; visa id: 1792
  br label %1851, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1793

1851:                                             ; preds = %1843, %1836
; BB210 :
  %.sroa.128.8 = phi float [ %1850, %1843 ], [ %1842, %1836 ]
  %1852 = lshr i32 %1762, 24		; visa id: 1794
  br i1 %1797, label %1860, label %1853, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1795

1853:                                             ; preds = %1851
; BB211 :
  %1854 = and i32 %132, 2048
  %1855 = sub nsw i32 0, %1852, !spirv.Decorations !8798
  %1856 = icmp eq i32 %1854, 0		; visa id: 1797
  %1857 = select i1 %1856, i32 %1852, i32 %1855		; visa id: 1799
  %1858 = sitofp i32 %1857 to float		; visa id: 1800
  %1859 = fmul float %1790, %1858		; visa id: 1801
  br label %1868, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1802

1860:                                             ; preds = %1851
; BB212 :
  %1861 = uitofp i32 %1852 to float		; visa id: 1804
  %1862 = fmul float %1790, %1861		; visa id: 1805
  %1863 = and i32 %132, 2048
  %1864 = icmp eq i32 %1863, 0		; visa id: 1806
  %1865 = select i1 %1864, i32 1, i32 -1		; visa id: 1808
  %1866 = sitofp i32 %1865 to float		; visa id: 1809
  %1867 = fmul float %1862, %1866		; visa id: 1810
  br label %1868, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1811

1868:                                             ; preds = %1860, %1853
; BB213 :
  %.sroa.176.8 = phi float [ %1867, %1860 ], [ %1859, %1853 ]
  %1869 = and i32 %1763, 255		; visa id: 1812
  br i1 %1797, label %1877, label %1870, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1813

1870:                                             ; preds = %1868
; BB214 :
  %1871 = and i32 %132, 4096
  %1872 = sub nsw i32 0, %1869, !spirv.Decorations !8798
  %1873 = icmp eq i32 %1871, 0		; visa id: 1815
  %1874 = select i1 %1873, i32 %1869, i32 %1872		; visa id: 1817
  %1875 = sitofp i32 %1874 to float		; visa id: 1818
  %1876 = fmul float %1790, %1875		; visa id: 1819
  br label %1885, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1820

1877:                                             ; preds = %1868
; BB215 :
  %1878 = uitofp i32 %1869 to float		; visa id: 1822
  %1879 = fmul float %1790, %1878		; visa id: 1823
  %1880 = and i32 %132, 4096
  %1881 = icmp eq i32 %1880, 0		; visa id: 1824
  %1882 = select i1 %1881, i32 1, i32 -1		; visa id: 1826
  %1883 = sitofp i32 %1882 to float		; visa id: 1827
  %1884 = fmul float %1879, %1883		; visa id: 1828
  br label %1885, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1829

1885:                                             ; preds = %1877, %1870
; BB216 :
  %.sroa.224.8 = phi float [ %1884, %1877 ], [ %1876, %1870 ]
  %1886 = bitcast i32 %1763 to <4 x i8>
  %1887 = extractelement <4 x i8> %1886, i32 1
  %1888 = zext i8 %1887 to i32		; visa id: 1830
  br i1 %1797, label %1896, label %1889, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1831

1889:                                             ; preds = %1885
; BB217 :
  %1890 = and i32 %132, 8192
  %1891 = sub nsw i32 0, %1888, !spirv.Decorations !8798
  %1892 = icmp eq i32 %1890, 0		; visa id: 1833
  %1893 = select i1 %1892, i32 %1888, i32 %1891		; visa id: 1835
  %1894 = sitofp i32 %1893 to float		; visa id: 1836
  %1895 = fmul float %1790, %1894		; visa id: 1837
  br label %1904, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1838

1896:                                             ; preds = %1885
; BB218 :
  %1897 = uitofp i32 %1888 to float		; visa id: 1840
  %1898 = fmul float %1790, %1897		; visa id: 1841
  %1899 = and i32 %132, 8192
  %1900 = icmp eq i32 %1899, 0		; visa id: 1842
  %1901 = select i1 %1900, i32 1, i32 -1		; visa id: 1844
  %1902 = sitofp i32 %1901 to float		; visa id: 1845
  %1903 = fmul float %1898, %1902		; visa id: 1846
  br label %1904, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1847

1904:                                             ; preds = %1896, %1889
; BB219 :
  %.sroa.272.8 = phi float [ %1903, %1896 ], [ %1895, %1889 ]
  %1905 = extractelement <4 x i8> %1886, i32 2
  %1906 = zext i8 %1905 to i32		; visa id: 1848
  br i1 %1797, label %1914, label %1907, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1849

1907:                                             ; preds = %1904
; BB220 :
  %1908 = and i32 %132, 16384
  %1909 = sub nsw i32 0, %1906, !spirv.Decorations !8798
  %1910 = icmp eq i32 %1908, 0		; visa id: 1851
  %1911 = select i1 %1910, i32 %1906, i32 %1909		; visa id: 1853
  %1912 = sitofp i32 %1911 to float		; visa id: 1854
  %1913 = fmul float %1790, %1912		; visa id: 1855
  br label %1922, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1856

1914:                                             ; preds = %1904
; BB221 :
  %1915 = uitofp i32 %1906 to float		; visa id: 1858
  %1916 = fmul float %1790, %1915		; visa id: 1859
  %1917 = and i32 %132, 16384
  %1918 = icmp eq i32 %1917, 0		; visa id: 1860
  %1919 = select i1 %1918, i32 1, i32 -1		; visa id: 1862
  %1920 = sitofp i32 %1919 to float		; visa id: 1863
  %1921 = fmul float %1916, %1920		; visa id: 1864
  br label %1922, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1865

1922:                                             ; preds = %1914, %1907
; BB222 :
  %.sroa.320.8 = phi float [ %1921, %1914 ], [ %1913, %1907 ]
  %1923 = lshr i32 %1763, 24		; visa id: 1866
  br i1 %1797, label %1931, label %1924, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1867

1924:                                             ; preds = %1922
; BB223 :
  %1925 = and i32 %132, 32768
  %1926 = sub nsw i32 0, %1923, !spirv.Decorations !8798
  %1927 = icmp eq i32 %1925, 0		; visa id: 1869
  %1928 = select i1 %1927, i32 %1923, i32 %1926		; visa id: 1871
  %1929 = sitofp i32 %1928 to float		; visa id: 1872
  %1930 = fmul float %1790, %1929		; visa id: 1873
  br label %1939, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1874

1931:                                             ; preds = %1922
; BB224 :
  %1932 = uitofp i32 %1923 to float		; visa id: 1876
  %1933 = fmul float %1790, %1932		; visa id: 1877
  %1934 = and i32 %132, 32768
  %1935 = icmp eq i32 %1934, 0		; visa id: 1878
  %1936 = select i1 %1935, i32 1, i32 -1		; visa id: 1880
  %1937 = sitofp i32 %1936 to float		; visa id: 1881
  %1938 = fmul float %1933, %1937		; visa id: 1882
  br label %1939, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1883

1939:                                             ; preds = %1931, %1924
; BB225 :
  %.sroa.368.8 = phi float [ %1938, %1931 ], [ %1930, %1924 ]
  %1940 = zext i16 %1775 to i32		; visa id: 1884
  %1941 = shl nuw i32 %1940, 16		; visa id: 1885
  %1942 = bitcast i32 %1941 to float
  %1943 = fmul float %.sroa.061.8, %1942		; visa id: 1886
  %1944 = fadd float %.sroa.12.0, %1943		; visa id: 1887
  %1945 = zext i16 %1776 to i32		; visa id: 1888
  %1946 = shl nuw i32 %1945, 16		; visa id: 1889
  %1947 = bitcast i32 %1946 to float
  %1948 = fmul float %.sroa.80.8, %1947		; visa id: 1890
  %1949 = fadd float %1944, %1948		; visa id: 1891
  %1950 = zext i16 %1777 to i32		; visa id: 1892
  %1951 = shl nuw i32 %1950, 16		; visa id: 1893
  %1952 = bitcast i32 %1951 to float
  %1953 = fmul float %.sroa.128.8, %1952		; visa id: 1894
  %1954 = fadd float %1949, %1953		; visa id: 1895
  %1955 = zext i16 %1778 to i32		; visa id: 1896
  %1956 = shl nuw i32 %1955, 16		; visa id: 1897
  %1957 = bitcast i32 %1956 to float
  %1958 = fmul float %.sroa.176.8, %1957		; visa id: 1898
  %1959 = fadd float %1954, %1958		; visa id: 1899
  %1960 = zext i16 %1781 to i32		; visa id: 1900
  %1961 = shl nuw i32 %1960, 16		; visa id: 1901
  %1962 = bitcast i32 %1961 to float
  %1963 = fmul float %.sroa.224.8, %1962		; visa id: 1902
  %1964 = fadd float %1959, %1963		; visa id: 1903
  %1965 = zext i16 %1782 to i32		; visa id: 1904
  %1966 = shl nuw i32 %1965, 16		; visa id: 1905
  %1967 = bitcast i32 %1966 to float
  %1968 = fmul float %.sroa.272.8, %1967		; visa id: 1906
  %1969 = fadd float %1964, %1968		; visa id: 1907
  %1970 = zext i16 %1783 to i32		; visa id: 1908
  %1971 = shl nuw i32 %1970, 16		; visa id: 1909
  %1972 = bitcast i32 %1971 to float
  %1973 = fmul float %.sroa.320.8, %1972		; visa id: 1910
  %1974 = fadd float %1969, %1973		; visa id: 1911
  %1975 = zext i16 %1784 to i32		; visa id: 1912
  %1976 = shl nuw i32 %1975, 16		; visa id: 1913
  %1977 = bitcast i32 %1976 to float
  %1978 = fmul float %.sroa.368.8, %1977		; visa id: 1914
  %1979 = fadd float %1974, %1978		; visa id: 1915
  %1980 = zext i16 %1764 to i32		; visa id: 1916
  %1981 = and i32 %1980, 15		; visa id: 1917
  %1982 = uitofp i32 %1981 to float		; visa id: 1918
  %1983 = fadd float %1982, 5.000000e-01		; visa id: 1919
  %1984 = fmul float %166, %1983		; visa id: 1920
  %1985 = fmul float %1984, 2.500000e-01		; visa id: 1921
  %1986 = bitcast float %1985 to i32
  %1987 = and i32 %1986, 2147483647		; visa id: 1922
  %1988 = icmp ugt i32 %1987, 2139095040		; visa id: 1923
  %1989 = or i1 %422, %1988		; visa id: 1924
  %1990 = and i32 %1765, 255		; visa id: 1925
  br i1 %1989, label %1998, label %1991, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1926

1991:                                             ; preds = %1939
; BB226 :
  %1992 = and i32 %153, 256
  %1993 = sub nsw i32 0, %1990, !spirv.Decorations !8798
  %1994 = icmp eq i32 %1992, 0		; visa id: 1928
  %1995 = select i1 %1994, i32 %1990, i32 %1993		; visa id: 1930
  %1996 = sitofp i32 %1995 to float		; visa id: 1931
  %1997 = fmul float %1985, %1996		; visa id: 1932
  br label %2006, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1933

1998:                                             ; preds = %1939
; BB227 :
  %1999 = uitofp i32 %1990 to float		; visa id: 1935
  %2000 = fmul float %1985, %1999		; visa id: 1936
  %2001 = and i32 %153, 256
  %2002 = icmp eq i32 %2001, 0		; visa id: 1937
  %2003 = select i1 %2002, i32 1, i32 -1		; visa id: 1939
  %2004 = sitofp i32 %2003 to float		; visa id: 1940
  %2005 = fmul float %2000, %2004		; visa id: 1941
  br label %2006, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1942

2006:                                             ; preds = %1998, %1991
; BB228 :
  %.sroa.061.9 = phi float [ %2005, %1998 ], [ %1997, %1991 ]
  %2007 = bitcast i32 %1765 to <4 x i8>
  %2008 = extractelement <4 x i8> %2007, i32 1
  %2009 = zext i8 %2008 to i32		; visa id: 1943
  br i1 %1989, label %2017, label %2010, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1944

2010:                                             ; preds = %2006
; BB229 :
  %2011 = and i32 %153, 512
  %2012 = sub nsw i32 0, %2009, !spirv.Decorations !8798
  %2013 = icmp eq i32 %2011, 0		; visa id: 1946
  %2014 = select i1 %2013, i32 %2009, i32 %2012		; visa id: 1948
  %2015 = sitofp i32 %2014 to float		; visa id: 1949
  %2016 = fmul float %1985, %2015		; visa id: 1950
  br label %2025, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1951

2017:                                             ; preds = %2006
; BB230 :
  %2018 = uitofp i32 %2009 to float		; visa id: 1953
  %2019 = fmul float %1985, %2018		; visa id: 1954
  %2020 = and i32 %153, 512
  %2021 = icmp eq i32 %2020, 0		; visa id: 1955
  %2022 = select i1 %2021, i32 1, i32 -1		; visa id: 1957
  %2023 = sitofp i32 %2022 to float		; visa id: 1958
  %2024 = fmul float %2019, %2023		; visa id: 1959
  br label %2025, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1960

2025:                                             ; preds = %2017, %2010
; BB231 :
  %.sroa.80.9 = phi float [ %2024, %2017 ], [ %2016, %2010 ]
  %2026 = extractelement <4 x i8> %2007, i32 2
  %2027 = zext i8 %2026 to i32		; visa id: 1961
  br i1 %1989, label %2035, label %2028, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1962

2028:                                             ; preds = %2025
; BB232 :
  %2029 = and i32 %153, 1024
  %2030 = sub nsw i32 0, %2027, !spirv.Decorations !8798
  %2031 = icmp eq i32 %2029, 0		; visa id: 1964
  %2032 = select i1 %2031, i32 %2027, i32 %2030		; visa id: 1966
  %2033 = sitofp i32 %2032 to float		; visa id: 1967
  %2034 = fmul float %1985, %2033		; visa id: 1968
  br label %2043, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1969

2035:                                             ; preds = %2025
; BB233 :
  %2036 = uitofp i32 %2027 to float		; visa id: 1971
  %2037 = fmul float %1985, %2036		; visa id: 1972
  %2038 = and i32 %153, 1024
  %2039 = icmp eq i32 %2038, 0		; visa id: 1973
  %2040 = select i1 %2039, i32 1, i32 -1		; visa id: 1975
  %2041 = sitofp i32 %2040 to float		; visa id: 1976
  %2042 = fmul float %2037, %2041		; visa id: 1977
  br label %2043, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1978

2043:                                             ; preds = %2035, %2028
; BB234 :
  %.sroa.128.9 = phi float [ %2042, %2035 ], [ %2034, %2028 ]
  %2044 = lshr i32 %1765, 24		; visa id: 1979
  br i1 %1989, label %2052, label %2045, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1980

2045:                                             ; preds = %2043
; BB235 :
  %2046 = and i32 %153, 2048
  %2047 = sub nsw i32 0, %2044, !spirv.Decorations !8798
  %2048 = icmp eq i32 %2046, 0		; visa id: 1982
  %2049 = select i1 %2048, i32 %2044, i32 %2047		; visa id: 1984
  %2050 = sitofp i32 %2049 to float		; visa id: 1985
  %2051 = fmul float %1985, %2050		; visa id: 1986
  br label %2060, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1987

2052:                                             ; preds = %2043
; BB236 :
  %2053 = uitofp i32 %2044 to float		; visa id: 1989
  %2054 = fmul float %1985, %2053		; visa id: 1990
  %2055 = and i32 %153, 2048
  %2056 = icmp eq i32 %2055, 0		; visa id: 1991
  %2057 = select i1 %2056, i32 1, i32 -1		; visa id: 1993
  %2058 = sitofp i32 %2057 to float		; visa id: 1994
  %2059 = fmul float %2054, %2058		; visa id: 1995
  br label %2060, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1996

2060:                                             ; preds = %2052, %2045
; BB237 :
  %.sroa.176.9 = phi float [ %2059, %2052 ], [ %2051, %2045 ]
  %2061 = and i32 %1766, 255		; visa id: 1997
  br i1 %1989, label %2069, label %2062, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1998

2062:                                             ; preds = %2060
; BB238 :
  %2063 = and i32 %153, 4096
  %2064 = sub nsw i32 0, %2061, !spirv.Decorations !8798
  %2065 = icmp eq i32 %2063, 0		; visa id: 2000
  %2066 = select i1 %2065, i32 %2061, i32 %2064		; visa id: 2002
  %2067 = sitofp i32 %2066 to float		; visa id: 2003
  %2068 = fmul float %1985, %2067		; visa id: 2004
  br label %2077, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2005

2069:                                             ; preds = %2060
; BB239 :
  %2070 = uitofp i32 %2061 to float		; visa id: 2007
  %2071 = fmul float %1985, %2070		; visa id: 2008
  %2072 = and i32 %153, 4096
  %2073 = icmp eq i32 %2072, 0		; visa id: 2009
  %2074 = select i1 %2073, i32 1, i32 -1		; visa id: 2011
  %2075 = sitofp i32 %2074 to float		; visa id: 2012
  %2076 = fmul float %2071, %2075		; visa id: 2013
  br label %2077, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2014

2077:                                             ; preds = %2069, %2062
; BB240 :
  %.sroa.224.9 = phi float [ %2076, %2069 ], [ %2068, %2062 ]
  %2078 = bitcast i32 %1766 to <4 x i8>
  %2079 = extractelement <4 x i8> %2078, i32 1
  %2080 = zext i8 %2079 to i32		; visa id: 2015
  br i1 %1989, label %2088, label %2081, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2016

2081:                                             ; preds = %2077
; BB241 :
  %2082 = and i32 %153, 8192
  %2083 = sub nsw i32 0, %2080, !spirv.Decorations !8798
  %2084 = icmp eq i32 %2082, 0		; visa id: 2018
  %2085 = select i1 %2084, i32 %2080, i32 %2083		; visa id: 2020
  %2086 = sitofp i32 %2085 to float		; visa id: 2021
  %2087 = fmul float %1985, %2086		; visa id: 2022
  br label %2096, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2023

2088:                                             ; preds = %2077
; BB242 :
  %2089 = uitofp i32 %2080 to float		; visa id: 2025
  %2090 = fmul float %1985, %2089		; visa id: 2026
  %2091 = and i32 %153, 8192
  %2092 = icmp eq i32 %2091, 0		; visa id: 2027
  %2093 = select i1 %2092, i32 1, i32 -1		; visa id: 2029
  %2094 = sitofp i32 %2093 to float		; visa id: 2030
  %2095 = fmul float %2090, %2094		; visa id: 2031
  br label %2096, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2032

2096:                                             ; preds = %2088, %2081
; BB243 :
  %.sroa.272.9 = phi float [ %2095, %2088 ], [ %2087, %2081 ]
  %2097 = extractelement <4 x i8> %2078, i32 2
  %2098 = zext i8 %2097 to i32		; visa id: 2033
  br i1 %1989, label %2106, label %2099, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2034

2099:                                             ; preds = %2096
; BB244 :
  %2100 = and i32 %153, 16384
  %2101 = sub nsw i32 0, %2098, !spirv.Decorations !8798
  %2102 = icmp eq i32 %2100, 0		; visa id: 2036
  %2103 = select i1 %2102, i32 %2098, i32 %2101		; visa id: 2038
  %2104 = sitofp i32 %2103 to float		; visa id: 2039
  %2105 = fmul float %1985, %2104		; visa id: 2040
  br label %2114, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2041

2106:                                             ; preds = %2096
; BB245 :
  %2107 = uitofp i32 %2098 to float		; visa id: 2043
  %2108 = fmul float %1985, %2107		; visa id: 2044
  %2109 = and i32 %153, 16384
  %2110 = icmp eq i32 %2109, 0		; visa id: 2045
  %2111 = select i1 %2110, i32 1, i32 -1		; visa id: 2047
  %2112 = sitofp i32 %2111 to float		; visa id: 2048
  %2113 = fmul float %2108, %2112		; visa id: 2049
  br label %2114, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2050

2114:                                             ; preds = %2106, %2099
; BB246 :
  %.sroa.320.9 = phi float [ %2113, %2106 ], [ %2105, %2099 ]
  %2115 = lshr i32 %1766, 24		; visa id: 2051
  br i1 %1989, label %2123, label %2116, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2052

2116:                                             ; preds = %2114
; BB247 :
  %2117 = and i32 %153, 32768
  %2118 = sub nsw i32 0, %2115, !spirv.Decorations !8798
  %2119 = icmp eq i32 %2117, 0		; visa id: 2054
  %2120 = select i1 %2119, i32 %2115, i32 %2118		; visa id: 2056
  %2121 = sitofp i32 %2120 to float		; visa id: 2057
  %2122 = fmul float %1985, %2121		; visa id: 2058
  br label %._crit_edge43.5, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2059

2123:                                             ; preds = %2114
; BB248 :
  %2124 = uitofp i32 %2115 to float		; visa id: 2061
  %2125 = fmul float %1985, %2124		; visa id: 2062
  %2126 = and i32 %153, 32768
  %2127 = icmp eq i32 %2126, 0		; visa id: 2063
  %2128 = select i1 %2127, i32 1, i32 -1		; visa id: 2065
  %2129 = sitofp i32 %2128 to float		; visa id: 2066
  %2130 = fmul float %2125, %2129		; visa id: 2067
  br label %._crit_edge43.5, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2068

._crit_edge43.5:                                  ; preds = %2123, %2116
; BB249 :
  %.sroa.368.9 = phi float [ %2130, %2123 ], [ %2122, %2116 ]
  %2131 = fmul float %.sroa.061.9, %1942		; visa id: 2069
  %2132 = fadd float %.sroa.29.0, %2131		; visa id: 2070
  %2133 = fmul float %.sroa.80.9, %1947		; visa id: 2071
  %2134 = fadd float %2132, %2133		; visa id: 2072
  %2135 = fmul float %.sroa.128.9, %1952		; visa id: 2073
  %2136 = fadd float %2134, %2135		; visa id: 2074
  %2137 = fmul float %.sroa.176.9, %1957		; visa id: 2075
  %2138 = fadd float %2136, %2137		; visa id: 2076
  %2139 = fmul float %.sroa.224.9, %1962		; visa id: 2077
  %2140 = fadd float %2138, %2139		; visa id: 2078
  %2141 = fmul float %.sroa.272.9, %1967		; visa id: 2079
  %2142 = fadd float %2140, %2141		; visa id: 2080
  %2143 = fmul float %.sroa.320.9, %1972		; visa id: 2081
  %2144 = fadd float %2142, %2143		; visa id: 2082
  %2145 = fmul float %.sroa.368.9, %1977		; visa id: 2083
  %2146 = fadd float %2144, %2145		; visa id: 2084
  %2147 = bitcast i32 %132 to <4 x i8>
  %2148 = extractelement <4 x i8> %2147, i32 2
  %2149 = lshr i32 %168, 2		; visa id: 2085
  %2150 = and i32 %2149, 768
  %2151 = zext i8 %2148 to i32		; visa id: 2086
  %2152 = or i32 %2151, %2150		; visa id: 2087
  %2153 = shl nuw nsw i32 %2152, 3, !spirv.Decorations !8791		; visa id: 2088
  %2154 = zext i32 %2153 to i64		; visa id: 2089
  %2155 = add i64 %121, %2154		; visa id: 2090
  %2156 = inttoptr i64 %2155 to ptr addrspace(1)		; visa id: 2091
  %2157 = load <2 x i32>, ptr addrspace(1) %2156, align 4		; visa id: 2091
  %2158 = bitcast i32 %153 to <4 x i8>
  %2159 = extractelement <4 x i8> %2158, i32 2
  %2160 = lshr i32 %182, 2		; visa id: 2092
  %2161 = and i32 %2160, 768
  %2162 = zext i8 %2159 to i32		; visa id: 2093
  %2163 = or i32 %2162, %2161		; visa id: 2094
  %2164 = shl nuw nsw i32 %2163, 3, !spirv.Decorations !8791		; visa id: 2095
  %2165 = zext i32 %2164 to i64		; visa id: 2096
  %2166 = add i64 %121, %2165		; visa id: 2097
  %2167 = inttoptr i64 %2166 to ptr addrspace(1)		; visa id: 2098
  %2168 = load <2 x i32>, ptr addrspace(1) %2167, align 4		; visa id: 2098
  %2169 = extractelement <2 x i32> %2157, i32 0		; visa id: 2099
  %2170 = extractelement <2 x i32> %2157, i32 1		; visa id: 2099
  %2171 = extractelement <2 x i32> %2168, i32 0		; visa id: 2099
  %2172 = extractelement <2 x i32> %2168, i32 1		; visa id: 2099
  %2173 = or i32 %191, 80		; visa id: 2099
  %2174 = zext i32 %2173 to i64		; visa id: 2100
  %2175 = add i64 %2174, %const_reg_qword2		; visa id: 2101
  %IntToPtr2648 = inttoptr i64 %2175 to ptr addrspace(1)		; visa id: 2102
  %vCastload649 = load i32, ptr addrspace(1) %IntToPtr2648, align 2		; visa id: 2102
  %2176 = add i64 %2175, 4
  %IntToPtr2650 = inttoptr i64 %2176 to ptr addrspace(1)
  %vCastload651 = load i32, ptr addrspace(1) %IntToPtr2650, align 2		; visa id: 2103
  %2177 = add i64 %2175, 8
  %IntToPtr2652 = inttoptr i64 %2177 to ptr addrspace(1)
  %vCastload653 = load i32, ptr addrspace(1) %IntToPtr2652, align 2		; visa id: 2104
  %2178 = add i64 %2175, 12
  %IntToPtr2654 = inttoptr i64 %2178 to ptr addrspace(1)
  %vCastload655 = load i32, ptr addrspace(1) %IntToPtr2654, align 2		; visa id: 2105
  %2179 = bitcast i32 %vCastload649 to <2 x i16>		; visa id: 2106
  %2180 = bitcast i32 %vCastload651 to <2 x i16>		; visa id: 2108
  %2181 = extractelement <2 x i16> %2179, i32 0		; visa id: 2110
  %2182 = extractelement <2 x i16> %2179, i32 1		; visa id: 2110
  %2183 = extractelement <2 x i16> %2180, i32 0		; visa id: 2110
  %2184 = extractelement <2 x i16> %2180, i32 1		; visa id: 2110
  %2185 = bitcast i32 %vCastload653 to <2 x i16>		; visa id: 2110
  %2186 = bitcast i32 %vCastload655 to <2 x i16>		; visa id: 2112
  %2187 = extractelement <2 x i16> %2185, i32 0		; visa id: 2114
  %2188 = extractelement <2 x i16> %2185, i32 1		; visa id: 2114
  %2189 = extractelement <2 x i16> %2186, i32 0		; visa id: 2114
  %2190 = extractelement <2 x i16> %2186, i32 1		; visa id: 2114
  %2191 = and i32 %2169, 255		; visa id: 2114
  br i1 %1797, label %2199, label %2192, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2115

2192:                                             ; preds = %._crit_edge43.5
; BB250 :
  %2193 = and i32 %132, 16777216
  %2194 = sub nsw i32 0, %2191, !spirv.Decorations !8798
  %2195 = icmp eq i32 %2193, 0		; visa id: 2117
  %2196 = select i1 %2195, i32 %2191, i32 %2194		; visa id: 2119
  %2197 = sitofp i32 %2196 to float		; visa id: 2120
  %2198 = fmul float %1790, %2197		; visa id: 2121
  br label %2207, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2122

2199:                                             ; preds = %._crit_edge43.5
; BB251 :
  %2200 = uitofp i32 %2191 to float		; visa id: 2124
  %2201 = fmul float %1790, %2200		; visa id: 2125
  %2202 = and i32 %132, 16777216
  %2203 = icmp eq i32 %2202, 0		; visa id: 2126
  %2204 = select i1 %2203, i32 1, i32 -1		; visa id: 2128
  %2205 = sitofp i32 %2204 to float		; visa id: 2129
  %2206 = fmul float %2201, %2205		; visa id: 2130
  br label %2207, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2131

2207:                                             ; preds = %2199, %2192
; BB252 :
  %.sroa.061.10 = phi float [ %2206, %2199 ], [ %2198, %2192 ]
  %2208 = bitcast i32 %2169 to <4 x i8>
  %2209 = extractelement <4 x i8> %2208, i32 1
  %2210 = zext i8 %2209 to i32		; visa id: 2132
  br i1 %1797, label %2218, label %2211, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2133

2211:                                             ; preds = %2207
; BB253 :
  %2212 = and i32 %132, 33554432
  %2213 = sub nsw i32 0, %2210, !spirv.Decorations !8798
  %2214 = icmp eq i32 %2212, 0		; visa id: 2135
  %2215 = select i1 %2214, i32 %2210, i32 %2213		; visa id: 2137
  %2216 = sitofp i32 %2215 to float		; visa id: 2138
  %2217 = fmul float %1790, %2216		; visa id: 2139
  br label %2226, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2140

2218:                                             ; preds = %2207
; BB254 :
  %2219 = uitofp i32 %2210 to float		; visa id: 2142
  %2220 = fmul float %1790, %2219		; visa id: 2143
  %2221 = and i32 %132, 33554432
  %2222 = icmp eq i32 %2221, 0		; visa id: 2144
  %2223 = select i1 %2222, i32 1, i32 -1		; visa id: 2146
  %2224 = sitofp i32 %2223 to float		; visa id: 2147
  %2225 = fmul float %2220, %2224		; visa id: 2148
  br label %2226, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2149

2226:                                             ; preds = %2218, %2211
; BB255 :
  %.sroa.80.10 = phi float [ %2225, %2218 ], [ %2217, %2211 ]
  %2227 = extractelement <4 x i8> %2208, i32 2
  %2228 = zext i8 %2227 to i32		; visa id: 2150
  br i1 %1797, label %2236, label %2229, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2151

2229:                                             ; preds = %2226
; BB256 :
  %2230 = and i32 %132, 67108864
  %2231 = sub nsw i32 0, %2228, !spirv.Decorations !8798
  %2232 = icmp eq i32 %2230, 0		; visa id: 2153
  %2233 = select i1 %2232, i32 %2228, i32 %2231		; visa id: 2155
  %2234 = sitofp i32 %2233 to float		; visa id: 2156
  %2235 = fmul float %1790, %2234		; visa id: 2157
  br label %2244, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2158

2236:                                             ; preds = %2226
; BB257 :
  %2237 = uitofp i32 %2228 to float		; visa id: 2160
  %2238 = fmul float %1790, %2237		; visa id: 2161
  %2239 = and i32 %132, 67108864
  %2240 = icmp eq i32 %2239, 0		; visa id: 2162
  %2241 = select i1 %2240, i32 1, i32 -1		; visa id: 2164
  %2242 = sitofp i32 %2241 to float		; visa id: 2165
  %2243 = fmul float %2238, %2242		; visa id: 2166
  br label %2244, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2167

2244:                                             ; preds = %2236, %2229
; BB258 :
  %.sroa.128.10 = phi float [ %2243, %2236 ], [ %2235, %2229 ]
  %2245 = lshr i32 %2169, 24		; visa id: 2168
  br i1 %1797, label %2253, label %2246, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2169

2246:                                             ; preds = %2244
; BB259 :
  %2247 = and i32 %132, 134217728
  %2248 = sub nsw i32 0, %2245, !spirv.Decorations !8798
  %2249 = icmp eq i32 %2247, 0		; visa id: 2171
  %2250 = select i1 %2249, i32 %2245, i32 %2248		; visa id: 2173
  %2251 = sitofp i32 %2250 to float		; visa id: 2174
  %2252 = fmul float %1790, %2251		; visa id: 2175
  br label %2261, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2176

2253:                                             ; preds = %2244
; BB260 :
  %2254 = uitofp i32 %2245 to float		; visa id: 2178
  %2255 = fmul float %1790, %2254		; visa id: 2179
  %2256 = and i32 %132, 134217728
  %2257 = icmp eq i32 %2256, 0		; visa id: 2180
  %2258 = select i1 %2257, i32 1, i32 -1		; visa id: 2182
  %2259 = sitofp i32 %2258 to float		; visa id: 2183
  %2260 = fmul float %2255, %2259		; visa id: 2184
  br label %2261, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2185

2261:                                             ; preds = %2253, %2246
; BB261 :
  %.sroa.176.10 = phi float [ %2260, %2253 ], [ %2252, %2246 ]
  %2262 = and i32 %2170, 255		; visa id: 2186
  br i1 %1797, label %2270, label %2263, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2187

2263:                                             ; preds = %2261
; BB262 :
  %2264 = and i32 %132, 268435456
  %2265 = sub nsw i32 0, %2262, !spirv.Decorations !8798
  %2266 = icmp eq i32 %2264, 0		; visa id: 2189
  %2267 = select i1 %2266, i32 %2262, i32 %2265		; visa id: 2191
  %2268 = sitofp i32 %2267 to float		; visa id: 2192
  %2269 = fmul float %1790, %2268		; visa id: 2193
  br label %2278, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2194

2270:                                             ; preds = %2261
; BB263 :
  %2271 = uitofp i32 %2262 to float		; visa id: 2196
  %2272 = fmul float %1790, %2271		; visa id: 2197
  %2273 = and i32 %132, 268435456
  %2274 = icmp eq i32 %2273, 0		; visa id: 2198
  %2275 = select i1 %2274, i32 1, i32 -1		; visa id: 2200
  %2276 = sitofp i32 %2275 to float		; visa id: 2201
  %2277 = fmul float %2272, %2276		; visa id: 2202
  br label %2278, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2203

2278:                                             ; preds = %2270, %2263
; BB264 :
  %.sroa.224.10 = phi float [ %2277, %2270 ], [ %2269, %2263 ]
  %2279 = bitcast i32 %2170 to <4 x i8>
  %2280 = extractelement <4 x i8> %2279, i32 1
  %2281 = zext i8 %2280 to i32		; visa id: 2204
  br i1 %1797, label %2289, label %2282, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2205

2282:                                             ; preds = %2278
; BB265 :
  %2283 = and i32 %132, 536870912
  %2284 = sub nsw i32 0, %2281, !spirv.Decorations !8798
  %2285 = icmp eq i32 %2283, 0		; visa id: 2207
  %2286 = select i1 %2285, i32 %2281, i32 %2284		; visa id: 2209
  %2287 = sitofp i32 %2286 to float		; visa id: 2210
  %2288 = fmul float %1790, %2287		; visa id: 2211
  br label %2297, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2212

2289:                                             ; preds = %2278
; BB266 :
  %2290 = uitofp i32 %2281 to float		; visa id: 2214
  %2291 = fmul float %1790, %2290		; visa id: 2215
  %2292 = and i32 %132, 536870912
  %2293 = icmp eq i32 %2292, 0		; visa id: 2216
  %2294 = select i1 %2293, i32 1, i32 -1		; visa id: 2218
  %2295 = sitofp i32 %2294 to float		; visa id: 2219
  %2296 = fmul float %2291, %2295		; visa id: 2220
  br label %2297, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2221

2297:                                             ; preds = %2289, %2282
; BB267 :
  %.sroa.272.10 = phi float [ %2296, %2289 ], [ %2288, %2282 ]
  %2298 = extractelement <4 x i8> %2279, i32 2
  %2299 = zext i8 %2298 to i32		; visa id: 2222
  br i1 %1797, label %2307, label %2300, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2223

2300:                                             ; preds = %2297
; BB268 :
  %2301 = and i32 %132, 1073741824
  %2302 = sub nsw i32 0, %2299, !spirv.Decorations !8798
  %2303 = icmp eq i32 %2301, 0		; visa id: 2225
  %2304 = select i1 %2303, i32 %2299, i32 %2302		; visa id: 2227
  %2305 = sitofp i32 %2304 to float		; visa id: 2228
  %2306 = fmul float %1790, %2305		; visa id: 2229
  br label %2315, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2230

2307:                                             ; preds = %2297
; BB269 :
  %2308 = uitofp i32 %2299 to float		; visa id: 2232
  %2309 = fmul float %1790, %2308		; visa id: 2233
  %2310 = and i32 %132, 1073741824
  %2311 = icmp eq i32 %2310, 0		; visa id: 2234
  %2312 = select i1 %2311, i32 1, i32 -1		; visa id: 2236
  %2313 = sitofp i32 %2312 to float		; visa id: 2237
  %2314 = fmul float %2309, %2313		; visa id: 2238
  br label %2315, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2239

2315:                                             ; preds = %2307, %2300
; BB270 :
  %.sroa.320.10 = phi float [ %2314, %2307 ], [ %2306, %2300 ]
  %2316 = lshr i32 %2170, 24		; visa id: 2240
  br i1 %1797, label %2323, label %2317, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2241

2317:                                             ; preds = %2315
; BB271 :
  %2318 = sub nsw i32 0, %2316, !spirv.Decorations !8798
  %2319 = icmp slt i32 %132, 0		; visa id: 2243
  %2320 = select i1 %2319, i32 %2318, i32 %2316		; visa id: 2244
  %2321 = sitofp i32 %2320 to float		; visa id: 2245
  %2322 = fmul float %1790, %2321		; visa id: 2246
  br label %2330, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2247

2323:                                             ; preds = %2315
; BB272 :
  %2324 = uitofp i32 %2316 to float		; visa id: 2249
  %2325 = fmul float %1790, %2324		; visa id: 2250
  %2326 = icmp sgt i32 %132, -1		; visa id: 2251
  %2327 = select i1 %2326, i32 1, i32 -1		; visa id: 2252
  %2328 = sitofp i32 %2327 to float		; visa id: 2253
  %2329 = fmul float %2325, %2328		; visa id: 2254
  br label %2330, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2255

2330:                                             ; preds = %2323, %2317
; BB273 :
  %.sroa.368.10 = phi float [ %2329, %2323 ], [ %2322, %2317 ]
  %2331 = zext i16 %2181 to i32		; visa id: 2256
  %2332 = shl nuw i32 %2331, 16		; visa id: 2257
  %2333 = bitcast i32 %2332 to float
  %2334 = fmul float %.sroa.061.10, %2333		; visa id: 2258
  %2335 = fadd float %.sroa.14.0, %2334		; visa id: 2259
  %2336 = zext i16 %2182 to i32		; visa id: 2260
  %2337 = shl nuw i32 %2336, 16		; visa id: 2261
  %2338 = bitcast i32 %2337 to float
  %2339 = fmul float %.sroa.80.10, %2338		; visa id: 2262
  %2340 = fadd float %2335, %2339		; visa id: 2263
  %2341 = zext i16 %2183 to i32		; visa id: 2264
  %2342 = shl nuw i32 %2341, 16		; visa id: 2265
  %2343 = bitcast i32 %2342 to float
  %2344 = fmul float %.sroa.128.10, %2343		; visa id: 2266
  %2345 = fadd float %2340, %2344		; visa id: 2267
  %2346 = zext i16 %2184 to i32		; visa id: 2268
  %2347 = shl nuw i32 %2346, 16		; visa id: 2269
  %2348 = bitcast i32 %2347 to float
  %2349 = fmul float %.sroa.176.10, %2348		; visa id: 2270
  %2350 = fadd float %2345, %2349		; visa id: 2271
  %2351 = zext i16 %2187 to i32		; visa id: 2272
  %2352 = shl nuw i32 %2351, 16		; visa id: 2273
  %2353 = bitcast i32 %2352 to float
  %2354 = fmul float %.sroa.224.10, %2353		; visa id: 2274
  %2355 = fadd float %2350, %2354		; visa id: 2275
  %2356 = zext i16 %2188 to i32		; visa id: 2276
  %2357 = shl nuw i32 %2356, 16		; visa id: 2277
  %2358 = bitcast i32 %2357 to float
  %2359 = fmul float %.sroa.272.10, %2358		; visa id: 2278
  %2360 = fadd float %2355, %2359		; visa id: 2279
  %2361 = zext i16 %2189 to i32		; visa id: 2280
  %2362 = shl nuw i32 %2361, 16		; visa id: 2281
  %2363 = bitcast i32 %2362 to float
  %2364 = fmul float %.sroa.320.10, %2363		; visa id: 2282
  %2365 = fadd float %2360, %2364		; visa id: 2283
  %2366 = zext i16 %2190 to i32		; visa id: 2284
  %2367 = shl nuw i32 %2366, 16		; visa id: 2285
  %2368 = bitcast i32 %2367 to float
  %2369 = fmul float %.sroa.368.10, %2368		; visa id: 2286
  %2370 = fadd float %2365, %2369		; visa id: 2287
  %2371 = and i32 %2171, 255		; visa id: 2288
  br i1 %1989, label %2379, label %2372, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2289

2372:                                             ; preds = %2330
; BB274 :
  %2373 = and i32 %153, 16777216
  %2374 = sub nsw i32 0, %2371, !spirv.Decorations !8798
  %2375 = icmp eq i32 %2373, 0		; visa id: 2291
  %2376 = select i1 %2375, i32 %2371, i32 %2374		; visa id: 2293
  %2377 = sitofp i32 %2376 to float		; visa id: 2294
  %2378 = fmul float %1985, %2377		; visa id: 2295
  br label %2387, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2296

2379:                                             ; preds = %2330
; BB275 :
  %2380 = uitofp i32 %2371 to float		; visa id: 2298
  %2381 = fmul float %1985, %2380		; visa id: 2299
  %2382 = and i32 %153, 16777216
  %2383 = icmp eq i32 %2382, 0		; visa id: 2300
  %2384 = select i1 %2383, i32 1, i32 -1		; visa id: 2302
  %2385 = sitofp i32 %2384 to float		; visa id: 2303
  %2386 = fmul float %2381, %2385		; visa id: 2304
  br label %2387, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2305

2387:                                             ; preds = %2379, %2372
; BB276 :
  %.sroa.061.11 = phi float [ %2386, %2379 ], [ %2378, %2372 ]
  %2388 = bitcast i32 %2171 to <4 x i8>
  %2389 = extractelement <4 x i8> %2388, i32 1
  %2390 = zext i8 %2389 to i32		; visa id: 2306
  br i1 %1989, label %2398, label %2391, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2307

2391:                                             ; preds = %2387
; BB277 :
  %2392 = and i32 %153, 33554432
  %2393 = sub nsw i32 0, %2390, !spirv.Decorations !8798
  %2394 = icmp eq i32 %2392, 0		; visa id: 2309
  %2395 = select i1 %2394, i32 %2390, i32 %2393		; visa id: 2311
  %2396 = sitofp i32 %2395 to float		; visa id: 2312
  %2397 = fmul float %1985, %2396		; visa id: 2313
  br label %2406, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2314

2398:                                             ; preds = %2387
; BB278 :
  %2399 = uitofp i32 %2390 to float		; visa id: 2316
  %2400 = fmul float %1985, %2399		; visa id: 2317
  %2401 = and i32 %153, 33554432
  %2402 = icmp eq i32 %2401, 0		; visa id: 2318
  %2403 = select i1 %2402, i32 1, i32 -1		; visa id: 2320
  %2404 = sitofp i32 %2403 to float		; visa id: 2321
  %2405 = fmul float %2400, %2404		; visa id: 2322
  br label %2406, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2323

2406:                                             ; preds = %2398, %2391
; BB279 :
  %.sroa.80.11 = phi float [ %2405, %2398 ], [ %2397, %2391 ]
  %2407 = extractelement <4 x i8> %2388, i32 2
  %2408 = zext i8 %2407 to i32		; visa id: 2324
  br i1 %1989, label %2416, label %2409, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2325

2409:                                             ; preds = %2406
; BB280 :
  %2410 = and i32 %153, 67108864
  %2411 = sub nsw i32 0, %2408, !spirv.Decorations !8798
  %2412 = icmp eq i32 %2410, 0		; visa id: 2327
  %2413 = select i1 %2412, i32 %2408, i32 %2411		; visa id: 2329
  %2414 = sitofp i32 %2413 to float		; visa id: 2330
  %2415 = fmul float %1985, %2414		; visa id: 2331
  br label %2424, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2332

2416:                                             ; preds = %2406
; BB281 :
  %2417 = uitofp i32 %2408 to float		; visa id: 2334
  %2418 = fmul float %1985, %2417		; visa id: 2335
  %2419 = and i32 %153, 67108864
  %2420 = icmp eq i32 %2419, 0		; visa id: 2336
  %2421 = select i1 %2420, i32 1, i32 -1		; visa id: 2338
  %2422 = sitofp i32 %2421 to float		; visa id: 2339
  %2423 = fmul float %2418, %2422		; visa id: 2340
  br label %2424, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2341

2424:                                             ; preds = %2416, %2409
; BB282 :
  %.sroa.128.11 = phi float [ %2423, %2416 ], [ %2415, %2409 ]
  %2425 = lshr i32 %2171, 24		; visa id: 2342
  br i1 %1989, label %2433, label %2426, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2343

2426:                                             ; preds = %2424
; BB283 :
  %2427 = and i32 %153, 134217728
  %2428 = sub nsw i32 0, %2425, !spirv.Decorations !8798
  %2429 = icmp eq i32 %2427, 0		; visa id: 2345
  %2430 = select i1 %2429, i32 %2425, i32 %2428		; visa id: 2347
  %2431 = sitofp i32 %2430 to float		; visa id: 2348
  %2432 = fmul float %1985, %2431		; visa id: 2349
  br label %2441, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2350

2433:                                             ; preds = %2424
; BB284 :
  %2434 = uitofp i32 %2425 to float		; visa id: 2352
  %2435 = fmul float %1985, %2434		; visa id: 2353
  %2436 = and i32 %153, 134217728
  %2437 = icmp eq i32 %2436, 0		; visa id: 2354
  %2438 = select i1 %2437, i32 1, i32 -1		; visa id: 2356
  %2439 = sitofp i32 %2438 to float		; visa id: 2357
  %2440 = fmul float %2435, %2439		; visa id: 2358
  br label %2441, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2359

2441:                                             ; preds = %2433, %2426
; BB285 :
  %.sroa.176.11 = phi float [ %2440, %2433 ], [ %2432, %2426 ]
  %2442 = and i32 %2172, 255		; visa id: 2360
  br i1 %1989, label %2450, label %2443, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2361

2443:                                             ; preds = %2441
; BB286 :
  %2444 = and i32 %153, 268435456
  %2445 = sub nsw i32 0, %2442, !spirv.Decorations !8798
  %2446 = icmp eq i32 %2444, 0		; visa id: 2363
  %2447 = select i1 %2446, i32 %2442, i32 %2445		; visa id: 2365
  %2448 = sitofp i32 %2447 to float		; visa id: 2366
  %2449 = fmul float %1985, %2448		; visa id: 2367
  br label %2458, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2368

2450:                                             ; preds = %2441
; BB287 :
  %2451 = uitofp i32 %2442 to float		; visa id: 2370
  %2452 = fmul float %1985, %2451		; visa id: 2371
  %2453 = and i32 %153, 268435456
  %2454 = icmp eq i32 %2453, 0		; visa id: 2372
  %2455 = select i1 %2454, i32 1, i32 -1		; visa id: 2374
  %2456 = sitofp i32 %2455 to float		; visa id: 2375
  %2457 = fmul float %2452, %2456		; visa id: 2376
  br label %2458, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2377

2458:                                             ; preds = %2450, %2443
; BB288 :
  %.sroa.224.11 = phi float [ %2457, %2450 ], [ %2449, %2443 ]
  %2459 = bitcast i32 %2172 to <4 x i8>
  %2460 = extractelement <4 x i8> %2459, i32 1
  %2461 = zext i8 %2460 to i32		; visa id: 2378
  br i1 %1989, label %2469, label %2462, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2379

2462:                                             ; preds = %2458
; BB289 :
  %2463 = and i32 %153, 536870912
  %2464 = sub nsw i32 0, %2461, !spirv.Decorations !8798
  %2465 = icmp eq i32 %2463, 0		; visa id: 2381
  %2466 = select i1 %2465, i32 %2461, i32 %2464		; visa id: 2383
  %2467 = sitofp i32 %2466 to float		; visa id: 2384
  %2468 = fmul float %1985, %2467		; visa id: 2385
  br label %2477, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2386

2469:                                             ; preds = %2458
; BB290 :
  %2470 = uitofp i32 %2461 to float		; visa id: 2388
  %2471 = fmul float %1985, %2470		; visa id: 2389
  %2472 = and i32 %153, 536870912
  %2473 = icmp eq i32 %2472, 0		; visa id: 2390
  %2474 = select i1 %2473, i32 1, i32 -1		; visa id: 2392
  %2475 = sitofp i32 %2474 to float		; visa id: 2393
  %2476 = fmul float %2471, %2475		; visa id: 2394
  br label %2477, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2395

2477:                                             ; preds = %2469, %2462
; BB291 :
  %.sroa.272.11 = phi float [ %2476, %2469 ], [ %2468, %2462 ]
  %2478 = extractelement <4 x i8> %2459, i32 2
  %2479 = zext i8 %2478 to i32		; visa id: 2396
  br i1 %1989, label %2487, label %2480, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2397

2480:                                             ; preds = %2477
; BB292 :
  %2481 = and i32 %153, 1073741824
  %2482 = sub nsw i32 0, %2479, !spirv.Decorations !8798
  %2483 = icmp eq i32 %2481, 0		; visa id: 2399
  %2484 = select i1 %2483, i32 %2479, i32 %2482		; visa id: 2401
  %2485 = sitofp i32 %2484 to float		; visa id: 2402
  %2486 = fmul float %1985, %2485		; visa id: 2403
  br label %2495, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2404

2487:                                             ; preds = %2477
; BB293 :
  %2488 = uitofp i32 %2479 to float		; visa id: 2406
  %2489 = fmul float %1985, %2488		; visa id: 2407
  %2490 = and i32 %153, 1073741824
  %2491 = icmp eq i32 %2490, 0		; visa id: 2408
  %2492 = select i1 %2491, i32 1, i32 -1		; visa id: 2410
  %2493 = sitofp i32 %2492 to float		; visa id: 2411
  %2494 = fmul float %2489, %2493		; visa id: 2412
  br label %2495, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2413

2495:                                             ; preds = %2487, %2480
; BB294 :
  %.sroa.320.11 = phi float [ %2494, %2487 ], [ %2486, %2480 ]
  %2496 = lshr i32 %2172, 24		; visa id: 2414
  br i1 %1989, label %2503, label %2497, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2415

2497:                                             ; preds = %2495
; BB295 :
  %2498 = sub nsw i32 0, %2496, !spirv.Decorations !8798
  %2499 = icmp slt i32 %153, 0		; visa id: 2417
  %2500 = select i1 %2499, i32 %2498, i32 %2496		; visa id: 2418
  %2501 = sitofp i32 %2500 to float		; visa id: 2419
  %2502 = fmul float %1985, %2501		; visa id: 2420
  br label %._crit_edge43.6, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2421

2503:                                             ; preds = %2495
; BB296 :
  %2504 = uitofp i32 %2496 to float		; visa id: 2423
  %2505 = fmul float %1985, %2504		; visa id: 2424
  %2506 = icmp sgt i32 %153, -1		; visa id: 2425
  %2507 = select i1 %2506, i32 1, i32 -1		; visa id: 2426
  %2508 = sitofp i32 %2507 to float		; visa id: 2427
  %2509 = fmul float %2505, %2508		; visa id: 2428
  br label %._crit_edge43.6, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2429

._crit_edge43.6:                                  ; preds = %2503, %2497
; BB297 :
  %.sroa.368.11 = phi float [ %2509, %2503 ], [ %2502, %2497 ]
  %2510 = fmul float %.sroa.061.11, %2333		; visa id: 2430
  %2511 = fadd float %.sroa.31.0, %2510		; visa id: 2431
  %2512 = fmul float %.sroa.80.11, %2338		; visa id: 2432
  %2513 = fadd float %2511, %2512		; visa id: 2433
  %2514 = fmul float %.sroa.128.11, %2343		; visa id: 2434
  %2515 = fadd float %2513, %2514		; visa id: 2435
  %2516 = fmul float %.sroa.176.11, %2348		; visa id: 2436
  %2517 = fadd float %2515, %2516		; visa id: 2437
  %2518 = fmul float %.sroa.224.11, %2353		; visa id: 2438
  %2519 = fadd float %2517, %2518		; visa id: 2439
  %2520 = fmul float %.sroa.272.11, %2358		; visa id: 2440
  %2521 = fadd float %2519, %2520		; visa id: 2441
  %2522 = fmul float %.sroa.320.11, %2363		; visa id: 2442
  %2523 = fadd float %2521, %2522		; visa id: 2443
  %2524 = fmul float %.sroa.368.11, %2368		; visa id: 2444
  %2525 = fadd float %2523, %2524		; visa id: 2445
  %2526 = and i32 %133, 255
  %2527 = lshr i32 %168, 4		; visa id: 2446
  %2528 = and i32 %2527, 768		; visa id: 2447
  %2529 = or i32 %2526, %2528		; visa id: 2448
  %2530 = shl nuw nsw i32 %2529, 3, !spirv.Decorations !8791		; visa id: 2449
  %2531 = zext i32 %2530 to i64		; visa id: 2450
  %2532 = add i64 %121, %2531		; visa id: 2451
  %2533 = inttoptr i64 %2532 to ptr addrspace(1)		; visa id: 2452
  %2534 = load <2 x i32>, ptr addrspace(1) %2533, align 4		; visa id: 2452
  %2535 = and i32 %154, 255
  %2536 = lshr i32 %182, 4		; visa id: 2453
  %2537 = and i32 %2536, 768		; visa id: 2454
  %2538 = or i32 %2535, %2537		; visa id: 2455
  %2539 = shl nuw nsw i32 %2538, 3, !spirv.Decorations !8791		; visa id: 2456
  %2540 = zext i32 %2539 to i64		; visa id: 2457
  %2541 = add i64 %121, %2540		; visa id: 2458
  %2542 = inttoptr i64 %2541 to ptr addrspace(1)		; visa id: 2459
  %2543 = load <2 x i32>, ptr addrspace(1) %2542, align 4		; visa id: 2459
  %2544 = extractelement <2 x i32> %2534, i32 0		; visa id: 2460
  %2545 = extractelement <2 x i32> %2534, i32 1		; visa id: 2460
  %2546 = extractelement <2 x i32> %2543, i32 0		; visa id: 2460
  %2547 = extractelement <2 x i32> %2543, i32 1		; visa id: 2460
  %2548 = or i32 %191, 96		; visa id: 2460
  %2549 = zext i32 %2548 to i64		; visa id: 2461
  %2550 = add i64 %2549, %const_reg_qword2		; visa id: 2462
  %IntToPtr2656 = inttoptr i64 %2550 to ptr addrspace(1)		; visa id: 2463
  %vCastload657 = load i32, ptr addrspace(1) %IntToPtr2656, align 2		; visa id: 2463
  %2551 = add i64 %2550, 4
  %IntToPtr2658 = inttoptr i64 %2551 to ptr addrspace(1)
  %vCastload659 = load i32, ptr addrspace(1) %IntToPtr2658, align 2		; visa id: 2464
  %2552 = add i64 %2550, 8
  %IntToPtr2660 = inttoptr i64 %2552 to ptr addrspace(1)
  %vCastload661 = load i32, ptr addrspace(1) %IntToPtr2660, align 2		; visa id: 2465
  %2553 = add i64 %2550, 12
  %IntToPtr2662 = inttoptr i64 %2553 to ptr addrspace(1)
  %vCastload663 = load i32, ptr addrspace(1) %IntToPtr2662, align 2		; visa id: 2466
  %2554 = bitcast i32 %vCastload657 to <2 x i16>		; visa id: 2467
  %2555 = bitcast i32 %vCastload659 to <2 x i16>		; visa id: 2469
  %2556 = extractelement <2 x i16> %2554, i32 0		; visa id: 2471
  %2557 = extractelement <2 x i16> %2554, i32 1		; visa id: 2471
  %2558 = extractelement <2 x i16> %2555, i32 0		; visa id: 2471
  %2559 = extractelement <2 x i16> %2555, i32 1		; visa id: 2471
  %2560 = bitcast i32 %vCastload661 to <2 x i16>		; visa id: 2471
  %2561 = bitcast i32 %vCastload663 to <2 x i16>		; visa id: 2473
  %2562 = extractelement <2 x i16> %2560, i32 0		; visa id: 2475
  %2563 = extractelement <2 x i16> %2560, i32 1		; visa id: 2475
  %2564 = extractelement <2 x i16> %2561, i32 0		; visa id: 2475
  %2565 = extractelement <2 x i16> %2561, i32 1		; visa id: 2475
  %2566 = lshr i32 %1785, 4		; visa id: 2475
  %2567 = uitofp i32 %2566 to float		; visa id: 2476
  %2568 = fadd float %2567, 5.000000e-01		; visa id: 2477
  %2569 = fmul float %147, %2568		; visa id: 2478
  %2570 = fmul float %2569, 2.500000e-01		; visa id: 2479
  %2571 = bitcast float %2570 to i32
  %2572 = and i32 %2571, 2147483647		; visa id: 2480
  %2573 = icmp ugt i32 %2572, 2139095040
  %2574 = fcmp oeq float %220, 0x7FF0000000000000		; visa id: 2481
  %2575 = fcmp une float %220, %220
  %2576 = or i1 %2575, %2574		; visa id: 2482
  %2577 = or i1 %2576, %2573		; visa id: 2484
  %2578 = and i32 %2544, 255		; visa id: 2486
  br i1 %2577, label %2586, label %2579, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2487

2579:                                             ; preds = %._crit_edge43.6
; BB298 :
  %2580 = and i32 %133, 256
  %2581 = sub nsw i32 0, %2578, !spirv.Decorations !8798
  %2582 = icmp eq i32 %2580, 0		; visa id: 2489
  %2583 = select i1 %2582, i32 %2578, i32 %2581		; visa id: 2491
  %2584 = sitofp i32 %2583 to float		; visa id: 2492
  %2585 = fmul float %2570, %2584		; visa id: 2493
  br label %2594, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2494

2586:                                             ; preds = %._crit_edge43.6
; BB299 :
  %2587 = uitofp i32 %2578 to float		; visa id: 2496
  %2588 = fmul float %2570, %2587		; visa id: 2497
  %2589 = and i32 %133, 256
  %2590 = icmp eq i32 %2589, 0		; visa id: 2498
  %2591 = select i1 %2590, i32 1, i32 -1		; visa id: 2500
  %2592 = sitofp i32 %2591 to float		; visa id: 2501
  %2593 = fmul float %2588, %2592		; visa id: 2502
  br label %2594, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2503

2594:                                             ; preds = %2586, %2579
; BB300 :
  %.sroa.061.12 = phi float [ %2593, %2586 ], [ %2585, %2579 ]
  %2595 = bitcast i32 %2544 to <4 x i8>
  %2596 = extractelement <4 x i8> %2595, i32 1
  %2597 = zext i8 %2596 to i32		; visa id: 2504
  br i1 %2577, label %2605, label %2598, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2505

2598:                                             ; preds = %2594
; BB301 :
  %2599 = and i32 %133, 512
  %2600 = sub nsw i32 0, %2597, !spirv.Decorations !8798
  %2601 = icmp eq i32 %2599, 0		; visa id: 2507
  %2602 = select i1 %2601, i32 %2597, i32 %2600		; visa id: 2509
  %2603 = sitofp i32 %2602 to float		; visa id: 2510
  %2604 = fmul float %2570, %2603		; visa id: 2511
  br label %2613, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2512

2605:                                             ; preds = %2594
; BB302 :
  %2606 = uitofp i32 %2597 to float		; visa id: 2514
  %2607 = fmul float %2570, %2606		; visa id: 2515
  %2608 = and i32 %133, 512
  %2609 = icmp eq i32 %2608, 0		; visa id: 2516
  %2610 = select i1 %2609, i32 1, i32 -1		; visa id: 2518
  %2611 = sitofp i32 %2610 to float		; visa id: 2519
  %2612 = fmul float %2607, %2611		; visa id: 2520
  br label %2613, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2521

2613:                                             ; preds = %2605, %2598
; BB303 :
  %.sroa.80.12 = phi float [ %2612, %2605 ], [ %2604, %2598 ]
  %2614 = extractelement <4 x i8> %2595, i32 2
  %2615 = zext i8 %2614 to i32		; visa id: 2522
  br i1 %2577, label %2623, label %2616, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2523

2616:                                             ; preds = %2613
; BB304 :
  %2617 = and i32 %133, 1024
  %2618 = sub nsw i32 0, %2615, !spirv.Decorations !8798
  %2619 = icmp eq i32 %2617, 0		; visa id: 2525
  %2620 = select i1 %2619, i32 %2615, i32 %2618		; visa id: 2527
  %2621 = sitofp i32 %2620 to float		; visa id: 2528
  %2622 = fmul float %2570, %2621		; visa id: 2529
  br label %2631, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2530

2623:                                             ; preds = %2613
; BB305 :
  %2624 = uitofp i32 %2615 to float		; visa id: 2532
  %2625 = fmul float %2570, %2624		; visa id: 2533
  %2626 = and i32 %133, 1024
  %2627 = icmp eq i32 %2626, 0		; visa id: 2534
  %2628 = select i1 %2627, i32 1, i32 -1		; visa id: 2536
  %2629 = sitofp i32 %2628 to float		; visa id: 2537
  %2630 = fmul float %2625, %2629		; visa id: 2538
  br label %2631, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2539

2631:                                             ; preds = %2623, %2616
; BB306 :
  %.sroa.128.12 = phi float [ %2630, %2623 ], [ %2622, %2616 ]
  %2632 = lshr i32 %2544, 24		; visa id: 2540
  br i1 %2577, label %2640, label %2633, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2541

2633:                                             ; preds = %2631
; BB307 :
  %2634 = and i32 %133, 2048
  %2635 = sub nsw i32 0, %2632, !spirv.Decorations !8798
  %2636 = icmp eq i32 %2634, 0		; visa id: 2543
  %2637 = select i1 %2636, i32 %2632, i32 %2635		; visa id: 2545
  %2638 = sitofp i32 %2637 to float		; visa id: 2546
  %2639 = fmul float %2570, %2638		; visa id: 2547
  br label %2648, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2548

2640:                                             ; preds = %2631
; BB308 :
  %2641 = uitofp i32 %2632 to float		; visa id: 2550
  %2642 = fmul float %2570, %2641		; visa id: 2551
  %2643 = and i32 %133, 2048
  %2644 = icmp eq i32 %2643, 0		; visa id: 2552
  %2645 = select i1 %2644, i32 1, i32 -1		; visa id: 2554
  %2646 = sitofp i32 %2645 to float		; visa id: 2555
  %2647 = fmul float %2642, %2646		; visa id: 2556
  br label %2648, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2557

2648:                                             ; preds = %2640, %2633
; BB309 :
  %.sroa.176.12 = phi float [ %2647, %2640 ], [ %2639, %2633 ]
  %2649 = and i32 %2545, 255		; visa id: 2558
  br i1 %2577, label %2657, label %2650, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2559

2650:                                             ; preds = %2648
; BB310 :
  %2651 = and i32 %133, 4096
  %2652 = sub nsw i32 0, %2649, !spirv.Decorations !8798
  %2653 = icmp eq i32 %2651, 0		; visa id: 2561
  %2654 = select i1 %2653, i32 %2649, i32 %2652		; visa id: 2563
  %2655 = sitofp i32 %2654 to float		; visa id: 2564
  %2656 = fmul float %2570, %2655		; visa id: 2565
  br label %2665, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2566

2657:                                             ; preds = %2648
; BB311 :
  %2658 = uitofp i32 %2649 to float		; visa id: 2568
  %2659 = fmul float %2570, %2658		; visa id: 2569
  %2660 = and i32 %133, 4096
  %2661 = icmp eq i32 %2660, 0		; visa id: 2570
  %2662 = select i1 %2661, i32 1, i32 -1		; visa id: 2572
  %2663 = sitofp i32 %2662 to float		; visa id: 2573
  %2664 = fmul float %2659, %2663		; visa id: 2574
  br label %2665, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2575

2665:                                             ; preds = %2657, %2650
; BB312 :
  %.sroa.224.12 = phi float [ %2664, %2657 ], [ %2656, %2650 ]
  %2666 = bitcast i32 %2545 to <4 x i8>
  %2667 = extractelement <4 x i8> %2666, i32 1
  %2668 = zext i8 %2667 to i32		; visa id: 2576
  br i1 %2577, label %2676, label %2669, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2577

2669:                                             ; preds = %2665
; BB313 :
  %2670 = and i32 %133, 8192
  %2671 = sub nsw i32 0, %2668, !spirv.Decorations !8798
  %2672 = icmp eq i32 %2670, 0		; visa id: 2579
  %2673 = select i1 %2672, i32 %2668, i32 %2671		; visa id: 2581
  %2674 = sitofp i32 %2673 to float		; visa id: 2582
  %2675 = fmul float %2570, %2674		; visa id: 2583
  br label %2684, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2584

2676:                                             ; preds = %2665
; BB314 :
  %2677 = uitofp i32 %2668 to float		; visa id: 2586
  %2678 = fmul float %2570, %2677		; visa id: 2587
  %2679 = and i32 %133, 8192
  %2680 = icmp eq i32 %2679, 0		; visa id: 2588
  %2681 = select i1 %2680, i32 1, i32 -1		; visa id: 2590
  %2682 = sitofp i32 %2681 to float		; visa id: 2591
  %2683 = fmul float %2678, %2682		; visa id: 2592
  br label %2684, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2593

2684:                                             ; preds = %2676, %2669
; BB315 :
  %.sroa.272.12 = phi float [ %2683, %2676 ], [ %2675, %2669 ]
  %2685 = extractelement <4 x i8> %2666, i32 2
  %2686 = zext i8 %2685 to i32		; visa id: 2594
  br i1 %2577, label %2694, label %2687, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2595

2687:                                             ; preds = %2684
; BB316 :
  %2688 = and i32 %133, 16384
  %2689 = sub nsw i32 0, %2686, !spirv.Decorations !8798
  %2690 = icmp eq i32 %2688, 0		; visa id: 2597
  %2691 = select i1 %2690, i32 %2686, i32 %2689		; visa id: 2599
  %2692 = sitofp i32 %2691 to float		; visa id: 2600
  %2693 = fmul float %2570, %2692		; visa id: 2601
  br label %2702, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2602

2694:                                             ; preds = %2684
; BB317 :
  %2695 = uitofp i32 %2686 to float		; visa id: 2604
  %2696 = fmul float %2570, %2695		; visa id: 2605
  %2697 = and i32 %133, 16384
  %2698 = icmp eq i32 %2697, 0		; visa id: 2606
  %2699 = select i1 %2698, i32 1, i32 -1		; visa id: 2608
  %2700 = sitofp i32 %2699 to float		; visa id: 2609
  %2701 = fmul float %2696, %2700		; visa id: 2610
  br label %2702, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2611

2702:                                             ; preds = %2694, %2687
; BB318 :
  %.sroa.320.12 = phi float [ %2701, %2694 ], [ %2693, %2687 ]
  %2703 = lshr i32 %2545, 24		; visa id: 2612
  br i1 %2577, label %2711, label %2704, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2613

2704:                                             ; preds = %2702
; BB319 :
  %2705 = and i32 %133, 32768
  %2706 = sub nsw i32 0, %2703, !spirv.Decorations !8798
  %2707 = icmp eq i32 %2705, 0		; visa id: 2615
  %2708 = select i1 %2707, i32 %2703, i32 %2706		; visa id: 2617
  %2709 = sitofp i32 %2708 to float		; visa id: 2618
  %2710 = fmul float %2570, %2709		; visa id: 2619
  br label %2719, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2620

2711:                                             ; preds = %2702
; BB320 :
  %2712 = uitofp i32 %2703 to float		; visa id: 2622
  %2713 = fmul float %2570, %2712		; visa id: 2623
  %2714 = and i32 %133, 32768
  %2715 = icmp eq i32 %2714, 0		; visa id: 2624
  %2716 = select i1 %2715, i32 1, i32 -1		; visa id: 2626
  %2717 = sitofp i32 %2716 to float		; visa id: 2627
  %2718 = fmul float %2713, %2717		; visa id: 2628
  br label %2719, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2629

2719:                                             ; preds = %2711, %2704
; BB321 :
  %.sroa.368.12 = phi float [ %2718, %2711 ], [ %2710, %2704 ]
  %2720 = zext i16 %2556 to i32		; visa id: 2630
  %2721 = shl nuw i32 %2720, 16		; visa id: 2631
  %2722 = bitcast i32 %2721 to float
  %2723 = fmul float %.sroa.061.12, %2722		; visa id: 2632
  %2724 = fadd float %.sroa.16.0, %2723		; visa id: 2633
  %2725 = zext i16 %2557 to i32		; visa id: 2634
  %2726 = shl nuw i32 %2725, 16		; visa id: 2635
  %2727 = bitcast i32 %2726 to float
  %2728 = fmul float %.sroa.80.12, %2727		; visa id: 2636
  %2729 = fadd float %2724, %2728		; visa id: 2637
  %2730 = zext i16 %2558 to i32		; visa id: 2638
  %2731 = shl nuw i32 %2730, 16		; visa id: 2639
  %2732 = bitcast i32 %2731 to float
  %2733 = fmul float %.sroa.128.12, %2732		; visa id: 2640
  %2734 = fadd float %2729, %2733		; visa id: 2641
  %2735 = zext i16 %2559 to i32		; visa id: 2642
  %2736 = shl nuw i32 %2735, 16		; visa id: 2643
  %2737 = bitcast i32 %2736 to float
  %2738 = fmul float %.sroa.176.12, %2737		; visa id: 2644
  %2739 = fadd float %2734, %2738		; visa id: 2645
  %2740 = zext i16 %2562 to i32		; visa id: 2646
  %2741 = shl nuw i32 %2740, 16		; visa id: 2647
  %2742 = bitcast i32 %2741 to float
  %2743 = fmul float %.sroa.224.12, %2742		; visa id: 2648
  %2744 = fadd float %2739, %2743		; visa id: 2649
  %2745 = zext i16 %2563 to i32		; visa id: 2650
  %2746 = shl nuw i32 %2745, 16		; visa id: 2651
  %2747 = bitcast i32 %2746 to float
  %2748 = fmul float %.sroa.272.12, %2747		; visa id: 2652
  %2749 = fadd float %2744, %2748		; visa id: 2653
  %2750 = zext i16 %2564 to i32		; visa id: 2654
  %2751 = shl nuw i32 %2750, 16		; visa id: 2655
  %2752 = bitcast i32 %2751 to float
  %2753 = fmul float %.sroa.320.12, %2752		; visa id: 2656
  %2754 = fadd float %2749, %2753		; visa id: 2657
  %2755 = zext i16 %2565 to i32		; visa id: 2658
  %2756 = shl nuw i32 %2755, 16		; visa id: 2659
  %2757 = bitcast i32 %2756 to float
  %2758 = fmul float %.sroa.368.12, %2757		; visa id: 2660
  %2759 = fadd float %2754, %2758		; visa id: 2661
  %2760 = lshr i32 %1980, 4		; visa id: 2662
  %2761 = uitofp i32 %2760 to float		; visa id: 2663
  %2762 = fadd float %2761, 5.000000e-01		; visa id: 2664
  %2763 = fmul float %166, %2762		; visa id: 2665
  %2764 = fmul float %2763, 2.500000e-01		; visa id: 2666
  %2765 = bitcast float %2764 to i32
  %2766 = and i32 %2765, 2147483647		; visa id: 2667
  %2767 = icmp ugt i32 %2766, 2139095040		; visa id: 2668
  %2768 = or i1 %422, %2767		; visa id: 2669
  %2769 = and i32 %2546, 255		; visa id: 2670
  br i1 %2768, label %2777, label %2770, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2671

2770:                                             ; preds = %2719
; BB322 :
  %2771 = and i32 %154, 256
  %2772 = sub nsw i32 0, %2769, !spirv.Decorations !8798
  %2773 = icmp eq i32 %2771, 0		; visa id: 2673
  %2774 = select i1 %2773, i32 %2769, i32 %2772		; visa id: 2675
  %2775 = sitofp i32 %2774 to float		; visa id: 2676
  %2776 = fmul float %2764, %2775		; visa id: 2677
  br label %2785, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2678

2777:                                             ; preds = %2719
; BB323 :
  %2778 = uitofp i32 %2769 to float		; visa id: 2680
  %2779 = fmul float %2764, %2778		; visa id: 2681
  %2780 = and i32 %154, 256
  %2781 = icmp eq i32 %2780, 0		; visa id: 2682
  %2782 = select i1 %2781, i32 1, i32 -1		; visa id: 2684
  %2783 = sitofp i32 %2782 to float		; visa id: 2685
  %2784 = fmul float %2779, %2783		; visa id: 2686
  br label %2785, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2687

2785:                                             ; preds = %2777, %2770
; BB324 :
  %.sroa.061.13 = phi float [ %2784, %2777 ], [ %2776, %2770 ]
  %2786 = bitcast i32 %2546 to <4 x i8>
  %2787 = extractelement <4 x i8> %2786, i32 1
  %2788 = zext i8 %2787 to i32		; visa id: 2688
  br i1 %2768, label %2796, label %2789, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2689

2789:                                             ; preds = %2785
; BB325 :
  %2790 = and i32 %154, 512
  %2791 = sub nsw i32 0, %2788, !spirv.Decorations !8798
  %2792 = icmp eq i32 %2790, 0		; visa id: 2691
  %2793 = select i1 %2792, i32 %2788, i32 %2791		; visa id: 2693
  %2794 = sitofp i32 %2793 to float		; visa id: 2694
  %2795 = fmul float %2764, %2794		; visa id: 2695
  br label %2804, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2696

2796:                                             ; preds = %2785
; BB326 :
  %2797 = uitofp i32 %2788 to float		; visa id: 2698
  %2798 = fmul float %2764, %2797		; visa id: 2699
  %2799 = and i32 %154, 512
  %2800 = icmp eq i32 %2799, 0		; visa id: 2700
  %2801 = select i1 %2800, i32 1, i32 -1		; visa id: 2702
  %2802 = sitofp i32 %2801 to float		; visa id: 2703
  %2803 = fmul float %2798, %2802		; visa id: 2704
  br label %2804, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2705

2804:                                             ; preds = %2796, %2789
; BB327 :
  %.sroa.80.13 = phi float [ %2803, %2796 ], [ %2795, %2789 ]
  %2805 = extractelement <4 x i8> %2786, i32 2
  %2806 = zext i8 %2805 to i32		; visa id: 2706
  br i1 %2768, label %2814, label %2807, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2707

2807:                                             ; preds = %2804
; BB328 :
  %2808 = and i32 %154, 1024
  %2809 = sub nsw i32 0, %2806, !spirv.Decorations !8798
  %2810 = icmp eq i32 %2808, 0		; visa id: 2709
  %2811 = select i1 %2810, i32 %2806, i32 %2809		; visa id: 2711
  %2812 = sitofp i32 %2811 to float		; visa id: 2712
  %2813 = fmul float %2764, %2812		; visa id: 2713
  br label %2822, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2714

2814:                                             ; preds = %2804
; BB329 :
  %2815 = uitofp i32 %2806 to float		; visa id: 2716
  %2816 = fmul float %2764, %2815		; visa id: 2717
  %2817 = and i32 %154, 1024
  %2818 = icmp eq i32 %2817, 0		; visa id: 2718
  %2819 = select i1 %2818, i32 1, i32 -1		; visa id: 2720
  %2820 = sitofp i32 %2819 to float		; visa id: 2721
  %2821 = fmul float %2816, %2820		; visa id: 2722
  br label %2822, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2723

2822:                                             ; preds = %2814, %2807
; BB330 :
  %.sroa.128.13 = phi float [ %2821, %2814 ], [ %2813, %2807 ]
  %2823 = lshr i32 %2546, 24		; visa id: 2724
  br i1 %2768, label %2831, label %2824, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2725

2824:                                             ; preds = %2822
; BB331 :
  %2825 = and i32 %154, 2048
  %2826 = sub nsw i32 0, %2823, !spirv.Decorations !8798
  %2827 = icmp eq i32 %2825, 0		; visa id: 2727
  %2828 = select i1 %2827, i32 %2823, i32 %2826		; visa id: 2729
  %2829 = sitofp i32 %2828 to float		; visa id: 2730
  %2830 = fmul float %2764, %2829		; visa id: 2731
  br label %2839, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2732

2831:                                             ; preds = %2822
; BB332 :
  %2832 = uitofp i32 %2823 to float		; visa id: 2734
  %2833 = fmul float %2764, %2832		; visa id: 2735
  %2834 = and i32 %154, 2048
  %2835 = icmp eq i32 %2834, 0		; visa id: 2736
  %2836 = select i1 %2835, i32 1, i32 -1		; visa id: 2738
  %2837 = sitofp i32 %2836 to float		; visa id: 2739
  %2838 = fmul float %2833, %2837		; visa id: 2740
  br label %2839, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2741

2839:                                             ; preds = %2831, %2824
; BB333 :
  %.sroa.176.13 = phi float [ %2838, %2831 ], [ %2830, %2824 ]
  %2840 = and i32 %2547, 255		; visa id: 2742
  br i1 %2768, label %2848, label %2841, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2743

2841:                                             ; preds = %2839
; BB334 :
  %2842 = and i32 %154, 4096
  %2843 = sub nsw i32 0, %2840, !spirv.Decorations !8798
  %2844 = icmp eq i32 %2842, 0		; visa id: 2745
  %2845 = select i1 %2844, i32 %2840, i32 %2843		; visa id: 2747
  %2846 = sitofp i32 %2845 to float		; visa id: 2748
  %2847 = fmul float %2764, %2846		; visa id: 2749
  br label %2856, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2750

2848:                                             ; preds = %2839
; BB335 :
  %2849 = uitofp i32 %2840 to float		; visa id: 2752
  %2850 = fmul float %2764, %2849		; visa id: 2753
  %2851 = and i32 %154, 4096
  %2852 = icmp eq i32 %2851, 0		; visa id: 2754
  %2853 = select i1 %2852, i32 1, i32 -1		; visa id: 2756
  %2854 = sitofp i32 %2853 to float		; visa id: 2757
  %2855 = fmul float %2850, %2854		; visa id: 2758
  br label %2856, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2759

2856:                                             ; preds = %2848, %2841
; BB336 :
  %.sroa.224.13 = phi float [ %2855, %2848 ], [ %2847, %2841 ]
  %2857 = bitcast i32 %2547 to <4 x i8>
  %2858 = extractelement <4 x i8> %2857, i32 1
  %2859 = zext i8 %2858 to i32		; visa id: 2760
  br i1 %2768, label %2867, label %2860, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2761

2860:                                             ; preds = %2856
; BB337 :
  %2861 = and i32 %154, 8192
  %2862 = sub nsw i32 0, %2859, !spirv.Decorations !8798
  %2863 = icmp eq i32 %2861, 0		; visa id: 2763
  %2864 = select i1 %2863, i32 %2859, i32 %2862		; visa id: 2765
  %2865 = sitofp i32 %2864 to float		; visa id: 2766
  %2866 = fmul float %2764, %2865		; visa id: 2767
  br label %2875, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2768

2867:                                             ; preds = %2856
; BB338 :
  %2868 = uitofp i32 %2859 to float		; visa id: 2770
  %2869 = fmul float %2764, %2868		; visa id: 2771
  %2870 = and i32 %154, 8192
  %2871 = icmp eq i32 %2870, 0		; visa id: 2772
  %2872 = select i1 %2871, i32 1, i32 -1		; visa id: 2774
  %2873 = sitofp i32 %2872 to float		; visa id: 2775
  %2874 = fmul float %2869, %2873		; visa id: 2776
  br label %2875, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2777

2875:                                             ; preds = %2867, %2860
; BB339 :
  %.sroa.272.13 = phi float [ %2874, %2867 ], [ %2866, %2860 ]
  %2876 = extractelement <4 x i8> %2857, i32 2
  %2877 = zext i8 %2876 to i32		; visa id: 2778
  br i1 %2768, label %2885, label %2878, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2779

2878:                                             ; preds = %2875
; BB340 :
  %2879 = and i32 %154, 16384
  %2880 = sub nsw i32 0, %2877, !spirv.Decorations !8798
  %2881 = icmp eq i32 %2879, 0		; visa id: 2781
  %2882 = select i1 %2881, i32 %2877, i32 %2880		; visa id: 2783
  %2883 = sitofp i32 %2882 to float		; visa id: 2784
  %2884 = fmul float %2764, %2883		; visa id: 2785
  br label %2893, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2786

2885:                                             ; preds = %2875
; BB341 :
  %2886 = uitofp i32 %2877 to float		; visa id: 2788
  %2887 = fmul float %2764, %2886		; visa id: 2789
  %2888 = and i32 %154, 16384
  %2889 = icmp eq i32 %2888, 0		; visa id: 2790
  %2890 = select i1 %2889, i32 1, i32 -1		; visa id: 2792
  %2891 = sitofp i32 %2890 to float		; visa id: 2793
  %2892 = fmul float %2887, %2891		; visa id: 2794
  br label %2893, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2795

2893:                                             ; preds = %2885, %2878
; BB342 :
  %.sroa.320.13 = phi float [ %2892, %2885 ], [ %2884, %2878 ]
  %2894 = lshr i32 %2547, 24		; visa id: 2796
  br i1 %2768, label %2902, label %2895, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2797

2895:                                             ; preds = %2893
; BB343 :
  %2896 = and i32 %154, 32768
  %2897 = sub nsw i32 0, %2894, !spirv.Decorations !8798
  %2898 = icmp eq i32 %2896, 0		; visa id: 2799
  %2899 = select i1 %2898, i32 %2894, i32 %2897		; visa id: 2801
  %2900 = sitofp i32 %2899 to float		; visa id: 2802
  %2901 = fmul float %2764, %2900		; visa id: 2803
  br label %._crit_edge43.7, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2804

2902:                                             ; preds = %2893
; BB344 :
  %2903 = uitofp i32 %2894 to float		; visa id: 2806
  %2904 = fmul float %2764, %2903		; visa id: 2807
  %2905 = and i32 %154, 32768
  %2906 = icmp eq i32 %2905, 0		; visa id: 2808
  %2907 = select i1 %2906, i32 1, i32 -1		; visa id: 2810
  %2908 = sitofp i32 %2907 to float		; visa id: 2811
  %2909 = fmul float %2904, %2908		; visa id: 2812
  br label %._crit_edge43.7, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2813

._crit_edge43.7:                                  ; preds = %2902, %2895
; BB345 :
  %.sroa.368.13 = phi float [ %2909, %2902 ], [ %2901, %2895 ]
  %2910 = fmul float %.sroa.061.13, %2722		; visa id: 2814
  %2911 = fadd float %.sroa.33.0, %2910		; visa id: 2815
  %2912 = fmul float %.sroa.80.13, %2727		; visa id: 2816
  %2913 = fadd float %2911, %2912		; visa id: 2817
  %2914 = fmul float %.sroa.128.13, %2732		; visa id: 2818
  %2915 = fadd float %2913, %2914		; visa id: 2819
  %2916 = fmul float %.sroa.176.13, %2737		; visa id: 2820
  %2917 = fadd float %2915, %2916		; visa id: 2821
  %2918 = fmul float %.sroa.224.13, %2742		; visa id: 2822
  %2919 = fadd float %2917, %2918		; visa id: 2823
  %2920 = fmul float %.sroa.272.13, %2747		; visa id: 2824
  %2921 = fadd float %2919, %2920		; visa id: 2825
  %2922 = fmul float %.sroa.320.13, %2752		; visa id: 2826
  %2923 = fadd float %2921, %2922		; visa id: 2827
  %2924 = fmul float %.sroa.368.13, %2757		; visa id: 2828
  %2925 = fadd float %2923, %2924		; visa id: 2829
  %2926 = bitcast i32 %133 to <4 x i8>
  %2927 = extractelement <4 x i8> %2926, i32 2
  %2928 = lshr i32 %168, 6		; visa id: 2830
  %2929 = and i32 %2928, 768
  %2930 = zext i8 %2927 to i32		; visa id: 2831
  %2931 = or i32 %2930, %2929		; visa id: 2832
  %2932 = shl nuw nsw i32 %2931, 3, !spirv.Decorations !8791		; visa id: 2833
  %2933 = zext i32 %2932 to i64		; visa id: 2834
  %2934 = add i64 %121, %2933		; visa id: 2835
  %2935 = inttoptr i64 %2934 to ptr addrspace(1)		; visa id: 2836
  %2936 = load <2 x i32>, ptr addrspace(1) %2935, align 4		; visa id: 2836
  %2937 = bitcast i32 %154 to <4 x i8>
  %2938 = extractelement <4 x i8> %2937, i32 2
  %2939 = lshr i32 %182, 6		; visa id: 2837
  %2940 = and i32 %2939, 768
  %2941 = zext i8 %2938 to i32		; visa id: 2838
  %2942 = or i32 %2941, %2940		; visa id: 2839
  %2943 = shl nuw nsw i32 %2942, 3, !spirv.Decorations !8791		; visa id: 2840
  %2944 = zext i32 %2943 to i64		; visa id: 2841
  %2945 = add i64 %121, %2944		; visa id: 2842
  %2946 = inttoptr i64 %2945 to ptr addrspace(1)		; visa id: 2843
  %2947 = load <2 x i32>, ptr addrspace(1) %2946, align 4		; visa id: 2843
  %2948 = extractelement <2 x i32> %2936, i32 0		; visa id: 2844
  %2949 = extractelement <2 x i32> %2936, i32 1		; visa id: 2844
  %2950 = extractelement <2 x i32> %2947, i32 0		; visa id: 2844
  %2951 = extractelement <2 x i32> %2947, i32 1		; visa id: 2844
  %2952 = or i32 %191, 112		; visa id: 2844
  %2953 = zext i32 %2952 to i64		; visa id: 2845
  %2954 = add i64 %2953, %const_reg_qword2		; visa id: 2846
  %IntToPtr2664 = inttoptr i64 %2954 to ptr addrspace(1)		; visa id: 2847
  %vCastload665 = load i32, ptr addrspace(1) %IntToPtr2664, align 2		; visa id: 2847
  %2955 = add i64 %2954, 4
  %IntToPtr2666 = inttoptr i64 %2955 to ptr addrspace(1)
  %vCastload667 = load i32, ptr addrspace(1) %IntToPtr2666, align 2		; visa id: 2848
  %2956 = add i64 %2954, 8
  %IntToPtr2668 = inttoptr i64 %2956 to ptr addrspace(1)
  %vCastload669 = load i32, ptr addrspace(1) %IntToPtr2668, align 2		; visa id: 2849
  %2957 = add i64 %2954, 12
  %IntToPtr2670 = inttoptr i64 %2957 to ptr addrspace(1)
  %vCastload671 = load i32, ptr addrspace(1) %IntToPtr2670, align 2		; visa id: 2850
  %2958 = bitcast i32 %vCastload665 to <2 x i16>		; visa id: 2851
  %2959 = bitcast i32 %vCastload667 to <2 x i16>		; visa id: 2853
  %2960 = extractelement <2 x i16> %2958, i32 0		; visa id: 2855
  %2961 = extractelement <2 x i16> %2958, i32 1		; visa id: 2855
  %2962 = extractelement <2 x i16> %2959, i32 0		; visa id: 2855
  %2963 = extractelement <2 x i16> %2959, i32 1		; visa id: 2855
  %2964 = bitcast i32 %vCastload669 to <2 x i16>		; visa id: 2855
  %2965 = bitcast i32 %vCastload671 to <2 x i16>		; visa id: 2857
  %2966 = extractelement <2 x i16> %2964, i32 0		; visa id: 2859
  %2967 = extractelement <2 x i16> %2964, i32 1		; visa id: 2859
  %2968 = extractelement <2 x i16> %2965, i32 0		; visa id: 2859
  %2969 = extractelement <2 x i16> %2965, i32 1		; visa id: 2859
  %2970 = and i32 %2948, 255		; visa id: 2859
  br i1 %2577, label %2978, label %2971, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2860

2971:                                             ; preds = %._crit_edge43.7
; BB346 :
  %2972 = and i32 %133, 16777216
  %2973 = sub nsw i32 0, %2970, !spirv.Decorations !8798
  %2974 = icmp eq i32 %2972, 0		; visa id: 2862
  %2975 = select i1 %2974, i32 %2970, i32 %2973		; visa id: 2864
  %2976 = sitofp i32 %2975 to float		; visa id: 2865
  %2977 = fmul float %2570, %2976		; visa id: 2866
  br label %2986, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2867

2978:                                             ; preds = %._crit_edge43.7
; BB347 :
  %2979 = uitofp i32 %2970 to float		; visa id: 2869
  %2980 = fmul float %2570, %2979		; visa id: 2870
  %2981 = and i32 %133, 16777216
  %2982 = icmp eq i32 %2981, 0		; visa id: 2871
  %2983 = select i1 %2982, i32 1, i32 -1		; visa id: 2873
  %2984 = sitofp i32 %2983 to float		; visa id: 2874
  %2985 = fmul float %2980, %2984		; visa id: 2875
  br label %2986, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2876

2986:                                             ; preds = %2978, %2971
; BB348 :
  %.sroa.061.14 = phi float [ %2985, %2978 ], [ %2977, %2971 ]
  %2987 = bitcast i32 %2948 to <4 x i8>
  %2988 = extractelement <4 x i8> %2987, i32 1
  %2989 = zext i8 %2988 to i32		; visa id: 2877
  br i1 %2577, label %2997, label %2990, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2878

2990:                                             ; preds = %2986
; BB349 :
  %2991 = and i32 %133, 33554432
  %2992 = sub nsw i32 0, %2989, !spirv.Decorations !8798
  %2993 = icmp eq i32 %2991, 0		; visa id: 2880
  %2994 = select i1 %2993, i32 %2989, i32 %2992		; visa id: 2882
  %2995 = sitofp i32 %2994 to float		; visa id: 2883
  %2996 = fmul float %2570, %2995		; visa id: 2884
  br label %3005, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2885

2997:                                             ; preds = %2986
; BB350 :
  %2998 = uitofp i32 %2989 to float		; visa id: 2887
  %2999 = fmul float %2570, %2998		; visa id: 2888
  %3000 = and i32 %133, 33554432
  %3001 = icmp eq i32 %3000, 0		; visa id: 2889
  %3002 = select i1 %3001, i32 1, i32 -1		; visa id: 2891
  %3003 = sitofp i32 %3002 to float		; visa id: 2892
  %3004 = fmul float %2999, %3003		; visa id: 2893
  br label %3005, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2894

3005:                                             ; preds = %2997, %2990
; BB351 :
  %.sroa.80.14 = phi float [ %3004, %2997 ], [ %2996, %2990 ]
  %3006 = extractelement <4 x i8> %2987, i32 2
  %3007 = zext i8 %3006 to i32		; visa id: 2895
  br i1 %2577, label %3015, label %3008, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2896

3008:                                             ; preds = %3005
; BB352 :
  %3009 = and i32 %133, 67108864
  %3010 = sub nsw i32 0, %3007, !spirv.Decorations !8798
  %3011 = icmp eq i32 %3009, 0		; visa id: 2898
  %3012 = select i1 %3011, i32 %3007, i32 %3010		; visa id: 2900
  %3013 = sitofp i32 %3012 to float		; visa id: 2901
  %3014 = fmul float %2570, %3013		; visa id: 2902
  br label %3023, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2903

3015:                                             ; preds = %3005
; BB353 :
  %3016 = uitofp i32 %3007 to float		; visa id: 2905
  %3017 = fmul float %2570, %3016		; visa id: 2906
  %3018 = and i32 %133, 67108864
  %3019 = icmp eq i32 %3018, 0		; visa id: 2907
  %3020 = select i1 %3019, i32 1, i32 -1		; visa id: 2909
  %3021 = sitofp i32 %3020 to float		; visa id: 2910
  %3022 = fmul float %3017, %3021		; visa id: 2911
  br label %3023, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2912

3023:                                             ; preds = %3015, %3008
; BB354 :
  %.sroa.128.14 = phi float [ %3022, %3015 ], [ %3014, %3008 ]
  %3024 = lshr i32 %2948, 24		; visa id: 2913
  br i1 %2577, label %3032, label %3025, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2914

3025:                                             ; preds = %3023
; BB355 :
  %3026 = and i32 %133, 134217728
  %3027 = sub nsw i32 0, %3024, !spirv.Decorations !8798
  %3028 = icmp eq i32 %3026, 0		; visa id: 2916
  %3029 = select i1 %3028, i32 %3024, i32 %3027		; visa id: 2918
  %3030 = sitofp i32 %3029 to float		; visa id: 2919
  %3031 = fmul float %2570, %3030		; visa id: 2920
  br label %3040, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2921

3032:                                             ; preds = %3023
; BB356 :
  %3033 = uitofp i32 %3024 to float		; visa id: 2923
  %3034 = fmul float %2570, %3033		; visa id: 2924
  %3035 = and i32 %133, 134217728
  %3036 = icmp eq i32 %3035, 0		; visa id: 2925
  %3037 = select i1 %3036, i32 1, i32 -1		; visa id: 2927
  %3038 = sitofp i32 %3037 to float		; visa id: 2928
  %3039 = fmul float %3034, %3038		; visa id: 2929
  br label %3040, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2930

3040:                                             ; preds = %3032, %3025
; BB357 :
  %.sroa.176.14 = phi float [ %3039, %3032 ], [ %3031, %3025 ]
  %3041 = and i32 %2949, 255		; visa id: 2931
  br i1 %2577, label %3049, label %3042, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2932

3042:                                             ; preds = %3040
; BB358 :
  %3043 = and i32 %133, 268435456
  %3044 = sub nsw i32 0, %3041, !spirv.Decorations !8798
  %3045 = icmp eq i32 %3043, 0		; visa id: 2934
  %3046 = select i1 %3045, i32 %3041, i32 %3044		; visa id: 2936
  %3047 = sitofp i32 %3046 to float		; visa id: 2937
  %3048 = fmul float %2570, %3047		; visa id: 2938
  br label %3057, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2939

3049:                                             ; preds = %3040
; BB359 :
  %3050 = uitofp i32 %3041 to float		; visa id: 2941
  %3051 = fmul float %2570, %3050		; visa id: 2942
  %3052 = and i32 %133, 268435456
  %3053 = icmp eq i32 %3052, 0		; visa id: 2943
  %3054 = select i1 %3053, i32 1, i32 -1		; visa id: 2945
  %3055 = sitofp i32 %3054 to float		; visa id: 2946
  %3056 = fmul float %3051, %3055		; visa id: 2947
  br label %3057, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2948

3057:                                             ; preds = %3049, %3042
; BB360 :
  %.sroa.224.14 = phi float [ %3056, %3049 ], [ %3048, %3042 ]
  %3058 = bitcast i32 %2949 to <4 x i8>
  %3059 = extractelement <4 x i8> %3058, i32 1
  %3060 = zext i8 %3059 to i32		; visa id: 2949
  br i1 %2577, label %3068, label %3061, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2950

3061:                                             ; preds = %3057
; BB361 :
  %3062 = and i32 %133, 536870912
  %3063 = sub nsw i32 0, %3060, !spirv.Decorations !8798
  %3064 = icmp eq i32 %3062, 0		; visa id: 2952
  %3065 = select i1 %3064, i32 %3060, i32 %3063		; visa id: 2954
  %3066 = sitofp i32 %3065 to float		; visa id: 2955
  %3067 = fmul float %2570, %3066		; visa id: 2956
  br label %3076, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2957

3068:                                             ; preds = %3057
; BB362 :
  %3069 = uitofp i32 %3060 to float		; visa id: 2959
  %3070 = fmul float %2570, %3069		; visa id: 2960
  %3071 = and i32 %133, 536870912
  %3072 = icmp eq i32 %3071, 0		; visa id: 2961
  %3073 = select i1 %3072, i32 1, i32 -1		; visa id: 2963
  %3074 = sitofp i32 %3073 to float		; visa id: 2964
  %3075 = fmul float %3070, %3074		; visa id: 2965
  br label %3076, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2966

3076:                                             ; preds = %3068, %3061
; BB363 :
  %.sroa.272.14 = phi float [ %3075, %3068 ], [ %3067, %3061 ]
  %3077 = extractelement <4 x i8> %3058, i32 2
  %3078 = zext i8 %3077 to i32		; visa id: 2967
  br i1 %2577, label %3086, label %3079, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2968

3079:                                             ; preds = %3076
; BB364 :
  %3080 = and i32 %133, 1073741824
  %3081 = sub nsw i32 0, %3078, !spirv.Decorations !8798
  %3082 = icmp eq i32 %3080, 0		; visa id: 2970
  %3083 = select i1 %3082, i32 %3078, i32 %3081		; visa id: 2972
  %3084 = sitofp i32 %3083 to float		; visa id: 2973
  %3085 = fmul float %2570, %3084		; visa id: 2974
  br label %3094, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2975

3086:                                             ; preds = %3076
; BB365 :
  %3087 = uitofp i32 %3078 to float		; visa id: 2977
  %3088 = fmul float %2570, %3087		; visa id: 2978
  %3089 = and i32 %133, 1073741824
  %3090 = icmp eq i32 %3089, 0		; visa id: 2979
  %3091 = select i1 %3090, i32 1, i32 -1		; visa id: 2981
  %3092 = sitofp i32 %3091 to float		; visa id: 2982
  %3093 = fmul float %3088, %3092		; visa id: 2983
  br label %3094, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2984

3094:                                             ; preds = %3086, %3079
; BB366 :
  %.sroa.320.14 = phi float [ %3093, %3086 ], [ %3085, %3079 ]
  %3095 = lshr i32 %2949, 24		; visa id: 2985
  br i1 %2577, label %3102, label %3096, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2986

3096:                                             ; preds = %3094
; BB367 :
  %3097 = sub nsw i32 0, %3095, !spirv.Decorations !8798
  %3098 = icmp slt i32 %133, 0		; visa id: 2988
  %3099 = select i1 %3098, i32 %3097, i32 %3095		; visa id: 2989
  %3100 = sitofp i32 %3099 to float		; visa id: 2990
  %3101 = fmul float %2570, %3100		; visa id: 2991
  br label %3109, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2992

3102:                                             ; preds = %3094
; BB368 :
  %3103 = uitofp i32 %3095 to float		; visa id: 2994
  %3104 = fmul float %2570, %3103		; visa id: 2995
  %3105 = icmp sgt i32 %133, -1		; visa id: 2996
  %3106 = select i1 %3105, i32 1, i32 -1		; visa id: 2997
  %3107 = sitofp i32 %3106 to float		; visa id: 2998
  %3108 = fmul float %3104, %3107		; visa id: 2999
  br label %3109, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3000

3109:                                             ; preds = %3102, %3096
; BB369 :
  %.sroa.368.14 = phi float [ %3108, %3102 ], [ %3101, %3096 ]
  %3110 = zext i16 %2960 to i32		; visa id: 3001
  %3111 = shl nuw i32 %3110, 16		; visa id: 3002
  %3112 = bitcast i32 %3111 to float
  %3113 = fmul float %.sroa.061.14, %3112		; visa id: 3003
  %3114 = fadd float %.sroa.18.0, %3113		; visa id: 3004
  %3115 = zext i16 %2961 to i32		; visa id: 3005
  %3116 = shl nuw i32 %3115, 16		; visa id: 3006
  %3117 = bitcast i32 %3116 to float
  %3118 = fmul float %.sroa.80.14, %3117		; visa id: 3007
  %3119 = fadd float %3114, %3118		; visa id: 3008
  %3120 = zext i16 %2962 to i32		; visa id: 3009
  %3121 = shl nuw i32 %3120, 16		; visa id: 3010
  %3122 = bitcast i32 %3121 to float
  %3123 = fmul float %.sroa.128.14, %3122		; visa id: 3011
  %3124 = fadd float %3119, %3123		; visa id: 3012
  %3125 = zext i16 %2963 to i32		; visa id: 3013
  %3126 = shl nuw i32 %3125, 16		; visa id: 3014
  %3127 = bitcast i32 %3126 to float
  %3128 = fmul float %.sroa.176.14, %3127		; visa id: 3015
  %3129 = fadd float %3124, %3128		; visa id: 3016
  %3130 = zext i16 %2966 to i32		; visa id: 3017
  %3131 = shl nuw i32 %3130, 16		; visa id: 3018
  %3132 = bitcast i32 %3131 to float
  %3133 = fmul float %.sroa.224.14, %3132		; visa id: 3019
  %3134 = fadd float %3129, %3133		; visa id: 3020
  %3135 = zext i16 %2967 to i32		; visa id: 3021
  %3136 = shl nuw i32 %3135, 16		; visa id: 3022
  %3137 = bitcast i32 %3136 to float
  %3138 = fmul float %.sroa.272.14, %3137		; visa id: 3023
  %3139 = fadd float %3134, %3138		; visa id: 3024
  %3140 = zext i16 %2968 to i32		; visa id: 3025
  %3141 = shl nuw i32 %3140, 16		; visa id: 3026
  %3142 = bitcast i32 %3141 to float
  %3143 = fmul float %.sroa.320.14, %3142		; visa id: 3027
  %3144 = fadd float %3139, %3143		; visa id: 3028
  %3145 = zext i16 %2969 to i32		; visa id: 3029
  %3146 = shl nuw i32 %3145, 16		; visa id: 3030
  %3147 = bitcast i32 %3146 to float
  %3148 = fmul float %.sroa.368.14, %3147		; visa id: 3031
  %3149 = fadd float %3144, %3148		; visa id: 3032
  %3150 = and i32 %2950, 255		; visa id: 3033
  br i1 %2768, label %3158, label %3151, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3034

3151:                                             ; preds = %3109
; BB370 :
  %3152 = and i32 %154, 16777216
  %3153 = sub nsw i32 0, %3150, !spirv.Decorations !8798
  %3154 = icmp eq i32 %3152, 0		; visa id: 3036
  %3155 = select i1 %3154, i32 %3150, i32 %3153		; visa id: 3038
  %3156 = sitofp i32 %3155 to float		; visa id: 3039
  %3157 = fmul float %2764, %3156		; visa id: 3040
  br label %3166, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3041

3158:                                             ; preds = %3109
; BB371 :
  %3159 = uitofp i32 %3150 to float		; visa id: 3043
  %3160 = fmul float %2764, %3159		; visa id: 3044
  %3161 = and i32 %154, 16777216
  %3162 = icmp eq i32 %3161, 0		; visa id: 3045
  %3163 = select i1 %3162, i32 1, i32 -1		; visa id: 3047
  %3164 = sitofp i32 %3163 to float		; visa id: 3048
  %3165 = fmul float %3160, %3164		; visa id: 3049
  br label %3166, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3050

3166:                                             ; preds = %3158, %3151
; BB372 :
  %.sroa.061.15 = phi float [ %3165, %3158 ], [ %3157, %3151 ]
  %3167 = bitcast i32 %2950 to <4 x i8>
  %3168 = extractelement <4 x i8> %3167, i32 1
  %3169 = zext i8 %3168 to i32		; visa id: 3051
  br i1 %2768, label %3177, label %3170, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3052

3170:                                             ; preds = %3166
; BB373 :
  %3171 = and i32 %154, 33554432
  %3172 = sub nsw i32 0, %3169, !spirv.Decorations !8798
  %3173 = icmp eq i32 %3171, 0		; visa id: 3054
  %3174 = select i1 %3173, i32 %3169, i32 %3172		; visa id: 3056
  %3175 = sitofp i32 %3174 to float		; visa id: 3057
  %3176 = fmul float %2764, %3175		; visa id: 3058
  br label %3185, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3059

3177:                                             ; preds = %3166
; BB374 :
  %3178 = uitofp i32 %3169 to float		; visa id: 3061
  %3179 = fmul float %2764, %3178		; visa id: 3062
  %3180 = and i32 %154, 33554432
  %3181 = icmp eq i32 %3180, 0		; visa id: 3063
  %3182 = select i1 %3181, i32 1, i32 -1		; visa id: 3065
  %3183 = sitofp i32 %3182 to float		; visa id: 3066
  %3184 = fmul float %3179, %3183		; visa id: 3067
  br label %3185, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3068

3185:                                             ; preds = %3177, %3170
; BB375 :
  %.sroa.80.15 = phi float [ %3184, %3177 ], [ %3176, %3170 ]
  %3186 = extractelement <4 x i8> %3167, i32 2
  %3187 = zext i8 %3186 to i32		; visa id: 3069
  br i1 %2768, label %3195, label %3188, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3070

3188:                                             ; preds = %3185
; BB376 :
  %3189 = and i32 %154, 67108864
  %3190 = sub nsw i32 0, %3187, !spirv.Decorations !8798
  %3191 = icmp eq i32 %3189, 0		; visa id: 3072
  %3192 = select i1 %3191, i32 %3187, i32 %3190		; visa id: 3074
  %3193 = sitofp i32 %3192 to float		; visa id: 3075
  %3194 = fmul float %2764, %3193		; visa id: 3076
  br label %3203, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3077

3195:                                             ; preds = %3185
; BB377 :
  %3196 = uitofp i32 %3187 to float		; visa id: 3079
  %3197 = fmul float %2764, %3196		; visa id: 3080
  %3198 = and i32 %154, 67108864
  %3199 = icmp eq i32 %3198, 0		; visa id: 3081
  %3200 = select i1 %3199, i32 1, i32 -1		; visa id: 3083
  %3201 = sitofp i32 %3200 to float		; visa id: 3084
  %3202 = fmul float %3197, %3201		; visa id: 3085
  br label %3203, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3086

3203:                                             ; preds = %3195, %3188
; BB378 :
  %.sroa.128.15 = phi float [ %3202, %3195 ], [ %3194, %3188 ]
  %3204 = lshr i32 %2950, 24		; visa id: 3087
  br i1 %2768, label %3212, label %3205, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3088

3205:                                             ; preds = %3203
; BB379 :
  %3206 = and i32 %154, 134217728
  %3207 = sub nsw i32 0, %3204, !spirv.Decorations !8798
  %3208 = icmp eq i32 %3206, 0		; visa id: 3090
  %3209 = select i1 %3208, i32 %3204, i32 %3207		; visa id: 3092
  %3210 = sitofp i32 %3209 to float		; visa id: 3093
  %3211 = fmul float %2764, %3210		; visa id: 3094
  br label %3220, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3095

3212:                                             ; preds = %3203
; BB380 :
  %3213 = uitofp i32 %3204 to float		; visa id: 3097
  %3214 = fmul float %2764, %3213		; visa id: 3098
  %3215 = and i32 %154, 134217728
  %3216 = icmp eq i32 %3215, 0		; visa id: 3099
  %3217 = select i1 %3216, i32 1, i32 -1		; visa id: 3101
  %3218 = sitofp i32 %3217 to float		; visa id: 3102
  %3219 = fmul float %3214, %3218		; visa id: 3103
  br label %3220, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3104

3220:                                             ; preds = %3212, %3205
; BB381 :
  %.sroa.176.15 = phi float [ %3219, %3212 ], [ %3211, %3205 ]
  %3221 = and i32 %2951, 255		; visa id: 3105
  br i1 %2768, label %3229, label %3222, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3106

3222:                                             ; preds = %3220
; BB382 :
  %3223 = and i32 %154, 268435456
  %3224 = sub nsw i32 0, %3221, !spirv.Decorations !8798
  %3225 = icmp eq i32 %3223, 0		; visa id: 3108
  %3226 = select i1 %3225, i32 %3221, i32 %3224		; visa id: 3110
  %3227 = sitofp i32 %3226 to float		; visa id: 3111
  %3228 = fmul float %2764, %3227		; visa id: 3112
  br label %3237, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3113

3229:                                             ; preds = %3220
; BB383 :
  %3230 = uitofp i32 %3221 to float		; visa id: 3115
  %3231 = fmul float %2764, %3230		; visa id: 3116
  %3232 = and i32 %154, 268435456
  %3233 = icmp eq i32 %3232, 0		; visa id: 3117
  %3234 = select i1 %3233, i32 1, i32 -1		; visa id: 3119
  %3235 = sitofp i32 %3234 to float		; visa id: 3120
  %3236 = fmul float %3231, %3235		; visa id: 3121
  br label %3237, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3122

3237:                                             ; preds = %3229, %3222
; BB384 :
  %.sroa.224.15 = phi float [ %3236, %3229 ], [ %3228, %3222 ]
  %3238 = bitcast i32 %2951 to <4 x i8>
  %3239 = extractelement <4 x i8> %3238, i32 1
  %3240 = zext i8 %3239 to i32		; visa id: 3123
  br i1 %2768, label %3248, label %3241, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3124

3241:                                             ; preds = %3237
; BB385 :
  %3242 = and i32 %154, 536870912
  %3243 = sub nsw i32 0, %3240, !spirv.Decorations !8798
  %3244 = icmp eq i32 %3242, 0		; visa id: 3126
  %3245 = select i1 %3244, i32 %3240, i32 %3243		; visa id: 3128
  %3246 = sitofp i32 %3245 to float		; visa id: 3129
  %3247 = fmul float %2764, %3246		; visa id: 3130
  br label %3256, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3131

3248:                                             ; preds = %3237
; BB386 :
  %3249 = uitofp i32 %3240 to float		; visa id: 3133
  %3250 = fmul float %2764, %3249		; visa id: 3134
  %3251 = and i32 %154, 536870912
  %3252 = icmp eq i32 %3251, 0		; visa id: 3135
  %3253 = select i1 %3252, i32 1, i32 -1		; visa id: 3137
  %3254 = sitofp i32 %3253 to float		; visa id: 3138
  %3255 = fmul float %3250, %3254		; visa id: 3139
  br label %3256, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3140

3256:                                             ; preds = %3248, %3241
; BB387 :
  %.sroa.272.15 = phi float [ %3255, %3248 ], [ %3247, %3241 ]
  %3257 = extractelement <4 x i8> %3238, i32 2
  %3258 = zext i8 %3257 to i32		; visa id: 3141
  br i1 %2768, label %3266, label %3259, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3142

3259:                                             ; preds = %3256
; BB388 :
  %3260 = and i32 %154, 1073741824
  %3261 = sub nsw i32 0, %3258, !spirv.Decorations !8798
  %3262 = icmp eq i32 %3260, 0		; visa id: 3144
  %3263 = select i1 %3262, i32 %3258, i32 %3261		; visa id: 3146
  %3264 = sitofp i32 %3263 to float		; visa id: 3147
  %3265 = fmul float %2764, %3264		; visa id: 3148
  br label %3274, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3149

3266:                                             ; preds = %3256
; BB389 :
  %3267 = uitofp i32 %3258 to float		; visa id: 3151
  %3268 = fmul float %2764, %3267		; visa id: 3152
  %3269 = and i32 %154, 1073741824
  %3270 = icmp eq i32 %3269, 0		; visa id: 3153
  %3271 = select i1 %3270, i32 1, i32 -1		; visa id: 3155
  %3272 = sitofp i32 %3271 to float		; visa id: 3156
  %3273 = fmul float %3268, %3272		; visa id: 3157
  br label %3274, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3158

3274:                                             ; preds = %3266, %3259
; BB390 :
  %.sroa.320.15 = phi float [ %3273, %3266 ], [ %3265, %3259 ]
  %3275 = lshr i32 %2951, 24		; visa id: 3159
  br i1 %2768, label %3282, label %3276, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3160

3276:                                             ; preds = %3274
; BB391 :
  %3277 = sub nsw i32 0, %3275, !spirv.Decorations !8798
  %3278 = icmp slt i32 %154, 0		; visa id: 3162
  %3279 = select i1 %3278, i32 %3277, i32 %3275		; visa id: 3163
  %3280 = sitofp i32 %3279 to float		; visa id: 3164
  %3281 = fmul float %2764, %3280		; visa id: 3165
  br label %3289, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3166

3282:                                             ; preds = %3274
; BB392 :
  %3283 = uitofp i32 %3275 to float		; visa id: 3168
  %3284 = fmul float %2764, %3283		; visa id: 3169
  %3285 = icmp sgt i32 %154, -1		; visa id: 3170
  %3286 = select i1 %3285, i32 1, i32 -1		; visa id: 3171
  %3287 = sitofp i32 %3286 to float		; visa id: 3172
  %3288 = fmul float %3284, %3287		; visa id: 3173
  br label %3289, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 3174

3289:                                             ; preds = %3282, %3276
; BB393 :
  %.sroa.368.15 = phi float [ %3288, %3282 ], [ %3281, %3276 ]
  %3290 = fmul float %.sroa.061.15, %3112		; visa id: 3175
  %3291 = fadd float %.sroa.35.0, %3290		; visa id: 3176
  %3292 = fmul float %.sroa.80.15, %3117		; visa id: 3177
  %3293 = fadd float %3291, %3292		; visa id: 3178
  %3294 = fmul float %.sroa.128.15, %3122		; visa id: 3179
  %3295 = fadd float %3293, %3294		; visa id: 3180
  %3296 = fmul float %.sroa.176.15, %3127		; visa id: 3181
  %3297 = fadd float %3295, %3296		; visa id: 3182
  %3298 = fmul float %.sroa.224.15, %3132		; visa id: 3183
  %3299 = fadd float %3297, %3298		; visa id: 3184
  %3300 = fmul float %.sroa.272.15, %3137		; visa id: 3185
  %3301 = fadd float %3299, %3300		; visa id: 3186
  %3302 = fmul float %.sroa.320.15, %3142		; visa id: 3187
  %3303 = fadd float %3301, %3302		; visa id: 3188
  %3304 = fmul float %.sroa.368.15, %3147		; visa id: 3189
  %3305 = fadd float %3303, %3304		; visa id: 3190
  %3306 = icmp ult i32 %122, 9		; visa id: 3191
  br i1 %3306, label %.._crit_edge43_crit_edge, label %.preheader, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 3192

.._crit_edge43_crit_edge:                         ; preds = %3289
; BB394 :
  %3307 = add nuw nsw i32 %122, 1, !spirv.Decorations !8791		; visa id: 3194
  br label %._crit_edge43, !stats.blockFrequency.digits !8799, !stats.blockFrequency.scale !8797		; visa id: 3195

.preheader:                                       ; preds = %3289
; BB395 :
  %.lcssa686 = phi float [ %3305, %3289 ]
  %.lcssa685 = phi float [ %3149, %3289 ]
  %.lcssa684 = phi float [ %2925, %3289 ]
  %.lcssa683 = phi float [ %2759, %3289 ]
  %.lcssa682 = phi float [ %2525, %3289 ]
  %.lcssa681 = phi float [ %2370, %3289 ]
  %.lcssa680 = phi float [ %2146, %3289 ]
  %.lcssa679 = phi float [ %1979, %3289 ]
  %.lcssa678 = phi float [ %1744, %3289 ]
  %.lcssa677 = phi float [ %1589, %3289 ]
  %.lcssa676 = phi float [ %1365, %3289 ]
  %.lcssa675 = phi float [ %1199, %3289 ]
  %.lcssa674 = phi float [ %965, %3289 ]
  %.lcssa673 = phi float [ %810, %3289 ]
  %.lcssa672 = phi float [ %586, %3289 ]
  %.lcssa = phi float [ %409, %3289 ]
  %3308 = fadd float %.lcssa, %.lcssa673		; visa id: 3197
  %3309 = fadd float %.lcssa675, %.lcssa677		; visa id: 3198
  %3310 = fadd float %.lcssa679, %.lcssa681		; visa id: 3199
  %3311 = fadd float %.lcssa683, %.lcssa685		; visa id: 3200
  %3312 = fadd float %3308, %3309		; visa id: 3201
  %3313 = fadd float %3310, %3311		; visa id: 3202
  %3314 = fadd float %3312, %3313		; visa id: 3203
  %3315 = fadd float %.lcssa672, %.lcssa674		; visa id: 3204
  %3316 = fadd float %.lcssa676, %.lcssa678		; visa id: 3205
  %3317 = fadd float %.lcssa680, %.lcssa682		; visa id: 3206
  %3318 = fadd float %.lcssa684, %.lcssa686		; visa id: 3207
  %3319 = fadd float %3315, %3316		; visa id: 3208
  %3320 = fadd float %3317, %3318		; visa id: 3209
  %3321 = fadd float %3319, %3320		; visa id: 3210
  br label %._crit_edge41, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8790		; visa id: 3213

._crit_edge:                                      ; preds = %precompiled_u32divrem_sp.exit
; BB396 :
  %.pre511 = zext i32 %retval.0.i to i64		; visa id: 3215
  br label %._crit_edge41, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 3220

._crit_edge41:                                    ; preds = %.._crit_edge41_crit_edge, %._crit_edge, %._crit_edge42, %.preheader
; BB397 :
  %.pre-phi = phi i64 [ %33, %._crit_edge42 ], [ %33, %.preheader ], [ %.pre511, %._crit_edge ], [ %33, %.._crit_edge41_crit_edge ]
  %.sroa.7.0 = phi float [ 0.000000e+00, %._crit_edge42 ], [ %3321, %.preheader ], [ 0.000000e+00, %._crit_edge ], [ 0.000000e+00, %.._crit_edge41_crit_edge ]
  %.sroa.060.0 = phi float [ 0.000000e+00, %._crit_edge42 ], [ %3314, %.preheader ], [ 0.000000e+00, %._crit_edge ], [ 0.000000e+00, %.._crit_edge41_crit_edge ]
  %3322 = phi i32 [ 0, %._crit_edge42 ], [ -1, %.preheader ], [ 0, %._crit_edge ], [ 0, %.._crit_edge41_crit_edge ]
  %3323 = phi i32 [ %62, %._crit_edge42 ], [ 0, %.preheader ], [ -1, %._crit_edge ], [ -1, %.._crit_edge41_crit_edge ]
  %3324 = icmp ne i32 %3322, 0		; visa id: 3221
  %3325 = icmp ne i32 %6, 0		; visa id: 3222
  %3326 = or i1 %30, %3325		; visa id: 3223
  %3327 = zext i32 %13 to i64		; visa id: 3225
  %3328 = icmp eq i32 %13, %29		; visa id: 3226
  %3329 = icmp ne i32 %3323, 0		; visa id: 3227
  %3330 = sext i1 %3329 to i32		; visa id: 3228
  %3331 = sub i32 0, %3330		; visa id: 3229
  %3332 = addrspacecast ptr addrspace(4) %4 to ptr addrspace(1)		; visa id: 3230
  %3333 = addrspacecast ptr addrspace(4) %5 to ptr addrspace(1)		; visa id: 3231
  %3334 = add nuw nsw i32 %simdLaneId, 1		; visa id: 3232
  %3335 = and i32 %3334, 31		; visa id: 3233
  %simdShuffle = call float @llvm.genx.GenISA.WaveShuffleIndex.f32(float %.sroa.060.0, i32 %3335, i32 0)		; visa id: 3234
  %3336 = and i32 %simdLaneId, 1
  %3337 = icmp eq i32 %3336, 0		; visa id: 3241
  %3338 = select i1 %3337, float %simdShuffle, float -0.000000e+00		; visa id: 3243
  %3339 = fadd float %.sroa.060.0, %3338		; visa id: 3244
  %3340 = add nuw nsw i32 %simdLaneId, 2		; visa id: 3245
  %3341 = and i32 %3340, 31		; visa id: 3246
  %simdShuffle.1 = call float @llvm.genx.GenISA.WaveShuffleIndex.f32(float %3339, i32 %3341, i32 0)		; visa id: 3247
  %3342 = icmp eq i32 %6, 0		; visa id: 3254
  br i1 %3326, label %._crit_edge41.._crit_edge45_crit_edge, label %3343, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8782		; visa id: 3255

._crit_edge41.._crit_edge45_crit_edge:            ; preds = %._crit_edge41
; BB:
  br label %._crit_edge45, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787

3343:                                             ; preds = %._crit_edge41
; BB399 :
  %3344 = select i1 %3342, float %simdShuffle.1, float -0.000000e+00		; visa id: 3257
  %3345 = fadd float %3339, %3344		; visa id: 3258
  %3346 = bitcast float %3345 to i32
  %3347 = select i1 %3324, i32 %3346, i32 2143289344		; visa id: 3259
  %3348 = and i32 %3347, 2147483647		; visa id: 3260
  %3349 = icmp ugt i32 %3348, 2139095040		; visa id: 3261
  br i1 %3349, label %3357, label %3350, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 3262

3350:                                             ; preds = %3343
; BB400 :
  %3351 = lshr i32 %3347, 16		; visa id: 3264
  %3352 = and i32 %3351, 1		; visa id: 3265
  %3353 = add i32 %3347, %3352
  %3354 = add i32 %3353, 32767		; visa id: 3266
  %3355 = lshr i32 %3354, 16		; visa id: 3267
  %3356 = trunc i32 %3355 to i16		; visa id: 3268
  br label %3361, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 3269

3357:                                             ; preds = %3343
; BB401 :
  %3358 = lshr i32 %3347, 16		; visa id: 3271
  %3359 = trunc i32 %3358 to i16		; visa id: 3272
  %3360 = or i16 %3359, 64		; visa id: 3273
  br label %3361, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 3274

3361:                                             ; preds = %3350, %3357
; BB402 :
  %3362 = phi i16 [ %3360, %3357 ], [ %3356, %3350 ]
  %3363 = shl nuw nsw i64 %3327, 1		; visa id: 3275
  %3364 = add i64 %3363, %const_reg_qword12		; visa id: 3276
  %3365 = inttoptr i64 %3364 to ptr addrspace(4)		; visa id: 3277
  %3366 = addrspacecast ptr addrspace(4) %3365 to ptr addrspace(1)		; visa id: 3277
  store i16 %3362, ptr addrspace(1) %3366, align 2		; visa id: 3278
  br i1 %3328, label %3367, label %.._crit_edge45_crit_edge, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 3280

.._crit_edge45_crit_edge:                         ; preds = %3361
; BB:
  br label %._crit_edge45, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784

3367:                                             ; preds = %3361
; BB404 :
  %3368 = shl nuw nsw i64 %.pre-phi, 2		; visa id: 3282
  %3369 = add i64 %3368, %const_reg_qword17		; visa id: 3283
  %3370 = inttoptr i64 %3369 to ptr addrspace(4)		; visa id: 3284
  %3371 = addrspacecast ptr addrspace(4) %3370 to ptr addrspace(1)		; visa id: 3284
  store i32 %3331, ptr addrspace(1) %3371, align 4		; visa id: 3285
  br i1 %3329, label %3372, label %.._crit_edge45_crit_edge606, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 3286

.._crit_edge45_crit_edge606:                      ; preds = %3367
; BB:
  br label %._crit_edge45, !stats.blockFrequency.digits !8800, !stats.blockFrequency.scale !8801

3372:                                             ; preds = %3367
; BB406 :
  %3373 = load i32, ptr addrspace(1) %3333, align 4		; visa id: 3288
  %3374 = icmp eq i32 %3373, 0		; visa id: 3289
  br i1 %3374, label %.._crit_edge45_crit_edge607, label %3375, !stats.blockFrequency.digits !8802, !stats.blockFrequency.scale !8803		; visa id: 3290

.._crit_edge45_crit_edge607:                      ; preds = %3372
; BB:
  br label %._crit_edge45, !stats.blockFrequency.digits !8804, !stats.blockFrequency.scale !8801

3375:                                             ; preds = %3372
; BB408 :
  %3376 = call i32 @llvm.genx.GenISA.icmpxchgatomicrawA64.i32.p1.p1(ptr addrspace(1) %3332, ptr addrspace(1) %3332, i32 0, i32 1)		; visa id: 3292
  br label %._crit_edge45, !stats.blockFrequency.digits !8805, !stats.blockFrequency.scale !8801		; visa id: 3297

._crit_edge45:                                    ; preds = %.._crit_edge45_crit_edge607, %.._crit_edge45_crit_edge606, %.._crit_edge45_crit_edge, %._crit_edge41.._crit_edge45_crit_edge, %3375
; BB409 :
  %simdShuffle.151 = call float @llvm.genx.GenISA.WaveShuffleIndex.f32(float %.sroa.7.0, i32 %3335, i32 0)		; visa id: 3298
  %3377 = select i1 %3337, float %simdShuffle.151, float -0.000000e+00		; visa id: 3305
  %3378 = fadd float %.sroa.7.0, %3377		; visa id: 3306
  %simdShuffle.1.1 = call float @llvm.genx.GenISA.WaveShuffleIndex.f32(float %3378, i32 %3341, i32 0)		; visa id: 3307
  br i1 %3326, label %._crit_edge45.._crit_edge46.1_crit_edge, label %3379, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8782		; visa id: 3314

._crit_edge45.._crit_edge46.1_crit_edge:          ; preds = %._crit_edge45
; BB:
  br label %._crit_edge46.1, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787

3379:                                             ; preds = %._crit_edge45
; BB411 :
  %3380 = select i1 %3342, float %simdShuffle.1.1, float -0.000000e+00		; visa id: 3316
  %3381 = fadd float %3378, %3380		; visa id: 3317
  %3382 = bitcast float %3381 to i32
  %3383 = select i1 %3324, i32 %3382, i32 2143289344		; visa id: 3318
  %3384 = and i32 %3383, 2147483647		; visa id: 3319
  %3385 = icmp ugt i32 %3384, 2139095040		; visa id: 3320
  br i1 %3385, label %3393, label %3386, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 3321

3386:                                             ; preds = %3379
; BB412 :
  %3387 = lshr i32 %3383, 16		; visa id: 3323
  %3388 = and i32 %3387, 1		; visa id: 3324
  %3389 = add i32 %3383, %3388
  %3390 = add i32 %3389, 32767		; visa id: 3325
  %3391 = lshr i32 %3390, 16		; visa id: 3326
  %3392 = trunc i32 %3391 to i16		; visa id: 3327
  br label %3397, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 3328

3393:                                             ; preds = %3379
; BB413 :
  %3394 = lshr i32 %3383, 16		; visa id: 3330
  %3395 = trunc i32 %3394 to i16		; visa id: 3331
  %3396 = or i16 %3395, 64		; visa id: 3332
  br label %3397, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 3333

3397:                                             ; preds = %3393, %3386
; BB414 :
  %3398 = phi i16 [ %3396, %3393 ], [ %3392, %3386 ]
  %3399 = shl nuw nsw i64 %3327, 1		; visa id: 3334
  %3400 = add i64 %3399, %const_reg_qword13		; visa id: 3335
  %3401 = inttoptr i64 %3400 to ptr addrspace(4)		; visa id: 3336
  %3402 = addrspacecast ptr addrspace(4) %3401 to ptr addrspace(1)		; visa id: 3336
  store i16 %3398, ptr addrspace(1) %3402, align 2		; visa id: 3337
  br i1 %3328, label %3403, label %.._crit_edge46.1_crit_edge, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 3339

.._crit_edge46.1_crit_edge:                       ; preds = %3397
; BB:
  br label %._crit_edge46.1, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784

3403:                                             ; preds = %3397
; BB416 :
  %3404 = shl nuw nsw i64 %.pre-phi, 2		; visa id: 3341
  %3405 = add i64 %3404, %const_reg_qword18		; visa id: 3342
  %3406 = inttoptr i64 %3405 to ptr addrspace(4)		; visa id: 3343
  %3407 = addrspacecast ptr addrspace(4) %3406 to ptr addrspace(1)		; visa id: 3343
  store i32 %3331, ptr addrspace(1) %3407, align 4		; visa id: 3344
  br i1 %3329, label %3408, label %.._crit_edge46.1_crit_edge608, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 3345

.._crit_edge46.1_crit_edge608:                    ; preds = %3403
; BB:
  br label %._crit_edge46.1, !stats.blockFrequency.digits !8800, !stats.blockFrequency.scale !8801

3408:                                             ; preds = %3403
; BB418 :
  %3409 = load i32, ptr addrspace(1) %3333, align 4		; visa id: 3347
  %3410 = icmp eq i32 %3409, 0		; visa id: 3348
  br i1 %3410, label %.._crit_edge46.1_crit_edge609, label %3411, !stats.blockFrequency.digits !8802, !stats.blockFrequency.scale !8803		; visa id: 3349

.._crit_edge46.1_crit_edge609:                    ; preds = %3408
; BB:
  br label %._crit_edge46.1, !stats.blockFrequency.digits !8804, !stats.blockFrequency.scale !8801

3411:                                             ; preds = %3408
; BB420 :
  %3412 = call i32 @llvm.genx.GenISA.icmpxchgatomicrawA64.i32.p1.p1(ptr addrspace(1) %3332, ptr addrspace(1) %3332, i32 0, i32 1)		; visa id: 3351
  br label %._crit_edge46.1, !stats.blockFrequency.digits !8805, !stats.blockFrequency.scale !8801		; visa id: 3356

._crit_edge46.1:                                  ; preds = %.._crit_edge46.1_crit_edge609, %.._crit_edge46.1_crit_edge608, %.._crit_edge46.1_crit_edge, %._crit_edge45.._crit_edge46.1_crit_edge, %3411
; BB421 :
  ret void, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8782		; visa id: 3357
}
