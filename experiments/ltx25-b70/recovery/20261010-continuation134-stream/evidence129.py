"""Pinned-parent source transforms for packet129 evidence publication only."""


def transform_capture(raw):
    """Keep capture tensor/report bytes and gates; publish both output files last.

    /view can serve these files and the qualification action reads the tensor
    capture. The private same-directory name is never an advertised artifact.
    """
    text = raw.decode('utf-8')
    old_import = 'from safetensors.torch import save_file\n'
    old_write = """        save_file(tensors, str(out / 'tensors.safetensors'))
        (out / 'summary.json').write_text(json.dumps(report, indent=2) + '\\n')
"""
    new_write = """        final = out / 'tensors.safetensors'
        temporary = evidence_publication.temporary_name(final)
        try:
            save_file(tensors, str(temporary))
            evidence_publication.publish_file(temporary, final)
        finally:
            temporary.unlink(missing_ok=True)
        evidence_publication.publish_bytes(
            out / 'summary.json', (json.dumps(report, indent=2) + '\\n').encode('utf-8'))
"""
    if text.count(old_import) != 1 or text.count(old_write) != 1:
        raise RuntimeError('Packet129 capture writer parent differs')
    text = text.replace(old_import, old_import + 'import evidence_publication\n', 1)
    return text.replace(old_write, new_write, 1).encode('utf-8')


def transform_server(raw):
    """Deny private publication names even when /view knows their exact name.

    Check the resolved disk path as well as the normal filename path so asset
    hash lookup and annotated input/output directories share the same rule.
    """
    text = raw.decode('utf-8')
    old = "                if os.path.isfile(file):\n                    if 'preview' in request.rel_url.query:\n"
    new = """                # Packet129: private staging names are never HTTP evidence.
                if any(part.startswith('.') and part.endswith('.partial')
                       for part in os.path.realpath(file).split(os.sep)):
                    return web.Response(status=404)

                if os.path.isfile(file):
                    if 'preview' in request.rel_url.query:
"""
    if text.count(old) != 1:
        raise RuntimeError('Packet129 view route parent differs')
    return text.replace(old, new, 1).encode('utf-8')


def transform_launcher(raw):
    """Keep startup/fault JSON bytes, publish after fsync via packet-local code.

    The launcher's existing recursive packet verification happens before its
    first write_json call. Resolve the helper from this verified packet rather
    than an ambient import path; this transform never runs the launcher.
    """
    text = raw.decode('utf-8')
    old = """def write_json(path, value):
    with path.open('x') as handle:
        handle.write(json.dumps(value, indent=2) + '\\n')
"""
    new = """def write_json(path, value):
    publication = runpy.run_path(str(
        Path(__file__).resolve().parents[1] / 'source/scripts/evidence_publication.py'))
    publication['publish_bytes'](path, (json.dumps(value, indent=2) + '\\n').encode('utf-8'))
"""
    if text.count(old) != 1:
        raise RuntimeError('Packet129 startup writer parent differs')
    return text.replace(old, new, 1).encode('utf-8')
