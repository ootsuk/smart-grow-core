from flask import Blueprint, jsonify, request
from database.db_manager import (
    select_system_config,
    open_db,
    get_latest_ai_report,
    get_ai_report_by_image
)
from web_app.services import (
    get_latest_sensor_data,
    get_latest_image,
    get_recent_alerts,
    get_next_schedules
)
from datetime import datetime, timedelta
import google.generativeai as genai
from core.utils import parse_ai_response
from config import LLM_API_KEY
from PIL import Image
import io
import os
from pathlib import Path
import glob

# Blueprintオブジェクトを作成
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Geminiモデルの初期化 (app.pyからロジックを移動)
if LLM_API_KEY:
    genai.configure(api_key=LLM_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-2.5-flash')
else:
    gemini_model = None

# ===== API エンドポイント =====

@api_bp.route('/dashboard-data')
def api_dashboard_data():
    """ダッシュボード用のデータをJSON形式で返す"""
    try:
        sensor_data = get_latest_sensor_data(layer_id=0)
        image_layer_id = request.args.get('layer_id', 1, type=int)
        latest_image = get_latest_image(image_layer_id)
        latest_ai_report = get_latest_ai_report(image_layer_id)
        alerts = get_recent_alerts(5)
        next_schedules = get_next_schedules(3)
        
        return jsonify({
            'success': True,
            'sensor_data': sensor_data,
            'latest_image': latest_image,
            'latest_ai_report': latest_ai_report,
            'alerts': alerts,
            'next_schedules': next_schedules,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/sensor-history')
def api_sensor_history():
    """センサー履歴データを取得（グラフ用）"""
    try:
        layer_id = 0
        hours = request.args.get('hours', 24, type=int)
        start_time = (datetime.now() - timedelta(hours=hours)).isoformat()

        interval_minutes = None
        if hours > 24 and hours <= 168:
            interval_minutes = 120
        elif hours > 168:
            interval_minutes = 360

        with open_db() as conn:
            cursor = conn.cursor()
            if interval_minutes is None:
                cursor.execute("SELECT timestamp, temperature, humidity, supply_pressure, drain_pressure FROM sensor_logs WHERE layer_id = ? AND timestamp >= ? ORDER BY timestamp ASC", (layer_id, start_time))
            else:
                cursor.execute("""
                    SELECT
                        datetime((strftime('%s', timestamp) / (? * 60)) * (? * 60), 'unixepoch') as timestamp,
                        ROUND(AVG(temperature), 1) as temperature,
                        ROUND(AVG(humidity), 1) as humidity,
                        ROUND(AVG(supply_pressure), 1) as supply_pressure,
                        ROUND(AVG(drain_pressure), 1) as drain_pressure
                    FROM sensor_logs WHERE layer_id = ? AND timestamp >= ?
                    GROUP BY 1 ORDER BY 1 ASC
                """, (interval_minutes, interval_minutes, layer_id, start_time))
            data = [dict(row) for row in cursor.fetchall()]

        return jsonify({'success': True, 'data': data, 'aggregated': interval_minutes is not None, 'interval_minutes': interval_minutes})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/images')
def api_images():
    """画像一覧を取得（ファイルシステムから直接）"""
    try:
        layer_id = request.args.get('layer_id', 1, type=int)
        limit = request.args.get('limit', 100, type=int)
        parent_dir = Path(__file__).parent.parent.parent
        image_dir = parent_dir / 'plant_images' / f'layer_{layer_id}'

        if not image_dir.exists():
            return jsonify({'success': True, 'images': []})

        image_files = []
        for ext in ['*.jpg', '*.jpeg', '*.png']:
            image_files.extend(glob.glob(str(image_dir / ext)))

        images = []
        for file_path in image_files:
            filename = os.path.basename(file_path)
            try:
                date_str = filename.split('.')[0]
                timestamp = datetime.strptime(date_str, '%Y%m%d_%H%M%S').isoformat()
            except ValueError:
                timestamp = datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()

            relative_path = f'plant_images/layer_{layer_id}/{filename}'
            images.append({'image_path': relative_path, 'timestamp': timestamp, 'filename': filename})

        images.sort(key=lambda x: x['timestamp'], reverse=True)
        return jsonify({'success': True, 'images': images[:limit]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/ai-reports-list')
def api_ai_reports_list():
    """AI解析レポート一覧を取得"""
    try:
        layer_id = request.args.get('layer_id', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        with open_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT report_id, timestamp, image_path, growth_rate, ai_summary, ai_advice, llm_model_name FROM ai_reports WHERE layer_id = ? ORDER BY timestamp DESC LIMIT ?", (layer_id, limit))
            reports = [dict(row) for row in cursor.fetchall()]
        return jsonify({'success': True, 'reports': reports})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/logs-list')
def api_logs_list():
    """システムログ一覧を取得"""
    try:
        log_level = request.args.get('log_level', None)
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        with open_db() as conn:
            cursor = conn.cursor()
            if log_level and log_level != 'ALL':
                cursor.execute("SELECT log_id, timestamp, layer_id, log_level, message, details FROM system_logs WHERE log_level = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?", (log_level, limit, offset))
            else:
                cursor.execute("SELECT log_id, timestamp, layer_id, log_level, message, details FROM system_logs ORDER BY timestamp DESC LIMIT ? OFFSET ?", (limit, offset))
            logs = [dict(row) for row in cursor.fetchall()]
        return jsonify({'success': True, 'logs': logs})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/system-config')
def api_system_config():
    """システム設定を取得"""
    try:
        config = select_system_config()
        return jsonify({'success': True, 'config': config})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/schedules')
def api_schedules_list():
    """スケジュール一覧を取得"""
    try:
        with open_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT schedule_id, layer_id, job_type, exec_time, is_enabled FROM schedules ORDER BY layer_id, job_type")
            schedules = [dict(row) for row in cursor.fetchall()]
        return jsonify({'success': True, 'schedules': schedules})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/schedules/<int:schedule_id>', methods=['PUT'])
def api_schedule_update(schedule_id):
    """スケジュールを更新"""
    try:
        data = request.get_json()
        with open_db() as conn:
            if 'exec_time' in data:
                conn.execute("UPDATE schedules SET exec_time = ? WHERE schedule_id = ?", (data['exec_time'], schedule_id))
            if 'is_enabled' in data:
                conn.execute("UPDATE schedules SET is_enabled = ? WHERE schedule_id = ?", (data['is_enabled'], schedule_id))
        return jsonify({'success': True, 'message': 'Schedule updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/schedules/<int:schedule_id>/toggle', methods=['PATCH'])
def api_schedule_toggle(schedule_id):
    """スケジュールの有効/無効を切り替え"""
    try:
        with open_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_enabled FROM schedules WHERE schedule_id = ?", (schedule_id,))
            row = cursor.fetchone()
            if not row:
                return jsonify({'success': False, 'error': 'Schedule not found'}), 404
            new_state = not row['is_enabled']
            cursor.execute("UPDATE schedules SET is_enabled = ? WHERE schedule_id = ?", (new_state, schedule_id))
        return jsonify({'success': True, 'is_enabled': new_state})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/ai-report/<int:report_id>')
def api_ai_report(report_id):
    """AI解析レポートの詳細を取得"""
    try:
        with open_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ai_reports WHERE report_id = ?", (report_id,))
            report = dict(cursor.fetchone()) if cursor.fetchone() else None
        if report:
            return jsonify({'success': True, 'report': report})
        return jsonify({'success': False, 'error': 'Report not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/ai-report-by-image')
def api_ai_report_by_image():
    """画像パスからAI解析レポートを取得"""
    try:
        image_path = request.args.get('image_path')
        if not image_path:
            return jsonify({'success': False, 'error': 'image_path parameter is required'}), 400
        report = get_ai_report_by_image(image_path)
        if report:
            return jsonify({'success': True, 'report': report})
        return jsonify({'success': False, 'error': 'No AI report found for this image'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/ai-chat', methods=['POST'])
def api_ai_chat():
    """AI チャット API - Gemini API を使用"""
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        image_filename = data.get('image_filename')
        sensor_data = data.get('sensor_data', {})

        if not user_message or not gemini_model:
            return jsonify({'error': 'Invalid request or AI model not configured'}), 400

        system_prompt = create_system_prompt(sensor_data, image_filename)

        image_data = None
        if image_filename:
            parent_dir = Path(__file__).parent.parent.parent
            image_path = parent_dir / 'plant_images' / f'layer_1/{image_filename}'
            if image_path.exists():
                with open(image_path, 'rb') as f:
                    image_data = Image.open(io.BytesIO(f.read()))

        content = [system_prompt + "\n\n" + user_message]
        if image_data:
            content.append(image_data)

        response = gemini_model.generate_content(content)
        ai_response = response.text

        # オプショナル: 解析結果を保存
        if image_data:
            try:
                analysis_result = parse_ai_response(ai_response)
                image_relative_path = f'plant_images/layer_1/{image_filename}'
                timestamp = datetime.now().isoformat()
                with open_db() as conn:
                    conn.execute("""
                        INSERT INTO ai_reports (layer_id, timestamp, image_path, growth_rate, ai_summary, ai_advice, json_response, llm_model_name, last_updated)
                        VALUES (1, ?, ?, ?, ?, ?, ?, 'gemini-2.5-flash', ?)
                    """, (timestamp, image_relative_path, analysis_result['growth_rate'], analysis_result['summary'], analysis_result['advice'], ai_response, timestamp))
            except Exception as e:
                print(f"AI chat report save error: {e}")

        return jsonify({'response': ai_response, 'timestamp': datetime.now().isoformat()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def create_system_prompt(sensor_data, image_filename):
    """システムプロンプトを作成"""
    prompt = "あなたは豆苗栽培の専門AIアシスタントです。\n"
    if sensor_data:
        prompt += "\n**現在のシステム情報:**\n"
        if sensor_data.get('temperature'): prompt += f"- 温度: {sensor_data['temperature']}℃\n"
        if sensor_data.get('humidity'): prompt += f"- 湿度: {sensor_data['humidity']}%\n"
    if image_filename:
        prompt += f"\n**添付画像:** {image_filename}\n画像を分析し、成長状態や問題点を教えてください。\n"
    prompt += "\n---\n\n"
    return prompt
