from io import BytesIO
from pathlib import Path
import tempfile
import unittest

from macos_port.download_assets import download_asset, AssetError, _blob_hasher, ASSETS, verify_asset


class AssetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.payload = b'test image bytes'
        digest = _blob_hasher(len(self.payload))
        digest.update(self.payload)
        self.entry = ('assets/images/test.png', len(self.payload), digest.hexdigest())

    def test_valid_download_is_atomic_and_reused(self):
        self.assertTrue(download_asset(self.root, self.entry, opener=lambda *a, **k: BytesIO(self.payload)))
        def no_network(*args, **kwargs): raise AssertionError('Already verified; must not download')
        self.assertFalse(download_asset(self.root, self.entry, opener=no_network))

    def test_invalid_payload_does_not_replace_existing_file(self):
        target = self.root / self.entry[0]
        target.parent.mkdir(parents=True)
        target.write_bytes(b'existing file')
        with self.assertRaises(AssetError):
            download_asset(self.root, self.entry, opener=lambda *a, **k: BytesIO(b'bad'))
        self.assertEqual(target.read_bytes(), b'existing file')
        self.assertEqual(list(target.parent.glob('*.download')), [])

    def test_path_traversal_rejected_before_download(self):
        with self.assertRaises(AssetError):
            download_asset(self.root, ('assets/../../escape', self.entry[1], self.entry[2]))

    def test_all_bundled_assets_match_pinned_tree(self):
        root = Path(__file__).resolve().parents[1]
        for path, size, digest in ASSETS:
            with self.subTest(path=path):
                self.assertTrue(verify_asset(root/path, size, digest))


if __name__ == '__main__': unittest.main()
