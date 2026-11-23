"""Find a device SDK with full Xcode or the repository's local SDKs."""
from pathlib import Path
import re
import subprocess


def iphoneos_sdk():
    try:
        return subprocess.check_output(
            ["xcrun", "--sdk", "iphoneos", "--show-sdk-path"],
            text=True, stderr=subprocess.PIPE).strip()
    except subprocess.CalledProcessError as exc:
        root = Path(__file__).resolve().parents[1] / "tools/sdks"
        candidates = [p for p in root.glob("iPhoneOS*.sdk")
                      if (p / "usr/include/stdio.h").is_file()]
        if not candidates:
            raise RuntimeError("找不到 iPhoneOS SDK：请安装 Xcode，或将设备 SDK 放入 tools/sdks/") from exc
        return str(max(candidates, key=lambda p: tuple(map(int, re.findall(r"\d+", p.name)))))
