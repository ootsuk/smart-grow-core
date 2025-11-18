from flask import Blueprint, render_template

# Blueprintオブジェクトを作成
view_bp = Blueprint('views', __name__)

@view_bp.route('/')
def dashboard():
    """ダッシュボード画面"""
    return render_template('dashboard.html')

@view_bp.route('/sensors')
def sensors():
    """センサーグラフ画面"""
    return render_template('sensors.html')

@view_bp.route('/gallery')
def gallery():
    """画像ギャラリー画面"""
    return render_template('gallery.html')

@view_bp.route('/ai-reports')
def ai_reports():
    """AI相談チャット画面"""
    return render_template('ai_chat.html')

@view_bp.route('/schedules')
def schedules():
    """スケジュール管理画面"""
    return render_template('schedules.html')

@view_bp.route('/settings')
def settings():
    """システム設定画面"""
    return render_template('settings.html')

@view_bp.route('/logs')
def logs():
    """システムログ画面"""
    return render_template('logs.html')

@view_bp.route('/schedules')
def schedules_page():
    """スケジュール管理ページ"""
    return render_template('schedules.html')
