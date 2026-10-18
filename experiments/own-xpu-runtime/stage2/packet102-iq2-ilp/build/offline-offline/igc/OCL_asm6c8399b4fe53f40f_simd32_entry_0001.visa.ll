; ------------------------------------------------
; OCL_asm6c8399b4fe53f40f_simd32_entry_0001.visa.ll
; ------------------------------------------------
; Function Attrs: convergent nounwind
define spir_kernel void @_ZTSZZNK11p49dvirtual6KernelILN3iq34TypeE22ELj2560ELj2EE17submit_stream_armILj2EEEN4sycl3_V15eventERNS6_5queueESt4spanIKPvLm18446744073709551615EERKSt6vectorIS7_SaIS7_EEENKUlRNS6_7handlerEE_clESK_EUlNS6_7nd_itemILi1EEEE_(ptr byval(%"struct.p39::__generated_Bound") align 8 %0, i32 %1, <8 x i32> %r0, <3 x i32> %globalOffset, i16 %localIdX, i16 %localIdY, i16 %localIdZ, ptr addrspace(2) %constBase, ptr addrspace(1) %globalBase, ptr %privateBase, i64 %const_reg_qword, i64 %const_reg_qword1, i64 %const_reg_qword2, i64 %const_reg_qword3, i64 %const_reg_qword4, i64 %const_reg_qword5, i64 %const_reg_qword6, i64 %const_reg_qword7, i64 %const_reg_qword8, i64 %const_reg_qword9, i64 %const_reg_qword10, i64 %const_reg_qword11, i64 %const_reg_qword12, i64 %const_reg_qword13, i64 %const_reg_qword14, i64 %const_reg_qword15, i64 %const_reg_qword16, i64 %const_reg_qword17, i64 %const_reg_qword18, i64 %const_reg_qword19, i64 %const_reg_qword20, i32 %const_reg_dword, i32 %const_reg_dword21, i32 %const_reg_dword22, i32 %const_reg_dword23, i32 %const_reg_dword24, i32 %bindlessOffset, i32 %bindlessOffset25) #0 {
; BB0 :
  %3 = extractelement <8 x i32> %r0, i32 1		; visa id: 2
  %simdLaneId16 = call i16 @llvm.genx.GenISA.simdLaneId()		; visa id: 2
  %4 = lshr i16 %localIdX, 5		; visa id: 5
  %5 = and i16 %4, 1		; visa id: 6
  %simdLaneId = zext i16 %simdLaneId16 to i32		; visa id: 7
  %6 = and i32 %simdLaneId, 3		; visa id: 8
  %7 = shl i32 %3, 5		; visa id: 9
  %8 = lshr i16 %localIdX, 3		; visa id: 10
  %9 = and i16 %8, 8184		; visa id: 11
  %10 = zext i16 %9 to i32		; visa id: 12
  %11 = add i32 %7, %10		; visa id: 13
  %12 = lshr i32 %simdLaneId, 2		; visa id: 14
  %13 = or i32 %12, %11		; visa id: 15
  %tobool.i = icmp eq i32 %const_reg_dword21, 0		; visa id: 16
  br i1 %tobool.i, label %.precompiled_u32divrem_sp.exit_crit_edge, label %if.end.i, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8782		; visa id: 17

.precompiled_u32divrem_sp.exit_crit_edge:         ; preds = %2
; BB1 :
  br label %precompiled_u32divrem_sp.exit, !stats.blockFrequency.digits !8783, !stats.blockFrequency.scale !8784		; visa id: 20

if.end.i:                                         ; preds = %2
; BB2 :
  %14 = call float @llvm.genx.GenISA.uitof.rtz.f32.i32(i32 %const_reg_dword21)		; visa id: 22
  %conv.i = fptoui float %14 to i32		; visa id: 24
  %sub.i = sub i32 %const_reg_dword21, %conv.i		; visa id: 25
  %15 = call float @llvm.genx.GenISA.uitof.rtz.f32.i32(i32 %13)		; visa id: 26
  %div.i = fdiv float 1.000000e+00, %14, !fpmath !8785		; visa id: 27
  %16 = call float @llvm.genx.GenISA.fma.rtz.f32.f32.f32.f32(float %div.i, float 0xBE98000000000000, float %div.i)		; visa id: 28
  %17 = call float @llvm.genx.GenISA.mul.rtz.f32.f32.f32(float %15, float %16)		; visa id: 29
  %conv3.i = fptoui float %15 to i32		; visa id: 30
  %sub4.i = sub i32 %13, %conv3.i		; visa id: 31
  %conv8.i = fptoui float %17 to i32		; visa id: 32
  %18 = call float @llvm.genx.GenISA.uitof.rtz.f32.i32(i32 %sub.i)		; visa id: 33
  %19 = call float @llvm.genx.GenISA.uitof.rtz.f32.i32(i32 %sub4.i)		; visa id: 34
  %20 = call float @llvm.genx.GenISA.uitof.rtz.f32.i32(i32 %conv8.i)		; visa id: 35
  %21 = fsub float 0.000000e+00, %14		; visa id: 36
  %22 = call float @llvm.genx.GenISA.fma.rtz.f32.f32.f32.f32(float %21, float %20, float %15)		; visa id: 37
  %23 = fsub float 0.000000e+00, %18		; visa id: 38
  %24 = call float @llvm.genx.GenISA.fma.rtz.f32.f32.f32.f32(float %23, float %20, float %19)		; visa id: 39
  %25 = call float @llvm.genx.GenISA.add.rtz.f32.f32.f32(float %22, float %24)		; visa id: 40
  %26 = call float @llvm.genx.GenISA.mul.rtz.f32.f32.f32(float %16, float %25)		; visa id: 41
  %conv16.i = fptoui float %26 to i32		; visa id: 43
  %add.i = add i32 %conv16.i, %conv8.i		; visa id: 44
  %mul.i = mul i32 %add.i, %const_reg_dword21		; visa id: 45
  %sub17.i = sub i32 %13, %mul.i		; visa id: 46
  %cmp.i = icmp uge i32 %sub17.i, %const_reg_dword21
  %27 = sext i1 %cmp.i to i32		; visa id: 47
  %28 = sub i32 0, %27
  %add19.i = add i32 %add.i, %28		; visa id: 48
  br label %precompiled_u32divrem_sp.exit, !stats.blockFrequency.digits !8786, !stats.blockFrequency.scale !8787		; visa id: 49

precompiled_u32divrem_sp.exit:                    ; preds = %.precompiled_u32divrem_sp.exit_crit_edge, %if.end.i
; BB3 :
  %retval.0.i = phi i32 [ %add19.i, %if.end.i ], [ -1, %.precompiled_u32divrem_sp.exit_crit_edge ]
  %29 = mul i32 %retval.0.i, %const_reg_dword21		; visa id: 50
  %30 = icmp uge i32 %13, %1
  %31 = icmp uge i32 %13, %1		; visa id: 51
  br i1 %31, label %precompiled_u32divrem_sp.exit.._crit_edge_crit_edge, label %32, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8782		; visa id: 52

precompiled_u32divrem_sp.exit.._crit_edge_crit_edge: ; preds = %precompiled_u32divrem_sp.exit
; BB4 :
  br label %._crit_edge, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 57

32:                                               ; preds = %precompiled_u32divrem_sp.exit
; BB5 :
  %33 = call { i32, i32 } @llvm.genx.GenISA.mul.pair(i32 %retval.0.i, i32 0, i32 12, i32 0)
  %34 = extractvalue { i32, i32 } %33, 0
  %35 = extractvalue { i32, i32 } %33, 1
  %36 = insertelement <2 x i32> undef, i32 %34, i32 0
  %37 = insertelement <2 x i32> %36, i32 %35, i32 1
  %38 = bitcast <2 x i32> %37 to i64		; visa id: 59
  %39 = add i64 %38, %const_reg_qword16		; visa id: 67
  %40 = inttoptr i64 %39 to ptr addrspace(4)		; visa id: 68
  %41 = addrspacecast ptr addrspace(4) %40 to ptr addrspace(1)		; visa id: 68
  %42 = load <2 x i32>, ptr addrspace(1) %41, align 4		; visa id: 69
  %43 = extractelement <2 x i32> %42, i32 0		; visa id: 70
  %44 = extractelement <2 x i32> %42, i32 1		; visa id: 70
  %45 = icmp uge i32 %43, %const_reg_dword23
  %46 = icmp ugt i32 %44, %const_reg_dword21		; visa id: 70
  %47 = or i1 %45, %46		; visa id: 71
  br i1 %47, label %.._crit_edge_crit_edge, label %48, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 73

.._crit_edge_crit_edge:                           ; preds = %32
; BB6 :
  br label %._crit_edge, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 78

48:                                               ; preds = %32
; BB7 :
  %49 = sub i32 %13, %29		; visa id: 80
  %50 = add i64 %39, 8		; visa id: 81
  %51 = inttoptr i64 %50 to ptr addrspace(4)		; visa id: 82
  %52 = addrspacecast ptr addrspace(4) %51 to ptr addrspace(1)		; visa id: 82
  %53 = load i32, ptr addrspace(1) %52, align 4		; visa id: 83
  %54 = sub nuw i32 %const_reg_dword21, %44, !spirv.Decorations !8788		; visa id: 84
  %55 = icmp ule i32 %53, %54
  %56 = icmp ule i32 %53, %const_reg_dword21		; visa id: 85
  %57 = and i1 %55, %56		; visa id: 86
  %58 = icmp ult i32 %49, %53		; visa id: 88
  %59 = and i1 %57, %58		; visa id: 89
  br i1 %59, label %62, label %._crit_edge44, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 90

._crit_edge44:                                    ; preds = %48
; BB8 :
  %60 = xor i1 %57, true		; visa id: 92
  %61 = sext i1 %60 to i32		; visa id: 93
  br label %._crit_edge, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8790		; visa id: 96

62:                                               ; preds = %48
; BB9 :
  %63 = bitcast i64 %const_reg_qword to <2 x i32>		; visa id: 98
  %64 = extractelement <2 x i32> %63, i32 0		; visa id: 99
  %65 = extractelement <2 x i32> %63, i32 1		; visa id: 99
  %66 = bitcast i64 %const_reg_qword1 to <2 x i32>		; visa id: 99
  %67 = extractelement <2 x i32> %66, i32 0		; visa id: 100
  %68 = extractelement <2 x i32> %66, i32 1		; visa id: 100
  %69 = call { i32, i32 } @llvm.genx.GenISA.mul.pair(i32 %43, i32 0, i32 %const_reg_dword21, i32 0)
  %70 = extractvalue { i32, i32 } %69, 0
  %71 = extractvalue { i32, i32 } %69, 1
  %72 = insertelement <2 x i32> undef, i32 %70, i32 0
  %73 = insertelement <2 x i32> %72, i32 %71, i32 1
  %74 = bitcast <2 x i32> %73 to i64		; visa id: 100
  %75 = zext i32 %44 to i64		; visa id: 108
  %76 = add nuw i64 %74, %75, !spirv.Decorations !8788		; visa id: 109
  %77 = zext i32 %49 to i64		; visa id: 110
  %78 = add nuw i64 %76, %77, !spirv.Decorations !8788		; visa id: 111
  %79 = bitcast i64 %78 to <2 x i32>		; visa id: 112
  %80 = extractelement <2 x i32> %79, i32 0		; visa id: 116
  %81 = extractelement <2 x i32> %79, i32 1		; visa id: 116
  %82 = icmp eq i16 %5, 0		; visa id: 116
  %83 = select i1 %82, i32 %64, i32 %67		; visa id: 117
  %84 = select i1 %82, i32 %65, i32 %68		; visa id: 118
  %85 = insertelement <2 x i32> undef, i32 %83, i32 0		; visa id: 119
  %86 = insertelement <2 x i32> %85, i32 %84, i32 1		; visa id: 120
  %87 = bitcast <2 x i32> %86 to i64		; visa id: 121
  %88 = call { i32, i32 } @llvm.genx.GenISA.mul.pair(i32 %80, i32 %81, i32 %const_reg_dword, i32 0)
  %89 = extractvalue { i32, i32 } %88, 0
  %90 = extractvalue { i32, i32 } %88, 1
  %91 = insertelement <2 x i32> undef, i32 %89, i32 0
  %92 = insertelement <2 x i32> %91, i32 %90, i32 1
  %93 = bitcast <2 x i32> %92 to i64		; visa id: 125
  %94 = add i64 %87, %93		; visa id: 133
  %95 = load <8 x float>, ptr addrspace(2) %constBase, align 8		; visa id: 134
  %96 = extractelement <8 x float> %95, i32 0		; visa id: 136
  %97 = extractelement <8 x float> %95, i32 1		; visa id: 136
  %98 = extractelement <8 x float> %95, i32 2		; visa id: 136
  %99 = extractelement <8 x float> %95, i32 3		; visa id: 136
  %100 = extractelement <8 x float> %95, i32 4		; visa id: 136
  %101 = extractelement <8 x float> %95, i32 5		; visa id: 136
  %102 = extractelement <8 x float> %95, i32 6		; visa id: 136
  %103 = extractelement <8 x float> %95, i32 7		; visa id: 136
  %104 = shl nuw nsw i32 %6, 6, !spirv.Decorations !8791		; visa id: 136
  %105 = add i32 %104, 8		; visa id: 137
  %106 = add i32 %104, 16		; visa id: 138
  %107 = add i32 %104, 24		; visa id: 139
  %108 = add i32 %104, 32		; visa id: 140
  %109 = add i32 %104, 40		; visa id: 141
  %110 = add i32 %104, 48		; visa id: 142
  %111 = add i32 %104, 56		; visa id: 143
  br label %NodeBlock, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8790		; visa id: 156

NodeBlock:                                        ; preds = %.NodeBlock_crit_edge, %62
; BB10 :
  %.sroa.36.0 = phi float [ %103, %62 ], [ %2117, %.NodeBlock_crit_edge ]
  %.sroa.31.0 = phi float [ %102, %62 ], [ %1868, %.NodeBlock_crit_edge ]
  %.sroa.28.0 = phi float [ %101, %62 ], [ %1619, %.NodeBlock_crit_edge ]
  %.sroa.21.0 = phi float [ %100, %62 ], [ %1370, %.NodeBlock_crit_edge ]
  %.sroa.18.0 = phi float [ %99, %62 ], [ %1122, %.NodeBlock_crit_edge ]
  %.sroa.13.0 = phi float [ %98, %62 ], [ %880, %.NodeBlock_crit_edge ]
  %.sroa.10.0 = phi float [ %97, %62 ], [ %637, %.NodeBlock_crit_edge ]
  %.sroa.0.0 = phi float [ %96, %62 ], [ %394, %.NodeBlock_crit_edge ]
  %112 = phi i32 [ 0, %62 ], [ %2119, %.NodeBlock_crit_edge ]
  %113 = mul nsw i32 %112, -56		; visa id: 157
  %114 = shl nuw nsw i32 %112, 8, !spirv.Decorations !8791		; visa id: 158
  %115 = shl nuw nsw i32 %112, 6, !spirv.Decorations !8791		; visa id: 159
  %116 = zext i32 %115 to i64		; visa id: 160
  %117 = add i64 %94, %116		; visa id: 161
  %118 = sext i32 %113 to i64		; visa id: 162
  %119 = add i64 %117, %118		; visa id: 163
  %120 = add i64 %119, 640		; visa id: 164
  %121 = shl nuw nsw i32 %112, 1, !spirv.Decorations !8791		; visa id: 165
  %122 = zext i32 %121 to i64		; visa id: 166
  %sink_402 = add i64 %94, 800		; visa id: 167
  %123 = add i64 %sink_402, %122		; visa id: 168
  %124 = inttoptr i64 %123 to ptr addrspace(4)		; visa id: 169
  %125 = add i64 %119, 720		; visa id: 169
  %126 = addrspacecast ptr addrspace(4) %124 to ptr addrspace(1)		; visa id: 170
  %127 = load i16, ptr addrspace(1) %126, align 2, !noalias !8793		; visa id: 171
  %sink_416 = shl nuw nsw i32 %simdLaneId, 4		; visa id: 173
  %sink_410 = and i32 %sink_416, 48		; visa id: 174
  %sink_396 = zext i32 %sink_410 to i64		; visa id: 175
  %128 = add i64 %117, %sink_396		; visa id: 176
  %129 = inttoptr i64 %128 to ptr addrspace(4)		; visa id: 177
  %130 = addrspacecast ptr addrspace(4) %129 to ptr addrspace(1)		; visa id: 177
  %131 = load i16, ptr addrspace(1) %130, align 2, !noalias !8793		; visa id: 178
  %sink_415 = shl nuw nsw i32 %6, 1		; visa id: 180
  %sink_401 = zext i32 %sink_415 to i64		; visa id: 181
  %132 = add i64 %120, %sink_401		; visa id: 182
  %133 = inttoptr i64 %132 to ptr addrspace(4)		; visa id: 183
  %134 = addrspacecast ptr addrspace(4) %133 to ptr addrspace(1)		; visa id: 183
  %135 = load i8, ptr addrspace(1) %134, align 1, !noalias !8793		; visa id: 184
  %136 = sext i16 %127 to i32		; visa id: 185
  %137 = and i32 %136, -2147483648		; visa id: 186
  %138 = zext i16 %127 to i32		; visa id: 187
  %139 = lshr i32 %138, 10		; visa id: 187
  %140 = and i32 %139, 31		; visa id: 188
  %141 = and i32 %138, 1023		; visa id: 189
  %142 = shl nuw nsw i32 %140, 23		; visa id: 190
  %143 = add nuw nsw i32 %142, 939524096		; visa id: 191
  %144 = shl nuw nsw i32 %141, 13		; visa id: 192
  %145 = or i32 %143, %144
  %146 = or i32 %145, %137		; visa id: 193
  %147 = icmp eq i32 %141, 0		; visa id: 194
  %148 = icmp eq i32 %141, 0		; visa id: 195
  %149 = select i1 %148, i32 0, i32 4194304		; visa id: 196
  %150 = or i32 %137, %149
  %151 = or i32 %150, 2139095040		; visa id: 197
  %152 = or i32 %114, %104		; visa id: 198
  %153 = zext i16 %131 to i32		; visa id: 199
  %154 = and i32 %153, 255
  %155 = zext i8 %135 to i32		; visa id: 200
  %156 = shl nuw nsw i32 %155, 8, !spirv.Decorations !8791		; visa id: 200
  %157 = and i32 %156, 768		; visa id: 201
  %158 = or i32 %154, %157		; visa id: 202
  %Pivot.not = icmp eq i32 %140, 31
  %.mux = select i1 %Pivot.not, i32 %151, i32 %146		; visa id: 203
  %159 = icmp ne i32 %140, 0
  %160 = or i1 %159, %147		; visa id: 205
  %161 = icmp ne i32 %140, 0
  %.mux.mux = select i1 %161, i32 %.mux, i32 %137		; visa id: 207
  br i1 %160, label %NodeBlock.._crit_edge45_crit_edge, label %.preheader1.preheader, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 209

.preheader1.preheader:                            ; preds = %NodeBlock
; BB11 :
  br label %.preheader1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 213

.preheader1:                                      ; preds = %.preheader1..preheader1_crit_edge, %.preheader1.preheader
; BB12 :
  %162 = phi i32 [ %164, %.preheader1..preheader1_crit_edge ], [ -14, %.preheader1.preheader ]
  %163 = phi i32 [ %167, %.preheader1..preheader1_crit_edge ], [ %141, %.preheader1.preheader ]
  %164 = add nsw i32 %162, -1, !spirv.Decorations !8798		; visa id: 214
  %165 = and i32 %163, 512
  %166 = icmp eq i32 %165, 0		; visa id: 215
  br i1 %166, label %.preheader1..preheader1_crit_edge, label %168, !stats.blockFrequency.digits !8799, !stats.blockFrequency.scale !8800		; visa id: 218

.preheader1..preheader1_crit_edge:                ; preds = %.preheader1
; BB13 :
  %167 = shl i32 %163, 1		; visa id: 220
  br label %.preheader1, !stats.blockFrequency.digits !8801, !stats.blockFrequency.scale !8802		; visa id: 221

168:                                              ; preds = %.preheader1
; BB14 :
  %.lcssa454 = phi i32 [ %163, %.preheader1 ]
  %.lcssa = phi i32 [ %164, %.preheader1 ]
  %169 = shl i32 %.lcssa, 23		; visa id: 223
  %170 = add i32 %169, 1065353216		; visa id: 224
  %171 = shl i32 %.lcssa454, 14		; visa id: 225
  %172 = and i32 %171, 8372224		; visa id: 226
  %173 = or i32 %170, %172
  %174 = or i32 %173, %137		; visa id: 227
  br label %._crit_edge45, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 229

NodeBlock.._crit_edge45_crit_edge:                ; preds = %NodeBlock
; BB15 :
  br label %._crit_edge45, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 232

._crit_edge45:                                    ; preds = %NodeBlock.._crit_edge45_crit_edge, %168
; BB16 :
  %175 = phi i32 [ %174, %168 ], [ %.mux.mux, %NodeBlock.._crit_edge45_crit_edge ]
  %176 = bitcast i32 %175 to float
  %177 = add i64 %125, %sink_401		; visa id: 233
  %178 = inttoptr i64 %177 to ptr addrspace(4)		; visa id: 234
  %179 = addrspacecast ptr addrspace(4) %178 to ptr addrspace(1)		; visa id: 234
  %180 = load i8, ptr addrspace(1) %179, align 1, !noalias !8793		; visa id: 235
  %b2s = sext i8 %180 to i16		; visa id: 237
  %181 = shl nuw nsw i32 %158, 3, !spirv.Decorations !8791		; visa id: 238
  %182 = zext i32 %181 to i64		; visa id: 239
  %sink_395 = ptrtoint ptr addrspace(1) %globalBase to i64		; visa id: 240
  %183 = add i64 %sink_395, %182		; visa id: 240
  %184 = inttoptr i64 %183 to ptr addrspace(1)		; visa id: 241
  %185 = load <2 x i32>, ptr addrspace(1) %184, align 4		; visa id: 241
  %b2s417 = and i16 %b2s, 15		; visa id: 242
  %186 = trunc i16 %b2s417 to i8		; visa id: 243
  %187 = uitofp i8 %186 to float		; visa id: 244
  %188 = fadd float %187, 5.000000e-01		; visa id: 245
  %189 = fmul float %188, %176		; visa id: 246
  %190 = fmul float %189, 2.500000e-01		; visa id: 247
  %191 = extractelement <2 x i32> %185, i32 0		; visa id: 248
  %192 = extractelement <2 x i32> %185, i32 1		; visa id: 248
  %193 = and i32 %175, 2139095040		; visa id: 248
  %194 = bitcast float %190 to i32
  %195 = and i32 %194, 2147483647		; visa id: 249
  %196 = icmp eq i32 %193, 2139095040
  %197 = icmp ugt i32 %195, 2139095040		; visa id: 250
  %198 = or i1 %196, %197		; visa id: 251
  %199 = and i32 %191, 255		; visa id: 253
  br i1 %198, label %207, label %200, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 254

200:                                              ; preds = %._crit_edge45
; BB17 :
  %201 = and i32 %153, 256
  %202 = sub nsw i32 0, %199, !spirv.Decorations !8798
  %203 = icmp eq i32 %201, 0		; visa id: 256
  %204 = select i1 %203, i32 %199, i32 %202		; visa id: 258
  %205 = sitofp i32 %204 to float		; visa id: 259
  %206 = fmul float %190, %205		; visa id: 260
  br label %215, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 261

207:                                              ; preds = %._crit_edge45
; BB18 :
  %208 = uitofp i32 %199 to float		; visa id: 263
  %209 = fmul float %190, %208		; visa id: 264
  %210 = and i32 %153, 256
  %211 = icmp eq i32 %210, 0		; visa id: 265
  %212 = select i1 %211, i32 1, i32 -1		; visa id: 267
  %213 = sitofp i32 %212 to float		; visa id: 268
  %214 = fmul float %209, %213		; visa id: 269
  br label %215, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 270

215:                                              ; preds = %200, %207
; BB19 :
  %.sroa.0125.0 = phi float [ %214, %207 ], [ %206, %200 ]
  %216 = bitcast i32 %191 to <4 x i8>
  %217 = extractelement <4 x i8> %216, i32 1
  %218 = zext i8 %217 to i32		; visa id: 271
  br i1 %198, label %226, label %219, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 272

219:                                              ; preds = %215
; BB20 :
  %220 = and i32 %153, 512
  %221 = sub nsw i32 0, %218, !spirv.Decorations !8798
  %222 = icmp eq i32 %220, 0		; visa id: 274
  %223 = select i1 %222, i32 %218, i32 %221		; visa id: 276
  %224 = sitofp i32 %223 to float		; visa id: 277
  %225 = fmul float %190, %224		; visa id: 278
  br label %234, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 279

226:                                              ; preds = %215
; BB21 :
  %227 = uitofp i32 %218 to float		; visa id: 281
  %228 = fmul float %190, %227		; visa id: 282
  %229 = and i32 %153, 512
  %230 = icmp eq i32 %229, 0		; visa id: 283
  %231 = select i1 %230, i32 1, i32 -1		; visa id: 285
  %232 = sitofp i32 %231 to float		; visa id: 286
  %233 = fmul float %228, %232		; visa id: 287
  br label %234, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 288

234:                                              ; preds = %226, %219
; BB22 :
  %.sroa.40.0 = phi float [ %233, %226 ], [ %225, %219 ]
  %235 = extractelement <4 x i8> %216, i32 2
  %236 = zext i8 %235 to i32		; visa id: 289
  br i1 %198, label %244, label %237, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 290

237:                                              ; preds = %234
; BB23 :
  %238 = and i32 %153, 1024
  %239 = sub nsw i32 0, %236, !spirv.Decorations !8798
  %240 = icmp eq i32 %238, 0		; visa id: 292
  %241 = select i1 %240, i32 %236, i32 %239		; visa id: 294
  %242 = sitofp i32 %241 to float		; visa id: 295
  %243 = fmul float %190, %242		; visa id: 296
  br label %252, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 297

244:                                              ; preds = %234
; BB24 :
  %245 = uitofp i32 %236 to float		; visa id: 299
  %246 = fmul float %190, %245		; visa id: 300
  %247 = and i32 %153, 1024
  %248 = icmp eq i32 %247, 0		; visa id: 301
  %249 = select i1 %248, i32 1, i32 -1		; visa id: 303
  %250 = sitofp i32 %249 to float		; visa id: 304
  %251 = fmul float %246, %250		; visa id: 305
  br label %252, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 306

252:                                              ; preds = %244, %237
; BB25 :
  %.sroa.64140.0 = phi float [ %251, %244 ], [ %243, %237 ]
  %253 = lshr i32 %191, 24		; visa id: 307
  br i1 %198, label %261, label %254, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 308

254:                                              ; preds = %252
; BB26 :
  %255 = and i32 %153, 2048
  %256 = sub nsw i32 0, %253, !spirv.Decorations !8798
  %257 = icmp eq i32 %255, 0		; visa id: 310
  %258 = select i1 %257, i32 %253, i32 %256		; visa id: 312
  %259 = sitofp i32 %258 to float		; visa id: 313
  %260 = fmul float %190, %259		; visa id: 314
  br label %269, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 315

261:                                              ; preds = %252
; BB27 :
  %262 = uitofp i32 %253 to float		; visa id: 317
  %263 = fmul float %190, %262		; visa id: 318
  %264 = and i32 %153, 2048
  %265 = icmp eq i32 %264, 0		; visa id: 319
  %266 = select i1 %265, i32 1, i32 -1		; visa id: 321
  %267 = sitofp i32 %266 to float		; visa id: 322
  %268 = fmul float %263, %267		; visa id: 323
  br label %269, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 324

269:                                              ; preds = %261, %254
; BB28 :
  %.sroa.88.0 = phi float [ %268, %261 ], [ %260, %254 ]
  %270 = and i32 %192, 255		; visa id: 325
  br i1 %198, label %278, label %271, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 326

271:                                              ; preds = %269
; BB29 :
  %272 = and i32 %153, 4096
  %273 = sub nsw i32 0, %270, !spirv.Decorations !8798
  %274 = icmp eq i32 %272, 0		; visa id: 328
  %275 = select i1 %274, i32 %270, i32 %273		; visa id: 330
  %276 = sitofp i32 %275 to float		; visa id: 331
  %277 = fmul float %190, %276		; visa id: 332
  br label %286, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 333

278:                                              ; preds = %269
; BB30 :
  %279 = uitofp i32 %270 to float		; visa id: 335
  %280 = fmul float %190, %279		; visa id: 336
  %281 = and i32 %153, 4096
  %282 = icmp eq i32 %281, 0		; visa id: 337
  %283 = select i1 %282, i32 1, i32 -1		; visa id: 339
  %284 = sitofp i32 %283 to float		; visa id: 340
  %285 = fmul float %280, %284		; visa id: 341
  br label %286, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 342

286:                                              ; preds = %278, %271
; BB31 :
  %.sroa.112155.0 = phi float [ %285, %278 ], [ %277, %271 ]
  %287 = bitcast i32 %192 to <4 x i8>
  %288 = extractelement <4 x i8> %287, i32 1
  %289 = zext i8 %288 to i32		; visa id: 343
  br i1 %198, label %297, label %290, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 344

290:                                              ; preds = %286
; BB32 :
  %291 = and i32 %153, 8192
  %292 = sub nsw i32 0, %289, !spirv.Decorations !8798
  %293 = icmp eq i32 %291, 0		; visa id: 346
  %294 = select i1 %293, i32 %289, i32 %292		; visa id: 348
  %295 = sitofp i32 %294 to float		; visa id: 349
  %296 = fmul float %190, %295		; visa id: 350
  br label %305, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 351

297:                                              ; preds = %286
; BB33 :
  %298 = uitofp i32 %289 to float		; visa id: 353
  %299 = fmul float %190, %298		; visa id: 354
  %300 = and i32 %153, 8192
  %301 = icmp eq i32 %300, 0		; visa id: 355
  %302 = select i1 %301, i32 1, i32 -1		; visa id: 357
  %303 = sitofp i32 %302 to float		; visa id: 358
  %304 = fmul float %299, %303		; visa id: 359
  br label %305, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 360

305:                                              ; preds = %297, %290
; BB34 :
  %.sroa.136.0 = phi float [ %304, %297 ], [ %296, %290 ]
  %306 = extractelement <4 x i8> %287, i32 2
  %307 = zext i8 %306 to i32		; visa id: 361
  br i1 %198, label %315, label %308, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 362

308:                                              ; preds = %305
; BB35 :
  %309 = and i32 %153, 16384
  %310 = sub nsw i32 0, %307, !spirv.Decorations !8798
  %311 = icmp eq i32 %309, 0		; visa id: 364
  %312 = select i1 %311, i32 %307, i32 %310		; visa id: 366
  %313 = sitofp i32 %312 to float		; visa id: 367
  %314 = fmul float %190, %313		; visa id: 368
  br label %323, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 369

315:                                              ; preds = %305
; BB36 :
  %316 = uitofp i32 %307 to float		; visa id: 371
  %317 = fmul float %190, %316		; visa id: 372
  %318 = and i32 %153, 16384
  %319 = icmp eq i32 %318, 0		; visa id: 373
  %320 = select i1 %319, i32 1, i32 -1		; visa id: 375
  %321 = sitofp i32 %320 to float		; visa id: 376
  %322 = fmul float %317, %321		; visa id: 377
  br label %323, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 378

323:                                              ; preds = %315, %308
; BB37 :
  %.sroa.160.0 = phi float [ %322, %315 ], [ %314, %308 ]
  %324 = lshr i32 %192, 24		; visa id: 379
  br i1 %198, label %331, label %325, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 380

325:                                              ; preds = %323
; BB38 :
  %326 = sub nsw i32 0, %324, !spirv.Decorations !8798
  %327 = icmp slt i16 %131, 0		; visa id: 382
  %328 = select i1 %327, i32 %326, i32 %324		; visa id: 383
  %329 = sitofp i32 %328 to float		; visa id: 384
  %330 = fmul float %190, %329		; visa id: 385
  br label %NodeBlock.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 386

331:                                              ; preds = %323
; BB39 :
  %332 = uitofp i32 %324 to float		; visa id: 388
  %333 = fmul float %190, %332		; visa id: 389
  %334 = fsub float 0.000000e+00, %333
  %335 = icmp slt i16 %131, 0		; visa id: 390
  %336 = select i1 %335, float %334, float %333		; visa id: 391
  br label %NodeBlock.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 392

NodeBlock.1:                                      ; preds = %331, %325
; BB40 :
  %.sroa.184.0 = phi float [ %336, %331 ], [ %330, %325 ]
  %337 = shl nuw i32 %152, 1		; visa id: 393
  %338 = zext i32 %337 to i64		; visa id: 394
  %339 = add i64 %338, %const_reg_qword2		; visa id: 395
  %IntToPtr2 = inttoptr i64 %339 to ptr addrspace(1)		; visa id: 396
  %vCastload = load i32, ptr addrspace(1) %IntToPtr2, align 2		; visa id: 396
  %340 = add i64 %339, 4
  %IntToPtr2327 = inttoptr i64 %340 to ptr addrspace(1)
  %vCastload328 = load i32, ptr addrspace(1) %IntToPtr2327, align 2		; visa id: 397
  %341 = add i64 %339, 8
  %IntToPtr2329 = inttoptr i64 %341 to ptr addrspace(1)
  %vCastload330 = load i32, ptr addrspace(1) %IntToPtr2329, align 2		; visa id: 398
  %342 = add i64 %339, 12
  %IntToPtr2331 = inttoptr i64 %342 to ptr addrspace(1)
  %vCastload332 = load i32, ptr addrspace(1) %IntToPtr2331, align 2		; visa id: 399
  %343 = bitcast i32 %vCastload to <2 x i16>		; visa id: 400
  %344 = bitcast i32 %vCastload328 to <2 x i16>		; visa id: 402
  %345 = extractelement <2 x i16> %343, i32 0		; visa id: 404
  %346 = extractelement <2 x i16> %343, i32 1		; visa id: 404
  %347 = extractelement <2 x i16> %344, i32 0		; visa id: 404
  %348 = extractelement <2 x i16> %344, i32 1		; visa id: 404
  %349 = bitcast i32 %vCastload330 to <2 x i16>		; visa id: 404
  %350 = bitcast i32 %vCastload332 to <2 x i16>		; visa id: 406
  %351 = extractelement <2 x i16> %349, i32 0		; visa id: 408
  %352 = extractelement <2 x i16> %349, i32 1		; visa id: 408
  %353 = extractelement <2 x i16> %350, i32 0		; visa id: 408
  %354 = extractelement <2 x i16> %350, i32 1		; visa id: 408
  %355 = zext i16 %345 to i32		; visa id: 408
  %356 = shl nuw i32 %355, 16, !spirv.Decorations !8788		; visa id: 409
  %357 = bitcast i32 %356 to float
  %358 = fmul float %.sroa.0125.0, %357		; visa id: 410
  %359 = fadd float %.sroa.0.0, %358		; visa id: 411
  %360 = zext i16 %346 to i32		; visa id: 412
  %361 = shl nuw i32 %360, 16, !spirv.Decorations !8788		; visa id: 413
  %362 = bitcast i32 %361 to float
  %363 = fmul float %.sroa.40.0, %362		; visa id: 414
  %364 = fadd float %359, %363		; visa id: 415
  %365 = zext i16 %347 to i32		; visa id: 416
  %366 = shl nuw i32 %365, 16, !spirv.Decorations !8788		; visa id: 417
  %367 = bitcast i32 %366 to float
  %368 = fmul float %.sroa.64140.0, %367		; visa id: 418
  %369 = fadd float %364, %368		; visa id: 419
  %370 = zext i16 %348 to i32		; visa id: 420
  %371 = shl nuw i32 %370, 16, !spirv.Decorations !8788		; visa id: 421
  %372 = bitcast i32 %371 to float
  %373 = fmul float %.sroa.88.0, %372		; visa id: 422
  %374 = fadd float %369, %373		; visa id: 423
  %375 = zext i16 %351 to i32		; visa id: 424
  %376 = shl nuw i32 %375, 16, !spirv.Decorations !8788		; visa id: 425
  %377 = bitcast i32 %376 to float
  %378 = fmul float %.sroa.112155.0, %377		; visa id: 426
  %379 = fadd float %374, %378		; visa id: 427
  %380 = zext i16 %352 to i32		; visa id: 428
  %381 = shl nuw i32 %380, 16, !spirv.Decorations !8788		; visa id: 429
  %382 = bitcast i32 %381 to float
  %383 = fmul float %.sroa.136.0, %382		; visa id: 430
  %384 = fadd float %379, %383		; visa id: 431
  %385 = zext i16 %353 to i32		; visa id: 432
  %386 = shl nuw i32 %385, 16, !spirv.Decorations !8788		; visa id: 433
  %387 = bitcast i32 %386 to float
  %388 = fmul float %.sroa.160.0, %387		; visa id: 434
  %389 = fadd float %384, %388		; visa id: 435
  %390 = zext i16 %354 to i32		; visa id: 436
  %391 = shl nuw i32 %390, 16, !spirv.Decorations !8788		; visa id: 437
  %392 = bitcast i32 %391 to float
  %393 = fmul float %.sroa.184.0, %392		; visa id: 438
  %394 = fadd float %389, %393		; visa id: 439
  %395 = or i32 %105, %114		; visa id: 440
  %sink_409 = lshr exact i32 %105, 2		; visa id: 441
  %sink_394 = zext i32 %sink_409 to i64		; visa id: 442
  %396 = add i64 %117, %sink_394		; visa id: 443
  %397 = inttoptr i64 %396 to ptr addrspace(4)		; visa id: 444
  %398 = addrspacecast ptr addrspace(4) %397 to ptr addrspace(1)		; visa id: 444
  %399 = load i16, ptr addrspace(1) %398, align 2, !noalias !8793		; visa id: 445
  %400 = load i8, ptr addrspace(1) %134, align 1, !noalias !8793		; visa id: 447
  %b2s418 = sext i8 %400 to i16
  %401 = zext i16 %399 to i32		; visa id: 449
  %402 = and i32 %401, 255
  %b2s419 = zext i8 %400 to i16		; visa id: 450
  %b2s420 = lshr i16 %b2s419, 2		; visa id: 451
  %403 = trunc i16 %b2s420 to i8		; visa id: 452
  %404 = zext i8 %403 to i32		; visa id: 453
  %405 = shl nuw nsw i32 %404, 8, !spirv.Decorations !8791		; visa id: 454
  %406 = and i32 %405, 768		; visa id: 455
  %407 = or i32 %402, %406		; visa id: 456
  br i1 %160, label %NodeBlock.1.._crit_edge45.1_crit_edge, label %.preheader1.1.preheader, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 457

.preheader1.1.preheader:                          ; preds = %NodeBlock.1
; BB41 :
  br label %.preheader1.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 461

.preheader1.1:                                    ; preds = %.preheader1.1..preheader1.1_crit_edge, %.preheader1.1.preheader
; BB42 :
  %408 = phi i32 [ %410, %.preheader1.1..preheader1.1_crit_edge ], [ -14, %.preheader1.1.preheader ]
  %409 = phi i32 [ %413, %.preheader1.1..preheader1.1_crit_edge ], [ %141, %.preheader1.1.preheader ]
  %410 = add nsw i32 %408, -1, !spirv.Decorations !8798		; visa id: 462
  %411 = and i32 %409, 512
  %412 = icmp eq i32 %411, 0		; visa id: 463
  br i1 %412, label %.preheader1.1..preheader1.1_crit_edge, label %414, !stats.blockFrequency.digits !8799, !stats.blockFrequency.scale !8800		; visa id: 466

.preheader1.1..preheader1.1_crit_edge:            ; preds = %.preheader1.1
; BB43 :
  %413 = shl i32 %409, 1		; visa id: 468
  br label %.preheader1.1, !stats.blockFrequency.digits !8801, !stats.blockFrequency.scale !8802		; visa id: 469

414:                                              ; preds = %.preheader1.1
; BB44 :
  %.lcssa456 = phi i32 [ %409, %.preheader1.1 ]
  %.lcssa455 = phi i32 [ %410, %.preheader1.1 ]
  %415 = shl i32 %.lcssa455, 23		; visa id: 471
  %416 = add i32 %415, 1065353216		; visa id: 472
  %417 = shl i32 %.lcssa456, 14		; visa id: 473
  %418 = and i32 %417, 8372224		; visa id: 474
  %419 = or i32 %416, %418
  %420 = or i32 %419, %137		; visa id: 475
  br label %._crit_edge45.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 477

NodeBlock.1.._crit_edge45.1_crit_edge:            ; preds = %NodeBlock.1
; BB45 :
  br label %._crit_edge45.1, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 480

._crit_edge45.1:                                  ; preds = %NodeBlock.1.._crit_edge45.1_crit_edge, %414
; BB46 :
  %421 = phi i32 [ %420, %414 ], [ %.mux.mux, %NodeBlock.1.._crit_edge45.1_crit_edge ]
  %422 = bitcast i32 %421 to float
  %423 = load i8, ptr addrspace(1) %179, align 1, !noalias !8793		; visa id: 481
  %b2s421 = sext i8 %423 to i16		; visa id: 483
  %424 = shl nuw nsw i32 %407, 3, !spirv.Decorations !8791		; visa id: 484
  %425 = zext i32 %424 to i64		; visa id: 485
  %426 = add i64 %sink_395, %425		; visa id: 486
  %427 = inttoptr i64 %426 to ptr addrspace(1)		; visa id: 487
  %428 = load <2 x i32>, ptr addrspace(1) %427, align 4		; visa id: 487
  %b2s422 = and i16 %b2s421, 15		; visa id: 488
  %429 = trunc i16 %b2s422 to i8		; visa id: 489
  %430 = uitofp i8 %429 to float		; visa id: 490
  %431 = fadd float %430, 5.000000e-01		; visa id: 491
  %432 = fmul float %431, %422		; visa id: 492
  %433 = fmul float %432, 2.500000e-01		; visa id: 493
  %434 = extractelement <2 x i32> %428, i32 0		; visa id: 494
  %435 = extractelement <2 x i32> %428, i32 1		; visa id: 494
  %436 = and i32 %421, 2139095040		; visa id: 494
  %437 = bitcast float %433 to i32
  %438 = and i32 %437, 2147483647		; visa id: 495
  %439 = icmp eq i32 %436, 2139095040
  %440 = icmp ugt i32 %438, 2139095040		; visa id: 496
  %441 = or i1 %439, %440		; visa id: 497
  %442 = and i32 %434, 255		; visa id: 499
  br i1 %441, label %450, label %443, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 500

443:                                              ; preds = %._crit_edge45.1
; BB47 :
  %444 = and i32 %401, 256
  %445 = sub nsw i32 0, %442, !spirv.Decorations !8798
  %446 = icmp eq i32 %444, 0		; visa id: 502
  %447 = select i1 %446, i32 %442, i32 %445		; visa id: 504
  %448 = sitofp i32 %447 to float		; visa id: 505
  %449 = fmul float %433, %448		; visa id: 506
  br label %458, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 507

450:                                              ; preds = %._crit_edge45.1
; BB48 :
  %451 = uitofp i32 %442 to float		; visa id: 509
  %452 = fmul float %433, %451		; visa id: 510
  %453 = and i32 %401, 256
  %454 = icmp eq i32 %453, 0		; visa id: 511
  %455 = select i1 %454, i32 1, i32 -1		; visa id: 513
  %456 = sitofp i32 %455 to float		; visa id: 514
  %457 = fmul float %452, %456		; visa id: 515
  br label %458, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 516

458:                                              ; preds = %450, %443
; BB49 :
  %.sroa.0125.1 = phi float [ %457, %450 ], [ %449, %443 ]
  %459 = bitcast i32 %434 to <4 x i8>
  %460 = extractelement <4 x i8> %459, i32 1
  %461 = zext i8 %460 to i32		; visa id: 517
  br i1 %441, label %469, label %462, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 518

462:                                              ; preds = %458
; BB50 :
  %463 = and i32 %401, 512
  %464 = sub nsw i32 0, %461, !spirv.Decorations !8798
  %465 = icmp eq i32 %463, 0		; visa id: 520
  %466 = select i1 %465, i32 %461, i32 %464		; visa id: 522
  %467 = sitofp i32 %466 to float		; visa id: 523
  %468 = fmul float %433, %467		; visa id: 524
  br label %477, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 525

469:                                              ; preds = %458
; BB51 :
  %470 = uitofp i32 %461 to float		; visa id: 527
  %471 = fmul float %433, %470		; visa id: 528
  %472 = and i32 %401, 512
  %473 = icmp eq i32 %472, 0		; visa id: 529
  %474 = select i1 %473, i32 1, i32 -1		; visa id: 531
  %475 = sitofp i32 %474 to float		; visa id: 532
  %476 = fmul float %471, %475		; visa id: 533
  br label %477, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 534

477:                                              ; preds = %469, %462
; BB52 :
  %.sroa.40.1 = phi float [ %476, %469 ], [ %468, %462 ]
  %478 = extractelement <4 x i8> %459, i32 2
  %479 = zext i8 %478 to i32		; visa id: 535
  br i1 %441, label %487, label %480, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 536

480:                                              ; preds = %477
; BB53 :
  %481 = and i32 %401, 1024
  %482 = sub nsw i32 0, %479, !spirv.Decorations !8798
  %483 = icmp eq i32 %481, 0		; visa id: 538
  %484 = select i1 %483, i32 %479, i32 %482		; visa id: 540
  %485 = sitofp i32 %484 to float		; visa id: 541
  %486 = fmul float %433, %485		; visa id: 542
  br label %495, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 543

487:                                              ; preds = %477
; BB54 :
  %488 = uitofp i32 %479 to float		; visa id: 545
  %489 = fmul float %433, %488		; visa id: 546
  %490 = and i32 %401, 1024
  %491 = icmp eq i32 %490, 0		; visa id: 547
  %492 = select i1 %491, i32 1, i32 -1		; visa id: 549
  %493 = sitofp i32 %492 to float		; visa id: 550
  %494 = fmul float %489, %493		; visa id: 551
  br label %495, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 552

495:                                              ; preds = %487, %480
; BB55 :
  %.sroa.64140.1 = phi float [ %494, %487 ], [ %486, %480 ]
  %496 = lshr i32 %434, 24		; visa id: 553
  br i1 %441, label %504, label %497, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 554

497:                                              ; preds = %495
; BB56 :
  %498 = and i32 %401, 2048
  %499 = sub nsw i32 0, %496, !spirv.Decorations !8798
  %500 = icmp eq i32 %498, 0		; visa id: 556
  %501 = select i1 %500, i32 %496, i32 %499		; visa id: 558
  %502 = sitofp i32 %501 to float		; visa id: 559
  %503 = fmul float %433, %502		; visa id: 560
  br label %512, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 561

504:                                              ; preds = %495
; BB57 :
  %505 = uitofp i32 %496 to float		; visa id: 563
  %506 = fmul float %433, %505		; visa id: 564
  %507 = and i32 %401, 2048
  %508 = icmp eq i32 %507, 0		; visa id: 565
  %509 = select i1 %508, i32 1, i32 -1		; visa id: 567
  %510 = sitofp i32 %509 to float		; visa id: 568
  %511 = fmul float %506, %510		; visa id: 569
  br label %512, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 570

512:                                              ; preds = %504, %497
; BB58 :
  %.sroa.88.1 = phi float [ %511, %504 ], [ %503, %497 ]
  %513 = and i32 %435, 255		; visa id: 571
  br i1 %441, label %521, label %514, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 572

514:                                              ; preds = %512
; BB59 :
  %515 = and i32 %401, 4096
  %516 = sub nsw i32 0, %513, !spirv.Decorations !8798
  %517 = icmp eq i32 %515, 0		; visa id: 574
  %518 = select i1 %517, i32 %513, i32 %516		; visa id: 576
  %519 = sitofp i32 %518 to float		; visa id: 577
  %520 = fmul float %433, %519		; visa id: 578
  br label %529, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 579

521:                                              ; preds = %512
; BB60 :
  %522 = uitofp i32 %513 to float		; visa id: 581
  %523 = fmul float %433, %522		; visa id: 582
  %524 = and i32 %401, 4096
  %525 = icmp eq i32 %524, 0		; visa id: 583
  %526 = select i1 %525, i32 1, i32 -1		; visa id: 585
  %527 = sitofp i32 %526 to float		; visa id: 586
  %528 = fmul float %523, %527		; visa id: 587
  br label %529, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 588

529:                                              ; preds = %521, %514
; BB61 :
  %.sroa.112155.1 = phi float [ %528, %521 ], [ %520, %514 ]
  %530 = bitcast i32 %435 to <4 x i8>
  %531 = extractelement <4 x i8> %530, i32 1
  %532 = zext i8 %531 to i32		; visa id: 589
  br i1 %441, label %540, label %533, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 590

533:                                              ; preds = %529
; BB62 :
  %534 = and i32 %401, 8192
  %535 = sub nsw i32 0, %532, !spirv.Decorations !8798
  %536 = icmp eq i32 %534, 0		; visa id: 592
  %537 = select i1 %536, i32 %532, i32 %535		; visa id: 594
  %538 = sitofp i32 %537 to float		; visa id: 595
  %539 = fmul float %433, %538		; visa id: 596
  br label %548, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 597

540:                                              ; preds = %529
; BB63 :
  %541 = uitofp i32 %532 to float		; visa id: 599
  %542 = fmul float %433, %541		; visa id: 600
  %543 = and i32 %401, 8192
  %544 = icmp eq i32 %543, 0		; visa id: 601
  %545 = select i1 %544, i32 1, i32 -1		; visa id: 603
  %546 = sitofp i32 %545 to float		; visa id: 604
  %547 = fmul float %542, %546		; visa id: 605
  br label %548, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 606

548:                                              ; preds = %540, %533
; BB64 :
  %.sroa.136.1 = phi float [ %547, %540 ], [ %539, %533 ]
  %549 = extractelement <4 x i8> %530, i32 2
  %550 = zext i8 %549 to i32		; visa id: 607
  br i1 %441, label %558, label %551, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 608

551:                                              ; preds = %548
; BB65 :
  %552 = and i32 %401, 16384
  %553 = sub nsw i32 0, %550, !spirv.Decorations !8798
  %554 = icmp eq i32 %552, 0		; visa id: 610
  %555 = select i1 %554, i32 %550, i32 %553		; visa id: 612
  %556 = sitofp i32 %555 to float		; visa id: 613
  %557 = fmul float %433, %556		; visa id: 614
  br label %566, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 615

558:                                              ; preds = %548
; BB66 :
  %559 = uitofp i32 %550 to float		; visa id: 617
  %560 = fmul float %433, %559		; visa id: 618
  %561 = and i32 %401, 16384
  %562 = icmp eq i32 %561, 0		; visa id: 619
  %563 = select i1 %562, i32 1, i32 -1		; visa id: 621
  %564 = sitofp i32 %563 to float		; visa id: 622
  %565 = fmul float %560, %564		; visa id: 623
  br label %566, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 624

566:                                              ; preds = %558, %551
; BB67 :
  %.sroa.160.1 = phi float [ %565, %558 ], [ %557, %551 ]
  %567 = lshr i32 %435, 24		; visa id: 625
  br i1 %441, label %574, label %568, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 626

568:                                              ; preds = %566
; BB68 :
  %569 = sub nsw i32 0, %567, !spirv.Decorations !8798
  %570 = icmp slt i16 %399, 0		; visa id: 628
  %571 = select i1 %570, i32 %569, i32 %567		; visa id: 629
  %572 = sitofp i32 %571 to float		; visa id: 630
  %573 = fmul float %433, %572		; visa id: 631
  br label %NodeBlock.2, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 632

574:                                              ; preds = %566
; BB69 :
  %575 = uitofp i32 %567 to float		; visa id: 634
  %576 = fmul float %433, %575		; visa id: 635
  %577 = fsub float 0.000000e+00, %576
  %578 = icmp slt i16 %399, 0		; visa id: 636
  %579 = select i1 %578, float %577, float %576		; visa id: 637
  br label %NodeBlock.2, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 638

NodeBlock.2:                                      ; preds = %574, %568
; BB70 :
  %.sroa.184.1 = phi float [ %579, %574 ], [ %573, %568 ]
  %580 = shl nuw i32 %395, 1		; visa id: 639
  %581 = zext i32 %580 to i64		; visa id: 640
  %582 = add i64 %581, %const_reg_qword2		; visa id: 641
  %IntToPtr2333 = inttoptr i64 %582 to ptr addrspace(1)		; visa id: 642
  %vCastload334 = load i32, ptr addrspace(1) %IntToPtr2333, align 2		; visa id: 642
  %583 = add i64 %582, 4
  %IntToPtr2335 = inttoptr i64 %583 to ptr addrspace(1)
  %vCastload336 = load i32, ptr addrspace(1) %IntToPtr2335, align 2		; visa id: 643
  %584 = add i64 %582, 8
  %IntToPtr2337 = inttoptr i64 %584 to ptr addrspace(1)
  %vCastload338 = load i32, ptr addrspace(1) %IntToPtr2337, align 2		; visa id: 644
  %585 = add i64 %582, 12
  %IntToPtr2339 = inttoptr i64 %585 to ptr addrspace(1)
  %vCastload340 = load i32, ptr addrspace(1) %IntToPtr2339, align 2		; visa id: 645
  %586 = bitcast i32 %vCastload334 to <2 x i16>		; visa id: 646
  %587 = bitcast i32 %vCastload336 to <2 x i16>		; visa id: 648
  %588 = extractelement <2 x i16> %586, i32 0		; visa id: 650
  %589 = extractelement <2 x i16> %586, i32 1		; visa id: 650
  %590 = extractelement <2 x i16> %587, i32 0		; visa id: 650
  %591 = extractelement <2 x i16> %587, i32 1		; visa id: 650
  %592 = bitcast i32 %vCastload338 to <2 x i16>		; visa id: 650
  %593 = bitcast i32 %vCastload340 to <2 x i16>		; visa id: 652
  %594 = extractelement <2 x i16> %592, i32 0		; visa id: 654
  %595 = extractelement <2 x i16> %592, i32 1		; visa id: 654
  %596 = extractelement <2 x i16> %593, i32 0		; visa id: 654
  %597 = extractelement <2 x i16> %593, i32 1		; visa id: 654
  %598 = zext i16 %588 to i32		; visa id: 654
  %599 = shl nuw i32 %598, 16, !spirv.Decorations !8788		; visa id: 655
  %600 = bitcast i32 %599 to float
  %601 = fmul float %.sroa.0125.1, %600		; visa id: 656
  %602 = fadd float %.sroa.10.0, %601		; visa id: 657
  %603 = zext i16 %589 to i32		; visa id: 658
  %604 = shl nuw i32 %603, 16, !spirv.Decorations !8788		; visa id: 659
  %605 = bitcast i32 %604 to float
  %606 = fmul float %.sroa.40.1, %605		; visa id: 660
  %607 = fadd float %602, %606		; visa id: 661
  %608 = zext i16 %590 to i32		; visa id: 662
  %609 = shl nuw i32 %608, 16, !spirv.Decorations !8788		; visa id: 663
  %610 = bitcast i32 %609 to float
  %611 = fmul float %.sroa.64140.1, %610		; visa id: 664
  %612 = fadd float %607, %611		; visa id: 665
  %613 = zext i16 %591 to i32		; visa id: 666
  %614 = shl nuw i32 %613, 16, !spirv.Decorations !8788		; visa id: 667
  %615 = bitcast i32 %614 to float
  %616 = fmul float %.sroa.88.1, %615		; visa id: 668
  %617 = fadd float %612, %616		; visa id: 669
  %618 = zext i16 %594 to i32		; visa id: 670
  %619 = shl nuw i32 %618, 16, !spirv.Decorations !8788		; visa id: 671
  %620 = bitcast i32 %619 to float
  %621 = fmul float %.sroa.112155.1, %620		; visa id: 672
  %622 = fadd float %617, %621		; visa id: 673
  %623 = zext i16 %595 to i32		; visa id: 674
  %624 = shl nuw i32 %623, 16, !spirv.Decorations !8788		; visa id: 675
  %625 = bitcast i32 %624 to float
  %626 = fmul float %.sroa.136.1, %625		; visa id: 676
  %627 = fadd float %622, %626		; visa id: 677
  %628 = zext i16 %596 to i32		; visa id: 678
  %629 = shl nuw i32 %628, 16, !spirv.Decorations !8788		; visa id: 679
  %630 = bitcast i32 %629 to float
  %631 = fmul float %.sroa.160.1, %630		; visa id: 680
  %632 = fadd float %627, %631		; visa id: 681
  %633 = zext i16 %597 to i32		; visa id: 682
  %634 = shl nuw i32 %633, 16, !spirv.Decorations !8788		; visa id: 683
  %635 = bitcast i32 %634 to float
  %636 = fmul float %.sroa.184.1, %635		; visa id: 684
  %637 = fadd float %632, %636		; visa id: 685
  %638 = or i32 %106, %114		; visa id: 686
  %sink_408 = lshr exact i32 %106, 2		; visa id: 687
  %sink_393 = zext i32 %sink_408 to i64		; visa id: 688
  %639 = add i64 %117, %sink_393		; visa id: 689
  %640 = inttoptr i64 %639 to ptr addrspace(4)		; visa id: 690
  %641 = addrspacecast ptr addrspace(4) %640 to ptr addrspace(1)		; visa id: 690
  %642 = load i16, ptr addrspace(1) %641, align 2, !noalias !8793		; visa id: 691
  %643 = load i8, ptr addrspace(1) %134, align 1, !noalias !8793		; visa id: 693
  %b2s423 = sext i8 %643 to i16
  %644 = zext i16 %642 to i32		; visa id: 695
  %645 = and i32 %644, 255
  %b2s424 = zext i8 %643 to i16		; visa id: 696
  %b2s425 = lshr i16 %b2s424, 4		; visa id: 697
  %646 = trunc i16 %b2s425 to i8		; visa id: 698
  %647 = zext i8 %646 to i32		; visa id: 699
  %648 = shl nuw nsw i32 %647, 8, !spirv.Decorations !8791		; visa id: 700
  %649 = and i32 %648, 768		; visa id: 701
  %650 = or i32 %645, %649		; visa id: 702
  br i1 %160, label %NodeBlock.2.._crit_edge45.2_crit_edge, label %.preheader1.2.preheader, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 703

.preheader1.2.preheader:                          ; preds = %NodeBlock.2
; BB71 :
  br label %.preheader1.2, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 707

.preheader1.2:                                    ; preds = %.preheader1.2..preheader1.2_crit_edge, %.preheader1.2.preheader
; BB72 :
  %651 = phi i32 [ %653, %.preheader1.2..preheader1.2_crit_edge ], [ -14, %.preheader1.2.preheader ]
  %652 = phi i32 [ %656, %.preheader1.2..preheader1.2_crit_edge ], [ %141, %.preheader1.2.preheader ]
  %653 = add nsw i32 %651, -1, !spirv.Decorations !8798		; visa id: 708
  %654 = and i32 %652, 512
  %655 = icmp eq i32 %654, 0		; visa id: 709
  br i1 %655, label %.preheader1.2..preheader1.2_crit_edge, label %657, !stats.blockFrequency.digits !8799, !stats.blockFrequency.scale !8800		; visa id: 712

.preheader1.2..preheader1.2_crit_edge:            ; preds = %.preheader1.2
; BB73 :
  %656 = shl i32 %652, 1		; visa id: 714
  br label %.preheader1.2, !stats.blockFrequency.digits !8801, !stats.blockFrequency.scale !8802		; visa id: 715

657:                                              ; preds = %.preheader1.2
; BB74 :
  %.lcssa458 = phi i32 [ %652, %.preheader1.2 ]
  %.lcssa457 = phi i32 [ %653, %.preheader1.2 ]
  %658 = shl i32 %.lcssa457, 23		; visa id: 717
  %659 = add i32 %658, 1065353216		; visa id: 718
  %660 = shl i32 %.lcssa458, 14		; visa id: 719
  %661 = and i32 %660, 8372224		; visa id: 720
  %662 = or i32 %659, %661
  %663 = or i32 %662, %137		; visa id: 721
  br label %._crit_edge45.2, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 723

NodeBlock.2.._crit_edge45.2_crit_edge:            ; preds = %NodeBlock.2
; BB75 :
  br label %._crit_edge45.2, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 726

._crit_edge45.2:                                  ; preds = %NodeBlock.2.._crit_edge45.2_crit_edge, %657
; BB76 :
  %664 = phi i32 [ %663, %657 ], [ %.mux.mux, %NodeBlock.2.._crit_edge45.2_crit_edge ]
  %665 = bitcast i32 %664 to float
  %666 = load i8, ptr addrspace(1) %179, align 1, !noalias !8793		; visa id: 727
  %b2s426 = sext i8 %666 to i16
  %667 = shl nuw nsw i32 %650, 3, !spirv.Decorations !8791		; visa id: 729
  %668 = zext i32 %667 to i64		; visa id: 730
  %669 = add i64 %sink_395, %668		; visa id: 731
  %670 = inttoptr i64 %669 to ptr addrspace(1)		; visa id: 732
  %671 = load <2 x i32>, ptr addrspace(1) %670, align 4		; visa id: 732
  %b2s427 = zext i8 %666 to i16		; visa id: 733
  %b2s428 = lshr i16 %b2s427, 4		; visa id: 734
  %672 = trunc i16 %b2s428 to i8		; visa id: 735
  %673 = uitofp i8 %672 to float		; visa id: 736
  %674 = fadd float %673, 5.000000e-01		; visa id: 737
  %675 = fmul float %674, %665		; visa id: 738
  %676 = fmul float %675, 2.500000e-01		; visa id: 739
  %677 = extractelement <2 x i32> %671, i32 0		; visa id: 740
  %678 = extractelement <2 x i32> %671, i32 1		; visa id: 740
  %679 = and i32 %664, 2139095040		; visa id: 740
  %680 = bitcast float %676 to i32
  %681 = and i32 %680, 2147483647		; visa id: 741
  %682 = icmp eq i32 %679, 2139095040
  %683 = icmp ugt i32 %681, 2139095040		; visa id: 742
  %684 = or i1 %682, %683		; visa id: 743
  %685 = and i32 %677, 255		; visa id: 745
  br i1 %684, label %693, label %686, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 746

686:                                              ; preds = %._crit_edge45.2
; BB77 :
  %687 = and i32 %644, 256
  %688 = sub nsw i32 0, %685, !spirv.Decorations !8798
  %689 = icmp eq i32 %687, 0		; visa id: 748
  %690 = select i1 %689, i32 %685, i32 %688		; visa id: 750
  %691 = sitofp i32 %690 to float		; visa id: 751
  %692 = fmul float %676, %691		; visa id: 752
  br label %701, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 753

693:                                              ; preds = %._crit_edge45.2
; BB78 :
  %694 = uitofp i32 %685 to float		; visa id: 755
  %695 = fmul float %676, %694		; visa id: 756
  %696 = and i32 %644, 256
  %697 = icmp eq i32 %696, 0		; visa id: 757
  %698 = select i1 %697, i32 1, i32 -1		; visa id: 759
  %699 = sitofp i32 %698 to float		; visa id: 760
  %700 = fmul float %695, %699		; visa id: 761
  br label %701, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 762

701:                                              ; preds = %693, %686
; BB79 :
  %.sroa.0125.2 = phi float [ %700, %693 ], [ %692, %686 ]
  %702 = bitcast i32 %677 to <4 x i8>
  %703 = extractelement <4 x i8> %702, i32 1
  %704 = zext i8 %703 to i32		; visa id: 763
  br i1 %684, label %712, label %705, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 764

705:                                              ; preds = %701
; BB80 :
  %706 = and i32 %644, 512
  %707 = sub nsw i32 0, %704, !spirv.Decorations !8798
  %708 = icmp eq i32 %706, 0		; visa id: 766
  %709 = select i1 %708, i32 %704, i32 %707		; visa id: 768
  %710 = sitofp i32 %709 to float		; visa id: 769
  %711 = fmul float %676, %710		; visa id: 770
  br label %720, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 771

712:                                              ; preds = %701
; BB81 :
  %713 = uitofp i32 %704 to float		; visa id: 773
  %714 = fmul float %676, %713		; visa id: 774
  %715 = and i32 %644, 512
  %716 = icmp eq i32 %715, 0		; visa id: 775
  %717 = select i1 %716, i32 1, i32 -1		; visa id: 777
  %718 = sitofp i32 %717 to float		; visa id: 778
  %719 = fmul float %714, %718		; visa id: 779
  br label %720, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 780

720:                                              ; preds = %712, %705
; BB82 :
  %.sroa.40.2 = phi float [ %719, %712 ], [ %711, %705 ]
  %721 = extractelement <4 x i8> %702, i32 2
  %722 = zext i8 %721 to i32		; visa id: 781
  br i1 %684, label %730, label %723, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 782

723:                                              ; preds = %720
; BB83 :
  %724 = and i32 %644, 1024
  %725 = sub nsw i32 0, %722, !spirv.Decorations !8798
  %726 = icmp eq i32 %724, 0		; visa id: 784
  %727 = select i1 %726, i32 %722, i32 %725		; visa id: 786
  %728 = sitofp i32 %727 to float		; visa id: 787
  %729 = fmul float %676, %728		; visa id: 788
  br label %738, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 789

730:                                              ; preds = %720
; BB84 :
  %731 = uitofp i32 %722 to float		; visa id: 791
  %732 = fmul float %676, %731		; visa id: 792
  %733 = and i32 %644, 1024
  %734 = icmp eq i32 %733, 0		; visa id: 793
  %735 = select i1 %734, i32 1, i32 -1		; visa id: 795
  %736 = sitofp i32 %735 to float		; visa id: 796
  %737 = fmul float %732, %736		; visa id: 797
  br label %738, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 798

738:                                              ; preds = %730, %723
; BB85 :
  %.sroa.64140.2 = phi float [ %737, %730 ], [ %729, %723 ]
  %739 = lshr i32 %677, 24		; visa id: 799
  br i1 %684, label %747, label %740, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 800

740:                                              ; preds = %738
; BB86 :
  %741 = and i32 %644, 2048
  %742 = sub nsw i32 0, %739, !spirv.Decorations !8798
  %743 = icmp eq i32 %741, 0		; visa id: 802
  %744 = select i1 %743, i32 %739, i32 %742		; visa id: 804
  %745 = sitofp i32 %744 to float		; visa id: 805
  %746 = fmul float %676, %745		; visa id: 806
  br label %755, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 807

747:                                              ; preds = %738
; BB87 :
  %748 = uitofp i32 %739 to float		; visa id: 809
  %749 = fmul float %676, %748		; visa id: 810
  %750 = and i32 %644, 2048
  %751 = icmp eq i32 %750, 0		; visa id: 811
  %752 = select i1 %751, i32 1, i32 -1		; visa id: 813
  %753 = sitofp i32 %752 to float		; visa id: 814
  %754 = fmul float %749, %753		; visa id: 815
  br label %755, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 816

755:                                              ; preds = %747, %740
; BB88 :
  %.sroa.88.2 = phi float [ %754, %747 ], [ %746, %740 ]
  %756 = and i32 %678, 255		; visa id: 817
  br i1 %684, label %764, label %757, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 818

757:                                              ; preds = %755
; BB89 :
  %758 = and i32 %644, 4096
  %759 = sub nsw i32 0, %756, !spirv.Decorations !8798
  %760 = icmp eq i32 %758, 0		; visa id: 820
  %761 = select i1 %760, i32 %756, i32 %759		; visa id: 822
  %762 = sitofp i32 %761 to float		; visa id: 823
  %763 = fmul float %676, %762		; visa id: 824
  br label %772, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 825

764:                                              ; preds = %755
; BB90 :
  %765 = uitofp i32 %756 to float		; visa id: 827
  %766 = fmul float %676, %765		; visa id: 828
  %767 = and i32 %644, 4096
  %768 = icmp eq i32 %767, 0		; visa id: 829
  %769 = select i1 %768, i32 1, i32 -1		; visa id: 831
  %770 = sitofp i32 %769 to float		; visa id: 832
  %771 = fmul float %766, %770		; visa id: 833
  br label %772, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 834

772:                                              ; preds = %764, %757
; BB91 :
  %.sroa.112155.2 = phi float [ %771, %764 ], [ %763, %757 ]
  %773 = bitcast i32 %678 to <4 x i8>
  %774 = extractelement <4 x i8> %773, i32 1
  %775 = zext i8 %774 to i32		; visa id: 835
  br i1 %684, label %783, label %776, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 836

776:                                              ; preds = %772
; BB92 :
  %777 = and i32 %644, 8192
  %778 = sub nsw i32 0, %775, !spirv.Decorations !8798
  %779 = icmp eq i32 %777, 0		; visa id: 838
  %780 = select i1 %779, i32 %775, i32 %778		; visa id: 840
  %781 = sitofp i32 %780 to float		; visa id: 841
  %782 = fmul float %676, %781		; visa id: 842
  br label %791, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 843

783:                                              ; preds = %772
; BB93 :
  %784 = uitofp i32 %775 to float		; visa id: 845
  %785 = fmul float %676, %784		; visa id: 846
  %786 = and i32 %644, 8192
  %787 = icmp eq i32 %786, 0		; visa id: 847
  %788 = select i1 %787, i32 1, i32 -1		; visa id: 849
  %789 = sitofp i32 %788 to float		; visa id: 850
  %790 = fmul float %785, %789		; visa id: 851
  br label %791, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 852

791:                                              ; preds = %783, %776
; BB94 :
  %.sroa.136.2 = phi float [ %790, %783 ], [ %782, %776 ]
  %792 = extractelement <4 x i8> %773, i32 2
  %793 = zext i8 %792 to i32		; visa id: 853
  br i1 %684, label %801, label %794, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 854

794:                                              ; preds = %791
; BB95 :
  %795 = and i32 %644, 16384
  %796 = sub nsw i32 0, %793, !spirv.Decorations !8798
  %797 = icmp eq i32 %795, 0		; visa id: 856
  %798 = select i1 %797, i32 %793, i32 %796		; visa id: 858
  %799 = sitofp i32 %798 to float		; visa id: 859
  %800 = fmul float %676, %799		; visa id: 860
  br label %809, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 861

801:                                              ; preds = %791
; BB96 :
  %802 = uitofp i32 %793 to float		; visa id: 863
  %803 = fmul float %676, %802		; visa id: 864
  %804 = and i32 %644, 16384
  %805 = icmp eq i32 %804, 0		; visa id: 865
  %806 = select i1 %805, i32 1, i32 -1		; visa id: 867
  %807 = sitofp i32 %806 to float		; visa id: 868
  %808 = fmul float %803, %807		; visa id: 869
  br label %809, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 870

809:                                              ; preds = %801, %794
; BB97 :
  %.sroa.160.2 = phi float [ %808, %801 ], [ %800, %794 ]
  %810 = lshr i32 %678, 24		; visa id: 871
  br i1 %684, label %817, label %811, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 872

811:                                              ; preds = %809
; BB98 :
  %812 = sub nsw i32 0, %810, !spirv.Decorations !8798
  %813 = icmp slt i16 %642, 0		; visa id: 874
  %814 = select i1 %813, i32 %812, i32 %810		; visa id: 875
  %815 = sitofp i32 %814 to float		; visa id: 876
  %816 = fmul float %676, %815		; visa id: 877
  br label %NodeBlock.3, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 878

817:                                              ; preds = %809
; BB99 :
  %818 = uitofp i32 %810 to float		; visa id: 880
  %819 = fmul float %676, %818		; visa id: 881
  %820 = fsub float 0.000000e+00, %819
  %821 = icmp slt i16 %642, 0		; visa id: 882
  %822 = select i1 %821, float %820, float %819		; visa id: 883
  br label %NodeBlock.3, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 884

NodeBlock.3:                                      ; preds = %817, %811
; BB100 :
  %.sroa.184.2 = phi float [ %822, %817 ], [ %816, %811 ]
  %823 = shl nuw i32 %638, 1		; visa id: 885
  %824 = zext i32 %823 to i64		; visa id: 886
  %825 = add i64 %824, %const_reg_qword2		; visa id: 887
  %IntToPtr2341 = inttoptr i64 %825 to ptr addrspace(1)		; visa id: 888
  %vCastload342 = load i32, ptr addrspace(1) %IntToPtr2341, align 2		; visa id: 888
  %826 = add i64 %825, 4
  %IntToPtr2343 = inttoptr i64 %826 to ptr addrspace(1)
  %vCastload344 = load i32, ptr addrspace(1) %IntToPtr2343, align 2		; visa id: 889
  %827 = add i64 %825, 8
  %IntToPtr2345 = inttoptr i64 %827 to ptr addrspace(1)
  %vCastload346 = load i32, ptr addrspace(1) %IntToPtr2345, align 2		; visa id: 890
  %828 = add i64 %825, 12
  %IntToPtr2347 = inttoptr i64 %828 to ptr addrspace(1)
  %vCastload348 = load i32, ptr addrspace(1) %IntToPtr2347, align 2		; visa id: 891
  %829 = bitcast i32 %vCastload342 to <2 x i16>		; visa id: 892
  %830 = bitcast i32 %vCastload344 to <2 x i16>		; visa id: 894
  %831 = extractelement <2 x i16> %829, i32 0		; visa id: 896
  %832 = extractelement <2 x i16> %829, i32 1		; visa id: 896
  %833 = extractelement <2 x i16> %830, i32 0		; visa id: 896
  %834 = extractelement <2 x i16> %830, i32 1		; visa id: 896
  %835 = bitcast i32 %vCastload346 to <2 x i16>		; visa id: 896
  %836 = bitcast i32 %vCastload348 to <2 x i16>		; visa id: 898
  %837 = extractelement <2 x i16> %835, i32 0		; visa id: 900
  %838 = extractelement <2 x i16> %835, i32 1		; visa id: 900
  %839 = extractelement <2 x i16> %836, i32 0		; visa id: 900
  %840 = extractelement <2 x i16> %836, i32 1		; visa id: 900
  %841 = zext i16 %831 to i32		; visa id: 900
  %842 = shl nuw i32 %841, 16, !spirv.Decorations !8788		; visa id: 901
  %843 = bitcast i32 %842 to float
  %844 = fmul float %.sroa.0125.2, %843		; visa id: 902
  %845 = fadd float %.sroa.13.0, %844		; visa id: 903
  %846 = zext i16 %832 to i32		; visa id: 904
  %847 = shl nuw i32 %846, 16, !spirv.Decorations !8788		; visa id: 905
  %848 = bitcast i32 %847 to float
  %849 = fmul float %.sroa.40.2, %848		; visa id: 906
  %850 = fadd float %845, %849		; visa id: 907
  %851 = zext i16 %833 to i32		; visa id: 908
  %852 = shl nuw i32 %851, 16, !spirv.Decorations !8788		; visa id: 909
  %853 = bitcast i32 %852 to float
  %854 = fmul float %.sroa.64140.2, %853		; visa id: 910
  %855 = fadd float %850, %854		; visa id: 911
  %856 = zext i16 %834 to i32		; visa id: 912
  %857 = shl nuw i32 %856, 16, !spirv.Decorations !8788		; visa id: 913
  %858 = bitcast i32 %857 to float
  %859 = fmul float %.sroa.88.2, %858		; visa id: 914
  %860 = fadd float %855, %859		; visa id: 915
  %861 = zext i16 %837 to i32		; visa id: 916
  %862 = shl nuw i32 %861, 16, !spirv.Decorations !8788		; visa id: 917
  %863 = bitcast i32 %862 to float
  %864 = fmul float %.sroa.112155.2, %863		; visa id: 918
  %865 = fadd float %860, %864		; visa id: 919
  %866 = zext i16 %838 to i32		; visa id: 920
  %867 = shl nuw i32 %866, 16, !spirv.Decorations !8788		; visa id: 921
  %868 = bitcast i32 %867 to float
  %869 = fmul float %.sroa.136.2, %868		; visa id: 922
  %870 = fadd float %865, %869		; visa id: 923
  %871 = zext i16 %839 to i32		; visa id: 924
  %872 = shl nuw i32 %871, 16, !spirv.Decorations !8788		; visa id: 925
  %873 = bitcast i32 %872 to float
  %874 = fmul float %.sroa.160.2, %873		; visa id: 926
  %875 = fadd float %870, %874		; visa id: 927
  %876 = zext i16 %840 to i32		; visa id: 928
  %877 = shl nuw i32 %876, 16, !spirv.Decorations !8788		; visa id: 929
  %878 = bitcast i32 %877 to float
  %879 = fmul float %.sroa.184.2, %878		; visa id: 930
  %880 = fadd float %875, %879		; visa id: 931
  %881 = or i32 %107, %114		; visa id: 932
  %sink_407 = lshr exact i32 %107, 2		; visa id: 933
  %sink_392 = zext i32 %sink_407 to i64		; visa id: 934
  %882 = add i64 %117, %sink_392		; visa id: 935
  %883 = inttoptr i64 %882 to ptr addrspace(4)		; visa id: 936
  %884 = addrspacecast ptr addrspace(4) %883 to ptr addrspace(1)		; visa id: 936
  %885 = load i16, ptr addrspace(1) %884, align 2, !noalias !8793		; visa id: 937
  %886 = load i8, ptr addrspace(1) %134, align 1, !noalias !8793		; visa id: 939
  %b2s429 = sext i8 %886 to i16
  %b2s430 = zext i8 %886 to i16		; visa id: 941
  %b2s431 = lshr i16 %b2s430, 6		; visa id: 942
  br i1 %160, label %NodeBlock.3.._crit_edge45.3_crit_edge, label %.preheader1.3.preheader, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 943

.preheader1.3.preheader:                          ; preds = %NodeBlock.3
; BB101 :
  br label %.preheader1.3, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 947

.preheader1.3:                                    ; preds = %.preheader1.3..preheader1.3_crit_edge, %.preheader1.3.preheader
; BB102 :
  %887 = phi i32 [ %889, %.preheader1.3..preheader1.3_crit_edge ], [ -14, %.preheader1.3.preheader ]
  %888 = phi i32 [ %892, %.preheader1.3..preheader1.3_crit_edge ], [ %141, %.preheader1.3.preheader ]
  %889 = add nsw i32 %887, -1, !spirv.Decorations !8798		; visa id: 948
  %890 = and i32 %888, 512
  %891 = icmp eq i32 %890, 0		; visa id: 949
  br i1 %891, label %.preheader1.3..preheader1.3_crit_edge, label %893, !stats.blockFrequency.digits !8799, !stats.blockFrequency.scale !8800		; visa id: 952

.preheader1.3..preheader1.3_crit_edge:            ; preds = %.preheader1.3
; BB103 :
  %892 = shl i32 %888, 1		; visa id: 954
  br label %.preheader1.3, !stats.blockFrequency.digits !8801, !stats.blockFrequency.scale !8802		; visa id: 955

893:                                              ; preds = %.preheader1.3
; BB104 :
  %.lcssa460 = phi i32 [ %888, %.preheader1.3 ]
  %.lcssa459 = phi i32 [ %889, %.preheader1.3 ]
  %894 = shl i32 %.lcssa459, 23		; visa id: 957
  %895 = add i32 %894, 1065353216		; visa id: 958
  %896 = shl i32 %.lcssa460, 14		; visa id: 959
  %897 = and i32 %896, 8372224		; visa id: 960
  %898 = or i32 %895, %897
  %899 = or i32 %898, %137		; visa id: 961
  br label %._crit_edge45.3, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 963

NodeBlock.3.._crit_edge45.3_crit_edge:            ; preds = %NodeBlock.3
; BB105 :
  br label %._crit_edge45.3, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 966

._crit_edge45.3:                                  ; preds = %NodeBlock.3.._crit_edge45.3_crit_edge, %893
; BB106 :
  %900 = phi i32 [ %899, %893 ], [ %.mux.mux, %NodeBlock.3.._crit_edge45.3_crit_edge ]
  %901 = bitcast i32 %900 to float
  %902 = load i8, ptr addrspace(1) %179, align 1, !noalias !8793		; visa id: 967
  %b2s432 = sext i8 %902 to i16
  %903 = trunc i16 %b2s431 to i8		; visa id: 969
  %904 = zext i8 %903 to i32		; visa id: 970
  %905 = shl nuw nsw i32 %904, 11		; visa id: 971
  %906 = zext i16 %885 to i32		; visa id: 972
  %907 = shl nuw nsw i32 %906, 3		; visa id: 973
  %908 = and i32 %907, 2040
  %909 = or i32 %905, %908		; visa id: 974
  %910 = zext i32 %909 to i64		; visa id: 975
  %911 = add i64 %sink_395, %910		; visa id: 976
  %912 = inttoptr i64 %911 to ptr addrspace(1)		; visa id: 977
  %913 = load <2 x i32>, ptr addrspace(1) %912, align 4		; visa id: 977
  %b2s433 = zext i8 %902 to i16		; visa id: 978
  %b2s434 = lshr i16 %b2s433, 4		; visa id: 979
  %914 = trunc i16 %b2s434 to i8		; visa id: 980
  %915 = uitofp i8 %914 to float		; visa id: 981
  %916 = fadd float %915, 5.000000e-01		; visa id: 982
  %917 = fmul float %916, %901		; visa id: 983
  %918 = fmul float %917, 2.500000e-01		; visa id: 984
  %919 = extractelement <2 x i32> %913, i32 0		; visa id: 985
  %920 = extractelement <2 x i32> %913, i32 1		; visa id: 985
  %921 = and i32 %900, 2139095040		; visa id: 985
  %922 = bitcast float %918 to i32
  %923 = and i32 %922, 2147483647		; visa id: 986
  %924 = icmp eq i32 %921, 2139095040
  %925 = icmp ugt i32 %923, 2139095040		; visa id: 987
  %926 = or i1 %924, %925		; visa id: 988
  %927 = and i32 %919, 255		; visa id: 990
  br i1 %926, label %935, label %928, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 991

928:                                              ; preds = %._crit_edge45.3
; BB107 :
  %929 = and i32 %906, 256
  %930 = sub nsw i32 0, %927, !spirv.Decorations !8798
  %931 = icmp eq i32 %929, 0		; visa id: 993
  %932 = select i1 %931, i32 %927, i32 %930		; visa id: 995
  %933 = sitofp i32 %932 to float		; visa id: 996
  %934 = fmul float %918, %933		; visa id: 997
  br label %943, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 998

935:                                              ; preds = %._crit_edge45.3
; BB108 :
  %936 = uitofp i32 %927 to float		; visa id: 1000
  %937 = fmul float %918, %936		; visa id: 1001
  %938 = and i32 %906, 256
  %939 = icmp eq i32 %938, 0		; visa id: 1002
  %940 = select i1 %939, i32 1, i32 -1		; visa id: 1004
  %941 = sitofp i32 %940 to float		; visa id: 1005
  %942 = fmul float %937, %941		; visa id: 1006
  br label %943, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1007

943:                                              ; preds = %935, %928
; BB109 :
  %.sroa.0125.3 = phi float [ %942, %935 ], [ %934, %928 ]
  %944 = bitcast i32 %919 to <4 x i8>
  %945 = extractelement <4 x i8> %944, i32 1
  %946 = zext i8 %945 to i32		; visa id: 1008
  br i1 %926, label %954, label %947, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1009

947:                                              ; preds = %943
; BB110 :
  %948 = and i32 %906, 512
  %949 = sub nsw i32 0, %946, !spirv.Decorations !8798
  %950 = icmp eq i32 %948, 0		; visa id: 1011
  %951 = select i1 %950, i32 %946, i32 %949		; visa id: 1013
  %952 = sitofp i32 %951 to float		; visa id: 1014
  %953 = fmul float %918, %952		; visa id: 1015
  br label %962, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1016

954:                                              ; preds = %943
; BB111 :
  %955 = uitofp i32 %946 to float		; visa id: 1018
  %956 = fmul float %918, %955		; visa id: 1019
  %957 = and i32 %906, 512
  %958 = icmp eq i32 %957, 0		; visa id: 1020
  %959 = select i1 %958, i32 1, i32 -1		; visa id: 1022
  %960 = sitofp i32 %959 to float		; visa id: 1023
  %961 = fmul float %956, %960		; visa id: 1024
  br label %962, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1025

962:                                              ; preds = %954, %947
; BB112 :
  %.sroa.40.3 = phi float [ %961, %954 ], [ %953, %947 ]
  %963 = extractelement <4 x i8> %944, i32 2
  %964 = zext i8 %963 to i32		; visa id: 1026
  br i1 %926, label %972, label %965, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1027

965:                                              ; preds = %962
; BB113 :
  %966 = and i32 %906, 1024
  %967 = sub nsw i32 0, %964, !spirv.Decorations !8798
  %968 = icmp eq i32 %966, 0		; visa id: 1029
  %969 = select i1 %968, i32 %964, i32 %967		; visa id: 1031
  %970 = sitofp i32 %969 to float		; visa id: 1032
  %971 = fmul float %918, %970		; visa id: 1033
  br label %980, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1034

972:                                              ; preds = %962
; BB114 :
  %973 = uitofp i32 %964 to float		; visa id: 1036
  %974 = fmul float %918, %973		; visa id: 1037
  %975 = and i32 %906, 1024
  %976 = icmp eq i32 %975, 0		; visa id: 1038
  %977 = select i1 %976, i32 1, i32 -1		; visa id: 1040
  %978 = sitofp i32 %977 to float		; visa id: 1041
  %979 = fmul float %974, %978		; visa id: 1042
  br label %980, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1043

980:                                              ; preds = %972, %965
; BB115 :
  %.sroa.64140.3 = phi float [ %979, %972 ], [ %971, %965 ]
  %981 = lshr i32 %919, 24		; visa id: 1044
  br i1 %926, label %989, label %982, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1045

982:                                              ; preds = %980
; BB116 :
  %983 = and i32 %906, 2048
  %984 = sub nsw i32 0, %981, !spirv.Decorations !8798
  %985 = icmp eq i32 %983, 0		; visa id: 1047
  %986 = select i1 %985, i32 %981, i32 %984		; visa id: 1049
  %987 = sitofp i32 %986 to float		; visa id: 1050
  %988 = fmul float %918, %987		; visa id: 1051
  br label %997, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1052

989:                                              ; preds = %980
; BB117 :
  %990 = uitofp i32 %981 to float		; visa id: 1054
  %991 = fmul float %918, %990		; visa id: 1055
  %992 = and i32 %906, 2048
  %993 = icmp eq i32 %992, 0		; visa id: 1056
  %994 = select i1 %993, i32 1, i32 -1		; visa id: 1058
  %995 = sitofp i32 %994 to float		; visa id: 1059
  %996 = fmul float %991, %995		; visa id: 1060
  br label %997, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1061

997:                                              ; preds = %989, %982
; BB118 :
  %.sroa.88.3 = phi float [ %996, %989 ], [ %988, %982 ]
  %998 = and i32 %920, 255		; visa id: 1062
  br i1 %926, label %1006, label %999, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1063

999:                                              ; preds = %997
; BB119 :
  %1000 = and i32 %906, 4096
  %1001 = sub nsw i32 0, %998, !spirv.Decorations !8798
  %1002 = icmp eq i32 %1000, 0		; visa id: 1065
  %1003 = select i1 %1002, i32 %998, i32 %1001		; visa id: 1067
  %1004 = sitofp i32 %1003 to float		; visa id: 1068
  %1005 = fmul float %918, %1004		; visa id: 1069
  br label %1014, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1070

1006:                                             ; preds = %997
; BB120 :
  %1007 = uitofp i32 %998 to float		; visa id: 1072
  %1008 = fmul float %918, %1007		; visa id: 1073
  %1009 = and i32 %906, 4096
  %1010 = icmp eq i32 %1009, 0		; visa id: 1074
  %1011 = select i1 %1010, i32 1, i32 -1		; visa id: 1076
  %1012 = sitofp i32 %1011 to float		; visa id: 1077
  %1013 = fmul float %1008, %1012		; visa id: 1078
  br label %1014, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1079

1014:                                             ; preds = %1006, %999
; BB121 :
  %.sroa.112155.3 = phi float [ %1013, %1006 ], [ %1005, %999 ]
  %1015 = bitcast i32 %920 to <4 x i8>
  %1016 = extractelement <4 x i8> %1015, i32 1
  %1017 = zext i8 %1016 to i32		; visa id: 1080
  br i1 %926, label %1025, label %1018, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1081

1018:                                             ; preds = %1014
; BB122 :
  %1019 = and i32 %906, 8192
  %1020 = sub nsw i32 0, %1017, !spirv.Decorations !8798
  %1021 = icmp eq i32 %1019, 0		; visa id: 1083
  %1022 = select i1 %1021, i32 %1017, i32 %1020		; visa id: 1085
  %1023 = sitofp i32 %1022 to float		; visa id: 1086
  %1024 = fmul float %918, %1023		; visa id: 1087
  br label %1033, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1088

1025:                                             ; preds = %1014
; BB123 :
  %1026 = uitofp i32 %1017 to float		; visa id: 1090
  %1027 = fmul float %918, %1026		; visa id: 1091
  %1028 = and i32 %906, 8192
  %1029 = icmp eq i32 %1028, 0		; visa id: 1092
  %1030 = select i1 %1029, i32 1, i32 -1		; visa id: 1094
  %1031 = sitofp i32 %1030 to float		; visa id: 1095
  %1032 = fmul float %1027, %1031		; visa id: 1096
  br label %1033, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1097

1033:                                             ; preds = %1025, %1018
; BB124 :
  %.sroa.136.3 = phi float [ %1032, %1025 ], [ %1024, %1018 ]
  %1034 = extractelement <4 x i8> %1015, i32 2
  %1035 = zext i8 %1034 to i32		; visa id: 1098
  br i1 %926, label %1043, label %1036, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1099

1036:                                             ; preds = %1033
; BB125 :
  %1037 = and i32 %906, 16384
  %1038 = sub nsw i32 0, %1035, !spirv.Decorations !8798
  %1039 = icmp eq i32 %1037, 0		; visa id: 1101
  %1040 = select i1 %1039, i32 %1035, i32 %1038		; visa id: 1103
  %1041 = sitofp i32 %1040 to float		; visa id: 1104
  %1042 = fmul float %918, %1041		; visa id: 1105
  br label %1051, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1106

1043:                                             ; preds = %1033
; BB126 :
  %1044 = uitofp i32 %1035 to float		; visa id: 1108
  %1045 = fmul float %918, %1044		; visa id: 1109
  %1046 = and i32 %906, 16384
  %1047 = icmp eq i32 %1046, 0		; visa id: 1110
  %1048 = select i1 %1047, i32 1, i32 -1		; visa id: 1112
  %1049 = sitofp i32 %1048 to float		; visa id: 1113
  %1050 = fmul float %1045, %1049		; visa id: 1114
  br label %1051, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1115

1051:                                             ; preds = %1043, %1036
; BB127 :
  %.sroa.160.3 = phi float [ %1050, %1043 ], [ %1042, %1036 ]
  %1052 = lshr i32 %920, 24		; visa id: 1116
  br i1 %926, label %1059, label %1053, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1117

1053:                                             ; preds = %1051
; BB128 :
  %1054 = sub nsw i32 0, %1052, !spirv.Decorations !8798
  %1055 = icmp slt i16 %885, 0		; visa id: 1119
  %1056 = select i1 %1055, i32 %1054, i32 %1052		; visa id: 1120
  %1057 = sitofp i32 %1056 to float		; visa id: 1121
  %1058 = fmul float %918, %1057		; visa id: 1122
  br label %NodeBlock.4, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1123

1059:                                             ; preds = %1051
; BB129 :
  %1060 = uitofp i32 %1052 to float		; visa id: 1125
  %1061 = fmul float %918, %1060		; visa id: 1126
  %1062 = fsub float 0.000000e+00, %1061
  %1063 = icmp slt i16 %885, 0		; visa id: 1127
  %1064 = select i1 %1063, float %1062, float %1061		; visa id: 1128
  br label %NodeBlock.4, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1129

NodeBlock.4:                                      ; preds = %1059, %1053
; BB130 :
  %.sroa.184.3 = phi float [ %1064, %1059 ], [ %1058, %1053 ]
  %1065 = shl nuw i32 %881, 1		; visa id: 1130
  %1066 = zext i32 %1065 to i64		; visa id: 1131
  %1067 = add i64 %1066, %const_reg_qword2		; visa id: 1132
  %IntToPtr2349 = inttoptr i64 %1067 to ptr addrspace(1)		; visa id: 1133
  %vCastload350 = load i32, ptr addrspace(1) %IntToPtr2349, align 2		; visa id: 1133
  %1068 = add i64 %1067, 4
  %IntToPtr2351 = inttoptr i64 %1068 to ptr addrspace(1)
  %vCastload352 = load i32, ptr addrspace(1) %IntToPtr2351, align 2		; visa id: 1134
  %1069 = add i64 %1067, 8
  %IntToPtr2353 = inttoptr i64 %1069 to ptr addrspace(1)
  %vCastload354 = load i32, ptr addrspace(1) %IntToPtr2353, align 2		; visa id: 1135
  %1070 = add i64 %1067, 12
  %IntToPtr2355 = inttoptr i64 %1070 to ptr addrspace(1)
  %vCastload356 = load i32, ptr addrspace(1) %IntToPtr2355, align 2		; visa id: 1136
  %1071 = bitcast i32 %vCastload350 to <2 x i16>		; visa id: 1137
  %1072 = bitcast i32 %vCastload352 to <2 x i16>		; visa id: 1139
  %1073 = extractelement <2 x i16> %1071, i32 0		; visa id: 1141
  %1074 = extractelement <2 x i16> %1071, i32 1		; visa id: 1141
  %1075 = extractelement <2 x i16> %1072, i32 0		; visa id: 1141
  %1076 = extractelement <2 x i16> %1072, i32 1		; visa id: 1141
  %1077 = bitcast i32 %vCastload354 to <2 x i16>		; visa id: 1141
  %1078 = bitcast i32 %vCastload356 to <2 x i16>		; visa id: 1143
  %1079 = extractelement <2 x i16> %1077, i32 0		; visa id: 1145
  %1080 = extractelement <2 x i16> %1077, i32 1		; visa id: 1145
  %1081 = extractelement <2 x i16> %1078, i32 0		; visa id: 1145
  %1082 = extractelement <2 x i16> %1078, i32 1		; visa id: 1145
  %1083 = zext i16 %1073 to i32		; visa id: 1145
  %1084 = shl nuw i32 %1083, 16, !spirv.Decorations !8788		; visa id: 1146
  %1085 = bitcast i32 %1084 to float
  %1086 = fmul float %.sroa.0125.3, %1085		; visa id: 1147
  %1087 = fadd float %.sroa.18.0, %1086		; visa id: 1148
  %1088 = zext i16 %1074 to i32		; visa id: 1149
  %1089 = shl nuw i32 %1088, 16, !spirv.Decorations !8788		; visa id: 1150
  %1090 = bitcast i32 %1089 to float
  %1091 = fmul float %.sroa.40.3, %1090		; visa id: 1151
  %1092 = fadd float %1087, %1091		; visa id: 1152
  %1093 = zext i16 %1075 to i32		; visa id: 1153
  %1094 = shl nuw i32 %1093, 16, !spirv.Decorations !8788		; visa id: 1154
  %1095 = bitcast i32 %1094 to float
  %1096 = fmul float %.sroa.64140.3, %1095		; visa id: 1155
  %1097 = fadd float %1092, %1096		; visa id: 1156
  %1098 = zext i16 %1076 to i32		; visa id: 1157
  %1099 = shl nuw i32 %1098, 16, !spirv.Decorations !8788		; visa id: 1158
  %1100 = bitcast i32 %1099 to float
  %1101 = fmul float %.sroa.88.3, %1100		; visa id: 1159
  %1102 = fadd float %1097, %1101		; visa id: 1160
  %1103 = zext i16 %1079 to i32		; visa id: 1161
  %1104 = shl nuw i32 %1103, 16, !spirv.Decorations !8788		; visa id: 1162
  %1105 = bitcast i32 %1104 to float
  %1106 = fmul float %.sroa.112155.3, %1105		; visa id: 1163
  %1107 = fadd float %1102, %1106		; visa id: 1164
  %1108 = zext i16 %1080 to i32		; visa id: 1165
  %1109 = shl nuw i32 %1108, 16, !spirv.Decorations !8788		; visa id: 1166
  %1110 = bitcast i32 %1109 to float
  %1111 = fmul float %.sroa.136.3, %1110		; visa id: 1167
  %1112 = fadd float %1107, %1111		; visa id: 1168
  %1113 = zext i16 %1081 to i32		; visa id: 1169
  %1114 = shl nuw i32 %1113, 16, !spirv.Decorations !8788		; visa id: 1170
  %1115 = bitcast i32 %1114 to float
  %1116 = fmul float %.sroa.160.3, %1115		; visa id: 1171
  %1117 = fadd float %1112, %1116		; visa id: 1172
  %1118 = zext i16 %1082 to i32		; visa id: 1173
  %1119 = shl nuw i32 %1118, 16, !spirv.Decorations !8788		; visa id: 1174
  %1120 = bitcast i32 %1119 to float
  %1121 = fmul float %.sroa.184.3, %1120		; visa id: 1175
  %1122 = fadd float %1117, %1121		; visa id: 1176
  %1123 = or i32 %108, %114		; visa id: 1177
  %sink_406 = lshr exact i32 %108, 2		; visa id: 1178
  %sink_391 = zext i32 %sink_406 to i64		; visa id: 1179
  %1124 = add i64 %117, %sink_391		; visa id: 1180
  %1125 = inttoptr i64 %1124 to ptr addrspace(4)		; visa id: 1181
  %1126 = addrspacecast ptr addrspace(4) %1125 to ptr addrspace(1)		; visa id: 1181
  %1127 = load i16, ptr addrspace(1) %1126, align 2, !noalias !8793		; visa id: 1182
  %sink_414 = lshr exact i32 %108, 5		; visa id: 1184
  %sink_400 = zext i32 %sink_414 to i64		; visa id: 1185
  %1128 = add i64 %120, %sink_400		; visa id: 1186
  %1129 = inttoptr i64 %1128 to ptr addrspace(4)		; visa id: 1187
  %1130 = addrspacecast ptr addrspace(4) %1129 to ptr addrspace(1)		; visa id: 1187
  %1131 = load i8, ptr addrspace(1) %1130, align 1, !noalias !8793		; visa id: 1188
  %1132 = zext i16 %1127 to i32		; visa id: 1189
  %1133 = and i32 %1132, 255
  %1134 = zext i8 %1131 to i32		; visa id: 1190
  %1135 = shl nuw nsw i32 %1134, 8, !spirv.Decorations !8791		; visa id: 1190
  %1136 = and i32 %1135, 768		; visa id: 1191
  %1137 = or i32 %1133, %1136		; visa id: 1192
  br i1 %160, label %NodeBlock.4.._crit_edge45.4_crit_edge, label %.preheader1.4.preheader, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1193

.preheader1.4.preheader:                          ; preds = %NodeBlock.4
; BB131 :
  br label %.preheader1.4, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1197

.preheader1.4:                                    ; preds = %.preheader1.4..preheader1.4_crit_edge, %.preheader1.4.preheader
; BB132 :
  %1138 = phi i32 [ %1140, %.preheader1.4..preheader1.4_crit_edge ], [ -14, %.preheader1.4.preheader ]
  %1139 = phi i32 [ %1143, %.preheader1.4..preheader1.4_crit_edge ], [ %141, %.preheader1.4.preheader ]
  %1140 = add nsw i32 %1138, -1, !spirv.Decorations !8798		; visa id: 1198
  %1141 = and i32 %1139, 512
  %1142 = icmp eq i32 %1141, 0		; visa id: 1199
  br i1 %1142, label %.preheader1.4..preheader1.4_crit_edge, label %1144, !stats.blockFrequency.digits !8799, !stats.blockFrequency.scale !8800		; visa id: 1202

.preheader1.4..preheader1.4_crit_edge:            ; preds = %.preheader1.4
; BB133 :
  %1143 = shl i32 %1139, 1		; visa id: 1204
  br label %.preheader1.4, !stats.blockFrequency.digits !8801, !stats.blockFrequency.scale !8802		; visa id: 1205

1144:                                             ; preds = %.preheader1.4
; BB134 :
  %.lcssa462 = phi i32 [ %1139, %.preheader1.4 ]
  %.lcssa461 = phi i32 [ %1140, %.preheader1.4 ]
  %1145 = shl i32 %.lcssa461, 23		; visa id: 1207
  %1146 = add i32 %1145, 1065353216		; visa id: 1208
  %1147 = shl i32 %.lcssa462, 14		; visa id: 1209
  %1148 = and i32 %1147, 8372224		; visa id: 1210
  %1149 = or i32 %1146, %1148
  %1150 = or i32 %1149, %137		; visa id: 1211
  br label %._crit_edge45.4, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1213

NodeBlock.4.._crit_edge45.4_crit_edge:            ; preds = %NodeBlock.4
; BB135 :
  br label %._crit_edge45.4, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1216

._crit_edge45.4:                                  ; preds = %NodeBlock.4.._crit_edge45.4_crit_edge, %1144
; BB136 :
  %1151 = phi i32 [ %1150, %1144 ], [ %.mux.mux, %NodeBlock.4.._crit_edge45.4_crit_edge ]
  %1152 = bitcast i32 %1151 to float
  %1153 = add i64 %125, %sink_400		; visa id: 1217
  %1154 = inttoptr i64 %1153 to ptr addrspace(4)		; visa id: 1218
  %1155 = addrspacecast ptr addrspace(4) %1154 to ptr addrspace(1)		; visa id: 1218
  %1156 = load i8, ptr addrspace(1) %1155, align 1, !noalias !8793		; visa id: 1219
  %b2s435 = sext i8 %1156 to i16		; visa id: 1221
  %1157 = shl nuw nsw i32 %1137, 3, !spirv.Decorations !8791		; visa id: 1222
  %1158 = zext i32 %1157 to i64		; visa id: 1223
  %1159 = add i64 %sink_395, %1158		; visa id: 1224
  %1160 = inttoptr i64 %1159 to ptr addrspace(1)		; visa id: 1225
  %1161 = load <2 x i32>, ptr addrspace(1) %1160, align 4		; visa id: 1225
  %b2s436 = and i16 %b2s435, 15		; visa id: 1226
  %1162 = trunc i16 %b2s436 to i8		; visa id: 1227
  %1163 = uitofp i8 %1162 to float		; visa id: 1228
  %1164 = fadd float %1163, 5.000000e-01		; visa id: 1229
  %1165 = fmul float %1164, %1152		; visa id: 1230
  %1166 = fmul float %1165, 2.500000e-01		; visa id: 1231
  %1167 = extractelement <2 x i32> %1161, i32 0		; visa id: 1232
  %1168 = extractelement <2 x i32> %1161, i32 1		; visa id: 1232
  %1169 = and i32 %1151, 2139095040		; visa id: 1232
  %1170 = bitcast float %1166 to i32
  %1171 = and i32 %1170, 2147483647		; visa id: 1233
  %1172 = icmp eq i32 %1169, 2139095040
  %1173 = icmp ugt i32 %1171, 2139095040		; visa id: 1234
  %1174 = or i1 %1172, %1173		; visa id: 1235
  %1175 = and i32 %1167, 255		; visa id: 1237
  br i1 %1174, label %1183, label %1176, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1238

1176:                                             ; preds = %._crit_edge45.4
; BB137 :
  %1177 = and i32 %1132, 256
  %1178 = sub nsw i32 0, %1175, !spirv.Decorations !8798
  %1179 = icmp eq i32 %1177, 0		; visa id: 1240
  %1180 = select i1 %1179, i32 %1175, i32 %1178		; visa id: 1242
  %1181 = sitofp i32 %1180 to float		; visa id: 1243
  %1182 = fmul float %1166, %1181		; visa id: 1244
  br label %1191, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1245

1183:                                             ; preds = %._crit_edge45.4
; BB138 :
  %1184 = uitofp i32 %1175 to float		; visa id: 1247
  %1185 = fmul float %1166, %1184		; visa id: 1248
  %1186 = and i32 %1132, 256
  %1187 = icmp eq i32 %1186, 0		; visa id: 1249
  %1188 = select i1 %1187, i32 1, i32 -1		; visa id: 1251
  %1189 = sitofp i32 %1188 to float		; visa id: 1252
  %1190 = fmul float %1185, %1189		; visa id: 1253
  br label %1191, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1254

1191:                                             ; preds = %1183, %1176
; BB139 :
  %.sroa.0125.4 = phi float [ %1190, %1183 ], [ %1182, %1176 ]
  %1192 = bitcast i32 %1167 to <4 x i8>
  %1193 = extractelement <4 x i8> %1192, i32 1
  %1194 = zext i8 %1193 to i32		; visa id: 1255
  br i1 %1174, label %1202, label %1195, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1256

1195:                                             ; preds = %1191
; BB140 :
  %1196 = and i32 %1132, 512
  %1197 = sub nsw i32 0, %1194, !spirv.Decorations !8798
  %1198 = icmp eq i32 %1196, 0		; visa id: 1258
  %1199 = select i1 %1198, i32 %1194, i32 %1197		; visa id: 1260
  %1200 = sitofp i32 %1199 to float		; visa id: 1261
  %1201 = fmul float %1166, %1200		; visa id: 1262
  br label %1210, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1263

1202:                                             ; preds = %1191
; BB141 :
  %1203 = uitofp i32 %1194 to float		; visa id: 1265
  %1204 = fmul float %1166, %1203		; visa id: 1266
  %1205 = and i32 %1132, 512
  %1206 = icmp eq i32 %1205, 0		; visa id: 1267
  %1207 = select i1 %1206, i32 1, i32 -1		; visa id: 1269
  %1208 = sitofp i32 %1207 to float		; visa id: 1270
  %1209 = fmul float %1204, %1208		; visa id: 1271
  br label %1210, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1272

1210:                                             ; preds = %1202, %1195
; BB142 :
  %.sroa.40.4 = phi float [ %1209, %1202 ], [ %1201, %1195 ]
  %1211 = extractelement <4 x i8> %1192, i32 2
  %1212 = zext i8 %1211 to i32		; visa id: 1273
  br i1 %1174, label %1220, label %1213, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1274

1213:                                             ; preds = %1210
; BB143 :
  %1214 = and i32 %1132, 1024
  %1215 = sub nsw i32 0, %1212, !spirv.Decorations !8798
  %1216 = icmp eq i32 %1214, 0		; visa id: 1276
  %1217 = select i1 %1216, i32 %1212, i32 %1215		; visa id: 1278
  %1218 = sitofp i32 %1217 to float		; visa id: 1279
  %1219 = fmul float %1166, %1218		; visa id: 1280
  br label %1228, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1281

1220:                                             ; preds = %1210
; BB144 :
  %1221 = uitofp i32 %1212 to float		; visa id: 1283
  %1222 = fmul float %1166, %1221		; visa id: 1284
  %1223 = and i32 %1132, 1024
  %1224 = icmp eq i32 %1223, 0		; visa id: 1285
  %1225 = select i1 %1224, i32 1, i32 -1		; visa id: 1287
  %1226 = sitofp i32 %1225 to float		; visa id: 1288
  %1227 = fmul float %1222, %1226		; visa id: 1289
  br label %1228, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1290

1228:                                             ; preds = %1220, %1213
; BB145 :
  %.sroa.64140.4 = phi float [ %1227, %1220 ], [ %1219, %1213 ]
  %1229 = lshr i32 %1167, 24		; visa id: 1291
  br i1 %1174, label %1237, label %1230, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1292

1230:                                             ; preds = %1228
; BB146 :
  %1231 = and i32 %1132, 2048
  %1232 = sub nsw i32 0, %1229, !spirv.Decorations !8798
  %1233 = icmp eq i32 %1231, 0		; visa id: 1294
  %1234 = select i1 %1233, i32 %1229, i32 %1232		; visa id: 1296
  %1235 = sitofp i32 %1234 to float		; visa id: 1297
  %1236 = fmul float %1166, %1235		; visa id: 1298
  br label %1245, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1299

1237:                                             ; preds = %1228
; BB147 :
  %1238 = uitofp i32 %1229 to float		; visa id: 1301
  %1239 = fmul float %1166, %1238		; visa id: 1302
  %1240 = and i32 %1132, 2048
  %1241 = icmp eq i32 %1240, 0		; visa id: 1303
  %1242 = select i1 %1241, i32 1, i32 -1		; visa id: 1305
  %1243 = sitofp i32 %1242 to float		; visa id: 1306
  %1244 = fmul float %1239, %1243		; visa id: 1307
  br label %1245, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1308

1245:                                             ; preds = %1237, %1230
; BB148 :
  %.sroa.88.4 = phi float [ %1244, %1237 ], [ %1236, %1230 ]
  %1246 = and i32 %1168, 255		; visa id: 1309
  br i1 %1174, label %1254, label %1247, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1310

1247:                                             ; preds = %1245
; BB149 :
  %1248 = and i32 %1132, 4096
  %1249 = sub nsw i32 0, %1246, !spirv.Decorations !8798
  %1250 = icmp eq i32 %1248, 0		; visa id: 1312
  %1251 = select i1 %1250, i32 %1246, i32 %1249		; visa id: 1314
  %1252 = sitofp i32 %1251 to float		; visa id: 1315
  %1253 = fmul float %1166, %1252		; visa id: 1316
  br label %1262, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1317

1254:                                             ; preds = %1245
; BB150 :
  %1255 = uitofp i32 %1246 to float		; visa id: 1319
  %1256 = fmul float %1166, %1255		; visa id: 1320
  %1257 = and i32 %1132, 4096
  %1258 = icmp eq i32 %1257, 0		; visa id: 1321
  %1259 = select i1 %1258, i32 1, i32 -1		; visa id: 1323
  %1260 = sitofp i32 %1259 to float		; visa id: 1324
  %1261 = fmul float %1256, %1260		; visa id: 1325
  br label %1262, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1326

1262:                                             ; preds = %1254, %1247
; BB151 :
  %.sroa.112155.4 = phi float [ %1261, %1254 ], [ %1253, %1247 ]
  %1263 = bitcast i32 %1168 to <4 x i8>
  %1264 = extractelement <4 x i8> %1263, i32 1
  %1265 = zext i8 %1264 to i32		; visa id: 1327
  br i1 %1174, label %1273, label %1266, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1328

1266:                                             ; preds = %1262
; BB152 :
  %1267 = and i32 %1132, 8192
  %1268 = sub nsw i32 0, %1265, !spirv.Decorations !8798
  %1269 = icmp eq i32 %1267, 0		; visa id: 1330
  %1270 = select i1 %1269, i32 %1265, i32 %1268		; visa id: 1332
  %1271 = sitofp i32 %1270 to float		; visa id: 1333
  %1272 = fmul float %1166, %1271		; visa id: 1334
  br label %1281, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1335

1273:                                             ; preds = %1262
; BB153 :
  %1274 = uitofp i32 %1265 to float		; visa id: 1337
  %1275 = fmul float %1166, %1274		; visa id: 1338
  %1276 = and i32 %1132, 8192
  %1277 = icmp eq i32 %1276, 0		; visa id: 1339
  %1278 = select i1 %1277, i32 1, i32 -1		; visa id: 1341
  %1279 = sitofp i32 %1278 to float		; visa id: 1342
  %1280 = fmul float %1275, %1279		; visa id: 1343
  br label %1281, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1344

1281:                                             ; preds = %1273, %1266
; BB154 :
  %.sroa.136.4 = phi float [ %1280, %1273 ], [ %1272, %1266 ]
  %1282 = extractelement <4 x i8> %1263, i32 2
  %1283 = zext i8 %1282 to i32		; visa id: 1345
  br i1 %1174, label %1291, label %1284, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1346

1284:                                             ; preds = %1281
; BB155 :
  %1285 = and i32 %1132, 16384
  %1286 = sub nsw i32 0, %1283, !spirv.Decorations !8798
  %1287 = icmp eq i32 %1285, 0		; visa id: 1348
  %1288 = select i1 %1287, i32 %1283, i32 %1286		; visa id: 1350
  %1289 = sitofp i32 %1288 to float		; visa id: 1351
  %1290 = fmul float %1166, %1289		; visa id: 1352
  br label %1299, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1353

1291:                                             ; preds = %1281
; BB156 :
  %1292 = uitofp i32 %1283 to float		; visa id: 1355
  %1293 = fmul float %1166, %1292		; visa id: 1356
  %1294 = and i32 %1132, 16384
  %1295 = icmp eq i32 %1294, 0		; visa id: 1357
  %1296 = select i1 %1295, i32 1, i32 -1		; visa id: 1359
  %1297 = sitofp i32 %1296 to float		; visa id: 1360
  %1298 = fmul float %1293, %1297		; visa id: 1361
  br label %1299, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1362

1299:                                             ; preds = %1291, %1284
; BB157 :
  %.sroa.160.4 = phi float [ %1298, %1291 ], [ %1290, %1284 ]
  %1300 = lshr i32 %1168, 24		; visa id: 1363
  br i1 %1174, label %1307, label %1301, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1364

1301:                                             ; preds = %1299
; BB158 :
  %1302 = sub nsw i32 0, %1300, !spirv.Decorations !8798
  %1303 = icmp slt i16 %1127, 0		; visa id: 1366
  %1304 = select i1 %1303, i32 %1302, i32 %1300		; visa id: 1367
  %1305 = sitofp i32 %1304 to float		; visa id: 1368
  %1306 = fmul float %1166, %1305		; visa id: 1369
  br label %NodeBlock.5, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1370

1307:                                             ; preds = %1299
; BB159 :
  %1308 = uitofp i32 %1300 to float		; visa id: 1372
  %1309 = fmul float %1166, %1308		; visa id: 1373
  %1310 = fsub float 0.000000e+00, %1309
  %1311 = icmp slt i16 %1127, 0		; visa id: 1374
  %1312 = select i1 %1311, float %1310, float %1309		; visa id: 1375
  br label %NodeBlock.5, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1376

NodeBlock.5:                                      ; preds = %1307, %1301
; BB160 :
  %.sroa.184.4 = phi float [ %1312, %1307 ], [ %1306, %1301 ]
  %1313 = shl nuw i32 %1123, 1		; visa id: 1377
  %1314 = zext i32 %1313 to i64		; visa id: 1378
  %1315 = add i64 %1314, %const_reg_qword2		; visa id: 1379
  %IntToPtr2357 = inttoptr i64 %1315 to ptr addrspace(1)		; visa id: 1380
  %vCastload358 = load i32, ptr addrspace(1) %IntToPtr2357, align 2		; visa id: 1380
  %1316 = add i64 %1315, 4
  %IntToPtr2359 = inttoptr i64 %1316 to ptr addrspace(1)
  %vCastload360 = load i32, ptr addrspace(1) %IntToPtr2359, align 2		; visa id: 1381
  %1317 = add i64 %1315, 8
  %IntToPtr2361 = inttoptr i64 %1317 to ptr addrspace(1)
  %vCastload362 = load i32, ptr addrspace(1) %IntToPtr2361, align 2		; visa id: 1382
  %1318 = add i64 %1315, 12
  %IntToPtr2363 = inttoptr i64 %1318 to ptr addrspace(1)
  %vCastload364 = load i32, ptr addrspace(1) %IntToPtr2363, align 2		; visa id: 1383
  %1319 = bitcast i32 %vCastload358 to <2 x i16>		; visa id: 1384
  %1320 = bitcast i32 %vCastload360 to <2 x i16>		; visa id: 1386
  %1321 = extractelement <2 x i16> %1319, i32 0		; visa id: 1388
  %1322 = extractelement <2 x i16> %1319, i32 1		; visa id: 1388
  %1323 = extractelement <2 x i16> %1320, i32 0		; visa id: 1388
  %1324 = extractelement <2 x i16> %1320, i32 1		; visa id: 1388
  %1325 = bitcast i32 %vCastload362 to <2 x i16>		; visa id: 1388
  %1326 = bitcast i32 %vCastload364 to <2 x i16>		; visa id: 1390
  %1327 = extractelement <2 x i16> %1325, i32 0		; visa id: 1392
  %1328 = extractelement <2 x i16> %1325, i32 1		; visa id: 1392
  %1329 = extractelement <2 x i16> %1326, i32 0		; visa id: 1392
  %1330 = extractelement <2 x i16> %1326, i32 1		; visa id: 1392
  %1331 = zext i16 %1321 to i32		; visa id: 1392
  %1332 = shl nuw i32 %1331, 16, !spirv.Decorations !8788		; visa id: 1393
  %1333 = bitcast i32 %1332 to float
  %1334 = fmul float %.sroa.0125.4, %1333		; visa id: 1394
  %1335 = fadd float %.sroa.21.0, %1334		; visa id: 1395
  %1336 = zext i16 %1322 to i32		; visa id: 1396
  %1337 = shl nuw i32 %1336, 16, !spirv.Decorations !8788		; visa id: 1397
  %1338 = bitcast i32 %1337 to float
  %1339 = fmul float %.sroa.40.4, %1338		; visa id: 1398
  %1340 = fadd float %1335, %1339		; visa id: 1399
  %1341 = zext i16 %1323 to i32		; visa id: 1400
  %1342 = shl nuw i32 %1341, 16, !spirv.Decorations !8788		; visa id: 1401
  %1343 = bitcast i32 %1342 to float
  %1344 = fmul float %.sroa.64140.4, %1343		; visa id: 1402
  %1345 = fadd float %1340, %1344		; visa id: 1403
  %1346 = zext i16 %1324 to i32		; visa id: 1404
  %1347 = shl nuw i32 %1346, 16, !spirv.Decorations !8788		; visa id: 1405
  %1348 = bitcast i32 %1347 to float
  %1349 = fmul float %.sroa.88.4, %1348		; visa id: 1406
  %1350 = fadd float %1345, %1349		; visa id: 1407
  %1351 = zext i16 %1327 to i32		; visa id: 1408
  %1352 = shl nuw i32 %1351, 16, !spirv.Decorations !8788		; visa id: 1409
  %1353 = bitcast i32 %1352 to float
  %1354 = fmul float %.sroa.112155.4, %1353		; visa id: 1410
  %1355 = fadd float %1350, %1354		; visa id: 1411
  %1356 = zext i16 %1328 to i32		; visa id: 1412
  %1357 = shl nuw i32 %1356, 16, !spirv.Decorations !8788		; visa id: 1413
  %1358 = bitcast i32 %1357 to float
  %1359 = fmul float %.sroa.136.4, %1358		; visa id: 1414
  %1360 = fadd float %1355, %1359		; visa id: 1415
  %1361 = zext i16 %1329 to i32		; visa id: 1416
  %1362 = shl nuw i32 %1361, 16, !spirv.Decorations !8788		; visa id: 1417
  %1363 = bitcast i32 %1362 to float
  %1364 = fmul float %.sroa.160.4, %1363		; visa id: 1418
  %1365 = fadd float %1360, %1364		; visa id: 1419
  %1366 = zext i16 %1330 to i32		; visa id: 1420
  %1367 = shl nuw i32 %1366, 16, !spirv.Decorations !8788		; visa id: 1421
  %1368 = bitcast i32 %1367 to float
  %1369 = fmul float %.sroa.184.4, %1368		; visa id: 1422
  %1370 = fadd float %1365, %1369		; visa id: 1423
  %1371 = or i32 %109, %114		; visa id: 1424
  %sink_405 = lshr exact i32 %109, 2		; visa id: 1425
  %sink_390 = zext i32 %sink_405 to i64		; visa id: 1426
  %1372 = add i64 %117, %sink_390		; visa id: 1427
  %1373 = inttoptr i64 %1372 to ptr addrspace(4)		; visa id: 1428
  %1374 = addrspacecast ptr addrspace(4) %1373 to ptr addrspace(1)		; visa id: 1428
  %1375 = load i16, ptr addrspace(1) %1374, align 2, !noalias !8793		; visa id: 1429
  %sink_413 = lshr i32 %109, 5		; visa id: 1431
  %sink_399 = zext i32 %sink_413 to i64		; visa id: 1432
  %1376 = add i64 %120, %sink_399		; visa id: 1433
  %1377 = inttoptr i64 %1376 to ptr addrspace(4)		; visa id: 1434
  %1378 = addrspacecast ptr addrspace(4) %1377 to ptr addrspace(1)		; visa id: 1434
  %1379 = load i8, ptr addrspace(1) %1378, align 1, !noalias !8793		; visa id: 1435
  %b2s437 = sext i8 %1379 to i16
  %1380 = zext i16 %1375 to i32		; visa id: 1437
  %1381 = and i32 %1380, 255
  %b2s438 = zext i8 %1379 to i16		; visa id: 1438
  %b2s439 = lshr i16 %b2s438, 2		; visa id: 1439
  %1382 = trunc i16 %b2s439 to i8		; visa id: 1440
  %1383 = zext i8 %1382 to i32		; visa id: 1441
  %1384 = shl nuw nsw i32 %1383, 8, !spirv.Decorations !8791		; visa id: 1442
  %1385 = and i32 %1384, 768		; visa id: 1443
  %1386 = or i32 %1381, %1385		; visa id: 1444
  br i1 %160, label %NodeBlock.5.._crit_edge45.5_crit_edge, label %.preheader1.5.preheader, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1445

.preheader1.5.preheader:                          ; preds = %NodeBlock.5
; BB161 :
  br label %.preheader1.5, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1449

.preheader1.5:                                    ; preds = %.preheader1.5..preheader1.5_crit_edge, %.preheader1.5.preheader
; BB162 :
  %1387 = phi i32 [ %1389, %.preheader1.5..preheader1.5_crit_edge ], [ -14, %.preheader1.5.preheader ]
  %1388 = phi i32 [ %1392, %.preheader1.5..preheader1.5_crit_edge ], [ %141, %.preheader1.5.preheader ]
  %1389 = add nsw i32 %1387, -1, !spirv.Decorations !8798		; visa id: 1450
  %1390 = and i32 %1388, 512
  %1391 = icmp eq i32 %1390, 0		; visa id: 1451
  br i1 %1391, label %.preheader1.5..preheader1.5_crit_edge, label %1393, !stats.blockFrequency.digits !8799, !stats.blockFrequency.scale !8800		; visa id: 1454

.preheader1.5..preheader1.5_crit_edge:            ; preds = %.preheader1.5
; BB163 :
  %1392 = shl i32 %1388, 1		; visa id: 1456
  br label %.preheader1.5, !stats.blockFrequency.digits !8801, !stats.blockFrequency.scale !8802		; visa id: 1457

1393:                                             ; preds = %.preheader1.5
; BB164 :
  %.lcssa464 = phi i32 [ %1388, %.preheader1.5 ]
  %.lcssa463 = phi i32 [ %1389, %.preheader1.5 ]
  %1394 = shl i32 %.lcssa463, 23		; visa id: 1459
  %1395 = add i32 %1394, 1065353216		; visa id: 1460
  %1396 = shl i32 %.lcssa464, 14		; visa id: 1461
  %1397 = and i32 %1396, 8372224		; visa id: 1462
  %1398 = or i32 %1395, %1397
  %1399 = or i32 %1398, %137		; visa id: 1463
  br label %._crit_edge45.5, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1465

NodeBlock.5.._crit_edge45.5_crit_edge:            ; preds = %NodeBlock.5
; BB165 :
  br label %._crit_edge45.5, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1468

._crit_edge45.5:                                  ; preds = %NodeBlock.5.._crit_edge45.5_crit_edge, %1393
; BB166 :
  %1400 = phi i32 [ %1399, %1393 ], [ %.mux.mux, %NodeBlock.5.._crit_edge45.5_crit_edge ]
  %1401 = bitcast i32 %1400 to float
  %1402 = add i64 %125, %sink_399		; visa id: 1469
  %1403 = inttoptr i64 %1402 to ptr addrspace(4)		; visa id: 1470
  %1404 = addrspacecast ptr addrspace(4) %1403 to ptr addrspace(1)		; visa id: 1470
  %1405 = load i8, ptr addrspace(1) %1404, align 1, !noalias !8793		; visa id: 1471
  %b2s440 = sext i8 %1405 to i16		; visa id: 1473
  %1406 = shl nuw nsw i32 %1386, 3, !spirv.Decorations !8791		; visa id: 1474
  %1407 = zext i32 %1406 to i64		; visa id: 1475
  %1408 = add i64 %sink_395, %1407		; visa id: 1476
  %1409 = inttoptr i64 %1408 to ptr addrspace(1)		; visa id: 1477
  %1410 = load <2 x i32>, ptr addrspace(1) %1409, align 4		; visa id: 1477
  %b2s441 = and i16 %b2s440, 15		; visa id: 1478
  %1411 = trunc i16 %b2s441 to i8		; visa id: 1479
  %1412 = uitofp i8 %1411 to float		; visa id: 1480
  %1413 = fadd float %1412, 5.000000e-01		; visa id: 1481
  %1414 = fmul float %1413, %1401		; visa id: 1482
  %1415 = fmul float %1414, 2.500000e-01		; visa id: 1483
  %1416 = extractelement <2 x i32> %1410, i32 0		; visa id: 1484
  %1417 = extractelement <2 x i32> %1410, i32 1		; visa id: 1484
  %1418 = and i32 %1400, 2139095040		; visa id: 1484
  %1419 = bitcast float %1415 to i32
  %1420 = and i32 %1419, 2147483647		; visa id: 1485
  %1421 = icmp eq i32 %1418, 2139095040
  %1422 = icmp ugt i32 %1420, 2139095040		; visa id: 1486
  %1423 = or i1 %1421, %1422		; visa id: 1487
  %1424 = and i32 %1416, 255		; visa id: 1489
  br i1 %1423, label %1432, label %1425, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1490

1425:                                             ; preds = %._crit_edge45.5
; BB167 :
  %1426 = and i32 %1380, 256
  %1427 = sub nsw i32 0, %1424, !spirv.Decorations !8798
  %1428 = icmp eq i32 %1426, 0		; visa id: 1492
  %1429 = select i1 %1428, i32 %1424, i32 %1427		; visa id: 1494
  %1430 = sitofp i32 %1429 to float		; visa id: 1495
  %1431 = fmul float %1415, %1430		; visa id: 1496
  br label %1440, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1497

1432:                                             ; preds = %._crit_edge45.5
; BB168 :
  %1433 = uitofp i32 %1424 to float		; visa id: 1499
  %1434 = fmul float %1415, %1433		; visa id: 1500
  %1435 = and i32 %1380, 256
  %1436 = icmp eq i32 %1435, 0		; visa id: 1501
  %1437 = select i1 %1436, i32 1, i32 -1		; visa id: 1503
  %1438 = sitofp i32 %1437 to float		; visa id: 1504
  %1439 = fmul float %1434, %1438		; visa id: 1505
  br label %1440, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1506

1440:                                             ; preds = %1432, %1425
; BB169 :
  %.sroa.0125.5 = phi float [ %1439, %1432 ], [ %1431, %1425 ]
  %1441 = bitcast i32 %1416 to <4 x i8>
  %1442 = extractelement <4 x i8> %1441, i32 1
  %1443 = zext i8 %1442 to i32		; visa id: 1507
  br i1 %1423, label %1451, label %1444, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1508

1444:                                             ; preds = %1440
; BB170 :
  %1445 = and i32 %1380, 512
  %1446 = sub nsw i32 0, %1443, !spirv.Decorations !8798
  %1447 = icmp eq i32 %1445, 0		; visa id: 1510
  %1448 = select i1 %1447, i32 %1443, i32 %1446		; visa id: 1512
  %1449 = sitofp i32 %1448 to float		; visa id: 1513
  %1450 = fmul float %1415, %1449		; visa id: 1514
  br label %1459, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1515

1451:                                             ; preds = %1440
; BB171 :
  %1452 = uitofp i32 %1443 to float		; visa id: 1517
  %1453 = fmul float %1415, %1452		; visa id: 1518
  %1454 = and i32 %1380, 512
  %1455 = icmp eq i32 %1454, 0		; visa id: 1519
  %1456 = select i1 %1455, i32 1, i32 -1		; visa id: 1521
  %1457 = sitofp i32 %1456 to float		; visa id: 1522
  %1458 = fmul float %1453, %1457		; visa id: 1523
  br label %1459, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1524

1459:                                             ; preds = %1451, %1444
; BB172 :
  %.sroa.40.5 = phi float [ %1458, %1451 ], [ %1450, %1444 ]
  %1460 = extractelement <4 x i8> %1441, i32 2
  %1461 = zext i8 %1460 to i32		; visa id: 1525
  br i1 %1423, label %1469, label %1462, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1526

1462:                                             ; preds = %1459
; BB173 :
  %1463 = and i32 %1380, 1024
  %1464 = sub nsw i32 0, %1461, !spirv.Decorations !8798
  %1465 = icmp eq i32 %1463, 0		; visa id: 1528
  %1466 = select i1 %1465, i32 %1461, i32 %1464		; visa id: 1530
  %1467 = sitofp i32 %1466 to float		; visa id: 1531
  %1468 = fmul float %1415, %1467		; visa id: 1532
  br label %1477, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1533

1469:                                             ; preds = %1459
; BB174 :
  %1470 = uitofp i32 %1461 to float		; visa id: 1535
  %1471 = fmul float %1415, %1470		; visa id: 1536
  %1472 = and i32 %1380, 1024
  %1473 = icmp eq i32 %1472, 0		; visa id: 1537
  %1474 = select i1 %1473, i32 1, i32 -1		; visa id: 1539
  %1475 = sitofp i32 %1474 to float		; visa id: 1540
  %1476 = fmul float %1471, %1475		; visa id: 1541
  br label %1477, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1542

1477:                                             ; preds = %1469, %1462
; BB175 :
  %.sroa.64140.5 = phi float [ %1476, %1469 ], [ %1468, %1462 ]
  %1478 = lshr i32 %1416, 24		; visa id: 1543
  br i1 %1423, label %1486, label %1479, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1544

1479:                                             ; preds = %1477
; BB176 :
  %1480 = and i32 %1380, 2048
  %1481 = sub nsw i32 0, %1478, !spirv.Decorations !8798
  %1482 = icmp eq i32 %1480, 0		; visa id: 1546
  %1483 = select i1 %1482, i32 %1478, i32 %1481		; visa id: 1548
  %1484 = sitofp i32 %1483 to float		; visa id: 1549
  %1485 = fmul float %1415, %1484		; visa id: 1550
  br label %1494, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1551

1486:                                             ; preds = %1477
; BB177 :
  %1487 = uitofp i32 %1478 to float		; visa id: 1553
  %1488 = fmul float %1415, %1487		; visa id: 1554
  %1489 = and i32 %1380, 2048
  %1490 = icmp eq i32 %1489, 0		; visa id: 1555
  %1491 = select i1 %1490, i32 1, i32 -1		; visa id: 1557
  %1492 = sitofp i32 %1491 to float		; visa id: 1558
  %1493 = fmul float %1488, %1492		; visa id: 1559
  br label %1494, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1560

1494:                                             ; preds = %1486, %1479
; BB178 :
  %.sroa.88.5 = phi float [ %1493, %1486 ], [ %1485, %1479 ]
  %1495 = and i32 %1417, 255		; visa id: 1561
  br i1 %1423, label %1503, label %1496, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1562

1496:                                             ; preds = %1494
; BB179 :
  %1497 = and i32 %1380, 4096
  %1498 = sub nsw i32 0, %1495, !spirv.Decorations !8798
  %1499 = icmp eq i32 %1497, 0		; visa id: 1564
  %1500 = select i1 %1499, i32 %1495, i32 %1498		; visa id: 1566
  %1501 = sitofp i32 %1500 to float		; visa id: 1567
  %1502 = fmul float %1415, %1501		; visa id: 1568
  br label %1511, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1569

1503:                                             ; preds = %1494
; BB180 :
  %1504 = uitofp i32 %1495 to float		; visa id: 1571
  %1505 = fmul float %1415, %1504		; visa id: 1572
  %1506 = and i32 %1380, 4096
  %1507 = icmp eq i32 %1506, 0		; visa id: 1573
  %1508 = select i1 %1507, i32 1, i32 -1		; visa id: 1575
  %1509 = sitofp i32 %1508 to float		; visa id: 1576
  %1510 = fmul float %1505, %1509		; visa id: 1577
  br label %1511, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1578

1511:                                             ; preds = %1503, %1496
; BB181 :
  %.sroa.112155.5 = phi float [ %1510, %1503 ], [ %1502, %1496 ]
  %1512 = bitcast i32 %1417 to <4 x i8>
  %1513 = extractelement <4 x i8> %1512, i32 1
  %1514 = zext i8 %1513 to i32		; visa id: 1579
  br i1 %1423, label %1522, label %1515, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1580

1515:                                             ; preds = %1511
; BB182 :
  %1516 = and i32 %1380, 8192
  %1517 = sub nsw i32 0, %1514, !spirv.Decorations !8798
  %1518 = icmp eq i32 %1516, 0		; visa id: 1582
  %1519 = select i1 %1518, i32 %1514, i32 %1517		; visa id: 1584
  %1520 = sitofp i32 %1519 to float		; visa id: 1585
  %1521 = fmul float %1415, %1520		; visa id: 1586
  br label %1530, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1587

1522:                                             ; preds = %1511
; BB183 :
  %1523 = uitofp i32 %1514 to float		; visa id: 1589
  %1524 = fmul float %1415, %1523		; visa id: 1590
  %1525 = and i32 %1380, 8192
  %1526 = icmp eq i32 %1525, 0		; visa id: 1591
  %1527 = select i1 %1526, i32 1, i32 -1		; visa id: 1593
  %1528 = sitofp i32 %1527 to float		; visa id: 1594
  %1529 = fmul float %1524, %1528		; visa id: 1595
  br label %1530, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1596

1530:                                             ; preds = %1522, %1515
; BB184 :
  %.sroa.136.5 = phi float [ %1529, %1522 ], [ %1521, %1515 ]
  %1531 = extractelement <4 x i8> %1512, i32 2
  %1532 = zext i8 %1531 to i32		; visa id: 1597
  br i1 %1423, label %1540, label %1533, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1598

1533:                                             ; preds = %1530
; BB185 :
  %1534 = and i32 %1380, 16384
  %1535 = sub nsw i32 0, %1532, !spirv.Decorations !8798
  %1536 = icmp eq i32 %1534, 0		; visa id: 1600
  %1537 = select i1 %1536, i32 %1532, i32 %1535		; visa id: 1602
  %1538 = sitofp i32 %1537 to float		; visa id: 1603
  %1539 = fmul float %1415, %1538		; visa id: 1604
  br label %1548, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1605

1540:                                             ; preds = %1530
; BB186 :
  %1541 = uitofp i32 %1532 to float		; visa id: 1607
  %1542 = fmul float %1415, %1541		; visa id: 1608
  %1543 = and i32 %1380, 16384
  %1544 = icmp eq i32 %1543, 0		; visa id: 1609
  %1545 = select i1 %1544, i32 1, i32 -1		; visa id: 1611
  %1546 = sitofp i32 %1545 to float		; visa id: 1612
  %1547 = fmul float %1542, %1546		; visa id: 1613
  br label %1548, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1614

1548:                                             ; preds = %1540, %1533
; BB187 :
  %.sroa.160.5 = phi float [ %1547, %1540 ], [ %1539, %1533 ]
  %1549 = lshr i32 %1417, 24		; visa id: 1615
  br i1 %1423, label %1556, label %1550, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1616

1550:                                             ; preds = %1548
; BB188 :
  %1551 = sub nsw i32 0, %1549, !spirv.Decorations !8798
  %1552 = icmp slt i16 %1375, 0		; visa id: 1618
  %1553 = select i1 %1552, i32 %1551, i32 %1549		; visa id: 1619
  %1554 = sitofp i32 %1553 to float		; visa id: 1620
  %1555 = fmul float %1415, %1554		; visa id: 1621
  br label %NodeBlock.6, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1622

1556:                                             ; preds = %1548
; BB189 :
  %1557 = uitofp i32 %1549 to float		; visa id: 1624
  %1558 = fmul float %1415, %1557		; visa id: 1625
  %1559 = fsub float 0.000000e+00, %1558
  %1560 = icmp slt i16 %1375, 0		; visa id: 1626
  %1561 = select i1 %1560, float %1559, float %1558		; visa id: 1627
  br label %NodeBlock.6, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1628

NodeBlock.6:                                      ; preds = %1556, %1550
; BB190 :
  %.sroa.184.5 = phi float [ %1561, %1556 ], [ %1555, %1550 ]
  %1562 = shl nuw i32 %1371, 1		; visa id: 1629
  %1563 = zext i32 %1562 to i64		; visa id: 1630
  %1564 = add i64 %1563, %const_reg_qword2		; visa id: 1631
  %IntToPtr2365 = inttoptr i64 %1564 to ptr addrspace(1)		; visa id: 1632
  %vCastload366 = load i32, ptr addrspace(1) %IntToPtr2365, align 2		; visa id: 1632
  %1565 = add i64 %1564, 4
  %IntToPtr2367 = inttoptr i64 %1565 to ptr addrspace(1)
  %vCastload368 = load i32, ptr addrspace(1) %IntToPtr2367, align 2		; visa id: 1633
  %1566 = add i64 %1564, 8
  %IntToPtr2369 = inttoptr i64 %1566 to ptr addrspace(1)
  %vCastload370 = load i32, ptr addrspace(1) %IntToPtr2369, align 2		; visa id: 1634
  %1567 = add i64 %1564, 12
  %IntToPtr2371 = inttoptr i64 %1567 to ptr addrspace(1)
  %vCastload372 = load i32, ptr addrspace(1) %IntToPtr2371, align 2		; visa id: 1635
  %1568 = bitcast i32 %vCastload366 to <2 x i16>		; visa id: 1636
  %1569 = bitcast i32 %vCastload368 to <2 x i16>		; visa id: 1638
  %1570 = extractelement <2 x i16> %1568, i32 0		; visa id: 1640
  %1571 = extractelement <2 x i16> %1568, i32 1		; visa id: 1640
  %1572 = extractelement <2 x i16> %1569, i32 0		; visa id: 1640
  %1573 = extractelement <2 x i16> %1569, i32 1		; visa id: 1640
  %1574 = bitcast i32 %vCastload370 to <2 x i16>		; visa id: 1640
  %1575 = bitcast i32 %vCastload372 to <2 x i16>		; visa id: 1642
  %1576 = extractelement <2 x i16> %1574, i32 0		; visa id: 1644
  %1577 = extractelement <2 x i16> %1574, i32 1		; visa id: 1644
  %1578 = extractelement <2 x i16> %1575, i32 0		; visa id: 1644
  %1579 = extractelement <2 x i16> %1575, i32 1		; visa id: 1644
  %1580 = zext i16 %1570 to i32		; visa id: 1644
  %1581 = shl nuw i32 %1580, 16, !spirv.Decorations !8788		; visa id: 1645
  %1582 = bitcast i32 %1581 to float
  %1583 = fmul float %.sroa.0125.5, %1582		; visa id: 1646
  %1584 = fadd float %.sroa.28.0, %1583		; visa id: 1647
  %1585 = zext i16 %1571 to i32		; visa id: 1648
  %1586 = shl nuw i32 %1585, 16, !spirv.Decorations !8788		; visa id: 1649
  %1587 = bitcast i32 %1586 to float
  %1588 = fmul float %.sroa.40.5, %1587		; visa id: 1650
  %1589 = fadd float %1584, %1588		; visa id: 1651
  %1590 = zext i16 %1572 to i32		; visa id: 1652
  %1591 = shl nuw i32 %1590, 16, !spirv.Decorations !8788		; visa id: 1653
  %1592 = bitcast i32 %1591 to float
  %1593 = fmul float %.sroa.64140.5, %1592		; visa id: 1654
  %1594 = fadd float %1589, %1593		; visa id: 1655
  %1595 = zext i16 %1573 to i32		; visa id: 1656
  %1596 = shl nuw i32 %1595, 16, !spirv.Decorations !8788		; visa id: 1657
  %1597 = bitcast i32 %1596 to float
  %1598 = fmul float %.sroa.88.5, %1597		; visa id: 1658
  %1599 = fadd float %1594, %1598		; visa id: 1659
  %1600 = zext i16 %1576 to i32		; visa id: 1660
  %1601 = shl nuw i32 %1600, 16, !spirv.Decorations !8788		; visa id: 1661
  %1602 = bitcast i32 %1601 to float
  %1603 = fmul float %.sroa.112155.5, %1602		; visa id: 1662
  %1604 = fadd float %1599, %1603		; visa id: 1663
  %1605 = zext i16 %1577 to i32		; visa id: 1664
  %1606 = shl nuw i32 %1605, 16, !spirv.Decorations !8788		; visa id: 1665
  %1607 = bitcast i32 %1606 to float
  %1608 = fmul float %.sroa.136.5, %1607		; visa id: 1666
  %1609 = fadd float %1604, %1608		; visa id: 1667
  %1610 = zext i16 %1578 to i32		; visa id: 1668
  %1611 = shl nuw i32 %1610, 16, !spirv.Decorations !8788		; visa id: 1669
  %1612 = bitcast i32 %1611 to float
  %1613 = fmul float %.sroa.160.5, %1612		; visa id: 1670
  %1614 = fadd float %1609, %1613		; visa id: 1671
  %1615 = zext i16 %1579 to i32		; visa id: 1672
  %1616 = shl nuw i32 %1615, 16, !spirv.Decorations !8788		; visa id: 1673
  %1617 = bitcast i32 %1616 to float
  %1618 = fmul float %.sroa.184.5, %1617		; visa id: 1674
  %1619 = fadd float %1614, %1618		; visa id: 1675
  %1620 = or i32 %110, %114		; visa id: 1676
  %sink_404 = lshr exact i32 %110, 2		; visa id: 1677
  %sink_389 = zext i32 %sink_404 to i64		; visa id: 1678
  %1621 = add i64 %117, %sink_389		; visa id: 1679
  %1622 = inttoptr i64 %1621 to ptr addrspace(4)		; visa id: 1680
  %1623 = addrspacecast ptr addrspace(4) %1622 to ptr addrspace(1)		; visa id: 1680
  %1624 = load i16, ptr addrspace(1) %1623, align 2, !noalias !8793		; visa id: 1681
  %sink_412 = lshr i32 %110, 5		; visa id: 1683
  %sink_398 = zext i32 %sink_412 to i64		; visa id: 1684
  %1625 = add i64 %120, %sink_398		; visa id: 1685
  %1626 = inttoptr i64 %1625 to ptr addrspace(4)		; visa id: 1686
  %1627 = addrspacecast ptr addrspace(4) %1626 to ptr addrspace(1)		; visa id: 1686
  %1628 = load i8, ptr addrspace(1) %1627, align 1, !noalias !8793		; visa id: 1687
  %b2s442 = sext i8 %1628 to i16
  %1629 = zext i16 %1624 to i32		; visa id: 1689
  %1630 = and i32 %1629, 255
  %b2s443 = zext i8 %1628 to i16		; visa id: 1690
  %b2s444 = lshr i16 %b2s443, 4		; visa id: 1691
  %1631 = trunc i16 %b2s444 to i8		; visa id: 1692
  %1632 = zext i8 %1631 to i32		; visa id: 1693
  %1633 = shl nuw nsw i32 %1632, 8, !spirv.Decorations !8791		; visa id: 1694
  %1634 = and i32 %1633, 768		; visa id: 1695
  %1635 = or i32 %1630, %1634		; visa id: 1696
  br i1 %160, label %NodeBlock.6.._crit_edge45.6_crit_edge, label %.preheader1.6.preheader, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1697

.preheader1.6.preheader:                          ; preds = %NodeBlock.6
; BB191 :
  br label %.preheader1.6, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1701

.preheader1.6:                                    ; preds = %.preheader1.6..preheader1.6_crit_edge, %.preheader1.6.preheader
; BB192 :
  %1636 = phi i32 [ %1638, %.preheader1.6..preheader1.6_crit_edge ], [ -14, %.preheader1.6.preheader ]
  %1637 = phi i32 [ %1641, %.preheader1.6..preheader1.6_crit_edge ], [ %141, %.preheader1.6.preheader ]
  %1638 = add nsw i32 %1636, -1, !spirv.Decorations !8798		; visa id: 1702
  %1639 = and i32 %1637, 512
  %1640 = icmp eq i32 %1639, 0		; visa id: 1703
  br i1 %1640, label %.preheader1.6..preheader1.6_crit_edge, label %1642, !stats.blockFrequency.digits !8799, !stats.blockFrequency.scale !8800		; visa id: 1707

.preheader1.6..preheader1.6_crit_edge:            ; preds = %.preheader1.6
; BB193 :
  %1641 = shl i32 %1637, 1		; visa id: 1709
  br label %.preheader1.6, !stats.blockFrequency.digits !8801, !stats.blockFrequency.scale !8802		; visa id: 1711

1642:                                             ; preds = %.preheader1.6
; BB194 :
  %.lcssa466 = phi i32 [ %1637, %.preheader1.6 ]
  %.lcssa465 = phi i32 [ %1638, %.preheader1.6 ]
  %1643 = shl i32 %.lcssa465, 23		; visa id: 1713
  %1644 = add i32 %1643, 1065353216		; visa id: 1714
  %1645 = shl i32 %.lcssa466, 14		; visa id: 1715
  %1646 = and i32 %1645, 8372224		; visa id: 1716
  %1647 = or i32 %1644, %1646
  %1648 = or i32 %1647, %137		; visa id: 1717
  br label %._crit_edge45.6, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1719

NodeBlock.6.._crit_edge45.6_crit_edge:            ; preds = %NodeBlock.6
; BB195 :
  br label %._crit_edge45.6, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1722

._crit_edge45.6:                                  ; preds = %NodeBlock.6.._crit_edge45.6_crit_edge, %1642
; BB196 :
  %1649 = phi i32 [ %1648, %1642 ], [ %.mux.mux, %NodeBlock.6.._crit_edge45.6_crit_edge ]
  %1650 = bitcast i32 %1649 to float
  %1651 = add i64 %125, %sink_398		; visa id: 1723
  %1652 = inttoptr i64 %1651 to ptr addrspace(4)		; visa id: 1724
  %1653 = addrspacecast ptr addrspace(4) %1652 to ptr addrspace(1)		; visa id: 1724
  %1654 = load i8, ptr addrspace(1) %1653, align 1, !noalias !8793		; visa id: 1725
  %b2s445 = sext i8 %1654 to i16
  %1655 = shl nuw nsw i32 %1635, 3, !spirv.Decorations !8791		; visa id: 1727
  %1656 = zext i32 %1655 to i64		; visa id: 1728
  %1657 = add i64 %sink_395, %1656		; visa id: 1729
  %1658 = inttoptr i64 %1657 to ptr addrspace(1)		; visa id: 1730
  %1659 = load <2 x i32>, ptr addrspace(1) %1658, align 4		; visa id: 1730
  %b2s446 = zext i8 %1654 to i16		; visa id: 1731
  %b2s447 = lshr i16 %b2s446, 4		; visa id: 1732
  %1660 = trunc i16 %b2s447 to i8		; visa id: 1733
  %1661 = uitofp i8 %1660 to float		; visa id: 1734
  %1662 = fadd float %1661, 5.000000e-01		; visa id: 1735
  %1663 = fmul float %1662, %1650		; visa id: 1736
  %1664 = fmul float %1663, 2.500000e-01		; visa id: 1737
  %1665 = extractelement <2 x i32> %1659, i32 0		; visa id: 1738
  %1666 = extractelement <2 x i32> %1659, i32 1		; visa id: 1738
  %1667 = and i32 %1649, 2139095040		; visa id: 1738
  %1668 = bitcast float %1664 to i32
  %1669 = and i32 %1668, 2147483647		; visa id: 1739
  %1670 = icmp eq i32 %1667, 2139095040
  %1671 = icmp ugt i32 %1669, 2139095040		; visa id: 1740
  %1672 = or i1 %1670, %1671		; visa id: 1741
  %1673 = and i32 %1665, 255		; visa id: 1743
  br i1 %1672, label %1681, label %1674, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1744

1674:                                             ; preds = %._crit_edge45.6
; BB197 :
  %1675 = and i32 %1629, 256
  %1676 = sub nsw i32 0, %1673, !spirv.Decorations !8798
  %1677 = icmp eq i32 %1675, 0		; visa id: 1746
  %1678 = select i1 %1677, i32 %1673, i32 %1676		; visa id: 1748
  %1679 = sitofp i32 %1678 to float		; visa id: 1749
  %1680 = fmul float %1664, %1679		; visa id: 1750
  br label %1689, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1751

1681:                                             ; preds = %._crit_edge45.6
; BB198 :
  %1682 = uitofp i32 %1673 to float		; visa id: 1753
  %1683 = fmul float %1664, %1682		; visa id: 1754
  %1684 = and i32 %1629, 256
  %1685 = icmp eq i32 %1684, 0		; visa id: 1755
  %1686 = select i1 %1685, i32 1, i32 -1		; visa id: 1757
  %1687 = sitofp i32 %1686 to float		; visa id: 1758
  %1688 = fmul float %1683, %1687		; visa id: 1759
  br label %1689, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1760

1689:                                             ; preds = %1681, %1674
; BB199 :
  %.sroa.0125.6 = phi float [ %1688, %1681 ], [ %1680, %1674 ]
  %1690 = bitcast i32 %1665 to <4 x i8>
  %1691 = extractelement <4 x i8> %1690, i32 1
  %1692 = zext i8 %1691 to i32		; visa id: 1761
  br i1 %1672, label %1700, label %1693, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1762

1693:                                             ; preds = %1689
; BB200 :
  %1694 = and i32 %1629, 512
  %1695 = sub nsw i32 0, %1692, !spirv.Decorations !8798
  %1696 = icmp eq i32 %1694, 0		; visa id: 1764
  %1697 = select i1 %1696, i32 %1692, i32 %1695		; visa id: 1766
  %1698 = sitofp i32 %1697 to float		; visa id: 1767
  %1699 = fmul float %1664, %1698		; visa id: 1768
  br label %1708, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1769

1700:                                             ; preds = %1689
; BB201 :
  %1701 = uitofp i32 %1692 to float		; visa id: 1771
  %1702 = fmul float %1664, %1701		; visa id: 1772
  %1703 = and i32 %1629, 512
  %1704 = icmp eq i32 %1703, 0		; visa id: 1773
  %1705 = select i1 %1704, i32 1, i32 -1		; visa id: 1775
  %1706 = sitofp i32 %1705 to float		; visa id: 1776
  %1707 = fmul float %1702, %1706		; visa id: 1777
  br label %1708, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1778

1708:                                             ; preds = %1700, %1693
; BB202 :
  %.sroa.40.6 = phi float [ %1707, %1700 ], [ %1699, %1693 ]
  %1709 = extractelement <4 x i8> %1690, i32 2
  %1710 = zext i8 %1709 to i32		; visa id: 1779
  br i1 %1672, label %1718, label %1711, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1780

1711:                                             ; preds = %1708
; BB203 :
  %1712 = and i32 %1629, 1024
  %1713 = sub nsw i32 0, %1710, !spirv.Decorations !8798
  %1714 = icmp eq i32 %1712, 0		; visa id: 1782
  %1715 = select i1 %1714, i32 %1710, i32 %1713		; visa id: 1784
  %1716 = sitofp i32 %1715 to float		; visa id: 1785
  %1717 = fmul float %1664, %1716		; visa id: 1786
  br label %1726, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1787

1718:                                             ; preds = %1708
; BB204 :
  %1719 = uitofp i32 %1710 to float		; visa id: 1789
  %1720 = fmul float %1664, %1719		; visa id: 1790
  %1721 = and i32 %1629, 1024
  %1722 = icmp eq i32 %1721, 0		; visa id: 1791
  %1723 = select i1 %1722, i32 1, i32 -1		; visa id: 1793
  %1724 = sitofp i32 %1723 to float		; visa id: 1794
  %1725 = fmul float %1720, %1724		; visa id: 1795
  br label %1726, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1796

1726:                                             ; preds = %1718, %1711
; BB205 :
  %.sroa.64140.6 = phi float [ %1725, %1718 ], [ %1717, %1711 ]
  %1727 = lshr i32 %1665, 24		; visa id: 1797
  br i1 %1672, label %1735, label %1728, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1798

1728:                                             ; preds = %1726
; BB206 :
  %1729 = and i32 %1629, 2048
  %1730 = sub nsw i32 0, %1727, !spirv.Decorations !8798
  %1731 = icmp eq i32 %1729, 0		; visa id: 1800
  %1732 = select i1 %1731, i32 %1727, i32 %1730		; visa id: 1802
  %1733 = sitofp i32 %1732 to float		; visa id: 1803
  %1734 = fmul float %1664, %1733		; visa id: 1804
  br label %1743, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1805

1735:                                             ; preds = %1726
; BB207 :
  %1736 = uitofp i32 %1727 to float		; visa id: 1807
  %1737 = fmul float %1664, %1736		; visa id: 1808
  %1738 = and i32 %1629, 2048
  %1739 = icmp eq i32 %1738, 0		; visa id: 1809
  %1740 = select i1 %1739, i32 1, i32 -1		; visa id: 1811
  %1741 = sitofp i32 %1740 to float		; visa id: 1812
  %1742 = fmul float %1737, %1741		; visa id: 1813
  br label %1743, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1814

1743:                                             ; preds = %1735, %1728
; BB208 :
  %.sroa.88.6 = phi float [ %1742, %1735 ], [ %1734, %1728 ]
  %1744 = and i32 %1666, 255		; visa id: 1815
  br i1 %1672, label %1752, label %1745, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1816

1745:                                             ; preds = %1743
; BB209 :
  %1746 = and i32 %1629, 4096
  %1747 = sub nsw i32 0, %1744, !spirv.Decorations !8798
  %1748 = icmp eq i32 %1746, 0		; visa id: 1818
  %1749 = select i1 %1748, i32 %1744, i32 %1747		; visa id: 1820
  %1750 = sitofp i32 %1749 to float		; visa id: 1821
  %1751 = fmul float %1664, %1750		; visa id: 1822
  br label %1760, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1823

1752:                                             ; preds = %1743
; BB210 :
  %1753 = uitofp i32 %1744 to float		; visa id: 1825
  %1754 = fmul float %1664, %1753		; visa id: 1826
  %1755 = and i32 %1629, 4096
  %1756 = icmp eq i32 %1755, 0		; visa id: 1827
  %1757 = select i1 %1756, i32 1, i32 -1		; visa id: 1829
  %1758 = sitofp i32 %1757 to float		; visa id: 1830
  %1759 = fmul float %1754, %1758		; visa id: 1831
  br label %1760, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1832

1760:                                             ; preds = %1752, %1745
; BB211 :
  %.sroa.112155.6 = phi float [ %1759, %1752 ], [ %1751, %1745 ]
  %1761 = bitcast i32 %1666 to <4 x i8>
  %1762 = extractelement <4 x i8> %1761, i32 1
  %1763 = zext i8 %1762 to i32		; visa id: 1833
  br i1 %1672, label %1771, label %1764, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1834

1764:                                             ; preds = %1760
; BB212 :
  %1765 = and i32 %1629, 8192
  %1766 = sub nsw i32 0, %1763, !spirv.Decorations !8798
  %1767 = icmp eq i32 %1765, 0		; visa id: 1836
  %1768 = select i1 %1767, i32 %1763, i32 %1766		; visa id: 1838
  %1769 = sitofp i32 %1768 to float		; visa id: 1839
  %1770 = fmul float %1664, %1769		; visa id: 1840
  br label %1779, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1841

1771:                                             ; preds = %1760
; BB213 :
  %1772 = uitofp i32 %1763 to float		; visa id: 1843
  %1773 = fmul float %1664, %1772		; visa id: 1844
  %1774 = and i32 %1629, 8192
  %1775 = icmp eq i32 %1774, 0		; visa id: 1845
  %1776 = select i1 %1775, i32 1, i32 -1		; visa id: 1847
  %1777 = sitofp i32 %1776 to float		; visa id: 1848
  %1778 = fmul float %1773, %1777		; visa id: 1849
  br label %1779, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1850

1779:                                             ; preds = %1771, %1764
; BB214 :
  %.sroa.136.6 = phi float [ %1778, %1771 ], [ %1770, %1764 ]
  %1780 = extractelement <4 x i8> %1761, i32 2
  %1781 = zext i8 %1780 to i32		; visa id: 1851
  br i1 %1672, label %1789, label %1782, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1852

1782:                                             ; preds = %1779
; BB215 :
  %1783 = and i32 %1629, 16384
  %1784 = sub nsw i32 0, %1781, !spirv.Decorations !8798
  %1785 = icmp eq i32 %1783, 0		; visa id: 1854
  %1786 = select i1 %1785, i32 %1781, i32 %1784		; visa id: 1856
  %1787 = sitofp i32 %1786 to float		; visa id: 1857
  %1788 = fmul float %1664, %1787		; visa id: 1858
  br label %1797, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1859

1789:                                             ; preds = %1779
; BB216 :
  %1790 = uitofp i32 %1781 to float		; visa id: 1861
  %1791 = fmul float %1664, %1790		; visa id: 1862
  %1792 = and i32 %1629, 16384
  %1793 = icmp eq i32 %1792, 0		; visa id: 1863
  %1794 = select i1 %1793, i32 1, i32 -1		; visa id: 1865
  %1795 = sitofp i32 %1794 to float		; visa id: 1866
  %1796 = fmul float %1791, %1795		; visa id: 1867
  br label %1797, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1868

1797:                                             ; preds = %1789, %1782
; BB217 :
  %.sroa.160.6 = phi float [ %1796, %1789 ], [ %1788, %1782 ]
  %1798 = lshr i32 %1666, 24		; visa id: 1869
  br i1 %1672, label %1805, label %1799, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1870

1799:                                             ; preds = %1797
; BB218 :
  %1800 = sub nsw i32 0, %1798, !spirv.Decorations !8798
  %1801 = icmp slt i16 %1624, 0		; visa id: 1872
  %1802 = select i1 %1801, i32 %1800, i32 %1798		; visa id: 1873
  %1803 = sitofp i32 %1802 to float		; visa id: 1874
  %1804 = fmul float %1664, %1803		; visa id: 1875
  br label %NodeBlock.7, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1876

1805:                                             ; preds = %1797
; BB219 :
  %1806 = uitofp i32 %1798 to float		; visa id: 1878
  %1807 = fmul float %1664, %1806		; visa id: 1879
  %1808 = fsub float 0.000000e+00, %1807
  %1809 = icmp slt i16 %1624, 0		; visa id: 1880
  %1810 = select i1 %1809, float %1808, float %1807		; visa id: 1881
  br label %NodeBlock.7, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1882

NodeBlock.7:                                      ; preds = %1805, %1799
; BB220 :
  %.sroa.184.6 = phi float [ %1810, %1805 ], [ %1804, %1799 ]
  %1811 = shl nuw i32 %1620, 1		; visa id: 1883
  %1812 = zext i32 %1811 to i64		; visa id: 1884
  %1813 = add i64 %1812, %const_reg_qword2		; visa id: 1885
  %IntToPtr2373 = inttoptr i64 %1813 to ptr addrspace(1)		; visa id: 1886
  %vCastload374 = load i32, ptr addrspace(1) %IntToPtr2373, align 2		; visa id: 1886
  %1814 = add i64 %1813, 4
  %IntToPtr2375 = inttoptr i64 %1814 to ptr addrspace(1)
  %vCastload376 = load i32, ptr addrspace(1) %IntToPtr2375, align 2		; visa id: 1887
  %1815 = add i64 %1813, 8
  %IntToPtr2377 = inttoptr i64 %1815 to ptr addrspace(1)
  %vCastload378 = load i32, ptr addrspace(1) %IntToPtr2377, align 2		; visa id: 1888
  %1816 = add i64 %1813, 12
  %IntToPtr2379 = inttoptr i64 %1816 to ptr addrspace(1)
  %vCastload380 = load i32, ptr addrspace(1) %IntToPtr2379, align 2		; visa id: 1889
  %1817 = bitcast i32 %vCastload374 to <2 x i16>		; visa id: 1890
  %1818 = bitcast i32 %vCastload376 to <2 x i16>		; visa id: 1892
  %1819 = extractelement <2 x i16> %1817, i32 0		; visa id: 1894
  %1820 = extractelement <2 x i16> %1817, i32 1		; visa id: 1894
  %1821 = extractelement <2 x i16> %1818, i32 0		; visa id: 1894
  %1822 = extractelement <2 x i16> %1818, i32 1		; visa id: 1894
  %1823 = bitcast i32 %vCastload378 to <2 x i16>		; visa id: 1894
  %1824 = bitcast i32 %vCastload380 to <2 x i16>		; visa id: 1896
  %1825 = extractelement <2 x i16> %1823, i32 0		; visa id: 1898
  %1826 = extractelement <2 x i16> %1823, i32 1		; visa id: 1898
  %1827 = extractelement <2 x i16> %1824, i32 0		; visa id: 1898
  %1828 = extractelement <2 x i16> %1824, i32 1		; visa id: 1898
  %1829 = zext i16 %1819 to i32		; visa id: 1898
  %1830 = shl nuw i32 %1829, 16, !spirv.Decorations !8788		; visa id: 1899
  %1831 = bitcast i32 %1830 to float
  %1832 = fmul float %.sroa.0125.6, %1831		; visa id: 1900
  %1833 = fadd float %.sroa.31.0, %1832		; visa id: 1901
  %1834 = zext i16 %1820 to i32		; visa id: 1902
  %1835 = shl nuw i32 %1834, 16, !spirv.Decorations !8788		; visa id: 1903
  %1836 = bitcast i32 %1835 to float
  %1837 = fmul float %.sroa.40.6, %1836		; visa id: 1904
  %1838 = fadd float %1833, %1837		; visa id: 1905
  %1839 = zext i16 %1821 to i32		; visa id: 1906
  %1840 = shl nuw i32 %1839, 16, !spirv.Decorations !8788		; visa id: 1907
  %1841 = bitcast i32 %1840 to float
  %1842 = fmul float %.sroa.64140.6, %1841		; visa id: 1908
  %1843 = fadd float %1838, %1842		; visa id: 1909
  %1844 = zext i16 %1822 to i32		; visa id: 1910
  %1845 = shl nuw i32 %1844, 16, !spirv.Decorations !8788		; visa id: 1911
  %1846 = bitcast i32 %1845 to float
  %1847 = fmul float %.sroa.88.6, %1846		; visa id: 1912
  %1848 = fadd float %1843, %1847		; visa id: 1913
  %1849 = zext i16 %1825 to i32		; visa id: 1914
  %1850 = shl nuw i32 %1849, 16, !spirv.Decorations !8788		; visa id: 1915
  %1851 = bitcast i32 %1850 to float
  %1852 = fmul float %.sroa.112155.6, %1851		; visa id: 1916
  %1853 = fadd float %1848, %1852		; visa id: 1917
  %1854 = zext i16 %1826 to i32		; visa id: 1918
  %1855 = shl nuw i32 %1854, 16, !spirv.Decorations !8788		; visa id: 1919
  %1856 = bitcast i32 %1855 to float
  %1857 = fmul float %.sroa.136.6, %1856		; visa id: 1920
  %1858 = fadd float %1853, %1857		; visa id: 1921
  %1859 = zext i16 %1827 to i32		; visa id: 1922
  %1860 = shl nuw i32 %1859, 16, !spirv.Decorations !8788		; visa id: 1923
  %1861 = bitcast i32 %1860 to float
  %1862 = fmul float %.sroa.160.6, %1861		; visa id: 1924
  %1863 = fadd float %1858, %1862		; visa id: 1925
  %1864 = zext i16 %1828 to i32		; visa id: 1926
  %1865 = shl nuw i32 %1864, 16, !spirv.Decorations !8788		; visa id: 1927
  %1866 = bitcast i32 %1865 to float
  %1867 = fmul float %.sroa.184.6, %1866		; visa id: 1928
  %1868 = fadd float %1863, %1867		; visa id: 1929
  %1869 = or i32 %111, %114		; visa id: 1930
  %sink_403 = lshr exact i32 %111, 2		; visa id: 1931
  %sink_ = zext i32 %sink_403 to i64		; visa id: 1932
  %1870 = add i64 %117, %sink_		; visa id: 1933
  %1871 = inttoptr i64 %1870 to ptr addrspace(4)		; visa id: 1934
  %1872 = addrspacecast ptr addrspace(4) %1871 to ptr addrspace(1)		; visa id: 1934
  %1873 = load i16, ptr addrspace(1) %1872, align 2, !noalias !8793		; visa id: 1935
  %sink_411 = lshr i32 %111, 5		; visa id: 1937
  %sink_397 = zext i32 %sink_411 to i64		; visa id: 1938
  %1874 = add i64 %120, %sink_397		; visa id: 1939
  %1875 = inttoptr i64 %1874 to ptr addrspace(4)		; visa id: 1940
  %1876 = addrspacecast ptr addrspace(4) %1875 to ptr addrspace(1)		; visa id: 1940
  %1877 = load i8, ptr addrspace(1) %1876, align 1, !noalias !8793		; visa id: 1941
  %b2s448 = sext i8 %1877 to i16
  %b2s449 = zext i8 %1877 to i16		; visa id: 1943
  %b2s450 = lshr i16 %b2s449, 6		; visa id: 1944
  br i1 %160, label %NodeBlock.7.._crit_edge45.7_crit_edge, label %.preheader1.7.preheader, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1945

.preheader1.7.preheader:                          ; preds = %NodeBlock.7
; BB221 :
  br label %.preheader1.7, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1949

.preheader1.7:                                    ; preds = %.preheader1.7..preheader1.7_crit_edge, %.preheader1.7.preheader
; BB222 :
  %1878 = phi i32 [ %1880, %.preheader1.7..preheader1.7_crit_edge ], [ -14, %.preheader1.7.preheader ]
  %1879 = phi i32 [ %1883, %.preheader1.7..preheader1.7_crit_edge ], [ %141, %.preheader1.7.preheader ]
  %1880 = add nsw i32 %1878, -1, !spirv.Decorations !8798		; visa id: 1950
  %1881 = and i32 %1879, 512
  %1882 = icmp eq i32 %1881, 0		; visa id: 1951
  br i1 %1882, label %.preheader1.7..preheader1.7_crit_edge, label %1884, !stats.blockFrequency.digits !8799, !stats.blockFrequency.scale !8800		; visa id: 1954

.preheader1.7..preheader1.7_crit_edge:            ; preds = %.preheader1.7
; BB223 :
  %1883 = shl i32 %1879, 1		; visa id: 1956
  br label %.preheader1.7, !stats.blockFrequency.digits !8801, !stats.blockFrequency.scale !8802		; visa id: 1957

1884:                                             ; preds = %.preheader1.7
; BB224 :
  %.lcssa468 = phi i32 [ %1879, %.preheader1.7 ]
  %.lcssa467 = phi i32 [ %1880, %.preheader1.7 ]
  %1885 = shl i32 %.lcssa467, 23		; visa id: 1959
  %1886 = add i32 %1885, 1065353216		; visa id: 1960
  %1887 = shl i32 %.lcssa468, 14		; visa id: 1961
  %1888 = and i32 %1887, 8372224		; visa id: 1962
  %1889 = or i32 %1886, %1888
  %1890 = or i32 %1889, %137		; visa id: 1963
  br label %._crit_edge45.7, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1964

NodeBlock.7.._crit_edge45.7_crit_edge:            ; preds = %NodeBlock.7
; BB:
  br label %._crit_edge45.7, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782

._crit_edge45.7:                                  ; preds = %NodeBlock.7.._crit_edge45.7_crit_edge, %1884
; BB226 :
  %1891 = phi i32 [ %1890, %1884 ], [ %.mux.mux, %NodeBlock.7.._crit_edge45.7_crit_edge ]
  %1892 = bitcast i32 %1891 to float
  %1893 = add i64 %125, %sink_397		; visa id: 1965
  %1894 = inttoptr i64 %1893 to ptr addrspace(4)		; visa id: 1966
  %1895 = addrspacecast ptr addrspace(4) %1894 to ptr addrspace(1)		; visa id: 1966
  %1896 = load i8, ptr addrspace(1) %1895, align 1, !noalias !8793		; visa id: 1967
  %b2s451 = sext i8 %1896 to i16
  %1897 = trunc i16 %b2s450 to i8		; visa id: 1969
  %1898 = zext i8 %1897 to i32		; visa id: 1970
  %1899 = shl nuw nsw i32 %1898, 11		; visa id: 1971
  %1900 = zext i16 %1873 to i32		; visa id: 1972
  %1901 = shl nuw nsw i32 %1900, 3		; visa id: 1973
  %1902 = and i32 %1901, 2040
  %1903 = or i32 %1899, %1902		; visa id: 1974
  %1904 = zext i32 %1903 to i64		; visa id: 1975
  %1905 = add i64 %sink_395, %1904		; visa id: 1976
  %1906 = inttoptr i64 %1905 to ptr addrspace(1)		; visa id: 1977
  %1907 = load <2 x i32>, ptr addrspace(1) %1906, align 4		; visa id: 1977
  %b2s452 = zext i8 %1896 to i16		; visa id: 1978
  %b2s453 = lshr i16 %b2s452, 4		; visa id: 1979
  %1908 = trunc i16 %b2s453 to i8		; visa id: 1980
  %1909 = uitofp i8 %1908 to float		; visa id: 1981
  %1910 = fadd float %1909, 5.000000e-01		; visa id: 1982
  %1911 = fmul float %1910, %1892		; visa id: 1983
  %1912 = fmul float %1911, 2.500000e-01		; visa id: 1984
  %1913 = extractelement <2 x i32> %1907, i32 0		; visa id: 1985
  %1914 = extractelement <2 x i32> %1907, i32 1		; visa id: 1985
  %1915 = and i32 %1891, 2139095040		; visa id: 1985
  %1916 = bitcast float %1912 to i32
  %1917 = and i32 %1916, 2147483647		; visa id: 1986
  %1918 = icmp eq i32 %1915, 2139095040
  %1919 = icmp ugt i32 %1917, 2139095040		; visa id: 1987
  %1920 = or i1 %1918, %1919		; visa id: 1988
  %1921 = and i32 %1913, 255		; visa id: 1990
  br i1 %1920, label %1929, label %1922, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 1991

1922:                                             ; preds = %._crit_edge45.7
; BB227 :
  %1923 = and i32 %1900, 256
  %1924 = sub nsw i32 0, %1921, !spirv.Decorations !8798
  %1925 = icmp eq i32 %1923, 0		; visa id: 1993
  %1926 = select i1 %1925, i32 %1921, i32 %1924		; visa id: 1995
  %1927 = sitofp i32 %1926 to float		; visa id: 1996
  %1928 = fmul float %1912, %1927		; visa id: 1997
  br label %1937, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 1998

1929:                                             ; preds = %._crit_edge45.7
; BB228 :
  %1930 = uitofp i32 %1921 to float		; visa id: 2000
  %1931 = fmul float %1912, %1930		; visa id: 2001
  %1932 = and i32 %1900, 256
  %1933 = icmp eq i32 %1932, 0		; visa id: 2002
  %1934 = select i1 %1933, i32 1, i32 -1		; visa id: 2004
  %1935 = sitofp i32 %1934 to float		; visa id: 2005
  %1936 = fmul float %1931, %1935		; visa id: 2006
  br label %1937, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2007

1937:                                             ; preds = %1929, %1922
; BB229 :
  %.sroa.0125.7 = phi float [ %1936, %1929 ], [ %1928, %1922 ]
  %1938 = bitcast i32 %1913 to <4 x i8>
  %1939 = extractelement <4 x i8> %1938, i32 1
  %1940 = zext i8 %1939 to i32		; visa id: 2008
  br i1 %1920, label %1948, label %1941, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2009

1941:                                             ; preds = %1937
; BB230 :
  %1942 = and i32 %1900, 512
  %1943 = sub nsw i32 0, %1940, !spirv.Decorations !8798
  %1944 = icmp eq i32 %1942, 0		; visa id: 2011
  %1945 = select i1 %1944, i32 %1940, i32 %1943		; visa id: 2013
  %1946 = sitofp i32 %1945 to float		; visa id: 2014
  %1947 = fmul float %1912, %1946		; visa id: 2015
  br label %1956, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2016

1948:                                             ; preds = %1937
; BB231 :
  %1949 = uitofp i32 %1940 to float		; visa id: 2018
  %1950 = fmul float %1912, %1949		; visa id: 2019
  %1951 = and i32 %1900, 512
  %1952 = icmp eq i32 %1951, 0		; visa id: 2020
  %1953 = select i1 %1952, i32 1, i32 -1		; visa id: 2022
  %1954 = sitofp i32 %1953 to float		; visa id: 2023
  %1955 = fmul float %1950, %1954		; visa id: 2024
  br label %1956, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2025

1956:                                             ; preds = %1948, %1941
; BB232 :
  %.sroa.40.7 = phi float [ %1955, %1948 ], [ %1947, %1941 ]
  %1957 = extractelement <4 x i8> %1938, i32 2
  %1958 = zext i8 %1957 to i32		; visa id: 2026
  br i1 %1920, label %1966, label %1959, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2027

1959:                                             ; preds = %1956
; BB233 :
  %1960 = and i32 %1900, 1024
  %1961 = sub nsw i32 0, %1958, !spirv.Decorations !8798
  %1962 = icmp eq i32 %1960, 0		; visa id: 2029
  %1963 = select i1 %1962, i32 %1958, i32 %1961		; visa id: 2031
  %1964 = sitofp i32 %1963 to float		; visa id: 2032
  %1965 = fmul float %1912, %1964		; visa id: 2033
  br label %1974, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2034

1966:                                             ; preds = %1956
; BB234 :
  %1967 = uitofp i32 %1958 to float		; visa id: 2036
  %1968 = fmul float %1912, %1967		; visa id: 2037
  %1969 = and i32 %1900, 1024
  %1970 = icmp eq i32 %1969, 0		; visa id: 2038
  %1971 = select i1 %1970, i32 1, i32 -1		; visa id: 2040
  %1972 = sitofp i32 %1971 to float		; visa id: 2041
  %1973 = fmul float %1968, %1972		; visa id: 2042
  br label %1974, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2043

1974:                                             ; preds = %1966, %1959
; BB235 :
  %.sroa.64140.7 = phi float [ %1973, %1966 ], [ %1965, %1959 ]
  %1975 = lshr i32 %1913, 24		; visa id: 2044
  br i1 %1920, label %1983, label %1976, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2045

1976:                                             ; preds = %1974
; BB236 :
  %1977 = and i32 %1900, 2048
  %1978 = sub nsw i32 0, %1975, !spirv.Decorations !8798
  %1979 = icmp eq i32 %1977, 0		; visa id: 2047
  %1980 = select i1 %1979, i32 %1975, i32 %1978		; visa id: 2049
  %1981 = sitofp i32 %1980 to float		; visa id: 2050
  %1982 = fmul float %1912, %1981		; visa id: 2051
  br label %1991, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2052

1983:                                             ; preds = %1974
; BB237 :
  %1984 = uitofp i32 %1975 to float		; visa id: 2054
  %1985 = fmul float %1912, %1984		; visa id: 2055
  %1986 = and i32 %1900, 2048
  %1987 = icmp eq i32 %1986, 0		; visa id: 2056
  %1988 = select i1 %1987, i32 1, i32 -1		; visa id: 2058
  %1989 = sitofp i32 %1988 to float		; visa id: 2059
  %1990 = fmul float %1985, %1989		; visa id: 2060
  br label %1991, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2061

1991:                                             ; preds = %1983, %1976
; BB238 :
  %.sroa.88.7 = phi float [ %1990, %1983 ], [ %1982, %1976 ]
  %1992 = and i32 %1914, 255		; visa id: 2062
  br i1 %1920, label %2000, label %1993, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2063

1993:                                             ; preds = %1991
; BB239 :
  %1994 = and i32 %1900, 4096
  %1995 = sub nsw i32 0, %1992, !spirv.Decorations !8798
  %1996 = icmp eq i32 %1994, 0		; visa id: 2065
  %1997 = select i1 %1996, i32 %1992, i32 %1995		; visa id: 2067
  %1998 = sitofp i32 %1997 to float		; visa id: 2068
  %1999 = fmul float %1912, %1998		; visa id: 2069
  br label %2008, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2070

2000:                                             ; preds = %1991
; BB240 :
  %2001 = uitofp i32 %1992 to float		; visa id: 2072
  %2002 = fmul float %1912, %2001		; visa id: 2073
  %2003 = and i32 %1900, 4096
  %2004 = icmp eq i32 %2003, 0		; visa id: 2074
  %2005 = select i1 %2004, i32 1, i32 -1		; visa id: 2076
  %2006 = sitofp i32 %2005 to float		; visa id: 2077
  %2007 = fmul float %2002, %2006		; visa id: 2078
  br label %2008, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2079

2008:                                             ; preds = %2000, %1993
; BB241 :
  %.sroa.112155.7 = phi float [ %2007, %2000 ], [ %1999, %1993 ]
  %2009 = bitcast i32 %1914 to <4 x i8>
  %2010 = extractelement <4 x i8> %2009, i32 1
  %2011 = zext i8 %2010 to i32		; visa id: 2080
  br i1 %1920, label %2019, label %2012, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2081

2012:                                             ; preds = %2008
; BB242 :
  %2013 = and i32 %1900, 8192
  %2014 = sub nsw i32 0, %2011, !spirv.Decorations !8798
  %2015 = icmp eq i32 %2013, 0		; visa id: 2083
  %2016 = select i1 %2015, i32 %2011, i32 %2014		; visa id: 2085
  %2017 = sitofp i32 %2016 to float		; visa id: 2086
  %2018 = fmul float %1912, %2017		; visa id: 2087
  br label %2027, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2088

2019:                                             ; preds = %2008
; BB243 :
  %2020 = uitofp i32 %2011 to float		; visa id: 2090
  %2021 = fmul float %1912, %2020		; visa id: 2091
  %2022 = and i32 %1900, 8192
  %2023 = icmp eq i32 %2022, 0		; visa id: 2092
  %2024 = select i1 %2023, i32 1, i32 -1		; visa id: 2094
  %2025 = sitofp i32 %2024 to float		; visa id: 2095
  %2026 = fmul float %2021, %2025		; visa id: 2096
  br label %2027, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2097

2027:                                             ; preds = %2019, %2012
; BB244 :
  %.sroa.136.7 = phi float [ %2026, %2019 ], [ %2018, %2012 ]
  %2028 = extractelement <4 x i8> %2009, i32 2
  %2029 = zext i8 %2028 to i32		; visa id: 2098
  br i1 %1920, label %2037, label %2030, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2099

2030:                                             ; preds = %2027
; BB245 :
  %2031 = and i32 %1900, 16384
  %2032 = sub nsw i32 0, %2029, !spirv.Decorations !8798
  %2033 = icmp eq i32 %2031, 0		; visa id: 2101
  %2034 = select i1 %2033, i32 %2029, i32 %2032		; visa id: 2103
  %2035 = sitofp i32 %2034 to float		; visa id: 2104
  %2036 = fmul float %1912, %2035		; visa id: 2105
  br label %2045, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2106

2037:                                             ; preds = %2027
; BB246 :
  %2038 = uitofp i32 %2029 to float		; visa id: 2108
  %2039 = fmul float %1912, %2038		; visa id: 2109
  %2040 = and i32 %1900, 16384
  %2041 = icmp eq i32 %2040, 0		; visa id: 2110
  %2042 = select i1 %2041, i32 1, i32 -1		; visa id: 2112
  %2043 = sitofp i32 %2042 to float		; visa id: 2113
  %2044 = fmul float %2039, %2043		; visa id: 2114
  br label %2045, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2115

2045:                                             ; preds = %2037, %2030
; BB247 :
  %.sroa.160.7 = phi float [ %2044, %2037 ], [ %2036, %2030 ]
  %2046 = lshr i32 %1914, 24		; visa id: 2116
  br i1 %1920, label %2053, label %2047, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2117

2047:                                             ; preds = %2045
; BB248 :
  %2048 = sub nsw i32 0, %2046, !spirv.Decorations !8798
  %2049 = icmp slt i16 %1873, 0		; visa id: 2119
  %2050 = select i1 %2049, i32 %2048, i32 %2046		; visa id: 2120
  %2051 = sitofp i32 %2050 to float		; visa id: 2121
  %2052 = fmul float %1912, %2051		; visa id: 2122
  br label %2059, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2123

2053:                                             ; preds = %2045
; BB249 :
  %2054 = uitofp i32 %2046 to float		; visa id: 2125
  %2055 = fmul float %1912, %2054		; visa id: 2126
  %2056 = fsub float 0.000000e+00, %2055
  %2057 = icmp slt i16 %1873, 0		; visa id: 2127
  %2058 = select i1 %2057, float %2056, float %2055		; visa id: 2128
  br label %2059, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8782		; visa id: 2129

2059:                                             ; preds = %2053, %2047
; BB250 :
  %.sroa.184.7 = phi float [ %2058, %2053 ], [ %2052, %2047 ]
  %2060 = shl nuw i32 %1869, 1		; visa id: 2130
  %2061 = zext i32 %2060 to i64		; visa id: 2131
  %2062 = add i64 %2061, %const_reg_qword2		; visa id: 2132
  %IntToPtr2381 = inttoptr i64 %2062 to ptr addrspace(1)		; visa id: 2133
  %vCastload382 = load i32, ptr addrspace(1) %IntToPtr2381, align 2		; visa id: 2133
  %2063 = add i64 %2062, 4
  %IntToPtr2383 = inttoptr i64 %2063 to ptr addrspace(1)
  %vCastload384 = load i32, ptr addrspace(1) %IntToPtr2383, align 2		; visa id: 2134
  %2064 = add i64 %2062, 8
  %IntToPtr2385 = inttoptr i64 %2064 to ptr addrspace(1)
  %vCastload386 = load i32, ptr addrspace(1) %IntToPtr2385, align 2		; visa id: 2135
  %2065 = add i64 %2062, 12
  %IntToPtr2387 = inttoptr i64 %2065 to ptr addrspace(1)
  %vCastload388 = load i32, ptr addrspace(1) %IntToPtr2387, align 2		; visa id: 2136
  %2066 = bitcast i32 %vCastload382 to <2 x i16>		; visa id: 2137
  %2067 = bitcast i32 %vCastload384 to <2 x i16>		; visa id: 2139
  %2068 = extractelement <2 x i16> %2066, i32 0		; visa id: 2141
  %2069 = extractelement <2 x i16> %2066, i32 1		; visa id: 2141
  %2070 = extractelement <2 x i16> %2067, i32 0		; visa id: 2141
  %2071 = extractelement <2 x i16> %2067, i32 1		; visa id: 2141
  %2072 = bitcast i32 %vCastload386 to <2 x i16>		; visa id: 2141
  %2073 = bitcast i32 %vCastload388 to <2 x i16>		; visa id: 2143
  %2074 = extractelement <2 x i16> %2072, i32 0		; visa id: 2145
  %2075 = extractelement <2 x i16> %2072, i32 1		; visa id: 2145
  %2076 = extractelement <2 x i16> %2073, i32 0		; visa id: 2145
  %2077 = extractelement <2 x i16> %2073, i32 1		; visa id: 2145
  %2078 = zext i16 %2068 to i32		; visa id: 2145
  %2079 = shl nuw i32 %2078, 16, !spirv.Decorations !8788		; visa id: 2146
  %2080 = bitcast i32 %2079 to float
  %2081 = fmul float %.sroa.0125.7, %2080		; visa id: 2147
  %2082 = fadd float %.sroa.36.0, %2081		; visa id: 2148
  %2083 = zext i16 %2069 to i32		; visa id: 2149
  %2084 = shl nuw i32 %2083, 16, !spirv.Decorations !8788		; visa id: 2150
  %2085 = bitcast i32 %2084 to float
  %2086 = fmul float %.sroa.40.7, %2085		; visa id: 2151
  %2087 = fadd float %2082, %2086		; visa id: 2152
  %2088 = zext i16 %2070 to i32		; visa id: 2153
  %2089 = shl nuw i32 %2088, 16, !spirv.Decorations !8788		; visa id: 2154
  %2090 = bitcast i32 %2089 to float
  %2091 = fmul float %.sroa.64140.7, %2090		; visa id: 2155
  %2092 = fadd float %2087, %2091		; visa id: 2156
  %2093 = zext i16 %2071 to i32		; visa id: 2157
  %2094 = shl nuw i32 %2093, 16, !spirv.Decorations !8788		; visa id: 2158
  %2095 = bitcast i32 %2094 to float
  %2096 = fmul float %.sroa.88.7, %2095		; visa id: 2159
  %2097 = fadd float %2092, %2096		; visa id: 2160
  %2098 = zext i16 %2074 to i32		; visa id: 2161
  %2099 = shl nuw i32 %2098, 16, !spirv.Decorations !8788		; visa id: 2162
  %2100 = bitcast i32 %2099 to float
  %2101 = fmul float %.sroa.112155.7, %2100		; visa id: 2163
  %2102 = fadd float %2097, %2101		; visa id: 2164
  %2103 = zext i16 %2075 to i32		; visa id: 2165
  %2104 = shl nuw i32 %2103, 16, !spirv.Decorations !8788		; visa id: 2166
  %2105 = bitcast i32 %2104 to float
  %2106 = fmul float %.sroa.136.7, %2105		; visa id: 2167
  %2107 = fadd float %2102, %2106		; visa id: 2168
  %2108 = zext i16 %2076 to i32		; visa id: 2169
  %2109 = shl nuw i32 %2108, 16, !spirv.Decorations !8788		; visa id: 2170
  %2110 = bitcast i32 %2109 to float
  %2111 = fmul float %.sroa.160.7, %2110		; visa id: 2171
  %2112 = fadd float %2107, %2111		; visa id: 2172
  %2113 = zext i16 %2077 to i32		; visa id: 2173
  %2114 = shl nuw i32 %2113, 16, !spirv.Decorations !8788		; visa id: 2174
  %2115 = bitcast i32 %2114 to float
  %2116 = fmul float %.sroa.184.7, %2115		; visa id: 2175
  %2117 = fadd float %2112, %2116		; visa id: 2176
  %2118 = icmp ult i32 %112, 9		; visa id: 2177
  br i1 %2118, label %.NodeBlock_crit_edge, label %.preheader.preheader, !stats.blockFrequency.digits !8796, !stats.blockFrequency.scale !8797		; visa id: 2178

.NodeBlock_crit_edge:                             ; preds = %2059
; BB251 :
  %2119 = add nuw nsw i32 %112, 1, !spirv.Decorations !8791		; visa id: 2180
  br label %NodeBlock, !stats.blockFrequency.digits !8803, !stats.blockFrequency.scale !8797		; visa id: 2181

.preheader.preheader:                             ; preds = %2059
; BB252 :
  %.lcssa476 = phi float [ %2117, %2059 ]
  %.lcssa475 = phi float [ %1868, %2059 ]
  %.lcssa474 = phi float [ %1619, %2059 ]
  %.lcssa473 = phi float [ %1370, %2059 ]
  %.lcssa472 = phi float [ %1122, %2059 ]
  %.lcssa471 = phi float [ %880, %2059 ]
  %.lcssa470 = phi float [ %637, %2059 ]
  %.lcssa469 = phi float [ %394, %2059 ]
  %2120 = fadd float %.lcssa469, %.lcssa470		; visa id: 2183
  %2121 = fadd float %.lcssa471, %.lcssa472		; visa id: 2184
  %2122 = fadd float %.lcssa473, %.lcssa474		; visa id: 2185
  %2123 = fadd float %.lcssa475, %.lcssa476		; visa id: 2186
  %2124 = fadd float %2120, %2121		; visa id: 2187
  %2125 = fadd float %2122, %2123		; visa id: 2188
  %2126 = fadd float %2124, %2125		; visa id: 2189
  br label %._crit_edge, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8790		; visa id: 2192

._crit_edge:                                      ; preds = %.._crit_edge_crit_edge, %precompiled_u32divrem_sp.exit.._crit_edge_crit_edge, %._crit_edge44, %.preheader.preheader
; BB253 :
  %2127 = phi i32 [ -1, %.preheader.preheader ], [ 0, %._crit_edge44 ], [ 0, %precompiled_u32divrem_sp.exit.._crit_edge_crit_edge ], [ 0, %.._crit_edge_crit_edge ]
  %2128 = phi i32 [ 0, %.preheader.preheader ], [ %61, %._crit_edge44 ], [ -1, %precompiled_u32divrem_sp.exit.._crit_edge_crit_edge ], [ -1, %.._crit_edge_crit_edge ]
  %2129 = phi float [ %2126, %.preheader.preheader ], [ 0.000000e+00, %._crit_edge44 ], [ 0.000000e+00, %precompiled_u32divrem_sp.exit.._crit_edge_crit_edge ], [ 0.000000e+00, %.._crit_edge_crit_edge ]
  %2130 = add nuw nsw i32 %simdLaneId, 1		; visa id: 2193
  %2131 = and i32 %2130, 31		; visa id: 2194
  %simdShuffle = call float @llvm.genx.GenISA.WaveShuffleIndex.f32(float %2129, i32 %2131, i32 0)		; visa id: 2195
  %2132 = and i32 %simdLaneId, 1
  %2133 = icmp eq i32 %2132, 0		; visa id: 2202
  %2134 = select i1 %2133, float %simdShuffle, float -0.000000e+00		; visa id: 2204
  %2135 = fadd float %2129, %2134		; visa id: 2205
  %2136 = add nuw nsw i32 %simdLaneId, 2		; visa id: 2206
  %2137 = and i32 %2136, 31		; visa id: 2207
  %simdShuffle.1 = call float @llvm.genx.GenISA.WaveShuffleIndex.f32(float %2135, i32 %2137, i32 0)		; visa id: 2208
  %2138 = icmp ne i32 %6, 0		; visa id: 2215
  %2139 = or i1 %30, %2138		; visa id: 2216
  br i1 %2139, label %._crit_edge.._crit_edge46_crit_edge, label %2140, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8782		; visa id: 2218

._crit_edge.._crit_edge46_crit_edge:              ; preds = %._crit_edge
; BB:
  br label %._crit_edge46, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787

2140:                                             ; preds = %._crit_edge
; BB255 :
  %2141 = icmp eq i32 %6, 0		; visa id: 2220
  %2142 = select i1 %2141, float %simdShuffle.1, float -0.000000e+00		; visa id: 2221
  %2143 = fadd float %2135, %2142		; visa id: 2222
  %2144 = bitcast float %2143 to i32
  %2145 = icmp ne i32 %2127, 0		; visa id: 2223
  %2146 = select i1 %2145, i32 %2144, i32 2143289344		; visa id: 2224
  %2147 = and i32 %2146, 2147483647		; visa id: 2225
  %2148 = icmp ugt i32 %2147, 2139095040		; visa id: 2226
  br i1 %2148, label %2156, label %2149, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 2227

2149:                                             ; preds = %2140
; BB256 :
  %2150 = lshr i32 %2146, 16		; visa id: 2229
  %2151 = and i32 %2150, 1		; visa id: 2230
  %2152 = add i32 %2146, %2151
  %2153 = add i32 %2152, 32767		; visa id: 2231
  %2154 = lshr i32 %2153, 16		; visa id: 2232
  %2155 = trunc i32 %2154 to i16		; visa id: 2233
  br label %2160, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 2234

2156:                                             ; preds = %2140
; BB257 :
  %2157 = lshr i32 %2146, 16		; visa id: 2236
  %2158 = trunc i32 %2157 to i16		; visa id: 2237
  %2159 = or i16 %2158, 64		; visa id: 2238
  br label %2160, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 2239

2160:                                             ; preds = %2149, %2156
; BB258 :
  %2161 = phi i16 [ %2159, %2156 ], [ %2155, %2149 ]
  %2162 = bitcast i64 %const_reg_qword12 to <2 x i32>		; visa id: 2240
  %2163 = extractelement <2 x i32> %2162, i32 0		; visa id: 2241
  %2164 = extractelement <2 x i32> %2162, i32 1		; visa id: 2241
  %2165 = bitcast i64 %const_reg_qword13 to <2 x i32>		; visa id: 2241
  %2166 = extractelement <2 x i32> %2165, i32 0		; visa id: 2242
  %2167 = extractelement <2 x i32> %2165, i32 1		; visa id: 2242
  %2168 = icmp eq i16 %5, 0		; visa id: 2242
  %2169 = select i1 %2168, i32 %2163, i32 %2166		; visa id: 2243
  %2170 = select i1 %2168, i32 %2164, i32 %2167		; visa id: 2244
  %2171 = insertelement <2 x i32> undef, i32 %2169, i32 0		; visa id: 2245
  %2172 = insertelement <2 x i32> %2171, i32 %2170, i32 1		; visa id: 2246
  %2173 = bitcast <2 x i32> %2172 to i64		; visa id: 2247
  %2174 = zext i32 %13 to i64		; visa id: 2251
  %2175 = shl nuw nsw i64 %2174, 1		; visa id: 2252
  %2176 = add i64 %2173, %2175		; visa id: 2253
  %2177 = inttoptr i64 %2176 to ptr addrspace(4)		; visa id: 2254
  %2178 = addrspacecast ptr addrspace(4) %2177 to ptr addrspace(1)		; visa id: 2254
  store i16 %2161, ptr addrspace(1) %2178, align 2		; visa id: 2255
  %2179 = icmp eq i32 %13, %29		; visa id: 2257
  br i1 %2179, label %2180, label %.._crit_edge46_crit_edge, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8787		; visa id: 2258

.._crit_edge46_crit_edge:                         ; preds = %2160
; BB:
  br label %._crit_edge46, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784

2180:                                             ; preds = %2160
; BB260 :
  %2181 = bitcast i64 %const_reg_qword17 to <2 x i32>		; visa id: 2260
  %2182 = extractelement <2 x i32> %2181, i32 0		; visa id: 2261
  %2183 = extractelement <2 x i32> %2181, i32 1		; visa id: 2261
  %2184 = bitcast i64 %const_reg_qword18 to <2 x i32>		; visa id: 2261
  %2185 = extractelement <2 x i32> %2184, i32 0		; visa id: 2262
  %2186 = extractelement <2 x i32> %2184, i32 1		; visa id: 2262
  %2187 = icmp ne i32 %2128, 0		; visa id: 2262
  %2188 = sext i1 %2187 to i32		; visa id: 2263
  %2189 = sub i32 0, %2188		; visa id: 2264
  %2190 = select i1 %2168, i32 %2182, i32 %2185		; visa id: 2265
  %2191 = select i1 %2168, i32 %2183, i32 %2186		; visa id: 2266
  %2192 = insertelement <2 x i32> undef, i32 %2190, i32 0		; visa id: 2267
  %2193 = insertelement <2 x i32> %2192, i32 %2191, i32 1		; visa id: 2268
  %2194 = bitcast <2 x i32> %2193 to i64		; visa id: 2269
  %2195 = zext i32 %retval.0.i to i64		; visa id: 2273
  %2196 = shl nuw nsw i64 %2195, 2		; visa id: 2274
  %2197 = add i64 %2194, %2196		; visa id: 2275
  %2198 = inttoptr i64 %2197 to ptr addrspace(4)		; visa id: 2276
  %2199 = addrspacecast ptr addrspace(4) %2198 to ptr addrspace(1)		; visa id: 2276
  store i32 %2189, ptr addrspace(1) %2199, align 4		; visa id: 2277
  br i1 %2187, label %2200, label %.._crit_edge46_crit_edge325, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8784		; visa id: 2278

.._crit_edge46_crit_edge325:                      ; preds = %2180
; BB:
  br label %._crit_edge46, !stats.blockFrequency.digits !8804, !stats.blockFrequency.scale !8805

2200:                                             ; preds = %2180
; BB262 :
  %2201 = inttoptr i64 %const_reg_qword20 to ptr addrspace(4)		; visa id: 2280
  %2202 = addrspacecast ptr addrspace(4) %2201 to ptr addrspace(1)		; visa id: 2280
  %2203 = load i32, ptr addrspace(1) %2202, align 4		; visa id: 2281
  %2204 = icmp eq i32 %2203, 0		; visa id: 2282
  br i1 %2204, label %.._crit_edge46_crit_edge326, label %2205, !stats.blockFrequency.digits !8806, !stats.blockFrequency.scale !8807		; visa id: 2283

.._crit_edge46_crit_edge326:                      ; preds = %2200
; BB:
  br label %._crit_edge46, !stats.blockFrequency.digits !8808, !stats.blockFrequency.scale !8805

2205:                                             ; preds = %2200
; BB264 :
  %2206 = inttoptr i64 %const_reg_qword19 to ptr addrspace(4)		; visa id: 2285
  %2207 = addrspacecast ptr addrspace(4) %2206 to ptr addrspace(1)		; visa id: 2285
  %2208 = call i32 @llvm.genx.GenISA.icmpxchgatomicrawA64.i32.p1.p1(ptr addrspace(1) %2207, ptr addrspace(1) %2207, i32 0, i32 1)		; visa id: 2286
  br label %._crit_edge46, !stats.blockFrequency.digits !8809, !stats.blockFrequency.scale !8805		; visa id: 2291

._crit_edge46:                                    ; preds = %.._crit_edge46_crit_edge326, %.._crit_edge46_crit_edge325, %.._crit_edge46_crit_edge, %._crit_edge.._crit_edge46_crit_edge, %2205
; BB265 :
  ret void, !stats.blockFrequency.digits !8781, !stats.blockFrequency.scale !8782		; visa id: 2292
}
