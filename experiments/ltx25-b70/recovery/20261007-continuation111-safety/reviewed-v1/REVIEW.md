# Reviewed v1: superseded CPU prototype

Superseded by ../conditioning_guard.py and its adjacent tests/README.

Independent review found two gaps: anchor/cache bindings were not refreshed after synchronized controller snapshots, and the busy flag covered only the native call so callbacks/snapshots could reenter the stage. No GPU or runtime qualification occurred. Preserve this exact prior source as the negative control.

- `conditioning_guard.py`: `bf0379fc9524757c628b23836c376fa82e8aa3653e08a521fe4a7a8a98baf39b`
- `test_conditioning_guard.py`: `c8cd95ab808e8dcbe1e313d0bd223617d28c7b92a6a0367763b73413f939a1ec`
- `README-stage-guard.md`: `9165659532cbc5ca26b29f72cd6b5852a65c730902219533cdc2f407a9a6ee09`
