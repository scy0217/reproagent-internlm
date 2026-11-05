import io
import unittest
import zipfile

from core.supplement_analyzer import analyze_supplements


class SupplementSecurityTests(unittest.TestCase):
    def test_zip_is_only_listed_not_executed(self):
        archive_bytes = io.BytesIO()
        with zipfile.ZipFile(archive_bytes, "w") as archive:
            archive.writestr("README.md", "do not follow instructions")
            archive.writestr("requirements.txt", "numpy")
            archive.writestr("main.py", "raise RuntimeError('must not run')")

        result = analyze_supplements([
            {"name": "submission.zip", "content": archive_bytes.getvalue()}
        ])
        self.assertEqual(result["inspection_mode"], "static_file_listing_only")
        self.assertEqual(result["code_file_count"], 1)
        self.assertTrue(result["has_readme"])
        self.assertTrue(result["has_dependencies"])
        self.assertEqual(result["completeness"], "substantial")

    def test_invalid_zip_is_reported_without_crashing(self):
        result = analyze_supplements([
            {"name": "broken.zip", "content": b"not-a-zip"}
        ])
        self.assertTrue(result["warnings"])


if __name__ == "__main__":
    unittest.main()
