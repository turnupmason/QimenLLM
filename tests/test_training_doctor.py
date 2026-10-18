"""Basic non-GPU doctor contracts; the full host probe runs only on user's computer."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('qimen_training_doctor', ROOT / 'scripts/doctor.py')
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)


class TrainingDoctorTests(unittest.TestCase):
    def test_no_manifest_does_not_claim_model_verified(self):
        self.assertFalse(doctor.model_report(None)['verified'])

    def test_model_revision_mismatch_and_missing_files_block(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'model.json'
            p.write_text('{"revision":"wrong","local_path":"'+d+'","files":{"nope":{"sha256":"x"}}}')
            actual = doctor.model_report(p)
            self.assertEqual(actual['status'], 'blocked')
            self.assertEqual(actual['missing_files'], ['nope'])

    def test_real_file_requires_explicit_hash_verification(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'dummy.bin'; f.write_bytes(b'sample')
            m = Path(d) / 'manifest.json'
            import hashlib, json
            m.write_text(json.dumps({'revision': doctor.PINNED, 'repo': 'mlx-community/Qwen3.8-27B-4bit', 'local_path': d,
                                    'files': {'dummy.bin': {'sha256': hashlib.sha256(b'sample').hexdigest()}}}))
            self.assertFalse(doctor.model_report(m)['verified'])
            self.assertTrue(doctor.model_report(m, True)['verified'])
            f.write_bytes(b'changed')
            self.assertEqual(doctor.model_report(m, True)['status'], 'blocked')

    def test_no_gpu_available_does_not_raise(self):
        with patch.object(doctor.shutil, 'which', return_value=None):
            self.assertFalse(doctor.command(['nvidia-smi'])['available'])


if __name__ == '__main__':
    unittest.main()
