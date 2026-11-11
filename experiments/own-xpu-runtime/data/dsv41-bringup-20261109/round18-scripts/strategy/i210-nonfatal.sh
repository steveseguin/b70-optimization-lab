#!/bin/bash
# Owner-approved 2026-11-11 17:50: on the I210 LAN chip 0000:a7:00.0 only (enp167s0, root complex 0000:a0 with card 4):
# AER completion timeout severity -> non-fatal (UESvrt 0x10c bit 14 cleared) and the longest completion timeout range
# (DevCtl2 0xc8 bits 3:0 = 0xE, 17 s - 64 s). Not persistent: re-run after every boot. Uses sudo -S (stdin) then sudo -k.
P=/home/steve/SUDO_PASSWORD.txt
sudo -S -p '' setpci -s a7:00.0 0x10c.L=0x00000000:0x00004000 < $P && sudo -S -p '' setpci -s a7:00.0 0xc8.W=0x000e:0x000f < $P
echo "I210 a7:00.0 UESvrt=$(sudo -S -p '' setpci -s a7:00.0 0x10c.L < $P) DevCtl2=$(sudo -S -p '' setpci -s a7:00.0 0xc8.W < $P) (want 004f2031 / 000e)"
sudo -k
