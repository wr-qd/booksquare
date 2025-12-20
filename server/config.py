import os
from datetime import timedelta

class Config:
    """基础配置类"""
    # Flask配置
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # 数据库配置
    # 默认固定到 server/instance/book_review.db，避免因启动目录不同而“连错库”导致账号看起来丢失/密码不一致
    _BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    _DEFAULT_SQLITE_PATH = os.path.join(_BASE_DIR, 'instance', 'book_review.db')
    _DEFAULT_SQLITE_URI = 'sqlite:///' + _DEFAULT_SQLITE_PATH.replace('\\', '/')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', _DEFAULT_SQLITE_URI)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT配置
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-me')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # 邮件配置
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_USERNAME', '')
    
    # 爬虫配置
    CRAWLER_DELAY = 1.0  # 爬虫请求延迟（秒）
    
    # 文件上传
    UPLOAD_FOLDER = os.path.join(_BASE_DIR, 'instance', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    SQLALCHEMY_ECHO = True

class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False

# 配置映射
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}