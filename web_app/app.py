import sys
import os
from pathlib import Path
from flask import Flask, send_from_directory

# 親ディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

# gRPC DNS設定（Gemini API接続のため、importより前に設定）
os.environ['GRPC_DNS_RESOLVER'] = 'native'

# Blueprintをインポート
from .routes.view_routes import view_bp
from .routes.api_routes import api_bp

def create_app():
    """Flaskアプリケーションを生成し、設定を行うファクトリ関数"""
    app = Flask(__name__)

    # --- Blueprintの登録 ---
    app.register_blueprint(view_bp)
    app.register_blueprint(api_bp)

    # --- 静的ファイル配信ルート ---
    # plant_images ディレクトリの画像を配信するためのルート
    @app.route('/plant_images/<path:filename>')
    def serve_plant_images(filename):
        # プロジェクトルートからの相対パスで画像ディレクトリを指定
        image_dir = Path(__file__).parent.parent / 'plant_images'
        return send_from_directory(image_dir, filename)

    print("--- Flask Appのルーティング設定 ---")
    for rule in app.url_map.iter_rules():
        print(f"URL: {rule.rule}, Endpoint: {rule.endpoint}, Methods: {','.join(rule.methods)}")
    print("---------------------------------")
    
    return app

if __name__ == '__main__':
    # このファイルが直接実行された場合（開発用）
    # run_web.py を経由して実行することを推奨
    app = create_app()
    app.run(host='0.0.0.0', port=8080, debug=True)
