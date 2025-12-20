from __future__ import annotations

import os
import secrets
from typing import Optional

import jwt
from flask import Blueprint, current_app, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename
from PIL import Image

from extensions import db
from models.user import BookshelfItem, CustomBook, User


custom_books_bp = Blueprint('custom_books', __name__, url_prefix='/api/custom-books')


def _require_user_id():
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    if not token:
        return None, (jsonify({'error': '未授权'}), 401)

    try:
        payload = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
        user_id = payload.get('user_id')
        if not user_id:
            return None, (jsonify({'error': 'Token无效'}), 401)

        user = User.query.get(user_id)
        if not user:
            return None, (jsonify({'error': '用户不存在'}), 404)

        return user_id, None
    except jwt.ExpiredSignatureError:
        return None, (jsonify({'error': 'Token已过期'}), 401)
    except jwt.InvalidTokenError:
        return None, (jsonify({'error': 'Token无效'}), 401)


def _uploads_dir() -> str:
    p = current_app.config.get('UPLOAD_FOLDER')
    if not p:
        # fallback
        p = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'instance', 'uploads')
    return os.path.abspath(p)


def _cover_url(filename: Optional[str]) -> Optional[str]:
    if not filename:
        return None
    return f'/api/custom-books/cover/{filename}'


def _is_allowed_image(filename: str) -> bool:
    ext = (os.path.splitext(filename)[1] or '').lower().lstrip('.')
    return ext in {'jpg', 'jpeg', 'png', 'webp'}


def _detect_image_ext(file_storage) -> Optional[str]:
    """Detect image extension from actual content.

    Returns extension including leading dot (e.g. '.png'), or None if unknown.
    """
    try:
        stream = getattr(file_storage, 'stream', None)
        if stream is None:
            return None

        try:
            pos = stream.tell()
        except Exception:
            pos = None

        try:
            stream.seek(0)
            img = Image.open(stream)
            fmt = (img.format or '').strip().lower()
        finally:
            try:
                stream.seek(0)
                if pos is not None:
                    stream.seek(pos)
            except Exception:
                pass

        mapping = {
            'jpeg': '.jpg',
            'jpg': '.jpg',
            'png': '.png',
            'webp': '.webp',
        }
        return mapping.get(fmt)
    except Exception:
        return None


@custom_books_bp.get('/cover/<path:filename>')
def get_cover(filename: str):
    # 不要求登录：封面仅用于展示
    directory = _uploads_dir()
    return send_from_directory(directory, filename)


@custom_books_bp.post('')
@custom_books_bp.post('/')
def create_custom_book():
    """新增自定义书籍（并自动加入书架）。

    multipart/form-data:
      - title: str (required)
      - author: str (required)
      - intro: str (optional)
      - cover: file (optional)
    """

    user_id, err = _require_user_id()
    if err:
        return err

    title = (request.form.get('title') or '').strip()
    author = (request.form.get('author') or '').strip()
    intro = (request.form.get('intro') or '').strip()

    if not title:
        return jsonify({'success': False, 'message': '书名不能为空'}), 400
    if not author:
        return jsonify({'success': False, 'message': '作者不能为空'}), 400
    if intro and len(intro) > 5000:
        return jsonify({'success': False, 'message': '简介过长（最多 5000 字）'}), 400

    cover_file = request.files.get('cover')
    cover_filename = None

    if cover_file and cover_file.filename:
        original_name = (cover_file.filename or '').strip()
        safe_name = secure_filename(original_name)

        ext = (os.path.splitext(safe_name)[1] or os.path.splitext(original_name)[1] or '').lower()
        if ext and ext.lstrip('.') in {'jpg', 'jpeg', 'png', 'webp'}:
            pass
        else:
            detected = _detect_image_ext(cover_file)
            if detected:
                ext = detected

        if not ext or ext.lstrip('.') not in {'jpg', 'jpeg', 'png', 'webp'}:
            return jsonify({'success': False, 'message': '封面仅支持 jpg/jpeg/png/webp'}), 400

        token = secrets.token_hex(10)
        cover_filename = f'cover_{user_id}_{token}{ext}'
        directory = _uploads_dir()
        os.makedirs(directory, exist_ok=True)
        cover_file.save(os.path.join(directory, cover_filename))

    book = CustomBook(user_id=user_id, title=title, author=author, intro=intro or None, cover_filename=cover_filename)
    db.session.add(book)
    db.session.flush()  # 获取 book.id

    book_id = f'custom-{book.id}'
    cover_url = _cover_url(cover_filename)

    existing = BookshelfItem.query.filter_by(user_id=user_id, book_id=book_id).first()
    if not existing:
        item = BookshelfItem(
            user_id=user_id,
            book_id=book_id,
            book_title=title,
            book_cover=cover_url,
            book_rating=None,
            book_author=author,
        )
        db.session.add(item)

    db.session.commit()

    return jsonify({'success': True, 'data': {'book': book.to_dict(cover_url=cover_url)}}), 201


@custom_books_bp.get('/<int:custom_id>')
@custom_books_bp.get('/<int:custom_id>/')
def get_custom_book(custom_id: int):
    """获取自定义书籍详情（仅允许查看自己的）。"""
    user_id, err = _require_user_id()
    if err:
        return err

    book = CustomBook.query.filter_by(id=custom_id, user_id=user_id).first()
    if not book:
        return jsonify({'success': False, 'message': '书籍不存在'}), 404

    return jsonify({'success': True, 'data': {'book': book.to_dict(cover_url=_cover_url(book.cover_filename))}})
