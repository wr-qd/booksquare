from flask import Blueprint, jsonify, request, current_app
import jwt

from extensions import db
from models.user import BookshelfItem, ReadingLog, ReadingNote, User


me_bp = Blueprint('me', __name__, url_prefix='/api/me')
# Allow trailing slashes on all routes to reduce 404 surprises.
me_bp.strict_slashes = False


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


@me_bp.get('/bookshelf')
def list_bookshelf():
    user_id, err = _require_user_id()
    if err:
        return err

    items = (
        BookshelfItem.query.filter_by(user_id=user_id)
        .order_by(BookshelfItem.added_at.desc())
        .all()
    )

    return jsonify({'success': True, 'data': {'items': [it.to_dict() for it in items]}})


@me_bp.get('/bookshelf/<book_id>')
def get_bookshelf_status(book_id: str):
    user_id, err = _require_user_id()
    if err:
        return err

    exists = (
        BookshelfItem.query.filter_by(user_id=user_id, book_id=str(book_id)).first() is not None
    )

    return jsonify({'success': True, 'data': {'liked': bool(exists)}})


@me_bp.post('/bookshelf')
def add_to_bookshelf():
    user_id, err = _require_user_id()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    book_id = (data.get('book_id') or '').strip()
    book_title = (data.get('book_title') or '').strip()

    if not book_id or not book_title:
        return jsonify({'success': False, 'message': 'book_id 和 book_title 不能为空'}), 400

    existing = BookshelfItem.query.filter_by(user_id=user_id, book_id=book_id).first()
    if existing:
        return jsonify({'success': True, 'data': {'item': existing.to_dict(), 'liked': True}})

    item = BookshelfItem(
        user_id=user_id,
        book_id=book_id,
        book_title=book_title,
        book_cover=(data.get('book_cover') or '').strip() or None,
        book_rating=(data.get('book_rating') if data.get('book_rating') is not None else None),
        book_author=(data.get('book_author') or '').strip() or None,
    )

    db.session.add(item)
    db.session.commit()

    return jsonify({'success': True, 'data': {'item': item.to_dict(), 'liked': True}}), 201


@me_bp.delete('/bookshelf/<book_id>')
def remove_from_bookshelf(book_id: str):
    user_id, err = _require_user_id()
    if err:
        return err

    item = BookshelfItem.query.filter_by(user_id=user_id, book_id=str(book_id)).first()
    if not item:
        return jsonify({'success': True, 'data': {'liked': False}})

    db.session.delete(item)
    db.session.commit()

    return jsonify({'success': True, 'data': {'liked': False}})


@me_bp.get('/reading-logs')
def list_reading_logs():
    """用户读书时间线（最新在前）"""
    user_id, err = _require_user_id()
    if err:
        return err

    limit = request.args.get('limit')
    try:
        limit_i = int(limit) if limit is not None else 50
    except Exception:
        limit_i = 50
    limit_i = max(1, min(limit_i, 200))

    items = (
        ReadingLog.query.filter_by(user_id=user_id)
        .order_by(ReadingLog.created_at.desc())
        .limit(limit_i)
        .all()
    )

    return jsonify({'success': True, 'data': {'items': [it.to_dict() for it in items]}})


@me_bp.get('/reading-logs/<book_id>')
def list_book_reading_logs(book_id: str):
    """某本书的读书日志列表（当前用户）"""
    user_id, err = _require_user_id()
    if err:
        return err

    items = (
        ReadingLog.query.filter_by(user_id=user_id, book_id=str(book_id))
        .order_by(ReadingLog.created_at.desc())
        .all()
    )

    return jsonify({'success': True, 'data': {'items': [it.to_dict() for it in items]}})


@me_bp.post('/reading-logs')
def create_reading_log():
    """新增一条读书评价"""
    user_id, err = _require_user_id()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    book_id = (data.get('book_id') or '').strip()
    book_title = (data.get('book_title') or '').strip()
    content = (data.get('content') or '').strip()

    if not book_id or not book_title:
        return jsonify({'success': False, 'message': 'book_id 和 book_title 不能为空'}), 400
    if not content:
        return jsonify({'success': False, 'message': '内容不能为空'}), 400
    if len(content) > 2000:
        return jsonify({'success': False, 'message': '内容过长（最多 2000 字）'}), 400

    item = ReadingLog(user_id=user_id, book_id=book_id, book_title=book_title, content=content)
    db.session.add(item)
    db.session.commit()

    return jsonify({'success': True, 'data': {'item': item.to_dict()}}), 201


@me_bp.delete('/reading-logs/<int:log_id>')
def delete_reading_log(log_id: int):
    """删除一条读书日志（仅允许删除自己的）"""
    user_id, err = _require_user_id()
    if err:
        return err

    item = ReadingLog.query.filter_by(id=log_id, user_id=user_id).first()
    if not item:
        return jsonify({'success': True, 'data': {'deleted': False}})

    db.session.delete(item)
    db.session.commit()

    return jsonify({'success': True, 'data': {'deleted': True}})


@me_bp.get('/notes/<book_id>')
def list_notes(book_id: str):
    user_id, err = _require_user_id()
    if err:
        return err

    items = (
        ReadingNote.query.filter_by(user_id=user_id, book_id=str(book_id))
        .order_by(ReadingNote.created_at.desc())
        .all()
    )

    return jsonify({'success': True, 'data': {'items': [it.to_dict() for it in items]}})


@me_bp.get('/notes')
def list_notes_by_query():
    # Allows frontend to pass ?book_id=xxx instead of path parameter
    user_id, err = _require_user_id()
    if err:
        return err

    book_id = (request.args.get('book_id') or '').strip()
    limit = request.args.get('limit')
    try:
        limit_i = int(limit) if limit is not None else 200
    except Exception:
        limit_i = 200
    limit_i = max(1, min(limit_i, 500))

    query = ReadingNote.query.filter_by(user_id=user_id)
    if book_id:
        query = query.filter_by(book_id=book_id)

    items = query.order_by(ReadingNote.created_at.desc()).limit(limit_i).all()

    return jsonify({'success': True, 'data': {'items': [it.to_dict() for it in items]}})


@me_bp.post('/notes')
def create_note():
    user_id, err = _require_user_id()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    book_id = (data.get('book_id') or '').strip()
    book_title = (data.get('book_title') or '').strip()
    kind = (data.get('kind') or '').strip().lower()
    quote_text = (data.get('quote_text') or '').strip()
    content = (data.get('content') or '').strip()
    asset_id = data.get('asset_id')
    try:
        asset_id_int = int(asset_id) if asset_id is not None else None
    except Exception:
        asset_id_int = None

    if not book_id or not book_title:
        return jsonify({'success': False, 'message': 'book_id 和 book_title 不能为空'}), 400
    if kind not in ('note', 'quote'):
        return jsonify({'success': False, 'message': 'kind 只能是 note 或 quote'}), 400

    if kind == 'note':
        if not content:
            return jsonify({'success': False, 'message': '随笔内容不能为空'}), 400
        if len(content) > 2000:
            return jsonify({'success': False, 'message': '随笔过长（最多 2000 字）'}), 400
        if quote_text and len(quote_text) > 2000:
            return jsonify({'success': False, 'message': '摘录过长（最多 2000 字）'}), 400
    else:
        if not quote_text:
            return jsonify({'success': False, 'message': '收藏句子不能为空'}), 400
        if len(quote_text) > 2000:
            return jsonify({'success': False, 'message': '收藏句子过长（最多 2000 字）'}), 400
        # quote 类型 content 可空
        if content and len(content) > 2000:
            return jsonify({'success': False, 'message': '备注过长（最多 2000 字）'}), 400

    item = ReadingNote(
        user_id=user_id,
        book_id=book_id,
        asset_id=asset_id_int,
        kind=kind,
        quote_text=quote_text or None,
        content=content or None,
    )
    db.session.add(item)
    db.session.commit()

    return jsonify({'success': True, 'data': {'item': item.to_dict()}}), 201


@me_bp.delete('/notes/<int:note_id>')
def delete_note(note_id: int):
    user_id, err = _require_user_id()
    if err:
        return err

    item = ReadingNote.query.filter_by(id=note_id, user_id=user_id).first()
    if not item:
        return jsonify({'success': True, 'data': {'deleted': False}})

    db.session.delete(item)
    db.session.commit()

    return jsonify({'success': True, 'data': {'deleted': True}})
