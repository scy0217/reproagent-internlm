import unittest

from core.scoring_profiles import apply_scoring


class ScoringTests(unittest.TestCase):
    def test_missing_code_does_not_reduce_scientific_score(self):
        verified = {
            "verified_issues": [{
                "title": "未提供代码仓库",
                "reason": "未公开完整代码",
                "severity": "high",
                "dimension": "code",
                "impact_scope": "resource_openness",
                "evidence": ["未提供链接"],
                "pages": [1],
            }]
        }
        extraction = {
            "title": "数值模拟研究",
            "methods": ["有限体积法"],
            "models_or_algorithms": [],
            "materials_or_datasets": [],
            "software_environment": [],
            "hardware_environment": [],
            "code_availability": {"status": "unknown"},
        }
        result = apply_scoring(
            verified,
            extraction,
            {"page_count": 10, "selected_pages": [1, 2, 3, 4, 5]},
        )
        self.assertEqual(result["reproducibility_score"], 100)
        self.assertLess(result["resource_openness_score"], 100)


if __name__ == "__main__":
    unittest.main()
