"""B1 overlays must validate the device's native firmware family."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core import log
from core.overlay import SourceOverlay
from patches.shared.rootfs.b1_firmware import B1Firmware, B1_FILES, N61_FILES


class B1FirmwareTests(unittest.TestCase):
    def donor(self, root, model):
        props = root / f"usr/share/firmware/multitouch/{model}.mtprops"
        props.parent.mkdir(parents=True)
        props.write_bytes(b"native model")
        base = root / "usr/share/firmware/wifi/C-4345__s-B1"
        base.mkdir(parents=True)
        for name in N61_FILES if model == "N61" else B1_FILES:
            (base / name).write_bytes(b"firmware")
        ctx = SimpleNamespace(donor_dir=str(root), ssh=Mock(), verify_device_system=Mock())
        return ctx, base

    def test_native_families_reach_copy_without_renaming(self):
        for model, required in (("N56", B1_FILES), ("N61", N61_FILES)):
            with self.subTest(model=model), tempfile.TemporaryDirectory() as tmp:
                ctx, base = self.donor(Path(tmp), model)
                with patch.object(SourceOverlay, "apply") as copy:
                    B1Firmware().apply(ctx)
                    copy.assert_called_once_with(ctx, None)
                self.assertEqual({p.name for p in base.iterdir()}, set(required))

    def test_missing_or_empty_native_firmware_stops_before_copy(self):
        for model, required in (("N56", B1_FILES), ("N61", N61_FILES)):
            for missing in (True, False):
                with self.subTest(model=model, missing=missing), tempfile.TemporaryDirectory() as tmp:
                    ctx, base = self.donor(Path(tmp), model)
                    bad = base / required[0]
                    if missing:
                        bad.unlink()
                    else:
                        bad.write_bytes(b"")
                    with patch.object(SourceOverlay, "apply") as copy:
                        with self.assertRaises(log.Die) as error:
                            B1Firmware().apply(ctx)
                        self.assertIn(str(bad), error.exception.message)
                        copy.assert_not_called()

    def test_device_mode_checks_native_names(self):
        for model, required in (("N56", B1_FILES), ("N61", N61_FILES)):
            with self.subTest(model=model):
                ctx = SimpleNamespace(donor_dir=None, ssh=Mock(), verify_device_system=Mock())
                ctx.ssh.sh.side_effect = [model.encode() + b"\n", b""]
                with patch.object(SourceOverlay, "apply") as copy:
                    B1Firmware().apply(ctx)
                    copy.assert_called_once_with(ctx, None)
                command = ctx.ssh.sh.call_args.args[0]
                for name in required:
                    self.assertIn('/' + name + '"', command)
