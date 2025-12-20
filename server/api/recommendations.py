from __future__ import annotations

from datetime import datetime
from typing import List

from flask import Blueprint, jsonify, request, current_app
import jwt

from extensions import db
from models.user import BookshelfItem, DailyRecommendation, User
from utils.douban_recommend import pick_recommendation_from_shelf


recommendations_bp = Blueprint('recommendations', __name__, url_prefix='/api/recommendations')


_DAILY_LIMIT = 2
_TOO_MANY_MSG = '书要细品，才能尝到字里行间的韵味。今天的两本推荐就先到这里吧。'


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

        return int(user_id), None
    except jwt.ExpiredSignatureError:
        return None, (jsonify({'error': 'Token已过期'}), 401)
    except jwt.InvalidTokenError:
        return None, (jsonify({'error': 'Token无效'}), 401)


def _today_key() -> str:
    return datetime.now().date().isoformat()


def _list_today(user_id: int) -> List[DailyRecommendation]:
    day = _today_key()
    return (
        DailyRecommendation.query.filter_by(user_id=user_id, day=day)
        .order_by(DailyRecommendation.created_at.asc())
        .all()
    )


def _ensure_one(user_id: int):
    items = _list_today(user_id)
    if items:
        return items
    return _generate_one(user_id)


def _current_item(items: List[DailyRecommendation]) -> List[DailyRecommendation]:
    """Return a single-item list representing the current recommendation.

    We still track up to `_DAILY_LIMIT` items per day in DB, but the UI only
    displays the latest one (refresh = replace).
    """
    if not items:
        return []
    return [items[-1]]


def _generate_one(user_id: int):
    day = _today_key()
    existing = _list_today(user_id)
    if len(existing) >= _DAILY_LIMIT:
        return existing

    shelf = BookshelfItem.query.filter_by(user_id=user_id).all()
    shelf_ids = [it.book_id for it in shelf if it and it.book_id]

    # Filter out custom books here; picker expects numeric ids.
    shelf_ids = [bid for bid in shelf_ids if str(bid).isdigit()]
    if not shelf_ids:
        raise RuntimeError('你的书架里还没有豆瓣书籍，先去添加几本吧')

    already_ids = [it.rec_book_id for it in existing]

    source_id, card = pick_recommendation_from_shelf(
        shelf_ids,
        already_recommended=already_ids,
        max_attempts=6,
    )

    rec = DailyRecommendation(
        user_id=user_id,
        day=day,
        source_book_id=str(source_id),
        rec_book_id=str(card.book_id),
        title=card.title,
        author=card.author or None,
        cover_url=card.cover_url or None,
        rating=card.rating or None,
        summary=card.summary or None,
    )
    db.session.add(rec)
    db.session.commit()

    return _list_today(user_id)


@recommendations_bp.get('/today')
def today():
    user_id, err = _require_user_id()
    if err:
        return err

    try:
        items = _ensure_one(user_id)
        current = _current_item(items)
        return jsonify(
            {
                'success': True,
                'data': {
                    'items': [it.to_dict() for it in current],
                    'day': _today_key(),
                    'limit': _DAILY_LIMIT,
                    'count': len(items),
                    'can_refresh': len(items) < _DAILY_LIMIT,
                },
            }
        )
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@recommendations_bp.post('/refresh')
def refresh():
    user_id, err = _require_user_id()
    if err:
        return err

    items = _list_today(user_id)
    if len(items) >= _DAILY_LIMIT:
        current = _current_item(items)
        return jsonify(
            {
                'success': False,
                'message': _TOO_MANY_MSG,
                'data': {
                    'items': [it.to_dict() for it in current],
                    'day': _today_key(),
                    'limit': _DAILY_LIMIT,
                    'count': len(items),
                    'can_refresh': False,
                },
            }
        )

    try:
        items2 = _generate_one(user_id)
        current2 = _current_item(items2)
        return jsonify(
            {
                'success': True,
                'data': {
                    'items': [it.to_dict() for it in current2],
                    'day': _today_key(),
                    'limit': _DAILY_LIMIT,
                    'count': len(items2),
                    'can_refresh': len(items2) < _DAILY_LIMIT,
                },
            }
        )
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
