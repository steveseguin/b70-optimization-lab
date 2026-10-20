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

## Clean-checkout portability correction

Remote CI found five additional historical links in four documents whose
ignored local targets had hidden their absence from Git. The
[additional Git-object proof](clean-checkout-link-proof.json) confirms that
all five targets were absent from the same baseline commit and that the
four document blobs are unchanged. These five exact links now have pinned
exceptions; their missing evidence has not been recovered.

One other frozen README is a mode-120000 absolute symlink into the original
host's `/home/steve` checkout. Its exact target text and SHA-256 are explicitly
baselined and reported as a known host-bound document. The checker never opens
that destination, even on the original host. Changing the symlink invalidates
the exception; any new host-bound document symlink fails by default.

`--all-tracked` now requires link destinations and resolved symlink targets to
belong to the Git index (including implied directories), in addition to existing
on disk. Ignored or untracked files can no longer make this scan pass locally
and fail on CI. Staged new files remain eligible. Frozen documents, symlinks and
experiment seals are unchanged.
