# Full-suite attempt A: pre-device refusal

The native parser rejected `--max-new 512` under its previous 128-token
argument bound. The stage exited with code 1 before creating its native output
directory; no prompt request or GPU timing result exists. The terminal
0.0227-second value describes the failed launch, not inference.

Original plan, admission, terminal receipt and process log are retained here.
[Summary](summary.json). The follow-up requires a separately built bounded
512-token pipeline parser; this attempt remains failed.
