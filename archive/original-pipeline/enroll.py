"""
Face Enrollment CLI Utility
Backward-compatible wrapper for enrolling identities into the database.
"""

import os
import sys
import argparse

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(parent_dir, 'src')
sys.path.insert(0, src_dir)
sys.path.insert(0, parent_dir)

from src.enroll import enroll_synthetic_identities, enroll_from_image_file
from src.database import get_db_manager

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Real-Time Face Enrollment Utility")
    parser.add_argument("--name", type=str, help="Name of the person to enroll")
    parser.add_argument("--image", type=str, help="Path to image file for enrollment")
    parser.add_argument("--synthetic", type=int, default=0, help="Enroll N synthetic identities for benchmarking (e.g. 50)")
    args = parser.parse_args()

    db = get_db_manager()

    if args.synthetic > 0:
        names = enroll_synthetic_identities(count=args.synthetic, db_manager=db)
        print(f"\n[OK] Enrolled {len(names)} identities.")
    elif args.name and args.image:
        success = enroll_from_image_file(args.image, args.name, db_manager=db)
        if success:
            print(f"\n[OK] Identity '{args.name}' enrolled successfully.")
        else:
            print(f"\n[ERROR] Failed to enroll '{args.name}'.")
    else:
        print("\n=== Face Enrollment Utility ===")
        print("Usage:")
        print("  python enroll.py --synthetic 50       # Enroll 50 test identities")
        print("  python enroll.py --name Alice --image photo.jpg  # Enroll photo\n")
