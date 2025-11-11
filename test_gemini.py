#!/usr/bin/env python3
"""Gemini API接続テスト"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from config import LLM_API_KEY
import google.generativeai as genai

print("=" * 60)
print("Gemini API 接続テスト")
print("=" * 60)

# APIキーの確認
if not LLM_API_KEY:
    print("❌ エラー: LLM_API_KEYが設定されていません")
    print("   .envファイルにLLM_API_KEYを設定してください")
    sys.exit(1)

print(f"✅ APIキー: {LLM_API_KEY[:10]}...{LLM_API_KEY[-4:]}")
print()

# Gemini APIの設定
try:
    genai.configure(api_key=LLM_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("✅ Gemini APIモデル初期化成功")
except Exception as e:
    print(f"❌ モデル初期化エラー: {e}")
    sys.exit(1)

# シンプルなテストリクエスト
print("\n" + "=" * 60)
print("テスト1: シンプルなテキスト生成")
print("=" * 60)

try:
    response = model.generate_content("こんにちは。簡単に自己紹介してください。")
    print(f"✅ レスポンス受信成功")
    print(f"📝 レスポンス内容:\n{response.text[:200]}...")
except Exception as e:
    print(f"❌ エラー: {e}")
    print(f"   エラータイプ: {type(e).__name__}")

# システムプロンプトを含むテスト
print("\n" + "=" * 60)
print("テスト2: システムプロンプト付きリクエスト")
print("=" * 60)

system_prompt = """あなたは豆苗栽培の専門AIアシスタントです。
**現在のシステム情報:**
- 温度: 23.5℃
- 湿度: 45.2%
- 給水タンク圧力: 120.5 kPa
- 排水タンク圧力: 75.3 kPa
"""

user_message = "現在の栽培環境について簡単にコメントしてください。"

try:
    response = model.generate_content(system_prompt + "\n\n" + user_message)
    print(f"✅ レスポンス受信成功")
    print(f"📝 レスポンス内容:\n{response.text[:300]}...")
except Exception as e:
    print(f"❌ エラー: {e}")
    print(f"   エラータイプ: {type(e).__name__}")

# 画像付きテスト
print("\n" + "=" * 60)
print("テスト3: 画像付きリクエスト")
print("=" * 60)

from PIL import Image
import io

# 画像ファイルを探す
image_path = Path(__file__).parent / 'plant_images' / 'layer_1' / '20251110_090001.png'

if image_path.exists():
    try:
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        image_data = Image.open(io.BytesIO(image_bytes))
        
        response = model.generate_content([
            "この画像について簡単に説明してください。",
            image_data
        ])
        print(f"✅ 画像付きレスポンス受信成功")
        print(f"📝 レスポンス内容:\n{response.text[:300]}...")
    except Exception as e:
        print(f"❌ エラー: {e}")
        print(f"   エラータイプ: {type(e).__name__}")
else:
    print(f"⚠️ スキップ: 画像ファイルが見つかりません")
    print(f"   パス: {image_path}")

print("\n" + "=" * 60)
print("テスト完了")
print("=" * 60)

