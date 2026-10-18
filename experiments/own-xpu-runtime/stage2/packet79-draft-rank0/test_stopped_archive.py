"""Only the exact retained failure is exempt from the started-chain guard."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import stopped_archive as archive
from storage import B


class StoppedArchive(unittest.TestCase):
    def test_exact_archive_passes(self):
        archive.require_fresh_chain(B)
        self.assertTrue((B/archive.ARCHIVE/'STOP').exists())

    def test_active_and_unknown_archives_refused(self):
        for name in ('device-cards01-a', 'device-cards01-b-k2fail-other'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                (Path(tmp)/name).mkdir()
                with self.assertRaisesRegex(ValueError, 'selection frozen'):
                    archive.require_fresh_chain(Path(tmp))

    def test_modified_pin_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pin = json.loads((archive.P/'archived-chains.json').read_text())
            pin.update(manifest=str(archive.P/pin['manifest']), sha256='0'*64)
            (root/'archived-chains.json').write_text(json.dumps(pin))
            with patch.object(archive, 'P', root), self.assertRaisesRegex(ValueError, 'manifest changed'):
                archive.verify_archive(B/archive.ARCHIVE)


if __name__ == '__main__':
    unittest.main()
