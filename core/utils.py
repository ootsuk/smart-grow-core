import re

def parse_ai_response(response_text):
    """AIレスポンスから成長率、サマリー、アドバイスを抽出する共通関数"""
    result = {
        'growth_rate': 0.0,
        'summary': '解析できませんでした。',
        'advice': 'AIからの応答を確認してください。'
    }

    if not response_text:
        return result

    try:
        # 成長率を抽出 (全角・半角コロン、スペースに対応)
        growth_match = re.search(r'成長率[:：\s]*(\d+\.?\d*)\s*%', response_text)
        if growth_match:
            result['growth_rate'] = float(growth_match.group(1))

        # 状態サマリーを抽出
        summary_match = re.search(r'\*\*状態サマリー[:：]\*\*\s*(.*?)(?=\*\*|$)', response_text, re.DOTALL)
        if summary_match:
            result['summary'] = summary_match.group(1).strip()[:500]  # 最大500文字
        else:
            # サマリーが見つからない場合は、レスポンスの最初の部分を流用
            result['summary'] = response_text.strip()[:200]

        # アドバイスを抽出
        advice_match = re.search(r'\*\*アドバイス[:：]\*\*\s*(.*?)(?=\*\*|$)', response_text, re.DOTALL)
        if advice_match:
            result['advice'] = advice_match.group(1).strip()[:500]  # 最大500文字
        else:
            # アドバイスが見つからない場合のフォールバック
            result['advice'] = '定期的な観察と管理を続けてください。'

    except Exception as e:
        print(f"[WARNING] AI response parsing error: {e}")
        # エラー発生時はレスポンス全体をサマリーに入れる
        result['summary'] = response_text.strip()[:500]

    return result
