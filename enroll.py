"""
Face Enrollment CLI Utility
Root entry point for enrolling identities into the access control database.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.enroll import enroll_synthetic_identities, enroll_from_image_file, enroll_identity
from src.database import get_db_manager
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Real-Time Face Enrollment Utility")
    parser.add_argument("--name", type=str, help="Name of the person to enroll")
    parser.add_argument("--image", type=str, help="Path to image file for enrollment")
    parser.add_argument("--synthetic", type=int, default=0, help="Enroll N synthetic identities for benchmarking (e.g. 50)")
    args = parser.parse_args()

    db = get_db_manager()

    if args.synthetic > 0:
        names = enroll_synthetic_identities(count=args.synthetic, db_manager=db)
        print(f"\n[OK] Enrolled {len(names)} identities into {db.db_file}.")
    elif args.name and args.image:
        success = enroll_from_image_file(args.image, args.name, db_manager=db)
        if success:
            print(f"\n[OK] Identity '{args.name}' successfully enrolled!")
        else:
            print(f"\n[ERROR] Failed to enroll '{args.name}'.")
    else:
        print("\n=== Face Enrollment Utility ===")
        print("Usage:")
        print("  python enroll.py --synthetic 50       # Enroll 50 test identities for benchmarking")
        print("  python enroll.py --name Alice --image photo.jpg  # Enroll single face photo\n")
