"""Select native resources from the verified donor, preserving on-device names."""
from dataclasses import dataclass
import hashlib
from pathlib import Path


@dataclass(frozen=True)
class NativeDevice:
    model: str
    product: str
    firmware: str
    product_type: bytes
    thermal_product: int
    thermal_compare: bytes
    thermal_branch: str

    @property
    def thermal_class(self):
        return "tm" + hashlib.md5(self.model.encode()).hexdigest()


DEVICES = {
    "N56": NativeDevice("N56", "iPhone7,1", "barbera",
                        bytes.fromhex("21a4d740953b746cec1360a18c6ad1bcff246dd0"),
                        0x427ac, bytes.fromhex("89f584528900a0721f01096b"), "b.eq"),
    "N61": NativeDevice("N61", "iPhone7,2", "tempranillo",
                        bytes.fromhex("172a43569a472d69a2e455635e5592b4c42ab4d1"),
                        0x43a35, bytes.fromhex("a94687528900a0721f01096b"), "b.ne"),
}


def native_device(ctx):
    donor = getattr(ctx, "donor_dir", None)
    if donor:
        root = Path(donor) / "usr/share/firmware/multitouch"
        found = [model for model in DEVICES if (root / (model + ".mtprops")).is_file()]
        if len(found) > 1:
            raise ValueError("donor contains both N56 and N61 model resources")
        if found:
            return DEVICES[found[0]]
    target = getattr(ctx, "t", {})
    model = getattr(ctx, "native_model", None) or target.get("device", {}).get("model", "n56ap")
    model = model.upper().removesuffix("AP")
    if model not in DEVICES:
        raise ValueError("unsupported native model: " + model)
    return DEVICES[model]


def native_path(ctx, path):
    return path.replace("N56", native_device(ctx).model)
