#!/usr/bin/env python3
"""Regression tests for scrape_common.is_real_storage accessory filter."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrape_common import is_real_storage


MUST_BLOCK = [
    "128GB External SSD Up to 450MB/s Flash Drive",
    "SSK 1TB External SSD USB Flash Drive up to 1000MB/s USB C+A 3.2 Stick",
    "Kingston 64GB DataTraveler USB Flash Drive Pendrive",
    "SanDisk 128GB Extreme microSDXC Memory Card",
    "Samsung 256GB EVO Plus SD Card",
    "Corsair Vengeance 32GB DDR4 RAM Memory",
    "Crucial 16GB DDR5 SODIMM Laptop Memory",
    "M.2 SSD Heatsink Cooler Aluminum Heat Sink 2280",
    "USB 3.0 SD Card Reader 64GB Compatible",
    "External USB DVD Blu-ray Optical Drive 3D",
    "SSK NVMe & SATA SSD Cloner M.2 Duplicator Dual Bay Dock",
    "MAIWO External Hard Drive Enclosure for 2.5 3.5 Inch SATA SSD HDD 24TB Capacity",
    "Sabrent USB 3.2 Type-C Tool-Free Enclosure for M.2 PCIe NVMe and SATA SSDs",
    "UGREEN 2.5 Inch HDD Case HDD/SSD Case SATA External Case Up to 6TB",
    "Carrying case compatible with Crucial X10 portable SSD (box only)",
    "20PCS Capacity Sticker Label for Hard Drive Tray Caddy",
    "Hard Drive Case Compatible with Samsung T7 Shield",
    "M.2 to USB-C Docking Station SATA Reader Adapter Converter for NVMe SSD",
]

MUST_KEEP = [
    "WD 24TB My Book Desktop External Hard Drive, USB 3.2 Gen1",
    "SanDisk Professional 48TB G-RAID Shuttle 8 - Enterprise-Class 8-Bay External Hard Drive",
    "Toshiba N300 PRO 24TB NAS (up to 24 Bays) 3.5-Inch Internal Hard Drive",
    "Seagate IronWolf 2TB Enterprise Internal NAS HDD for Multi-Bay",
    "Seagate Game Drive for Xbox 2TB External Hard Drive Portable HDD",
    "Samsung Portable SSD T7 Shield, 4TB, USB 3.2 Gen.2, Incl. USB Type C Cable",
    "WD_BLACK 4TB SN850X NVMe Internal Gaming SSD with Heatsink",
    "Samsung 990 PRO 2TB SSD w/Heatsink PCIe 4.0 M.2",
    "Crucial MX500 1TB SATA Internal SSD",
    "WD 8TB Elements Desktop External Hard Drive USB 3.0",
]


class TestIsRealStorage(unittest.TestCase):
    def test_must_block(self):
        for title in MUST_BLOCK:
            with self.subTest(title=title[:60]):
                self.assertFalse(is_real_storage(title), f"should block: {title}")

    def test_must_keep(self):
        for title in MUST_KEEP:
            with self.subTest(title=title[:60]):
                self.assertTrue(is_real_storage(title), f"should keep: {title}")


if __name__ == "__main__":
    unittest.main()
