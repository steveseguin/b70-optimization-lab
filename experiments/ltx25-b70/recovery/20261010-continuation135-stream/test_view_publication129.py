"""Actual /view handler CPU races; no listener, network, devices or live paths."""
import ast
import asyncio
import mimetypes
import os
from pathlib import Path
import tempfile
import threading
import types
import unittest

from aiohttp import web
import evidence129
import evidence_publication

PARENT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-128')


class ViewPublication129(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ltx129-view-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.original = (PARENT / 'source/server.py').read_bytes()
        tree = ast.parse(evidence129.transform_server(self.original))
        handler = next(node for node in ast.walk(tree)
                       if isinstance(node, ast.AsyncFunctionDef) and node.name == 'view_image')
        handler.decorator_list = []
        module = ast.Module(body=[handler], type_ignores=[])
        folder_paths = types.SimpleNamespace(
            annotated_filepath=lambda name: (name, None),
            get_directory_by_type=lambda kind: str(self.root),
            is_dangerous_content_type=lambda content_type: False)
        self.resolved = None
        namespace = dict(os=os, web=web, folder_paths=folder_paths, mimetypes=mimetypes,
                         self=types.SimpleNamespace(asset_manager=types.SimpleNamespace(enabled=True),
                             user_manager=types.SimpleNamespace(get_request_user_id=lambda req: 'cpu')),
                         resolve_hash_to_path=lambda value: self.resolved)
        exec(compile(ast.fix_missing_locations(module), '<actual-view129>', 'exec'), namespace)
        self.route = namespace['view_image']

    def get(self, filename, subfolder=None):
        query = {'filename': filename}
        if subfolder is not None:
            query['subfolder'] = subfolder
        request = types.SimpleNamespace(rel_url=types.SimpleNamespace(query=query), headers={})
        return asyncio.run(self.route(request))

    def race(self, filename):
        final = self.root / filename
        temporary = evidence_publication.temporary_name(final)
        midwrite, release = threading.Event(), threading.Event()
        errors = []
        def writer():
            try:
                with temporary.open('xb') as stream:
                    stream.write(b'first-half')
                    stream.flush()
                    midwrite.set()
                    if not release.wait(3):
                        raise TimeoutError('route did not finish')
                    stream.write(b'-second-half')
                evidence_publication.publish_file(temporary, final)
            except BaseException as error:
                errors.append(error)
        thread = threading.Thread(target=writer)
        thread.start()
        try:
            self.assertTrue(midwrite.wait(3))
            self.assertEqual(self.get(filename).status, 404)
            self.assertEqual(self.get(temporary.name).status, 404)
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        response = self.get(filename)
        self.assertEqual(response.status, 200)
        self.assertIsInstance(response, web.FileResponse)
        self.assertEqual(Path(response._path).read_bytes(), b'first-half-second-half')

    def test_preview_mp4_midwrite(self):
        self.race('preview_00001_.mp4')

    def test_capture_safetensors_midwrite(self):
        self.race('tensors.safetensors')

    def test_capture_summary_midwrite(self):
        self.race('summary.json')

    def test_hash_alias_to_private_staging_file_is_denied(self):
        path = self.root / '.preview.mp4.partial'
        path.write_bytes(b'partial')
        self.resolved = types.SimpleNamespace(abs_path=str(path), download_name='alias.mp4',
                                               content_type='video/mp4')
        self.assertEqual(self.get('blake3:private').status, 404)

    def test_staging_directory_is_denied(self):
        path = self.root / '.capture.partial'
        path.mkdir()
        (path / 'summary.json').write_bytes(b'partial')
        self.assertEqual(self.get('summary.json', path.name).status, 404)

    def test_symlink_alias_to_private_staging_file_is_denied(self):
        path = self.root / '.preview.mp4.partial'
        path.write_bytes(b'partial')
        (self.root / 'alias.mp4').symlink_to(path)
        self.assertEqual(self.get('alias.mp4').status, 404)

    def test_unknown_server_parent_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'parent differs'):
            evidence129.transform_server(self.original.replace(b'if os.path.isfile(file):', b'if True:'))


if __name__ == '__main__':
    unittest.main()
