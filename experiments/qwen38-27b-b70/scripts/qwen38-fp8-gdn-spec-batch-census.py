#!/usr/bin/env python3
"""Spec-path GDN census (R158, rewritten 2026-10-04 for the R310 image).

Operator diagnostic only; never a speed or quality claim.

Asks the speculative (multi-token verify) GDN kernel, `torch.ops._xpu_C.gdn_attention`
with num_spec_decodes > 0, two questions with random data of the real per-rank shapes
(TP2: 8 of 16 key heads, 24 of 48 value heads; TP1: 16 and 48):

  1. Row-count census, ONE request.  Is verify row r (output, z) and the state the call
     leaves for an accepted prefix of length a (SSM slot a-1, conv window) bit-identical
     whatever the number n of verify rows in the call?  For n in ROW_COUNTS the first
     min(n, 6) rows are compared with the 6-row call (the shipped shape: 1 sampled + 5
     draft tokens), and every row with the non-speculative decode kernel applied token by
     token (what the same server computes without MTP).  Repeat determinism per n; the
     6-row call with the shipped conv-state length (3 + 5 rows) versus a longer one.
  2. Batch census, several requests each verifying 6 rows: every request's rows and
     states in a B-request call versus that request alone, also with the request order
     permuted, and repeated.  (The shipped launchers run --max-num-seqs 1; this is for the
     multi-user lanes.)

How R310 calls the kernel (site-packages, read 2026-10-04):
  * vllm/model_executor/layers/mamba/gdn/qwen_gdn_linear_attn.py forward_xpu
    -> torch.ops.vllm.gdn_attention_core_xpu(core_attn_out, z, qkvz, ba,
       self._xpu_conv_state, self._xpu_ssm_state, prefix)
  * vllm/_xpu_ops.py _gdn_attention_core_xpu_impl -> torch.ops._xpu_C.gdn_attention(...,
    conv_bias=None (conv1d has no bias), activation="silu", reorder_input=True
    (Qwen3.5 layout, gqa_interleaved_layout=False), tp_size).  A pure verify step passes
    num_spec_decodes=B, has_initial_state=None, non_spec_query_start_loc=None,
    non_spec_token_indx=empty int32, non_spec_state_indices_tensor=None,
    spec_query_start_loc=[0, n, 2n, ...] int32, spec_token_indx=arange(B*n) int32,
    spec_state_indices_tensor=block_table[:, :n] int32 [B, n] (n = active spec width),
    num_accepted_tokens int32 [B] (the previous step's accepted count).
    With VLLM_XPU_GDN_SPEC_GROUP=16 (shipped; default 16) a step with more than 16 spec
    requests is cut into calls of at most 16 requests; VLLM_XPU_GDN_SPLIT_MIXED=1
    (shipped; default 0) only acts on steps that mix prefill/decode with spec rows.
  * State layout (vllm/model_executor/layers/mamba/mamba_utils.py, "SD" default):
    conv_state [blocks, (W-1) + num_spec, conv_dim] float16 -- one line per request in
    column 0 of its slot row; the kernel reads the window starting at row
    num_accepted-1 and rewrites the line as [2 history rows, the n inputs].  This is why
    the September script (3-row conv state) now stops with "conv_state must have at least
    4 rows".  ssm_state [blocks, lv, 128, 128] float16: initial state from slot
    [num_accepted-1], the state after verify token t written to slot [t].
  * Kernel source matching the R310 library's checks:
    vllm-xpu-kernels csrc/xpu/gdn_attn/{gdn_attn_interface.cpp,causal_conv1d.hpp,
    gated_delta_rule.hpp} (local checkout of 6d92b1b used to read it).
NOT covered: the one-card package's shipped image (R312d-c) with B70_GDN_CHECKPOINT=1
replaces this kernel by _xpu_C.gdn_attention_ckpt (packages/qwen38-27b-fp8-tp1-b70/
overlays/b70_gdn_checkpoint.py); the TP1 rows here are the stock R310 kernel at TP1 shapes.

Run on R310 (one card; both TP shapes run on it):

  docker run --rm --network none --workdir /tmp --device /dev/dri:/dev/dri \
    --group-add <render gid> --ipc=host --shm-size=2g --memory 10g --memory-swap 10g \
    --entrypoint python3 \
    --env-file /mnt/fast-ai/bench-results/fp8-census-r310-20261004/env.list \
    -e ZE_AFFINITY_MASK=0 -e ONEAPI_DEVICE_SELECTOR=level_zero:0 \
    -v $PWD/experiments/qwen38-27b-b70/scripts:/work:ro -v $OUT:/out \
    sha256:eb8165070409959c9ce4ba4c605ebaf2a39f82ce6b755e408241ab85b08b1e04 \
    /work/qwen38-fp8-gdn-spec-batch-census.py --out /out/gdn-spec-census-r310.json

R313 (patches/vllm-xpu-kernels-gdn-spec-decode-exact-r313-20261004.patch: the spec kernel carries
the SSM state through the slot's float16 rounding, as decode does): same command on the R313 image
with --expect-decode-equal (exit 1 unless every row/state equals token-by-token decode and the
row-count, batch and repeat checks still pass).
"""
from __future__ import annotations

import argparse
import json
import platform
import time
from pathlib import Path

import torch

NK, NV, DK, DV, WIDTH = 16, 48, 128, 128, 4   # config.json linear_* and conv kernel
DT = torch.float16                             # --dtype float16; mamba cache dtype auto
SHIPPED_ROWS = 6                               # MTP depth 5: 1 sampled + 5 drafts
ROW_COUNTS = [2, 3, 4, 5, 6, 7, 8, 9, 12, 16, 17, 24, 32, 33]
BATCHES = [1, 2, 3, 4, 5, 6, 8, 16, 17, 24, 32, 33, 48, 64]
I32 = torch.int32


def bits(t: torch.Tensor) -> torch.Tensor:
    t = t.detach().contiguous()
    return t.view(torch.int16) if t.element_size() == 2 else t.view(torch.int32)


def beq(a: torch.Tensor, b: torch.Tensor) -> bool:
    return a.shape == b.shape and bool(torch.equal(bits(a), bits(b)))


def max_abs(a: torch.Tensor, b: torch.Tensor) -> float:
    return float((a.float() - b.float()).abs().max().item()) if a.numel() else 0.0


class Rank:
    """Per-rank shapes and constant layer parameters for one TP size."""

    def __init__(self, tp: int, dev, gen):
        self.tp, self.dev = tp, dev
        lk = NK // tp
        self.lv = NV // tp
        self.qkvz_w = lk * (2 * DK + 2 * DV * NV // NK)
        self.ba_w = 2 * self.lv
        self.conv_dim = lk * (2 * DK + DV * NV // NK)
        self.gen = gen
        self.cw = self.rand((self.conv_dim, WIDTH), 0.2)        # conv1d.weight.view(C, W)
        self.a_log = self.rand((self.lv,), 1.0, torch.float32)  # A_log is float32
        self.dt_bias = self.rand((self.lv,), 1.0)               # must match out dtype

    def rand(self, shape, scale, dtype=DT):
        return (torch.randn(shape, generator=self.gen, device="cpu") * scale).to(
            dtype).to(self.dev).contiguous()

    def shapes(self) -> dict:
        return {"tp": self.tp, "k_heads_local": NK // self.tp, "v_heads_local": self.lv,
                "qkvz_width": self.qkvz_w, "ba_width": self.ba_w,
                "conv_dim_local": self.conv_dim, "ssm_slot": [self.lv, DV, DK]}

    def _op(self, out, z, qkvz, ba, conv, ssm, **kw):
        torch.ops._xpu_C.gdn_attention(
            out, z, qkvz, ba, NK, NV, DK, DV,
            conv_state=conv, ssm_state=ssm, conv_weights=self.cw, conv_bias=None,
            activation="silu", A_log=self.a_log, dt_bias=self.dt_bias,
            tp_size=self.tp, reorder_input=True, **kw)

    def spec(self, qkvz, ba, conv, ssm, state_idx, n_acc):
        """One verify step: B requests x n rows (n = state_idx.shape[1])."""
        b, n = state_idx.shape
        t = b * n
        out = torch.zeros((t, self.lv, DV), dtype=DT, device=self.dev)
        z = torch.empty_like(out)
        self._op(out, z, qkvz.contiguous(), ba.contiguous(), conv, ssm,
                 num_prefills=0, num_decodes=0, num_spec_decodes=b,
                 has_initial_state=None, non_spec_query_start_loc=None,
                 non_spec_token_indx=torch.empty(0, dtype=I32, device=self.dev),
                 non_spec_state_indices_tensor=None,
                 spec_query_start_loc=torch.arange(0, t + 1, n, dtype=I32, device=self.dev),
                 spec_token_indx=torch.arange(t, dtype=I32, device=self.dev),
                 spec_state_indices_tensor=state_idx.to(I32).contiguous(),
                 num_accepted_tokens=n_acc.to(I32).contiguous(), num_actual_tokens=t)
        torch.xpu.synchronize()
        return out, z

    def decode(self, qkvz1, ba1, conv, ssm):
        """Non-speculative one-token decode for slot 0 (as the server without MTP)."""
        out = torch.zeros((1, self.lv, DV), dtype=DT, device=self.dev)
        z = torch.empty_like(out)
        self._op(out, z, qkvz1.contiguous(), ba1.contiguous(), conv, ssm,
                 num_prefills=0, num_decodes=1, num_spec_decodes=0,
                 has_initial_state=None,
                 non_spec_query_start_loc=torch.tensor([0, 1], dtype=I32, device=self.dev),
                 non_spec_token_indx=None,
                 non_spec_state_indices_tensor=torch.zeros(1, dtype=I32, device=self.dev),
                 spec_query_start_loc=None, spec_token_indx=None,
                 spec_state_indices_tensor=None, num_accepted_tokens=None,
                 num_actual_tokens=1)
        torch.xpu.synchronize()
        return out, z


def row_count_census(rk: Rank, a0: int) -> dict:
    """One request; n verify rows; previous step accepted a0 tokens."""
    nmax = max(ROW_COUNTS)
    rows_big = WIDTH - 1 + nmax - 1           # long enough for every n
    rows_ship = WIDTH - 1 + SHIPPED_ROWS - 1  # the shipped depth-5 layout
    qkvz = rk.rand((nmax, rk.qkvz_w), 1.0)
    ba = rk.rand((nmax, rk.ba_w), 1.0)
    conv0 = torch.zeros((nmax, rows_big, rk.conv_dim), dtype=DT, device=rk.dev)
    conv0[0] = rk.rand((rows_big, rk.conv_dim), 1.0)       # request's line = slot 0
    ssm0 = rk.rand((nmax, rk.lv, DV, DK), 0.1)              # slots 0..nmax-1
    acc = torch.tensor([a0], dtype=I32, device=rk.dev)
    hist = WIDTH - 2                                        # history rows kept in the line

    def run(n, conv_src):
        conv, ssm = conv_src.clone(), ssm0.clone()
        idx = torch.arange(n, dtype=I32, device=rk.dev).view(1, n)
        out, z = rk.spec(qkvz[:n], ba[:n], conv, ssm, idx, acc)
        return {"out": out, "z": z, "ssm": ssm[:n].clone(), "line": conv[0].clone()}

    # Token-by-token decode reference from the same starting state.
    ref_conv = conv0[0:1, a0 - 1:a0 - 1 + WIDTH - 1].clone().contiguous()  # [1, W-1, C]
    ref_ssm = ssm0[a0 - 1:a0].clone()
    dec_out, dec_z, dec_ssm, dec_conv = [], [], [], []
    for t in range(nmax):
        o, z = rk.decode(qkvz[t:t + 1], ba[t:t + 1], ref_conv, ref_ssm)
        dec_out.append(o); dec_z.append(z)
        dec_ssm.append(ref_ssm[0].clone()); dec_conv.append(ref_conv[0].clone())
    dec_out, dec_z = torch.cat(dec_out), torch.cat(dec_z)

    base = run(SHIPPED_ROWS, conv0)
    ship = run(SHIPPED_ROWS, conv0[:, :rows_ship].contiguous())
    k6 = SHIPPED_ROWS
    shipped_layout = {
        "conv_rows_shipped": rows_ship, "conv_rows_long": rows_big,
        "out_z_equal": beq(ship["out"], base["out"]) and beq(ship["z"], base["z"]),
        "ssm_equal": beq(ship["ssm"], base["ssm"]),
        "conv_line_equal": beq(ship["line"][:hist + k6], base["line"][:hist + k6]),
    }
    print(f"CENSUS gdn_spec tp={rk.tp} a0={a0} shipped_conv_rows={rows_ship}"
          f" equal_to_long_conv_rows={all(v for k, v in shipped_layout.items() if k.endswith('equal'))}",
          flush=True)

    rows = []
    for n in ROW_COUNTS:
        if n < a0:
            continue
        r = run(n, conv0)
        r2 = run(n, conv0)
        k = min(n, SHIPPED_ROWS)
        out_eq = beq(r["out"][:k], base["out"][:k]) and beq(r["z"][:k], base["z"][:k])
        ssm_eq = beq(r["ssm"][:k], base["ssm"][:k])
        conv_eq = beq(r["line"][:hist + k], base["line"][:hist + k])
        # Against token-by-token decode, every row of this call.
        row_bad = [i for i in range(n) if not (beq(r["out"][i], dec_out[i])
                                               and beq(r["z"][i], dec_z[i]))]
        state_bad = [a for a in range(1, n + 1)
                     if not (beq(r["ssm"][a - 1], dec_ssm[a - 1])
                             and beq(r["line"][a - 1:a - 1 + WIDTH - 1], dec_conv[a - 1]))]
        entry = {
            "rows": n, "compared_rows_with_6row_call": k,
            "out_z_equal_6row_shape": out_eq,
            "ssm_states_equal_6row_shape": ssm_eq,
            "conv_line_equal_6row_shape": conv_eq,
            "max_abs_out_vs_6row": max_abs(r["out"][:k], base["out"][:k]),
            "rows_equal_decode": not row_bad,
            "first_row_differing_from_decode": row_bad[0] if row_bad else None,
            "rows_differing_from_decode": len(row_bad),
            "max_abs_out_vs_decode": max_abs(r["out"], dec_out[:n]),
            "states_equal_decode_for_every_prefix": not state_bad,
            "first_prefix_state_differing_from_decode": state_bad[0] if state_bad else None,
            "max_abs_ssm_vs_decode": max(max_abs(r["ssm"][a - 1], dec_ssm[a - 1])
                                         for a in range(1, n + 1)),
            "repeat_equal": all(beq(r[x], r2[x]) for x in ("out", "z", "ssm", "line")),
        }
        rows.append(entry)
        print(f"CENSUS gdn_spec tp={rk.tp} a0={a0} rows={n}"
              f" equal_to_6row_shape={out_eq and ssm_eq and conv_eq}"
              f" equal_to_decode={entry['rows_equal_decode'] and entry['states_equal_decode_for_every_prefix']}"
              f" repeat={entry['repeat_equal']}", flush=True)
    return {
        "previous_accepted_a0": a0,
        "shipped_conv_layout_vs_long": shipped_layout,
        "by_rows": rows,
        "all_equal_6row_shape": all(e["out_z_equal_6row_shape"] and e["ssm_states_equal_6row_shape"]
                                    and e["conv_line_equal_6row_shape"] for e in rows),
        "all_equal_decode": all(e["rows_equal_decode"] and e["states_equal_decode_for_every_prefix"]
                                for e in rows),
        "all_repeat_equal": all(e["repeat_equal"] for e in rows),
    }


def batch_census(rk: Rank, batches: list[int], seed: int) -> dict:
    """B requests x 6 verify rows versus each request alone."""
    n = SHIPPED_ROWS
    nb = max(batches)
    rows_ship = WIDTH - 1 + n - 1
    qkvz = rk.rand((nb, n, rk.qkvz_w), 1.0)
    ba = rk.rand((nb, n, rk.ba_w), 1.0)
    slots = torch.arange(nb * n, dtype=I32, device=rk.dev).view(nb, n)  # request s: s*6..s*6+5
    conv0 = rk.rand((nb * n, rows_ship, rk.conv_dim), 1.0)
    ssm0 = rk.rand((nb * n, rk.lv, DV, DK), 0.1)
    acc_all = torch.tensor([1 + s % n for s in range(nb)], dtype=I32, device=rk.dev)

    def run(seqs):
        conv, ssm = conv0.clone(), ssm0.clone()
        sel = torch.tensor(seqs, dtype=torch.long, device=rk.dev)
        out, z = rk.spec(qkvz[sel].reshape(-1, rk.qkvz_w), ba[sel].reshape(-1, rk.ba_w),
                         conv, ssm, slots[sel], acc_all[sel])
        res = {}
        for i, s in enumerate(seqs):
            sl = slots[s].long()
            res[s] = {"out": out[i * n:(i + 1) * n], "z": z[i * n:(i + 1) * n],
                      "ssm": ssm[sl].clone(), "line": conv[sl[0]].clone()}
        return res

    def same(a, b):
        return all(beq(a[x], b[x]) for x in ("out", "z", "ssm", "line"))

    alone = {}
    for s in range(nb):
        alone.update(run([s]))
    gen = torch.Generator(device="cpu").manual_seed(seed + 7)
    rows = []
    for b in batches:
        seqs = list(range(b))
        r1, r2 = run(seqs), run(seqs)
        perm = torch.randperm(b, generator=gen).tolist()
        rp = run([seqs[p] for p in perm])
        bad = [s for s in seqs if not same(r1[s], alone[s])]
        entry = {
            "requests": b, "rows": b * n,
            "equal_alone": not bad, "requests_differing_from_alone": len(bad),
            "first_request_differing": bad[0] if bad else None,
            "max_abs_out_vs_alone": max(max_abs(r1[s]["out"], alone[s]["out"]) for s in seqs),
            "permuted_equal_alone": all(same(rp[s], alone[s]) for s in seqs),
            "repeat_equal": all(same(r1[s], r2[s]) for s in seqs),
            "server_splits_into_groups_of_16": b > 16,
        }
        rows.append(entry)
        print(f"CENSUS gdn_spec_batch tp={rk.tp} requests={b} rows={b * n}"
              f" equal_alone={entry['equal_alone']} permuted_equal={entry['permuted_equal_alone']}"
              f" repeat={entry['repeat_equal']}", flush=True)
    return {"rows_per_request": n, "conv_rows": rows_ship,
            "previous_accepted": "1 + request % 6",
            "by_requests": rows,
            "all_batch_invariant": all(e["equal_alone"] and e["permuted_equal_alone"] for e in rows),
            "first_failing_requests": next((e["requests"] for e in rows if not e["equal_alone"]), None)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=20261004)
    ap.add_argument("--tp", default="2,1", help="per-rank shapes to test, e.g. 2,1")
    ap.add_argument("--accepted", default="1,3,6",
                    help="previous step's accepted counts for the row census")
    ap.add_argument("--batches", default=",".join(map(str, BATCHES)))
    ap.add_argument("--skip-batch", action="store_true")
    ap.add_argument("--skip-rows", action="store_true")
    ap.add_argument("--expect-decode-equal", action="store_true",
                    help="gate for the r313 kernel: exit 1 unless every row census is equal to "
                         "token-by-token decode, the 6-row shape and its repeat, and every batch "
                         "census is batch-invariant and repeatable")
    a = ap.parse_args()

    if not torch.xpu.is_available():
        raise SystemExit("XPU is required")
    import vllm  # noqa: F401
    import vllm_xpu_kernels._xpu_C  # noqa: F401  (registers _xpu_C ops)
    if not hasattr(torch.ops._xpu_C, "gdn_attention"):
        raise SystemExit("_xpu_C::gdn_attention is missing in this image")
    dev = torch.device("xpu:0")
    props = torch.xpu.get_device_properties(0)
    report = {
        "schema": "neural.download.qwen38-fp8-gdn-spec-census.v2",
        "classification": "operator-diagnostic-only",
        "environment": {"device": props.name, "torch": torch.__version__,
                        "vllm": getattr(vllm, "__version__", None),
                        "vllm_file": getattr(vllm, "__file__", None),
                        "python": platform.python_version(), "seed": a.seed,
                        "op_schema": str(torch.ops._xpu_C.gdn_attention.default._schema)},
        "shipped_verify_rows": SHIPPED_ROWS,
        "by_tp": {},
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    for tp in [int(x) for x in a.tp.split(",") if x]:
        gen = torch.Generator(device="cpu").manual_seed(a.seed + tp)
        rk = Rank(tp, dev, gen)
        sec = report["by_tp"].setdefault(f"tp{tp}", {"shapes": rk.shapes()})
        t0 = time.perf_counter()
        if not a.skip_rows:
            sec["row_count_census"] = {}
            for a0 in [int(x) for x in a.accepted.split(",") if x]:
                try:
                    sec["row_count_census"][f"a0={a0}"] = row_count_census(rk, a0)
                except Exception as exc:  # noqa: BLE001
                    sec["row_count_census"][f"a0={a0}"] = {"status": "unavailable",
                                                           "error": repr(exc)}
                    print(f"CENSUS gdn_spec tp={tp} a0={a0} status=unavailable {exc!r}"[:240],
                          flush=True)
                a.out.write_text(json.dumps(report, indent=1))
        if not a.skip_batch:
            try:
                sec["batch_census"] = batch_census(
                    rk, [int(x) for x in a.batches.split(",") if x], a.seed)
            except Exception as exc:  # noqa: BLE001
                sec["batch_census"] = {"status": "unavailable", "error": repr(exc)}
                print(f"CENSUS gdn_spec_batch tp={tp} status=unavailable {exc!r}"[:240],
                      flush=True)
        sec["census_seconds"] = round(time.perf_counter() - t0, 1)
        a.out.write_text(json.dumps(report, indent=1))
        del rk
        torch.xpu.empty_cache()

    summary = {}
    for tp, sec in report["by_tp"].items():
        for key, rc in sec.get("row_count_census", {}).items():
            summary[f"{tp} rows {key}"] = {k: rc.get(k, "unavailable") for k in
                                           ("all_equal_6row_shape", "all_equal_decode",
                                            "all_repeat_equal")}
        bc = sec.get("batch_census", {})
        if bc:
            summary[f"{tp} batch"] = {k: bc.get(k, "unavailable") for k in
                                      ("all_batch_invariant", "first_failing_requests")}
    report["summary"] = summary
    if a.expect_decode_equal:
        failed = []
        for tp, sec in report["by_tp"].items():
            for key, rc in sec.get("row_count_census", {}).items():
                if not all(rc.get(k) is True for k in
                           ("all_equal_6row_shape", "all_equal_decode", "all_repeat_equal")):
                    failed.append(f"{tp} rows {key}")
            bc = sec.get("batch_census")
            if bc and not (bc.get("all_batch_invariant") is True and all(
                    e["repeat_equal"] for e in bc.get("by_requests", []))):
                failed.append(f"{tp} batch")
        report["expect_decode_equal"] = {"passed": not failed, "failed": failed}
        print(f"CENSUS expect_decode_equal passed={not failed} failed={failed}", flush=True)
    a.out.write_text(json.dumps(report, indent=1))
    print(json.dumps(summary, indent=1))
    if a.expect_decode_equal and not report["expect_decode_equal"]["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
