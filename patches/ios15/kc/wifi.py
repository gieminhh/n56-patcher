"""BCM4345B0/B1 firmware mappings for the J96 iOS 15 hashstore."""
from pathlib import Path

from core.patch import Patch
from core.native_device import native_device
from patches.ios15.impl.kc.wifi import adapt_wifi


class Wifi(Patch):
    id = "kc.wifi"
    layer = "kc"
    feature = "wifi"
    scope = "version"
    requires = ("kc.j96_clean",)
    after = ("kc.mt_n56", "kc.chestnut_kext", "kc.pinot_lcd", "kc.sn2400")
    note = "iOS15 BCM4345B0/B1 原生固件哈希、TRX 长度及 KASLR 指针映射"

    def apply(self, ctx, art):
        output = Path(ctx.wk("kc.wifi.raw"))
        source = Path(ctx.derived_root)
        firmware = (Path(ctx.donor_dir) / "usr/share/firmware/wifi"
                    if getattr(ctx, "donor_dir", None) else source / "n56/firmware")
        # art, not a saved baseline: preceding drivers may already own padding.
        ctx.patch_reports[self.id] = adapt_wifi(
            art, firmware, output, native_kernel=source / "n56/kernel.raw",
            reference_kernel=source / "j96/kernel.raw", model=native_device(ctx).model)
        return str(output)
