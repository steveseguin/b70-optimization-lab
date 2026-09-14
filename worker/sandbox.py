"""Pinned source snapshots and a CPU-only, network-disabled coding sandbox.

The source repository is never mounted. There is no clone, worktree, or .git in
the editable snapshot. Stop the container before exporting its reviewable patch.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import stat
import subprocess
import tarfile
import time
import uuid


MAX_FILES = 50_000
MAX_SOURCE_BYTES = 2 * 1024 * 1024 * 1024
MAX_OUTPUT = 10_000
COMMAND_TIMEOUT = 120
COMPLETE = "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"
CHILD_ENV = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LC_ALL": "C.UTF-8"}


class SandboxError(RuntimeError):
    pass


def _run(args, *, cwd=None, timeout=120, check=True):
    return subprocess.run(args, cwd=cwd, env=CHILD_ENV, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout, check=check)


def _json_write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def _source_state(repo):
    def git(*args):
        return _run(["git", "-C", str(repo), *args]).stdout
    status = git("status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignore-submodules=none")
    return {"head": git("rev-parse", "HEAD").decode().strip(),
            "status_sha256": hashlib.sha256(status).hexdigest(),
            "clean": not status,
            "index_sha256": hashlib.sha256(git("ls-files", "--stage", "-z")).hexdigest()}


def _regular_tree(root):
    """Inventory without following links. Reject links and special files."""
    result = {}
    total = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(directory) / name
            info = path.lstat()
            relative = path.relative_to(root).as_posix()
            if name == ".git":
                raise SandboxError(".git is prohibited in snapshots: " + relative)
            if stat.S_ISDIR(info.st_mode):
                continue
            if not stat.S_ISREG(info.st_mode):
                raise SandboxError("symlink or special file prohibited: " + relative)
            total += info.st_size
            if total > MAX_SOURCE_BYTES or len(result) >= MAX_FILES:
                raise SandboxError("snapshot exceeds size or file-count limit")
            digest = hashlib.sha256()
            with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as file:
                opened = os.fstat(file.fileno())
                if opened.st_ino != info.st_ino or opened.st_dev != info.st_dev:
                    raise SandboxError("snapshot changed during inventory")
                for block in iter(lambda: file.read(1024 * 1024), b""):
                    digest.update(block)
            result[relative] = {"sha256": digest.hexdigest(), "bytes": info.st_size,
                                "mode": "100755" if info.st_mode & 0o111 else "100644"}
    return result


def safe_extract(archive, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    total = count = 0
    with tarfile.open(archive, "r:") as source:
        for member in source:
            parts = Path(member.name).parts
            if (not parts or Path(member.name).is_absolute() or ".." in parts
                    or ".git" in parts or "\\" in member.name):
                raise SandboxError("unsafe archive path: " + repr(member.name))
            target = destination.joinpath(*parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise SandboxError("archive links and special files are prohibited")
            total += member.size
            count += 1
            if total > MAX_SOURCE_BYTES or count > MAX_FILES:
                raise SandboxError("archive exceeds size or file-count limit")
            target.parent.mkdir(parents=True, exist_ok=True)
            stream = source.extractfile(member)
            with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                   0o755 if member.mode & 0o111 else 0o644), "wb") as output:
                shutil.copyfileobj(stream, output)


def prepare_snapshot(repo, commit, run_dir):
    """Create a source snapshot from an exact commit in a clean repository."""
    repo, run_dir = Path(repo).resolve(), Path(run_dir).absolute()
    for ancestor in (run_dir, *run_dir.parents):
        if ancestor.is_symlink():
            raise SandboxError("snapshot run directory cannot use symlink ancestors")
    run_dir = run_dir.resolve()
    if run_dir.is_relative_to(repo):
        raise SandboxError("snapshot run directory must be outside the source repository")
    top = _run(["git", "-C", str(repo), "rev-parse", "--show-toplevel"]).stdout.decode().strip()
    if Path(top).resolve() != repo:
        raise SandboxError("source repo must name its repository root")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise SandboxError("source commit must be an exact lowercase 40-hex Git commit")
    source = _source_state(repo)
    if not source["clean"]:
        raise SandboxError("source repository must be clean")
    actual = _run(["git", "-C", str(repo), "rev-parse", "--verify", commit + "^{commit}"]).stdout.decode().strip()
    if actual != commit:
        raise SandboxError("source commit did not resolve exactly")
    # Check blob types/sizes before writing an archive; reject submodules too.
    tree = _run(["git", "-C", str(repo), "ls-tree", "-r", "-l", "-z", commit]).stdout
    total = count = 0
    for entry in tree.split(b"\0"):
        if not entry:
            continue
        info, _ = entry.split(b"\t", 1)
        mode, kind, _, size = info.split()
        if mode not in (b"100644", b"100755") or kind != b"blob":
            raise SandboxError("source snapshot cannot contain symlinks or submodules")
        count += 1
        total += int(size)
    if count > MAX_FILES or total > MAX_SOURCE_BYTES:
        raise SandboxError("source snapshot exceeds size or file-count limit")
    run_dir.mkdir(parents=True, exist_ok=False)
    archive = run_dir / "source.tar"
    with archive.open("xb") as output:
        subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", commit],
                       stdout=output, stderr=subprocess.PIPE, env=CHILD_ENV, timeout=120, check=True)
    digest = hashlib.sha256()
    with archive.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    archive_sha = digest.hexdigest()
    safe_extract(archive, run_dir / "baseline")
    shutil.copytree(run_dir / "baseline", run_dir / "workspace", symlinks=False)
    metadata = {"schema": "neural.download.worker.snapshot.v1", "source_repo": str(repo),
                "source_commit": commit, "source_state": source,
                "source_archive_sha256": archive_sha,
                "source_tree_sha256": hashlib.sha256(tree).hexdigest(),
                "baseline": _regular_tree(run_dir / "baseline")}
    if _source_state(repo) != source:
        raise SandboxError("source repository changed while snapshotting")
    _json_write(run_dir / "snapshot.json", metadata)
    return metadata


def _git_quote(path):
    # Git's quoted path grammar uses octal UTF-8 bytes, not JSON \u escapes.
    result = '"'
    for byte in path.encode("utf-8", errors="surrogateescape"):
        if byte in (34, 92):
            result += "\\" + chr(byte)
        elif 32 <= byte < 127:
            result += chr(byte)
        else:
            result += "\\%03o" % byte
    return result + '"'


def export_patch(run_dir):
    """Export text, binary, add/delete and executable-mode changes after stop."""
    run_dir = Path(run_dir).resolve()
    metadata = json.loads((run_dir / "snapshot.json").read_text())
    state_path = run_dir / "sandbox.json"
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if state.get("container_id") and not state.get("stopped"):
            raise SandboxError("stop the sandbox before exporting its patch")
    baseline = _regular_tree(run_dir / "baseline")
    if baseline != metadata["baseline"]:
        raise SandboxError("baseline was changed")
    workspace = _regular_tree(run_dir / "workspace")
    if _source_state(metadata["source_repo"]) != metadata["source_state"]:
        raise SandboxError("original source repository changed")
    changed, patches = [], []
    for name in sorted(set(baseline) | set(workspace)):
        before, after = baseline.get(name), workspace.get(name)
        if before == after:
            continue
        old = run_dir / "baseline" / name if before else Path("/dev/null")
        new = run_dir / "workspace" / name if after else Path("/dev/null")
        diff = _run(["git", "diff", "--no-index", "--binary", "--no-ext-diff", "--no-renames",
                     "--", str(old), str(new)], check=False)
        if diff.returncode not in (0, 1):
            raise SandboxError("git diff failed: " + diff.stderr.decode(errors="replace"))
        lines = diff.stdout.splitlines(keepends=True)
        normalized = []
        in_body = False
        for line in lines:
            if line.startswith(b"@@") or line.startswith(b"GIT binary patch"):
                in_body = True
            if not in_body and line.startswith(b"diff --git "):
                line = ("diff --git " + _git_quote("a/" + name) + " " + _git_quote("b/" + name) + "\n").encode()
            elif not in_body and line.startswith(b"--- "):
                line = ("--- " + (_git_quote("a/" + name) if before else "/dev/null") + "\n").encode()
            elif not in_body and line.startswith(b"+++ "):
                line = ("+++ " + (_git_quote("b/" + name) if after else "/dev/null") + "\n").encode()
            normalized.append(line)
        patches.append(b"".join(normalized))
        changed.append({"path": name, "change": "added" if before is None else "deleted" if after is None else "modified",
                        "before": before, "after": after})
    patch = b"".join(patches)
    (run_dir / "changes.patch").write_bytes(patch)
    receipt = {"source_commit": metadata["source_commit"], "source_archive_sha256": metadata["source_archive_sha256"],
               "source_repo_unchanged": True, "baseline_unchanged": True,
               "patch_sha256": hashlib.sha256(patch).hexdigest(), "changed_files": changed}
    _json_write(run_dir / "changes.json", receipt)
    return receipt


def _bounded_command(args, timeout):
    """Drain output while retaining at most MAX_OUTPUT bytes, with a wall bound."""
    child = subprocess.Popen(args, env=CHILD_ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             start_new_session=True)
    saved, received = bytearray(), 0
    deadline = time.monotonic() + timeout
    selector = selectors.DefaultSelector()
    selector.register(child.stdout, selectors.EVENT_READ)
    timed_out = False
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                os.killpg(child.pid, signal.SIGKILL)
                break
            for key, _ in selector.select(min(remaining, 0.5)):
                data = os.read(key.fileobj.fileno(), 65536)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                received += len(data)
                saved.extend(data[:max(0, MAX_OUTPUT - len(saved))])
        try:
            code = child.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(child.pid, signal.SIGKILL)
            code = child.wait(timeout=5)
    finally:
        selector.close()
        child.stdout.close()
    output = saved.decode("utf-8", errors="replace")
    if received > len(saved):
        notice = f"\n[output truncated; received {received} bytes]"
        output = output[:MAX_OUTPUT - len(notice)] + notice
    return {"output": output, "returncode": code, "timed_out": timed_out,
            "output_bytes_received": received}


class DockerSandbox:
    def __init__(self, run_dir, image, acceptance_dir=None, docker="docker"):
        if not re.fullmatch(r"(?:sha256:[0-9a-f]{64}|[^@\s]+@sha256:[0-9a-f]{64})", image):
            raise SandboxError("sandbox image must be an immutable digest or image ID")
        self.run_dir = Path(run_dir).resolve()
        if not (self.run_dir / "snapshot.json").is_file():
            raise SandboxError("prepare_snapshot must run first")
        if (self.run_dir / "sandbox.json").exists():
            raise SandboxError("sandbox state already exists; refusing reuse")
        self.image, self.docker = image, docker
        self.acceptance_dir = Path(acceptance_dir).resolve() if acceptance_dir else None
        if self.acceptance_dir:
            _regular_tree(self.acceptance_dir)
        for path in (self.run_dir / "workspace", self.acceptance_dir):
            if path and any(c in str(path) for c in ",\n\r"):
                raise SandboxError("mount path contains unsupported separator")
        if os.getuid() == 0:
            raise SandboxError("run the worker as a normal non-root user")
        self.name = "local-coding-worker-" + uuid.uuid4().hex
        self.owner = uuid.uuid4().hex
        self.container_id = None
        self.image_id = None
        self.stopped = False
        self.aborted = False
        self.stop_attempted = False

    def _save(self):
        _json_write(self.run_dir / "sandbox.json", self.serialize())

    def _docker(self, *args, **kwargs):
        return _run([self.docker, *args], **kwargs)

    def create_command(self):
        args = [self.docker, "create", "--name", self.name, "--label", "local-coding-worker.owner=" + self.owner,
                "--network", "none", "--read-only", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges", "--pids-limit", "128",
                "--cpus", "2", "--memory", "2g", "--memory-swap", "2g",
                "--user", f"{os.getuid()}:{os.getgid()}", "--init", "--workdir", "/workspace",
                "--mount", f"type=bind,src={self.run_dir / 'workspace'},dst=/workspace",
                "--tmpfs", "/tmp:rw,exec,nosuid,nodev,size=268435456,mode=1777",
                "--env", "HOME=/tmp", "--env", "PATH=/usr/local/bin:/usr/bin:/bin",
                "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "GIT_CONFIG_NOSYSTEM=1"]
        if self.acceptance_dir:
            args += ["--mount", f"type=bind,src={self.acceptance_dir},dst=/acceptance,readonly"]
        return args + ["--entrypoint", "/bin/sh", self.image, "-c", "while :; do sleep 3600; done"]

    def _verify_identity(self):
        if not self.container_id:
            raise SandboxError("no owned container ID")
        result = self._docker("inspect", self.container_id)
        rows = json.loads(result.stdout)
        if len(rows) != 1:
            raise SandboxError("container inspect did not return one container")
        row = rows[0]
        if (row.get("Id") != self.container_id or row.get("Name") != "/" + self.name
                or row.get("Image") != self.image_id
                or row.get("Config", {}).get("Labels", {}).get("local-coding-worker.owner") != self.owner):
            raise SandboxError("container ownership identity mismatch; refusing action")
        return row

    def start(self):
        if self.container_id or self.stopped or self.aborted:
            raise SandboxError("sandbox cannot be started twice")
        image = json.loads(self._docker("image", "inspect", self.image).stdout)
        if len(image) != 1 or not re.fullmatch(r"sha256:[0-9a-f]{64}", image[0].get("Id", "")):
            raise SandboxError("unable to resolve immutable local image ID")
        self.image_id = image[0]["Id"]
        result = _run(self.create_command())
        candidate_id = result.stdout.decode().strip()
        if not re.fullmatch(r"[0-9a-f]{64}", candidate_id):
            raise SandboxError("docker create did not return an exact container ID")
        self.container_id = candidate_id
        self._save()
        self._verify_identity()
        self._docker("start", self.container_id)
        if not self._verify_identity().get("State", {}).get("Running"):
            self.aborted = True
            self._save()
            raise SandboxError("sandbox did not enter running state")
        self._save()
        return self

    def execute(self, action):
        command = action.get("command") if isinstance(action, dict) else None
        if not isinstance(command, str) or not command or "\0" in command:
            raise SandboxError("action requires a nonempty command string")
        if self.aborted or self.stopped:
            raise SandboxError("sandbox is stopped or aborted")
        if not self._verify_identity().get("State", {}).get("Running"):
            self.aborted = True
            self._save()
            raise SandboxError("sandbox is no longer running")
        if command == COMPLETE:
            from minisweagent.exceptions import Submitted
            submission = "Task submitted; review the exported patch."
            raise Submitted({"role": "exit", "content": submission,
                             "extra": {"exit_status": "Submitted", "submission": submission}})
        args = [self.docker, "exec", "--workdir", "/workspace", self.container_id,
                "/usr/bin/timeout", "--signal=TERM", "--kill-after=5", str(COMMAND_TIMEOUT),
                "/bin/bash", "--noprofile", "--norc", "-c", command]
        result = _bounded_command(args, COMMAND_TIMEOUT + 15)
        if result["timed_out"] or result["returncode"] in (124, 137):
            self.aborted = True
            self._save()
            self.stop()
            raise SandboxError("command timed out; task aborted and owned sandbox stopped")
        return result

    def stop(self):
        if self.stopped:
            return
        if not self.container_id:
            self.stopped = True
            self._save()
            return
        if self.stop_attempted:
            raise SandboxError("single owned stop already attempted; no automatic retry")
        row = self._verify_identity()
        self.stop_attempted = True
        self._save()
        if row.get("State", {}).get("Running"):
            self._docker("stop", "--time", "10", self.container_id, timeout=20)
        if self._verify_identity().get("State", {}).get("Running"):
            raise SandboxError("owned sandbox still running after stop")
        self.stopped = True
        self._save()

    def get_template_vars(self, **kwargs):
        return {"cwd": "/workspace", "working_dir": "/workspace", "platform": "Linux",
                "system": "Linux", "shell": "/bin/bash", "network": "none", **kwargs}

    def serialize(self):
        return {"type": "local-cpu-docker", "run_dir": str(self.run_dir), "image": self.image,
                "image_id": self.image_id, "container_name": self.name, "container_id": self.container_id,
                "owner": self.owner, "stopped": self.stopped, "aborted": self.aborted,
                "stop_attempted": self.stop_attempted,
                "limits": {"cpus": 2, "memory_bytes": 2147483648, "pids": 128,
                           "command_timeout_s": COMMAND_TIMEOUT, "output_bytes": MAX_OUTPUT},
                "network": "none", "root_filesystem_readonly": True}

    def export_patch(self):
        if not self.stopped:
            raise SandboxError("stop the sandbox before exporting its patch")
        return export_patch(self.run_dir)
