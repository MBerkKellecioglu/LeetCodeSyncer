from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "leetcode_syncer.py"
SPEC = importlib.util.spec_from_file_location("leetcode_syncer", MODULE_PATH)
syncer = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(syncer)


class LeetCodeSyncerTests(unittest.TestCase):
    def test_available_local_port_returns_valid_port(self) -> None:
        port = syncer.available_local_port()
        self.assertGreater(port, 0)
        self.assertLessEqual(port, 65535)

    def test_load_config_reads_non_secret_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = pathlib.Path(temporary_directory)
            repository_path = temporary_path / "solutions"
            repository_path.mkdir()
            config_path = temporary_path / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "solutions_repository": str(repository_path),
                        "expected_remote": "https://github.com/example/solutions.git",
                        "git_name": "Example User",
                        "git_email": "12345+example@users.noreply.github.com",
                    }
                ),
                encoding="utf-8",
            )

            original_config_path = syncer.CONFIG_PATH
            try:
                syncer.CONFIG_PATH = config_path
                syncer.load_config()
            finally:
                syncer.CONFIG_PATH = original_config_path

            self.assertEqual(syncer.REPO, repository_path.resolve())
            self.assertEqual(
                syncer.EXPECTED_REMOTE,
                "https://github.com/example/solutions.git",
            )
            self.assertEqual(syncer.GIT_NAME, "Example User")

    def test_supported_languages_have_safe_extensions(self) -> None:
        for extension in syncer.LANG_EXT.values():
            self.assertNotIn("/", extension)
            self.assertNotIn("\\", extension)


if __name__ == "__main__":
    unittest.main()
