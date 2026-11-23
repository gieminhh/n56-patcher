"""Read the physical regulatory model with the ramdisk's native MobileGestalt."""
from pathlib import Path
import subprocess

from core.ios_sdk import iphoneos_sdk


def reader(ctx):
    output = Path(ctx.wk("regulatory-model/reader"))
    source = Path(__file__).with_suffix(".c")
    output.parent.mkdir(parents=True, exist_ok=True)
    if not output.exists() or output.stat().st_mtime < source.stat().st_mtime:
        subprocess.run(["xcrun", "clang", "-target", "arm64-apple-ios12.0",
                        "-isysroot", iphoneos_sdk(), "-Os", "-framework", "CoreFoundation",
                        "-Wl,-no_fixup_chains", str(source), "-o", str(output)],
                       check=True, capture_output=True)
        subprocess.run(["codesign", "-s", "-", "-f", "--digest-algorithm=sha256", str(output)],
                       check=True, capture_output=True)
    return str(output)
