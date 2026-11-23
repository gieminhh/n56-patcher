import argparse
import plistlib
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core import log, slots_cli
from core.flow import Flow


class ResumeInstallTests(unittest.TestCase):
    def flow(self, marker=b'yes', build='19H422'):
        ctx = SimpleNamespace(dry_run=False, installation=Mock(), slot={'version': '15'},
                              t={'version': 'ios15', 'build': '19H422'}, ssh=Mock(),
                              wk=lambda p: '/nonexistent/n56-resume-test/' + p)
        ctx.ssh.sh.side_effect = [marker, plistlib.dumps({'ProductBuildVersion': build})]
        flow = Flow.__new__(Flow)
        flow.ctx = ctx
        for name in ('_need_ramdisk', 'patch_rootfs', 'build', 'rootfs', 'volumes', '_clear_checkpoints'):
            setattr(flow, name, Mock())
        return flow

    def test_completed_base_resumes_overlays_without_format_or_stream(self):
        flow = self.flow()
        flow.resume_install()
        flow.patch_rootfs.assert_called_once_with()
        flow.build.assert_called_once_with()
        flow.rootfs.assert_not_called()
        flow.volumes.assert_not_called()
        flow._clear_checkpoints.assert_not_called()
        flow.ctx.installation.prepare.assert_called_once_with()

    def test_missing_base_or_wrong_build_refuses_writes(self):
        for marker, build in ((b'', '19H422'), (b'yes', '16H88')):
            with self.subTest(marker=marker, build=build):
                flow = self.flow(marker, build)
                with self.assertRaises(log.Die):
                    flow.resume_install()
                flow.patch_rootfs.assert_not_called()
                flow.build.assert_not_called()
                flow.ctx.installation.close.assert_called_once_with()

    def test_creation_authorization_is_bound_to_proven_empty_data_uuid(self):
        for contents in (b'empty', b'occupied'):
            with self.subTest(contents=contents):
                flow = self.flow()
                flow.ctx.t['data_protection'] = 'encrypted'
                flow.ctx.slot.update(system=4, data=5)
                flow.ctx.ssh.sh.side_effect = [b'yes', plistlib.dumps({'ProductBuildVersion': '19H422'}), contents]
                with patch('core.flow.Apfs') as apfs, \
                     patch('patches.ios15.impl.rootfs.system_policy.inspect_volume',
                           return_value={'uuid': '1234', 'unencrypted': False}) as inspect:
                    apfs.return_value.volumes.return_value = [(5, 0, b'superblock')]
                    flow.resume_install()
                    if contents == b'occupied':
                        self.assertFalse(hasattr(flow.ctx, '_ios15_new_data'))
                        inspect.assert_not_called()
                    else:
                        self.assertEqual(flow.ctx._ios15_new_data, {'slice': 5, 'uuid': '1234'})
                        inspect.assert_called_once_with(b'superblock', 5)
                        flow.ctx.installation.save_layout.assert_called_once_with()

    def test_cli_records_only_after_successful_patch_and_build(self):
        import n56patcher
        for fails in (False, True):
            with self.subTest(fails=fails):
                flow = Mock()
                if fails:
                    flow.resume_install.side_effect = log.Die(1)
                with patch.object(slots_cli, '_state', return_value={}), \
                     patch.object(slots_cli, 'donor_ready', return_value=True), \
                     patch.object(slots_cli.slots, 'plan_install', return_value={'status': 'ready'}), \
                     patch.object(n56patcher, 'make_flow', return_value=(None, None, flow)), \
                     patch.object(slots_cli, 'cmd_record', return_value=0) as record:
                    result = slots_cli.cmd_resume(argparse.Namespace(version='15'))
                    self.assertEqual(result, 1 if fails else 0)
                    if fails:
                        record.assert_not_called(); flow.build.assert_not_called()
                    else:
                        flow.resume_install.assert_called_once_with(); record.assert_called_once()
                    flow.close.assert_called_once_with()
