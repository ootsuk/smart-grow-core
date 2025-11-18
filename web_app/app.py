import sys
import os
from pathlib import Path

# 親ディレクトリをパスに追加（database, config等にアクセスするため）
sys.path.insert(0, str(Path(__file__).parent.parent))

# gRPC DNS解決の設定（Gemini API接続のため、importより前に設定）
os.environ['GRPC_DNS_RESOLVER'] = 'native'

from flask import Flask, render_template, jsonify, request, send_from_directory
from database.db_manager import (
    select_system_config, 
    select_schedules,
    open_db,
    get_latest_ai_report,
    get_today_ai_report,
    get_ai_report_by_image
)
from jobs.ai_analysis_job import parse_ai_response
from datetime import datetime, timedelta
import google.generativeai as genai
from config import LLM_API_KEY
from PIL import Image
import io

app = Flask(__name__)

# Gemini API の設定
if LLM_API_KEY:
    genai.configure(api_key=LLM_API_KEY)
    # 最新のモデル名に変更（gemini-1.5-flashは非推奨）
    gemini_model = genai.GenerativeModel('gemini-2.5-flash')
    print("✅ Gemini API初期化成功: gemini-2.5-flash")
else:
    gemini_model = None
    print("⚠️ Warning: LLM_API_KEY が設定されていません。AI機能は無効です。")

# 画像ファイルを配信するためのルート
@app.route('/plant_images/<path:filename>')
def serve_plant_images(filename):
    """plant_images ディレクトリの画像を配信"""
    # 親ディレクトリのplant_imagesを参照
    parent_dir = Path(__file__).parent.parent
    return send_from_directory(parent_dir / 'plant_images', filename)

# ===== ヘルパー関数 =====

def get_latest_sensor_data(layer_id=1):
    """最新のセンサーデータを取得"""
    with open_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT temperature, humidity, supply_pressure, drain_pressure, timestamp
            FROM sensor_logs
            WHERE layer_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (layer_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_latest_image(layer_id=1):
    """最新の画像を取得"""
    with open_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT image_path, timestamp
            FROM ai_reports
            WHERE layer_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (layer_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_recent_alerts(limit=5):
    """最近のアラートを取得"""
    with open_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, layer_id, log_level, message, details
            FROM system_logs
            WHERE log_level IN ('CRITICAL', 'ERROR', 'WARNING')
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

def get_next_schedules(limit=3):
    """次回実行予定のスケジュールを取得"""
    schedules = select_schedules()
    # exec_timeでソート
    schedules.sort(key=lambda x: x['exec_time'])
    return schedules[:limit]


# ===== ルーティング =====

@app.route('/')
def dashboard():
    """ダッシュボード画面"""
    return render_template('dashboard.html')

@app.route('/sensors')
def sensors():
    """センサーグラフ画面"""
    return render_template('sensors.html')

@app.route('/gallery')
def gallery():
    """画像ギャラリー画面"""
    return render_template('gallery.html')

@app.route('/ai-reports')
def ai_reports():
    """AI相談チャット画面"""
    return render_template('ai_chat.html')

@app.route('/schedules')
def schedules():
    """スケジュール管理画面"""
    return render_template('schedules.html')

# 設定ページは未実装のためコメントアウト
# @app.route('/settings')
# def settings():
#     """システム設定画面"""
#     return render_template('settings.html')

@app.route('/logs')
def logs():
    """システムログ画面"""
    return render_template('logs.html')


# ===== API エンドポイント =====

@app.route('/api/dashboard-data')
def api_dashboard_data():
    """ダッシュボード用のデータをJSON形式で返す"""
    try:
        # センサーデータはLayer 0（システム全体）から取得
        sensor_data = get_latest_sensor_data(layer_id=0)
        
        # 画像は指定されたlayer（デフォルト=1）から取得
        image_layer_id = request.args.get('layer_id', 1, type=int)
        latest_image = get_latest_image(image_layer_id)
        
        # 本日撮影された画像のAI解析レポートを取得
        latest_ai_report = get_today_ai_report(image_layer_id)
        
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
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sensor-history')
def api_sensor_history():
    """センサー履歴データを取得（グラフ用）"""
    try:
        # センサーデータはLayer 0（システム全体）から取得
        layer_id = 0
        hours = request.args.get('hours', 24, type=int)
        
        start_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # 期間に応じて集約間隔を決定
        if hours <= 24:
            # 24時間: 30分ごと（そのまま）
            interval_minutes = None  # 集約なし
        elif hours <= 168:
            # 7日間: 2時間ごとの平均
            interval_minutes = 120
        else:
            # 30日間: 6時間ごとの平均
            interval_minutes = 360
        
        with open_db() as conn:
            cursor = conn.cursor()
            
            if interval_minutes is None:
                # 集約なし（24時間表示）
                cursor.execute("""
                    SELECT timestamp, temperature, humidity, supply_pressure, drain_pressure
                    FROM sensor_logs
                    WHERE layer_id = ? AND timestamp >= ?
                    ORDER BY timestamp ASC
                """, (layer_id, start_time))
                
                rows = cursor.fetchall()
                data = [dict(row) for row in rows]
            else:
                # データ集約（7日/30日表示）
                cursor.execute("""
                    SELECT 
                        datetime(
                            (strftime('%s', timestamp) / (? * 60)) * (? * 60),
                            'unixepoch'
                        ) as timestamp,
                        ROUND(AVG(temperature), 1) as temperature,
                        ROUND(AVG(humidity), 1) as humidity,
                        ROUND(AVG(supply_pressure), 1) as supply_pressure,
                        ROUND(AVG(drain_pressure), 1) as drain_pressure
                    FROM sensor_logs
                    WHERE layer_id = ? AND timestamp >= ?
                    GROUP BY datetime(
                        (strftime('%s', timestamp) / (? * 60)) * (? * 60),
                        'unixepoch'
                    )
                    ORDER BY timestamp ASC
                """, (interval_minutes, interval_minutes, layer_id, start_time, interval_minutes, interval_minutes))
                
                rows = cursor.fetchall()
                data = [dict(row) for row in rows]
        
        return jsonify({
            'success': True,
            'data': data,
            'aggregated': interval_minutes is not None,
            'interval_minutes': interval_minutes
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/images')
def api_images():
    """画像一覧を取得（ファイルシステムから直接）"""
    try:
        import glob
        from datetime import datetime
        
        layer_id = request.args.get('layer_id', 1, type=int)
        limit = request.args.get('limit', 100, type=int)
        
        # plant_imagesディレクトリのパス
        parent_dir = Path(__file__).parent.parent
        image_dir = parent_dir / 'plant_images' / f'layer_{layer_id}'
        
        if not image_dir.exists():
            return jsonify({
                'success': True,
                'images': []
            })
        
        # jpg, jpeg, png形式の画像を取得
        image_files = []
        for ext in ['*.jpg', '*.jpeg', '*.png']:
            image_files.extend(glob.glob(str(image_dir / ext)))
        
        # ファイル名から日時を抽出してソート
        images = []
        for file_path in image_files:
            filename = os.path.basename(file_path)
            # ファイル名から日時を抽出（例: 20251110_090001.jpg）
            try:
                date_str = filename.split('.')[0]  # 拡張子を除去
                timestamp = datetime.strptime(date_str, '%Y%m%d_%H%M%S').isoformat()
            except:
                # パースできない場合はファイルの更新日時を使用
                mtime = os.path.getmtime(file_path)
                timestamp = datetime.fromtimestamp(mtime).isoformat()
            
            # 相対パスを生成
            relative_path = f'plant_images/layer_{layer_id}/{filename}'
            
            images.append({
                'image_path': relative_path,
                'timestamp': timestamp,
                'filename': filename
            })
        
        # 日時でソート（新しい順）
        images.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # 件数制限
        images = images[:limit]
        
        return jsonify({
            'success': True,
            'images': images
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/ai-reports-list')
def api_ai_reports_list():
    """AI解析レポート一覧を取得"""
    try:
        layer_id = request.args.get('layer_id', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        
        with open_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT report_id, timestamp, image_path, growth_rate, 
                       ai_summary, ai_advice, llm_model_name
                FROM ai_reports
                WHERE layer_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (layer_id, limit))
            
            rows = cursor.fetchall()
            reports = [dict(row) for row in rows]
        
        return jsonify({
            'success': True,
            'reports': reports
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/logs-list')
def api_logs_list():
    """システムログ一覧を取得"""
    try:
        log_level = request.args.get('log_level', None)
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        with open_db() as conn:
            cursor = conn.cursor()
            
            if log_level and log_level != 'ALL':
                cursor.execute("""
                    SELECT log_id, timestamp, layer_id, log_level, message, details
                    FROM system_logs
                    WHERE log_level = ?
                    ORDER BY timestamp DESC
                    LIMIT ? OFFSET ?
                """, (log_level, limit, offset))
            else:
                cursor.execute("""
                    SELECT log_id, timestamp, layer_id, log_level, message, details
                    FROM system_logs
                    ORDER BY timestamp DESC
                    LIMIT ? OFFSET ?
                """, (limit, offset))
            
            rows = cursor.fetchall()
            logs = [dict(row) for row in rows]
        
        return jsonify({
            'success': True,
            'logs': logs
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/system-config')
def api_system_config():
    """システム設定を取得"""
    try:
        config = select_system_config()
        return jsonify({
            'success': True,
            'config': config
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ===== スケジュール管理 API =====

@app.route('/schedules')
def schedules_page():
    """スケジュール管理ページ"""
    return render_template('schedules.html')

@app.route('/api/schedules')
def api_schedules_list():
    """スケジュール一覧を取得"""
    try:
        with open_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT schedule_id, layer_id, job_type, exec_time, is_enabled
                FROM schedules
                ORDER BY layer_id, job_type
            """)
            rows = cursor.fetchall()
            schedules = [dict(row) for row in rows]
        
        return jsonify({
            'success': True,
            'schedules': schedules
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/schedules/<int:schedule_id>', methods=['PUT'])
def api_schedule_update(schedule_id):
    """スケジュールを更新"""
    try:
        data = request.get_json()
        exec_time = data.get('exec_time')
        is_enabled = data.get('is_enabled')
        
        if exec_time is None and is_enabled is None:
            return jsonify({
                'success': False,
                'error': 'exec_time or is_enabled is required'
            }), 400
        
        with open_db() as conn:
            cursor = conn.cursor()
            
            # 更新するフィールドを動的に構築
            update_fields = []
            params = []
            
            if exec_time is not None:
                update_fields.append('exec_time = ?')
                params.append(exec_time)
            
            if is_enabled is not None:
                update_fields.append('is_enabled = ?')
                params.append(1 if is_enabled else 0)
            
            params.append(schedule_id)
            
            query = f"UPDATE schedules SET {', '.join(update_fields)} WHERE schedule_id = ?"
            cursor.execute(query, params)
        
        return jsonify({
            'success': True,
            'message': 'Schedule updated successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/schedules/<int:schedule_id>/toggle', methods=['PATCH'])
def api_schedule_toggle(schedule_id):
    """スケジュールの有効/無効を切り替え"""
    try:
        with open_db() as conn:
            cursor = conn.cursor()
            
            # 現在の状態を取得
            cursor.execute("SELECT is_enabled FROM schedules WHERE schedule_id = ?", (schedule_id,))
            row = cursor.fetchone()
            
            if not row:
                return jsonify({
                    'success': False,
                    'error': 'Schedule not found'
                }), 404
            
            # トグル
            new_state = 0 if row['is_enabled'] else 1
            cursor.execute("UPDATE schedules SET is_enabled = ? WHERE schedule_id = ?", (new_state, schedule_id))
        
        return jsonify({
            'success': True,
            'is_enabled': bool(new_state)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ===== AI チャット API =====

@app.route('/api/ai-report/<int:report_id>')
def api_ai_report(report_id):
    """AI解析レポートの詳細を取得"""
    try:
        with open_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ai_reports WHERE report_id = ?", (report_id,))
            row = cursor.fetchone()
            
            if row:
                report = dict(row)
                return jsonify({
                    'success': True,
                    'report': report
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Report not found'
                }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/ai-report-by-image')
def api_ai_report_by_image():
    """画像パスからAI解析レポートを取得"""
    try:
        image_path = request.args.get('image_path')
        if not image_path:
            return jsonify({
                'success': False,
                'error': 'image_path parameter is required'
            }), 400
        
        report = get_ai_report_by_image(image_path)
        
        if report:
            return jsonify({
                'success': True,
                'report': report
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No AI report found for this image'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/ai-chat', methods=['POST'])
def api_ai_chat():
    """AI チャット API - Gemini API を使用"""
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        image_filename = data.get('image_filename')
        sensor_data = data.get('sensor_data', {})
        
        if not user_message:
            return jsonify({'error': 'メッセージが空です'}), 400
        
        # Gemini API が設定されていない場合
        if not gemini_model:
            return jsonify({'error': 'AI機能が無効です。LLM_API_KEYを設定してください。'}), 503
        
        # システムプロンプトの作成
        system_prompt = create_system_prompt(sensor_data, image_filename)
        
        # 画像がある場合は読み込む
        image_data = None
        if image_filename:
            try:
                # Layer 1を想定（必要に応じて変更）
                parent_dir = Path(__file__).parent.parent
                image_path = parent_dir / 'plant_images' / 'layer_1' / image_filename
                
                if image_path.exists():
                    # 画像ファイルを読み込み
                    with open(image_path, 'rb') as f:
                        image_bytes = f.read()
                    
                    # Gemini用に画像データを準備
                    image_data = Image.open(io.BytesIO(image_bytes))
                else:
                    print(f"Warning: 画像ファイルが見つかりません: {image_path}")
            except Exception as e:
                print(f"画像読み込みエラー: {e}")
        
        # Gemini APIに送信
        try:
            if image_data:
                # 画像付きメッセージ
                print(f"[AI Chat] 画像付きリクエスト: {user_message[:50]}...")
                response = gemini_model.generate_content([
                    system_prompt + "\n\n" + user_message,
                    image_data
                ])
            else:
                # テキストのみ
                print(f"[AI Chat] テキストリクエスト: {user_message[:50]}...")
                response = gemini_model.generate_content(system_prompt + "\n\n" + user_message)
            
            ai_response = response.text
            print(f"[AI Chat] レスポンス受信: {len(ai_response)}文字")
            
            # 画像付き分析の場合、結果をai_reportsテーブルに保存
            if image_data and image_filename:
                try:
                    # レイヤーIDを画像パスから取得（例: layer_1/20251111_090000.jpg → layer_id=1）
                    layer_id = 1  # デフォルト
                    if 'layer_' in image_filename:
                        # ファイル名からlayer_idを抽出する試み
                        pass  # 今は固定でlayer_id=1
                    
                    # 画像の相対パス
                    image_relative_path = f'plant_images/layer_{layer_id}/{image_filename}'
                    
                    # AI応答を解析
                    analysis_result = parse_ai_response(ai_response)
                    
                    # ai_reportsテーブルに保存
                    timestamp = datetime.now().isoformat()
                    with open_db() as conn:
                        conn.execute("""
                            INSERT INTO ai_reports (
                                layer_id, timestamp, image_path, growth_rate, ai_summary, ai_advice,
                                ai_comparison, json_response, slack_sent, llm_model_name, last_updated
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'gemini-2.5-flash', ?)
                        """, (
                            layer_id, timestamp, image_relative_path, 
                            analysis_result['growth_rate'], 
                            analysis_result['summary'], 
                            analysis_result['advice'],
                            analysis_result['comparison'],
                            ai_response, timestamp
                        ))
                    
                    print(f"[AI Chat] AI解析結果をデータベースに保存しました")
                    
                except Exception as save_error:
                    # 保存エラーはユーザーには表示せず、ログのみ
                    print(f"[WARNING] AI解析結果の保存に失敗: {save_error}")
            
            return jsonify({
                'response': ai_response,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            error_msg = str(e)
            print(f"[AI Chat] Gemini API エラー: {error_msg}")
            
            # エラーメッセージをユーザーフレンドリーに
            if 'Timeout' in error_msg or 'DNS' in error_msg:
                user_error = 'Gemini APIへの接続がタイムアウトしました。ネットワーク接続を確認してください。'
            elif '403' in error_msg or 'API key' in error_msg:
                user_error = 'APIキーが無効です。設定を確認してください。'
            elif '429' in error_msg:
                user_error = 'APIの使用制限に達しました。しばらく待ってから再試行してください。'
            else:
                user_error = f'AI処理中にエラーが発生しました: {error_msg}'
            
            return jsonify({'error': user_error}), 500
        
    except Exception as e:
        print(f"API エラー: {e}")
        return jsonify({'error': str(e)}), 500


def create_system_prompt(sensor_data, image_filename):
    """システムプロンプトを作成"""
    prompt = """あなたは豆苗栽培の専門AIアシスタントです。
ユーザーの質問に対して、以下の情報を参考にしながら、正確で親切な回答をしてください。

**回答時の注意事項:**
- Markdown形式で回答してください
- 見出し、箇条書き、表、コードブロックなどを適切に使用してください
- 具体的な数値やデータがある場合は、それを明示してください
- ユーザーが理解しやすいように、分かりやすい言葉で説明してください
- 必要に応じて絵文字（🌱、💧、☀️など）を使って見やすくしてください

"""
    
    # センサーデータを追加
    if sensor_data:
        prompt += "\n**現在のシステム情報:**\n"
        if 'temperature' in sensor_data and sensor_data['temperature']:
            prompt += f"- 温度: {sensor_data['temperature']}℃\n"
        if 'humidity' in sensor_data and sensor_data['humidity']:
            prompt += f"- 湿度: {sensor_data['humidity']}%\n"
        # 注意: タンク圧力データは植物成長分析に不要なため除外
    
    # 画像情報を追加
    if image_filename:
        prompt += f"\n**添付画像:** {image_filename}\n"
        prompt += "画像を分析して、豆苗の成長状態、健康状態、問題点などを詳しく教えてください。\n"
    
    prompt += "\n---\n\n"
    
    return prompt


if __name__ == '__main__':
    # 開発用サーバー起動
    app.run(host='0.0.0.0', port=8080, debug=True)

