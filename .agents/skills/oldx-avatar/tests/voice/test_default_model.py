"""Default TTS selection and model-bound voice safety; no network calls."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "voice"))
import common as C


class DefaultModelTests(unittest.TestCase):
    def test_defaults_to_plus(self):
        self.assertEqual(C.MODEL, "qwen-audio-3.1-tts-plus")

    def test_matching_voice_is_accepted(self):
        C.require_voice_model({"model": C.MODEL})

    def test_other_or_unknown_model_is_rejected(self):
        for model in ("qwen-audio-3.1-tts-flash", "speech-2.6-hd", None):
            with self.subTest(model=model), self.assertRaises(SystemExit) as error:
                C.require_voice_model({"model": model})
            self.assertEqual(error.exception.code, 5)


if __name__ == "__main__":
    unittest.main()
