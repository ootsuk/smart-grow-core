import unittest
import sys
import os

# Add the parent directory to the path to find the jobs module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from jobs.ai_analysis_job import parse_ai_response

class TestAiAnalysisJob(unittest.TestCase):

    def test_parse_ai_response_full(self):
        """Test parsing a full AI response with comparison."""
        response_text = """
        **成長率:** 75.5%
        **状態サマリー:**
        全体的に順調に成長しています。葉の色も濃く、健康そうです。
        **前日比較:**
        昨日と比較して、茎が2cmほど伸び、葉の数も増えました。
        **アドバイス:**
        • 引き続き、日当たりの良い場所に置いてください。
        • 水やりは1日1回で十分です。
        """
        result = parse_ai_response(response_text)
        self.assertEqual(result['growth_rate'], 75.5)
        self.assertIn('順調に成長', result['summary'])
        self.assertIn('茎が2cmほど伸び', result['comparison'])
        self.assertIn('日当たりの良い場所', result['advice'])

    def test_parse_ai_response_no_comparison(self):
        """Test parsing an AI response without a comparison section."""
        response_text = """
        **成長率:** 30%
        **状態サマリー:**
        発芽したばかりで、まだ小さいです。
        **アドバイス:**
        • 水をやりすぎないように注意してください。
        """
        result = parse_ai_response(response_text)
        self.assertEqual(result['growth_rate'], 30.0)
        self.assertIn('発芽したばかり', result['summary'])
        self.assertEqual(result['comparison'], '')
        self.assertIn('水をやりすぎないように', result['advice'])

    def test_parse_ai_response_missing_fields(self):
        """Test parsing a response with some missing fields."""
        response_text = """
        **成長率:** 90%
        **状態サマリー:**
        収穫時期です。
        """
        result = parse_ai_response(response_text)
        self.assertEqual(result['growth_rate'], 90.0)
        self.assertEqual(result['summary'], '収穫時期です。')
        self.assertEqual(result['comparison'], '')
        self.assertEqual(result['advice'], '')

    def test_parse_ai_response_no_markdown(self):
        """Test parsing a plain text response."""
        response_text = "順調です。"
        result = parse_ai_response(response_text)
        self.assertEqual(result['growth_rate'], 0.0)
        self.assertEqual(result['summary'], '順調です。')
        self.assertEqual(result['comparison'], '')
        self.assertEqual(result['advice'], '')


if __name__ == '__main__':
    unittest.main()
