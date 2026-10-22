"""Run tests with temporary storage and deterministic camera configuration."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from src import config

    with tempfile.TemporaryDirectory(prefix="face-recognition-tests-") as directory:
        storage = Path(directory)
        config.DATA_DIR = storage
        config.REPORTS_DIR = storage / "reports"
        config.KNOWN_FACES_DIR = storage / "known_faces"
        config.DATABASE_FILE = str(storage / "tests.db")
        config.ENCODINGS_JSON_FILE = str(storage / "encodings.json")
        config.LOG_FILE = str(storage / "tests.log")
        config.CAMERA_BACKEND = "synthetic"
        detector_patch = patch('src.scrfd.SCRFDDetector._initialize_session')
        detector_patch.start()  # Unit tests must not download or load production models.
        try:
            suite = unittest.defaultTestLoader.discover(str(root / "tests"))
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            return 0 if result.wasSuccessful() else 1
        finally:
            detector_patch.stop()
            web = sys.modules.get("src.app")
            if web:
                web.shutdown_pipeline()
                if web.db_manager:
                    web.db_manager.close_session(web.session_id)
                    web.db_manager.close()


if __name__ == "__main__":
    sys.exit(main())
