#!/usr/bin/env python3
"""End-to-end tests for the Samsung updater pty driver against a fake utility."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


DRIVER = Path(__file__).with_name("drive-samsung-fumagician-pty.py")

FAKE_UPDATER = r"""#!/usr/bin/env bash
# Mimics fumagician's prompt sequence without touching any device.
echo "|#|               Drive Model               |    Serial Number    | Firmware |"
echo "|1| Samsung SSD 980 PRO with Heatsink 1TB  | S6WSNS0T109768K     | 4B2QGXA7 |"
printf 'Do you want to continue the firmware update? [Y/N]: '
read -r answer
echo
if [[ ${answer} != Y ]]; then
  echo "Exiting Samsung SSD Firmware Update Utility Ver. 3.1"
  exit 0
fi
echo "  YOU MUST TAKE BACK UP OF ALL DATA ON THE DRIVE AS THE FIRMWARE UPDATE"
printf 'Do you want to continue the firmware update? [Y/N]: '
read -r answer_again
echo
if [[ ${answer_again} != Y ]]; then
  echo "Exiting Samsung SSD Firmware Update Utility Ver. 3.1"
  exit 0
fi
echo "Downloading firmware ..."
echo "Firmware Update Completed"
printf 'Do you want to continue the firmware update on next device? [Y/N]: '
read -r answer2
echo
echo "answer2=${answer2}"
printf 'Press any key to EXIT...'
read -r -n 1 _
echo
exit 0
"""


def run_driver(
    tmp: Path, answer: str, fake: str = FAKE_UPDATER
) -> tuple[int, str, str]:
    binary = tmp / "fumagician"
    binary.write_text(fake, encoding="utf-8")
    binary.chmod(0o755)
    transcript = tmp / "transcript.log"
    proc = subprocess.run(
        [
            sys.executable,
            str(DRIVER),
            "--cwd",
            str(tmp),
            "--transcript",
            str(transcript),
            "--answer-continue",
            answer,
            "--prompt-timeout",
            "10",
            "--total-timeout",
            "30",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return (
        proc.returncode,
        proc.stdout,
        transcript.read_text(encoding="utf-8", errors="replace"),
    )


class DriverTests(unittest.TestCase):
    def test_confirm_path_answers_y_then_n_then_enter(self):
        with TemporaryDirectory() as tmp:
            rc, out, transcript = run_driver(Path(tmp), "Y")
            self.assertEqual(rc, 0, out)
            self.assertIn("Firmware Update Completed", transcript)
            self.assertIn("[driver-reply] Y", transcript)
            self.assertIn("answer2=N", transcript)
            self.assertIn("'answered_continue': True", out)
            self.assertIn("'answered_next_device': 1", out)
            self.assertIn("'saw_firmware_update_completed': True", out)

    def test_vendor_dry_run_answers_n_and_exits_clean(self):
        with TemporaryDirectory() as tmp:
            rc, out, transcript = run_driver(Path(tmp), "N")
            self.assertEqual(rc, 0, out)
            self.assertIn("[driver-reply] N", transcript)
            self.assertNotIn("Firmware Update Completed", transcript)
            self.assertIn("'saw_firmware_update_completed': False", out)

    def test_confirm_without_completion_banner_fails(self):
        fake = FAKE_UPDATER.replace(
            'echo "Firmware Update Completed"', 'echo "Firmware update FAILED"'
        )
        with TemporaryDirectory() as tmp:
            rc, out, _ = run_driver(Path(tmp), "Y", fake)
            self.assertEqual(rc, 4, out)

    def test_silent_utility_hits_prompt_timeout(self):
        fake = "#!/usr/bin/env bash\nsleep 30\n"
        with TemporaryDirectory() as tmp:
            binary = Path(tmp) / "fumagician"
            binary.write_text(fake, encoding="utf-8")
            binary.chmod(0o755)
            proc = subprocess.run(
                [
                    sys.executable,
                    str(DRIVER),
                    "--cwd",
                    tmp,
                    "--transcript",
                    str(Path(tmp) / "t.log"),
                    "--answer-continue",
                    "N",
                    "--prompt-timeout",
                    "2",
                    "--total-timeout",
                    "20",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(proc.returncode, 3, proc.stdout)
            self.assertIn("'exit_reason': 'prompt-timeout'", proc.stdout)

    def test_missing_binary_fails_closed(self):
        with TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [
                    sys.executable,
                    str(DRIVER),
                    "--cwd",
                    tmp,
                    "--transcript",
                    str(Path(tmp) / "t.log"),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertFalse(os.path.exists(Path(tmp) / "fumagician"))


if __name__ == "__main__":
    unittest.main()
