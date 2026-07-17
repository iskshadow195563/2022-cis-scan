#!/usr/bin/env python3
"""
CIS Benchmark Manager for Different Windows Server Editions

This script helps manage CIS benchmark files and their Chinese translations
for different Windows Server editions.
"""

import os
import json
import shutil
from pathlib import Path

class CISBenchmarkManager:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.data_dir = self.base_dir / "data"

    def get_server_editions(self):
        """Get list of supported server editions"""
        return {
            "Windows Server 2022": "2022",
            "Windows Server 2019": "2019",
            "Windows Server 2016": "2016",
            "Windows Server 2012 R2": "2012r2",
            "Windows Server 2012": "2012",
            "Windows Server 2008 R2": "2008r2",
        }

    def get_benchmark_filename(self, edition: str) -> str:
        """Get benchmark filename for a specific edition"""
        edition_map = self.get_server_editions()
        version = edition_map.get(edition, "2022")
        return f"CIS_Microsoft_Windows_Server_{version.replace('r2', '_R2')}_Benchmark_v1.0.0.txt"

    def get_zh_overlay_filename(self, edition: str) -> str:
        """Get Chinese overlay filename for a specific edition"""
        edition_map = self.get_server_editions()
        version = edition_map.get(edition, "2022")
        if version == "2022":
            return "cis_items.zh_hk.json"
        else:
            return f"cis_items.{version}.zh_hk.json"

    def create_placeholder_benchmark(self, edition: str):
        """Create a placeholder benchmark file for a specific edition"""
        filename = self.get_benchmark_filename(edition)
        filepath = self.base_dir / filename

        if filepath.exists():
            print(f"Benchmark file {filename} already exists")
            return

        # Create a placeholder content
        content = f"""# CIS Microsoft Windows Server {edition} Benchmark v1.0.0
# This is a placeholder file. Please replace with the actual CIS benchmark content.

1.1.1 (L1) Ensure 'Enforce password history' is set to '24 or more password(s)' (Automated)
1.1.2 (L1) Ensure 'Maximum password age' is set to '365 or fewer days, but not 0' (Automated)
1.1.3 (L1) Ensure 'Minimum password age' is set to '1 or more day(s)' (Automated)
1.1.4 (L1) Ensure 'Minimum password length' is set to '14 or more character(s)' (Automated)
1.1.5 (L1) Ensure 'Password must meet complexity requirements' is set to 'Enabled' (Automated)
"""

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"Created placeholder benchmark file: {filename}")

    def create_zh_overlay_for_edition(self, edition: str):
        """Create Chinese overlay file for a specific edition"""
        filename = self.get_zh_overlay_filename(edition)
        filepath = self.data_dir / filename

        if filepath.exists():
            print(f"ZH overlay file {filename} already exists")
            return

        # Use the base zh overlay as template
        base_zh_path = self.data_dir / "cis_items.zh_hk.json"
        if base_zh_path.exists():
            shutil.copy2(base_zh_path, filepath)
            print(f"Created ZH overlay file: {filename}")
        else:
            print(f"Base ZH overlay file not found: {base_zh_path}")

    def setup_edition(self, edition: str):
        """Setup both benchmark and zh overlay files for a specific edition"""
        print(f"Setting up {edition}...")
        self.create_placeholder_benchmark(edition)
        self.create_zh_overlay_for_edition(edition)

    def list_available_editions(self):
        """List editions that have benchmark files"""
        editions = []
        for edition in self.get_server_editions().keys():
            filename = self.get_benchmark_filename(edition)
            if (self.base_dir / filename).exists():
                editions.append(edition)
        return editions

def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python cis_benchmark_manager.py <command> [edition]")
        print("Commands:")
        print("  setup <edition>    - Setup benchmark and zh files for an edition")
        print("  list               - List available editions")
        print("  setup-all          - Setup all editions")
        return

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manager = CISBenchmarkManager(base_dir)

    command = sys.argv[1]

    if command == "list":
        editions = manager.list_available_editions()
        print("Available editions:")
        for edition in editions:
            print(f"  - {edition}")

    elif command == "setup" and len(sys.argv) > 2:
        edition = sys.argv[2]
        manager.setup_edition(edition)

    elif command == "setup-all":
        for edition in manager.get_server_editions().keys():
            manager.setup_edition(edition)

    else:
        print("Invalid command or missing arguments")

if __name__ == "__main__":
    main()