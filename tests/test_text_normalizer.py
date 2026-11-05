import unittest

from core.text_normalizer import (
    normalize_scientific_text,
    quarantine_broken_symbol_issues,
)


class TextNormalizerTests(unittest.TestCase):
    def test_superscript_scientific_notation(self):
        self.assertEqual(normalize_scientific_text("10⁻⁴ h"), "10^-4 h")

    def test_broken_negative_exponent_is_repaired_when_unambiguous(self):
        self.assertEqual(normalize_scientific_text("10□4 kg"), "10^(-4) kg")

    def test_unrecoverable_symbol_issue_is_quarantined(self):
        result = quarantine_broken_symbol_issues({
            "verified_issues": [{
                "title": "温度数量级冲突",
                "evidence": ["温差为10□"],
            }],
            "rejected_issues": [],
        })
        self.assertEqual(result["verified_issues"], [])
        self.assertEqual(len(result["rejected_issues"]), 1)


if __name__ == "__main__":
    unittest.main()
