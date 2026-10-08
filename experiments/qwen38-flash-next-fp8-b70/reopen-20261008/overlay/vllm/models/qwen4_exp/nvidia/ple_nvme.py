# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM project
"""B70 0013: serve the INT8 PLE n-gram table from NVMe (host side).

Everything here is host-only (numpy / os / threads; numba when present) and
imports nothing from vLLM, so the tests load it standalone. The model-side
wiring lives in ngram_embedding.py (``Qwen4ExpNGramEmbedding.b70_nvme_*``),
model_state.py (``b70_pre_forward``) and the V2 model runner (the call just
before "Run model", real batches only).

Per TP rank, per step:
  1. ``host_ngram_ids``: the n-gram ids of the real tokens, bit-identical to
     ``Qwen4ExpNGramEmbedding.compute_ngram_ids`` (same integer ops in numpy;
     the products never exceed 2^63 for in-vocab tokens, and numpy/torch wrap
     and take remainders identically even when they would).
  2. ``PleNvmeServer.resolve``: own-range rows -> slots in a pinned row cache
     (CLOCK, this step and the previous step protected); the misses of the
     step are deduplicated and read from the table file with O_DIRECT.
  3. The caller H2D-copies the int64 slot ids and launches the existing
     pinned-lookup Triton kernel over the cache's UVA view (slot -1 = row not
     owned by this rank, or a padding token: nothing stored, stays zero).

Env contract (read in ngram_embedding.py, documented here):
  B70_PLE_INT8_NVME=1               enable (requires B70_PLE_INT8=1)
  B70_PLE_INT8_NVME_PATH            table file (default B70_PLE_INT8_PATH)
  B70_PLE_INT8_NVME_CACHE_GIB       row cache, TOTAL over the TP ranks (default 8)
  B70_PLE_INT8_NVME_IO_THREADS      reader threads per rank (default 16)
  B70_PLE_INT8_NVME_SYNC_ONLY=1     hook + host hash + cache bookkeeping, rows
                                    served from the in-RAM pinned table
  B70_PLE_INT8_NVME_STATS=1         periodic per-rank stats line
  B70_PLE_INT8_NVME_STATS_S         stats interval, seconds (default 60)
  B70_PLE_INT8_NVME_BOOT_SAMPLE     own rows read at boot for the scale check
                                    (default 65536)

0013b (v2), both default to v1 behaviour:
  B70_PLE_INT8_NVME_READER=py|native|uring
                                    py (default): v1's Python thread pool
                                    (os.preadv per read). native: a C pthread
                                    pool that pread()s a whole batch with the
                                    GIL released. uring: one io_uring per
                                    reader (raw syscalls; liburing is not in
                                    the image), IO_THREADS reads in flight,
                                    no threads. Both native readers are built
                                    from the C source below with gcc at first
                                    use (B70_PLE_INT8_NVME_NATIVE_DIR, default
                                    $TMPDIR/b70-ple-nvme) or loaded from
                                    B70_PLE_INT8_NVME_NATIVE_LIB. A failed or
                                    short native read goes through v1's retry
                                    path (3 retries, then raise).
  B70_PLE_INT8_NVME_LOOKAHEAD=0|1   prefill lookahead (A-design §3.3): after
                                    step k's gather is launched, a background
                                    thread hashes the next prefill chunk of
                                    every prefilling request (tokens from
                                    req_states.all_token_ids), drops the rows
                                    the cache already holds and reads the
                                    rest into its own buffers. Step k+1's hook
                                    takes them (waiting for, or cancelling,
                                    an unfinished job) and uses them for its
                                    misses before any sync read; nothing the
                                    lookahead does is needed for correctness.
  B70_PLE_INT8_NVME_LOOKAHEAD_TOKENS
                                    tokens predicted per step (default: the
                                    scheduler's max_num_batched_tokens)
"""

from __future__ import annotations

import ctypes
import hashlib
import logging
import mmap
import os
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

logger = logging.getLogger("vllm.models.qwen4_exp.nvidia.ple_nvme")

PAGE = 4096
# One row read is at most two pages (a 164-byte row crosses at most one
# page boundary); every bounce slot is this large.
READ_SLOT = 2 * PAGE
# Retry backoff for a failed or short read, seconds (then raise).
RETRY_BACKOFF_S = (0.001, 0.010, 0.100)

try:  # numba makes the CLOCK sweep cheap; the fallback is a Python loop.
    import numba as _numba

    _HAVE_NUMBA = True
except Exception:  # pragma: no cover - numba is present in the image
    _numba = None
    _HAVE_NUMBA = False


# --------------------------------------------------------------------------
# Host n-gram hash
# --------------------------------------------------------------------------


def host_ngram_ids(
    tokens: np.ndarray,
    query_start_loc: np.ndarray,
    ngram_context: np.ndarray,
    *,
    multipliers: np.ndarray,
    sizes: np.ndarray,
    offsets: np.ndarray,
    eos_token_id: int,
    heads_per_ngram: int,
    heads: np.ndarray | None = None,
) -> np.ndarray:
    """N-gram ids [T, H] of the real tokens (host, bit-exact with the device).

    ``tokens`` [T] are the real (unpadded) tokens of the batch, laid out by
    ``query_start_loc`` [R + 1] (qsl[0] == 0, qsl[R] == T); ``ngram_context``
    [>= R, ngram_size - 1] the tokens before each request's first token (EOS
    where there are none). Mirrors ``compute_ngram_ids``' pure-torch path: a
    shifted token is replaced by EOS when it lies before the start of the
    token's EOS segment. ``heads`` (optional) selects which of the
    (ngram_size - 1) * heads_per_ngram heads to return, in that order.
    """
    tokens = np.asarray(tokens).reshape(-1).astype(np.int64, copy=False)
    qsl = np.asarray(query_start_loc).astype(np.int64, copy=False)
    mult = np.asarray(multipliers, dtype=np.int64)
    sizes = np.asarray(sizes, dtype=np.int64)
    offsets = np.asarray(offsets, dtype=np.int64)
    ngram_size = int(mult.shape[0])
    ctx_len = ngram_size - 1
    num_heads = ctx_len * heads_per_ngram
    if heads is None:
        heads = np.arange(num_heads)
    heads = np.asarray(heads, dtype=np.int64)
    num_tokens = tokens.shape[0]
    num_reqs = qsl.shape[0] - 1
    if num_tokens == 0 or num_reqs <= 0:
        return np.empty((num_tokens, heads.shape[0]), dtype=np.int64)
    if qsl[0] != 0 or qsl[-1] != num_tokens:
        raise ValueError(
            f"query_start_loc [{qsl[0]}..{qsl[-1]}] does not cover {num_tokens} tokens"
        )
    lens = np.diff(qsl)
    if (lens < 0).any():
        raise ValueError("query_start_loc must be non-decreasing")
    ctx = np.asarray(ngram_context)[:num_reqs].astype(np.int64, copy=False)
    # Flat layout: each request's ctx_len context tokens, then its tokens.
    req_start = qsl[:-1] + ctx_len * np.arange(num_reqs, dtype=np.int64)
    total = num_tokens + ctx_len * num_reqs
    seq = np.empty(total, dtype=np.int64)
    req_of_tok = np.repeat(np.arange(num_reqs, dtype=np.int64), lens)
    tok_flat = np.arange(num_tokens, dtype=np.int64) + ctx_len * (req_of_tok + 1)
    seq[tok_flat] = tokens
    seq[(req_start[:, None] + np.arange(ctx_len, dtype=np.int64)).reshape(-1)] = (
        ctx.reshape(-1)
    )
    # Previous EOS strictly before each position, clamped to "just before the
    # request's context" (the device path's -1 at the start of the row).
    index = np.arange(total, dtype=np.int64)
    eos_at = np.where(seq == eos_token_id, index, -1)
    inclusive = np.maximum.accumulate(eos_at)
    previous = np.empty(total, dtype=np.int64)
    previous[0] = -1
    previous[1:] = inclusive[:-1]
    previous = np.maximum(previous, np.repeat(req_start - 1, lens + ctx_len))
    position_in_segment = (index - previous - 1)[tok_flat]
    terms = []
    for shift in range(ngram_size):
        if shift == 0:
            shifted = seq[tok_flat]
        else:
            source = np.maximum(tok_flat - shift, 0)
            shifted = np.where(
                position_in_segment >= shift, seq[source], np.int64(eos_token_id)
            )
        terms.append(shifted * mult[shift])
    out = np.empty((num_tokens, heads.shape[0]), dtype=np.int64)
    mixed_by_order: dict[int, np.ndarray] = {}
    for column, head in enumerate(heads.tolist()):
        order = head // heads_per_ngram + 2
        mixed = mixed_by_order.get(order)
        if mixed is None:
            mixed = terms[0]
            for index_ in range(1, order):
                mixed = np.bitwise_xor(mixed, terms[index_])
            mixed_by_order[order] = mixed
        out[:, column] = np.remainder(mixed, sizes[head]) + offsets[head]
    return out


def owned_heads(sizes: np.ndarray, offsets: np.ndarray, start: int, end: int) -> np.ndarray:
    """Heads whose global rows intersect [start, end)."""
    sizes = np.asarray(sizes, dtype=np.int64)
    offsets = np.asarray(offsets, dtype=np.int64)
    hit = (offsets < end) & (offsets + sizes > start)
    return np.nonzero(hit)[0].astype(np.int64)


# --------------------------------------------------------------------------
# Native batch readers (0013b)
# --------------------------------------------------------------------------

READERS = ("py", "native", "uring")

_NATIVE_SRC = r"""/* B70 0013b: batched O_DIRECT row reads for the NVMe PLE table.
 *
 * Two readers, both called through ctypes (which drops the GIL for the whole
 * call), both filling res[i] with the byte count of read i (or -errno) and
 * lat_ns[i] with its latency:
 *   - pool:  a persistent pthread pool; the caller and up to nthreads-1
 *            helpers pull read indices from an atomic counter and pread();
 *   - uring: one io_uring (raw syscalls, no liburing) per reader; up to qd
 *            IORING_OP_READs in flight, refilled as completions arrive.
 * Neither retries; the Python side retries failed or short reads.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <linux/io_uring.h>
#include <pthread.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

static inline int64_t now_ns(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (int64_t)t.tv_sec * 1000000000LL + t.tv_nsec;
}

typedef struct {
    int fd;
    int64_t n;
    const int64_t *off;
    const int32_t *len;
    uint8_t *bounce;
    int64_t slot;
    int32_t *res;
    int64_t *lat;
} ple_job;

static void run_job(ple_job *job, int64_t *next) {
    for (;;) {
        int64_t i = __atomic_fetch_add(next, 1, __ATOMIC_RELAXED);
        if (i >= job->n) return;
        int64_t t0 = now_ns();
        ssize_t r = pread(job->fd, job->bounce + i * job->slot, (size_t)job->len[i],
                          (off_t)job->off[i]);
        job->res[i] = r < 0 ? -errno : (int32_t)r;
        job->lat[i] = now_ns() - t0;
    }
}

/* ------------------------------------------------------------------ pool */

typedef struct ple_pool ple_pool;
typedef struct {
    ple_pool *pool;
    int id;
    pthread_cond_t cv;
    uint64_t gen;
} ple_worker;

struct ple_pool {
    int nhelpers;
    pthread_t *threads;
    ple_worker *workers;
    pthread_mutex_t mu;
    pthread_cond_t done_cv;
    ple_job job;
    int64_t next;
    int active;
    int stop;
};

static void *worker_main(void *arg) {
    ple_worker *w = (ple_worker *)arg;
    ple_pool *p = w->pool;
    uint64_t seen = 0;
    pthread_mutex_lock(&p->mu);
    for (;;) {
        while (!p->stop && w->gen == seen) pthread_cond_wait(&w->cv, &p->mu);
        if (p->stop) break;
        seen = w->gen;
        pthread_mutex_unlock(&p->mu);
        run_job(&p->job, &p->next);
        pthread_mutex_lock(&p->mu);
        if (--p->active == 0) pthread_cond_signal(&p->done_cv);
    }
    pthread_mutex_unlock(&p->mu);
    return NULL;
}

void *ple_pool_create(int nthreads) {
    ple_pool *p = calloc(1, sizeof(*p));
    if (!p) return NULL;
    p->nhelpers = nthreads > 1 ? nthreads - 1 : 0;
    pthread_mutex_init(&p->mu, NULL);
    pthread_cond_init(&p->done_cv, NULL);
    p->threads = calloc(p->nhelpers + 1, sizeof(pthread_t));
    p->workers = calloc(p->nhelpers + 1, sizeof(ple_worker));
    for (int i = 0; i < p->nhelpers; i++) {
        p->workers[i].pool = p;
        p->workers[i].id = i;
        pthread_cond_init(&p->workers[i].cv, NULL);
        if (pthread_create(&p->threads[i], NULL, worker_main, &p->workers[i]) != 0) {
            p->nhelpers = i;
            break;
        }
    }
    return p;
}

void ple_pool_destroy(void *handle) {
    ple_pool *p = (ple_pool *)handle;
    if (!p) return;
    pthread_mutex_lock(&p->mu);
    p->stop = 1;
    for (int i = 0; i < p->nhelpers; i++) pthread_cond_signal(&p->workers[i].cv);
    pthread_mutex_unlock(&p->mu);
    for (int i = 0; i < p->nhelpers; i++) pthread_join(p->threads[i], NULL);
    free(p->threads);
    free(p->workers);
    free(p);
}

/* One call = one batch; not reentrant (one pool per reader, one caller). */
int ple_pool_read(void *handle, int fd, int64_t n, const int64_t *off,
                  const int32_t *len, uint8_t *bounce, int64_t slot, int32_t *res,
                  int64_t *lat) {
    ple_pool *p = (ple_pool *)handle;
    if (n <= 0) return 0;
    int helpers = p->nhelpers;
    if ((int64_t)helpers > n - 1) helpers = (int)(n - 1);
    pthread_mutex_lock(&p->mu);
    p->job = (ple_job){fd, n, off, len, bounce, slot, res, lat};
    p->next = 0;
    p->active = helpers;
    for (int i = 0; i < helpers; i++) {
        p->workers[i].gen++;
        pthread_cond_signal(&p->workers[i].cv);
    }
    pthread_mutex_unlock(&p->mu);
    ple_job job = p->job;
    run_job(&job, &p->next);
    pthread_mutex_lock(&p->mu);
    while (p->active > 0) pthread_cond_wait(&p->done_cv, &p->mu);
    pthread_mutex_unlock(&p->mu);
    return 0;
}

/* ----------------------------------------------------------------- uring */

typedef struct {
    int ring_fd;
    unsigned sq_entries, cq_entries;
    unsigned *sq_head, *sq_tail, *sq_mask, *sq_array;
    unsigned *cq_head, *cq_tail, *cq_mask;
    struct io_uring_sqe *sqes;
    struct io_uring_cqe *cqes;
    void *sq_ptr, *cq_ptr;
    size_t sq_sz, cq_sz, sqes_sz;
} ple_ring;

/* Returns a handle, or NULL with *err = errno. */
void *ple_uring_create(unsigned entries, int *err) {
    struct io_uring_params params;
    memset(&params, 0, sizeof(params));
    int fd = (int)syscall(__NR_io_uring_setup, entries, &params);
    if (fd < 0) {
        *err = errno;
        return NULL;
    }
    ple_ring *r = calloc(1, sizeof(*r));
    r->ring_fd = fd;
    r->sq_entries = params.sq_entries;
    r->cq_entries = params.cq_entries;
    r->sq_sz = params.sq_off.array + params.sq_entries * sizeof(unsigned);
    r->cq_sz = params.cq_off.cqes + params.cq_entries * sizeof(struct io_uring_cqe);
    int single = (params.features & IORING_FEAT_SINGLE_MMAP) != 0;
    if (single) {
        if (r->cq_sz > r->sq_sz) r->sq_sz = r->cq_sz;
        r->cq_sz = r->sq_sz;
    }
    r->sq_ptr = mmap(NULL, r->sq_sz, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_POPULATE, fd,
                     IORING_OFF_SQ_RING);
    if (r->sq_ptr == MAP_FAILED) goto fail;
    if (single) {
        r->cq_ptr = r->sq_ptr;
    } else {
        r->cq_ptr = mmap(NULL, r->cq_sz, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_POPULATE,
                         fd, IORING_OFF_CQ_RING);
        if (r->cq_ptr == MAP_FAILED) goto fail;
    }
    r->sqes_sz = params.sq_entries * sizeof(struct io_uring_sqe);
    r->sqes = mmap(NULL, r->sqes_sz, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_POPULATE, fd,
                   IORING_OFF_SQES);
    if (r->sqes == MAP_FAILED) goto fail;
    uint8_t *sq = r->sq_ptr, *cq = r->cq_ptr;
    r->sq_head = (unsigned *)(sq + params.sq_off.head);
    r->sq_tail = (unsigned *)(sq + params.sq_off.tail);
    r->sq_mask = (unsigned *)(sq + params.sq_off.ring_mask);
    r->sq_array = (unsigned *)(sq + params.sq_off.array);
    r->cq_head = (unsigned *)(cq + params.cq_off.head);
    r->cq_tail = (unsigned *)(cq + params.cq_off.tail);
    r->cq_mask = (unsigned *)(cq + params.cq_off.ring_mask);
    r->cqes = (struct io_uring_cqe *)(cq + params.cq_off.cqes);
    return r;
fail:
    *err = errno;
    close(fd);
    free(r);
    return NULL;
}

void ple_uring_destroy(void *handle) {
    ple_ring *r = (ple_ring *)handle;
    if (!r) return;
    munmap(r->sqes, r->sqes_sz);
    if (r->cq_ptr != r->sq_ptr) munmap(r->cq_ptr, r->cq_sz);
    munmap(r->sq_ptr, r->sq_sz);
    close(r->ring_fd);
    free(r);
}

/* 0 on success (per-read results in res), -errno if the ring itself failed. */
int ple_uring_read(void *handle, int fd, int64_t n, const int64_t *off,
                   const int32_t *len, uint8_t *bounce, int64_t slot, int qd,
                   int32_t *res, int64_t *lat) {
    ple_ring *r = (ple_ring *)handle;
    if (qd < 1) qd = 1;
    if ((unsigned)qd > r->sq_entries) qd = (int)r->sq_entries;
    int64_t submitted = 0, completed = 0;
    int inflight = 0;
    unsigned pending = 0; /* queued in the SQ, not yet taken by the kernel */
    unsigned mask = *r->sq_mask, cmask = *r->cq_mask;
    while (completed < n) {
        unsigned tail = *r->sq_tail;
        unsigned head = __atomic_load_n(r->sq_head, __ATOMIC_ACQUIRE);
        while (submitted < n && inflight < qd && tail - head < r->sq_entries) {
            unsigned idx = tail & mask;
            struct io_uring_sqe *sqe = &r->sqes[idx];
            memset(sqe, 0, sizeof(*sqe));
            sqe->opcode = IORING_OP_READ;
            sqe->fd = fd;
            sqe->addr = (uint64_t)(uintptr_t)(bounce + submitted * slot);
            sqe->len = (uint32_t)len[submitted];
            sqe->off = (uint64_t)off[submitted];
            sqe->user_data = (uint64_t)submitted;
            r->sq_array[idx] = idx;
            lat[submitted] = now_ns();
            tail++;
            submitted++;
            inflight++;
            pending++;
        }
        __atomic_store_n(r->sq_tail, tail, __ATOMIC_RELEASE);
        int ret = (int)syscall(__NR_io_uring_enter, r->ring_fd, pending, 1,
                               IORING_ENTER_GETEVENTS, NULL, 0);
        if (ret < 0) {
            if (errno == EINTR || errno == EAGAIN || errno == EBUSY) continue;
            return -errno;
        }
        pending -= (unsigned)ret > pending ? pending : (unsigned)ret;
        unsigned chead = *r->cq_head;
        unsigned ctail = __atomic_load_n(r->cq_tail, __ATOMIC_ACQUIRE);
        int64_t t = now_ns();
        while (chead != ctail) {
            struct io_uring_cqe *cqe = &r->cqes[chead & cmask];
            int64_t i = (int64_t)cqe->user_data;
            res[i] = cqe->res;
            lat[i] = t - lat[i];
            chead++;
            completed++;
            inflight--;
        }
        __atomic_store_n(r->cq_head, chead, __ATOMIC_RELEASE);
    }
    return 0;
}
"""

_NATIVE_LOCK = threading.Lock()
_NATIVE_LIB: ctypes.CDLL | None = None


def _native_lib() -> ctypes.CDLL:
    """Build (once per source hash) and load the C readers.

    ctypes drops the GIL for the whole foreign call, so one call reads a whole
    batch without touching Python. Several TP ranks may build at once: each
    compiles to a private temporary and renames it into place.
    """
    global _NATIVE_LIB
    with _NATIVE_LOCK:
        if _NATIVE_LIB is not None:
            return _NATIVE_LIB
        path = os.environ.get("B70_PLE_INT8_NVME_NATIVE_LIB")
        if not path:
            digest = hashlib.sha256(_NATIVE_SRC.encode()).hexdigest()[:16]
            folder = os.environ.get("B70_PLE_INT8_NVME_NATIVE_DIR") or os.path.join(
                tempfile.gettempdir(), "b70-ple-nvme"
            )
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, f"ple_nvme_reader-{digest}.so")
            if not os.path.exists(path):
                tmp = f"{path}.{os.getpid()}.{threading.get_ident()}"
                src = tmp + ".c"
                with open(src, "w") as handle:
                    handle.write(_NATIVE_SRC)
                try:
                    subprocess.run(
                        [os.environ.get("CC", "gcc"), "-O2", "-shared", "-fPIC",
                         "-pthread", "-o", tmp, src],
                        check=True, capture_output=True, text=True,
                    )
                except (OSError, subprocess.CalledProcessError) as exc:
                    detail = getattr(exc, "stderr", "") or str(exc)
                    raise RuntimeError(
                        f"PLE NVMe native reader: cannot build {path}: {detail}"
                    ) from exc
                finally:
                    try:
                        os.unlink(src)
                    except OSError:
                        pass
                os.replace(tmp, path)
        lib = ctypes.CDLL(path)
        vp, i64, i32 = ctypes.c_void_p, ctypes.c_int64, ctypes.c_int
        lib.ple_pool_create.argtypes = [i32]
        lib.ple_pool_create.restype = vp
        lib.ple_pool_destroy.argtypes = [vp]
        lib.ple_pool_destroy.restype = None
        lib.ple_pool_read.argtypes = [vp, i32, i64, vp, vp, vp, i64, vp, vp]
        lib.ple_pool_read.restype = i32
        lib.ple_uring_create.argtypes = [ctypes.c_uint, ctypes.POINTER(ctypes.c_int)]
        lib.ple_uring_create.restype = vp
        lib.ple_uring_destroy.argtypes = [vp]
        lib.ple_uring_destroy.restype = None
        lib.ple_uring_read.argtypes = [vp, i32, i64, vp, vp, vp, i64, i32, vp, vp]
        lib.ple_uring_read.restype = i32
        _NATIVE_LIB = lib
        logger.info("PLE NVMe native reader loaded from %s", path)
        return lib


# --------------------------------------------------------------------------
# O_DIRECT row reader
# --------------------------------------------------------------------------


def safetensors_tensor_location(path: str, name: str) -> tuple[int, list[int], str]:
    """(absolute byte offset, shape, dtype) of one tensor of a .safetensors file."""
    import json

    with open(path, "rb") as handle:
        header_len = int.from_bytes(handle.read(8), "little")
        header = json.loads(handle.read(header_len))
    info = header[name]
    begin = int(info["data_offsets"][0])
    return 8 + header_len + begin, [int(v) for v in info["shape"]], str(info["dtype"])


class PleNvmeRowStore:
    """Read 164-byte table rows from the file with O_DIRECT (one fd per rank).

    Row g is at ``data_start + row_bytes * g``. Each row is one 4 KiB read,
    or 8 KiB when it crosses a page boundary. Reads go into page-aligned
    anonymous-mmap bounce slots (8 KiB each) and are split into contiguous
    batches over ``io_threads`` workers, each looping ``os.preadv`` (which
    releases the GIL). A failed or short read is retried 3 times (1/10/100
    ms), then raises; nothing is ever zero-filled.

    ``reader`` (0013b): "py" is the above; "native" replaces the Python
    workers by a C pthread pool (``io_threads`` threads, one ctypes call per
    batch, GIL released); "uring" submits the batch through one io_uring with
    ``queue_depth`` (default ``io_threads``) reads in flight. A native read
    that fails or comes back short goes through the same Python retry path.
    One store is used by one thread at a time.
    """

    def __init__(
        self,
        path: str,
        data_start: int,
        row_bytes: int,
        num_rows: int,
        *,
        io_threads: int = 16,
        max_batch_rows: int = 8192,
        direct: bool = True,
        reader: str = "py",
        queue_depth: int | None = None,
    ) -> None:
        if reader not in READERS:
            raise ValueError(f"PLE NVMe reader {reader!r} not in {READERS}")
        self.reader = reader
        self.path = path
        self.data_start = int(data_start)
        self.row_bytes = int(row_bytes)
        self.num_rows = int(num_rows)
        self.io_threads = max(1, int(io_threads))
        self.max_batch_rows = max(1, int(max_batch_rows))
        flags = os.O_RDONLY | (os.O_DIRECT if direct else 0)
        self.fd = os.open(path, flags)
        self.direct = direct
        self.file_size = os.fstat(self.fd).st_size
        end = self.data_start + self.row_bytes * self.num_rows
        if end > self.file_size:
            os.close(self.fd)
            raise ValueError(
                f"{path}: {self.num_rows} rows x {self.row_bytes} B from byte "
                f"{self.data_start} end at {end}, past the file ({self.file_size} B)"
            )
        self._bounce = mmap.mmap(-1, self.max_batch_rows * READ_SLOT)
        self._bounce_view = memoryview(self._bounce)
        self._bounce_np = np.frombuffer(self._bounce, dtype=np.uint8).reshape(
            self.max_batch_rows, READ_SLOT
        )
        self._pool = (
            ThreadPoolExecutor(self.io_threads, thread_name_prefix="ple-nvme")
            if self.io_threads > 1 and reader == "py"
            else None
        )
        self._preadv = os.preadv  # tests swap this for fault injection
        self._lat = np.zeros(self.max_batch_rows, dtype=np.float64)
        self._row_offsets = np.arange(self.row_bytes, dtype=np.int64)
        self._lib = None
        self._handle = None
        self.queue_depth = max(1, int(queue_depth or self.io_threads))
        # fd the native call reads through (tests point it elsewhere to make
        # every native read fail and exercise the Python retry path).
        self._native_fd = self.fd
        self.native_retries = 0
        if reader != "py":
            try:
                lib = _native_lib()
                if reader == "native":
                    handle = lib.ple_pool_create(self.io_threads)
                    if not handle:
                        raise RuntimeError("PLE NVMe native reader: pool create failed")
                else:
                    entries = 8
                    while entries < self.queue_depth:
                        entries *= 2
                    err = ctypes.c_int(0)
                    handle = lib.ple_uring_create(entries, ctypes.byref(err))
                    if not handle:
                        raise OSError(err.value, f"io_uring_setup({entries}) failed: "
                                                 f"{os.strerror(err.value)}")
            except BaseException:
                os.close(self.fd)
                self.fd = -1
                raise
            self._lib = lib
            self._handle = handle
            self._res = np.zeros(self.max_batch_rows, dtype=np.int32)
            self._lat_ns = np.zeros(self.max_batch_rows, dtype=np.int64)
            self._bounce_addr = self._bounce_np.ctypes.data

    def close(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=True)
            self._pool = None
        if self._handle is not None:
            if self.reader == "native":
                self._lib.ple_pool_destroy(self._handle)
            else:
                self._lib.ple_uring_destroy(self._handle)
            self._handle = None
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def _read_one(self, slot: int, row: int, offset: int, length: int, need: int) -> None:
        view = self._bounce_view[slot * READ_SLOT : slot * READ_SLOT + length]
        last_error: str = ""
        for attempt in range(len(RETRY_BACKOFF_S) + 1):
            try:
                got = self._preadv(self.fd, [view], offset)
                if got >= need:
                    return
                last_error = f"short read {got} < {need} B"
            except OSError as exc:
                last_error = f"errno {exc.errno} ({exc.strerror})"
            if attempt < len(RETRY_BACKOFF_S):
                time.sleep(RETRY_BACKOFF_S[attempt])
        raise RuntimeError(
            f"PLE NVMe read failed after {len(RETRY_BACKOFF_S)} retries: row {row}, "
            f"file offset {offset}, length {length}: {last_error} ({self.path})"
        )

    def _read_range(
        self, lo: int, hi: int, rows: np.ndarray, offsets: np.ndarray,
        lengths: np.ndarray, needs: np.ndarray,
    ) -> None:
        lat = self._lat
        for i in range(lo, hi):
            t0 = time.perf_counter()
            self._read_one(i, int(rows[i]), int(offsets[i]), int(lengths[i]), int(needs[i]))
            lat[i] = time.perf_counter() - t0

    def _read_native(self, count: int, rows: np.ndarray, offsets: np.ndarray,
                     lengths: np.ndarray, needs: np.ndarray) -> None:
        off = np.ascontiguousarray(offsets, dtype=np.int64)
        length = np.ascontiguousarray(lengths, dtype=np.int32)
        res = self._res[:count]
        lat_ns = self._lat_ns[:count]
        if self.reader == "native":
            rc = self._lib.ple_pool_read(
                self._handle, self._native_fd, count, off.ctypes.data,
                length.ctypes.data, self._bounce_addr, READ_SLOT,
                res.ctypes.data, lat_ns.ctypes.data,
            )
        else:
            rc = self._lib.ple_uring_read(
                self._handle, self._native_fd, count, off.ctypes.data,
                length.ctypes.data, self._bounce_addr, READ_SLOT, self.queue_depth,
                res.ctypes.data, lat_ns.ctypes.data,
            )
        if rc < 0:
            # The ring itself failed (not one read): nothing is trusted.
            raise RuntimeError(
                f"PLE NVMe {self.reader} reader failed: errno {-rc} "
                f"({os.strerror(-rc)}) ({self.path})"
            )
        self._lat[:count] = lat_ns * 1e-9
        bad = np.nonzero(res < needs)[0]
        for i in bad.tolist():
            self.native_retries += 1
            t0 = time.perf_counter()
            self._read_one(i, int(rows[i]), int(offsets[i]), int(lengths[i]), int(needs[i]))
            self._lat[i] += time.perf_counter() - t0

    def read_rows(self, rows: np.ndarray, out: np.ndarray | None = None,
                  latencies: list | None = None) -> np.ndarray:
        """Bytes of ``rows`` (global row ids) as uint8 [n, row_bytes]."""
        rows = np.asarray(rows, dtype=np.int64).reshape(-1)
        n = rows.shape[0]
        if out is None:
            out = np.empty((n, self.row_bytes), dtype=np.uint8)
        if n == 0:
            return out
        if rows.min() < 0 or rows.max() >= self.num_rows:
            raise IndexError(
                f"PLE NVMe row out of range [0, {self.num_rows}): "
                f"{int(rows.min())}..{int(rows.max())}"
            )
        for lo in range(0, n, self.max_batch_rows):
            hi = min(n, lo + self.max_batch_rows)
            part = rows[lo:hi]
            count = hi - lo
            byte = self.data_start + part * self.row_bytes
            page = byte & ~np.int64(PAGE - 1)
            inner = byte - page
            lengths = np.where(inner + self.row_bytes > PAGE, READ_SLOT, PAGE).astype(np.int64)
            needs = inner + self.row_bytes
            workers = min(self.io_threads, count)
            if self._handle is not None:
                self._read_native(count, part, page, lengths, needs)
            elif workers <= 1 or self._pool is None:
                self._read_range(0, count, part, page, lengths, needs)
            else:
                bounds = np.linspace(0, count, workers + 1).astype(np.int64)
                futures = [
                    self._pool.submit(
                        self._read_range, int(bounds[w]), int(bounds[w + 1]),
                        part, page, lengths, needs,
                    )
                    for w in range(workers)
                    if bounds[w + 1] > bounds[w]
                ]
                for future in futures:
                    future.result()
            if latencies is not None:
                latencies.append(self._lat[:count].copy())
            columns = inner[:, None] + self._row_offsets[None, :]
            out[lo:hi] = np.take_along_axis(self._bounce_np[:count], columns, axis=1)
        return out


# --------------------------------------------------------------------------
# Row cache
# --------------------------------------------------------------------------

_EPOCH_FREE = np.iinfo(np.int64).min // 2


def _clock_alloc_py(n, hand, ref, epoch, min_epoch, step, out):
    capacity = ref.shape[0]
    got = 0
    scanned = 0
    limit = 2 * capacity + n
    while got < n:
        if scanned >= limit:
            return got, hand
        slot = hand
        hand += 1
        if hand == capacity:
            hand = 0
        scanned += 1
        if epoch[slot] >= min_epoch:
            continue
        if ref[slot]:
            ref[slot] = 0
            continue
        out[got] = slot
        epoch[slot] = step
        ref[slot] = 1
        got += 1
    return got, hand


_clock_alloc = (
    _numba.njit(cache=False, nogil=True)(_clock_alloc_py) if _HAVE_NUMBA else _clock_alloc_py
)


class PleRowCache:
    """Per-rank row cache: pinned uint8 [C, row_bytes] slots + host maps.

    ``row2slot`` is a direct int32 map over the rank's own rows (-1 = absent).
    Eviction is CLOCK (second chance) with epoch protection: a slot touched in
    this step or the previous one is never evicted. A step that needs more
    slots than CLOCK can free raises RuntimeError before any map changes
    (the boot check makes that unreachable: capacity >= 2 x the largest step).
    ``slab`` is any uint8 [C, row_bytes] numpy array (the pinned tensor's
    ``.numpy()`` view in the engine); None = bookkeeping only (SYNC_ONLY).
    Slot ids are int64 everywhere (slot * row_bytes exceeds 2^31 once
    C > 13,094,412 rows).
    """

    def __init__(self, num_rows: int, capacity: int, row_bytes: int,
                 slab: np.ndarray | None = None) -> None:
        if capacity <= 0:
            raise ValueError("PLE NVMe cache capacity must be > 0")
        if capacity > np.iinfo(np.int32).max:
            raise ValueError("PLE NVMe cache capacity exceeds the int32 row map")
        if slab is not None and (slab.shape[0] < capacity or slab.shape[1] != row_bytes
                                 or slab.dtype != np.uint8):
            raise ValueError(f"PLE NVMe cache slab {slab.shape} {slab.dtype} does not fit")
        self.num_rows = int(num_rows)
        self.capacity = int(capacity)
        self.row_bytes = int(row_bytes)
        self.slab = slab
        self.row2slot = np.full(self.num_rows, -1, dtype=np.int32)
        self.slot2row = np.full(self.capacity, -1, dtype=np.int64)
        self.ref = np.zeros(self.capacity, dtype=np.uint8)
        self.epoch = np.full(self.capacity, _EPOCH_FREE, dtype=np.int64)
        self.hand = 0
        self.step = 0
        self._alloc_out = np.empty(0, dtype=np.int64)

    def meta_bytes(self) -> int:
        return (self.row2slot.nbytes + self.slot2row.nbytes + self.ref.nbytes
                + self.epoch.nbytes)

    def begin_step(self) -> int:
        self.step += 1
        return self.step

    def lookup(self, local_rows: np.ndarray) -> np.ndarray:
        """int64 slots of ``local_rows`` (-1 = miss); marks the hits used."""
        slots = self.row2slot[local_rows].astype(np.int64)
        hit = slots >= 0
        if hit.any():
            used = slots[hit]
            self.ref[used] = 1
            self.epoch[used] = self.step
        return slots

    def allocate(self, count: int) -> np.ndarray:
        if count > self._alloc_out.shape[0]:
            self._alloc_out = np.empty(max(count, 1024), dtype=np.int64)
        out = self._alloc_out
        got, hand = _clock_alloc(
            count, self.hand, self.ref, self.epoch, self.step - 1, self.step, out
        )
        self.hand = int(hand)
        if got < count:
            # Undo the partial pick's marks so the cache state is unchanged
            # except for cleared reference bits (a normal CLOCK side effect).
            # (They were evictable before, so "old" is their honest epoch.)
            picked = out[:got]
            self.epoch[picked] = _EPOCH_FREE
            self.ref[picked] = 0
            raise RuntimeError(
                f"PLE NVMe cache: step needs {count} new slots but only {got} are "
                f"evictable (capacity {self.capacity}; slots touched this or the "
                "previous step are protected) — raise B70_PLE_INT8_NVME_CACHE_GIB"
            )
        return out[:count].copy()

    def install(self, local_rows: np.ndarray, data: np.ndarray | None) -> np.ndarray:
        """Place unique missing ``local_rows`` into freshly allocated slots."""
        slots = self.allocate(local_rows.shape[0])
        old = self.slot2row[slots]
        evicted = old[old >= 0]
        if evicted.size:
            self.row2slot[evicted] = -1
        if self.slab is not None and data is not None:
            self.slab[slots] = data
        self.slot2row[slots] = local_rows
        self.row2slot[local_rows] = slots.astype(np.int32)
        return slots


# --------------------------------------------------------------------------
# Stats
# --------------------------------------------------------------------------


class PleNvmeStats:
    """Counters over an interval; one log line per interval (per rank)."""

    def __init__(self, rank: int, interval_s: float, enabled: bool) -> None:
        self.rank = rank
        self.interval_s = float(interval_s)
        self.enabled = enabled
        self._reset(time.monotonic())
        self.total_steps = 0
        self.total_reads = 0
        self.total_prefetched = 0

    def _reset(self, now: float) -> None:
        self.t0 = now
        self.steps = 0
        self.lookups = 0
        self.hits = 0
        self.misses = 0
        self.reads = 0
        self.hook_ms: list[float] = []
        self.io_ms: list[float] = []
        self.read_lat: list[np.ndarray] = []
        self.prefetched = 0
        self.wait_ms: list[float] = []

    def record(self, lookups: int, hits: int, misses: int, reads: int,
               hook_ms: float, io_ms: float, prefetched: int = 0,
               wait_ms: float = 0.0) -> None:
        """``misses`` = cache misses at hook time; ``reads`` = the ones read
        in the hook (sync); ``prefetched`` = the ones served from the
        lookahead's buffers (0013b); ``wait_ms`` = time the hook waited for
        (or cancelled) an unfinished lookahead job."""
        self.total_steps += 1
        self.total_reads += reads
        self.total_prefetched += prefetched
        if not self.enabled:
            return
        self.prefetched += prefetched
        if wait_ms > 0.0:
            self.wait_ms.append(wait_ms)
        self.steps += 1
        self.lookups += lookups
        self.hits += hits
        self.misses += misses
        self.reads += reads
        self.hook_ms.append(hook_ms)
        self.io_ms.append(io_ms)
        if io_ms > 5.0:
            logger.info("PLE NVMe rank %d: slow step, %d reads took %.1f ms",
                        self.rank, reads, io_ms)
        now = time.monotonic()
        if now - self.t0 >= self.interval_s:
            logger.info("%s", self.line(now))
            self._reset(now)

    def line(self, now: float | None = None) -> str:
        now = time.monotonic() if now is None else now
        lat = (np.concatenate(self.read_lat) * 1e3) if self.read_lat else np.zeros(0)
        hook = np.asarray(self.hook_ms) if self.hook_ms else np.zeros(1)

        def pct(values: np.ndarray, q: float) -> float:
            return float(np.percentile(values, q)) if values.size else 0.0

        rate = self.hits / self.lookups if self.lookups else 0.0
        return (
            f"PLE NVMe rank {self.rank}: {self.steps} steps in {now - self.t0:.0f} s, "
            f"hit rate {rate:.3f} ({self.hits}/{self.lookups}), "
            f"misses/step {self.misses / max(self.steps, 1):.1f}, reads {self.reads}, "
            f"read p50 {pct(lat, 50):.3f} ms p99 {pct(lat, 99):.3f} ms, "
            f"bubble p50 {pct(hook, 50):.3f} ms p99 {pct(hook, 99):.3f} ms "
            f"max {float(hook.max()):.3f} ms"
            + (
                f", from lookahead {self.prefetched}, lookahead waits "
                f"{len(self.wait_ms)} (max {max(self.wait_ms):.3f} ms)"
                if self.prefetched or self.wait_ms else ""
            )
        )


# --------------------------------------------------------------------------
# Per-rank server
# --------------------------------------------------------------------------


class PleNvmeServer:
    """Host side of one rank: hash -> own rows -> cache slots (+ reads)."""

    def __init__(
        self,
        *,
        tp_start: int,
        tp_end: int,
        multipliers: np.ndarray,
        sizes: np.ndarray,
        offsets: np.ndarray,
        eos_token_id: int,
        heads_per_ngram: int,
        cache: PleRowCache,
        store: PleNvmeRowStore | None,
        stats: PleNvmeStats,
        sync_only: bool = False,
    ) -> None:
        self.tp_start = int(tp_start)
        self.tp_end = int(tp_end)
        self.multipliers = np.asarray(multipliers, dtype=np.int64)
        self.sizes = np.asarray(sizes, dtype=np.int64)
        self.offsets = np.asarray(offsets, dtype=np.int64)
        self.eos_token_id = int(eos_token_id)
        self.heads_per_ngram = int(heads_per_ngram)
        self.num_heads = (self.multipliers.shape[0] - 1) * self.heads_per_ngram
        self.own_heads = owned_heads(self.sizes, self.offsets, self.tp_start, self.tp_end)
        self.cache = cache
        self.store = store
        self.stats = stats
        self.sync_only = sync_only
        if not sync_only and store is None:
            raise ValueError("PLE NVMe server needs a row store unless SYNC_ONLY")
        self._lock = threading.Lock()
        self.extra_installed = 0
        self.extra_dropped = 0

    def hash(self, tokens, qsl, ctx, heads=None) -> np.ndarray:
        return host_ngram_ids(
            tokens, qsl, ctx,
            multipliers=self.multipliers, sizes=self.sizes, offsets=self.offsets,
            eos_token_id=self.eos_token_id, heads_per_ngram=self.heads_per_ngram,
            heads=heads,
        )

    def resolve(self, tokens: np.ndarray, qsl: np.ndarray, ctx: np.ndarray,
                num_tokens_padded: int, out: np.ndarray, *, t_start: float | None = None,
                prefetched: tuple[np.ndarray, np.ndarray] | None = None,
                wait_ms: float = 0.0) -> np.ndarray:
        """Fill ``out`` (int64, >= num_tokens_padded * num_heads) and return it.

        NVMe mode: slot ids of this rank's rows, -1 elsewhere (other ranks'
        rows, padding tokens). SYNC_ONLY: the global ids of all heads for the
        real tokens, -1 for padding (served by the in-RAM table); the cache
        still runs its bookkeeping on the own rows so the hit rate is real.

        ``prefetched`` (0013b lookahead): (sorted unique local rows, their
        bytes) read by the lookahead for this step. Order, per step:
          1. lookup of this step's own rows: every hit is marked with this
             step's epoch, so nothing below can evict it;
          2. the misses are taken from ``prefetched`` where present and read
             from the file otherwise (sync), then installed together;
          3. prefetched rows this step did not need are installed after
             that, best effort (dropped if CLOCK cannot place them), so they
             can only displace rows older than the previous step.
        The prefetched rows are never in the cache before step 1, so step
        k's work cannot evict them: their eviction protection starts in the
        step that uses them.
        """
        t_start = time.perf_counter() if t_start is None else t_start
        num_tokens = int(np.asarray(tokens).shape[0])
        heads = self.num_heads
        view = out[: num_tokens_padded * heads].reshape(num_tokens_padded, heads)
        view.fill(-1)
        self.cache.begin_step()
        io_ms = 0.0
        reads = 0
        from_prefetch = 0
        lookups = hits = misses = 0
        pre_rows = pre_data = None
        pre_used = None
        if prefetched is not None and not self.sync_only and prefetched[0].size:
            pre_rows, pre_data = prefetched
            pre_used = np.zeros(pre_rows.shape[0], dtype=bool)
        if num_tokens:
            if self.sync_only:
                ids = self.hash(tokens, qsl, ctx)
                view[:num_tokens] = ids
                own = ids[:, self.own_heads]
            else:
                own = self.hash(tokens, qsl, ctx, heads=self.own_heads)
            mask = (own >= self.tp_start) & (own < self.tp_end)
            local = own[mask] - self.tp_start
            slots = self.cache.lookup(local)
            miss = slots < 0
            lookups = int(local.shape[0])
            misses = int(miss.sum())
            hits = lookups - misses
            if misses:
                miss_rows = np.unique(local[miss])
                data = None
                if not self.sync_only:
                    need = miss_rows
                    data = np.empty((miss_rows.shape[0], self.cache.row_bytes), np.uint8)
                    found = np.zeros(miss_rows.shape[0], dtype=bool)
                    if pre_rows is not None:
                        pos = np.minimum(np.searchsorted(pre_rows, miss_rows),
                                         pre_rows.shape[0] - 1)
                        found = pre_rows[pos] == miss_rows
                        if found.any():
                            data[found] = pre_data[pos[found]]
                            pre_used[pos[found]] = True
                            from_prefetch = int(found.sum())
                        need = miss_rows[~found]
                    if need.size:
                        t_io = time.perf_counter()
                        lat: list = []
                        data[~found] = self.store.read_rows(need + self.tp_start,
                                                            latencies=lat)
                        io_ms = (time.perf_counter() - t_io) * 1e3
                        reads = int(need.shape[0])
                        if self.stats.enabled:
                            self.stats.read_lat.extend(lat)
                self.cache.install(miss_rows, data)
                slots = self.cache.row2slot[local].astype(np.int64)
            if not self.sync_only:
                sub = view[:num_tokens]
                cols = np.full(own.shape, -1, dtype=np.int64)
                cols[mask] = slots
                sub[:, self.own_heads] = cols
        if pre_rows is not None:
            self._install_extra(pre_rows[~pre_used], pre_data[~pre_used])
        hook_ms = (time.perf_counter() - t_start) * 1e3
        self.stats.record(lookups, hits, misses, reads, hook_ms, io_ms,
                          prefetched=from_prefetch, wait_ms=wait_ms)
        return out

    def _install_extra(self, rows: np.ndarray, data: np.ndarray) -> int:
        """Install prefetched rows the step did not use (best effort)."""
        if not rows.size:
            return 0
        absent = self.cache.row2slot[rows] < 0
        rows, data = rows[absent], data[absent]
        if not rows.size:
            return 0
        try:
            self.cache.install(rows, data)
        except RuntimeError:
            self.extra_dropped += int(rows.shape[0])
            return 0
        self.extra_installed += int(rows.shape[0])
        return int(rows.shape[0])


# --------------------------------------------------------------------------
# Prefill lookahead (0013b, A-design §3.3)
# --------------------------------------------------------------------------


def plan_next_chunks(
    idx_mapping: np.ndarray,
    num_computed: np.ndarray,
    num_scheduled: np.ndarray,
    prefill_len: np.ndarray,
    budget: int,
) -> list[tuple[int, int, int]]:
    """Predict the next step's prefill chunks: [(req_idx, start, end)].

    For every request of the batch (batch order) still prefilling after this
    step, the next chunk starts where this step's ends (num_computed +
    num_scheduled) and runs to the end of its prefill, within a token budget
    shared in batch order; requests that decode next step take one token
    each. A wrong guess (the scheduler picks differently, preemption, abort)
    only costs reads: the next hook always resolves the real ids.
    """
    num = int(idx_mapping.shape[0])
    start = num_computed[:num].astype(np.int64) + num_scheduled[:num].astype(np.int64)
    end_all = prefill_len[:num].astype(np.int64)
    prefilling = start < end_all
    left = int(budget) - int((~prefilling).sum())
    plan: list[tuple[int, int, int]] = []
    for i in np.nonzero(prefilling)[0].tolist():
        if left <= 0:
            break
        s0 = int(start[i])
        e0 = min(int(end_all[i]), s0 + left)
        plan.append((int(idx_mapping[i]), s0, e0))
        left -= e0 - s0
    return plan


def current_chunk_keys(idx_mapping: np.ndarray, num_computed: np.ndarray,
                       num_scheduled: np.ndarray, prefill_len: np.ndarray) -> frozenset:
    """Keys (req_idx, start) of this step's prefill chunks, for matching the
    job a previous step's plan_next_chunks started."""
    num = int(idx_mapping.shape[0])
    keys = set()
    for i in range(num):
        s0 = int(num_computed[i])
        if s0 < int(prefill_len[i]) and int(num_scheduled[i]) > 0:
            keys.add((int(idx_mapping[i]), s0))
    return frozenset(keys)


class _LookaheadJob:
    __slots__ = ("keys", "tokens", "qsl", "ctx", "cancel", "started", "done",
                 "rows", "data", "error", "t_submit", "t_done", "planned")

    def __init__(self, keys, tokens, qsl, ctx) -> None:
        self.keys = keys
        self.tokens = tokens
        self.qsl = qsl
        self.ctx = ctx
        self.cancel = False
        self.started = False
        self.done = False
        self.rows: list[np.ndarray] = []
        self.data: list[np.ndarray] = []
        self.error: BaseException | None = None
        self.t_submit = time.perf_counter()
        self.t_done = 0.0
        self.planned = 0


class PleLookahead:
    """Background pre-reader of the next prefill chunk's rows (one per rank).

    Threads and ownership:
      - the step thread (the model runner) is the only writer of the cache;
        it calls ``take`` at the start of a hook and ``submit`` after the
        gather launch, so at most one job exists and none spans a hook;
      - the lookahead thread hashes the job's tokens (pure numpy), reads the
        cache's row->slot map WITHOUT a lock to skip rows already cached (a
        stale answer costs one extra read, or one hook-time read of a row
        evicted since; never wrong bytes), and reads the rest with its own
        store (own fd, own bounce buffers) into job-owned arrays, in
        sub-batches so a cancel takes effect within one sub-batch;
      - results are handed over under the condition variable once the job is
        done or cancelled; the step thread then installs them (resolve).
    Memory: at most ``max_rows`` rows per job (the planned tokens x own heads)
    x 164 B, plus the store's ``sub_batch`` x 8 KiB bounce buffer.
    Errors in the job are logged and dropped: the sync path reads anything
    missing and raises there if the disk is really failing.
    """

    def __init__(self, server: "PleNvmeServer", store: PleNvmeRowStore, *,
                 sub_batch: int = 256, max_rows: int | None = None,
                 name: str = "ple-nvme-lookahead") -> None:
        self.server = server
        self.store = store
        self.sub_batch = max(1, min(int(sub_batch), store.max_batch_rows))
        self.max_rows = max_rows
        self._cv = threading.Condition()
        self._job: _LookaheadJob | None = None
        self._stop = False
        self.submitted = 0
        self.cancelled = 0
        self.rows_read = 0
        self.errors = 0
        self.last_job_ms = 0.0
        self._thread = threading.Thread(target=self._main, name=name, daemon=True)
        self._thread.start()

    # -- step thread ---------------------------------------------------
    def submit(self, keys: frozenset, tokens: np.ndarray, qsl: np.ndarray,
               ctx: np.ndarray) -> None:
        """Start reading the rows of a predicted chunk (arrays are copied)."""
        job = _LookaheadJob(keys, np.array(tokens, dtype=np.int64, copy=True),
                            np.array(qsl, dtype=np.int64, copy=True),
                            np.array(ctx, dtype=np.int64, copy=True))
        with self._cv:
            if self._job is not None:
                raise RuntimeError("PLE NVMe lookahead: submit before take")
            self._job = job
            self.submitted += 1
            self._cv.notify_all()

    def take(self, current_keys: frozenset) -> tuple[tuple[np.ndarray, np.ndarray] | None, float]:
        """End the pending job and return ((rows, data) | None, wait_ms).

        If the job is still running and none of its predicted chunks is in
        this step, it is cancelled (its finished sub-batches are kept);
        otherwise the hook waits for it: its remaining reads are no more
        than the sync path would issue for the same rows.
        """
        with self._cv:
            job = self._job
            if job is None:
                return None, 0.0
            t0 = time.perf_counter()
            waited = False
            if not job.done:
                waited = True
                if not (job.keys & current_keys):
                    job.cancel = True
                while not job.done:
                    self._cv.wait()
            self._job = None
        wait_ms = (time.perf_counter() - t0) * 1e3 if waited else 0.0
        if job.cancel:
            self.cancelled += 1
        if job.error is not None:
            self.errors += 1
            logger.warning("PLE NVMe lookahead job failed (the hook reads instead): %s",
                           job.error)
        if not job.rows:
            return None, wait_ms
        rows = np.concatenate(job.rows)
        data = np.concatenate(job.data)
        return (rows, data), wait_ms

    def close(self) -> None:
        with self._cv:
            self._stop = True
            if self._job is not None:
                self._job.cancel = True
            self._cv.notify_all()
        self._thread.join(timeout=5.0)
        self.store.close()

    # -- lookahead thread ------------------------------------------------
    def _main(self) -> None:
        while True:
            with self._cv:
                while not self._stop and (self._job is None or self._job.started):
                    self._cv.wait()
                if self._stop:
                    return
                job = self._job
                job.started = True
            try:
                self._work(job)
            except BaseException as exc:  # noqa: BLE001 - handed to the step thread
                job.error = exc
            with self._cv:
                job.done = True
                job.t_done = time.perf_counter()
                self.last_job_ms = (job.t_done - job.t_submit) * 1e3
                self._cv.notify_all()

    def _work(self, job: _LookaheadJob) -> None:
        server = self.server
        if job.cancel or job.tokens.shape[0] == 0:
            return
        own = server.hash(job.tokens, job.qsl, job.ctx, heads=server.own_heads)
        mask = (own >= server.tp_start) & (own < server.tp_end)
        local = np.unique(own[mask] - server.tp_start)
        # Unlocked read of the step thread's map (see the class docstring).
        local = local[server.cache.row2slot[local] < 0]
        if self.max_rows is not None:
            local = local[: self.max_rows]
        job.planned = int(local.shape[0])
        for lo in range(0, local.shape[0], self.sub_batch):
            if job.cancel:
                return
            part = local[lo : lo + self.sub_batch]
            data = self.store.read_rows(part + server.tp_start)
            job.rows.append(part)
            job.data.append(data)
            self.rows_read += int(part.shape[0])


def cache_rows_per_rank(total_gib: float, tp_size: int, row_bytes: int) -> int:
    per_rank = int(total_gib * (1 << 30)) // max(1, tp_size)
    return per_rank // row_bytes


__all__ = [
    "READERS",
    "PleLookahead",
    "PleNvmeRowStore",
    "PleNvmeServer",
    "PleNvmeStats",
    "PleRowCache",
    "cache_rows_per_rank",
    "host_ngram_ids",
    "current_chunk_keys",
    "owned_heads",
    "plan_next_chunks",
    "safetensors_tensor_location",
]
