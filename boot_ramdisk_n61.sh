#!/bin/bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
TOOLS="$DIR/tools/SSHRD_Script/Darwin"
RD="$DIR/tools/SSHRD_Script/sshramdisk"

echo "[*] Waiting for device in DFU mode..."
while true; do
    INFO=$("$TOOLS/irecovery" -q 2>/dev/null || true)
    if echo "$INFO" | grep -q "MODE: DFU"; then
        break
    fi
    sleep 1
done

echo "[*] Device detected in DFU mode."
if ! echo "$INFO" | grep -q "PWND"; then
    echo "[*] Running gaster pwn..."
    "$TOOLS/gaster" pwn
    "$TOOLS/gaster" reset 2>/dev/null || true
    sleep 1
fi

echo "[*] Uploading iBSS..."
"$TOOLS/irecovery" -f "$RD/iBSS.img4"
sleep 2

echo "[*] Uploading iBEC..."
"$TOOLS/irecovery" -f "$RD/iBEC.img4"
sleep 3

echo "[*] Sending boot logo..."
"$TOOLS/irecovery" -f "$RD/logo.img4" 2>/dev/null || true
"$TOOLS/irecovery" -c "setpicture 0x1" 2>/dev/null || true

echo "[*] Sending ramdisk (126MB)..."
"$TOOLS/irecovery" -f "$RD/ramdisk.img4"
"$TOOLS/irecovery" -c ramdisk
sleep 1

echo "[*] Sending devicetree..."
"$TOOLS/irecovery" -f "$RD/devicetree.img4"
"$TOOLS/irecovery" -c devicetree
sleep 1

echo "[*] Sending trustcache..."
"$TOOLS/irecovery" -f "$RD/trustcache.img4"
"$TOOLS/irecovery" -c firmware
sleep 1

echo "[*] Sending kernelcache..."
"$TOOLS/irecovery" -f "$RD/kernelcache.img4"
"$TOOLS/irecovery" -c bootx

echo "[*] Boot command sent! Device is booting SSH Ramdisk..."
