#!/usr/bin/env python3
"""Check all .txt files in data/ for duplicate names."""

import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.importers.family_tree_text import parse_family_tree_txt, detect_duplicates


def main():
    data_dir = Path(__file__).parent / "data"
    txt_files = sorted(data_dir.glob("*.txt"))
    
    if not txt_files:
        print("No .txt files found in data/")
        return
    
    print(f"Checking {len(txt_files)} files for duplicates...\n")
    print("=" * 80)
    
    for txt_file in txt_files:
        print(f"\nFile: {txt_file.name}")
        print("-" * 80)
        
        try:
            # Parse the file
            people = parse_family_tree_txt(str(txt_file))
            
            # Detect duplicates
            duplicate_warnings = detect_duplicates(people, txt_file.name)
            
            if duplicate_warnings:
                print(f"Found {len(duplicate_warnings)} duplicate(s):\n")
                for warning in duplicate_warnings:
                    print(f"  ⚠️  {warning}")
            else:
                print(f"✅ No duplicates found ({len(people)} unique people)")
                
        except Exception as e:
            print(f"❌ Error processing file: {e}")
    
    print("\n" + "=" * 80)
    print("Duplicate check complete.")


if __name__ == "__main__":
    main()
