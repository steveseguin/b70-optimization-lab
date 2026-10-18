; ------------------------------------------------
; OCL_asm6c8399b4fe53f40f_simd32_entry_0002.visa.ll
; ------------------------------------------------
; Function Attrs: convergent nounwind
define spir_kernel void @_ZTSZZNK6p90exp6KernelILN3iq34TypeE22ELj2560ELj64ELb0ELb1ELj0EE6submitERN4sycl3_V15queueESt4spanIKPvLm18446744073709551615EERKSt6vectorINS5_5eventESaISD_EEENKUlRNS5_7handlerEE_clESJ_EUlNS5_7nd_itemILi1EEEE_(ptr byval(%"struct.p39::__generated_Bound") align 8 %0, i32 %1, <8 x i32> %r0, <3 x i32> %globalOffset, i16 %localIdX, i16 %localIdY, i16 %localIdZ, ptr addrspace(2) %constBase, ptr addrspace(1) %globalBase, ptr %privateBase, i64 %const_reg_qword, i64 %const_reg_qword1, i64 %const_reg_qword2, i64 %const_reg_qword3, i64 %const_reg_qword4, i64 %const_reg_qword5, i64 %const_reg_qword6, i64 %const_reg_qword7, i64 %const_reg_qword8, i64 %const_reg_qword9, i64 %const_reg_qword10, i64 %const_reg_qword11, i64 %const_reg_qword12, i64 %const_reg_qword13, i64 %const_reg_qword14, i64 %const_reg_qword15, i64 %const_reg_qword16, i64 %const_reg_qword17, i64 %const_reg_qword18, i64 %const_reg_qword19, i64 %const_reg_qword20, i32 %const_reg_dword, i32 %const_reg_dword21, i32 %const_reg_dword22, i32 %const_reg_dword23, i32 %const_reg_dword24, i32 %bindlessOffset, i32 %bindlessOffset25) #0 {
; BB0 :
  %3 = extractelement <8 x i32> %r0, i32 1		; visa id: 2
  %simdLaneId16 = call i16 @llvm.genx.GenISA.simdLaneId()		; visa id: 2
  %4 = lshr i16 %localIdX, 5		; visa id: 5
  %simdLaneId = zext i16 %simdLaneId16 to i32		; visa id: 6
  %5 = and i32 %simdLaneId, 3		; visa id: 7
  %6 = zext i16 %4 to i32		; visa id: 8
  %7 = and i32 %6, 1		; visa id: 9
  %8 = lshr i32 %6, 1		; visa id: 10
  %9 = add nuw i32 %8, %3, !spirv.Decorations !8781		; visa id: 11
  %10 = shl i32 %9, 3		; visa id: 12
  %11 = lshr i32 %simdLaneId, 2		; visa id: 13
  %12 = or i32 %10, %11		; visa id: 14
  %tobool.i = icmp eq i32 %const_reg_dword21, 0		; visa id: 15
  br i1 %tobool.i, label %.precompiled_u32divrem_sp.exit_crit_edge, label %if.end.i, !stats.blockFrequency.digits !8783, !stats.blockFrequency.scale !8784		; visa id: 16

.precompiled_u32divrem_sp.exit_crit_edge:         ; preds = %2
; BB1 :
  br label %precompiled_u32divrem_sp.exit, !stats.blockFrequency.digits !8785, !stats.blockFrequency.scale !8786		; visa id: 19

if.end.i:                                         ; preds = %2
; BB2 :
  %13 = call float @llvm.genx.GenISA.uitof.rtz.f32.i32(i32 %const_reg_dword21)		; visa id: 21
  %conv.i = fptoui float %13 to i32		; visa id: 23
  %sub.i = sub i32 %const_reg_dword21, %conv.i		; visa id: 24
  %14 = call float @llvm.genx.GenISA.uitof.rtz.f32.i32(i32 %12)		; visa id: 25
  %div.i = fdiv float 1.000000e+00, %13, !fpmath !8787		; visa id: 26
  %15 = call float @llvm.genx.GenISA.fma.rtz.f32.f32.f32.f32(float %div.i, float 0xBE98000000000000, float %div.i)		; visa id: 27
  %16 = call float @llvm.genx.GenISA.mul.rtz.f32.f32.f32(float %14, float %15)		; visa id: 28
  %conv3.i = fptoui float %14 to i32		; visa id: 29
  %sub4.i = sub i32 %12, %conv3.i		; visa id: 30
  %conv8.i = fptoui float %16 to i32		; visa id: 31
  %17 = call float @llvm.genx.GenISA.uitof.rtz.f32.i32(i32 %sub.i)		; visa id: 32
  %18 = call float @llvm.genx.GenISA.uitof.rtz.f32.i32(i32 %sub4.i)		; visa id: 33
  %19 = call float @llvm.genx.GenISA.uitof.rtz.f32.i32(i32 %conv8.i)		; visa id: 34
  %20 = fsub float 0.000000e+00, %13		; visa id: 35
  %21 = call float @llvm.genx.GenISA.fma.rtz.f32.f32.f32.f32(float %20, float %19, float %14)		; visa id: 36
  %22 = fsub float 0.000000e+00, %17		; visa id: 37
  %23 = call float @llvm.genx.GenISA.fma.rtz.f32.f32.f32.f32(float %22, float %19, float %18)		; visa id: 38
  %24 = call float @llvm.genx.GenISA.add.rtz.f32.f32.f32(float %21, float %23)		; visa id: 39
  %25 = call float @llvm.genx.GenISA.mul.rtz.f32.f32.f32(float %15, float %24)		; visa id: 40
  %conv16.i = fptoui float %25 to i32		; visa id: 42
  %add.i = add i32 %conv16.i, %conv8.i		; visa id: 43
  %mul.i = mul i32 %add.i, %const_reg_dword21		; visa id: 44
  %sub17.i = sub i32 %12, %mul.i		; visa id: 45
  %cmp.i = icmp uge i32 %sub17.i, %const_reg_dword21
  %26 = sext i1 %cmp.i to i32		; visa id: 46
  %27 = sub i32 0, %26
  %add19.i = add i32 %add.i, %27		; visa id: 47
  br label %precompiled_u32divrem_sp.exit, !stats.blockFrequency.digits !8788, !stats.blockFrequency.scale !8789		; visa id: 48

precompiled_u32divrem_sp.exit:                    ; preds = %.precompiled_u32divrem_sp.exit_crit_edge, %if.end.i
; BB3 :
  %retval.0.i = phi i32 [ %add19.i, %if.end.i ], [ -1, %.precompiled_u32divrem_sp.exit_crit_edge ]
  %28 = mul i32 %retval.0.i, %const_reg_dword21		; visa id: 49
  %29 = icmp uge i32 %12, %1
  %30 = icmp uge i32 %12, %1		; visa id: 50
  br i1 %30, label %precompiled_u32divrem_sp.exit.._crit_edge_crit_edge, label %31, !stats.blockFrequency.digits !8783, !stats.blockFrequency.scale !8784		; visa id: 51

precompiled_u32divrem_sp.exit.._crit_edge_crit_edge: ; preds = %precompiled_u32divrem_sp.exit
; BB4 :
  br label %._crit_edge, !stats.blockFrequency.digits !8783, !stats.blockFrequency.scale !8789		; visa id: 56

31:                                               ; preds = %precompiled_u32divrem_sp.exit
; BB5 :
  %32 = call { i32, i32 } @llvm.genx.GenISA.mul.pair(i32 %retval.0.i, i32 0, i32 12, i32 0)
  %33 = extractvalue { i32, i32 } %32, 0
  %34 = extractvalue { i32, i32 } %32, 1
  %35 = insertelement <2 x i32> undef, i32 %33, i32 0
  %36 = insertelement <2 x i32> %35, i32 %34, i32 1
  %37 = bitcast <2 x i32> %36 to i64		; visa id: 58
  %38 = add i64 %37, %const_reg_qword16		; visa id: 66
  %39 = inttoptr i64 %38 to ptr addrspace(4)		; visa id: 67
  %40 = addrspacecast ptr addrspace(4) %39 to ptr addrspace(1)		; visa id: 67
  %41 = load <2 x i32>, ptr addrspace(1) %40, align 4		; visa id: 68
  %42 = extractelement <2 x i32> %41, i32 0		; visa id: 69
  %43 = extractelement <2 x i32> %41, i32 1		; visa id: 69
  %44 = icmp uge i32 %42, %const_reg_dword23
  %45 = icmp ugt i32 %43, %const_reg_dword21		; visa id: 69
  %46 = or i1 %44, %45		; visa id: 70
  br i1 %46, label %.._crit_edge_crit_edge, label %47, !stats.blockFrequency.digits !8783, !stats.blockFrequency.scale !8789		; visa id: 72

.._crit_edge_crit_edge:                           ; preds = %31
; BB6 :
  br label %._crit_edge, !stats.blockFrequency.digits !8783, !stats.blockFrequency.scale !8786		; visa id: 77

47:                                               ; preds = %31
; BB7 :
  %48 = sub i32 %12, %28		; visa id: 79
  %49 = add i64 %38, 8		; visa id: 80
  %50 = inttoptr i64 %49 to ptr addrspace(4)		; visa id: 81
  %51 = addrspacecast ptr addrspace(4) %50 to ptr addrspace(1)		; visa id: 81
  %52 = load i32, ptr addrspace(1) %51, align 4		; visa id: 82
  %53 = sub nuw i32 %const_reg_dword21, %43, !spirv.Decorations !8781		; visa id: 83
  %54 = icmp ule i32 %52, %53
  %55 = icmp ule i32 %52, %const_reg_dword21		; visa id: 84
  %56 = and i1 %54, %55		; visa id: 85
  %57 = icmp ult i32 %48, %52		; visa id: 87
  %58 = and i1 %56, %57		; visa id: 88
  br i1 %58, label %61, label %._crit_edge43, !stats.blockFrequency.digits !8783, !stats.blockFrequency.scale !8786		; visa id: 89

._crit_edge43:                                    ; preds = %47
; BB8 :
  %59 = xor i1 %56, true		; visa id: 91
  %60 = sext i1 %59 to i32		; visa id: 92
  br label %._crit_edge, !stats.blockFrequency.digits !8783, !stats.blockFrequency.scale !8790		; visa id: 95

61:                                               ; preds = %47
; BB9 :
  %62 = bitcast i64 %const_reg_qword to <2 x i32>		; visa id: 97
  %63 = extractelement <2 x i32> %62, i32 0		; visa id: 98
  %64 = extractelement <2 x i32> %62, i32 1		; visa id: 98
  %65 = bitcast i64 %const_reg_qword1 to <2 x i32>		; visa id: 98
  %66 = extractelement <2 x i32> %65, i32 0		; visa id: 99
  %67 = extractelement <2 x i32> %65, i32 1		; visa id: 99
  %68 = ptrtoint ptr addrspace(2) %constBase to i64		; visa id: 99
  %69 = add i64 %68, 32
  %70 = call { i32, i32 } @llvm.genx.GenISA.mul.pair(i32 %42, i32 0, i32 %const_reg_dword21, i32 0)
  %71 = extractvalue { i32, i32 } %70, 0
  %72 = extractvalue { i32, i32 } %70, 1
  %73 = insertelement <2 x i32> undef, i32 %71, i32 0
  %74 = insertelement <2 x i32> %73, i32 %72, i32 1
  %75 = bitcast <2 x i32> %74 to i64		; visa id: 99
  %76 = zext i32 %43 to i64		; visa id: 107
  %77 = add nuw i64 %75, %76, !spirv.Decorations !8781		; visa id: 108
  %78 = zext i32 %48 to i64		; visa id: 109
  %79 = add nuw i64 %77, %78, !spirv.Decorations !8781		; visa id: 110
  %80 = bitcast i64 %79 to <2 x i32>		; visa id: 111
  %81 = extractelement <2 x i32> %80, i32 0		; visa id: 115
  %82 = extractelement <2 x i32> %80, i32 1		; visa id: 115
  %83 = icmp eq i32 %7, 0		; visa id: 115
  %84 = select i1 %83, i32 %63, i32 %66		; visa id: 116
  %85 = select i1 %83, i32 %64, i32 %67		; visa id: 117
  %86 = insertelement <2 x i32> undef, i32 %84, i32 0		; visa id: 118
  %87 = insertelement <2 x i32> %86, i32 %85, i32 1		; visa id: 119
  %88 = bitcast <2 x i32> %87 to i64		; visa id: 120
  %89 = call { i32, i32 } @llvm.genx.GenISA.mul.pair(i32 %81, i32 %82, i32 %const_reg_dword, i32 0)
  %90 = extractvalue { i32, i32 } %89, 0
  %91 = extractvalue { i32, i32 } %89, 1
  %92 = insertelement <2 x i32> undef, i32 %90, i32 0
  %93 = insertelement <2 x i32> %92, i32 %91, i32 1
  %94 = bitcast <2 x i32> %93 to i64		; visa id: 124
  %95 = add i64 %88, %94		; visa id: 132
  %chunkPtr = inttoptr i64 %69 to ptr addrspace(2)
  %96 = load <8 x float>, ptr addrspace(2) %chunkPtr, align 8		; visa id: 133
  %97 = extractelement <8 x float> %96, i32 0		; visa id: 135
  %98 = extractelement <8 x float> %96, i32 1		; visa id: 135
  %99 = extractelement <8 x float> %96, i32 2		; visa id: 135
  %100 = extractelement <8 x float> %96, i32 3		; visa id: 135
  %101 = extractelement <8 x float> %96, i32 4		; visa id: 135
  %102 = extractelement <8 x float> %96, i32 5		; visa id: 135
  %103 = extractelement <8 x float> %96, i32 6		; visa id: 135
  %104 = extractelement <8 x float> %96, i32 7		; visa id: 135
  %105 = shl nuw nsw i32 %5, 6, !spirv.Decorations !8791		; visa id: 135
  %106 = shl nuw nsw i32 %5, 4, !spirv.Decorations !8791		; visa id: 136
  %107 = zext i32 %106 to i64		; visa id: 137
  %108 = add i64 %95, %107		; visa id: 138
  %109 = add i64 %95, 640		; visa id: 139
  %110 = shl nuw nsw i32 %5, 1, !spirv.Decorations !8791		; visa id: 140
  %111 = zext i32 %110 to i64		; visa id: 141
  %112 = add i64 %109, %111		; visa id: 142
  %113 = add i64 %95, 720		; visa id: 143
  %114 = add i64 %113, %111		; visa id: 144
  %115 = add i64 %95, 800		; visa id: 145
  %116 = ptrtoint ptr addrspace(1) %globalBase to i64		; visa id: 146
  br label %.preheader1.preheader, !stats.blockFrequency.digits !8783, !stats.blockFrequency.scale !8790		; visa id: 157

.preheader1.preheader:                            ; preds = %..preheader1.preheader_crit_edge, %61
; BB10 :
  %.sroa.36.0 = phi float [ %104, %61 ], [ %1886, %..preheader1.preheader_crit_edge ]
  %.sroa.31.0 = phi float [ %103, %61 ], [ %1675, %..preheader1.preheader_crit_edge ]
  %.sroa.28.0 = phi float [ %102, %61 ], [ %1452, %..preheader1.preheader_crit_edge ]
  %.sroa.21.0 = phi float [ %101, %61 ], [ %1241, %..preheader1.preheader_crit_edge ]
  %.sroa.18.0 = phi float [ %100, %61 ], [ %1018, %..preheader1.preheader_crit_edge ]
  %.sroa.13.0 = phi float [ %99, %61 ], [ %807, %..preheader1.preheader_crit_edge ]
  %.sroa.10.0 = phi float [ %98, %61 ], [ %583, %..preheader1.preheader_crit_edge ]
  %.sroa.0.0 = phi float [ %97, %61 ], [ %372, %..preheader1.preheader_crit_edge ]
  %117 = phi i32 [ 0, %61 ], [ %1888, %..preheader1.preheader_crit_edge ]
  %118 = shl nuw nsw i32 %117, 8, !spirv.Decorations !8791		; visa id: 158
  %119 = shl nuw nsw i32 %117, 6, !spirv.Decorations !8791		; visa id: 159
  %120 = zext i32 %119 to i64		; visa id: 160
  %121 = add i64 %108, %120		; visa id: 161
  %122 = inttoptr i64 %121 to ptr addrspace(4)		; visa id: 162
  %generic_cast_to_ptr = addrspacecast ptr addrspace(4) %122 to ptr addrspace(1)		; visa id: 162
  %123 = load <4 x i32>, ptr addrspace(1) %generic_cast_to_ptr, align 4		; visa id: 163
  %124 = extractelement <4 x i32> %123, i32 0		; visa id: 164
  %125 = extractelement <4 x i32> %123, i32 1		; visa id: 164
  %126 = extractelement <4 x i32> %123, i32 2		; visa id: 164
  %127 = extractelement <4 x i32> %123, i32 3		; visa id: 164
  %128 = or i32 %118, %105		; visa id: 164
  %129 = shl nuw nsw i32 %117, 3, !spirv.Decorations !8791		; visa id: 165
  %130 = zext i32 %129 to i64		; visa id: 166
  %131 = add i64 %112, %130		; visa id: 167
  %132 = inttoptr i64 %131 to ptr addrspace(4)		; visa id: 168
  %133 = addrspacecast ptr addrspace(4) %132 to ptr addrspace(1)		; visa id: 168
  %134 = load i16, ptr addrspace(1) %133, align 2, !noalias !8793		; visa id: 169
  %135 = add i64 %114, %130		; visa id: 171
  %136 = inttoptr i64 %135 to ptr addrspace(4)		; visa id: 172
  %137 = addrspacecast ptr addrspace(4) %136 to ptr addrspace(1)		; visa id: 172
  %138 = load i16, ptr addrspace(1) %137, align 2, !noalias !8793		; visa id: 173
  %139 = shl nuw nsw i32 %117, 2, !spirv.Decorations !8791		; visa id: 175
  %140 = zext i32 %139 to i64		; visa id: 176
  %141 = add i64 %115, %140		; visa id: 177
  %142 = inttoptr i64 %141 to ptr addrspace(4)		; visa id: 178
  %143 = addrspacecast ptr addrspace(4) %142 to ptr addrspace(1)		; visa id: 178
  %144 = load float, ptr addrspace(1) %143, align 4, !noalias !8793		; visa id: 179
  %145 = and i32 %124, 255
  %146 = zext i16 %134 to i32		; visa id: 180
  %147 = shl nuw nsw i32 %146, 8, !spirv.Decorations !8791		; visa id: 181
  %148 = and i32 %147, 768		; visa id: 182
  %149 = or i32 %145, %148		; visa id: 183
  %150 = shl nuw nsw i32 %149, 3, !spirv.Decorations !8791		; visa id: 184
  %151 = zext i32 %150 to i64		; visa id: 185
  %152 = add i64 %116, %151		; visa id: 186
  %153 = inttoptr i64 %152 to ptr addrspace(1)		; visa id: 187
  %154 = load <2 x i32>, ptr addrspace(1) %153, align 4		; visa id: 187
  %155 = bitcast float %144 to i32
  %156 = and i32 %155, 2147483647		; visa id: 188
  %157 = bitcast i32 %156 to float
  %158 = fcmp une float %157, %157
  %159 = fcmp oeq float %157, 0x7FF0000000000000		; visa id: 189
  %160 = or i1 %158, %159		; visa id: 190
  %161 = zext i16 %138 to i32		; visa id: 192
  %162 = and i32 %161, 15		; visa id: 193
  %163 = uitofp i32 %162 to float		; visa id: 194
  %164 = fadd float %163, 5.000000e-01		; visa id: 195
  %165 = fmul float %144, %164		; visa id: 196
  %166 = fmul float %165, 2.500000e-01		; visa id: 197
  %167 = extractelement <2 x i32> %154, i32 0		; visa id: 198
  %168 = extractelement <2 x i32> %154, i32 1		; visa id: 198
  %169 = bitcast float %166 to i32
  %170 = and i32 %169, 2147483647		; visa id: 198
  %171 = icmp ugt i32 %170, 2139095040
  %172 = or i1 %160, %171		; visa id: 199
  %173 = and i32 %167, 255		; visa id: 201
  br i1 %172, label %181, label %174, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 202

174:                                              ; preds = %.preheader1.preheader
; BB11 :
  %175 = and i32 %124, 256
  %176 = sub nsw i32 0, %173, !spirv.Decorations !8800
  %177 = icmp eq i32 %175, 0		; visa id: 204
  %178 = select i1 %177, i32 %173, i32 %176		; visa id: 206
  %179 = sitofp i32 %178 to float		; visa id: 207
  %180 = fmul float %166, %179		; visa id: 208
  br label %189, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 209

181:                                              ; preds = %.preheader1.preheader
; BB12 :
  %182 = uitofp i32 %173 to float		; visa id: 211
  %183 = fmul float %166, %182		; visa id: 212
  %184 = and i32 %124, 256
  %185 = icmp eq i32 %184, 0		; visa id: 213
  %186 = select i1 %185, i32 1, i32 -1		; visa id: 215
  %187 = sitofp i32 %186 to float		; visa id: 216
  %188 = fmul float %183, %187		; visa id: 217
  br label %189, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 218

189:                                              ; preds = %174, %181
; BB13 :
  %.sroa.0121.0 = phi float [ %188, %181 ], [ %180, %174 ]
  %190 = bitcast i32 %167 to <4 x i8>
  %191 = extractelement <4 x i8> %190, i32 1
  %192 = zext i8 %191 to i32		; visa id: 219
  br i1 %172, label %200, label %193, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 220

193:                                              ; preds = %189
; BB14 :
  %194 = and i32 %124, 512
  %195 = sub nsw i32 0, %192, !spirv.Decorations !8800
  %196 = icmp eq i32 %194, 0		; visa id: 222
  %197 = select i1 %196, i32 %192, i32 %195		; visa id: 224
  %198 = sitofp i32 %197 to float		; visa id: 225
  %199 = fmul float %166, %198		; visa id: 226
  br label %208, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 227

200:                                              ; preds = %189
; BB15 :
  %201 = uitofp i32 %192 to float		; visa id: 229
  %202 = fmul float %166, %201		; visa id: 230
  %203 = and i32 %124, 512
  %204 = icmp eq i32 %203, 0		; visa id: 231
  %205 = select i1 %204, i32 1, i32 -1		; visa id: 233
  %206 = sitofp i32 %205 to float		; visa id: 234
  %207 = fmul float %202, %206		; visa id: 235
  br label %208, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 236

208:                                              ; preds = %200, %193
; BB16 :
  %.sroa.40.0 = phi float [ %207, %200 ], [ %199, %193 ]
  %209 = extractelement <4 x i8> %190, i32 2
  %210 = zext i8 %209 to i32		; visa id: 237
  br i1 %172, label %218, label %211, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 238

211:                                              ; preds = %208
; BB17 :
  %212 = and i32 %124, 1024
  %213 = sub nsw i32 0, %210, !spirv.Decorations !8800
  %214 = icmp eq i32 %212, 0		; visa id: 240
  %215 = select i1 %214, i32 %210, i32 %213		; visa id: 242
  %216 = sitofp i32 %215 to float		; visa id: 243
  %217 = fmul float %166, %216		; visa id: 244
  br label %226, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 245

218:                                              ; preds = %208
; BB18 :
  %219 = uitofp i32 %210 to float		; visa id: 247
  %220 = fmul float %166, %219		; visa id: 248
  %221 = and i32 %124, 1024
  %222 = icmp eq i32 %221, 0		; visa id: 249
  %223 = select i1 %222, i32 1, i32 -1		; visa id: 251
  %224 = sitofp i32 %223 to float		; visa id: 252
  %225 = fmul float %220, %224		; visa id: 253
  br label %226, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 254

226:                                              ; preds = %218, %211
; BB19 :
  %.sroa.64136.0 = phi float [ %225, %218 ], [ %217, %211 ]
  %227 = lshr i32 %167, 24		; visa id: 255
  br i1 %172, label %235, label %228, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 256

228:                                              ; preds = %226
; BB20 :
  %229 = and i32 %124, 2048
  %230 = sub nsw i32 0, %227, !spirv.Decorations !8800
  %231 = icmp eq i32 %229, 0		; visa id: 258
  %232 = select i1 %231, i32 %227, i32 %230		; visa id: 260
  %233 = sitofp i32 %232 to float		; visa id: 261
  %234 = fmul float %166, %233		; visa id: 262
  br label %243, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 263

235:                                              ; preds = %226
; BB21 :
  %236 = uitofp i32 %227 to float		; visa id: 265
  %237 = fmul float %166, %236		; visa id: 266
  %238 = and i32 %124, 2048
  %239 = icmp eq i32 %238, 0		; visa id: 267
  %240 = select i1 %239, i32 1, i32 -1		; visa id: 269
  %241 = sitofp i32 %240 to float		; visa id: 270
  %242 = fmul float %237, %241		; visa id: 271
  br label %243, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 272

243:                                              ; preds = %235, %228
; BB22 :
  %.sroa.88.0 = phi float [ %242, %235 ], [ %234, %228 ]
  %244 = and i32 %168, 255		; visa id: 273
  br i1 %172, label %252, label %245, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 274

245:                                              ; preds = %243
; BB23 :
  %246 = and i32 %124, 4096
  %247 = sub nsw i32 0, %244, !spirv.Decorations !8800
  %248 = icmp eq i32 %246, 0		; visa id: 276
  %249 = select i1 %248, i32 %244, i32 %247		; visa id: 278
  %250 = sitofp i32 %249 to float		; visa id: 279
  %251 = fmul float %166, %250		; visa id: 280
  br label %260, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 281

252:                                              ; preds = %243
; BB24 :
  %253 = uitofp i32 %244 to float		; visa id: 283
  %254 = fmul float %166, %253		; visa id: 284
  %255 = and i32 %124, 4096
  %256 = icmp eq i32 %255, 0		; visa id: 285
  %257 = select i1 %256, i32 1, i32 -1		; visa id: 287
  %258 = sitofp i32 %257 to float		; visa id: 288
  %259 = fmul float %254, %258		; visa id: 289
  br label %260, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 290

260:                                              ; preds = %252, %245
; BB25 :
  %.sroa.112151.0 = phi float [ %259, %252 ], [ %251, %245 ]
  %261 = bitcast i32 %168 to <4 x i8>
  %262 = extractelement <4 x i8> %261, i32 1
  %263 = zext i8 %262 to i32		; visa id: 291
  br i1 %172, label %271, label %264, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 292

264:                                              ; preds = %260
; BB26 :
  %265 = and i32 %124, 8192
  %266 = sub nsw i32 0, %263, !spirv.Decorations !8800
  %267 = icmp eq i32 %265, 0		; visa id: 294
  %268 = select i1 %267, i32 %263, i32 %266		; visa id: 296
  %269 = sitofp i32 %268 to float		; visa id: 297
  %270 = fmul float %166, %269		; visa id: 298
  br label %279, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 299

271:                                              ; preds = %260
; BB27 :
  %272 = uitofp i32 %263 to float		; visa id: 301
  %273 = fmul float %166, %272		; visa id: 302
  %274 = and i32 %124, 8192
  %275 = icmp eq i32 %274, 0		; visa id: 303
  %276 = select i1 %275, i32 1, i32 -1		; visa id: 305
  %277 = sitofp i32 %276 to float		; visa id: 306
  %278 = fmul float %273, %277		; visa id: 307
  br label %279, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 308

279:                                              ; preds = %271, %264
; BB28 :
  %.sroa.136.0 = phi float [ %278, %271 ], [ %270, %264 ]
  %280 = extractelement <4 x i8> %261, i32 2
  %281 = zext i8 %280 to i32		; visa id: 309
  br i1 %172, label %289, label %282, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 310

282:                                              ; preds = %279
; BB29 :
  %283 = and i32 %124, 16384
  %284 = sub nsw i32 0, %281, !spirv.Decorations !8800
  %285 = icmp eq i32 %283, 0		; visa id: 312
  %286 = select i1 %285, i32 %281, i32 %284		; visa id: 314
  %287 = sitofp i32 %286 to float		; visa id: 315
  %288 = fmul float %166, %287		; visa id: 316
  br label %297, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 317

289:                                              ; preds = %279
; BB30 :
  %290 = uitofp i32 %281 to float		; visa id: 319
  %291 = fmul float %166, %290		; visa id: 320
  %292 = and i32 %124, 16384
  %293 = icmp eq i32 %292, 0		; visa id: 321
  %294 = select i1 %293, i32 1, i32 -1		; visa id: 323
  %295 = sitofp i32 %294 to float		; visa id: 324
  %296 = fmul float %291, %295		; visa id: 325
  br label %297, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 326

297:                                              ; preds = %289, %282
; BB31 :
  %.sroa.160.0 = phi float [ %296, %289 ], [ %288, %282 ]
  %298 = lshr i32 %168, 24		; visa id: 327
  br i1 %172, label %306, label %299, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 328

299:                                              ; preds = %297
; BB32 :
  %300 = and i32 %124, 32768
  %301 = sub nsw i32 0, %298, !spirv.Decorations !8800
  %302 = icmp eq i32 %300, 0		; visa id: 330
  %303 = select i1 %302, i32 %298, i32 %301		; visa id: 332
  %304 = sitofp i32 %303 to float		; visa id: 333
  %305 = fmul float %166, %304		; visa id: 334
  br label %314, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 335

306:                                              ; preds = %297
; BB33 :
  %307 = uitofp i32 %298 to float		; visa id: 337
  %308 = fmul float %166, %307		; visa id: 338
  %309 = and i32 %124, 32768
  %310 = icmp eq i32 %309, 0		; visa id: 339
  %311 = select i1 %310, i32 1, i32 -1		; visa id: 341
  %312 = sitofp i32 %311 to float		; visa id: 342
  %313 = fmul float %308, %312		; visa id: 343
  br label %314, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 344

314:                                              ; preds = %306, %299
; BB34 :
  %.sroa.184.0 = phi float [ %313, %306 ], [ %305, %299 ]
  %315 = shl nuw i32 %128, 1		; visa id: 345
  %316 = zext i32 %315 to i64		; visa id: 346
  %317 = add i64 %316, %const_reg_qword2		; visa id: 347
  %IntToPtr2 = inttoptr i64 %317 to ptr addrspace(1)		; visa id: 348
  %vCastload = load i32, ptr addrspace(1) %IntToPtr2, align 2		; visa id: 348
  %318 = add i64 %317, 4
  %IntToPtr2269 = inttoptr i64 %318 to ptr addrspace(1)
  %vCastload270 = load i32, ptr addrspace(1) %IntToPtr2269, align 2		; visa id: 349
  %319 = add i64 %317, 8
  %IntToPtr2271 = inttoptr i64 %319 to ptr addrspace(1)
  %vCastload272 = load i32, ptr addrspace(1) %IntToPtr2271, align 2		; visa id: 350
  %320 = add i64 %317, 12
  %IntToPtr2273 = inttoptr i64 %320 to ptr addrspace(1)
  %vCastload274 = load i32, ptr addrspace(1) %IntToPtr2273, align 2		; visa id: 351
  %321 = bitcast i32 %vCastload to <2 x i16>		; visa id: 352
  %322 = bitcast i32 %vCastload270 to <2 x i16>		; visa id: 354
  %323 = extractelement <2 x i16> %321, i32 0		; visa id: 356
  %324 = extractelement <2 x i16> %321, i32 1		; visa id: 356
  %325 = extractelement <2 x i16> %322, i32 0		; visa id: 356
  %326 = extractelement <2 x i16> %322, i32 1		; visa id: 356
  %327 = bitcast i32 %vCastload272 to <2 x i16>		; visa id: 356
  %328 = bitcast i32 %vCastload274 to <2 x i16>		; visa id: 358
  %329 = extractelement <2 x i16> %327, i32 0		; visa id: 360
  %330 = extractelement <2 x i16> %327, i32 1		; visa id: 360
  %331 = extractelement <2 x i16> %328, i32 0		; visa id: 360
  %332 = extractelement <2 x i16> %328, i32 1		; visa id: 360
  %333 = zext i16 %323 to i32		; visa id: 360
  %334 = shl nuw i32 %333, 16, !spirv.Decorations !8781		; visa id: 361
  %335 = bitcast i32 %334 to float
  %336 = fmul float %.sroa.0121.0, %335		; visa id: 362
  %337 = fadd float %.sroa.0.0, %336		; visa id: 363
  %338 = zext i16 %324 to i32		; visa id: 364
  %339 = shl nuw i32 %338, 16, !spirv.Decorations !8781		; visa id: 365
  %340 = bitcast i32 %339 to float
  %341 = fmul float %.sroa.40.0, %340		; visa id: 366
  %342 = fadd float %337, %341		; visa id: 367
  %343 = zext i16 %325 to i32		; visa id: 368
  %344 = shl nuw i32 %343, 16, !spirv.Decorations !8781		; visa id: 369
  %345 = bitcast i32 %344 to float
  %346 = fmul float %.sroa.64136.0, %345		; visa id: 370
  %347 = fadd float %342, %346		; visa id: 371
  %348 = zext i16 %326 to i32		; visa id: 372
  %349 = shl nuw i32 %348, 16, !spirv.Decorations !8781		; visa id: 373
  %350 = bitcast i32 %349 to float
  %351 = fmul float %.sroa.88.0, %350		; visa id: 374
  %352 = fadd float %347, %351		; visa id: 375
  %353 = zext i16 %329 to i32		; visa id: 376
  %354 = shl nuw i32 %353, 16, !spirv.Decorations !8781		; visa id: 377
  %355 = bitcast i32 %354 to float
  %356 = fmul float %.sroa.112151.0, %355		; visa id: 378
  %357 = fadd float %352, %356		; visa id: 379
  %358 = zext i16 %330 to i32		; visa id: 380
  %359 = shl nuw i32 %358, 16, !spirv.Decorations !8781		; visa id: 381
  %360 = bitcast i32 %359 to float
  %361 = fmul float %.sroa.136.0, %360		; visa id: 382
  %362 = fadd float %357, %361		; visa id: 383
  %363 = zext i16 %331 to i32		; visa id: 384
  %364 = shl nuw i32 %363, 16, !spirv.Decorations !8781		; visa id: 385
  %365 = bitcast i32 %364 to float
  %366 = fmul float %.sroa.160.0, %365		; visa id: 386
  %367 = fadd float %362, %366		; visa id: 387
  %368 = zext i16 %332 to i32		; visa id: 388
  %369 = shl nuw i32 %368, 16, !spirv.Decorations !8781		; visa id: 389
  %370 = bitcast i32 %369 to float
  %371 = fmul float %.sroa.184.0, %370		; visa id: 390
  %372 = fadd float %367, %371		; visa id: 391
  %373 = bitcast i32 %124 to <4 x i8>
  %374 = extractelement <4 x i8> %373, i32 2
  %375 = shl nuw nsw i32 %146, 6		; visa id: 392
  %376 = and i32 %375, 768
  %377 = zext i8 %374 to i32		; visa id: 393
  %378 = or i32 %377, %376		; visa id: 394
  %379 = shl nuw nsw i32 %378, 3, !spirv.Decorations !8791		; visa id: 395
  %380 = zext i32 %379 to i64		; visa id: 396
  %381 = add i64 %116, %380		; visa id: 397
  %382 = inttoptr i64 %381 to ptr addrspace(1)		; visa id: 398
  %383 = load <2 x i32>, ptr addrspace(1) %382, align 4		; visa id: 398
  %384 = extractelement <2 x i32> %383, i32 0		; visa id: 399
  %385 = extractelement <2 x i32> %383, i32 1		; visa id: 399
  %386 = and i32 %384, 255		; visa id: 399
  br i1 %172, label %394, label %387, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 400

387:                                              ; preds = %314
; BB35 :
  %388 = and i32 %124, 16777216
  %389 = sub nsw i32 0, %386, !spirv.Decorations !8800
  %390 = icmp eq i32 %388, 0		; visa id: 402
  %391 = select i1 %390, i32 %386, i32 %389		; visa id: 404
  %392 = sitofp i32 %391 to float		; visa id: 405
  %393 = fmul float %166, %392		; visa id: 406
  br label %402, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 407

394:                                              ; preds = %314
; BB36 :
  %395 = uitofp i32 %386 to float		; visa id: 409
  %396 = fmul float %166, %395		; visa id: 410
  %397 = and i32 %124, 16777216
  %398 = icmp eq i32 %397, 0		; visa id: 411
  %399 = select i1 %398, i32 1, i32 -1		; visa id: 413
  %400 = sitofp i32 %399 to float		; visa id: 414
  %401 = fmul float %396, %400		; visa id: 415
  br label %402, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 416

402:                                              ; preds = %394, %387
; BB37 :
  %.sroa.0121.1 = phi float [ %401, %394 ], [ %393, %387 ]
  %403 = bitcast i32 %384 to <4 x i8>
  %404 = extractelement <4 x i8> %403, i32 1
  %405 = zext i8 %404 to i32		; visa id: 417
  br i1 %172, label %413, label %406, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 418

406:                                              ; preds = %402
; BB38 :
  %407 = and i32 %124, 33554432
  %408 = sub nsw i32 0, %405, !spirv.Decorations !8800
  %409 = icmp eq i32 %407, 0		; visa id: 420
  %410 = select i1 %409, i32 %405, i32 %408		; visa id: 422
  %411 = sitofp i32 %410 to float		; visa id: 423
  %412 = fmul float %166, %411		; visa id: 424
  br label %421, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 425

413:                                              ; preds = %402
; BB39 :
  %414 = uitofp i32 %405 to float		; visa id: 427
  %415 = fmul float %166, %414		; visa id: 428
  %416 = and i32 %124, 33554432
  %417 = icmp eq i32 %416, 0		; visa id: 429
  %418 = select i1 %417, i32 1, i32 -1		; visa id: 431
  %419 = sitofp i32 %418 to float		; visa id: 432
  %420 = fmul float %415, %419		; visa id: 433
  br label %421, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 434

421:                                              ; preds = %413, %406
; BB40 :
  %.sroa.40.1 = phi float [ %420, %413 ], [ %412, %406 ]
  %422 = extractelement <4 x i8> %403, i32 2
  %423 = zext i8 %422 to i32		; visa id: 435
  br i1 %172, label %431, label %424, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 436

424:                                              ; preds = %421
; BB41 :
  %425 = and i32 %124, 67108864
  %426 = sub nsw i32 0, %423, !spirv.Decorations !8800
  %427 = icmp eq i32 %425, 0		; visa id: 438
  %428 = select i1 %427, i32 %423, i32 %426		; visa id: 440
  %429 = sitofp i32 %428 to float		; visa id: 441
  %430 = fmul float %166, %429		; visa id: 442
  br label %439, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 443

431:                                              ; preds = %421
; BB42 :
  %432 = uitofp i32 %423 to float		; visa id: 445
  %433 = fmul float %166, %432		; visa id: 446
  %434 = and i32 %124, 67108864
  %435 = icmp eq i32 %434, 0		; visa id: 447
  %436 = select i1 %435, i32 1, i32 -1		; visa id: 449
  %437 = sitofp i32 %436 to float		; visa id: 450
  %438 = fmul float %433, %437		; visa id: 451
  br label %439, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 452

439:                                              ; preds = %431, %424
; BB43 :
  %.sroa.64136.1 = phi float [ %438, %431 ], [ %430, %424 ]
  %440 = lshr i32 %384, 24		; visa id: 453
  br i1 %172, label %448, label %441, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 454

441:                                              ; preds = %439
; BB44 :
  %442 = and i32 %124, 134217728
  %443 = sub nsw i32 0, %440, !spirv.Decorations !8800
  %444 = icmp eq i32 %442, 0		; visa id: 456
  %445 = select i1 %444, i32 %440, i32 %443		; visa id: 458
  %446 = sitofp i32 %445 to float		; visa id: 459
  %447 = fmul float %166, %446		; visa id: 460
  br label %456, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 461

448:                                              ; preds = %439
; BB45 :
  %449 = uitofp i32 %440 to float		; visa id: 463
  %450 = fmul float %166, %449		; visa id: 464
  %451 = and i32 %124, 134217728
  %452 = icmp eq i32 %451, 0		; visa id: 465
  %453 = select i1 %452, i32 1, i32 -1		; visa id: 467
  %454 = sitofp i32 %453 to float		; visa id: 468
  %455 = fmul float %450, %454		; visa id: 469
  br label %456, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 470

456:                                              ; preds = %448, %441
; BB46 :
  %.sroa.88.1 = phi float [ %455, %448 ], [ %447, %441 ]
  %457 = and i32 %385, 255		; visa id: 471
  br i1 %172, label %465, label %458, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 472

458:                                              ; preds = %456
; BB47 :
  %459 = and i32 %124, 268435456
  %460 = sub nsw i32 0, %457, !spirv.Decorations !8800
  %461 = icmp eq i32 %459, 0		; visa id: 474
  %462 = select i1 %461, i32 %457, i32 %460		; visa id: 476
  %463 = sitofp i32 %462 to float		; visa id: 477
  %464 = fmul float %166, %463		; visa id: 478
  br label %473, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 479

465:                                              ; preds = %456
; BB48 :
  %466 = uitofp i32 %457 to float		; visa id: 481
  %467 = fmul float %166, %466		; visa id: 482
  %468 = and i32 %124, 268435456
  %469 = icmp eq i32 %468, 0		; visa id: 483
  %470 = select i1 %469, i32 1, i32 -1		; visa id: 485
  %471 = sitofp i32 %470 to float		; visa id: 486
  %472 = fmul float %467, %471		; visa id: 487
  br label %473, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 488

473:                                              ; preds = %465, %458
; BB49 :
  %.sroa.112151.1 = phi float [ %472, %465 ], [ %464, %458 ]
  %474 = bitcast i32 %385 to <4 x i8>
  %475 = extractelement <4 x i8> %474, i32 1
  %476 = zext i8 %475 to i32		; visa id: 489
  br i1 %172, label %484, label %477, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 490

477:                                              ; preds = %473
; BB50 :
  %478 = and i32 %124, 536870912
  %479 = sub nsw i32 0, %476, !spirv.Decorations !8800
  %480 = icmp eq i32 %478, 0		; visa id: 492
  %481 = select i1 %480, i32 %476, i32 %479		; visa id: 494
  %482 = sitofp i32 %481 to float		; visa id: 495
  %483 = fmul float %166, %482		; visa id: 496
  br label %492, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 497

484:                                              ; preds = %473
; BB51 :
  %485 = uitofp i32 %476 to float		; visa id: 499
  %486 = fmul float %166, %485		; visa id: 500
  %487 = and i32 %124, 536870912
  %488 = icmp eq i32 %487, 0		; visa id: 501
  %489 = select i1 %488, i32 1, i32 -1		; visa id: 503
  %490 = sitofp i32 %489 to float		; visa id: 504
  %491 = fmul float %486, %490		; visa id: 505
  br label %492, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 506

492:                                              ; preds = %484, %477
; BB52 :
  %.sroa.136.1 = phi float [ %491, %484 ], [ %483, %477 ]
  %493 = extractelement <4 x i8> %474, i32 2
  %494 = zext i8 %493 to i32		; visa id: 507
  br i1 %172, label %502, label %495, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 508

495:                                              ; preds = %492
; BB53 :
  %496 = and i32 %124, 1073741824
  %497 = sub nsw i32 0, %494, !spirv.Decorations !8800
  %498 = icmp eq i32 %496, 0		; visa id: 510
  %499 = select i1 %498, i32 %494, i32 %497		; visa id: 512
  %500 = sitofp i32 %499 to float		; visa id: 513
  %501 = fmul float %166, %500		; visa id: 514
  br label %510, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 515

502:                                              ; preds = %492
; BB54 :
  %503 = uitofp i32 %494 to float		; visa id: 517
  %504 = fmul float %166, %503		; visa id: 518
  %505 = and i32 %124, 1073741824
  %506 = icmp eq i32 %505, 0		; visa id: 519
  %507 = select i1 %506, i32 1, i32 -1		; visa id: 521
  %508 = sitofp i32 %507 to float		; visa id: 522
  %509 = fmul float %504, %508		; visa id: 523
  br label %510, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 524

510:                                              ; preds = %502, %495
; BB55 :
  %.sroa.160.1 = phi float [ %509, %502 ], [ %501, %495 ]
  %511 = lshr i32 %385, 24		; visa id: 525
  br i1 %172, label %518, label %512, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 526

512:                                              ; preds = %510
; BB56 :
  %513 = sub nsw i32 0, %511, !spirv.Decorations !8800
  %514 = icmp slt i32 %124, 0		; visa id: 528
  %515 = select i1 %514, i32 %513, i32 %511		; visa id: 529
  %516 = sitofp i32 %515 to float		; visa id: 530
  %517 = fmul float %166, %516		; visa id: 531
  br label %525, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 532

518:                                              ; preds = %510
; BB57 :
  %519 = uitofp i32 %511 to float		; visa id: 534
  %520 = fmul float %166, %519		; visa id: 535
  %521 = icmp sgt i32 %124, -1		; visa id: 536
  %522 = select i1 %521, i32 1, i32 -1		; visa id: 537
  %523 = sitofp i32 %522 to float		; visa id: 538
  %524 = fmul float %520, %523		; visa id: 539
  br label %525, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 540

525:                                              ; preds = %518, %512
; BB58 :
  %.sroa.184.1 = phi float [ %524, %518 ], [ %517, %512 ]
  %526 = or i32 %315, 16		; visa id: 541
  %527 = zext i32 %526 to i64		; visa id: 542
  %528 = add i64 %527, %const_reg_qword2		; visa id: 543
  %IntToPtr2275 = inttoptr i64 %528 to ptr addrspace(1)		; visa id: 544
  %vCastload276 = load i32, ptr addrspace(1) %IntToPtr2275, align 2		; visa id: 544
  %529 = add i64 %528, 4
  %IntToPtr2277 = inttoptr i64 %529 to ptr addrspace(1)
  %vCastload278 = load i32, ptr addrspace(1) %IntToPtr2277, align 2		; visa id: 545
  %530 = add i64 %528, 8
  %IntToPtr2279 = inttoptr i64 %530 to ptr addrspace(1)
  %vCastload280 = load i32, ptr addrspace(1) %IntToPtr2279, align 2		; visa id: 546
  %531 = add i64 %528, 12
  %IntToPtr2281 = inttoptr i64 %531 to ptr addrspace(1)
  %vCastload282 = load i32, ptr addrspace(1) %IntToPtr2281, align 2		; visa id: 547
  %532 = bitcast i32 %vCastload276 to <2 x i16>		; visa id: 548
  %533 = bitcast i32 %vCastload278 to <2 x i16>		; visa id: 550
  %534 = extractelement <2 x i16> %532, i32 0		; visa id: 552
  %535 = extractelement <2 x i16> %532, i32 1		; visa id: 552
  %536 = extractelement <2 x i16> %533, i32 0		; visa id: 552
  %537 = extractelement <2 x i16> %533, i32 1		; visa id: 552
  %538 = bitcast i32 %vCastload280 to <2 x i16>		; visa id: 552
  %539 = bitcast i32 %vCastload282 to <2 x i16>		; visa id: 554
  %540 = extractelement <2 x i16> %538, i32 0		; visa id: 556
  %541 = extractelement <2 x i16> %538, i32 1		; visa id: 556
  %542 = extractelement <2 x i16> %539, i32 0		; visa id: 556
  %543 = extractelement <2 x i16> %539, i32 1		; visa id: 556
  %544 = zext i16 %534 to i32		; visa id: 556
  %545 = shl nuw i32 %544, 16, !spirv.Decorations !8781		; visa id: 557
  %546 = bitcast i32 %545 to float
  %547 = fmul float %.sroa.0121.1, %546		; visa id: 558
  %548 = fadd float %.sroa.10.0, %547		; visa id: 559
  %549 = zext i16 %535 to i32		; visa id: 560
  %550 = shl nuw i32 %549, 16, !spirv.Decorations !8781		; visa id: 561
  %551 = bitcast i32 %550 to float
  %552 = fmul float %.sroa.40.1, %551		; visa id: 562
  %553 = fadd float %548, %552		; visa id: 563
  %554 = zext i16 %536 to i32		; visa id: 564
  %555 = shl nuw i32 %554, 16, !spirv.Decorations !8781		; visa id: 565
  %556 = bitcast i32 %555 to float
  %557 = fmul float %.sroa.64136.1, %556		; visa id: 566
  %558 = fadd float %553, %557		; visa id: 567
  %559 = zext i16 %537 to i32		; visa id: 568
  %560 = shl nuw i32 %559, 16, !spirv.Decorations !8781		; visa id: 569
  %561 = bitcast i32 %560 to float
  %562 = fmul float %.sroa.88.1, %561		; visa id: 570
  %563 = fadd float %558, %562		; visa id: 571
  %564 = zext i16 %540 to i32		; visa id: 572
  %565 = shl nuw i32 %564, 16, !spirv.Decorations !8781		; visa id: 573
  %566 = bitcast i32 %565 to float
  %567 = fmul float %.sroa.112151.1, %566		; visa id: 574
  %568 = fadd float %563, %567		; visa id: 575
  %569 = zext i16 %541 to i32		; visa id: 576
  %570 = shl nuw i32 %569, 16, !spirv.Decorations !8781		; visa id: 577
  %571 = bitcast i32 %570 to float
  %572 = fmul float %.sroa.136.1, %571		; visa id: 578
  %573 = fadd float %568, %572		; visa id: 579
  %574 = zext i16 %542 to i32		; visa id: 580
  %575 = shl nuw i32 %574, 16, !spirv.Decorations !8781		; visa id: 581
  %576 = bitcast i32 %575 to float
  %577 = fmul float %.sroa.160.1, %576		; visa id: 582
  %578 = fadd float %573, %577		; visa id: 583
  %579 = zext i16 %543 to i32		; visa id: 584
  %580 = shl nuw i32 %579, 16, !spirv.Decorations !8781		; visa id: 585
  %581 = bitcast i32 %580 to float
  %582 = fmul float %.sroa.184.1, %581		; visa id: 586
  %583 = fadd float %578, %582		; visa id: 587
  %584 = and i32 %125, 255
  %585 = shl nuw nsw i32 %146, 4		; visa id: 588
  %586 = and i32 %585, 768		; visa id: 589
  %587 = or i32 %584, %586		; visa id: 590
  %588 = lshr i32 %161, 4		; visa id: 591
  %589 = and i32 %588, 15		; visa id: 592
  %590 = uitofp i32 %589 to float		; visa id: 593
  %591 = fadd float %590, 5.000000e-01		; visa id: 594
  %592 = fmul float %144, %591		; visa id: 595
  %593 = fmul float %592, 2.500000e-01		; visa id: 596
  %594 = shl nuw nsw i32 %587, 3, !spirv.Decorations !8791		; visa id: 597
  %595 = zext i32 %594 to i64		; visa id: 598
  %596 = add i64 %116, %595		; visa id: 599
  %597 = inttoptr i64 %596 to ptr addrspace(1)		; visa id: 600
  %598 = load <2 x i32>, ptr addrspace(1) %597, align 4		; visa id: 600
  %599 = extractelement <2 x i32> %598, i32 0		; visa id: 601
  %600 = extractelement <2 x i32> %598, i32 1		; visa id: 601
  %601 = bitcast float %593 to i32
  %602 = and i32 %601, 2147483647		; visa id: 601
  %603 = icmp ugt i32 %602, 2139095040
  %604 = fcmp oeq float %157, 0x7FF0000000000000		; visa id: 602
  %605 = fcmp une float %157, %157
  %606 = or i1 %605, %604		; visa id: 603
  %607 = or i1 %606, %603		; visa id: 605
  %608 = and i32 %599, 255		; visa id: 607
  br i1 %607, label %616, label %609, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 608

609:                                              ; preds = %525
; BB59 :
  %610 = and i32 %125, 256
  %611 = sub nsw i32 0, %608, !spirv.Decorations !8800
  %612 = icmp eq i32 %610, 0		; visa id: 610
  %613 = select i1 %612, i32 %608, i32 %611		; visa id: 612
  %614 = sitofp i32 %613 to float		; visa id: 613
  %615 = fmul float %593, %614		; visa id: 614
  br label %624, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 615

616:                                              ; preds = %525
; BB60 :
  %617 = uitofp i32 %608 to float		; visa id: 617
  %618 = fmul float %593, %617		; visa id: 618
  %619 = and i32 %125, 256
  %620 = icmp eq i32 %619, 0		; visa id: 619
  %621 = select i1 %620, i32 1, i32 -1		; visa id: 621
  %622 = sitofp i32 %621 to float		; visa id: 622
  %623 = fmul float %618, %622		; visa id: 623
  br label %624, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 624

624:                                              ; preds = %616, %609
; BB61 :
  %.sroa.0121.2 = phi float [ %623, %616 ], [ %615, %609 ]
  %625 = bitcast i32 %599 to <4 x i8>
  %626 = extractelement <4 x i8> %625, i32 1
  %627 = zext i8 %626 to i32		; visa id: 625
  br i1 %607, label %635, label %628, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 626

628:                                              ; preds = %624
; BB62 :
  %629 = and i32 %125, 512
  %630 = sub nsw i32 0, %627, !spirv.Decorations !8800
  %631 = icmp eq i32 %629, 0		; visa id: 628
  %632 = select i1 %631, i32 %627, i32 %630		; visa id: 630
  %633 = sitofp i32 %632 to float		; visa id: 631
  %634 = fmul float %593, %633		; visa id: 632
  br label %643, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 633

635:                                              ; preds = %624
; BB63 :
  %636 = uitofp i32 %627 to float		; visa id: 635
  %637 = fmul float %593, %636		; visa id: 636
  %638 = and i32 %125, 512
  %639 = icmp eq i32 %638, 0		; visa id: 637
  %640 = select i1 %639, i32 1, i32 -1		; visa id: 639
  %641 = sitofp i32 %640 to float		; visa id: 640
  %642 = fmul float %637, %641		; visa id: 641
  br label %643, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 642

643:                                              ; preds = %635, %628
; BB64 :
  %.sroa.40.2 = phi float [ %642, %635 ], [ %634, %628 ]
  %644 = extractelement <4 x i8> %625, i32 2
  %645 = zext i8 %644 to i32		; visa id: 643
  br i1 %607, label %653, label %646, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 644

646:                                              ; preds = %643
; BB65 :
  %647 = and i32 %125, 1024
  %648 = sub nsw i32 0, %645, !spirv.Decorations !8800
  %649 = icmp eq i32 %647, 0		; visa id: 646
  %650 = select i1 %649, i32 %645, i32 %648		; visa id: 648
  %651 = sitofp i32 %650 to float		; visa id: 649
  %652 = fmul float %593, %651		; visa id: 650
  br label %661, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 651

653:                                              ; preds = %643
; BB66 :
  %654 = uitofp i32 %645 to float		; visa id: 653
  %655 = fmul float %593, %654		; visa id: 654
  %656 = and i32 %125, 1024
  %657 = icmp eq i32 %656, 0		; visa id: 655
  %658 = select i1 %657, i32 1, i32 -1		; visa id: 657
  %659 = sitofp i32 %658 to float		; visa id: 658
  %660 = fmul float %655, %659		; visa id: 659
  br label %661, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 660

661:                                              ; preds = %653, %646
; BB67 :
  %.sroa.64136.2 = phi float [ %660, %653 ], [ %652, %646 ]
  %662 = lshr i32 %599, 24		; visa id: 661
  br i1 %607, label %670, label %663, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 662

663:                                              ; preds = %661
; BB68 :
  %664 = and i32 %125, 2048
  %665 = sub nsw i32 0, %662, !spirv.Decorations !8800
  %666 = icmp eq i32 %664, 0		; visa id: 664
  %667 = select i1 %666, i32 %662, i32 %665		; visa id: 666
  %668 = sitofp i32 %667 to float		; visa id: 667
  %669 = fmul float %593, %668		; visa id: 668
  br label %678, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 669

670:                                              ; preds = %661
; BB69 :
  %671 = uitofp i32 %662 to float		; visa id: 671
  %672 = fmul float %593, %671		; visa id: 672
  %673 = and i32 %125, 2048
  %674 = icmp eq i32 %673, 0		; visa id: 673
  %675 = select i1 %674, i32 1, i32 -1		; visa id: 675
  %676 = sitofp i32 %675 to float		; visa id: 676
  %677 = fmul float %672, %676		; visa id: 677
  br label %678, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 678

678:                                              ; preds = %670, %663
; BB70 :
  %.sroa.88.2 = phi float [ %677, %670 ], [ %669, %663 ]
  %679 = and i32 %600, 255		; visa id: 679
  br i1 %607, label %687, label %680, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 680

680:                                              ; preds = %678
; BB71 :
  %681 = and i32 %125, 4096
  %682 = sub nsw i32 0, %679, !spirv.Decorations !8800
  %683 = icmp eq i32 %681, 0		; visa id: 682
  %684 = select i1 %683, i32 %679, i32 %682		; visa id: 684
  %685 = sitofp i32 %684 to float		; visa id: 685
  %686 = fmul float %593, %685		; visa id: 686
  br label %695, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 687

687:                                              ; preds = %678
; BB72 :
  %688 = uitofp i32 %679 to float		; visa id: 689
  %689 = fmul float %593, %688		; visa id: 690
  %690 = and i32 %125, 4096
  %691 = icmp eq i32 %690, 0		; visa id: 691
  %692 = select i1 %691, i32 1, i32 -1		; visa id: 693
  %693 = sitofp i32 %692 to float		; visa id: 694
  %694 = fmul float %689, %693		; visa id: 695
  br label %695, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 696

695:                                              ; preds = %687, %680
; BB73 :
  %.sroa.112151.2 = phi float [ %694, %687 ], [ %686, %680 ]
  %696 = bitcast i32 %600 to <4 x i8>
  %697 = extractelement <4 x i8> %696, i32 1
  %698 = zext i8 %697 to i32		; visa id: 697
  br i1 %607, label %706, label %699, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 698

699:                                              ; preds = %695
; BB74 :
  %700 = and i32 %125, 8192
  %701 = sub nsw i32 0, %698, !spirv.Decorations !8800
  %702 = icmp eq i32 %700, 0		; visa id: 700
  %703 = select i1 %702, i32 %698, i32 %701		; visa id: 702
  %704 = sitofp i32 %703 to float		; visa id: 703
  %705 = fmul float %593, %704		; visa id: 704
  br label %714, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 705

706:                                              ; preds = %695
; BB75 :
  %707 = uitofp i32 %698 to float		; visa id: 707
  %708 = fmul float %593, %707		; visa id: 708
  %709 = and i32 %125, 8192
  %710 = icmp eq i32 %709, 0		; visa id: 709
  %711 = select i1 %710, i32 1, i32 -1		; visa id: 711
  %712 = sitofp i32 %711 to float		; visa id: 712
  %713 = fmul float %708, %712		; visa id: 713
  br label %714, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 714

714:                                              ; preds = %706, %699
; BB76 :
  %.sroa.136.2 = phi float [ %713, %706 ], [ %705, %699 ]
  %715 = extractelement <4 x i8> %696, i32 2
  %716 = zext i8 %715 to i32		; visa id: 715
  br i1 %607, label %724, label %717, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 716

717:                                              ; preds = %714
; BB77 :
  %718 = and i32 %125, 16384
  %719 = sub nsw i32 0, %716, !spirv.Decorations !8800
  %720 = icmp eq i32 %718, 0		; visa id: 718
  %721 = select i1 %720, i32 %716, i32 %719		; visa id: 720
  %722 = sitofp i32 %721 to float		; visa id: 721
  %723 = fmul float %593, %722		; visa id: 722
  br label %732, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 723

724:                                              ; preds = %714
; BB78 :
  %725 = uitofp i32 %716 to float		; visa id: 725
  %726 = fmul float %593, %725		; visa id: 726
  %727 = and i32 %125, 16384
  %728 = icmp eq i32 %727, 0		; visa id: 727
  %729 = select i1 %728, i32 1, i32 -1		; visa id: 729
  %730 = sitofp i32 %729 to float		; visa id: 730
  %731 = fmul float %726, %730		; visa id: 731
  br label %732, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 732

732:                                              ; preds = %724, %717
; BB79 :
  %.sroa.160.2 = phi float [ %731, %724 ], [ %723, %717 ]
  %733 = lshr i32 %600, 24		; visa id: 733
  br i1 %607, label %741, label %734, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 734

734:                                              ; preds = %732
; BB80 :
  %735 = and i32 %125, 32768
  %736 = sub nsw i32 0, %733, !spirv.Decorations !8800
  %737 = icmp eq i32 %735, 0		; visa id: 736
  %738 = select i1 %737, i32 %733, i32 %736		; visa id: 738
  %739 = sitofp i32 %738 to float		; visa id: 739
  %740 = fmul float %593, %739		; visa id: 740
  br label %749, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 741

741:                                              ; preds = %732
; BB81 :
  %742 = uitofp i32 %733 to float		; visa id: 743
  %743 = fmul float %593, %742		; visa id: 744
  %744 = and i32 %125, 32768
  %745 = icmp eq i32 %744, 0		; visa id: 745
  %746 = select i1 %745, i32 1, i32 -1		; visa id: 747
  %747 = sitofp i32 %746 to float		; visa id: 748
  %748 = fmul float %743, %747		; visa id: 749
  br label %749, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 750

749:                                              ; preds = %741, %734
; BB82 :
  %.sroa.184.2 = phi float [ %748, %741 ], [ %740, %734 ]
  %750 = or i32 %315, 32		; visa id: 751
  %751 = zext i32 %750 to i64		; visa id: 752
  %752 = add i64 %751, %const_reg_qword2		; visa id: 753
  %IntToPtr2283 = inttoptr i64 %752 to ptr addrspace(1)		; visa id: 754
  %vCastload284 = load i32, ptr addrspace(1) %IntToPtr2283, align 2		; visa id: 754
  %753 = add i64 %752, 4
  %IntToPtr2285 = inttoptr i64 %753 to ptr addrspace(1)
  %vCastload286 = load i32, ptr addrspace(1) %IntToPtr2285, align 2		; visa id: 755
  %754 = add i64 %752, 8
  %IntToPtr2287 = inttoptr i64 %754 to ptr addrspace(1)
  %vCastload288 = load i32, ptr addrspace(1) %IntToPtr2287, align 2		; visa id: 756
  %755 = add i64 %752, 12
  %IntToPtr2289 = inttoptr i64 %755 to ptr addrspace(1)
  %vCastload290 = load i32, ptr addrspace(1) %IntToPtr2289, align 2		; visa id: 757
  %756 = bitcast i32 %vCastload284 to <2 x i16>		; visa id: 758
  %757 = bitcast i32 %vCastload286 to <2 x i16>		; visa id: 760
  %758 = extractelement <2 x i16> %756, i32 0		; visa id: 762
  %759 = extractelement <2 x i16> %756, i32 1		; visa id: 762
  %760 = extractelement <2 x i16> %757, i32 0		; visa id: 762
  %761 = extractelement <2 x i16> %757, i32 1		; visa id: 762
  %762 = bitcast i32 %vCastload288 to <2 x i16>		; visa id: 762
  %763 = bitcast i32 %vCastload290 to <2 x i16>		; visa id: 764
  %764 = extractelement <2 x i16> %762, i32 0		; visa id: 766
  %765 = extractelement <2 x i16> %762, i32 1		; visa id: 766
  %766 = extractelement <2 x i16> %763, i32 0		; visa id: 766
  %767 = extractelement <2 x i16> %763, i32 1		; visa id: 766
  %768 = zext i16 %758 to i32		; visa id: 766
  %769 = shl nuw i32 %768, 16, !spirv.Decorations !8781		; visa id: 767
  %770 = bitcast i32 %769 to float
  %771 = fmul float %.sroa.0121.2, %770		; visa id: 768
  %772 = fadd float %.sroa.13.0, %771		; visa id: 769
  %773 = zext i16 %759 to i32		; visa id: 770
  %774 = shl nuw i32 %773, 16, !spirv.Decorations !8781		; visa id: 771
  %775 = bitcast i32 %774 to float
  %776 = fmul float %.sroa.40.2, %775		; visa id: 772
  %777 = fadd float %772, %776		; visa id: 773
  %778 = zext i16 %760 to i32		; visa id: 774
  %779 = shl nuw i32 %778, 16, !spirv.Decorations !8781		; visa id: 775
  %780 = bitcast i32 %779 to float
  %781 = fmul float %.sroa.64136.2, %780		; visa id: 776
  %782 = fadd float %777, %781		; visa id: 777
  %783 = zext i16 %761 to i32		; visa id: 778
  %784 = shl nuw i32 %783, 16, !spirv.Decorations !8781		; visa id: 779
  %785 = bitcast i32 %784 to float
  %786 = fmul float %.sroa.88.2, %785		; visa id: 780
  %787 = fadd float %782, %786		; visa id: 781
  %788 = zext i16 %764 to i32		; visa id: 782
  %789 = shl nuw i32 %788, 16, !spirv.Decorations !8781		; visa id: 783
  %790 = bitcast i32 %789 to float
  %791 = fmul float %.sroa.112151.2, %790		; visa id: 784
  %792 = fadd float %787, %791		; visa id: 785
  %793 = zext i16 %765 to i32		; visa id: 786
  %794 = shl nuw i32 %793, 16, !spirv.Decorations !8781		; visa id: 787
  %795 = bitcast i32 %794 to float
  %796 = fmul float %.sroa.136.2, %795		; visa id: 788
  %797 = fadd float %792, %796		; visa id: 789
  %798 = zext i16 %766 to i32		; visa id: 790
  %799 = shl nuw i32 %798, 16, !spirv.Decorations !8781		; visa id: 791
  %800 = bitcast i32 %799 to float
  %801 = fmul float %.sroa.160.2, %800		; visa id: 792
  %802 = fadd float %797, %801		; visa id: 793
  %803 = zext i16 %767 to i32		; visa id: 794
  %804 = shl nuw i32 %803, 16, !spirv.Decorations !8781		; visa id: 795
  %805 = bitcast i32 %804 to float
  %806 = fmul float %.sroa.184.2, %805		; visa id: 796
  %807 = fadd float %802, %806		; visa id: 797
  %808 = bitcast i32 %125 to <4 x i8>
  %809 = extractelement <4 x i8> %808, i32 2
  %810 = shl nuw nsw i32 %146, 2		; visa id: 798
  %811 = and i32 %810, 768
  %812 = zext i8 %809 to i32		; visa id: 799
  %813 = or i32 %812, %811		; visa id: 800
  %814 = shl nuw nsw i32 %813, 3, !spirv.Decorations !8791		; visa id: 801
  %815 = zext i32 %814 to i64		; visa id: 802
  %816 = add i64 %116, %815		; visa id: 803
  %817 = inttoptr i64 %816 to ptr addrspace(1)		; visa id: 804
  %818 = load <2 x i32>, ptr addrspace(1) %817, align 4		; visa id: 804
  %819 = extractelement <2 x i32> %818, i32 0		; visa id: 805
  %820 = extractelement <2 x i32> %818, i32 1		; visa id: 805
  %821 = and i32 %819, 255		; visa id: 805
  br i1 %607, label %829, label %822, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 806

822:                                              ; preds = %749
; BB83 :
  %823 = and i32 %125, 16777216
  %824 = sub nsw i32 0, %821, !spirv.Decorations !8800
  %825 = icmp eq i32 %823, 0		; visa id: 808
  %826 = select i1 %825, i32 %821, i32 %824		; visa id: 810
  %827 = sitofp i32 %826 to float		; visa id: 811
  %828 = fmul float %593, %827		; visa id: 812
  br label %837, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 813

829:                                              ; preds = %749
; BB84 :
  %830 = uitofp i32 %821 to float		; visa id: 815
  %831 = fmul float %593, %830		; visa id: 816
  %832 = and i32 %125, 16777216
  %833 = icmp eq i32 %832, 0		; visa id: 817
  %834 = select i1 %833, i32 1, i32 -1		; visa id: 819
  %835 = sitofp i32 %834 to float		; visa id: 820
  %836 = fmul float %831, %835		; visa id: 821
  br label %837, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 822

837:                                              ; preds = %829, %822
; BB85 :
  %.sroa.0121.3 = phi float [ %836, %829 ], [ %828, %822 ]
  %838 = bitcast i32 %819 to <4 x i8>
  %839 = extractelement <4 x i8> %838, i32 1
  %840 = zext i8 %839 to i32		; visa id: 823
  br i1 %607, label %848, label %841, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 824

841:                                              ; preds = %837
; BB86 :
  %842 = and i32 %125, 33554432
  %843 = sub nsw i32 0, %840, !spirv.Decorations !8800
  %844 = icmp eq i32 %842, 0		; visa id: 826
  %845 = select i1 %844, i32 %840, i32 %843		; visa id: 828
  %846 = sitofp i32 %845 to float		; visa id: 829
  %847 = fmul float %593, %846		; visa id: 830
  br label %856, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 831

848:                                              ; preds = %837
; BB87 :
  %849 = uitofp i32 %840 to float		; visa id: 833
  %850 = fmul float %593, %849		; visa id: 834
  %851 = and i32 %125, 33554432
  %852 = icmp eq i32 %851, 0		; visa id: 835
  %853 = select i1 %852, i32 1, i32 -1		; visa id: 837
  %854 = sitofp i32 %853 to float		; visa id: 838
  %855 = fmul float %850, %854		; visa id: 839
  br label %856, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 840

856:                                              ; preds = %848, %841
; BB88 :
  %.sroa.40.3 = phi float [ %855, %848 ], [ %847, %841 ]
  %857 = extractelement <4 x i8> %838, i32 2
  %858 = zext i8 %857 to i32		; visa id: 841
  br i1 %607, label %866, label %859, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 842

859:                                              ; preds = %856
; BB89 :
  %860 = and i32 %125, 67108864
  %861 = sub nsw i32 0, %858, !spirv.Decorations !8800
  %862 = icmp eq i32 %860, 0		; visa id: 844
  %863 = select i1 %862, i32 %858, i32 %861		; visa id: 846
  %864 = sitofp i32 %863 to float		; visa id: 847
  %865 = fmul float %593, %864		; visa id: 848
  br label %874, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 849

866:                                              ; preds = %856
; BB90 :
  %867 = uitofp i32 %858 to float		; visa id: 851
  %868 = fmul float %593, %867		; visa id: 852
  %869 = and i32 %125, 67108864
  %870 = icmp eq i32 %869, 0		; visa id: 853
  %871 = select i1 %870, i32 1, i32 -1		; visa id: 855
  %872 = sitofp i32 %871 to float		; visa id: 856
  %873 = fmul float %868, %872		; visa id: 857
  br label %874, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 858

874:                                              ; preds = %866, %859
; BB91 :
  %.sroa.64136.3 = phi float [ %873, %866 ], [ %865, %859 ]
  %875 = lshr i32 %819, 24		; visa id: 859
  br i1 %607, label %883, label %876, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 860

876:                                              ; preds = %874
; BB92 :
  %877 = and i32 %125, 134217728
  %878 = sub nsw i32 0, %875, !spirv.Decorations !8800
  %879 = icmp eq i32 %877, 0		; visa id: 862
  %880 = select i1 %879, i32 %875, i32 %878		; visa id: 864
  %881 = sitofp i32 %880 to float		; visa id: 865
  %882 = fmul float %593, %881		; visa id: 866
  br label %891, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 867

883:                                              ; preds = %874
; BB93 :
  %884 = uitofp i32 %875 to float		; visa id: 869
  %885 = fmul float %593, %884		; visa id: 870
  %886 = and i32 %125, 134217728
  %887 = icmp eq i32 %886, 0		; visa id: 871
  %888 = select i1 %887, i32 1, i32 -1		; visa id: 873
  %889 = sitofp i32 %888 to float		; visa id: 874
  %890 = fmul float %885, %889		; visa id: 875
  br label %891, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 876

891:                                              ; preds = %883, %876
; BB94 :
  %.sroa.88.3 = phi float [ %890, %883 ], [ %882, %876 ]
  %892 = and i32 %820, 255		; visa id: 877
  br i1 %607, label %900, label %893, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 878

893:                                              ; preds = %891
; BB95 :
  %894 = and i32 %125, 268435456
  %895 = sub nsw i32 0, %892, !spirv.Decorations !8800
  %896 = icmp eq i32 %894, 0		; visa id: 880
  %897 = select i1 %896, i32 %892, i32 %895		; visa id: 882
  %898 = sitofp i32 %897 to float		; visa id: 883
  %899 = fmul float %593, %898		; visa id: 884
  br label %908, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 885

900:                                              ; preds = %891
; BB96 :
  %901 = uitofp i32 %892 to float		; visa id: 887
  %902 = fmul float %593, %901		; visa id: 888
  %903 = and i32 %125, 268435456
  %904 = icmp eq i32 %903, 0		; visa id: 889
  %905 = select i1 %904, i32 1, i32 -1		; visa id: 891
  %906 = sitofp i32 %905 to float		; visa id: 892
  %907 = fmul float %902, %906		; visa id: 893
  br label %908, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 894

908:                                              ; preds = %900, %893
; BB97 :
  %.sroa.112151.3 = phi float [ %907, %900 ], [ %899, %893 ]
  %909 = bitcast i32 %820 to <4 x i8>
  %910 = extractelement <4 x i8> %909, i32 1
  %911 = zext i8 %910 to i32		; visa id: 895
  br i1 %607, label %919, label %912, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 896

912:                                              ; preds = %908
; BB98 :
  %913 = and i32 %125, 536870912
  %914 = sub nsw i32 0, %911, !spirv.Decorations !8800
  %915 = icmp eq i32 %913, 0		; visa id: 898
  %916 = select i1 %915, i32 %911, i32 %914		; visa id: 900
  %917 = sitofp i32 %916 to float		; visa id: 901
  %918 = fmul float %593, %917		; visa id: 902
  br label %927, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 903

919:                                              ; preds = %908
; BB99 :
  %920 = uitofp i32 %911 to float		; visa id: 905
  %921 = fmul float %593, %920		; visa id: 906
  %922 = and i32 %125, 536870912
  %923 = icmp eq i32 %922, 0		; visa id: 907
  %924 = select i1 %923, i32 1, i32 -1		; visa id: 909
  %925 = sitofp i32 %924 to float		; visa id: 910
  %926 = fmul float %921, %925		; visa id: 911
  br label %927, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 912

927:                                              ; preds = %919, %912
; BB100 :
  %.sroa.136.3 = phi float [ %926, %919 ], [ %918, %912 ]
  %928 = extractelement <4 x i8> %909, i32 2
  %929 = zext i8 %928 to i32		; visa id: 913
  br i1 %607, label %937, label %930, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 914

930:                                              ; preds = %927
; BB101 :
  %931 = and i32 %125, 1073741824
  %932 = sub nsw i32 0, %929, !spirv.Decorations !8800
  %933 = icmp eq i32 %931, 0		; visa id: 916
  %934 = select i1 %933, i32 %929, i32 %932		; visa id: 918
  %935 = sitofp i32 %934 to float		; visa id: 919
  %936 = fmul float %593, %935		; visa id: 920
  br label %945, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 921

937:                                              ; preds = %927
; BB102 :
  %938 = uitofp i32 %929 to float		; visa id: 923
  %939 = fmul float %593, %938		; visa id: 924
  %940 = and i32 %125, 1073741824
  %941 = icmp eq i32 %940, 0		; visa id: 925
  %942 = select i1 %941, i32 1, i32 -1		; visa id: 927
  %943 = sitofp i32 %942 to float		; visa id: 928
  %944 = fmul float %939, %943		; visa id: 929
  br label %945, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 930

945:                                              ; preds = %937, %930
; BB103 :
  %.sroa.160.3 = phi float [ %944, %937 ], [ %936, %930 ]
  %946 = lshr i32 %820, 24		; visa id: 931
  br i1 %607, label %953, label %947, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 932

947:                                              ; preds = %945
; BB104 :
  %948 = sub nsw i32 0, %946, !spirv.Decorations !8800
  %949 = icmp slt i32 %125, 0		; visa id: 934
  %950 = select i1 %949, i32 %948, i32 %946		; visa id: 935
  %951 = sitofp i32 %950 to float		; visa id: 936
  %952 = fmul float %593, %951		; visa id: 937
  br label %960, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 938

953:                                              ; preds = %945
; BB105 :
  %954 = uitofp i32 %946 to float		; visa id: 940
  %955 = fmul float %593, %954		; visa id: 941
  %956 = icmp sgt i32 %125, -1		; visa id: 942
  %957 = select i1 %956, i32 1, i32 -1		; visa id: 943
  %958 = sitofp i32 %957 to float		; visa id: 944
  %959 = fmul float %955, %958		; visa id: 945
  br label %960, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 946

960:                                              ; preds = %953, %947
; BB106 :
  %.sroa.184.3 = phi float [ %959, %953 ], [ %952, %947 ]
  %961 = or i32 %315, 48		; visa id: 947
  %962 = zext i32 %961 to i64		; visa id: 948
  %963 = add i64 %962, %const_reg_qword2		; visa id: 949
  %IntToPtr2291 = inttoptr i64 %963 to ptr addrspace(1)		; visa id: 950
  %vCastload292 = load i32, ptr addrspace(1) %IntToPtr2291, align 2		; visa id: 950
  %964 = add i64 %963, 4
  %IntToPtr2293 = inttoptr i64 %964 to ptr addrspace(1)
  %vCastload294 = load i32, ptr addrspace(1) %IntToPtr2293, align 2		; visa id: 951
  %965 = add i64 %963, 8
  %IntToPtr2295 = inttoptr i64 %965 to ptr addrspace(1)
  %vCastload296 = load i32, ptr addrspace(1) %IntToPtr2295, align 2		; visa id: 952
  %966 = add i64 %963, 12
  %IntToPtr2297 = inttoptr i64 %966 to ptr addrspace(1)
  %vCastload298 = load i32, ptr addrspace(1) %IntToPtr2297, align 2		; visa id: 953
  %967 = bitcast i32 %vCastload292 to <2 x i16>		; visa id: 954
  %968 = bitcast i32 %vCastload294 to <2 x i16>		; visa id: 956
  %969 = extractelement <2 x i16> %967, i32 0		; visa id: 958
  %970 = extractelement <2 x i16> %967, i32 1		; visa id: 958
  %971 = extractelement <2 x i16> %968, i32 0		; visa id: 958
  %972 = extractelement <2 x i16> %968, i32 1		; visa id: 958
  %973 = bitcast i32 %vCastload296 to <2 x i16>		; visa id: 958
  %974 = bitcast i32 %vCastload298 to <2 x i16>		; visa id: 960
  %975 = extractelement <2 x i16> %973, i32 0		; visa id: 962
  %976 = extractelement <2 x i16> %973, i32 1		; visa id: 962
  %977 = extractelement <2 x i16> %974, i32 0		; visa id: 962
  %978 = extractelement <2 x i16> %974, i32 1		; visa id: 962
  %979 = zext i16 %969 to i32		; visa id: 962
  %980 = shl nuw i32 %979, 16, !spirv.Decorations !8781		; visa id: 963
  %981 = bitcast i32 %980 to float
  %982 = fmul float %.sroa.0121.3, %981		; visa id: 964
  %983 = fadd float %.sroa.18.0, %982		; visa id: 965
  %984 = zext i16 %970 to i32		; visa id: 966
  %985 = shl nuw i32 %984, 16, !spirv.Decorations !8781		; visa id: 967
  %986 = bitcast i32 %985 to float
  %987 = fmul float %.sroa.40.3, %986		; visa id: 968
  %988 = fadd float %983, %987		; visa id: 969
  %989 = zext i16 %971 to i32		; visa id: 970
  %990 = shl nuw i32 %989, 16, !spirv.Decorations !8781		; visa id: 971
  %991 = bitcast i32 %990 to float
  %992 = fmul float %.sroa.64136.3, %991		; visa id: 972
  %993 = fadd float %988, %992		; visa id: 973
  %994 = zext i16 %972 to i32		; visa id: 974
  %995 = shl nuw i32 %994, 16, !spirv.Decorations !8781		; visa id: 975
  %996 = bitcast i32 %995 to float
  %997 = fmul float %.sroa.88.3, %996		; visa id: 976
  %998 = fadd float %993, %997		; visa id: 977
  %999 = zext i16 %975 to i32		; visa id: 978
  %1000 = shl nuw i32 %999, 16, !spirv.Decorations !8781		; visa id: 979
  %1001 = bitcast i32 %1000 to float
  %1002 = fmul float %.sroa.112151.3, %1001		; visa id: 980
  %1003 = fadd float %998, %1002		; visa id: 981
  %1004 = zext i16 %976 to i32		; visa id: 982
  %1005 = shl nuw i32 %1004, 16, !spirv.Decorations !8781		; visa id: 983
  %1006 = bitcast i32 %1005 to float
  %1007 = fmul float %.sroa.136.3, %1006		; visa id: 984
  %1008 = fadd float %1003, %1007		; visa id: 985
  %1009 = zext i16 %977 to i32		; visa id: 986
  %1010 = shl nuw i32 %1009, 16, !spirv.Decorations !8781		; visa id: 987
  %1011 = bitcast i32 %1010 to float
  %1012 = fmul float %.sroa.160.3, %1011		; visa id: 988
  %1013 = fadd float %1008, %1012		; visa id: 989
  %1014 = zext i16 %978 to i32		; visa id: 990
  %1015 = shl nuw i32 %1014, 16, !spirv.Decorations !8781		; visa id: 991
  %1016 = bitcast i32 %1015 to float
  %1017 = fmul float %.sroa.184.3, %1016		; visa id: 992
  %1018 = fadd float %1013, %1017		; visa id: 993
  %1019 = lshr i32 %161, 8		; visa id: 994
  %1020 = and i32 %126, 255
  %1021 = and i32 %146, 768		; visa id: 995
  %1022 = or i32 %1020, %1021		; visa id: 996
  %1023 = and i32 %1019, 15		; visa id: 997
  %1024 = uitofp i32 %1023 to float		; visa id: 998
  %1025 = fadd float %1024, 5.000000e-01		; visa id: 999
  %1026 = fmul float %144, %1025		; visa id: 1000
  %1027 = fmul float %1026, 2.500000e-01		; visa id: 1001
  %1028 = shl nuw nsw i32 %1022, 3, !spirv.Decorations !8791		; visa id: 1002
  %1029 = zext i32 %1028 to i64		; visa id: 1003
  %1030 = add i64 %116, %1029		; visa id: 1004
  %1031 = inttoptr i64 %1030 to ptr addrspace(1)		; visa id: 1005
  %1032 = load <2 x i32>, ptr addrspace(1) %1031, align 4		; visa id: 1005
  %1033 = extractelement <2 x i32> %1032, i32 0		; visa id: 1006
  %1034 = extractelement <2 x i32> %1032, i32 1		; visa id: 1006
  %1035 = bitcast float %1027 to i32
  %1036 = and i32 %1035, 2147483647		; visa id: 1006
  %1037 = icmp ugt i32 %1036, 2139095040
  %1038 = fcmp oeq float %157, 0x7FF0000000000000		; visa id: 1007
  %1039 = fcmp une float %157, %157
  %1040 = or i1 %1039, %1038		; visa id: 1008
  %1041 = or i1 %1040, %1037		; visa id: 1010
  %1042 = and i32 %1033, 255		; visa id: 1012
  br i1 %1041, label %1050, label %1043, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1013

1043:                                             ; preds = %960
; BB107 :
  %1044 = and i32 %126, 256
  %1045 = sub nsw i32 0, %1042, !spirv.Decorations !8800
  %1046 = icmp eq i32 %1044, 0		; visa id: 1015
  %1047 = select i1 %1046, i32 %1042, i32 %1045		; visa id: 1017
  %1048 = sitofp i32 %1047 to float		; visa id: 1018
  %1049 = fmul float %1027, %1048		; visa id: 1019
  br label %1058, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1020

1050:                                             ; preds = %960
; BB108 :
  %1051 = uitofp i32 %1042 to float		; visa id: 1022
  %1052 = fmul float %1027, %1051		; visa id: 1023
  %1053 = and i32 %126, 256
  %1054 = icmp eq i32 %1053, 0		; visa id: 1024
  %1055 = select i1 %1054, i32 1, i32 -1		; visa id: 1026
  %1056 = sitofp i32 %1055 to float		; visa id: 1027
  %1057 = fmul float %1052, %1056		; visa id: 1028
  br label %1058, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1029

1058:                                             ; preds = %1050, %1043
; BB109 :
  %.sroa.0121.4 = phi float [ %1057, %1050 ], [ %1049, %1043 ]
  %1059 = bitcast i32 %1033 to <4 x i8>
  %1060 = extractelement <4 x i8> %1059, i32 1
  %1061 = zext i8 %1060 to i32		; visa id: 1030
  br i1 %1041, label %1069, label %1062, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1031

1062:                                             ; preds = %1058
; BB110 :
  %1063 = and i32 %126, 512
  %1064 = sub nsw i32 0, %1061, !spirv.Decorations !8800
  %1065 = icmp eq i32 %1063, 0		; visa id: 1033
  %1066 = select i1 %1065, i32 %1061, i32 %1064		; visa id: 1035
  %1067 = sitofp i32 %1066 to float		; visa id: 1036
  %1068 = fmul float %1027, %1067		; visa id: 1037
  br label %1077, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1038

1069:                                             ; preds = %1058
; BB111 :
  %1070 = uitofp i32 %1061 to float		; visa id: 1040
  %1071 = fmul float %1027, %1070		; visa id: 1041
  %1072 = and i32 %126, 512
  %1073 = icmp eq i32 %1072, 0		; visa id: 1042
  %1074 = select i1 %1073, i32 1, i32 -1		; visa id: 1044
  %1075 = sitofp i32 %1074 to float		; visa id: 1045
  %1076 = fmul float %1071, %1075		; visa id: 1046
  br label %1077, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1047

1077:                                             ; preds = %1069, %1062
; BB112 :
  %.sroa.40.4 = phi float [ %1076, %1069 ], [ %1068, %1062 ]
  %1078 = extractelement <4 x i8> %1059, i32 2
  %1079 = zext i8 %1078 to i32		; visa id: 1048
  br i1 %1041, label %1087, label %1080, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1049

1080:                                             ; preds = %1077
; BB113 :
  %1081 = and i32 %126, 1024
  %1082 = sub nsw i32 0, %1079, !spirv.Decorations !8800
  %1083 = icmp eq i32 %1081, 0		; visa id: 1051
  %1084 = select i1 %1083, i32 %1079, i32 %1082		; visa id: 1053
  %1085 = sitofp i32 %1084 to float		; visa id: 1054
  %1086 = fmul float %1027, %1085		; visa id: 1055
  br label %1095, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1056

1087:                                             ; preds = %1077
; BB114 :
  %1088 = uitofp i32 %1079 to float		; visa id: 1058
  %1089 = fmul float %1027, %1088		; visa id: 1059
  %1090 = and i32 %126, 1024
  %1091 = icmp eq i32 %1090, 0		; visa id: 1060
  %1092 = select i1 %1091, i32 1, i32 -1		; visa id: 1062
  %1093 = sitofp i32 %1092 to float		; visa id: 1063
  %1094 = fmul float %1089, %1093		; visa id: 1064
  br label %1095, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1065

1095:                                             ; preds = %1087, %1080
; BB115 :
  %.sroa.64136.4 = phi float [ %1094, %1087 ], [ %1086, %1080 ]
  %1096 = lshr i32 %1033, 24		; visa id: 1066
  br i1 %1041, label %1104, label %1097, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1067

1097:                                             ; preds = %1095
; BB116 :
  %1098 = and i32 %126, 2048
  %1099 = sub nsw i32 0, %1096, !spirv.Decorations !8800
  %1100 = icmp eq i32 %1098, 0		; visa id: 1069
  %1101 = select i1 %1100, i32 %1096, i32 %1099		; visa id: 1071
  %1102 = sitofp i32 %1101 to float		; visa id: 1072
  %1103 = fmul float %1027, %1102		; visa id: 1073
  br label %1112, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1074

1104:                                             ; preds = %1095
; BB117 :
  %1105 = uitofp i32 %1096 to float		; visa id: 1076
  %1106 = fmul float %1027, %1105		; visa id: 1077
  %1107 = and i32 %126, 2048
  %1108 = icmp eq i32 %1107, 0		; visa id: 1078
  %1109 = select i1 %1108, i32 1, i32 -1		; visa id: 1080
  %1110 = sitofp i32 %1109 to float		; visa id: 1081
  %1111 = fmul float %1106, %1110		; visa id: 1082
  br label %1112, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1083

1112:                                             ; preds = %1104, %1097
; BB118 :
  %.sroa.88.4 = phi float [ %1111, %1104 ], [ %1103, %1097 ]
  %1113 = and i32 %1034, 255		; visa id: 1084
  br i1 %1041, label %1121, label %1114, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1085

1114:                                             ; preds = %1112
; BB119 :
  %1115 = and i32 %126, 4096
  %1116 = sub nsw i32 0, %1113, !spirv.Decorations !8800
  %1117 = icmp eq i32 %1115, 0		; visa id: 1087
  %1118 = select i1 %1117, i32 %1113, i32 %1116		; visa id: 1089
  %1119 = sitofp i32 %1118 to float		; visa id: 1090
  %1120 = fmul float %1027, %1119		; visa id: 1091
  br label %1129, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1092

1121:                                             ; preds = %1112
; BB120 :
  %1122 = uitofp i32 %1113 to float		; visa id: 1094
  %1123 = fmul float %1027, %1122		; visa id: 1095
  %1124 = and i32 %126, 4096
  %1125 = icmp eq i32 %1124, 0		; visa id: 1096
  %1126 = select i1 %1125, i32 1, i32 -1		; visa id: 1098
  %1127 = sitofp i32 %1126 to float		; visa id: 1099
  %1128 = fmul float %1123, %1127		; visa id: 1100
  br label %1129, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1101

1129:                                             ; preds = %1121, %1114
; BB121 :
  %.sroa.112151.4 = phi float [ %1128, %1121 ], [ %1120, %1114 ]
  %1130 = bitcast i32 %1034 to <4 x i8>
  %1131 = extractelement <4 x i8> %1130, i32 1
  %1132 = zext i8 %1131 to i32		; visa id: 1102
  br i1 %1041, label %1140, label %1133, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1103

1133:                                             ; preds = %1129
; BB122 :
  %1134 = and i32 %126, 8192
  %1135 = sub nsw i32 0, %1132, !spirv.Decorations !8800
  %1136 = icmp eq i32 %1134, 0		; visa id: 1105
  %1137 = select i1 %1136, i32 %1132, i32 %1135		; visa id: 1107
  %1138 = sitofp i32 %1137 to float		; visa id: 1108
  %1139 = fmul float %1027, %1138		; visa id: 1109
  br label %1148, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1110

1140:                                             ; preds = %1129
; BB123 :
  %1141 = uitofp i32 %1132 to float		; visa id: 1112
  %1142 = fmul float %1027, %1141		; visa id: 1113
  %1143 = and i32 %126, 8192
  %1144 = icmp eq i32 %1143, 0		; visa id: 1114
  %1145 = select i1 %1144, i32 1, i32 -1		; visa id: 1116
  %1146 = sitofp i32 %1145 to float		; visa id: 1117
  %1147 = fmul float %1142, %1146		; visa id: 1118
  br label %1148, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1119

1148:                                             ; preds = %1140, %1133
; BB124 :
  %.sroa.136.4 = phi float [ %1147, %1140 ], [ %1139, %1133 ]
  %1149 = extractelement <4 x i8> %1130, i32 2
  %1150 = zext i8 %1149 to i32		; visa id: 1120
  br i1 %1041, label %1158, label %1151, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1121

1151:                                             ; preds = %1148
; BB125 :
  %1152 = and i32 %126, 16384
  %1153 = sub nsw i32 0, %1150, !spirv.Decorations !8800
  %1154 = icmp eq i32 %1152, 0		; visa id: 1123
  %1155 = select i1 %1154, i32 %1150, i32 %1153		; visa id: 1125
  %1156 = sitofp i32 %1155 to float		; visa id: 1126
  %1157 = fmul float %1027, %1156		; visa id: 1127
  br label %1166, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1128

1158:                                             ; preds = %1148
; BB126 :
  %1159 = uitofp i32 %1150 to float		; visa id: 1130
  %1160 = fmul float %1027, %1159		; visa id: 1131
  %1161 = and i32 %126, 16384
  %1162 = icmp eq i32 %1161, 0		; visa id: 1132
  %1163 = select i1 %1162, i32 1, i32 -1		; visa id: 1134
  %1164 = sitofp i32 %1163 to float		; visa id: 1135
  %1165 = fmul float %1160, %1164		; visa id: 1136
  br label %1166, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1137

1166:                                             ; preds = %1158, %1151
; BB127 :
  %.sroa.160.4 = phi float [ %1165, %1158 ], [ %1157, %1151 ]
  %1167 = lshr i32 %1034, 24		; visa id: 1138
  br i1 %1041, label %1175, label %1168, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1139

1168:                                             ; preds = %1166
; BB128 :
  %1169 = and i32 %126, 32768
  %1170 = sub nsw i32 0, %1167, !spirv.Decorations !8800
  %1171 = icmp eq i32 %1169, 0		; visa id: 1141
  %1172 = select i1 %1171, i32 %1167, i32 %1170		; visa id: 1143
  %1173 = sitofp i32 %1172 to float		; visa id: 1144
  %1174 = fmul float %1027, %1173		; visa id: 1145
  br label %1183, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1146

1175:                                             ; preds = %1166
; BB129 :
  %1176 = uitofp i32 %1167 to float		; visa id: 1148
  %1177 = fmul float %1027, %1176		; visa id: 1149
  %1178 = and i32 %126, 32768
  %1179 = icmp eq i32 %1178, 0		; visa id: 1150
  %1180 = select i1 %1179, i32 1, i32 -1		; visa id: 1152
  %1181 = sitofp i32 %1180 to float		; visa id: 1153
  %1182 = fmul float %1177, %1181		; visa id: 1154
  br label %1183, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1155

1183:                                             ; preds = %1175, %1168
; BB130 :
  %.sroa.184.4 = phi float [ %1182, %1175 ], [ %1174, %1168 ]
  %1184 = or i32 %315, 64		; visa id: 1156
  %1185 = zext i32 %1184 to i64		; visa id: 1157
  %1186 = add i64 %1185, %const_reg_qword2		; visa id: 1158
  %IntToPtr2299 = inttoptr i64 %1186 to ptr addrspace(1)		; visa id: 1159
  %vCastload300 = load i32, ptr addrspace(1) %IntToPtr2299, align 2		; visa id: 1159
  %1187 = add i64 %1186, 4
  %IntToPtr2301 = inttoptr i64 %1187 to ptr addrspace(1)
  %vCastload302 = load i32, ptr addrspace(1) %IntToPtr2301, align 2		; visa id: 1160
  %1188 = add i64 %1186, 8
  %IntToPtr2303 = inttoptr i64 %1188 to ptr addrspace(1)
  %vCastload304 = load i32, ptr addrspace(1) %IntToPtr2303, align 2		; visa id: 1161
  %1189 = add i64 %1186, 12
  %IntToPtr2305 = inttoptr i64 %1189 to ptr addrspace(1)
  %vCastload306 = load i32, ptr addrspace(1) %IntToPtr2305, align 2		; visa id: 1162
  %1190 = bitcast i32 %vCastload300 to <2 x i16>		; visa id: 1163
  %1191 = bitcast i32 %vCastload302 to <2 x i16>		; visa id: 1165
  %1192 = extractelement <2 x i16> %1190, i32 0		; visa id: 1167
  %1193 = extractelement <2 x i16> %1190, i32 1		; visa id: 1167
  %1194 = extractelement <2 x i16> %1191, i32 0		; visa id: 1167
  %1195 = extractelement <2 x i16> %1191, i32 1		; visa id: 1167
  %1196 = bitcast i32 %vCastload304 to <2 x i16>		; visa id: 1167
  %1197 = bitcast i32 %vCastload306 to <2 x i16>		; visa id: 1169
  %1198 = extractelement <2 x i16> %1196, i32 0		; visa id: 1171
  %1199 = extractelement <2 x i16> %1196, i32 1		; visa id: 1171
  %1200 = extractelement <2 x i16> %1197, i32 0		; visa id: 1171
  %1201 = extractelement <2 x i16> %1197, i32 1		; visa id: 1171
  %1202 = zext i16 %1192 to i32		; visa id: 1171
  %1203 = shl nuw i32 %1202, 16, !spirv.Decorations !8781		; visa id: 1172
  %1204 = bitcast i32 %1203 to float
  %1205 = fmul float %.sroa.0121.4, %1204		; visa id: 1173
  %1206 = fadd float %.sroa.21.0, %1205		; visa id: 1174
  %1207 = zext i16 %1193 to i32		; visa id: 1175
  %1208 = shl nuw i32 %1207, 16, !spirv.Decorations !8781		; visa id: 1176
  %1209 = bitcast i32 %1208 to float
  %1210 = fmul float %.sroa.40.4, %1209		; visa id: 1177
  %1211 = fadd float %1206, %1210		; visa id: 1178
  %1212 = zext i16 %1194 to i32		; visa id: 1179
  %1213 = shl nuw i32 %1212, 16, !spirv.Decorations !8781		; visa id: 1180
  %1214 = bitcast i32 %1213 to float
  %1215 = fmul float %.sroa.64136.4, %1214		; visa id: 1181
  %1216 = fadd float %1211, %1215		; visa id: 1182
  %1217 = zext i16 %1195 to i32		; visa id: 1183
  %1218 = shl nuw i32 %1217, 16, !spirv.Decorations !8781		; visa id: 1184
  %1219 = bitcast i32 %1218 to float
  %1220 = fmul float %.sroa.88.4, %1219		; visa id: 1185
  %1221 = fadd float %1216, %1220		; visa id: 1186
  %1222 = zext i16 %1198 to i32		; visa id: 1187
  %1223 = shl nuw i32 %1222, 16, !spirv.Decorations !8781		; visa id: 1188
  %1224 = bitcast i32 %1223 to float
  %1225 = fmul float %.sroa.112151.4, %1224		; visa id: 1189
  %1226 = fadd float %1221, %1225		; visa id: 1190
  %1227 = zext i16 %1199 to i32		; visa id: 1191
  %1228 = shl nuw i32 %1227, 16, !spirv.Decorations !8781		; visa id: 1192
  %1229 = bitcast i32 %1228 to float
  %1230 = fmul float %.sroa.136.4, %1229		; visa id: 1193
  %1231 = fadd float %1226, %1230		; visa id: 1194
  %1232 = zext i16 %1200 to i32		; visa id: 1195
  %1233 = shl nuw i32 %1232, 16, !spirv.Decorations !8781		; visa id: 1196
  %1234 = bitcast i32 %1233 to float
  %1235 = fmul float %.sroa.160.4, %1234		; visa id: 1197
  %1236 = fadd float %1231, %1235		; visa id: 1198
  %1237 = zext i16 %1201 to i32		; visa id: 1199
  %1238 = shl nuw i32 %1237, 16, !spirv.Decorations !8781		; visa id: 1200
  %1239 = bitcast i32 %1238 to float
  %1240 = fmul float %.sroa.184.4, %1239		; visa id: 1201
  %1241 = fadd float %1236, %1240		; visa id: 1202
  %1242 = bitcast i32 %126 to <4 x i8>
  %1243 = extractelement <4 x i8> %1242, i32 2
  %1244 = lshr i32 %146, 2		; visa id: 1203
  %1245 = and i32 %1244, 768
  %1246 = zext i8 %1243 to i32		; visa id: 1204
  %1247 = or i32 %1246, %1245		; visa id: 1205
  %1248 = shl nuw nsw i32 %1247, 3, !spirv.Decorations !8791		; visa id: 1206
  %1249 = zext i32 %1248 to i64		; visa id: 1207
  %1250 = add i64 %116, %1249		; visa id: 1208
  %1251 = inttoptr i64 %1250 to ptr addrspace(1)		; visa id: 1209
  %1252 = load <2 x i32>, ptr addrspace(1) %1251, align 4		; visa id: 1209
  %1253 = extractelement <2 x i32> %1252, i32 0		; visa id: 1210
  %1254 = extractelement <2 x i32> %1252, i32 1		; visa id: 1210
  %1255 = and i32 %1253, 255		; visa id: 1210
  br i1 %1041, label %1263, label %1256, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1211

1256:                                             ; preds = %1183
; BB131 :
  %1257 = and i32 %126, 16777216
  %1258 = sub nsw i32 0, %1255, !spirv.Decorations !8800
  %1259 = icmp eq i32 %1257, 0		; visa id: 1213
  %1260 = select i1 %1259, i32 %1255, i32 %1258		; visa id: 1215
  %1261 = sitofp i32 %1260 to float		; visa id: 1216
  %1262 = fmul float %1027, %1261		; visa id: 1217
  br label %1271, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1218

1263:                                             ; preds = %1183
; BB132 :
  %1264 = uitofp i32 %1255 to float		; visa id: 1220
  %1265 = fmul float %1027, %1264		; visa id: 1221
  %1266 = and i32 %126, 16777216
  %1267 = icmp eq i32 %1266, 0		; visa id: 1222
  %1268 = select i1 %1267, i32 1, i32 -1		; visa id: 1224
  %1269 = sitofp i32 %1268 to float		; visa id: 1225
  %1270 = fmul float %1265, %1269		; visa id: 1226
  br label %1271, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1227

1271:                                             ; preds = %1263, %1256
; BB133 :
  %.sroa.0121.5 = phi float [ %1270, %1263 ], [ %1262, %1256 ]
  %1272 = bitcast i32 %1253 to <4 x i8>
  %1273 = extractelement <4 x i8> %1272, i32 1
  %1274 = zext i8 %1273 to i32		; visa id: 1228
  br i1 %1041, label %1282, label %1275, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1229

1275:                                             ; preds = %1271
; BB134 :
  %1276 = and i32 %126, 33554432
  %1277 = sub nsw i32 0, %1274, !spirv.Decorations !8800
  %1278 = icmp eq i32 %1276, 0		; visa id: 1231
  %1279 = select i1 %1278, i32 %1274, i32 %1277		; visa id: 1233
  %1280 = sitofp i32 %1279 to float		; visa id: 1234
  %1281 = fmul float %1027, %1280		; visa id: 1235
  br label %1290, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1236

1282:                                             ; preds = %1271
; BB135 :
  %1283 = uitofp i32 %1274 to float		; visa id: 1238
  %1284 = fmul float %1027, %1283		; visa id: 1239
  %1285 = and i32 %126, 33554432
  %1286 = icmp eq i32 %1285, 0		; visa id: 1240
  %1287 = select i1 %1286, i32 1, i32 -1		; visa id: 1242
  %1288 = sitofp i32 %1287 to float		; visa id: 1243
  %1289 = fmul float %1284, %1288		; visa id: 1244
  br label %1290, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1245

1290:                                             ; preds = %1282, %1275
; BB136 :
  %.sroa.40.5 = phi float [ %1289, %1282 ], [ %1281, %1275 ]
  %1291 = extractelement <4 x i8> %1272, i32 2
  %1292 = zext i8 %1291 to i32		; visa id: 1246
  br i1 %1041, label %1300, label %1293, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1247

1293:                                             ; preds = %1290
; BB137 :
  %1294 = and i32 %126, 67108864
  %1295 = sub nsw i32 0, %1292, !spirv.Decorations !8800
  %1296 = icmp eq i32 %1294, 0		; visa id: 1249
  %1297 = select i1 %1296, i32 %1292, i32 %1295		; visa id: 1251
  %1298 = sitofp i32 %1297 to float		; visa id: 1252
  %1299 = fmul float %1027, %1298		; visa id: 1253
  br label %1308, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1254

1300:                                             ; preds = %1290
; BB138 :
  %1301 = uitofp i32 %1292 to float		; visa id: 1256
  %1302 = fmul float %1027, %1301		; visa id: 1257
  %1303 = and i32 %126, 67108864
  %1304 = icmp eq i32 %1303, 0		; visa id: 1258
  %1305 = select i1 %1304, i32 1, i32 -1		; visa id: 1260
  %1306 = sitofp i32 %1305 to float		; visa id: 1261
  %1307 = fmul float %1302, %1306		; visa id: 1262
  br label %1308, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1263

1308:                                             ; preds = %1300, %1293
; BB139 :
  %.sroa.64136.5 = phi float [ %1307, %1300 ], [ %1299, %1293 ]
  %1309 = lshr i32 %1253, 24		; visa id: 1264
  br i1 %1041, label %1317, label %1310, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1265

1310:                                             ; preds = %1308
; BB140 :
  %1311 = and i32 %126, 134217728
  %1312 = sub nsw i32 0, %1309, !spirv.Decorations !8800
  %1313 = icmp eq i32 %1311, 0		; visa id: 1267
  %1314 = select i1 %1313, i32 %1309, i32 %1312		; visa id: 1269
  %1315 = sitofp i32 %1314 to float		; visa id: 1270
  %1316 = fmul float %1027, %1315		; visa id: 1271
  br label %1325, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1272

1317:                                             ; preds = %1308
; BB141 :
  %1318 = uitofp i32 %1309 to float		; visa id: 1274
  %1319 = fmul float %1027, %1318		; visa id: 1275
  %1320 = and i32 %126, 134217728
  %1321 = icmp eq i32 %1320, 0		; visa id: 1276
  %1322 = select i1 %1321, i32 1, i32 -1		; visa id: 1278
  %1323 = sitofp i32 %1322 to float		; visa id: 1279
  %1324 = fmul float %1319, %1323		; visa id: 1280
  br label %1325, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1281

1325:                                             ; preds = %1317, %1310
; BB142 :
  %.sroa.88.5 = phi float [ %1324, %1317 ], [ %1316, %1310 ]
  %1326 = and i32 %1254, 255		; visa id: 1282
  br i1 %1041, label %1334, label %1327, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1283

1327:                                             ; preds = %1325
; BB143 :
  %1328 = and i32 %126, 268435456
  %1329 = sub nsw i32 0, %1326, !spirv.Decorations !8800
  %1330 = icmp eq i32 %1328, 0		; visa id: 1285
  %1331 = select i1 %1330, i32 %1326, i32 %1329		; visa id: 1287
  %1332 = sitofp i32 %1331 to float		; visa id: 1288
  %1333 = fmul float %1027, %1332		; visa id: 1289
  br label %1342, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1290

1334:                                             ; preds = %1325
; BB144 :
  %1335 = uitofp i32 %1326 to float		; visa id: 1292
  %1336 = fmul float %1027, %1335		; visa id: 1293
  %1337 = and i32 %126, 268435456
  %1338 = icmp eq i32 %1337, 0		; visa id: 1294
  %1339 = select i1 %1338, i32 1, i32 -1		; visa id: 1296
  %1340 = sitofp i32 %1339 to float		; visa id: 1297
  %1341 = fmul float %1336, %1340		; visa id: 1298
  br label %1342, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1299

1342:                                             ; preds = %1334, %1327
; BB145 :
  %.sroa.112151.5 = phi float [ %1341, %1334 ], [ %1333, %1327 ]
  %1343 = bitcast i32 %1254 to <4 x i8>
  %1344 = extractelement <4 x i8> %1343, i32 1
  %1345 = zext i8 %1344 to i32		; visa id: 1300
  br i1 %1041, label %1353, label %1346, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1301

1346:                                             ; preds = %1342
; BB146 :
  %1347 = and i32 %126, 536870912
  %1348 = sub nsw i32 0, %1345, !spirv.Decorations !8800
  %1349 = icmp eq i32 %1347, 0		; visa id: 1303
  %1350 = select i1 %1349, i32 %1345, i32 %1348		; visa id: 1305
  %1351 = sitofp i32 %1350 to float		; visa id: 1306
  %1352 = fmul float %1027, %1351		; visa id: 1307
  br label %1361, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1308

1353:                                             ; preds = %1342
; BB147 :
  %1354 = uitofp i32 %1345 to float		; visa id: 1310
  %1355 = fmul float %1027, %1354		; visa id: 1311
  %1356 = and i32 %126, 536870912
  %1357 = icmp eq i32 %1356, 0		; visa id: 1312
  %1358 = select i1 %1357, i32 1, i32 -1		; visa id: 1314
  %1359 = sitofp i32 %1358 to float		; visa id: 1315
  %1360 = fmul float %1355, %1359		; visa id: 1316
  br label %1361, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1317

1361:                                             ; preds = %1353, %1346
; BB148 :
  %.sroa.136.5 = phi float [ %1360, %1353 ], [ %1352, %1346 ]
  %1362 = extractelement <4 x i8> %1343, i32 2
  %1363 = zext i8 %1362 to i32		; visa id: 1318
  br i1 %1041, label %1371, label %1364, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1319

1364:                                             ; preds = %1361
; BB149 :
  %1365 = and i32 %126, 1073741824
  %1366 = sub nsw i32 0, %1363, !spirv.Decorations !8800
  %1367 = icmp eq i32 %1365, 0		; visa id: 1321
  %1368 = select i1 %1367, i32 %1363, i32 %1366		; visa id: 1323
  %1369 = sitofp i32 %1368 to float		; visa id: 1324
  %1370 = fmul float %1027, %1369		; visa id: 1325
  br label %1379, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1326

1371:                                             ; preds = %1361
; BB150 :
  %1372 = uitofp i32 %1363 to float		; visa id: 1328
  %1373 = fmul float %1027, %1372		; visa id: 1329
  %1374 = and i32 %126, 1073741824
  %1375 = icmp eq i32 %1374, 0		; visa id: 1330
  %1376 = select i1 %1375, i32 1, i32 -1		; visa id: 1332
  %1377 = sitofp i32 %1376 to float		; visa id: 1333
  %1378 = fmul float %1373, %1377		; visa id: 1334
  br label %1379, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1335

1379:                                             ; preds = %1371, %1364
; BB151 :
  %.sroa.160.5 = phi float [ %1378, %1371 ], [ %1370, %1364 ]
  %1380 = lshr i32 %1254, 24		; visa id: 1336
  br i1 %1041, label %1387, label %1381, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1337

1381:                                             ; preds = %1379
; BB152 :
  %1382 = sub nsw i32 0, %1380, !spirv.Decorations !8800
  %1383 = icmp slt i32 %126, 0		; visa id: 1339
  %1384 = select i1 %1383, i32 %1382, i32 %1380		; visa id: 1340
  %1385 = sitofp i32 %1384 to float		; visa id: 1341
  %1386 = fmul float %1027, %1385		; visa id: 1342
  br label %1394, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1343

1387:                                             ; preds = %1379
; BB153 :
  %1388 = uitofp i32 %1380 to float		; visa id: 1345
  %1389 = fmul float %1027, %1388		; visa id: 1346
  %1390 = icmp sgt i32 %126, -1		; visa id: 1347
  %1391 = select i1 %1390, i32 1, i32 -1		; visa id: 1348
  %1392 = sitofp i32 %1391 to float		; visa id: 1349
  %1393 = fmul float %1389, %1392		; visa id: 1350
  br label %1394, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1351

1394:                                             ; preds = %1387, %1381
; BB154 :
  %.sroa.184.5 = phi float [ %1393, %1387 ], [ %1386, %1381 ]
  %1395 = or i32 %315, 80		; visa id: 1352
  %1396 = zext i32 %1395 to i64		; visa id: 1353
  %1397 = add i64 %1396, %const_reg_qword2		; visa id: 1354
  %IntToPtr2307 = inttoptr i64 %1397 to ptr addrspace(1)		; visa id: 1355
  %vCastload308 = load i32, ptr addrspace(1) %IntToPtr2307, align 2		; visa id: 1355
  %1398 = add i64 %1397, 4
  %IntToPtr2309 = inttoptr i64 %1398 to ptr addrspace(1)
  %vCastload310 = load i32, ptr addrspace(1) %IntToPtr2309, align 2		; visa id: 1356
  %1399 = add i64 %1397, 8
  %IntToPtr2311 = inttoptr i64 %1399 to ptr addrspace(1)
  %vCastload312 = load i32, ptr addrspace(1) %IntToPtr2311, align 2		; visa id: 1357
  %1400 = add i64 %1397, 12
  %IntToPtr2313 = inttoptr i64 %1400 to ptr addrspace(1)
  %vCastload314 = load i32, ptr addrspace(1) %IntToPtr2313, align 2		; visa id: 1358
  %1401 = bitcast i32 %vCastload308 to <2 x i16>		; visa id: 1359
  %1402 = bitcast i32 %vCastload310 to <2 x i16>		; visa id: 1361
  %1403 = extractelement <2 x i16> %1401, i32 0		; visa id: 1363
  %1404 = extractelement <2 x i16> %1401, i32 1		; visa id: 1363
  %1405 = extractelement <2 x i16> %1402, i32 0		; visa id: 1363
  %1406 = extractelement <2 x i16> %1402, i32 1		; visa id: 1363
  %1407 = bitcast i32 %vCastload312 to <2 x i16>		; visa id: 1363
  %1408 = bitcast i32 %vCastload314 to <2 x i16>		; visa id: 1365
  %1409 = extractelement <2 x i16> %1407, i32 0		; visa id: 1367
  %1410 = extractelement <2 x i16> %1407, i32 1		; visa id: 1367
  %1411 = extractelement <2 x i16> %1408, i32 0		; visa id: 1367
  %1412 = extractelement <2 x i16> %1408, i32 1		; visa id: 1367
  %1413 = zext i16 %1403 to i32		; visa id: 1367
  %1414 = shl nuw i32 %1413, 16, !spirv.Decorations !8781		; visa id: 1368
  %1415 = bitcast i32 %1414 to float
  %1416 = fmul float %.sroa.0121.5, %1415		; visa id: 1369
  %1417 = fadd float %.sroa.28.0, %1416		; visa id: 1370
  %1418 = zext i16 %1404 to i32		; visa id: 1371
  %1419 = shl nuw i32 %1418, 16, !spirv.Decorations !8781		; visa id: 1372
  %1420 = bitcast i32 %1419 to float
  %1421 = fmul float %.sroa.40.5, %1420		; visa id: 1373
  %1422 = fadd float %1417, %1421		; visa id: 1374
  %1423 = zext i16 %1405 to i32		; visa id: 1375
  %1424 = shl nuw i32 %1423, 16, !spirv.Decorations !8781		; visa id: 1376
  %1425 = bitcast i32 %1424 to float
  %1426 = fmul float %.sroa.64136.5, %1425		; visa id: 1377
  %1427 = fadd float %1422, %1426		; visa id: 1378
  %1428 = zext i16 %1406 to i32		; visa id: 1379
  %1429 = shl nuw i32 %1428, 16, !spirv.Decorations !8781		; visa id: 1380
  %1430 = bitcast i32 %1429 to float
  %1431 = fmul float %.sroa.88.5, %1430		; visa id: 1381
  %1432 = fadd float %1427, %1431		; visa id: 1382
  %1433 = zext i16 %1409 to i32		; visa id: 1383
  %1434 = shl nuw i32 %1433, 16, !spirv.Decorations !8781		; visa id: 1384
  %1435 = bitcast i32 %1434 to float
  %1436 = fmul float %.sroa.112151.5, %1435		; visa id: 1385
  %1437 = fadd float %1432, %1436		; visa id: 1386
  %1438 = zext i16 %1410 to i32		; visa id: 1387
  %1439 = shl nuw i32 %1438, 16, !spirv.Decorations !8781		; visa id: 1388
  %1440 = bitcast i32 %1439 to float
  %1441 = fmul float %.sroa.136.5, %1440		; visa id: 1389
  %1442 = fadd float %1437, %1441		; visa id: 1390
  %1443 = zext i16 %1411 to i32		; visa id: 1391
  %1444 = shl nuw i32 %1443, 16, !spirv.Decorations !8781		; visa id: 1392
  %1445 = bitcast i32 %1444 to float
  %1446 = fmul float %.sroa.160.5, %1445		; visa id: 1393
  %1447 = fadd float %1442, %1446		; visa id: 1394
  %1448 = zext i16 %1412 to i32		; visa id: 1395
  %1449 = shl nuw i32 %1448, 16, !spirv.Decorations !8781		; visa id: 1396
  %1450 = bitcast i32 %1449 to float
  %1451 = fmul float %.sroa.184.5, %1450		; visa id: 1397
  %1452 = fadd float %1447, %1451		; visa id: 1398
  %1453 = and i32 %127, 255
  %1454 = lshr i32 %146, 4		; visa id: 1399
  %1455 = and i32 %1454, 768		; visa id: 1400
  %1456 = or i32 %1453, %1455		; visa id: 1401
  %1457 = lshr i32 %161, 12		; visa id: 1402
  %1458 = uitofp i32 %1457 to float		; visa id: 1403
  %1459 = fadd float %1458, 5.000000e-01		; visa id: 1404
  %1460 = fmul float %144, %1459		; visa id: 1405
  %1461 = fmul float %1460, 2.500000e-01		; visa id: 1406
  %1462 = shl nuw nsw i32 %1456, 3, !spirv.Decorations !8791		; visa id: 1407
  %1463 = zext i32 %1462 to i64		; visa id: 1408
  %1464 = add i64 %116, %1463		; visa id: 1409
  %1465 = inttoptr i64 %1464 to ptr addrspace(1)		; visa id: 1410
  %1466 = load <2 x i32>, ptr addrspace(1) %1465, align 4		; visa id: 1410
  %1467 = extractelement <2 x i32> %1466, i32 0		; visa id: 1411
  %1468 = extractelement <2 x i32> %1466, i32 1		; visa id: 1411
  %1469 = bitcast float %1461 to i32
  %1470 = and i32 %1469, 2147483647		; visa id: 1411
  %1471 = icmp ugt i32 %1470, 2139095040
  %1472 = fcmp oeq float %157, 0x7FF0000000000000		; visa id: 1412
  %1473 = fcmp une float %157, %157
  %1474 = or i1 %1473, %1472		; visa id: 1413
  %1475 = or i1 %1474, %1471		; visa id: 1415
  %1476 = and i32 %1467, 255		; visa id: 1417
  br i1 %1475, label %1484, label %1477, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1418

1477:                                             ; preds = %1394
; BB155 :
  %1478 = and i32 %127, 256
  %1479 = sub nsw i32 0, %1476, !spirv.Decorations !8800
  %1480 = icmp eq i32 %1478, 0		; visa id: 1420
  %1481 = select i1 %1480, i32 %1476, i32 %1479		; visa id: 1422
  %1482 = sitofp i32 %1481 to float		; visa id: 1423
  %1483 = fmul float %1461, %1482		; visa id: 1424
  br label %1492, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1425

1484:                                             ; preds = %1394
; BB156 :
  %1485 = uitofp i32 %1476 to float		; visa id: 1427
  %1486 = fmul float %1461, %1485		; visa id: 1428
  %1487 = and i32 %127, 256
  %1488 = icmp eq i32 %1487, 0		; visa id: 1429
  %1489 = select i1 %1488, i32 1, i32 -1		; visa id: 1431
  %1490 = sitofp i32 %1489 to float		; visa id: 1432
  %1491 = fmul float %1486, %1490		; visa id: 1433
  br label %1492, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1434

1492:                                             ; preds = %1484, %1477
; BB157 :
  %.sroa.0121.6 = phi float [ %1491, %1484 ], [ %1483, %1477 ]
  %1493 = bitcast i32 %1467 to <4 x i8>
  %1494 = extractelement <4 x i8> %1493, i32 1
  %1495 = zext i8 %1494 to i32		; visa id: 1435
  br i1 %1475, label %1503, label %1496, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1436

1496:                                             ; preds = %1492
; BB158 :
  %1497 = and i32 %127, 512
  %1498 = sub nsw i32 0, %1495, !spirv.Decorations !8800
  %1499 = icmp eq i32 %1497, 0		; visa id: 1438
  %1500 = select i1 %1499, i32 %1495, i32 %1498		; visa id: 1440
  %1501 = sitofp i32 %1500 to float		; visa id: 1441
  %1502 = fmul float %1461, %1501		; visa id: 1442
  br label %1511, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1443

1503:                                             ; preds = %1492
; BB159 :
  %1504 = uitofp i32 %1495 to float		; visa id: 1445
  %1505 = fmul float %1461, %1504		; visa id: 1446
  %1506 = and i32 %127, 512
  %1507 = icmp eq i32 %1506, 0		; visa id: 1447
  %1508 = select i1 %1507, i32 1, i32 -1		; visa id: 1449
  %1509 = sitofp i32 %1508 to float		; visa id: 1450
  %1510 = fmul float %1505, %1509		; visa id: 1451
  br label %1511, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1452

1511:                                             ; preds = %1503, %1496
; BB160 :
  %.sroa.40.6 = phi float [ %1510, %1503 ], [ %1502, %1496 ]
  %1512 = extractelement <4 x i8> %1493, i32 2
  %1513 = zext i8 %1512 to i32		; visa id: 1453
  br i1 %1475, label %1521, label %1514, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1454

1514:                                             ; preds = %1511
; BB161 :
  %1515 = and i32 %127, 1024
  %1516 = sub nsw i32 0, %1513, !spirv.Decorations !8800
  %1517 = icmp eq i32 %1515, 0		; visa id: 1456
  %1518 = select i1 %1517, i32 %1513, i32 %1516		; visa id: 1458
  %1519 = sitofp i32 %1518 to float		; visa id: 1459
  %1520 = fmul float %1461, %1519		; visa id: 1460
  br label %1529, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1461

1521:                                             ; preds = %1511
; BB162 :
  %1522 = uitofp i32 %1513 to float		; visa id: 1463
  %1523 = fmul float %1461, %1522		; visa id: 1464
  %1524 = and i32 %127, 1024
  %1525 = icmp eq i32 %1524, 0		; visa id: 1465
  %1526 = select i1 %1525, i32 1, i32 -1		; visa id: 1467
  %1527 = sitofp i32 %1526 to float		; visa id: 1468
  %1528 = fmul float %1523, %1527		; visa id: 1469
  br label %1529, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1470

1529:                                             ; preds = %1521, %1514
; BB163 :
  %.sroa.64136.6 = phi float [ %1528, %1521 ], [ %1520, %1514 ]
  %1530 = lshr i32 %1467, 24		; visa id: 1471
  br i1 %1475, label %1538, label %1531, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1472

1531:                                             ; preds = %1529
; BB164 :
  %1532 = and i32 %127, 2048
  %1533 = sub nsw i32 0, %1530, !spirv.Decorations !8800
  %1534 = icmp eq i32 %1532, 0		; visa id: 1474
  %1535 = select i1 %1534, i32 %1530, i32 %1533		; visa id: 1476
  %1536 = sitofp i32 %1535 to float		; visa id: 1477
  %1537 = fmul float %1461, %1536		; visa id: 1478
  br label %1546, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1479

1538:                                             ; preds = %1529
; BB165 :
  %1539 = uitofp i32 %1530 to float		; visa id: 1481
  %1540 = fmul float %1461, %1539		; visa id: 1482
  %1541 = and i32 %127, 2048
  %1542 = icmp eq i32 %1541, 0		; visa id: 1483
  %1543 = select i1 %1542, i32 1, i32 -1		; visa id: 1485
  %1544 = sitofp i32 %1543 to float		; visa id: 1486
  %1545 = fmul float %1540, %1544		; visa id: 1487
  br label %1546, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1488

1546:                                             ; preds = %1538, %1531
; BB166 :
  %.sroa.88.6 = phi float [ %1545, %1538 ], [ %1537, %1531 ]
  %1547 = and i32 %1468, 255		; visa id: 1489
  br i1 %1475, label %1555, label %1548, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1490

1548:                                             ; preds = %1546
; BB167 :
  %1549 = and i32 %127, 4096
  %1550 = sub nsw i32 0, %1547, !spirv.Decorations !8800
  %1551 = icmp eq i32 %1549, 0		; visa id: 1492
  %1552 = select i1 %1551, i32 %1547, i32 %1550		; visa id: 1494
  %1553 = sitofp i32 %1552 to float		; visa id: 1495
  %1554 = fmul float %1461, %1553		; visa id: 1496
  br label %1563, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1497

1555:                                             ; preds = %1546
; BB168 :
  %1556 = uitofp i32 %1547 to float		; visa id: 1499
  %1557 = fmul float %1461, %1556		; visa id: 1500
  %1558 = and i32 %127, 4096
  %1559 = icmp eq i32 %1558, 0		; visa id: 1501
  %1560 = select i1 %1559, i32 1, i32 -1		; visa id: 1503
  %1561 = sitofp i32 %1560 to float		; visa id: 1504
  %1562 = fmul float %1557, %1561		; visa id: 1505
  br label %1563, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1506

1563:                                             ; preds = %1555, %1548
; BB169 :
  %.sroa.112151.6 = phi float [ %1562, %1555 ], [ %1554, %1548 ]
  %1564 = bitcast i32 %1468 to <4 x i8>
  %1565 = extractelement <4 x i8> %1564, i32 1
  %1566 = zext i8 %1565 to i32		; visa id: 1507
  br i1 %1475, label %1574, label %1567, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1508

1567:                                             ; preds = %1563
; BB170 :
  %1568 = and i32 %127, 8192
  %1569 = sub nsw i32 0, %1566, !spirv.Decorations !8800
  %1570 = icmp eq i32 %1568, 0		; visa id: 1510
  %1571 = select i1 %1570, i32 %1566, i32 %1569		; visa id: 1512
  %1572 = sitofp i32 %1571 to float		; visa id: 1513
  %1573 = fmul float %1461, %1572		; visa id: 1514
  br label %1582, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1515

1574:                                             ; preds = %1563
; BB171 :
  %1575 = uitofp i32 %1566 to float		; visa id: 1517
  %1576 = fmul float %1461, %1575		; visa id: 1518
  %1577 = and i32 %127, 8192
  %1578 = icmp eq i32 %1577, 0		; visa id: 1519
  %1579 = select i1 %1578, i32 1, i32 -1		; visa id: 1521
  %1580 = sitofp i32 %1579 to float		; visa id: 1522
  %1581 = fmul float %1576, %1580		; visa id: 1523
  br label %1582, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1524

1582:                                             ; preds = %1574, %1567
; BB172 :
  %.sroa.136.6 = phi float [ %1581, %1574 ], [ %1573, %1567 ]
  %1583 = extractelement <4 x i8> %1564, i32 2
  %1584 = zext i8 %1583 to i32		; visa id: 1525
  br i1 %1475, label %1592, label %1585, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1526

1585:                                             ; preds = %1582
; BB173 :
  %1586 = and i32 %127, 16384
  %1587 = sub nsw i32 0, %1584, !spirv.Decorations !8800
  %1588 = icmp eq i32 %1586, 0		; visa id: 1528
  %1589 = select i1 %1588, i32 %1584, i32 %1587		; visa id: 1530
  %1590 = sitofp i32 %1589 to float		; visa id: 1531
  %1591 = fmul float %1461, %1590		; visa id: 1532
  br label %1600, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1533

1592:                                             ; preds = %1582
; BB174 :
  %1593 = uitofp i32 %1584 to float		; visa id: 1535
  %1594 = fmul float %1461, %1593		; visa id: 1536
  %1595 = and i32 %127, 16384
  %1596 = icmp eq i32 %1595, 0		; visa id: 1537
  %1597 = select i1 %1596, i32 1, i32 -1		; visa id: 1539
  %1598 = sitofp i32 %1597 to float		; visa id: 1540
  %1599 = fmul float %1594, %1598		; visa id: 1541
  br label %1600, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1542

1600:                                             ; preds = %1592, %1585
; BB175 :
  %.sroa.160.6 = phi float [ %1599, %1592 ], [ %1591, %1585 ]
  %1601 = lshr i32 %1468, 24		; visa id: 1543
  br i1 %1475, label %1609, label %1602, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1544

1602:                                             ; preds = %1600
; BB176 :
  %1603 = and i32 %127, 32768
  %1604 = sub nsw i32 0, %1601, !spirv.Decorations !8800
  %1605 = icmp eq i32 %1603, 0		; visa id: 1546
  %1606 = select i1 %1605, i32 %1601, i32 %1604		; visa id: 1548
  %1607 = sitofp i32 %1606 to float		; visa id: 1549
  %1608 = fmul float %1461, %1607		; visa id: 1550
  br label %1617, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1551

1609:                                             ; preds = %1600
; BB177 :
  %1610 = uitofp i32 %1601 to float		; visa id: 1553
  %1611 = fmul float %1461, %1610		; visa id: 1554
  %1612 = and i32 %127, 32768
  %1613 = icmp eq i32 %1612, 0		; visa id: 1555
  %1614 = select i1 %1613, i32 1, i32 -1		; visa id: 1557
  %1615 = sitofp i32 %1614 to float		; visa id: 1558
  %1616 = fmul float %1611, %1615		; visa id: 1559
  br label %1617, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1560

1617:                                             ; preds = %1609, %1602
; BB178 :
  %.sroa.184.6 = phi float [ %1616, %1609 ], [ %1608, %1602 ]
  %1618 = or i32 %315, 96		; visa id: 1561
  %1619 = zext i32 %1618 to i64		; visa id: 1562
  %1620 = add i64 %1619, %const_reg_qword2		; visa id: 1563
  %IntToPtr2315 = inttoptr i64 %1620 to ptr addrspace(1)		; visa id: 1564
  %vCastload316 = load i32, ptr addrspace(1) %IntToPtr2315, align 2		; visa id: 1564
  %1621 = add i64 %1620, 4
  %IntToPtr2317 = inttoptr i64 %1621 to ptr addrspace(1)
  %vCastload318 = load i32, ptr addrspace(1) %IntToPtr2317, align 2		; visa id: 1565
  %1622 = add i64 %1620, 8
  %IntToPtr2319 = inttoptr i64 %1622 to ptr addrspace(1)
  %vCastload320 = load i32, ptr addrspace(1) %IntToPtr2319, align 2		; visa id: 1566
  %1623 = add i64 %1620, 12
  %IntToPtr2321 = inttoptr i64 %1623 to ptr addrspace(1)
  %vCastload322 = load i32, ptr addrspace(1) %IntToPtr2321, align 2		; visa id: 1567
  %1624 = bitcast i32 %vCastload316 to <2 x i16>		; visa id: 1568
  %1625 = bitcast i32 %vCastload318 to <2 x i16>		; visa id: 1570
  %1626 = extractelement <2 x i16> %1624, i32 0		; visa id: 1572
  %1627 = extractelement <2 x i16> %1624, i32 1		; visa id: 1572
  %1628 = extractelement <2 x i16> %1625, i32 0		; visa id: 1572
  %1629 = extractelement <2 x i16> %1625, i32 1		; visa id: 1572
  %1630 = bitcast i32 %vCastload320 to <2 x i16>		; visa id: 1572
  %1631 = bitcast i32 %vCastload322 to <2 x i16>		; visa id: 1574
  %1632 = extractelement <2 x i16> %1630, i32 0		; visa id: 1576
  %1633 = extractelement <2 x i16> %1630, i32 1		; visa id: 1576
  %1634 = extractelement <2 x i16> %1631, i32 0		; visa id: 1576
  %1635 = extractelement <2 x i16> %1631, i32 1		; visa id: 1576
  %1636 = zext i16 %1626 to i32		; visa id: 1576
  %1637 = shl nuw i32 %1636, 16, !spirv.Decorations !8781		; visa id: 1577
  %1638 = bitcast i32 %1637 to float
  %1639 = fmul float %.sroa.0121.6, %1638		; visa id: 1578
  %1640 = fadd float %.sroa.31.0, %1639		; visa id: 1579
  %1641 = zext i16 %1627 to i32		; visa id: 1580
  %1642 = shl nuw i32 %1641, 16, !spirv.Decorations !8781		; visa id: 1581
  %1643 = bitcast i32 %1642 to float
  %1644 = fmul float %.sroa.40.6, %1643		; visa id: 1582
  %1645 = fadd float %1640, %1644		; visa id: 1583
  %1646 = zext i16 %1628 to i32		; visa id: 1584
  %1647 = shl nuw i32 %1646, 16, !spirv.Decorations !8781		; visa id: 1585
  %1648 = bitcast i32 %1647 to float
  %1649 = fmul float %.sroa.64136.6, %1648		; visa id: 1586
  %1650 = fadd float %1645, %1649		; visa id: 1587
  %1651 = zext i16 %1629 to i32		; visa id: 1588
  %1652 = shl nuw i32 %1651, 16, !spirv.Decorations !8781		; visa id: 1589
  %1653 = bitcast i32 %1652 to float
  %1654 = fmul float %.sroa.88.6, %1653		; visa id: 1590
  %1655 = fadd float %1650, %1654		; visa id: 1591
  %1656 = zext i16 %1632 to i32		; visa id: 1592
  %1657 = shl nuw i32 %1656, 16, !spirv.Decorations !8781		; visa id: 1593
  %1658 = bitcast i32 %1657 to float
  %1659 = fmul float %.sroa.112151.6, %1658		; visa id: 1594
  %1660 = fadd float %1655, %1659		; visa id: 1595
  %1661 = zext i16 %1633 to i32		; visa id: 1596
  %1662 = shl nuw i32 %1661, 16, !spirv.Decorations !8781		; visa id: 1597
  %1663 = bitcast i32 %1662 to float
  %1664 = fmul float %.sroa.136.6, %1663		; visa id: 1598
  %1665 = fadd float %1660, %1664		; visa id: 1599
  %1666 = zext i16 %1634 to i32		; visa id: 1600
  %1667 = shl nuw i32 %1666, 16, !spirv.Decorations !8781		; visa id: 1601
  %1668 = bitcast i32 %1667 to float
  %1669 = fmul float %.sroa.160.6, %1668		; visa id: 1602
  %1670 = fadd float %1665, %1669		; visa id: 1603
  %1671 = zext i16 %1635 to i32		; visa id: 1604
  %1672 = shl nuw i32 %1671, 16, !spirv.Decorations !8781		; visa id: 1605
  %1673 = bitcast i32 %1672 to float
  %1674 = fmul float %.sroa.184.6, %1673		; visa id: 1606
  %1675 = fadd float %1670, %1674		; visa id: 1607
  %1676 = bitcast i32 %127 to <4 x i8>
  %1677 = extractelement <4 x i8> %1676, i32 2
  %1678 = lshr i32 %146, 6		; visa id: 1608
  %1679 = and i32 %1678, 768
  %1680 = zext i8 %1677 to i32		; visa id: 1609
  %1681 = or i32 %1680, %1679		; visa id: 1610
  %1682 = shl nuw nsw i32 %1681, 3, !spirv.Decorations !8791		; visa id: 1611
  %1683 = zext i32 %1682 to i64		; visa id: 1612
  %1684 = add i64 %116, %1683		; visa id: 1613
  %1685 = inttoptr i64 %1684 to ptr addrspace(1)		; visa id: 1614
  %1686 = load <2 x i32>, ptr addrspace(1) %1685, align 4		; visa id: 1614
  %1687 = extractelement <2 x i32> %1686, i32 0		; visa id: 1615
  %1688 = extractelement <2 x i32> %1686, i32 1		; visa id: 1615
  %1689 = and i32 %1687, 255		; visa id: 1615
  br i1 %1475, label %1697, label %1690, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1616

1690:                                             ; preds = %1617
; BB179 :
  %1691 = and i32 %127, 16777216
  %1692 = sub nsw i32 0, %1689, !spirv.Decorations !8800
  %1693 = icmp eq i32 %1691, 0		; visa id: 1618
  %1694 = select i1 %1693, i32 %1689, i32 %1692		; visa id: 1620
  %1695 = sitofp i32 %1694 to float		; visa id: 1621
  %1696 = fmul float %1461, %1695		; visa id: 1622
  br label %1705, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1623

1697:                                             ; preds = %1617
; BB180 :
  %1698 = uitofp i32 %1689 to float		; visa id: 1625
  %1699 = fmul float %1461, %1698		; visa id: 1626
  %1700 = and i32 %127, 16777216
  %1701 = icmp eq i32 %1700, 0		; visa id: 1627
  %1702 = select i1 %1701, i32 1, i32 -1		; visa id: 1629
  %1703 = sitofp i32 %1702 to float		; visa id: 1630
  %1704 = fmul float %1699, %1703		; visa id: 1631
  br label %1705, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1632

1705:                                             ; preds = %1697, %1690
; BB181 :
  %.sroa.0121.7 = phi float [ %1704, %1697 ], [ %1696, %1690 ]
  %1706 = bitcast i32 %1687 to <4 x i8>
  %1707 = extractelement <4 x i8> %1706, i32 1
  %1708 = zext i8 %1707 to i32		; visa id: 1633
  br i1 %1475, label %1716, label %1709, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1634

1709:                                             ; preds = %1705
; BB182 :
  %1710 = and i32 %127, 33554432
  %1711 = sub nsw i32 0, %1708, !spirv.Decorations !8800
  %1712 = icmp eq i32 %1710, 0		; visa id: 1636
  %1713 = select i1 %1712, i32 %1708, i32 %1711		; visa id: 1638
  %1714 = sitofp i32 %1713 to float		; visa id: 1639
  %1715 = fmul float %1461, %1714		; visa id: 1640
  br label %1724, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1641

1716:                                             ; preds = %1705
; BB183 :
  %1717 = uitofp i32 %1708 to float		; visa id: 1643
  %1718 = fmul float %1461, %1717		; visa id: 1644
  %1719 = and i32 %127, 33554432
  %1720 = icmp eq i32 %1719, 0		; visa id: 1645
  %1721 = select i1 %1720, i32 1, i32 -1		; visa id: 1647
  %1722 = sitofp i32 %1721 to float		; visa id: 1648
  %1723 = fmul float %1718, %1722		; visa id: 1649
  br label %1724, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1650

1724:                                             ; preds = %1716, %1709
; BB184 :
  %.sroa.40.7 = phi float [ %1723, %1716 ], [ %1715, %1709 ]
  %1725 = extractelement <4 x i8> %1706, i32 2
  %1726 = zext i8 %1725 to i32		; visa id: 1651
  br i1 %1475, label %1734, label %1727, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1652

1727:                                             ; preds = %1724
; BB185 :
  %1728 = and i32 %127, 67108864
  %1729 = sub nsw i32 0, %1726, !spirv.Decorations !8800
  %1730 = icmp eq i32 %1728, 0		; visa id: 1654
  %1731 = select i1 %1730, i32 %1726, i32 %1729		; visa id: 1656
  %1732 = sitofp i32 %1731 to float		; visa id: 1657
  %1733 = fmul float %1461, %1732		; visa id: 1658
  br label %1742, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1659

1734:                                             ; preds = %1724
; BB186 :
  %1735 = uitofp i32 %1726 to float		; visa id: 1661
  %1736 = fmul float %1461, %1735		; visa id: 1662
  %1737 = and i32 %127, 67108864
  %1738 = icmp eq i32 %1737, 0		; visa id: 1663
  %1739 = select i1 %1738, i32 1, i32 -1		; visa id: 1665
  %1740 = sitofp i32 %1739 to float		; visa id: 1666
  %1741 = fmul float %1736, %1740		; visa id: 1667
  br label %1742, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1668

1742:                                             ; preds = %1734, %1727
; BB187 :
  %.sroa.64136.7 = phi float [ %1741, %1734 ], [ %1733, %1727 ]
  %1743 = lshr i32 %1687, 24		; visa id: 1669
  br i1 %1475, label %1751, label %1744, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1670

1744:                                             ; preds = %1742
; BB188 :
  %1745 = and i32 %127, 134217728
  %1746 = sub nsw i32 0, %1743, !spirv.Decorations !8800
  %1747 = icmp eq i32 %1745, 0		; visa id: 1672
  %1748 = select i1 %1747, i32 %1743, i32 %1746		; visa id: 1674
  %1749 = sitofp i32 %1748 to float		; visa id: 1675
  %1750 = fmul float %1461, %1749		; visa id: 1676
  br label %1759, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1677

1751:                                             ; preds = %1742
; BB189 :
  %1752 = uitofp i32 %1743 to float		; visa id: 1679
  %1753 = fmul float %1461, %1752		; visa id: 1680
  %1754 = and i32 %127, 134217728
  %1755 = icmp eq i32 %1754, 0		; visa id: 1681
  %1756 = select i1 %1755, i32 1, i32 -1		; visa id: 1683
  %1757 = sitofp i32 %1756 to float		; visa id: 1684
  %1758 = fmul float %1753, %1757		; visa id: 1685
  br label %1759, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1686

1759:                                             ; preds = %1751, %1744
; BB190 :
  %.sroa.88.7 = phi float [ %1758, %1751 ], [ %1750, %1744 ]
  %1760 = and i32 %1688, 255		; visa id: 1687
  br i1 %1475, label %1768, label %1761, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1688

1761:                                             ; preds = %1759
; BB191 :
  %1762 = and i32 %127, 268435456
  %1763 = sub nsw i32 0, %1760, !spirv.Decorations !8800
  %1764 = icmp eq i32 %1762, 0		; visa id: 1690
  %1765 = select i1 %1764, i32 %1760, i32 %1763		; visa id: 1692
  %1766 = sitofp i32 %1765 to float		; visa id: 1693
  %1767 = fmul float %1461, %1766		; visa id: 1694
  br label %1776, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1695

1768:                                             ; preds = %1759
; BB192 :
  %1769 = uitofp i32 %1760 to float		; visa id: 1697
  %1770 = fmul float %1461, %1769		; visa id: 1698
  %1771 = and i32 %127, 268435456
  %1772 = icmp eq i32 %1771, 0		; visa id: 1699
  %1773 = select i1 %1772, i32 1, i32 -1		; visa id: 1701
  %1774 = sitofp i32 %1773 to float		; visa id: 1702
  %1775 = fmul float %1770, %1774		; visa id: 1703
  br label %1776, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1704

1776:                                             ; preds = %1768, %1761
; BB193 :
  %.sroa.112151.7 = phi float [ %1775, %1768 ], [ %1767, %1761 ]
  %1777 = bitcast i32 %1688 to <4 x i8>
  %1778 = extractelement <4 x i8> %1777, i32 1
  %1779 = zext i8 %1778 to i32		; visa id: 1705
  br i1 %1475, label %1787, label %1780, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1706

1780:                                             ; preds = %1776
; BB194 :
  %1781 = and i32 %127, 536870912
  %1782 = sub nsw i32 0, %1779, !spirv.Decorations !8800
  %1783 = icmp eq i32 %1781, 0		; visa id: 1708
  %1784 = select i1 %1783, i32 %1779, i32 %1782		; visa id: 1710
  %1785 = sitofp i32 %1784 to float		; visa id: 1711
  %1786 = fmul float %1461, %1785		; visa id: 1712
  br label %1795, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1713

1787:                                             ; preds = %1776
; BB195 :
  %1788 = uitofp i32 %1779 to float		; visa id: 1715
  %1789 = fmul float %1461, %1788		; visa id: 1716
  %1790 = and i32 %127, 536870912
  %1791 = icmp eq i32 %1790, 0		; visa id: 1717
  %1792 = select i1 %1791, i32 1, i32 -1		; visa id: 1719
  %1793 = sitofp i32 %1792 to float		; visa id: 1720
  %1794 = fmul float %1789, %1793		; visa id: 1721
  br label %1795, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1722

1795:                                             ; preds = %1787, %1780
; BB196 :
  %.sroa.136.7 = phi float [ %1794, %1787 ], [ %1786, %1780 ]
  %1796 = extractelement <4 x i8> %1777, i32 2
  %1797 = zext i8 %1796 to i32		; visa id: 1723
  br i1 %1475, label %1805, label %1798, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1724

1798:                                             ; preds = %1795
; BB197 :
  %1799 = and i32 %127, 1073741824
  %1800 = sub nsw i32 0, %1797, !spirv.Decorations !8800
  %1801 = icmp eq i32 %1799, 0		; visa id: 1726
  %1802 = select i1 %1801, i32 %1797, i32 %1800		; visa id: 1728
  %1803 = sitofp i32 %1802 to float		; visa id: 1729
  %1804 = fmul float %1461, %1803		; visa id: 1730
  br label %1813, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1731

1805:                                             ; preds = %1795
; BB198 :
  %1806 = uitofp i32 %1797 to float		; visa id: 1733
  %1807 = fmul float %1461, %1806		; visa id: 1734
  %1808 = and i32 %127, 1073741824
  %1809 = icmp eq i32 %1808, 0		; visa id: 1735
  %1810 = select i1 %1809, i32 1, i32 -1		; visa id: 1737
  %1811 = sitofp i32 %1810 to float		; visa id: 1738
  %1812 = fmul float %1807, %1811		; visa id: 1739
  br label %1813, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1740

1813:                                             ; preds = %1805, %1798
; BB199 :
  %.sroa.160.7 = phi float [ %1812, %1805 ], [ %1804, %1798 ]
  %1814 = lshr i32 %1688, 24		; visa id: 1741
  br i1 %1475, label %1821, label %1815, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1742

1815:                                             ; preds = %1813
; BB200 :
  %1816 = sub nsw i32 0, %1814, !spirv.Decorations !8800
  %1817 = icmp slt i32 %127, 0		; visa id: 1744
  %1818 = select i1 %1817, i32 %1816, i32 %1814		; visa id: 1745
  %1819 = sitofp i32 %1818 to float		; visa id: 1746
  %1820 = fmul float %1461, %1819		; visa id: 1747
  br label %1828, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1748

1821:                                             ; preds = %1813
; BB201 :
  %1822 = uitofp i32 %1814 to float		; visa id: 1750
  %1823 = fmul float %1461, %1822		; visa id: 1751
  %1824 = icmp sgt i32 %127, -1		; visa id: 1752
  %1825 = select i1 %1824, i32 1, i32 -1		; visa id: 1753
  %1826 = sitofp i32 %1825 to float		; visa id: 1754
  %1827 = fmul float %1823, %1826		; visa id: 1755
  br label %1828, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8784		; visa id: 1756

1828:                                             ; preds = %1821, %1815
; BB202 :
  %.sroa.184.7 = phi float [ %1827, %1821 ], [ %1820, %1815 ]
  %1829 = or i32 %315, 112		; visa id: 1757
  %1830 = zext i32 %1829 to i64		; visa id: 1758
  %1831 = add i64 %1830, %const_reg_qword2		; visa id: 1759
  %IntToPtr2323 = inttoptr i64 %1831 to ptr addrspace(1)		; visa id: 1760
  %vCastload324 = load i32, ptr addrspace(1) %IntToPtr2323, align 2		; visa id: 1760
  %1832 = add i64 %1831, 4
  %IntToPtr2325 = inttoptr i64 %1832 to ptr addrspace(1)
  %vCastload326 = load i32, ptr addrspace(1) %IntToPtr2325, align 2		; visa id: 1761
  %1833 = add i64 %1831, 8
  %IntToPtr2327 = inttoptr i64 %1833 to ptr addrspace(1)
  %vCastload328 = load i32, ptr addrspace(1) %IntToPtr2327, align 2		; visa id: 1762
  %1834 = add i64 %1831, 12
  %IntToPtr2329 = inttoptr i64 %1834 to ptr addrspace(1)
  %vCastload330 = load i32, ptr addrspace(1) %IntToPtr2329, align 2		; visa id: 1763
  %1835 = bitcast i32 %vCastload324 to <2 x i16>		; visa id: 1764
  %1836 = bitcast i32 %vCastload326 to <2 x i16>		; visa id: 1766
  %1837 = extractelement <2 x i16> %1835, i32 0		; visa id: 1768
  %1838 = extractelement <2 x i16> %1835, i32 1		; visa id: 1768
  %1839 = extractelement <2 x i16> %1836, i32 0		; visa id: 1768
  %1840 = extractelement <2 x i16> %1836, i32 1		; visa id: 1768
  %1841 = bitcast i32 %vCastload328 to <2 x i16>		; visa id: 1768
  %1842 = bitcast i32 %vCastload330 to <2 x i16>		; visa id: 1770
  %1843 = extractelement <2 x i16> %1841, i32 0		; visa id: 1772
  %1844 = extractelement <2 x i16> %1841, i32 1		; visa id: 1772
  %1845 = extractelement <2 x i16> %1842, i32 0		; visa id: 1772
  %1846 = extractelement <2 x i16> %1842, i32 1		; visa id: 1772
  %1847 = zext i16 %1837 to i32		; visa id: 1772
  %1848 = shl nuw i32 %1847, 16, !spirv.Decorations !8781		; visa id: 1773
  %1849 = bitcast i32 %1848 to float
  %1850 = fmul float %.sroa.0121.7, %1849		; visa id: 1774
  %1851 = fadd float %.sroa.36.0, %1850		; visa id: 1775
  %1852 = zext i16 %1838 to i32		; visa id: 1776
  %1853 = shl nuw i32 %1852, 16, !spirv.Decorations !8781		; visa id: 1777
  %1854 = bitcast i32 %1853 to float
  %1855 = fmul float %.sroa.40.7, %1854		; visa id: 1778
  %1856 = fadd float %1851, %1855		; visa id: 1779
  %1857 = zext i16 %1839 to i32		; visa id: 1780
  %1858 = shl nuw i32 %1857, 16, !spirv.Decorations !8781		; visa id: 1781
  %1859 = bitcast i32 %1858 to float
  %1860 = fmul float %.sroa.64136.7, %1859		; visa id: 1782
  %1861 = fadd float %1856, %1860		; visa id: 1783
  %1862 = zext i16 %1840 to i32		; visa id: 1784
  %1863 = shl nuw i32 %1862, 16, !spirv.Decorations !8781		; visa id: 1785
  %1864 = bitcast i32 %1863 to float
  %1865 = fmul float %.sroa.88.7, %1864		; visa id: 1786
  %1866 = fadd float %1861, %1865		; visa id: 1787
  %1867 = zext i16 %1843 to i32		; visa id: 1788
  %1868 = shl nuw i32 %1867, 16, !spirv.Decorations !8781		; visa id: 1789
  %1869 = bitcast i32 %1868 to float
  %1870 = fmul float %.sroa.112151.7, %1869		; visa id: 1790
  %1871 = fadd float %1866, %1870		; visa id: 1791
  %1872 = zext i16 %1844 to i32		; visa id: 1792
  %1873 = shl nuw i32 %1872, 16, !spirv.Decorations !8781		; visa id: 1793
  %1874 = bitcast i32 %1873 to float
  %1875 = fmul float %.sroa.136.7, %1874		; visa id: 1794
  %1876 = fadd float %1871, %1875		; visa id: 1795
  %1877 = zext i16 %1845 to i32		; visa id: 1796
  %1878 = shl nuw i32 %1877, 16, !spirv.Decorations !8781		; visa id: 1797
  %1879 = bitcast i32 %1878 to float
  %1880 = fmul float %.sroa.160.7, %1879		; visa id: 1798
  %1881 = fadd float %1876, %1880		; visa id: 1799
  %1882 = zext i16 %1846 to i32		; visa id: 1800
  %1883 = shl nuw i32 %1882, 16, !spirv.Decorations !8781		; visa id: 1801
  %1884 = bitcast i32 %1883 to float
  %1885 = fmul float %.sroa.184.7, %1884		; visa id: 1802
  %1886 = fadd float %1881, %1885		; visa id: 1803
  %1887 = icmp ult i32 %117, 9		; visa id: 1804
  br i1 %1887, label %..preheader1.preheader_crit_edge, label %.preheader.preheader, !stats.blockFrequency.digits !8798, !stats.blockFrequency.scale !8799		; visa id: 1805

..preheader1.preheader_crit_edge:                 ; preds = %1828
; BB203 :
  %1888 = add nuw nsw i32 %117, 1, !spirv.Decorations !8791		; visa id: 1807
  br label %.preheader1.preheader, !stats.blockFrequency.digits !8801, !stats.blockFrequency.scale !8799		; visa id: 1808

.preheader.preheader:                             ; preds = %1828
; BB204 :
  %.lcssa337 = phi float [ %1886, %1828 ]
  %.lcssa336 = phi float [ %1675, %1828 ]
  %.lcssa335 = phi float [ %1452, %1828 ]
  %.lcssa334 = phi float [ %1241, %1828 ]
  %.lcssa333 = phi float [ %1018, %1828 ]
  %.lcssa332 = phi float [ %807, %1828 ]
  %.lcssa331 = phi float [ %583, %1828 ]
  %.lcssa = phi float [ %372, %1828 ]
  %1889 = fadd float %.lcssa, %.lcssa331		; visa id: 1810
  %1890 = fadd float %.lcssa332, %.lcssa333		; visa id: 1811
  %1891 = fadd float %.lcssa334, %.lcssa335		; visa id: 1812
  %1892 = fadd float %.lcssa336, %.lcssa337		; visa id: 1813
  %1893 = fadd float %1889, %1890		; visa id: 1814
  %1894 = fadd float %1891, %1892		; visa id: 1815
  %1895 = fadd float %1893, %1894		; visa id: 1816
  br label %._crit_edge, !stats.blockFrequency.digits !8783, !stats.blockFrequency.scale !8790		; visa id: 1819

._crit_edge:                                      ; preds = %.._crit_edge_crit_edge, %precompiled_u32divrem_sp.exit.._crit_edge_crit_edge, %._crit_edge43, %.preheader.preheader
; BB205 :
  %1896 = phi i32 [ -1, %.preheader.preheader ], [ 0, %._crit_edge43 ], [ 0, %precompiled_u32divrem_sp.exit.._crit_edge_crit_edge ], [ 0, %.._crit_edge_crit_edge ]
  %1897 = phi i32 [ 0, %.preheader.preheader ], [ %60, %._crit_edge43 ], [ -1, %precompiled_u32divrem_sp.exit.._crit_edge_crit_edge ], [ -1, %.._crit_edge_crit_edge ]
  %1898 = phi float [ %1895, %.preheader.preheader ], [ 0.000000e+00, %._crit_edge43 ], [ 0.000000e+00, %precompiled_u32divrem_sp.exit.._crit_edge_crit_edge ], [ 0.000000e+00, %.._crit_edge_crit_edge ]
  %1899 = add nuw nsw i32 %simdLaneId, 1		; visa id: 1820
  %1900 = and i32 %1899, 31		; visa id: 1821
  %simdShuffle = call float @llvm.genx.GenISA.WaveShuffleIndex.f32(float %1898, i32 %1900, i32 0)		; visa id: 1822
  %1901 = and i32 %simdLaneId, 1
  %1902 = icmp eq i32 %1901, 0		; visa id: 1829
  %1903 = select i1 %1902, float %simdShuffle, float -0.000000e+00		; visa id: 1831
  %1904 = fadd float %1898, %1903		; visa id: 1832
  %1905 = add nuw nsw i32 %simdLaneId, 2		; visa id: 1833
  %1906 = and i32 %1905, 31		; visa id: 1834
  %simdShuffle.1 = call float @llvm.genx.GenISA.WaveShuffleIndex.f32(float %1904, i32 %1906, i32 0)		; visa id: 1835
  %1907 = icmp ne i32 %5, 0		; visa id: 1842
  %1908 = or i1 %29, %1907		; visa id: 1843
  br i1 %1908, label %._crit_edge.._crit_edge44_crit_edge, label %1909, !stats.blockFrequency.digits !8783, !stats.blockFrequency.scale !8784		; visa id: 1845

._crit_edge.._crit_edge44_crit_edge:              ; preds = %._crit_edge
; BB:
  br label %._crit_edge44, !stats.blockFrequency.digits !8783, !stats.blockFrequency.scale !8789

1909:                                             ; preds = %._crit_edge
; BB207 :
  %1910 = icmp eq i32 %5, 0		; visa id: 1847
  %1911 = select i1 %1910, float %simdShuffle.1, float -0.000000e+00		; visa id: 1848
  %1912 = fadd float %1904, %1911		; visa id: 1849
  %1913 = bitcast float %1912 to i32
  %1914 = icmp ne i32 %1896, 0		; visa id: 1850
  %1915 = select i1 %1914, i32 %1913, i32 2143289344		; visa id: 1851
  %1916 = and i32 %1915, 2147483647		; visa id: 1852
  %1917 = icmp ugt i32 %1916, 2139095040		; visa id: 1853
  br i1 %1917, label %1925, label %1918, !stats.blockFrequency.digits !8783, !stats.blockFrequency.scale !8789		; visa id: 1854

1918:                                             ; preds = %1909
; BB208 :
  %1919 = lshr i32 %1915, 16		; visa id: 1856
  %1920 = and i32 %1919, 1		; visa id: 1857
  %1921 = add i32 %1915, %1920
  %1922 = add i32 %1921, 32767		; visa id: 1858
  %1923 = lshr i32 %1922, 16		; visa id: 1859
  %1924 = trunc i32 %1923 to i16		; visa id: 1860
  br label %1929, !stats.blockFrequency.digits !8783, !stats.blockFrequency.scale !8786		; visa id: 1861

1925:                                             ; preds = %1909
; BB209 :
  %1926 = lshr i32 %1915, 16		; visa id: 1863
  %1927 = trunc i32 %1926 to i16		; visa id: 1864
  %1928 = or i16 %1927, 64		; visa id: 1865
  br label %1929, !stats.blockFrequency.digits !8783, !stats.blockFrequency.scale !8786		; visa id: 1866

1929:                                             ; preds = %1918, %1925
; BB210 :
  %1930 = phi i16 [ %1928, %1925 ], [ %1924, %1918 ]
  %1931 = bitcast i64 %const_reg_qword12 to <2 x i32>		; visa id: 1867
  %1932 = extractelement <2 x i32> %1931, i32 0		; visa id: 1868
  %1933 = extractelement <2 x i32> %1931, i32 1		; visa id: 1868
  %1934 = bitcast i64 %const_reg_qword13 to <2 x i32>		; visa id: 1868
  %1935 = extractelement <2 x i32> %1934, i32 0		; visa id: 1869
  %1936 = extractelement <2 x i32> %1934, i32 1		; visa id: 1869
  %1937 = icmp eq i32 %7, 0		; visa id: 1869
  %1938 = select i1 %1937, i32 %1932, i32 %1935		; visa id: 1870
  %1939 = select i1 %1937, i32 %1933, i32 %1936		; visa id: 1871
  %1940 = insertelement <2 x i32> undef, i32 %1938, i32 0		; visa id: 1872
  %1941 = insertelement <2 x i32> %1940, i32 %1939, i32 1		; visa id: 1873
  %1942 = bitcast <2 x i32> %1941 to i64		; visa id: 1874
  %1943 = zext i32 %12 to i64		; visa id: 1878
  %1944 = shl nuw nsw i64 %1943, 1		; visa id: 1879
  %1945 = add i64 %1942, %1944		; visa id: 1880
  %1946 = inttoptr i64 %1945 to ptr addrspace(4)		; visa id: 1881
  %1947 = addrspacecast ptr addrspace(4) %1946 to ptr addrspace(1)		; visa id: 1881
  store i16 %1930, ptr addrspace(1) %1947, align 2		; visa id: 1882
  %1948 = icmp eq i32 %12, %28		; visa id: 1884
  br i1 %1948, label %1949, label %.._crit_edge44_crit_edge, !stats.blockFrequency.digits !8783, !stats.blockFrequency.scale !8789		; visa id: 1885

.._crit_edge44_crit_edge:                         ; preds = %1929
; BB:
  br label %._crit_edge44, !stats.blockFrequency.digits !8783, !stats.blockFrequency.scale !8786

1949:                                             ; preds = %1929
; BB212 :
  %1950 = bitcast i64 %const_reg_qword17 to <2 x i32>		; visa id: 1887
  %1951 = extractelement <2 x i32> %1950, i32 0		; visa id: 1888
  %1952 = extractelement <2 x i32> %1950, i32 1		; visa id: 1888
  %1953 = bitcast i64 %const_reg_qword18 to <2 x i32>		; visa id: 1888
  %1954 = extractelement <2 x i32> %1953, i32 0		; visa id: 1889
  %1955 = extractelement <2 x i32> %1953, i32 1		; visa id: 1889
  %1956 = icmp ne i32 %1897, 0		; visa id: 1889
  %1957 = sext i1 %1956 to i32		; visa id: 1890
  %1958 = sub i32 0, %1957		; visa id: 1891
  %1959 = select i1 %1937, i32 %1951, i32 %1954		; visa id: 1892
  %1960 = select i1 %1937, i32 %1952, i32 %1955		; visa id: 1893
  %1961 = insertelement <2 x i32> undef, i32 %1959, i32 0		; visa id: 1894
  %1962 = insertelement <2 x i32> %1961, i32 %1960, i32 1		; visa id: 1895
  %1963 = bitcast <2 x i32> %1962 to i64		; visa id: 1896
  %1964 = zext i32 %retval.0.i to i64		; visa id: 1900
  %1965 = shl nuw nsw i64 %1964, 2		; visa id: 1901
  %1966 = add i64 %1963, %1965		; visa id: 1902
  %1967 = inttoptr i64 %1966 to ptr addrspace(4)		; visa id: 1903
  %1968 = addrspacecast ptr addrspace(4) %1967 to ptr addrspace(1)		; visa id: 1903
  store i32 %1958, ptr addrspace(1) %1968, align 4		; visa id: 1904
  br i1 %1956, label %1969, label %.._crit_edge44_crit_edge267, !stats.blockFrequency.digits !8783, !stats.blockFrequency.scale !8786		; visa id: 1905

.._crit_edge44_crit_edge267:                      ; preds = %1949
; BB:
  br label %._crit_edge44, !stats.blockFrequency.digits !8802, !stats.blockFrequency.scale !8803

1969:                                             ; preds = %1949
; BB214 :
  %1970 = inttoptr i64 %const_reg_qword20 to ptr addrspace(4)		; visa id: 1907
  %1971 = addrspacecast ptr addrspace(4) %1970 to ptr addrspace(1)		; visa id: 1907
  %1972 = load i32, ptr addrspace(1) %1971, align 4		; visa id: 1908
  %1973 = icmp eq i32 %1972, 0		; visa id: 1909
  br i1 %1973, label %.._crit_edge44_crit_edge268, label %1974, !stats.blockFrequency.digits !8804, !stats.blockFrequency.scale !8805		; visa id: 1910

.._crit_edge44_crit_edge268:                      ; preds = %1969
; BB:
  br label %._crit_edge44, !stats.blockFrequency.digits !8806, !stats.blockFrequency.scale !8803

1974:                                             ; preds = %1969
; BB216 :
  %1975 = inttoptr i64 %const_reg_qword19 to ptr addrspace(4)		; visa id: 1912
  %1976 = addrspacecast ptr addrspace(4) %1975 to ptr addrspace(1)		; visa id: 1912
  %1977 = call i32 @llvm.genx.GenISA.icmpxchgatomicrawA64.i32.p1.p1(ptr addrspace(1) %1976, ptr addrspace(1) %1976, i32 0, i32 1)		; visa id: 1913
  br label %._crit_edge44, !stats.blockFrequency.digits !8807, !stats.blockFrequency.scale !8803		; visa id: 1918

._crit_edge44:                                    ; preds = %.._crit_edge44_crit_edge268, %.._crit_edge44_crit_edge267, %.._crit_edge44_crit_edge, %._crit_edge.._crit_edge44_crit_edge, %1974
; BB217 :
  ret void, !stats.blockFrequency.digits !8783, !stats.blockFrequency.scale !8784		; visa id: 1919
}
