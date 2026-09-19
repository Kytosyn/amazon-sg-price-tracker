#!/usr/bin/env python3
"""Unit tests for title-based storage interface/protocol tagging."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrape_common import PROTOCOL_TAGS, infer_protocols, primary_protocol


CASES = [
    # NVMe M.2 SSD (PCIe also named) — primary NVMe; M.2 coexists
    (
        "Samsung 990 PRO 2TB SSD w/Heatsink PCIe 4.0 M.2 NVMe",
        ["NVMe", "PCIe", "M.2"],
        "NVMe",
    ),
    (
        "WD_BLACK 4TB SN850X NVMe Internal Gaming SSD with Heatsink M.2 2280",
        ["NVMe", "M.2"],
        "NVMe",
    ),
    # SATA HDD / SSD
    (
        "Seagate IronWolf Pro 28TB NAS Internal Hard Drive 3.5\" SATA 6GB/S",
        ["SATA"],
        "SATA",
    ),
    (
        "Seagate Exos 26TB Internal Server Hard Drive 3.5 Inch HDD SATA3, 7200RPM",
        ["SATA"],
        "SATA",
    ),
    (
        "Crucial MX500 1TB SATA Internal SSD 2.5 Inch",
        ["SATA"],
        "SATA",
    ),
    (
        "Toshiba X300 3.5\" 14000GB Serial ATA III Hard Drive 7200RPM",
        ["SATA"],
        "SATA",
    ),
    # SAS enterprise
    (
        "HP P23608-B21 16TB SAS 7.2K LFF LP 512e ISE HDD",
        ["SAS"],
        "SAS",
    ),
    (
        "Axiom Enterprise Hard Drive 12 TB SAS 12Gb/s 7200 RPM",
        ["SAS"],
        "SAS",
    ),
    # USB portable / desktop external (no Thunderbolt)
    (
        "WD 24TB My Book Desktop External Hard Drive, USB 3.2 Gen1",
        ["USB"],
        "USB",
    ),
    (
        "Samsung Portable SSD T7 Shield, 4TB, USB 3.2 Gen.2, USB Type C Cable",
        ["USB"],
        "USB",
    ),
    (
        "WD 8TB Elements Desktop External Hard Drive USB 3.0",
        ["USB"],
        "USB",
    ),
    # Thunderbolt enclosure/SSD (+ USB-C often listed) — primary Thunderbolt
    (
        "SanDisk Professional 48TB G-RAID Shuttle 8 External Hard Drive, "
        "Thunderbolt 3 and USB-C, Hardware RAID",
        ["Thunderbolt", "USB"],
        "Thunderbolt",
    ),
    (
        "G-DRIVE 22TB Project Hard Drive, Thunderbolt 3, USB (10Gbps), 7200RPM",
        ["Thunderbolt", "USB"],
        "Thunderbolt",
    ),
    (
        "OWC Express 1M2 4TB USB4 40Gb/s Portable NVMe SSD Storage Solution",
        ["NVMe", "Thunderbolt", "USB"],
        "NVMe",
    ),
    # PCIe without NVMe wording
    (
        "Internal Solid State Drive 2TB PCIe Gen4x4 Add-in Card",
        ["PCIe"],
        "PCIe",
    ),
    # Capacity-only HDD — no interface words (bare TB must not → Thunderbolt)
    (
        "Western Digital Ultrastar WUH722018CL5204 18 TB Hard Drive",
        [],
        "",
    ),
    (
        "Apricorn Aegis Desktop Padlock 22 TB Encrypted Hard Drive",
        [],
        "",
    ),
    # M.2 form-factor only (no bus named)
    (
        "Kingston 1TB M.2 2280 Internal Solid State Drive",
        ["M.2"],
        "M.2",
    ),
    # SAS + SATA dual wording → primary SAS; both in protocols
    (
        "Enterprise 8TB SAS/SATA Dual-Port Hard Drive",
        ["SAS", "SATA"],
        "SAS",
    ),
]


class TestInferProtocols(unittest.TestCase):
    def test_cases(self):
        for title, expect_protocols, expect_primary in CASES:
            with self.subTest(title=title[:70]):
                got = infer_protocols(title)
                self.assertEqual(got, expect_protocols, title)
                self.assertEqual(primary_protocol(got), expect_primary, title)

    def test_stable_order(self):
        """Matched tags always emit in PROTOCOL_TAGS order."""
        title = "USB Thunderbolt 3 M.2 NVMe PCIe Gen4 SAS SATA SSD 2TB"
        got = infer_protocols(title)
        self.assertEqual(got, list(PROTOCOL_TAGS))
        self.assertEqual(primary_protocol(got), "NVMe")

    def test_empty_title(self):
        self.assertEqual(infer_protocols(""), [])
        self.assertEqual(primary_protocol([]), "")

    def test_bare_tb_capacity_not_thunderbolt(self):
        self.assertNotIn("Thunderbolt", infer_protocols("Seagate 4TB Barracuda HDD"))
        self.assertNotIn("Thunderbolt", infer_protocols("WD 18 TB Purple Pro"))


if __name__ == "__main__":
    unittest.main()
