import unittest

from core.numeric_verifier import calculate_value, verify_numeric_claims


class NumericVerifierTests(unittest.TestCase):
    def test_relative_decrease_matches_claim(self):
        result = verify_numeric_claims([
            {
                "claim_id": "N001",
                "claim": "烘干时间缩短约60.7%",
                "operation": "relative_decrease",
                "baseline": 129.8623,
                "result": 51.0934,
                "claimed_value": 60.7,
                "tolerance": 0.1,
                "unit": "%",
                "page": 28,
            }
        ])
        self.assertEqual(result["consistent_count"], 1)
        self.assertTrue(result["results"][0]["passed"])

    def test_zero_baseline_is_reported_as_error(self):
        result = verify_numeric_claims([
            {
                "operation": "ratio",
                "baseline": 0,
                "result": 1,
                "claimed_value": 1,
            }
        ])
        self.assertEqual(result["error_count"], 1)
        self.assertEqual(result["results"][0]["status"], "error")

    def test_unsupported_operation_is_rejected(self):
        with self.assertRaises(ValueError):
            calculate_value("execute_code", 1, 2)


if __name__ == "__main__":
    unittest.main()
