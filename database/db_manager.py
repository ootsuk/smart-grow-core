import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager

from config import * # DB_PATH, DEFAULT_LAYERS, DEFAULT_SCHEDULES, DEFAULT_SYSTEM_CONFIG をインポート

@contextmanager
def open_db(db_path=None):
    """
    データベース接続を開き、コンテキストを抜けるときにコミット/ロールバック/クローズを行う共通関数。
    """
    if db_path is None:
        db_path = DB_PATH
        
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        # カラム名でアクセスできるように設定
        conn.row_factory = sqlite3.Row
        yield conn
        # 処理が成功した場合にコミット
        conn.commit()
        
    except sqlite3.Error as e:
        print(f"DBエラー: {e}")
        with open("db_error.log", "a") as f:
            f.write(f"[{datetime.now()}] {e}\n")
        if conn:
            # エラー発生時にロールバック
            conn.rollback()
        # エラーを再送出
        raise
        
    finally:
        if conn:
            # 接続を閉じる
            conn.close()

def get_create_table_queries():
    """
    データベース初期化のためのテーブル作成クエリリストを返す。
    """
    return [
        # layers テーブル
        """
        CREATE TABLE IF NOT EXISTS layers (
            layer_id INTEGER PRIMARY KEY,
            layer_name TEXT NOT NULL,
            cam_id INTEGER NOT NULL,
            is_active BOOLEAN NOT NULL
        );
        """,
        # schedules テーブル
        """
        CREATE TABLE IF NOT EXISTS schedules (
            schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            layer_id INTEGER,
            job_type TEXT NOT NULL,
            exec_time TEXT NOT NULL,
            is_enabled BOOLEAN NOT NULL,
            FOREIGN KEY (layer_id) REFERENCES layers (layer_id)
        );
        """,
        # sensor_logs テーブル (温湿度と水圧の時系列ログ)
        """
        CREATE TABLE IF NOT EXISTS sensor_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            layer_id INTEGER,
            timestamp TEXT NOT NULL,
            temperature REAL,
            humidity REAL,
            supply_pressure REAL,
            drain_pressure REAL,
            FOREIGN KEY (layer_id) REFERENCES layers (layer_id)
        );
        """,
        # system_config テーブル (各種設定と閾値、GPIOピン)
        """
        CREATE TABLE IF NOT EXISTS system_config (
            config_id INTEGER PRIMARY KEY,
            water_duration_sec INTEGER NOT NULL,
            slack_webhook_url TEXT,
            temp_high_threshold REAL NOT NULL,
            temp_low_threshold REAL NOT NULL,
            pump_gpio_sig INTEGER NOT NULL,
            dashboard_url TEXT,
            i2c_bus_num INTEGER NOT NULL,
            supply_low_threshold REAL,
            drain_high_threshold REAL,
            supply_pressure_gpio_sig INTEGER,
            drain_pressure_gpio_sig INTEGER,
            llm_api_key_enc TEXT,
            llm_model_name TEXT,
            last_modified TEXT NOT NULL
        );
        """,
        # ai_reports テーブル
        """
        CREATE TABLE IF NOT EXISTS ai_reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            layer_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            image_path TEXT NOT NULL,
            growth_rate REAL,
            ai_summary TEXT,
            ai_advice TEXT,
            ai_comparison TEXT, -- Added: 前日比較の結果
            json_response TEXT,
            slack_sent INTEGER DEFAULT 0,
            error_log TEXT,
            llm_model_name TEXT,
            last_updated TEXT NOT NULL,
            FOREIGN KEY (layer_id) REFERENCES layers (layer_id)
        );
        """,
        # system_logs テーブル (システムの動作ログやアラート)
        """
        CREATE TABLE IF NOT EXISTS system_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            layer_id INTEGER NOT NULL,
            log_level TEXT NOT NULL, --INFO, WARNING, ERROR, CRITICAL
            message TEXT NOT NULL,
            details TEXT
        );
        """
    ]

def init_db(db_path=DB_PATH):
    """
    データベースが存在しない場合に作成・初期化し、デフォルト値を挿入する。
    """
    # 本番運用を想定し、意図しない再初期化を防止
    if os.environ.get("APP_ENV") == "production" and os.path.exists(db_path):
        print(f"本番環境のため、既存のDB {db_path} の初期化はスキップされました。")
        return

    if not os.path.exists(db_path):
        print(f"初期化中: {db_path}")
        with open_db(db_path) as conn:
            cursor = conn.cursor()
            
            # 1. テーブル作成
            for query in get_create_table_queries():
                cursor.execute(query)

            # 2. デフォルトデータ挿入
            cursor.executemany(
                "INSERT INTO layers (layer_id, layer_name, cam_id, is_active) VALUES (?, ?, ?, ?)",
                DEFAULT_LAYERS
            )
            cursor.executemany(
                "INSERT INTO schedules (layer_id, job_type, exec_time, is_enabled) VALUES (?, ?, ?, ?)",
                DEFAULT_SCHEDULES
            )

            now = datetime.now().isoformat()
            cfg = DEFAULT_SYSTEM_CONFIG
            
            # system_config 挿入
            cursor.execute(
                """
                INSERT INTO system_config (
                    config_id, water_duration_sec, slack_webhook_url, temp_high_threshold, temp_low_threshold,
                    pump_gpio_sig, dashboard_url, i2c_bus_num, supply_low_threshold, drain_high_threshold,
                    supply_pressure_gpio_sig, drain_pressure_gpio_sig, llm_api_key_enc, llm_model_name, last_modified
                ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cfg['water_duration_sec'], cfg['slack_webhook_url'], cfg['temp_high_threshold'], cfg['temp_low_threshold'],
                    cfg['pump_gpio_sig'], cfg['dashboard_url'], cfg['i2c_bus_num'], cfg['supply_low_threshold'],
                    cfg['drain_high_threshold'], cfg['supply_pressure_gpio_sig'], cfg['drain_pressure_gpio_sig'],
                    cfg['llm_api_key_enc'], cfg['llm_model_name'], now
                )
            )

            print("初期化完了")
    else:
        print(f"{db_path} は既に存在します")

def insert_sensor_log(layer_id, temperature=None, humidity=None, supply_pressure=None, drain_pressure=None):
    """
    温湿度と水圧のデータを sensor_logs テーブルに記録する。
    """
    timestamp = datetime.now().isoformat()
    with open_db() as conn:
        conn.execute(
            "INSERT INTO sensor_logs (layer_id, timestamp, temperature, humidity, supply_pressure, drain_pressure) VALUES (?, ?, ?, ?, ?, ?)",
            (layer_id, timestamp, temperature, humidity, supply_pressure, drain_pressure)
        )

def insert_camera_log(layer_id, image_path):
    """
    カメラ撮影後にAI解析に前段階として画像パスを含むレポートの器を作成する
    """
    timestamp = datetime.now().isoformat()
    with open_db() as conn:
        conn.execute(
            """
            INSERT INTO ai_reports (
                layer_id, timestamp, growth_rate, ai_summary, ai_advice, ai_comparison, image_path, json_response, slack_sent, llm_model_name, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (layer_id, timestamp, 0.0, 'N/A', '', 'N/A', image_path, '{}', 0, 'gpt-4-turbo', timestamp)
        )


def insert_system_log(layer_id, log_level, message, details=None):
    """
    システムの動作ログやアラートを system_logs テーブルに記録する。
    """
    timestamp = datetime.now().isoformat()
    with open_db() as conn:
        conn.execute(
            "INSERT INTO system_logs (timestamp, layer_id, log_level, message, details) VALUES (?, ?, ?, ?, ?)",
            (timestamp, layer_id, log_level, message, details)
        )

def select_layer_info(layer_id):
    """
    指定された layer_id の情報を取得する。
    """
    with open_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM layers WHERE layer_id = ?", (layer_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_previous_day_image(layer_id, current_image_path):
    """
    指定された今日の画像パスから日付を読み取り、
    その前日の最新の画像パスを取得する。
    """
    from datetime import datetime, timedelta
    import os

    try:
        # 今日の画像ファイル名から日付を抽出 (例: 20251112_090000.jpg)
        basename = os.path.basename(current_image_path)
        today_str = basename.split('_')[0]
        today_dt = datetime.strptime(today_str, '%Y%m%d')

        # 前日の日付を計算
        previous_day_dt = today_dt - timedelta(days=1)
        previous_day_str = previous_day_dt.strftime('%Y%m%d')

        with open_db() as conn:
            cursor = conn.cursor()
            # 前日の画像の中で、最も新しいものを取得
            cursor.execute("""
                SELECT image_path FROM ai_reports
                WHERE layer_id = ?
                  AND image_path LIKE ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (layer_id, f'%/{previous_day_str}_%'))

            row = cursor.fetchone()
            return row['image_path'] if row else None

    except (ValueError, IndexError) as e:
        print(f"Error parsing date from image path '{current_image_path}': {e}")
        return None

def select_schedules():
    """
    有効なスケジュール情報をすべて取得する。
    """
    with open_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM schedules WHERE is_enabled = 1")
        return [dict(row) for row in cursor.fetchall()]

def select_system_config():
    """
    システム設定を system_config テーブルから取得し、辞書として返す。
    """
    config = {}
    with open_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM system_config WHERE config_id = 1")
        row = cursor.fetchone()
        
        if row:
            # sqlite3.Row オブジェクトを辞書に変換し、数値型を適切に変換
            for k, v in dict(row).items():
                if k == 'config_id': continue
                try:
                    # 文字列が数値（整数または浮動小数点数）のように見える場合、型変換を試みる
                    if isinstance(v, str) and (v.replace('.', '', 1).isdigit() or (v.startswith('-') and v[1:].replace('.', '', 1).isdigit())):
                        config[k] = float(v) if '.' in v else int(v)
                    else:
                        config[k] = v
                except ValueError:
                    # 変換失敗時（通常発生しないが安全のため）
                    config[k] = v
        return config
    
def get_latest_tank_status(layer_id):
    """
    最新の給水圧と排水圧のログを取得する。
    """
    with open_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT supply_pressure, drain_pressure, timestamp FROM sensor_logs WHERE layer_id=? ORDER BY timestamp DESC LIMIT 1",
            (layer_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def select_i2c_bus_num():
    """
    system_config テーブルから I2C バス番号を取得する。
    """
    system_config = select_system_config() or {}
    i2c_bus = system_config.get('i2c_bus_num', 1)
    return i2c_bus

def get_latest_ai_report(layer_id):
    """
    指定されたレイヤーの最新のAI解析レポートを取得する。
    """
    with open_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM ai_reports
            WHERE layer_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (layer_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_today_ai_report(layer_id):
    """
    本日撮影された画像の最新AI解析レポートを取得する。
    画像ファイル名から日付を判定（YYYYMMDD形式）。
    """
    from datetime import datetime
    
    today_str = datetime.now().strftime('%Y%m%d')  # 例: '20251112'
    
    with open_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM ai_reports
            WHERE layer_id = ?
              AND image_path LIKE ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (layer_id, f'%/{today_str}_%'))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_ai_report_by_image(image_path):
    """
    画像パスから対応するAI解析レポートを取得する。
    """
    with open_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM ai_reports
            WHERE image_path = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (image_path,))
        row = cursor.fetchone()
        return dict(row) if row else None