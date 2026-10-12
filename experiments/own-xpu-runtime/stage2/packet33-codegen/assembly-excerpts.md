# Short annotated GEN excerpts

Offline target0xe223 revision0, precise divide/sqrt retained. Full dumps are ignored build artifacts; hashes and control-flow block lists are in the review JSON. These are selected lines, not entire loops. No device executed.

## R5 IQ4_NL down

`build/igc-a69786/OCL_asmc78371f103cf7ac1_simd32_entry_0003.asm`, SHA256 `111b1adffa4047f28908028e6284fda8a983049a4e26a4891ad4b1cb75d9a7f7`.

```asm
(W)     load.ugm.d32x4t.a64.ca.cc (1|M0)  r18:1 [r11:1+0xC0]       {$7} // ex_desc:0xC0000; desc:0x219B580 // $53
(W)     load.ugm.d32x2t.a64.ca.cc (1|M0)  r4:1  [r11:1+0xD0]       {$8} // ex_desc:0xD0000; desc:0x2199580 // $55
(W)     load.ugm.d64x1t.a64.ca.ca (1|M0)  r11:1 [r10:1]            {I@2,$10} // ex_desc:0x0; desc:0x2188780 // $149
(W)     load.ugm.d32x2t.a64 (1|M0)  r34:1       [r12:1]            {I@1,$11} // ex_desc:0x0; desc:0x2109580 // $158
(W)     load.ugm.d32x1t.a64 (1|M0)  r8:1        [r4:1]             {I@2,$12} // ex_desc:0x0; desc:0x2108580 // $170
(W)     load.ugm.d64x1t.a64.ca.ca (1|M0)  r11:1 [r12:1]            {I@2,$13} // ex_desc:0x0; desc:0x2188780 // $227
(W)     load.ugm.d64x2t.a64.ca.ca (1|M0)  r1:1  [r8:1]             {I@4,$15} // ex_desc:0x0; desc:0x2189780 // $247
(W)     load.ugm.d32x8t.a64.ca.cc (1|M0)  r1:1  [r9:1+0xF8]        {I@1,$2} // ex_desc:0xF8000; desc:0x219C580 // $538
```

## p33.down.bank iteration1

`build/igc-p33-cfc890008950/OCL_asm417cfc36614c865f_simd32_entry_0001.asm`, SHA256 `497df8874df8e865f907aa898d33a39a741f9199d0f7b948c6840831f86ad48e`.

```asm
(W)     load.ugm.d32x3t.a64 (1|M0)  r3:1        [r4:1]             {I@1,$1} // ex_desc:0x0; desc:0x210A580 // $63
        load.ugm.d16u32.a64 (32|M0)  r20:2      [r16:4]            {I@1,$2} // ex_desc:0x0; desc:0x8200B80 // $109
        load.ugm.d32.a64 (32|M0)  r28:2         [r18:4]            {I@1,$3} // ex_desc:0x0; desc:0x8200580 // $164
        load.ugm.d32.a64 (32|M0)  r30:2         [r18:4+0x4]        {$4} // ex_desc:0x4000; desc:0x8200580 // $165
        load.ugm.d32.a64 (32|M0)  r4:2          [r24:4]            {I@1,$5} // ex_desc:0x0; desc:0x8200580 // $170
        load.ugm.d32.a64 (32|M0)  r32:2         [r24:4+0x4]        {$6} // ex_desc:0x4000; desc:0x8200580 // $171
        load.ugm.d32.a64 (32|M0)  r34:2         [r24:4+0x8]        {$7} // ex_desc:0x8000; desc:0x8200580 // $176
        load.ugm.d32.a64 (32|M0)  r6:2          [r24:4+0xC]        {$8} // ex_desc:0xC000; desc:0x8200580 // $177
```

## p33.down.select final-module diagnostic

`build/igc-p33-cfc890008950/OCL_asm417cfc36614c865f_simd32_entry_0002.asm`, SHA256 `a70470ec568125f27ea57ed5868f5b4dbf6fae3197956bb7a97c5737afdada83`.

```asm
(W)     load.ugm.d32x3t.a64 (1|M0)  r3:1        [r4:1]             {I@1,$1} // ex_desc:0x0; desc:0x210A580 // $63
        load.ugm.d16u32.a64 (32|M0)  r20:2      [r16:4]            {I@1,$2} // ex_desc:0x0; desc:0x8200B80 // $109
        load.ugm.d8u32.a64 (32|M0)  r22:2       [r12:4]            {I@2,$3} // ex_desc:0x0; desc:0x8200980 // $166
        load.ugm.d16u32.a64 (32|M0)  r24:2      [r18:4]            {I@1,$4} // ex_desc:0x0; desc:0x8200B80 // $171
        load.ugm.d8u32.a64 (32|M0)  r32:2       [r26:4]            {I@2,$5} // ex_desc:0x0; desc:0x8200980 // $222
        load.ugm.d16u32.a64 (32|M0)  r30:2      [r20:4]            {I@1,$6} // ex_desc:0x0; desc:0x8200B80 // $227
        load.ugm.d8u32.a64 (32|M0)  r30:2       [r20:4]            {I@2,$7} // ex_desc:0x0; desc:0x8200980 // $277
        load.ugm.d16u32.a64 (32|M0)  r4:2       [r24:4]            {I@1,$8} // ex_desc:0x0; desc:0x8200B80 // $282
```

The bank interior octet has one u16 scale gather and six d32 data gathers (two packed codes, four packed BF16 pairs), with no table gather. These are still A64 UGM scatter/gather messages; source vector reads did not become a transposed block load. The select spelling removes source table loads but becomes divergent control flow and retains17 data messages per octet. See the independently traced blocks rather than extrapolating the above snippets.
