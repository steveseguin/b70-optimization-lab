#!/usr/bin/env python3
"""Export committed canonical engine sources without building or running them."""
import argparse
import ast
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile


class BundleError(ValueError):
    pass


SYSTEM_HEADERS = set("algorithm array atomic bit cassert cctype cerrno cfenv charconv chrono cmath condition_variable csignal cstddef cstdint cstdio cstdlib cstring deque filesystem fstream functional iomanip iostream limits map memory mutex numeric optional ostream random set span sstream stdexcept string string_view thread tuple type_traits typeinfo unordered_map unordered_set utility variant vector fcntl.h poll.h sched.h unistd.h".split())
SYSTEM_PREFIXES = ("sycl/", "openssl/", "level_zero/", "sys/", "linux/")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE)


def safe_relative(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts or "\\" in name:
        raise BundleError("Unsafe relative path: " + name)
    return path


# Shared protocol modules are source, not copied lab launch artifacts. Include
# even the lazy persistent import so the archive has a complete literal closure.
PORTABLE_LIVE_RUNTIME=(
    'tools/pipeline_driver.py','tools/wavefront_driver.py','tools/live_wavefront_driver.py',
    'tools/persistent_live_suite.py','tools/persistent_wavefront_driver.py',
    'planning/wavefront.py','planning/live_draft.py')

# Each independently introduced entrypoint requires its complete literal and
# dynamic runtime closure. Historical source trees without that entrypoint keep
# their earlier requirements; no exported launcher/authority is substituted.
RING_RUNTIME=PORTABLE_LIVE_RUNTIME+(
    'tools/ring_driver.py','tools/ring_wire.py',
    'planning/ring_coordinator.py','planning/ring_contract.py')
RING_LIVE_RUNTIME=RING_RUNTIME+('tools/ring_live_driver.py','tools/ring_live_wire.py')
PENDING_RING_RUNTIME=RING_LIVE_RUNTIME+(
    'tools/pending_ring_live_driver.py','tools/pending_ring_live_wire.py')
ROLLING_RUNTIME=PENDING_RING_RUNTIME+(
    'tools/rolling_ring_driver.py','planning/rolling_provider/__init__.py',
    'planning/rolling_provider/arbiter.py','planning/rolling_provider/coordinator.py',
    'planning/rolling_provider/transport.py')
PERSISTENT_ROLLING_RUNTIME=ROLLING_RUNTIME+(
    'tools/persistent_rolling_driver.py','tools/persistent_rolling_suite.py')
DYNAMIC_RUNTIME_GROUPS=(
    ('deployment/portable_live.py',PORTABLE_LIVE_RUNTIME),
    ('tools/ring_driver.py',RING_RUNTIME),
    ('tools/ring_live_driver.py',RING_LIVE_RUNTIME),
    ('tools/pending_ring_live_driver.py',PENDING_RING_RUNTIME),
    ('tools/rolling_ring_driver.py',ROLLING_RUNTIME),
    ('tools/persistent_rolling_driver.py',PERSISTENT_ROLLING_RUNTIME))
# Planning research/tests import these CPU fixtures. Include only committed
# fixtures; an import of an untracked/missing fixture still fails closed below.
RING_TEST_SUPPORT=(
    'tools/test_wavefront_driver.py','tools/test_ring_driver.py','tools/test_ring_wire.py',
    'tools/test_ring_live_driver.py','tools/test_ring_live_wire.py',
    'tools/test_pending_ring_live_driver.py','tools/test_rolling_ring_driver.py',
    'tools/test_rolling_ring_socket.py','tools/test_persistent_rolling.py')


def python_closure(contents):
    edges=[];external=set()
    for name,data in sorted(contents.items()):
        if not name.endswith('.py'):continue
        try:tree=ast.parse(data,filename=name)
        except SyntaxError as error:raise BundleError('Invalid Python source: '+name) from error
        parent=PurePosixPath(name).parent
        def dependency(module,level=0):
            top=module.split('.')[0]
            if not level and top in sys.stdlib_module_names:
                external.add(top);return
            roots=[parent,PurePosixPath('.'),PurePosixPath('tools'),PurePosixPath('deployment'),PurePosixPath('planning'),PurePosixPath('release')]
            if level:
                root=parent
                for _ in range(level-1):root=root.parent
                roots=[root]
            relative=PurePosixPath(*module.split('.'))
            for root in roots:
                stem=root/relative
                for candidate in (str(stem)+'.py',str(stem/'__init__.py')):
                    if candidate in contents:
                        edges.append({'from':name,'to':candidate});return
            raise BundleError('Missing/untracked Python dependency in '+name+': '+module)
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                for alias in node.names:dependency(alias.name)
            elif isinstance(node,ast.ImportFrom):
                if node.module:dependency(node.module,node.level)
                else:
                    for alias in node.names:dependency(alias.name,node.level)
    return sorted(edges,key=lambda row:(row['from'],row['to'])),sorted(external)


def prepare(engine):
    engine = Path(engine).resolve()
    root = Path(git(engine, "rev-parse", "--show-toplevel").decode().strip())
    prefix = engine.relative_to(root).as_posix()
    commit = git(root, "rev-parse", "HEAD").decode().strip()
    tracked = set(git(root, "ls-files", "-z", "--", prefix).decode().split("\0")) - {""}
    source_names = sorted(name for name in tracked if name.startswith(prefix + "/src/"))
    required = [prefix + "/" + name for name in ("README.md", "build.py", "build-manifest.json")]
    optional = sorted(name for name in tracked if any(name.startswith(prefix + "/" + folder + "/")
                      for folder in ("planning", "release", "deployment", "profiles")))
    if b"from deployment.prepare import" in (engine / "build.py").read_bytes():
        required += [prefix + "/deployment/" + name for name in ("prepare.py", "bound.hpp.in")]
    dynamic = sorted({name for trigger,names in DYNAMIC_RUNTIME_GROUPS
                      if prefix+'/'+trigger in tracked for name in names})
    required += [prefix+'/'+name for name in dynamic]
    optional += [prefix+'/'+name for name in RING_TEST_SUPPORT if prefix+'/'+name in tracked]
    selected = sorted(set(source_names + required + optional))
    contents, inputs = {}, []
    if not source_names:
        raise BundleError("No tracked canonical sources")
    for name in selected:
        if name not in tracked:
            raise BundleError("Untracked required input: " + name)
        path = root / name
        if not path.is_file() or path.is_symlink() or path.resolve() != path:
            raise BundleError("Missing or non-regular input: " + name)
        data = path.read_bytes()
        try:
            original = git(root, "show", commit + ":" + name)
        except subprocess.CalledProcessError as error:
            raise BundleError("Input is not committed at source_commit: " + name) from error
        if original != data:
            raise BundleError("Input differs from source_commit: " + name)
        rel = path.relative_to(engine).as_posix()
        contents[rel] = data
        inputs.append({"path": name, "sha256": digest(data), "bytes": len(data)})
    source = {name[4:]: data for name, data in contents.items() if name.startswith("src/")}
    original_manifest = json.loads(contents["build-manifest.json"])
    units = original_manifest["translation_units"]
    for unit in units:
        safe_relative(unit["source"])
        obj = safe_relative(unit["object"])
        if len(obj.parts) != 1 or obj.suffix != ".o":
            raise BundleError("Unsupported output object path: " + str(obj))
        if unit["source"] not in source:
            raise BundleError("Missing/untracked translation unit: " + unit["source"])
    for asset in {*original_manifest.get("assets", {}), *original_manifest.get("files", {})}:
        safe_relative(asset)
        if asset not in source:
            raise BundleError("Missing/untracked declared source or asset: " + asset)
    local_edges, system_headers, supplemental = [], set(), []
    pending_sources = sorted(source.items())
    for name, data in pending_sources:
        if PurePosixPath(name).suffix not in {".cpp", ".hpp", ".h", ".inc"}:
            continue
        text = re.sub(r"/\*.*?\*/", "", data.decode(), flags=re.S)
        for line in text.splitlines():
            directive = re.match(r"\s*#\s*include\s+(.+)", line)
            if not directive:
                continue
            match = re.match(r'(["<])([^">]+)[">]\s*(?://.*)?$', directive[1])
            if not match:
                raise BundleError("Nonliteral or unsupported include in " + name + ": " + line)
            kind, target = match.groups()
            safe_relative(target)
            candidates = [(engine / "src" / PurePosixPath(name).parent / target).resolve(),
                          (engine / "src" / target).resolve()]
            found = None
            for candidate in candidates:
                try:
                    relative = candidate.relative_to(engine / "src").as_posix()
                except ValueError:
                    raise BundleError("Include escapes source tree: " + target)
                if relative in source:
                    found = relative
                    break
                if candidate.exists():
                    if relative not in source:
                        raise BundleError("Untracked include dependency: " + relative)
                    found = relative
                    break
            if found is None and target == "device_validation.hpp":
                # This project header is used by an inactive Host-only branch.
                # Include its exact committed bytes, never call it a system header.
                support = engine.parent / "gsq-rco-iq3s/integration/host-support/device_validation.hpp"
                support_rel = support.relative_to(root).as_posix()
                try:
                    git(root, "ls-files", "--error-unmatch", "--", support_rel)
                    original = git(root, "show", commit + ":" + support_rel)
                except subprocess.CalledProcessError as error:
                    raise BundleError("Missing committed supplemental header: " + support_rel) from error
                if not support.is_file() or support.is_symlink() or support.resolve() != support or support.read_bytes() != original:
                    raise BundleError("Missing or changed supplemental header: " + support_rel)
                contents["src/" + target] = source[target] = original
                inputs.append({"path": support_rel, "sha256": digest(original), "bytes": len(original)})
                supplemental.append({"input": support_rel, "archive_path": "src/" + target})
                pending_sources.append((target, original))
                found = target
            if found:
                local_edges.append({"from": name, "to": found})
            elif kind == '"':
                raise BundleError("Missing local include in " + name + ": " + target)
            elif target in SYSTEM_HEADERS or target.startswith(SYSTEM_PREFIXES):
                system_headers.add(target)
            else:
                raise BundleError("Unknown angle include is not an admitted system header: " + target)
    python_edges,python_system=python_closure(contents)
    # build.py consumes only these keys. Historical object locations and
    # consolidation provenance are not build dependencies or release inputs.
    manifest = {"schema": "ownrt.engine.source-build.v1",
                "compiler": original_manifest["compiler"],
                "translation_units": [{key: unit[key] for key in ("object", "source", "flags")}
                                      for unit in units],
                "link": original_manifest["link"]}
    contents["build-manifest.json"] = json_bytes(manifest)
    contents["SOURCE-README.md"] = (
        "# Own XPU runtime source snapshot\n\n"
        "Research source only. This archive is not a portable runtime release, a\n"
        "quality certification or a speed claim. No engine build or GPU work was\n"
        "performed by the bundler. Model weights, service adapters, loader authority\n"
        "files outside this tree, binaries, receipts and host state are excluded.\n\n"
        "The build entrypoint is build.py. Read SOURCE-MANIFEST.json for exact\n"
        "source hashes, compiler path, flags, system headers and unresolved runtime\n"
        "dependencies. With those prerequisites installed, the compile-only command\n"
        "is: python3 build.py /path/to/empty-build-directory --jobs 1\n\n"
        "The generated build-manifest.json retains every translation unit, its flags,\n"
        "link order and compiler settings; historical local object paths are omitted.\n"
        "Its original committed bytes are identified in the source input manifest.\n"
        "Original source bytes, including runtime defaults needing adaptation, are\n"
        "unchanged. Do not run a model merely because compilation succeeds.\n"
    ).encode()
    runtime_paths = []
    for name, data in sorted(source.items()):
        if PurePosixPath(name).suffix in {".cpp", ".hpp", ".h", ".inc"}:
            for line_no, line in enumerate(data.decode().splitlines(), 1):
                if re.search(r"/(?:home|mnt)/", line):
                    runtime_paths.append({"path": "src/" + name, "line": line_no})
    report = {
        "schema": "ownrt.engine.source-bundle.v1", "source_commit": commit,
        "engine_repository_path": prefix, "status": "research-source-only",
        "validation": {"tracked_committed_inputs": True, "literal_local_include_closure": True,
                       "literal_python_import_closure": True, "clean_source_build": False, "runtime_smoke": False,
                       "quality_gate": False, "portable_runtime": False},
        "inputs": inputs,
        "files": [{"path": name, "sha256": digest(data), "bytes": len(data)}
                  for name, data in sorted(contents.items())],
        "include_edges": local_edges, "external_system_headers": sorted(system_headers),
        "python_import_edges": python_edges, "python_standard_library_modules": python_system,
        "explicit_dynamic_python_dependencies": dynamic,
        "supplemental_source_inputs": supplemental,
        "toolchain_prerequisites": {"python": ">=3.10", "compiler": manifest["compiler"],
                                    "link_compiler": manifest["link"]["compiler"],
                                    "link_flags": manifest["link"]["flags"],
                                    "platform": "Linux; Intel oneAPI 2026.0 SYCL compiler, C++20 headers, OpenSSL and Level Zero development libraries"},
        "runtime_host_path_locations": runtime_paths,
        "missing": ["Clean supported-toolchain build from this archive",
                    "External model, tokenizer, loader-authority and service dependencies",
                    "Portable runtime paths, placement and host admission",
                    "Runtime smoke, independent quality and performance qualification",
                    "Public release upload and remote download/hash verification"],
    }
    contents["SOURCE-MANIFEST.json"] = json_bytes(report)
    return contents, report


def archive_bytes(contents):
    output = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0, compresslevel=9) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for name, data in sorted(contents.items()):
                safe_relative(name)
                member = tarfile.TarInfo("own-xpu-runtime-source/" + name)
                member.size = len(data)
                member.mode = 0o644
                member.uid = member.gid = member.mtime = 0
                archive.addfile(member, io.BytesIO(data))
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New archive path (.tar.gz); also writes PATH.manifest.json")
    parser.add_argument("--engine", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    contents, report = prepare(args.engine)
    data = archive_bytes(contents)
    companion = Path(str(args.output) + ".manifest.json")
    if args.output.exists() or companion.exists():
        raise BundleError("Output already exists; choose a new path")
    with args.output.open("xb") as stream:
        stream.write(data)
    report = {**report, "archive": {"sha256": digest(data), "bytes": len(data)}}
    with companion.open("xb") as stream:
        stream.write(json_bytes(report))
    print(json.dumps({"status": report["status"], "source_commit": report["source_commit"],
                      "files": len(contents), **report["archive"]}))


if __name__ == "__main__":
    main()
