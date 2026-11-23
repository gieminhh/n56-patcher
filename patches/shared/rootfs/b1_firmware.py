import os

from core import log
from core.overlay import SourceItem, SourceOverlay

B1_FILES = (
    "barbera.trx",
    "barbera.clmb",
    "barbera.txcb",
    "P-barbera_M-CORO_V-m__m-3.7.txt",
    "P-barbera_M-CORO_V-m__m-5.1.txt",
    "P-barbera_M-CORO_V-t__m-3.7.txt",
    "P-barbera_M-CORO_V-u__m-3.7.txt",
)
N61_FILES = tuple(name.replace("barbera", "tempranillo") for name in B1_FILES)


class B1Firmware(SourceOverlay):
    id = "rootfs.b1_firmware"
    feature = "wifi"
    scope = "device"
    note = "从本机 SystemA 复制完整 B1 Wi-Fi/蓝牙固件目录"
    items = (
        SourceItem(
            source="device_s1:usr/share/firmware/wifi/C-4345__s-B1",
            dest="usr/share/firmware/wifi/C-4345__s-B1",
            op="copy",
            depends_on_signing=True,
        ),
    )

    def apply(self, ctx, art=None):
        ctx.verify_device_system(ctx.ssh)
        if ctx.donor_dir:
            # N61 的原生 B1 固件名为 tempranillo，不能按 N56 的 barbera 检查。
            is_n61 = os.path.isfile(os.path.join(
                ctx.donor_dir, "usr/share/firmware/multitouch/N61.mtprops"))
            required = N61_FILES if is_n61 else B1_FILES
            base = os.path.join(ctx.donor_dir, "usr/share/firmware/wifi/C-4345__s-B1")
            for name in required:
                path = os.path.join(base, name)
                if not os.path.isfile(path) or os.path.getsize(path) == 0:
                    log.die(f"donor 快照中的 B1 固件缺失或为空: {path}")
        else:
            is_n61 = ctx.ssh.sh(
                'if test -s /mnt1/usr/share/firmware/multitouch/N61.mtprops; '
                'then echo N61; else echo N56; fi').strip() == b"N61"
            required = N61_FILES if is_n61 else B1_FILES
            base = "/mnt1/usr/share/firmware/wifi/C-4345__s-B1"
            ctx.ssh.sh(" && ".join(f'test -s "{base}/{name}"' for name in required))
        log.log(f"  B1 固件：{'N61 (tempranillo)' if is_n61 else 'N56 (barbera)'}")
        super().apply(ctx, art)
