"""An obsolete high-cost training entry must fail before any dataset/model IO."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RetiredAuthorPilotTests(unittest.TestCase):
    def run_retired(self, arguments):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, '-I', str(ROOT / 'training/train_mac_author_lora.py'),
                 *arguments], cwd=directory, capture_output=True, text=True,
                timeout=10,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Retired author-quote pilot', result.stderr)
            self.assertIn('No model was loaded', result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_entry_fails_without_allocating_or_reading_a_model(self):
        self.run_retired([])

    def test_old_resume_arguments_cannot_restart_the_pilot(self):
        self.run_retired([
            '--model-receipt', 'absent-model', '--manifest', 'absent-release',
            '--dataset-root', 'absent-data', '--output', 'must-not-create',
            '--baseline-report', 'absent-baseline', '--resume', 'old-checkpoint',
        ])
