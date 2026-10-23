# Closed compiler-cache copy refused before mutation

The reviewed archive helper was attempted once on October 23. Its initial source
hash failed with PermissionError on a root-owned mode0600 cache file, before the
archive-start receipt, tar creation or deletion. Current service and external
storage checks had passed before the attempted hash. All original operation
paths were observed absent afterward. The refusal is preserved in the
[operation receipt](receipts/closed-restore-caches-copy-refusal.json).

Metadata and effective-access checks found 36 unreadable files totaling
582,155,334 bytes among 8,766 root-owned files, and 1,908 nonwritable immediate
unlink parents. Excluding unreadable files leaves only 488,189,754 logical bytes
and does not solve unlink permissions. This is a preparation gap, not an archive
or device failure. No permission, owner, service or machine setting changed.

The [frozen preparation](CLOSED-RESTORE-CACHES.md), original inventory and
[independent review](receipts/independent-closed-restore-caches-review.json)
remain unchanged. The next approach is a separately reviewed user coordinator
and narrowly fixed privileged filesystem child. Its candidate scope remains the
same eighteen closed restore20–28 compiler caches; active restore29, model files,
application logs and research results remain outside that scope. It must retain
separate verified-copy and prune operations, durable recovery mapping, current
service configuration checks and the external reserve. No successful archive,
reclaimed space or authorization for a device launch follows from this refusal.
