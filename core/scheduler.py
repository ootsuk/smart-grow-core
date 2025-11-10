from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import time
import sys
from database.db_manager import select_schedules, insert_system_log, open_db
from jobs.camera_jobs import execute_photo_job
from jobs.sensor_jobs import execute_sensor_job
from jobs.pump_jobs import execute_pump_job 

# グローバルなスケジューラインスタンスを定義
scheduler = BackgroundScheduler()

# スケジュール監視用の変数
last_schedule_check_time = None

def get_job_info(job):
    """DBレコードから実行関数と引数を取得する"""
    job_type = job['job_type']
    layer_id = job['layer_id']

    if job_type == 'camera':
        job_func = execute_photo_job
    elif job_type == 'sensor':
        job_func = execute_sensor_job
    elif job_type == 'water':
        job_func = execute_pump_job
    else:
        print(f"警告: 未知のジョブタイプ '{job_type}' をスキップしました。")
        return None, None
    
    # 全てのジョブは layer_id を引数に取る
    job_args = {'layer_id': layer_id}
    return job_func, job_args

def get_cron_trigger(job_type, exec_time):
    """
    ジョブタイプとexec_timeに基づいて適切なCronTriggerを生成する。
    
    * sensor/water: 間隔実行 (例: '00:30:00' -> 0,30 * * * *)
    * camera: 特定時刻の固定実行 (例: '09:00:00' -> 0 9 * * *)
    """
    try:
        H, M, S = map(int, exec_time.split(':'))
    except ValueError:
        print(f"エラー: 不正な時刻形式 '{exec_time}'")
        return CronTrigger(minute='*') # 毎分実行でフォールバック
    
    # センサー/水やりジョブの場合、exec_timeの分/秒を間隔と解釈する
    if job_type in ['sensor', 'water']:
        total_minutes = M + H * 60
        
        if total_minutes > 0 and 60 % total_minutes == 0:
            # 60分を割り切れる間隔の場合 (例: 10, 15, 20, 30分)
            # Cronで分(minute)を指定し、毎時実行
            minute_interval = ','.join([str(i) for i in range(0, 60, total_minutes)])
            return CronTrigger(minute=minute_interval, hour='*', second=0)

        elif H > 0 or M > 0:
            # それ以外は、単なる固定時刻として扱う
            return CronTrigger(hour=H, minute=M, second=0)

    # カメラジョブまたはその他の固定時刻ジョブの場合
    # 毎日指定時刻に実行
    return CronTrigger(hour=H, minute=M, second=0)


def check_schedule_changes():
    """
    schedulesテーブルに変更があったかチェックする。
    最後にスケジュールを読み込んだ時刻以降に更新があれば True を返す。
    """
    global last_schedule_check_time
    
    try:
        with open_db() as conn:
            cursor = conn.cursor()
            
            # schedulesテーブルには更新時刻がないため、
            # スケジュールの内容（schedule_id, exec_time, is_enabled）をハッシュ化して比較
            cursor.execute("""
                SELECT schedule_id, layer_id, job_type, exec_time, is_enabled
                FROM schedules
                ORDER BY schedule_id
            """)
            rows = cursor.fetchall()
            
            # 現在のスケジュール情報を文字列化
            current_hash = str([dict(row) for row in rows])
            
            if last_schedule_check_time is None:
                # 初回実行時
                last_schedule_check_time = current_hash
                return False
            
            if current_hash != last_schedule_check_time:
                # 変更を検出
                last_schedule_check_time = current_hash
                return True
            
            return False
            
    except Exception as e:
        print(f"スケジュール変更チェックエラー: {e}")
        return False

def load_and_schedule_jobs():
    """
    データベースから有効なスケジュールを読み込み、APSchedulerに登録する。
    """
    print("--- スケジュール設定を開始します (APScheduler) ---")
    
    # 既存のすべてのジョブを削除し、再登録に備える
    scheduler.remove_all_jobs() 

    schedules = select_schedules()
    
    if not schedules:
        print("DBに有効なスケジュールが見つかりませんでした。")
        return

    for job in schedules:
        schedule_id = job['schedule_id']
        job_type = job['job_type']
        exec_time = job['exec_time']
        layer_id = job['layer_id']

        job_func, job_args = get_job_info(job)
        
        if job_func:
            try:
                # 適切なCronTriggerを生成
                trigger = get_cron_trigger(job_type, exec_time)

                # APSchedulerにジョブを登録
                scheduler.add_job(
                    func=job_func,
                    trigger=trigger,
                    id=f'job_{schedule_id}', # 変更・削除のためにIDを割り当てる
                    kwargs=job_args,
                    name=f'Layer {layer_id} / {job_type} @ {exec_time[:5]}',
                    max_instances=1 # ジョブが重複して実行されないようにする
                )
                


                if job_type in ['sensor', 'water']:
                    # 間隔実行として登録した場合
                    H, M, S = map(int, exec_time.split(':'))
                    total_minutes = M + H * 60
                    if total_minutes > 0 and 60 % total_minutes == 0:
                        # 30分おきなどの「間隔」を明記
                        print(f"✓ スケジュール登録: [Layer {layer_id} / {job_type}] 毎時 {total_minutes}分おきに実行 (Cron: 0,{total_minutes}...分)")
                    else:
                        # 固定時刻として登録した場合
                        print(f"✓ スケジュール登録: [Layer {layer_id} / {job_type}] 毎日 {exec_time[:5]} に実行")
                else:
                    # カメラジョブ（固定時刻）
                    print(f"✓ スケジュール登録: [Layer {layer_id} / {job_type}] 毎日 {exec_time[:5]} に実行")

            except Exception as e:
                print(f"スケジュール登録エラー (ID {schedule_id}): {e}")

    print("--- スケジュール設定が完了しました ---")

def monitor_schedule_changes():
    """
    定期的にDBをチェックし、スケジュールに変更があれば再読み込みする。
    この関数はAPSchedulerのジョブとして60秒ごとに実行される。
    """
    if check_schedule_changes():
        print("\n⚠️  スケジュールの変更を検出しました。再読み込みします...")
        insert_system_log(
            layer_id=0,
            log_level='INFO',
            message='Schedule changes detected',
            details='Reloading schedules from database.'
        )
        
        # スケジュールを再読み込み
        load_and_schedule_jobs()
        
        # 監視ジョブ自体を再登録（load_and_schedule_jobsで全削除されるため）
        scheduler.add_job(
            func=monitor_schedule_changes,
            trigger='interval',
            seconds=60,
            id='schedule_monitor',
            name='Schedule Monitor',
            replace_existing=True
        )
        
        print("✅ スケジュールの再読み込みが完了しました。\n")

# main.pyから呼び出される関数
def run_scheduler():
    """
    APSchedulerを起動し、メインスレッドを維持する。
    """
    # スケジュール設定を最初に実行
    load_and_schedule_jobs()

    # スケジューラを起動
    if not scheduler.running:
        scheduler.start()
        print("APSchedulerが起動しました。")
        # スケジュール開始ログを記録
        insert_system_log(
            layer_id=0,                                     # システム全体を示す
            log_level='INFO', 
            message='Scheduler Started',                    
            details='APScheduler main loop initiated successfully.' 
        )
    
    # スケジュール監視ジョブを追加（60秒ごとにDBをチェック）
    scheduler.add_job(
        func=monitor_schedule_changes,
        trigger='interval',
        seconds=60,
        id='schedule_monitor',
        name='Schedule Monitor',
        replace_existing=True
    )
    print("📡 スケジュール監視を開始しました（60秒ごとにDBをチェック）\n")

    # メインスレッドを維持する。ジョブはバックグラウンドで実行される。
    try:
        # スケジューラ起動中は time.sleep でプロセスを維持する
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        # 終了シグナルを受け取った際、スケジューラをシャットダウン
        print("\nAPSchedulerをシャットダウンします...")
        if scheduler.running:
            scheduler.shutdown(wait=False)
        # main.py の KeyboardInterrupt 処理に任せる
        raise