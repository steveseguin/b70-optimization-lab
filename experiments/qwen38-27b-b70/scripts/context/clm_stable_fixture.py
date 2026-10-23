"""Explicit diagnostic fixture for repeatable root-directory listings.

Campaign 58 seed 2 asked for ``ls -la /app/`` in its first action. The ``..``
entry exposed the container's creation time and differed from campaign 55 before
the first differing model reply. This agent sets ONLY the sandbox root directory's
mtime after normal setup, before any model call. It does not filter tool output,
alter the task, or make arbitrary shell commands deterministic.

Use the separate plain-stable-fixture arm with SANDBOX_ROOT_MTIME explicitly set
to integer Unix seconds. Both arms of a comparison must use the same fixture.
"""
from __future__ import annotations

import json
import os
import re

from clm_baselines import PlainAgent


def fixture_epoch(value: str | None) -> int:
    if value is None or not re.fullmatch(r"[0-9]{1,11}", value):
        raise ValueError("SANDBOX_ROOT_MTIME must be explicit integer Unix seconds")
    epoch = int(value)
    if epoch > 4102444800:
        raise ValueError("SANDBOX_ROOT_MTIME must be between 0 and 4102444800")
    return epoch


def fixture_command(epoch: int) -> str:
    # Executed only through Harbor's environment.exec, never on the host. Keep
    # atime intact; ctime necessarily changes when the OS applies the mtime.
    epoch = fixture_epoch(str(epoch))
    return "python3 - <<'PY'\n" + f"""import json, os
path = '/'
before = os.stat(path)
target_ns = {epoch} * 1000000000
os.utime(path, ns=(before.st_atime_ns, target_ns))
after = os.stat(path)
if after.st_mtime_ns != target_ns:
    raise RuntimeError('sandbox root mtime did not take effect')
print(json.dumps({{'path': path, 'mtime_ns': after.st_mtime_ns,
                  'previous_mtime_ns': before.st_mtime_ns}}))
""" + "PY"


class StableFixtureAgent(PlainAgent):
    @staticmethod
    def name() -> str:
        return "plain-stable-fixture"

    def __init__(self, *args, **kwargs):
        self.sandbox_root_mtime = fixture_epoch(os.environ.get("SANDBOX_ROOT_MTIME"))
        super().__init__(*args, **kwargs)

    async def setup(self, environment) -> None:
        await super().setup(environment)
        result = await environment.exec(
            command=fixture_command(self.sandbox_root_mtime), timeout_sec=10
        )
        if result.return_code != 0:
            raise RuntimeError(f"sandbox root mtime setup failed: {result.stderr}")
        try:
            receipt = json.loads(result.stdout)
            if (receipt["path"] != "/" or
                    receipt["mtime_ns"] != self.sandbox_root_mtime * 1_000_000_000):
                raise ValueError("sandbox root mtime receipt did not match")
        except (ValueError, KeyError, TypeError) as exc:
            raise RuntimeError("invalid sandbox root mtime receipt") from exc
        receipt["scope"] = "sandbox root directory mtime only; no tool-output filtering"
        (self.logs_dir / "stable-fixture.json").write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False) + "\n"
        )
