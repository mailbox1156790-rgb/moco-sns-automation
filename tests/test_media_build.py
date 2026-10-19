import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from moco.media import native


class NativeBuildTests(unittest.TestCase):
    def test_shared_runtime_aliases_use_one_canonical_cache_and_preserve_old_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            shared = base / "shared"
            shared.mkdir()
            old = shared / "swift-cache/old-pch"
            old.parent.mkdir()
            old.write_text("preserved")
            invocations = []

            def compile_stub(args, **kwargs):
                invocations.append((args, kwargs["env"]))
                Path(args[-1]).write_bytes(b"fixture-native-binary")

            with patch("moco.media.run", side_effect=compile_stub):
                for name in ["checkout", "release"]:
                    root = base / name
                    (root / "scripts").mkdir(parents=True)
                    source = root / "scripts/native.swift"
                    source.write_text("// fixture")
                    os.utime(source, (time.time() + 10, time.time() + 10))
                    (root / "var").symlink_to(shared, target_is_directory=True)
                    self.assertTrue(native(root).is_file())
            self.assertEqual(len(invocations), 2)
            for args, env in invocations:
                expected = str(shared / "swift-cache-canonical")
                self.assertEqual(args[args.index("-module-cache-path") + 1], expected)
                self.assertEqual(env["CLANG_MODULE_CACHE_PATH"], expected)
                self.assertEqual(env["SWIFT_MODULECACHE_PATH"], expected)
            self.assertEqual(old.read_text(), "preserved")
