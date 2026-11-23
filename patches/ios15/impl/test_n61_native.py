"""Host-only N61 checks. Set N61_DONOR to a verified 16H88 snapshot for real checks."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from core.context import load_target
from core.native_device import DEVICES
from core.patch import select
from patches.ios15.impl import fixtures
from patches.ios15.impl.rootfs import bluetoothd, camera_config, motion_platform


class NativeBinaryProfileTests(unittest.TestCase):
    def test_bluetooth_product_prefix_and_immediate_tail_are_both_n61(self):
        self.assertEqual(bluetoothd.patches_for('N56'), bluetoothd.PATCHES)
        edits = bluetoothd.patches_for('N61')
        product = DEVICES['N61'].product_type
        for i in (0, 2):
            self.assertEqual(edits[i][2], product[:16])
        for i in (1, 3):
            code = edits[i][2]
            low = (int.from_bytes(code[:4], 'little') >> 5) & 0xffff
            high = (int.from_bytes(code[4:], 'little') >> 5) & 0xffff
            self.assertEqual((low | (high << 16)).to_bytes(4, 'little'), product[16:])
        self.assertEqual(edits[4:], bluetoothd.PATCHES[4:])

    def test_n61_camera_name_does_not_alias_n56(self):
        self.assertEqual(camera_config.avgestalt_edits('N61')[0][2], b'N61-N66m')
        self.assertEqual(camera_config.avgestalt_edits('N56'), camera_config.AVGESTALT_EDITS)

    def test_n61_motion_uses_35_instead_of_34(self):
        n56 = motion_platform.locationd_edits('N56')
        n61 = motion_platform.locationd_edits('N61')
        self.assertEqual([row[0] for row in n61[:2]], [row[0] + 4 for row in n56[:2]])
        self.assertEqual(n61[2:], n56[2:])


class RealN61Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        donor = os.environ.get('N61_DONOR')
        if not donor:
            raise unittest.SkipTest('set N61_DONOR to a verified N61 16H88 snapshot')
        cls.donor = Path(donor).resolve()
        if not (cls.donor / 'usr/share/firmware/multitouch/N61.mtprops').is_file():
            raise ValueError('N61_DONOR has no N61.mtprops')
        cls.j96 = fixtures.rootfs('j96')

    def context(self, work):
        return SimpleNamespace(donor_dir=str(self.donor), t=load_target('n56-ios15'),
                               derived_root=str(fixtures.derived_root()), patch_reports={},
                               wk=lambda p: str(Path(work) / p), verify_device_system=Mock(),
                               mount_rootfs=lambda p: str(self.j96) if p == 'j96' else self.fail(p))

    def test_selected_native_overlay_sources_all_exist(self):
        with tempfile.TemporaryDirectory() as work:
            ctx = self.context(work)
            missing = []
            for overlay in select(ctx.t)['rootfs']:
                for item in overlay.items_for(ctx) if hasattr(overlay, 'items_for') else ():
                    if item.source.startswith('device_s1:'):
                        rel = item.source.split(':', 1)[1]
                        if not (self.donor / rel).exists():
                            missing.append((overlay.id, rel))
            self.assertEqual(missing, [])

    def test_camera_derives_native_n61_plists_and_cache_plan(self):
        from patches.ios15.rootfs.camera_config import CameraConfig
        with tempfile.TemporaryDirectory() as work:
            ctx = self.context(work)
            overlay = CameraConfig()
            result = Path(overlay.derive(ctx, 'session', overlay.items_for(ctx)[0]))
            report = ctx.patch_reports[overlay.id]
            self.assertIn('/N61', report['source'])
            self.assertIn('/N61', report['destination'])
            self.assertTrue(all(d['multistream_preserved'] for d in report['devices']))
            original = self.donor / camera_config.SOURCE.replace('N56', 'N61') / 'CameraSetup.plist'
            self.assertEqual((result.parent / original.name).read_bytes(), original.read_bytes())
            self.assertTrue(overlay.signing_inputs(ctx)['cache_plans'][0]['trustcache_entries'])

    def test_thermal_imports_n61_class_and_native_product_id_and_signs(self):
        from patches.ios15.impl.rootfs.thermal import build as thermal
        with tempfile.TemporaryDirectory() as work:
            ctx = self.context(work)
            result = thermal.prepare(ctx)
            daemon = Path(result['daemon'])
            model = json.loads((daemon.parent / 'inline-model.json').read_text())
            report = ctx.patch_reports[thermal.PATCH_ID]
            self.assertEqual(model['class_name'], DEVICES['N61'].thermal_class)
            self.assertEqual(model['product_id'], '0x43a35')
            self.assertEqual(model['native_filter_state'], '-1.0f,-1')
            self.assertIn('N61AP', report['required_config']['dest'])
            self.assertTrue(report['signature']['verified_strict'])
            self.assertFalse(report['structural']['runtime_tested'])

    def test_wifi_changes_only_native_tempranillo_records(self):
        from patches.ios15.impl.kc.wifi import adapt_wifi, N61_APPROVED
        root = fixtures.derived_root()
        with tempfile.TemporaryDirectory() as work:
            report = adapt_wifi(root / 'j96/kernel.raw', self.donor / 'usr/share/firmware/wifi',
                                Path(work) / 'wifi.raw', native_kernel=root / 'n56/kernel.raw',
                                reference_kernel=root / 'j96/kernel.raw', model='N61')
            self.assertEqual(set(report['native_files']), set(N61_APPROVED))
            self.assertEqual(report['validation']['unrelated_filename_mappings'], 639)
            self.assertTrue(report['validation']['verification_code_unchanged'])

    def test_native_touch_personality_is_n61(self):
        from patches.shared.impl.common.macho import Kernel
        from patches.shared.impl.kc.n56_touch import touch
        native = Kernel(fixtures.derived('n56/kernel.raw'))
        target = Kernel(fixtures.derived('j96/kernel.raw'))
        with tempfile.TemporaryDirectory() as work:
            output = Path(work) / 'touch.raw'
            output.write_bytes(touch(native, target, 'N61'))
            candidate = Kernel(output)
            entry = candidate.kexts['com.apple.driver.AppleMultitouchSPIJ96']
            personality = entry['IOKitPersonalities']['AppleMultitouchSPI - J96']
            self.assertEqual(personality['IONameMatch'], ['multi-touch,n61'])

    def test_native_runtime_baseband_and_personalized_bytes_preserved(self):
        from patches.ios15.impl.rootfs.baseband_firmware import build_donor_firmware_root, FIRMWARE_PATHS
        with tempfile.TemporaryDirectory() as work:
            output = build_donor_firmware_root(self.donor, work)
            for relative in FIRMWARE_PATHS:
                for name in ('bbticket.der', 'sbl1.mbn', 'apps.mbn'):
                    source = self.donor / FIRMWARE_PATHS[0] / name
                    self.assertEqual(hashlib.sha256((output / relative / name).read_bytes()).digest(),
                                     hashlib.sha256(source.read_bytes()).digest())

    def test_n61_locationd_and_matching_cache_plans(self):
        source = (self.j96 / motion_platform.LOCATIOND).read_bytes()
        data = motion_platform.patch_locationd(source, 'N61')
        for offset, before, _ in motion_platform.LOCATIOND_EDITS[:2]:
            self.assertEqual(data[offset:offset + 4], before)
        for offset, _, after in motion_platform.locationd_edits('N61'):
            self.assertEqual(data[offset:offset + len(after)], after)
        from patches.ios15.impl.rootfs.dyld_cache import plan_edits
        self.assertTrue(plan_edits(self.j96, motion_platform.cache_edits('N61'),
                                   owner=motion_platform.PATCH_ID)['trustcache_entries'])
