from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
import secrets

class User(db.Model):
    """用户模型"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    avatar = db.Column(db.String(255), default='')
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    bookshelf = db.relationship('BookshelfItem', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    reading_logs = db.relationship('ReadingLog', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        """设置密码"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'email': self.email,
            'username': self.username,
            'avatar': self.avatar,
            'is_verified': self.is_verified,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class EmailVerification(db.Model):
    """邮箱验证码模型"""
    __tablename__ = 'email_verifications'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    code = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    
    @staticmethod
    def generate_code():
        """生成6位验证码"""
        return ''.join([str(secrets.randbelow(10)) for _ in range(6)])


class BookshelfItem(db.Model):
    """书架项目模型"""
    __tablename__ = 'bookshelf_items'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    book_id = db.Column(db.String(50), nullable=False)  # 豆瓣图书ID
    book_title = db.Column(db.String(255), nullable=False)
    book_cover = db.Column(db.String(255))
    book_rating = db.Column(db.Float)
    book_author = db.Column(db.String(255))
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'book_id': self.book_id,
            'book_title': self.book_title,
            'book_cover': self.book_cover,
            'book_rating': self.book_rating,
            'book_author': self.book_author,
            'added_at': self.added_at.isoformat() if self.added_at else None
        }


class ReadingLog(db.Model):
    """读书日志/评价模型"""

    __tablename__ = 'reading_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    book_id = db.Column(db.String(50), nullable=False, index=True)
    book_title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'book_id': self.book_id,
            'book_title': self.book_title,
            'content': self.content,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ReadingNote(db.Model):
    """阅读随笔与收藏句子。"""

    __tablename__ = 'reading_notes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    book_id = db.Column(db.String(50), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('reader_assets.id'), nullable=True, index=True)

    kind = db.Column(db.String(16), nullable=False)  # note | quote
    quote_text = db.Column(db.Text)
    content = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        db.Index('idx_reading_notes_user_book', 'user_id', 'book_id'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'book_id': self.book_id,
            'asset_id': self.asset_id,
            'kind': self.kind,
            'quote_text': self.quote_text,
            'content': self.content,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class CustomBook(db.Model):
    """用户自定义书籍（用于补充豆瓣搜不到的书）"""

    __tablename__ = 'custom_books'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255), nullable=False)
    intro = db.Column(db.Text)
    cover_filename = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self, cover_url: str | None = None):
        return {
            'id': self.id,
            'book_id': f'custom-{self.id}',
            'title': self.title,
            'author': self.author,
            'summary': (self.intro or '').strip() or None,
            'cover_url': cover_url,
            'rating': None,
            'tags': [],
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class DailyRecommendation(db.Model):
    """每日推荐（按用户、按天存储，最多 2 本）。"""

    __tablename__ = 'daily_recommendations'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    day = db.Column(db.String(10), nullable=False, index=True)  # YYYY-MM-DD

    source_book_id = db.Column(db.String(50), nullable=False)
    rec_book_id = db.Column(db.String(50), nullable=False)

    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255))
    cover_url = db.Column(db.String(512))
    rating = db.Column(db.String(32))
    summary = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'day', 'rec_book_id', name='uq_daily_rec_user_day_book'),
        db.Index('idx_daily_rec_user_day', 'user_id', 'day'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'day': self.day,
            'source_book_id': self.source_book_id,
            'book_id': self.rec_book_id,
            'title': self.title,
            'author': self.author,
            'cover_url': self.cover_url,
            'rating': self.rating,
            'summary': self.summary,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ReaderAsset(db.Model):
    """用户阅读资源（下载到本地后站内阅读）。

    仅存储来自白名单数据源、且用户有权获取的资源。
    """

    __tablename__ = 'reader_assets'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Link back to the bookshelf book_id (Douban numeric id or custom-<id>)
    book_id = db.Column(db.String(50), nullable=False, index=True)

    source = db.Column(db.String(32), nullable=False)  # e.g. gutendex
    source_id = db.Column(db.String(64))
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255))

    format = db.Column(db.String(16), nullable=False)  # txt | epub | pdf
    download_url = db.Column(db.String(1024), nullable=False)
    file_path = db.Column(db.String(1024), nullable=False)
    file_size = db.Column(db.Integer)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        db.Index('idx_reader_asset_user_book', 'user_id', 'book_id'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'book_id': self.book_id,
            'source': self.source,
            'source_id': self.source_id,
            'title': self.title,
            'author': self.author,
            'format': self.format,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ReaderProgress(db.Model):
    """用户阅读进度（按资源保存）。

    使用独立表，避免对已有表做 schema 变更（SQLite 下 create_all 不会自动加列）。
    """

    __tablename__ = 'reader_progress'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('reader_assets.id'), nullable=False, index=True)

    # txt: value is scrollY (stringified int)
    # epub: value is CFI string
    kind = db.Column(db.String(16), nullable=False)  # txt | epub
    value = db.Column(db.String(2048), nullable=False)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'asset_id', 'kind', name='uq_reader_progress_user_asset_kind'),
        db.Index('idx_reader_progress_user_asset', 'user_id', 'asset_id'),
    )

    def to_dict(self):
        return {
            'asset_id': self.asset_id,
            'kind': self.kind,
            'value': self.value,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
