# Historical documentation link baseline

The model-package closeout exposed 545 broken link occurrences in 91 existing
documents during the all-tracked scan. All were already broken in commit
`b9039197262ee538301db724c77cbb4ee7341c8f`; no new recipe links are exempted.
The separate four root README links introduced by this closeout were corrected.

[Git-object proof](historical-link-proof.json) records every affected document
SHA-256, Git blob, relative link, resolved missing target and baseline commit.
Each document was read with `git cat-file blob` and matched the working file
byte for byte. `git ls-tree -rz` established target absence, including implied
directories. This used Git objects without a branch or checkout.

[The broad-scan baseline](../2026-10-10/link-baseline.json) now contains 535
additional distinct document/link exceptions bound to those exact document
SHA-256 values. The checker continues to report these as known broken. Any
change to an excepted document invalidates its pin; new links remain errors.
This preserves frozen experiment and lineage bytes without claiming their
missing destinations have been recovered.
