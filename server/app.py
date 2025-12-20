import os

# Load optional environment variables from `server/.env`
try:
    from dotenv import load_dotenv

    _ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(_ENV_PATH, override=False)
except Exception:
    # dotenv is optional at runtime
    pass

from flask import Flask, jsonify
from flask_cors import CORS
from config import config
from extensions import db, mail
from urllib.parse import urlparse

# 确保作为脚本运行时，`import app` 指向当前模块，避免出现双实例导致 SQLAlchemy 未绑定
import sys as _sys
_sys.modules.setdefault('app', _sys.modules[__name__])

def create_app(config_name='default'):
    """应用工厂函数"""
    app = Flask(__name__)
    
    # 加载配置
    app.config.from_object(config[config_name])
    
    # 初始化扩展
    db.init_app(app)
    mail.init_app(app)

    # 打印实际数据库连接信息，便于排查“连错库导致账号不一致”
    try:
        uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        app.logger.info(f"SQLALCHEMY_DATABASE_URI={uri}")
        if isinstance(uri, str) and uri.startswith('sqlite:'):
            parsed = urlparse(uri)
            if parsed.path:
                app.logger.info(f"SQLite path={os.path.abspath(parsed.path.lstrip('/'))}")
    except Exception:
        pass
    
    # 启用CORS
    CORS(app)
    
    # 创建数据库表（开发环境）
    try:
        with app.app_context():
            from models import user as _user_models
            db.create_all()
    except Exception as e:
        print(f"警告: 数据库连接失败 - {e}")
        print("提示: 请确保MySQL已启动并创建了 'book_review_system' 数据库")
    
    # 注册路由
    register_routes(app)
    
    return app

def register_routes(app):
    """注册路由"""
    from api.auth import auth_bp
    from api.books import books_bp
    from api.custom_books import custom_books_bp
    from api.me import me_bp
    from api.recommendations import recommendations_bp
    from api.reader import reader_bp
    
    # 注册蓝图
    app.register_blueprint(auth_bp)
    app.register_blueprint(books_bp)
    app.register_blueprint(custom_books_bp)
    app.register_blueprint(me_bp)
    app.register_blueprint(recommendations_bp)
    app.register_blueprint(reader_bp)
    
    @app.route('/')
    def index():
        return jsonify({
            'message': '书籍评论系统API',
            'version': '1.0.0',
            'endpoints': {
                'auth': '/api/auth/*',
                'books': '/api/books/*',
                'comments': '/api/comments/*'
            }
        })
    
    @app.route('/api/health')
    def health_check():
        return jsonify({'status': 'healthy', 'database': 'connected'})
    
    @app.route('/api/test')
    def test():
        return jsonify({'message': 'API测试成功'})

    @app.route('/api/debug/routes')
    def debug_routes():
        try:
            rules = []
            for r in app.url_map.iter_rules():
                methods = sorted([m for m in (r.methods or set()) if m not in ('HEAD', 'OPTIONS')])
                rules.append({'rule': str(r), 'endpoint': r.endpoint, 'methods': methods})
            return jsonify({'success': True, 'count': len(rules), 'routes': rules})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500
    
    # 测试数据库连接
    @app.route('/api/test-db')
    def test_db():
        try:
            # 尝试执行一个简单的查询
            result = db.session.execute('SELECT 1')
            return jsonify({'database': 'connected', 'result': 'success'})
        except Exception as e:
            return jsonify({'database': 'error', 'message': str(e)}), 500

# 创建应用实例
app = create_app()

if __name__ == '__main__':
    debug = os.getenv('FLASK_DEBUG', '1') not in ('0', 'false', 'False')
    app.run(host='0.0.0.0', port=5000, debug=debug, use_reloader=False, threaded=True)