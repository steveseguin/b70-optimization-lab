# Qwen3.8 Flash-Next HC-up grouped S3g intent

Date: 2026-08-31

Status: design intent only; not yet frozen and not launchable

S2 proved grouped E=1 byte-exact in all 30 tested real-weight/M cells while
the packed-view and packed-matmul alternatives failed eight low-M cells. The
original all-provider S3 is not authorized by its frozen antecedent.

The prospective S3g scope is:

- all 97 target HC-up checkpoint weights;
- M64 only;
- contiguous authority and grouped E=1 only;
- 97 cells and 194 isolated one-card arms;
- the same exact checkpoint, loader, staged kernel, XPU, closure, mutation,
  repeatability, and no-promotion gates as S2;
- a new evidence root and plan identity.

S3g must not run until the driver supports a distinct `s3g` scope, focused
tests pass, the resulting worker/driver/plan hashes are frozen into a full
preregistration, and independent static review finds no blocker. A complete
exact pass would authorize only a source-dispatch design and tests. It would
not authorize a full-model load, endpoint launch, or throughput claim.
