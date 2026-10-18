
/tmp/packet58xd-vmlinux:     file format elf64-x86-64


Disassembly of section .text:

ffffffff820e1d20 <.text+0x10e1d20>:
ffffffff820e1d20:	e8 eb 23 26 ff       	call   0xffffffff81344110
ffffffff820e1d25:	55                   	push   %rbp
ffffffff820e1d26:	4d 89 c1             	mov    %r8,%r9
ffffffff820e1d29:	48 89 e5             	mov    %rsp,%rbp
ffffffff820e1d2c:	41 55                	push   %r13
ffffffff820e1d2e:	49 89 f5             	mov    %rsi,%r13
ffffffff820e1d31:	41 54                	push   %r12
ffffffff820e1d33:	49 89 fc             	mov    %rdi,%r12
ffffffff820e1d36:	53                   	push   %rbx
ffffffff820e1d37:	48 83 ec 38          	sub    $0x38,%rsp
ffffffff820e1d3b:	65 48 8b 05 c5 72 35 	mov    %gs:0x23572c5(%rip),%rax        # 0xffffffff84439008
ffffffff820e1d42:	02
ffffffff820e1d43:	48 89 45 e0          	mov    %rax,-0x20(%rbp)
ffffffff820e1d47:	31 c0                	xor    %eax,%eax
ffffffff820e1d49:	48 c7 45 c8 f9 f9 fe 	movq   $0xffffffff82fef9f9,-0x38(%rbp)
ffffffff820e1d50:	82
ffffffff820e1d51:	48 c7 45 d0 b1 bc 01 	movq   $0xffffffff8301bcb1,-0x30(%rbp)
ffffffff820e1d58:	83
ffffffff820e1d59:	48 c7 45 d8 b6 bc 01 	movq   $0xffffffff8301bcb6,-0x28(%rbp)
ffffffff820e1d60:	83
ffffffff820e1d61:	4d 85 c0             	test   %r8,%r8
ffffffff820e1d64:	74 72                	je     0xffffffff820e1dd8
ffffffff820e1d66:	41 f7 c0 ff 03 00 00 	test   $0x3ff,%r8d
ffffffff820e1d6d:	75 69                	jne    0xffffffff820e1dd8
ffffffff820e1d6f:	4c 89 c0             	mov    %r8,%rax
ffffffff820e1d72:	48 c1 e8 0a          	shr    $0xa,%rax
ffffffff820e1d76:	74 64                	je     0xffffffff820e1ddc
ffffffff820e1d78:	a9 ff 03 00 00       	test   $0x3ff,%eax
ffffffff820e1d7d:	75 67                	jne    0xffffffff820e1de6
ffffffff820e1d7f:	49 c1 e9 14          	shr    $0x14,%r9
ffffffff820e1d83:	bb 02 00 00 00       	mov    $0x2,%ebx
ffffffff820e1d88:	48 83 fb 03          	cmp    $0x3,%rbx
ffffffff820e1d8c:	73 67                	jae    0xffffffff820e1df5
ffffffff820e1d8e:	ff 74 dd c8          	push   -0x38(%rbp,%rbx,8)
ffffffff820e1d92:	49 89 c8             	mov    %rcx,%r8
ffffffff820e1d95:	48 c7 c6 bb bc 01 83 	mov    $0xffffffff8301bcbb,%rsi
ffffffff820e1d9c:	48 89 d1             	mov    %rdx,%rcx
ffffffff820e1d9f:	4c 89 e7             	mov    %r12,%rdi
ffffffff820e1da2:	4c 89 ea             	mov    %r13,%rdx
ffffffff820e1da5:	e8 86 8c 01 00       	call   0xffffffff820faa30
ffffffff820e1daa:	58                   	pop    %rax
ffffffff820e1dab:	48 8b 45 e0          	mov    -0x20(%rbp),%rax
ffffffff820e1daf:	65 48 2b 05 51 72 35 	sub    %gs:0x2357251(%rip),%rax        # 0xffffffff84439008
ffffffff820e1db6:	02
ffffffff820e1db7:	75 37                	jne    0xffffffff820e1df0
ffffffff820e1db9:	48 8d 65 e8          	lea    -0x18(%rbp),%rsp
ffffffff820e1dbd:	5b                   	pop    %rbx
ffffffff820e1dbe:	41 5c                	pop    %r12
ffffffff820e1dc0:	41 5d                	pop    %r13
ffffffff820e1dc2:	5d                   	pop    %rbp
ffffffff820e1dc3:	31 c0                	xor    %eax,%eax
ffffffff820e1dc5:	31 d2                	xor    %edx,%edx
ffffffff820e1dc7:	31 c9                	xor    %ecx,%ecx
ffffffff820e1dc9:	31 f6                	xor    %esi,%esi
ffffffff820e1dcb:	31 ff                	xor    %edi,%edi
ffffffff820e1dcd:	45 31 c0             	xor    %r8d,%r8d
ffffffff820e1dd0:	45 31 c9             	xor    %r9d,%r9d
ffffffff820e1dd3:	e9 d8 23 5c 00       	jmp    0xffffffff826a41b0
ffffffff820e1dd8:	31 db                	xor    %ebx,%ebx
ffffffff820e1dda:	eb ac                	jmp    0xffffffff820e1d88
ffffffff820e1ddc:	45 31 c9             	xor    %r9d,%r9d
ffffffff820e1ddf:	bb 01 00 00 00       	mov    $0x1,%ebx
ffffffff820e1de4:	eb a2                	jmp    0xffffffff820e1d88
ffffffff820e1de6:	49 89 c1             	mov    %rax,%r9
ffffffff820e1de9:	bb 01 00 00 00       	mov    $0x1,%ebx
ffffffff820e1dee:	eb 98                	jmp    0xffffffff820e1d88
ffffffff820e1df0:	e8 5b f3 5a 00       	call   0xffffffff82691150
ffffffff820e1df5:	48 89 de             	mov    %rbx,%rsi
ffffffff820e1df8:	48 c7 c7 c0 9d dc 83 	mov    $0xffffffff83dc9dc0,%rdi
ffffffff820e1dff:	4c 89 4d b0          	mov    %r9,-0x50(%rbp)
ffffffff820e1e03:	48 89 4d b8          	mov    %rcx,-0x48(%rbp)
ffffffff820e1e07:	48 89 55 c0          	mov    %rdx,-0x40(%rbp)
ffffffff820e1e0b:	e8 50 36 c4 ff       	call   0xffffffff81d25460
ffffffff820e1e10:	4c 8b 4d b0          	mov    -0x50(%rbp),%r9
ffffffff820e1e14:	48 8b 4d b8          	mov    -0x48(%rbp),%rcx
ffffffff820e1e18:	48 8b 55 c0          	mov    -0x40(%rbp),%rdx
ffffffff820e1e1c:	e9 6d ff ff ff       	jmp    0xffffffff820e1d8e
ffffffff820e1e21:	66 66 2e 0f 1f 84 00 	data16 cs nopw 0x0(%rax,%rax,1)
ffffffff820e1e28:	00 00 00 00
ffffffff820e1e2c:	0f 1f 40 00          	nopl   0x0(%rax)
ffffffff820e1e30:	90                   	nop
ffffffff820e1e31:	90                   	nop
ffffffff820e1e32:	90                   	nop
ffffffff820e1e33:	90                   	nop
ffffffff820e1e34:	90                   	nop
ffffffff820e1e35:	90                   	nop
ffffffff820e1e36:	90                   	nop
ffffffff820e1e37:	90                   	nop
ffffffff820e1e38:	90                   	nop
ffffffff820e1e39:	90                   	nop
ffffffff820e1e3a:	90                   	nop
ffffffff820e1e3b:	90                   	nop
ffffffff820e1e3c:	90                   	nop
ffffffff820e1e3d:	90                   	nop
ffffffff820e1e3e:	90                   	nop
ffffffff820e1e3f:	90                   	nop
ffffffff820e1e40:	e8 cb 22 26 ff       	call   0xffffffff81344110
ffffffff820e1e45:	55                   	push   %rbp
ffffffff820e1e46:	48 89 e5             	mov    %rsp,%rbp
ffffffff820e1e49:	41 56                	push   %r14
ffffffff820e1e4b:	49 89 ce             	mov    %rcx,%r14
ffffffff820e1e4e:	41 55                	push   %r13
ffffffff820e1e50:	49 89 fd             	mov    %rdi,%r13
ffffffff820e1e53:	41 54                	push   %r12
ffffffff820e1e55:	41 89 d4             	mov    %edx,%r12d
ffffffff820e1e58:	48 c7 c2 9e ed fb 82 	mov    $0xffffffff82fbed9e,%rdx
ffffffff820e1e5f:	53                   	push   %rbx
ffffffff820e1e60:	48 89 f3             	mov    %rsi,%rbx
ffffffff820e1e63:	4c 8b 06             	mov    (%rsi),%r8
ffffffff820e1e66:	4c 03 46 08          	add    0x8(%rsi),%r8
ffffffff820e1e6a:	48 c7 c6 38 d3 01 83 	mov    $0xffffffff8301d338,%rsi
ffffffff820e1e71:	e8 aa fe ff ff       	call   0xffffffff820e1d20
ffffffff820e1e76:	4c 8b 03             	mov    (%rbx),%r8
ffffffff820e1e79:	4c 89 f1             	mov    %r14,%rcx
ffffffff820e1e7c:	4c 89 ef             	mov    %r13,%rdi
ffffffff820e1e7f:	48 c7 c2 81 f6 fe 82 	mov    $0xffffffff82fef681,%rdx
ffffffff820e1e86:	48 c7 c6 38 d3 01 83 	mov    $0xffffffff8301d338,%rsi
ffffffff820e1e8d:	e8 8e fe ff ff       	call   0xffffffff820e1d20
ffffffff820e1e92:	41 f6 c4 04          	test   $0x4,%r12b
ffffffff820e1e96:	75 24                	jne    0xffffffff820e1ebc
ffffffff820e1e98:	41 f6 c4 01          	test   $0x1,%r12b
ffffffff820e1e9c:	75 41                	jne    0xffffffff820e1edf
ffffffff820e1e9e:	41 83 e4 02          	and    $0x2,%r12d
ffffffff820e1ea2:	75 5e                	jne    0xffffffff820e1f02
ffffffff820e1ea4:	5b                   	pop    %rbx
ffffffff820e1ea5:	41 5c                	pop    %r12
ffffffff820e1ea7:	41 5d                	pop    %r13
ffffffff820e1ea9:	41 5e                	pop    %r14
ffffffff820e1eab:	5d                   	pop    %rbp
ffffffff820e1eac:	31 d2                	xor    %edx,%edx
ffffffff820e1eae:	31 c9                	xor    %ecx,%ecx
ffffffff820e1eb0:	31 f6                	xor    %esi,%esi
ffffffff820e1eb2:	31 ff                	xor    %edi,%edi
ffffffff820e1eb4:	45 31 c0             	xor    %r8d,%r8d
ffffffff820e1eb7:	e9 f4 22 5c 00       	jmp    0xffffffff826a41b0
ffffffff820e1ebc:	4c 8b 43 20          	mov    0x20(%rbx),%r8
ffffffff820e1ec0:	4c 89 f1             	mov    %r14,%rcx
ffffffff820e1ec3:	4c 89 ef             	mov    %r13,%rdi
ffffffff820e1ec6:	48 c7 c2 99 02 02 83 	mov    $0xffffffff83020299,%rdx
ffffffff820e1ecd:	48 c7 c6 38 d3 01 83 	mov    $0xffffffff8301d338,%rsi
ffffffff820e1ed4:	e8 47 fe ff ff       	call   0xffffffff820e1d20
ffffffff820e1ed9:	41 f6 c4 01          	test   $0x1,%r12b
ffffffff820e1edd:	74 bf                	je     0xffffffff820e1e9e
ffffffff820e1edf:	4c 8b 43 10          	mov    0x10(%rbx),%r8
ffffffff820e1ee3:	4c 89 f1             	mov    %r14,%rcx
ffffffff820e1ee6:	4c 89 ef             	mov    %r13,%rdi
ffffffff820e1ee9:	48 c7 c2 cd bc 01 83 	mov    $0xffffffff8301bccd,%rdx
ffffffff820e1ef0:	48 c7 c6 38 d3 01 83 	mov    $0xffffffff8301d338,%rsi
ffffffff820e1ef7:	e8 24 fe ff ff       	call   0xffffffff820e1d20
ffffffff820e1efc:	41 83 e4 02          	and    $0x2,%r12d
ffffffff820e1f00:	74 a2                	je     0xffffffff820e1ea4
ffffffff820e1f02:	4c 8b 43 18          	mov    0x18(%rbx),%r8
ffffffff820e1f06:	4c 89 f1             	mov    %r14,%rcx
ffffffff820e1f09:	4c 89 ef             	mov    %r13,%rdi
ffffffff820e1f0c:	48 c7 c2 d6 bc 01 83 	mov    $0xffffffff8301bcd6,%rdx
ffffffff820e1f13:	48 c7 c6 38 d3 01 83 	mov    $0xffffffff8301d338,%rsi
ffffffff820e1f1a:	e8 01 fe ff ff       	call   0xffffffff820e1d20
ffffffff820e1f1f:	5b                   	pop    %rbx
ffffffff820e1f20:	41 5c                	pop    %r12
ffffffff820e1f22:	41 5d                	pop    %r13
ffffffff820e1f24:	41 5e                	pop    %r14
ffffffff820e1f26:	5d                   	pop    %rbp
ffffffff820e1f27:	31 d2                	xor    %edx,%edx
ffffffff820e1f29:	31 c9                	xor    %ecx,%ecx
ffffffff820e1f2b:	31 f6                	xor    %esi,%esi
ffffffff820e1f2d:	31 ff                	xor    %edi,%edi
ffffffff820e1f2f:	45                   	rex.RB
