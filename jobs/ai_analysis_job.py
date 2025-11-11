import os
import sys
from pathlib import Path
from datetime import datetime

# 親ディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

# gRPC DNS設定（Gemini API用）
os.environ['GRPC_DNS_RESOLVER'] = 'native'

from database.db_manager import insert_system_log, select_system_config, open_db
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
        
        # 画像を読み込み
        with open(full_image_path, 'rb') as f:
            image_bytes = f.read()
        image_data = Image.open(io.BytesIO(image_bytes))
        
        # 最新のセンサーデータを取得
        sensor_data = get_latest_sensor_data(layer_id)
        
        # プロンプトの作成
        prompt = create_analysis_prompt(sensor_data)
        
        # Gemini APIで分析
        print(f"[INFO] Gemini APIで画像分析中...")
        response = model.generate_content([prompt, image_data])
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


def create_analysis_prompt(sensor_data):
    """AI分析用のプロンプトを作成"""
    prompt = """あなたは豆苗栽培の専門家AIです。
この画像を分析して、豆苗の成長状態を評価してください。

以下の形式で回答してください：

**成長率: [0-100の数値]%**
（0%=種まき直後、100%=収穫適期）

**状態サマリー:**
（豆苗の現在の状態を2-3文で簡潔に説明）

**アドバイス:**
• [具体的なアドバイス1]
• [具体的なアドバイス2]
• [具体的なアドバイス3]

"""
    
    # センサーデータを追加
    if sensor_data:
        prompt += "\n**現在の環境データ:**\n"
        if 'temperature' in sensor_data:
            prompt += f"• 温度: {sensor_data['temperature']}℃\n"
        if 'humidity' in sensor_data:
            prompt += f"• 湿度: {sensor_data['humidity']}%\n"
        if 'supply_pressure' in sensor_data:
            prompt += f"• 給水タンク: {sensor_data['supply_pressure']} kPa\n"
        if 'drain_pressure' in sensor_data:
            prompt += f"• 排水タンク: {sensor_data['drain_pressure']} kPa\n"
    
    prompt += "\n画像を分析して、上記の形式で回答してください。"
    
    return prompt


def parse_ai_response(response_text):
    """AIレスポンスから構造化データを抽出"""
    result = {
        'growth_rate': 0.0,
        'summary': '',
        'advice': ''
    }
    
    try:
        # 成長率を抽出
        import re
        growth_match = re.search(r'成長率[:\s]*(\d+\.?\d*)\s*%', response_text)
        if growth_match:
            result['growth_rate'] = float(growth_match.group(1))
        
        # 状態サマリーを抽出
        summary_match = re.search(r'\*\*状態サマリー:\*\*\s*(.*?)(?=\*\*|$)', response_text, re.DOTALL)
        if summary_match:
            result['summary'] = summary_match.group(1).strip()[:500]  # 最大500文字
        else:
            # サマリーが見つからない場合は全文の最初の200文字
            result['summary'] = response_text[:200].strip()
        
        # アドバイスを抽出
        advice_match = re.search(r'\*\*アドバイス:\*\*\s*(.*?)(?=\*\*|$)', response_text, re.DOTALL)
        if advice_match:
            result['advice'] = advice_match.group(1).strip()[:500]  # 最大500文字
        else:
            result['advice'] = '定期的な水やりと環境管理を続けてください。'
        
    except Exception as e:
        print(f"[WARNING] AI response parsing error: {e}")
        result['summary'] = response_text[:200]  # フォールバック
    
    return result


def save_ai_report(layer_id, image_path, growth_rate, ai_summary, ai_advice, json_response):
    """AI解析結果をデータベースに保存"""
    timestamp = datetime.now().isoformat()
    
    with open_db() as conn:
        conn.execute("""
            INSERT INTO ai_reports (
                layer_id, timestamp, image_path, growth_rate, ai_summary, ai_advice,
                json_response, slack_sent, llm_model_name, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'gemini-2.5-flash', ?)
        """, (
            layer_id, timestamp, image_path, growth_rate, ai_summary, ai_advice,
            json_response, timestamp
        ))
    
    print(f"[INFO] AI解析結果をデータベースに保存しました")

