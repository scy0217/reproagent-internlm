import unittest

import pymupdf

from core.report_generator import generate_pdf_report


class PdfReportTests(unittest.TestCase):
    def test_chinese_body_text_is_embedded_and_extractable(self):
        extraction = {
            "title": "中文显示测试",
            "research_goal": "验证科研论文可复现性审计报告的中文字形完整性",
            "research_object": "神经网络实验",
            "methods": ["对照实验"],
            "main_results": ["确认问题、证据页码和主要结果均应显示"],
        }
        verified = {
            "verification_summary": "报告正文不应为空，也不应出现缺字方框。",
            "verified_issues": [{
                "title": "基线数据缺失",
                "severity": "medium",
                "pages": [3],
                "reason": "无法独立核验结果",
                "evidence": ["原文证据完整"],
                "impact_scope": "scientific_reproducibility",
            }],
            "verified_strengths": ["研究目标清晰"],
            "rejected_issues": [],
            "score_breakdown": {},
        }

        pdf_bytes = generate_pdf_report(
            extraction,
            verified,
            "测试论文.pdf",
        )
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        extracted_text = "".join(page.get_text() for page in document)

        required_phrases = [
            "科研论文可复现性审计报告",
            "确认问题",
            "证据页码",
            "主要结果",
            "研究目标",
            "验证科研论文可复现性审计报告的中文字形完整性",
        ]
        for phrase in required_phrases:
            self.assertIn(phrase, extracted_text)


if __name__ == "__main__":
    unittest.main()
