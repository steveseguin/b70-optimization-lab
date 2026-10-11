"""Bounded vector evaluation of packet1b's scalar decoder equations.

The scalar loader and its format tables remain the authority. No external
decoder is imported. qualify.py compares these bytes with that authority.
No float64 products, fused operations, or dequantized weight rounding.
"""
import numpy as np
from loaders.dequant import BY_NAME, IQ2_S_GRID, IQ3_S_GRID, IQ4


def decode(kind, raw):
    block, size = BY_NAME[kind]
    if len(raw) % size:
        raise ValueError('partial block')
    if kind == 'F32':
        return np.frombuffer(raw, '<f4').copy()
    if kind == 'BF16':
        return (np.frombuffer(raw, '<u2').astype(np.uint32) << 16).view(np.float32)
    b = np.frombuffer(raw, np.uint8).reshape(-1, size)
    i = np.arange(block)
    def half(at):
        return b[:, at:at+2].copy().view('<f2').astype(np.float32)
    if kind == 'Q8_0':
        return (half(0)*b[:, 2:].copy().view(np.int8).astype(np.float32)).ravel()
    if kind == 'IQ4_NL':
        idx = (b[:, 2+i%16] >> (4*(i//16))) & 15
        return (half(0)*np.array(IQ4, np.float32)[idx]).ravel()
    if kind == 'Q6_K':
        low = (b[:, (i//128)*64+i%64] >> (4*((i%128)//64))) & 15
        high = (b[:, 128+(i//128)*32+i%32] >> (2*((i%128)//32))) & 3
        sc = b[:, 192+i//16].copy().view(np.int8).astype(np.float32)
        q = (low | (high << 4)).astype(np.int32)-32
        return ((half(208)*sc)*q.astype(np.float32)).ravel()
    if kind == 'IQ3_S':
        quad = i//4
        idx = b[:, 2+quad].astype(np.int32) | (((b[:, 66+quad//8] >> (quad%8)) & 1) << 8)
        grid = np.array(IQ3_S_GRID, np.uint32)
        mag = ((grid[idx] >> (8*(i%4))) & 255).astype(np.float32)
        sign = (1-2*((b[:, 74+i//8] >> (i%8)) & 1).astype(np.int32)).astype(np.float32)
        sc = ((b[:, 106+i//64] >> (4*((i//32)%2))) & 15).astype(np.float32)
        return (((half(0)*(1+2*sc))*mag)*sign).ravel()
    if kind == 'IQ2_S':
        octet = i//8
        idx = b[:, 2+octet].astype(np.int32) | (((b[:, 66+octet//4] >> (2*(octet%4))) & 3) << 8)
        grid = np.array(IQ2_S_GRID, np.uint64)
        mag = ((grid[idx] >> (8*(i%8)).astype(np.uint64)) & 255).astype(np.float32)
        sign = (1-2*((b[:, 34+octet] >> (i%8)) & 1).astype(np.int32)).astype(np.float32)
        sc = ((b[:, 74+i//32] >> (4*((i//16)%2))) & 15).astype(np.float32)
        return ((((half(0)*(np.float32(.5)+sc))*np.float32(.25))*mag)*sign).ravel()
    raise ValueError('unqualified grid: '+kind)
