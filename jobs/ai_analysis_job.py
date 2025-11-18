import os
import sys
from pathlib import Path
from datetime import datetime

# 親ディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

# gRPC DNS設定（Gemini API用）
os.environ['GRPC_DNS_RESOLVER'] = 'native'

from database.db_manager import insert_system_log, select_system_config, open_db, get_previous_day_image
from config import LLM_API_KEY
import google.generativeai as genai
from PIL import Image
import io


def execute_ai_analysis_job(layer_id: int, image_path: str):
    """
    AI画像解析ジョブ。
    カメラ撮影後に自動実行され、豆苗の成長率や健康状態を分析してDBに保存する。
    
    Args:
        layer_id: レイヤーID
        image_path: 解析対象の画像パス（例: plant_images/layer_1/20251111_090000.jpg）
    """
    print(f"[{datetime.now()}] [AI ANALYSIS JOB START] Layer {layer_id}, Image: {image_path}")
    
    # ログ記録: ジョブ開始
    insert_system_log(
        layer_id=layer_id,
        log_level='INFO',
        message='AI analysis job started.',
        details=f"Image: {image_path}"
    )
    
    # Gemini APIの設定確認
    if not LLM_API_KEY:
        error_msg = 'LLM_API_KEY が設定されていません。AI解析をスキップします。'
        print(f"[ERROR] {error_msg}")
        insert_system_log(
            layer_id=layer_id,
            log_level='ERROR',
            message='AI analysis skipped: API key not configured.',
            details=error_msg
        )
        return
    
    # 画像ファイルの存在確認
    project_root = Path(__file__).parent.parent
    full_image_path = project_root / image_path
    
    if not full_image_path.exists():
        error_msg = f'画像ファイルが見つかりません: {full_image_path}'
        print(f"[ERROR] {error_msg}")
        insert_system_log(
            layer_id=layer_id,
            log_level='ERROR',
            message='AI analysis failed: Image not found.',
            details=error_msg
        )
        return
    
    try:
        # Gemini APIの初期化
        genai.configure(api_key=LLM_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        # 画像を読み込み (今日)
        with open(full_image_path, 'rb') as f:
            image_bytes_today = f.read()
        image_data_today = Image.open(io.BytesIO(image_bytes_today))

        # 前日の画像を取得
        previous_day_image_path = get_previous_day_image(layer_id, image_path)
        image_data_yesterday = None
        if previous_day_image_path:
            full_previous_path = project_root / previous_day_image_path
            if full_previous_path.exists():
                with open(full_previous_path, 'rb') as f:
                    image_bytes_yesterday = f.read()
                image_data_yesterday = Image.open(io.BytesIO(image_bytes_yesterday))
                print(f"[INFO] 前日の画像を発見: {previous_day_image_path}")
        
        # 最新のセンサーデータを取得
        sensor_data = get_latest_sensor_data(layer_id)
        
        # プロンプトの作成
        prompt = create_analysis_prompt(sensor_data, has_previous_image=bool(image_data_yesterday))

        # Gemini APIで分析
        print(f"[INFO] Gemini APIで画像分析中...")
        if image_data_yesterday:
            # 2枚の画像で比較分析
            response = model.generate_content([prompt, image_data_yesterday, image_data_today])
        else:
            # 1枚の画像で分析
            response = model.generate_content([prompt, image_data_today])
        ai_response = response.text
        
        print(f"[INFO] AI分析完了")
        
        # レスポンスを解析して構造化データを抽出
        analysis_result = parse_ai_response(ai_response)
        
        # データベースに保存
        save_ai_report(
            layer_id=layer_id,
            image_path=image_path,
            growth_rate=analysis_result['growth_rate'],
            ai_summary=analysis_result['summary'],
            ai_advice=analysis_result['advice'],
            ai_comparison=analysis_result['comparison'],
            json_response=ai_response
        )
        
        print(f"[{datetime.now()}] [AI ANALYSIS JOB COMPLETE] Layer {layer_id}, 成長率: {analysis_result['growth_rate']}%")
        
        # ログ記録: ジョブ完了
        insert_system_log(
            layer_id=layer_id,
            log_level='INFO',
            message=f"AI analysis completed. Growth rate: {analysis_result['growth_rate']}%",
            details=f"Summary: {analysis_result['summary'][:100]}..."
        )
        
    except Exception as e:
        error_msg = f"AI分析中にエラーが発生しました: {str(e)}"
        print(f"[ERROR] {error_msg}")
        insert_system_log(
            layer_id=layer_id,
            log_level='ERROR',
            message='AI analysis failed.',
            details=error_msg
        )


def get_latest_sensor_data(layer_id):
    """最新のセンサーデータを取得"""
    with open_db() as conn:
        cursor = conn.cursor()
        # Layer 0のシステム全体データを取得
        cursor.execute("""
            SELECT temperature, humidity, supply_pressure, drain_pressure, timestamp
            FROM sensor_logs
            WHERE layer_id = 0
            ORDER BY timestamp DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        return dict(row) if row else {}


def create_analysis_prompt(sensor_data, has_previous_image=False):
    """AI分析用のプロンプトを作成"""
    if has_previous_image:
        # 2枚の画像を比較する場合のプロンプト
        prompt = """あなたは豆苗栽培の専門家AIです。
1枚目（昨日）と2枚目（今日）の画像を比較分析し、豆苗の成長状態を評価してください。

以下の形式で厳密に回答してください：

**成長率: [0-100の数値]%**
（0%=種まき直後、100%=収穫適期）

**状態サマリー:**
（今日の豆苗の状態を2-3文で簡潔に説明）

**前日比較:**
（昨日から今日にかけての変化を具体的に説明）

**アドバイス:**
• [具体的なアドバイス1]
• [具体的なアドバイス2]
"""
    else:
        # 1枚の画像を分析する場合のプロンプト
        prompt = """あなたは豆苗栽培の専門家AIです。
この画像を分析して、豆苗の成長状態を評価してください。

以下の形式で厳密に回答してください：

**成長率: [0-100の数値]%**
（0%=種まき直後、100%=収穫適期）

**状態サマリー:**
（豆苗の現在の状態を2-3文で簡潔に説明）

**アドバイス:**
• [具体的なアドバイス1]
• [具体的なアドバイス2]
"""

    # センサーデータを追加
    if sensor_data:
        prompt += "\n\n**現在の環境データ:**\n"
        if 'temperature' in sensor_data and sensor_data['temperature'] is not None:
            prompt += f"• 温度: {sensor_data['temperature']:.1f}℃\n"
        if 'humidity' in sensor_data and sensor_data['humidity'] is not None:
            prompt += f"• 湿度: {sensor_data['humidity']:.1f}%\n"
    
    prompt += "\n画像を分析して、上記の形式で回答してください。"
    return prompt


def _extract_section(pattern, text):
    """正規表現で特定のセクションを抽出するヘルパー関数"""
    import re
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ''

def parse_ai_response(response_text):
    """AIレスポンスから構造化データを抽出"""
    import re

    growth_rate_match = re.search(r'\*\*成長率:\*\*\s*(\d+\.?\d*)\s*%', response_text)
    growth_rate = float(growth_rate_match.group(1)) if growth_rate_match else 0.0

    summary = _extract_section(r'\*\*状態サマリー:\*\*(.*?)(?=\n\*\*|$)', response_text)
    comparison = _extract_section(r'\*\*前日比較:\*\*(.*?)(?=\n\*\*|$)', response_text)
    advice = _extract_section(r'\*\*アドバイス:\*\*(.*?)(?=\n\*\*|$)', response_text)

    # いずれのセクションも抽出できなかった場合は、レスポンス全体をサマリーに入れる
    if not any([summary, comparison, advice]):
        summary = response_text.strip()

    return {
        'growth_rate': growth_rate,
        'summary': summary,
        'comparison': comparison,
        'advice': advice,
    }


def save_ai_report(layer_id, image_path, growth_rate, ai_summary, ai_advice, ai_comparison, json_response):
    """AI解析結果をデータベースに保存"""
    timestamp = datetime.now().isoformat()
    
    with open_db() as conn:
        conn.execute("""
            INSERT INTO ai_reports (
                layer_id, timestamp, image_path, growth_rate, ai_summary, ai_advice,
                ai_comparison, json_response, slack_sent, llm_model_name, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'gemini-2.5-flash', ?)
        """, (
            layer_id, timestamp, image_path, growth_rate, ai_summary, ai_advice,
            ai_comparison, json_response, timestamp
        ))
    
    print(f"[INFO] AI解析結果をデータベースに保存しました")

