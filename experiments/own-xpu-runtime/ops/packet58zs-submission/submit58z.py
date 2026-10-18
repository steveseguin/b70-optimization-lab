#!/usr/bin/env python3
"""Post-chain wrapper for packet58z's sealed submission CLI (fix in a copy; the sealed tree is untouched).

Defect: packet58z vendored `shared_submission_cli.py` into the packet folder, where its
`REPO_ROOT = Path(__file__).resolve().parents[1]` resolves to `stage2/` instead of the repository
root, so every repo-relative evidence path (`promotionAttestation`, evidence bundle) is joined
twice and the dry-run refuses. This wrapper imports the packet's own unmodified
`submission_cli.py`, loads the shared CLI exactly as it does, and only sets `REPO_ROOT` to the
repository root before `main()`. Every check, payload and receipt path is otherwise unchanged.
"""
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[4]          # .../llm-optimizations
PACKET = REPO / 'experiments/own-xpu-runtime/stage2/packet58z-onecard-record'
assert (REPO / '.git').exists() and (PACKET / 'submission_cli.py').is_file()
sys.path.insert(0, str(PACKET))
import submission_cli  # the sealed packet58z CLI, unmodified

module = submission_cli.load_submitter()
assert module.REPO_ROOT == PACKET.parent, ('unexpected REPO_ROOT', module.REPO_ROOT)
module.REPO_ROOT = REPO
raise SystemExit(module.main())
