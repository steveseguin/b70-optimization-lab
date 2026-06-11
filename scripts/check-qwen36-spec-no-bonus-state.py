#!/usr/bin/env python3
"""Validate the XPU no-bonus speculative accounting invariant.

The opt-in no-bonus diagnostic suppresses the target verifier bonus token on a
full-accept speculative row. If the scheduler still treats that bonus position
as committed, the next step skips over the suppressed token. This script builds
a small CPU scheduler fixture and verifies that suppressing the bonus also rolls
back one computed token so the next step can recompute the bonus position.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vllm-src",
        type=Path,
        default=Path("/home/steve/src/vllm"),
        help="Path to the local vLLM source tree.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sys.path.insert(0, str(args.vllm_src))
    os.environ["VLLM_XPU_SPEC_DECODE_DISABLE_FULL_ACCEPT_BONUS"] = "1"

    from tests.v1.core.utils import create_requests, create_scheduler
    from vllm.v1.outputs import DraftTokenIds, ModelRunnerOutput

    scheduler = create_scheduler(
        num_speculative_tokens=5,
        max_num_batched_tokens=128,
        max_model_len=128,
    )
    (request,) = create_requests(
        num_requests=1,
        num_tokens=8,
        max_tokens=64,
        req_ids=["req"],
    )
    scheduler.add_request(request)

    prefill = scheduler.schedule()
    scheduler.update_from_output(
        prefill,
        ModelRunnerOutput(
            req_ids=["req"],
            req_id_to_index={"req": 0},
            sampled_token_ids=[[101]],
            logprobs=None,
            prompt_logprobs_dict={},
            pooler_output=[],
        ),
    )

    scheduler.update_draft_token_ids(
        DraftTokenIds(req_ids=["req"], draft_token_ids=[[201, 202, 203, 204, 205]])
    )
    spec_output = scheduler.schedule()
    assert spec_output.scheduled_spec_decode_tokens["req"] == [
        201,
        202,
        203,
        204,
        205,
    ]
    assert spec_output.num_scheduled_tokens["req"] == 6

    scheduler.update_from_output(
        spec_output,
        ModelRunnerOutput(
            req_ids=["req"],
            req_id_to_index={"req": 0},
            sampled_token_ids=[[201, 202, 203, 204, 205, 999]],
            logprobs=None,
            prompt_logprobs_dict={},
            pooler_output=[],
        ),
    )

    assert list(request.output_token_ids) == [101, 201, 202, 203, 204, 205]
    assert 999 not in request.output_token_ids
    assert request.num_computed_tokens == request.num_tokens - 1

    print(
        {
            "passed": True,
            "num_computed_tokens": request.num_computed_tokens,
            "num_tokens": request.num_tokens,
            "output_tokens": list(request.output_token_ids),
            "suppressed_bonus": 999,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
