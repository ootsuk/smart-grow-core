from database.db_manager import open_db, select_schedules

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
