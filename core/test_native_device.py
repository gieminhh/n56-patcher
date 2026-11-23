from pathlib import Path
import json
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.native_device import DEVICES, native_device
from core.flow import Flow
from core import slots, slots_cli, log
from patches.shared.rootfs.n56_model_files import RootfsN56ModelFiles
from patches.ios15.rootfs.camera_config import CameraConfig


class NativeDeviceTests(unittest.TestCase):
    def test_n61_donor_overrides_legacy_target_name_without_mutating_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            props = Path(tmp) / 'usr/share/firmware/multitouch/N61.mtprops'
            props.parent.mkdir(parents=True); props.write_bytes(b'native')
            ctx = SimpleNamespace(donor_dir=tmp, t={'device': {'model': 'n56ap'}})
            self.assertEqual(native_device(ctx).model, 'N61')
            self.assertEqual(ctx.t['device']['model'], 'n56ap')
            for overlay in (RootfsN56ModelFiles(), CameraConfig()):
                for item in overlay.items_for(ctx):
                    self.assertNotIn('N56', item.source)
                    self.assertNotIn('N56', item.dest)
            self.assertIn('N56', RootfsN56ModelFiles.items[0].source)

    def test_explicit_n61_and_default_n56(self):
        self.assertEqual(native_device(SimpleNamespace()).model, 'N56')
        self.assertEqual(native_device(SimpleNamespace(native_model='n61ap')).model, 'N61')
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            native_device(SimpleNamespace(native_model='n66ap'))

    def test_mixed_donor_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'usr/share/firmware/multitouch'; root.mkdir(parents=True)
            for model in DEVICES:
                (root / (model + '.mtprops')).write_bytes(b'native')
            with self.assertRaisesRegex(ValueError, 'both'):
                native_device(SimpleNamespace(donor_dir=tmp))

    def test_boot_identity_checks_physical_n61_instead_of_legacy_target_name(self):
        flow = Flow.__new__(Flow)
        flow.identity_check = True
        flow.ctx = SimpleNamespace(native_model='N61', tool=lambda _: 'irecovery',
                                   t={'device': {'model': 'n56ap', 'ecid': ''}})
        with patch('core.flow.run', return_value=SimpleNamespace(stdout=b'MODEL: n61ap\n')):
            flow._identity_guard()
        with patch('core.flow.run', return_value=SimpleNamespace(stdout=b'MODEL: n56ap\n')):
            with self.assertRaises(log.Die):
                flow._identity_guard()

    def test_boot_hash_and_reuse_distinguish_native_model(self):
        a = slots_cli._boot_parts_from_manifest({'native_model': 'N56'})
        b = slots_cli._boot_parts_from_manifest({'native_model': 'N61'})
        self.assertNotEqual(slots.boot_inputs_sha(a), slots.boot_inputs_sha(b))
        with tempfile.TemporaryDirectory() as work:
            target = {'name': 'n56-ios15', 'version': 'ios15', 'mounts': {}, 'bootargs': ''}
            flow = Flow.__new__(Flow)
            flow.ctx = SimpleNamespace(native_model='N61', t=target, installation=Mock(),
                                       wk=lambda p: str(Path(work) / p))
            flow.sel = {}
            boot = {'target': target['name'], 'mounts': {}, 'selection': {}, 'bootargs': ''}
            for model, expected in (('N56', False), ('N61', True)):
                boot['native_model'] = model
                Path(flow.ctx.wk('boot.json')).write_text(json.dumps(boot))
                self.assertEqual(flow._boot_matches_layout(), expected)
