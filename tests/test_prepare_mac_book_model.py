"""Exercise offline pinned MLX model preparation without downloading any weights."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('qimen_prepare_mac_model', ROOT/'scripts/prepare_mac_book_model.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class PrepareMacModelTests(unittest.TestCase):
    def fixture(self, base, symlinks=False):
        root = base/'repo'
        (root/'data/provenance').mkdir(parents=True)
        (root/'work').mkdir()
        source = base/'cache'
        source.mkdir()
        files = {}
        for n in range(15):
            name = f'part-{n}.bin'
            data = f'bytes-{n}'.encode()
            files[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
            if symlinks:
                blobs = base/'blobs'
                blobs.mkdir(exist_ok=True)
                blob = blobs/name
                blob.write_bytes(data)
                (source/name).symlink_to(blob)
            else:
                (source/name).write_bytes(data)
        (root/'data/provenance/qwen38_27b_download_v1.json').write_text(
            json.dumps({'repo': mod.REPO, 'revision': mod.REVISION, 'files': files}))
        return root, source, files

    def test_direct_files_create_manifest_no_duplicate(self):
        with tempfile.TemporaryDirectory() as d:
            root, source, files = self.fixture(Path(d))
            created = mod.prepare(root, explicit=source)
            self.assertEqual(created['status'], 'created_verified')
            self.assertFalse(created['hardlinked'])
            self.assertEqual(created['files'], 15)
            self.assertEqual(mod.prepare(root, explicit=source)['status'], 'existing_verified')
            self.assertFalse(list((root/'work').rglob('*.bin')))

    def test_huggingface_symlinks_materialize_hardlinks_not_copies(self):
        with tempfile.TemporaryDirectory() as d:
            root, source, files = self.fixture(Path(d), symlinks=True)
            created = mod.prepare(root, explicit=source)
            self.assertTrue(created['hardlinked'])
            target = Path(created['model'])
            self.assertTrue(mod.contained_without_symlinks(target, files))
            for name in files:
                self.assertTrue(os.path.samefile(source/name, target/name))
            self.assertEqual(mod.prepare(root)['status'], 'existing_verified')

    def test_hash_mismatch_never_creates_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            root, source, files = self.fixture(Path(d))
            (source/'part-0.bin').write_bytes(b'wrong')
            with self.assertRaises(FileNotFoundError):
                mod.prepare(root, explicit=source)
            self.assertFalse((root/'work/mac-book-model-manifest-v1.json').exists())

    def test_existing_manifest_identity_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            root, source, files = self.fixture(Path(d))
            manifest = root/'work/mac-book-model-manifest-v1.json'
            manifest.write_text('{"revision":"wrong"}')
            with self.assertRaises(ValueError):
                mod.prepare(root, explicit=source)
            self.assertEqual(manifest.read_text(), '{"revision":"wrong"}')

    def test_candidate_search_uses_pinned_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            pinned = home/'.cache/huggingface/hub'/mod.MODEL_NAME/'snapshots'/mod.REVISION
            pinned.mkdir(parents=True)
            self.assertEqual(mod.candidate_directories(root=home, home=home, environ={}), [pinned])


if __name__ == '__main__':
    unittest.main()
