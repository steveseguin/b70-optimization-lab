"""Native FP8 PLE storage. CPU core uses only stdlib; never initializes a device.

Exactness contract: safetensors offsets address the publisher's 160 raw bytes,
not decoded floats. Cache insertion, eviction and fallthrough only copy bytes.
IDs remain global until the TP owner interval is checked. Nonowners emit zero.
The model still uses its int8 owner SUM, FP8 view, output-dtype cast, scale cast
and multiply, in that order. No LUT, requantization, or table rewrite exists.
A CPU byte proof does not certify XPU transport/collectives or the V30 model.
"""
from array import array
from bisect import bisect_right
import hashlib
import json
import mmap
import os
from pathlib import Path
import struct

CACHE_PER_RANK = 1 << 30
STAGING_LIMIT = 256 << 20


def unique_object(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError(f'duplicate key: {k}')
        result[k] = v
    return result


def metadata_bytes(rows, cache_bytes, width=160):
    return rows * 4 + (cache_bytes // width) * 17


class RowStore:
    """Read-only, payload-sliced mmaps of the locally owned checkpoint rows.

    Only headers are read at construction. mmap page residency is reclaimable;
    mapped address space is NOT pinned memory or an enforced page-cache cap.
    Checkpoints must remain immutable throughout the run (read-only mount).
    """
    def __init__(self, folder, prefix, rows, width, parts, start, end):
        self.rows, self.width, self.start, self.end = rows, width, start, end
        if not (0 <= start < end <= rows and width > 0 and parts > 0):
            raise ValueError('invalid table geometry')
        root = Path(folder).resolve()
        index_raw = (root / 'model.safetensors.index.json').read_bytes()
        index = json.loads(index_raw, object_pairs_hook=unique_object)['weight_map']
        self.index_sha256 = hashlib.sha256(index_raw).hexdigest()
        names = {f'{prefix}.shard_{i}.weight' for i in range(parts)}
        actual = {n for n in index if n.startswith(prefix + '.shard_')}
        if actual != names:
            raise ValueError('incomplete or unexpected PLE shard namespace')
        self.segments, self.header_sha256 = [], {}
        size = (rows + parts - 1) // parts
        headers = {}
        try:
            for i in range(parts):
                name = f'{prefix}.shard_{i}.weight'
                rel = Path(index[name])
                path = root / rel
                if rel.is_absolute() or '..' in rel.parts or path.is_symlink() or root not in path.resolve().parents:
                    raise ValueError('unsafe shard path')
                if rel not in headers:
                    with path.open('rb') as f:
                        raw_len = f.read(8)
                        if len(raw_len) != 8:
                            raise ValueError('short header length')
                        length, = struct.unpack('<Q', raw_len)
                        if length > 32 << 20:
                            raise ValueError('oversized header')
                        raw = f.read(length)
                        if len(raw) != length:
                            raise ValueError('short header')
                    headers[rel] = (8 + length, json.loads(raw, object_pairs_hook=unique_object))
                    self.header_sha256[str(rel)] = hashlib.sha256(raw_len + raw).hexdigest()
                base, header = headers[rel]
                info = header[name]
                lo, hi = i * size, min(rows, (i + 1) * size)
                a, b = info['data_offsets']
                if (info['dtype'] not in ('F8_E4M3', 'F8_E4M3FN') or
                        info['shape'] != [hi-lo, width] or a < 0 or
                        b-a != (hi-lo)*width or base+b > path.stat().st_size):
                    raise ValueError('FP8 shard dtype/shape/offset/truncation mismatch')
                left, right = max(lo, start), min(hi, end)
                if left >= right:
                    continue
                offset = base + a + (left-lo)*width
                aligned = offset // mmap.ALLOCATIONGRANULARITY * mmap.ALLOCATIONGRANULARITY
                delta = offset - aligned
                with path.open('rb') as f:
                    mapping = mmap.mmap(f.fileno(), delta+(right-left)*width,
                                        access=mmap.ACCESS_READ, offset=aligned)
                self.segments.append((left, right, mapping, delta, str(path), aligned))
            self.starts = [s[0] for s in self.segments]
            if sum(b-a for a,b,*_ in self.segments) != end-start:
                raise ValueError('local PLE coverage mismatch')
        except BaseException:
            self.close()
            raise

    def read_row(self, row):
        if not self.start <= row < self.end:
            raise IndexError('row outside TP ownership')
        lo, hi, mapping, delta, path, offset = self.segments[bisect_right(self.starts, row)-1]
        # A truncation after mapping would otherwise SIGBUS. Content mutation is
        # prevented by the model's read-only mount and hash-bound launch identity.
        if os.stat(path).st_size < offset + len(mapping):
            raise ValueError('checkpoint truncated after mapping')
        at = delta + (row-lo)*self.width
        result = mapping[at:at+self.width]
        if len(result) != self.width:
            raise ValueError('short row')
        return result

    def resident_bytes(self):
        """RSS of these exact read-only mappings, from proc, not mapped length.

        File pages may be shared: do not sum this with system pressure, cgroup
        file bytes or another rank's RSS. Failure/ambiguous mapping is unknown.
        """
        try:
            wanted = {(p, off, ((len(m)+4095)//4096)*4096) for _,_,m,_,p,off in self.segments}
            seen, total, current = set(), 0, None
            for line in Path('/proc/self/smaps').read_text().splitlines():
                fields = line.split(None, 5)
                if fields and '-' in fields[0] and len(fields) >= 5:
                    a,b = (int(x,16) for x in fields[0].split('-'))
                    current = (fields[5] if len(fields)>5 else '', int(fields[2],16), b-a)
                elif line.startswith('Rss:') and current in wanted:
                    if current in seen:
                        return None
                    seen.add(current)
                    total += int(line.split()[1])*1024
            return total if seen == wanted else None
        except (OSError, ValueError):
            return None

    def close(self):
        for _,_,mapping,*_ in self.segments:
            mapping.close()
        self.segments = []


class ClockCache:
    """Fixed payload and fixed dense metadata, no per-row Python dictionary.

    One 1 GiB pinned slab/rank, including unused tail bytes; <=4 GiB TP4.
    gather_into copies each row before eviction can reuse its slot, so duplicate
    IDs and batches larger than the cache remain exact. Single caller per rank.
    """
    def __init__(self, store, buffer):
        self.store, self.buffer = store, memoryview(buffer).cast('B')
        self.capacity = len(self.buffer)//store.width
        if not 0 < self.capacity or len(self.buffer) > CACHE_PER_RANK:
            raise ValueError('cache must contain a row and be <=1 GiB/rank')
        self.row2slot = array('i', [-1])*(store.end-store.start)
        self.slot2row = array('q', [-1])*self.capacity
        self.reference = bytearray(self.capacity)
        self.epoch = array('q', [0])*self.capacity
        if self.row2slot.itemsize != 4 or self.slot2row.itemsize != 8:
            raise RuntimeError('unsupported metadata integer width')
        self.hand = self.hits = self.misses = self.evictions = 0

    def _row(self, row):
        local = row-self.store.start
        slot = self.row2slot[local]
        if slot >= 0:
            self.hits += 1
        else:
            self.misses += 1
            # Read first: failure never publishes a partially filled cache slot.
            raw = self.store.read_row(row)
            while self.reference[self.hand]:
                self.reference[self.hand] = 0
                self.hand = (self.hand+1)%self.capacity
            slot = self.hand
            old = self.slot2row[slot]
            if old >= 0:
                self.row2slot[old-self.store.start] = -1
                self.evictions += 1
            at = slot*self.store.width
            self.buffer[at:at+self.store.width] = raw
            self.row2slot[local], self.slot2row[slot] = slot, row
            self.epoch[slot] += 1
            self.hand = (slot+1)%self.capacity
        self.reference[slot] = 1
        at = slot*self.store.width
        return self.buffer[at:at+self.store.width]

    def gather_into(self, ids, output):
        out = memoryview(output).cast('B')
        width = self.store.width
        if len(out) != len(ids)*width or len(out) > STAGING_LIMIT:
            raise ValueError('gather output size exceeds bounded stage or wrong shape')
        # Validate the whole request before mutating output/cache.
        if any(type(i) is not int or not 0 <= i < self.store.rows for i in ids):
            raise IndexError('invalid global PLE ID')
        zero = bytes(width)
        for n, row in enumerate(ids):
            out[n*width:(n+1)*width] = (self._row(row) if self.store.start <= row < self.store.end else zero)

    def close(self):
        self.buffer.release()
        self.store.close()


def host_ngram_ids(tokens, qsl, context, multipliers, sizes, offsets, eos, heads_per_ngram):
    """Independent CPU mirror of torch int64 wrapping multiply/XOR/remainder.

    Used in tests, not an alternative runtime hash. Runtime prefetch computes
    IDs using the original model method on the actual current-step inputs.
    An EOS resets following tokens, not the history of the EOS token itself.
    """
    n = len(multipliers)
    if (not qsl or qsl[0] != 0 or qsl[-1] != len(tokens) or
            any(a>b for a,b in zip(qsl,qsl[1:])) or
            len(context) != len(qsl)-1 or any(len(c)!=n-1 for c in context) or
            len(sizes) != (n-1)*heads_per_ngram or len(offsets)!=len(sizes)):
        raise ValueError('invalid ngram layout')
    def signed(x):
        return (x+(1<<63))%(1<<64)-(1<<63)
    result = []
    for req,(lo,hi) in enumerate(zip(qsl,qsl[1:])):
        seq = list(context[req])+list(tokens[lo:hi])
        previous = -1
        for pos,tok in enumerate(seq):
            if pos >= n-1:
                terms = [signed((seq[pos-k] if pos-previous-1 >= k else eos)*multipliers[k]) for k in range(n)]
                values = []
                mixed = terms[0]
                for order in range(2,n+1):
                    mixed ^= terms[order-1]
                    for head in range((order-2)*heads_per_ngram,(order-1)*heads_per_ngram):
                        values.append(mixed%sizes[head]+offsets[head])
                result.append(values)
            if tok == eos:
                previous = pos
    return result


def bind_module(module, folder, prefix):
    """Runtime only: allocate bounded pins, never allocate the full PLE tensor."""
    import torch
    from vllm import screen1b_guard as guard
    embedding = module.ngram_embedding
    if hasattr(embedding, '_screen1b_cache'):
        return
    if embedding.tp_size != 4 or embedding.etp_data_parallel_size != 1:
        raise RuntimeError('mmap PLE is qualified for TP4, DP1 geometry only')
    contract = json.loads(Path('/screen-package/memory-contract.json').read_text())
    if (embedding.org_vocab_size != contract['ple_rows'] or
            embedding.embedding_dim != contract['ple_row_bytes'] or
            CACHE_PER_RANK != contract['ple_cache_bytes_per_rank'] or
            embedding._screen1b_step_capacity != contract['max_total_tokens'] or
            module.ngram_heads != contract['ngram_heads']):
        raise RuntimeError('runtime PLE geometry differs from sealed memory contract')
    first = embedding.shard_indices.org_vocab_start_index
    end = embedding.shard_indices.org_vocab_end_index
    store = RowStore(folder, prefix, embedding.org_vocab_size, embedding.embedding_dim,
                     module.split_ngram_parts, first, end)
    meta = metadata_bytes(end-first, CACHE_PER_RANK, embedding.embedding_dim)
    try:
        with guard.admission('PLE_cache_and_metadata', CACHE_PER_RANK+meta):
            slab = torch.empty(CACHE_PER_RANK, dtype=torch.uint8, device='cpu', pin_memory=True)
            if not slab.is_pinned():
                raise RuntimeError('PLE cache must be pinned')
            cache = ClockCache(store, slab.numpy())
        embedding._screen1b_cache_slab = slab
        embedding._screen1b_cache = cache
        guard.receipt('PLE_mmap_bound', mapped_payload_bytes=(end-first)*store.width,
                      pinned_cache_bytes=CACHE_PER_RANK, metadata_bytes=meta,
                      index_sha256=store.index_sha256, header_sha256=store.header_sha256)
    except BaseException:
        store.close()
        raise


def allocate_step_buffers(embedding, tokens, heads):
    import torch
    from vllm import screen1b_guard as guard
    shape = (tokens, heads, embedding.embedding_dim)
    count = tokens*heads*embedding.embedding_dim
    if tokens <= 0 or count*2 > STAGING_LIMIT:
        raise RuntimeError('PLE step buffers exceed staging bound')
    with guard.admission('PLE_step_buffers', count):
        embedding._screen1b_step_host = torch.zeros(shape, dtype=torch.uint8, device='cpu', pin_memory=True)
        embedding._screen1b_step_device = torch.zeros(shape, dtype=torch.uint8, device=embedding.weight.device)
    embedding._screen1b_step_capacity = tokens


def pre_forward(model_inputs):
    """Prepare current-step rows before graph replay, using the ORIGINAL hash.

    Synchronous first implementation: issued before attention, but misses ARE
    on the critical path. Static device storage keeps addresses stable across
    graph replay. Every step overwrites every used row including TP zeros;
    no token history, rejected draft, or response is cached. Only model bytes.
    """
    import torch
    from vllm import screen1b_guard as guard
    for module in guard._tables.values():
        embedding = module.ngram_embedding
        ids = module.compute_ngram_ids(model_inputs['input_ids'],
                                      model_inputs['query_start_loc'],
                                      model_inputs['ngram_context'])
        count = ids.shape[0]
        if count > embedding._screen1b_step_capacity:
            raise RuntimeError('PLE step exceeds fixed buffers')
        # This D2H also waits for the preceding step to finish reading buffers.
        flat = ids.to(device='cpu').reshape(-1).tolist()
        host = embedding._screen1b_step_host[:count]
        embedding._screen1b_cache.gather_into(flat, host.numpy())
        embedding._screen1b_step_device[:count].copy_(host, non_blocking=False)


def gather_prepared(embedding, ids):
    # Returning a clone matters: vocab_parallel_embedding masks in-place and
    # all_reduce may mutate its input. Never let either alter the static slab.
    if ids.shape[0] > embedding._screen1b_step_capacity:
        raise RuntimeError('PLE forward exceeds fixed buffers')
    return embedding._screen1b_step_device[:ids.shape[0]].clone().view(embedding.weight.dtype)
