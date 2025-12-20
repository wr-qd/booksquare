from __future__ import annotations

import os
import re
from datetime import datetime
from urllib.parse import urlparse

import jwt
import requests
from flask import Blueprint, Response, current_app, jsonify, request, send_file
from charset_normalizer import from_bytes

from extensions import db
from models.user import BookshelfItem, ReaderAsset, ReaderProgress, User
from utils.reader_sources.gutendex import GutendexTemporaryError, is_allowed_gutenberg_download, search_gutendex


reader_bp = Blueprint('reader', __name__, url_prefix='/api/reader')


def _safe_filename(name: str) -> str:
    name = (name or '').strip()
    if not name:
        return 'file'
    # keep simple ASCII-ish subset to avoid path tricks
    name = re.sub(r'[^A-Za-z0-9._-]+', '_', name)
    name = name.strip('._')
    return name or 'file'


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


def _storage_dir(user_id: int) -> str:
    base = current_app.instance_path
    d = os.path.join(base, 'reader_assets', str(user_id))
    os.makedirs(d, exist_ok=True)
    return d


def _decode_txt_bytes(raw: bytes) -> str:
    """Best-effort decode bytes to text, preferring UTF-8, handling BOM/GB系."""
    if not raw:
        return ''

    # BOM checks first
    if raw.startswith(b'\xef\xbb\xbf'):
        try:
            return raw.decode('utf-8-sig')
        except Exception:
            pass
    if raw.startswith(b'\xff\xfe\x00\x00'):
        try:
            return raw.decode('utf-32-le')
        except Exception:
            pass
    if raw.startswith(b'\x00\x00\xfe\xff'):
        try:
            return raw.decode('utf-32-be')
        except Exception:
            pass
    if raw.startswith(b'\xff\xfe'):
        try:
            return raw.decode('utf-16-le')
        except Exception:
            pass
    if raw.startswith(b'\xfe\xff'):
        try:
            return raw.decode('utf-16-be')
        except Exception:
            pass

    # Try utf-8 straight
    try:
        return raw.decode('utf-8')
    except Exception:
        pass

    # charset-normalizer guess
    try:
        best = from_bytes(raw).best()
        if best and best.encoding:
            try:
                return raw.decode(best.encoding)
            except Exception:
                pass
    except Exception:
        pass

    # GB18030 fallback (covers GBK/GB2312)
    try:
        return raw.decode('gb18030')
    except Exception:
        pass

    # Last resort
    return raw.decode('utf-8', errors='ignore')


@reader_bp.get('/sources')
def sources():
    """Search allowed reading sources for a bookshelf book.

    Query:
      - book_id: bookshelf book id
    """
    user_id, err = _require_user_id()
    if err:
        return err

    book_id = (request.args.get('book_id') or '').strip()
    if not book_id:
        return jsonify({'success': False, 'message': 'book_id 不能为空'}), 400

    shelf = BookshelfItem.query.filter_by(user_id=user_id, book_id=book_id).first()
    if not shelf:
        return jsonify({'success': False, 'message': '请先把这本书加入书架再获取全文资源'}), 400

    query = f"{shelf.book_title} {shelf.book_author or ''}".strip()

    try:
        items = search_gutendex(query, limit=8)
        return jsonify(
            {
                'success': True,
                'data': {
                    'book': {
                        'book_id': shelf.book_id,
                        'title': shelf.book_title,
                        'author': shelf.book_author,
                    },
                    'sources': [
                        {
                            'source': 'gutendex',
                            'name': 'Project Gutenberg',
                            'items': [it.to_dict() for it in items],
                        }
                    ],
                },
            }
        )
    except GutendexTemporaryError:
        return jsonify({'success': False, 'message': 'Gutenberg 书源暂时不可用（网络超时），请稍后重试'}), 502
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@reader_bp.post('/download')
def download():
    """Download a selected resource into server storage.

    Body JSON:
      - book_id
      - source (currently: gutendex)
      - source_id
      - title
      - author
      - format: txt | epub
      - url: direct download url (must be allowlisted)
    """
    user_id, err = _require_user_id()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    book_id = (data.get('book_id') or '').strip()
    source = (data.get('source') or '').strip()
    source_id = (data.get('source_id') or '').strip() or None
    title = (data.get('title') or '').strip()
    author = (data.get('author') or '').strip() or None
    fmt = (data.get('format') or '').strip().lower()
    url = (data.get('url') or '').strip()

    if not book_id or not source or not title or not fmt or not url:
        return jsonify({'success': False, 'message': '参数不完整'}), 400

    shelf = BookshelfItem.query.filter_by(user_id=user_id, book_id=book_id).first()
    if not shelf:
        return jsonify({'success': False, 'message': '请先把这本书加入书架再下载'}), 400

    if source != 'gutendex':
        return jsonify({'success': False, 'message': '暂不支持该书源'}), 400

    if fmt not in ('txt', 'epub'):
        return jsonify({'success': False, 'message': '暂仅支持 txt/epub'}), 400

    if not is_allowed_gutenberg_download(url):
        return jsonify({'success': False, 'message': '下载链接不在允许的域名范围内'}), 400

    # Download
    try:
        r = requests.get(url, stream=True, timeout=25)
        r.raise_for_status()

        ext = 'txt' if fmt == 'txt' else 'epub'
        now = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        safe_name = f"{book_id}_{source}_{source_id or 'na'}_{now}.{ext}"
        out_dir = _storage_dir(user_id)
        out_path = os.path.join(out_dir, safe_name)

        size = 0
        max_bytes = 60 * 1024 * 1024  # 60MB safety cap
        with open(out_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024 * 64):
                if not chunk:
                    continue
                f.write(chunk)
                size += len(chunk)
                if size > max_bytes:
                    try:
                        f.close()
                    except Exception:
                        pass
                    try:
                        os.remove(out_path)
                    except Exception:
                        pass
                    return jsonify({'success': False, 'message': '文件过大，已停止下载'}), 400

        asset = ReaderAsset(
            user_id=user_id,
            book_id=book_id,
            source=source,
            source_id=source_id,
            title=title,
            author=author,
            format=fmt,
            download_url=url,
            file_path=out_path,
            file_size=size,
        )
        db.session.add(asset)
        db.session.commit()

        return jsonify(
            {
                'success': True,
                'data': {
                    'asset': asset.to_dict(),
                },
            }
        )

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@reader_bp.post('/upload')
def upload():
    """Upload a local TXT/EPUB file for in-app reading.

    Multipart form:
      - book_id
      - file
      - title (optional)
      - author (optional)
      - format (optional: txt|epub). If omitted, infer from filename.
    """

    user_id, err = _require_user_id()
    if err:
        return err

    book_id = (request.form.get('book_id') or '').strip()
    title = (request.form.get('title') or '').strip()
    author = (request.form.get('author') or '').strip() or None
    fmt = (request.form.get('format') or '').strip().lower()
    f = request.files.get('file')

    if not book_id or not f:
        return jsonify({'success': False, 'message': 'book_id 与 file 不能为空'}), 400

    shelf = BookshelfItem.query.filter_by(user_id=user_id, book_id=book_id).first()
    if not shelf:
        return jsonify({'success': False, 'message': '请先把这本书加入书架再导入'}), 400

    original_name = f.filename or ''
    ext = os.path.splitext(original_name)[1].lower().lstrip('.')
    if not fmt:
        fmt = ext

    if fmt not in ('txt', 'epub'):
        return jsonify({'success': False, 'message': '暂仅支持导入 txt/epub'}), 400

    # size limit (60MB)
    try:
        f.stream.seek(0, os.SEEK_END)
        size = int(f.stream.tell())
        f.stream.seek(0)
    except Exception:
        size = None

    max_bytes = 60 * 1024 * 1024
    if size is not None and size > max_bytes:
        return jsonify({'success': False, 'message': '文件过大（上限 60MB）'}), 400

    now = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    out_dir = _storage_dir(user_id)
    base = _safe_filename(os.path.splitext(original_name)[0])
    out_path = os.path.join(out_dir, f"{book_id}_upload_{base}_{now}.{fmt}")

    try:
        # Read all bytes for normalization; still honor size cap.
        raw = f.read()
        actual_size = len(raw)
        if actual_size > max_bytes:
            return jsonify({'success': False, 'message': '文件过大（上限 60MB）'}), 400

        if fmt == 'txt':
            text = _decode_txt_bytes(raw)
            with open(out_path, 'wb') as fw:
                fw.write(text.encode('utf-8'))
        else:
            # epub or other binary-safe formats stay untouched
            with open(out_path, 'wb') as fw:
                fw.write(raw)

        asset = ReaderAsset(
            user_id=user_id,
            book_id=book_id,
            source='upload',
            source_id=None,
            title=title or (os.path.splitext(original_name)[0].strip() or shelf.book_title),
            author=author or shelf.book_author,
            format=fmt,
            download_url='local-upload',
            file_path=out_path,
            file_size=actual_size,
        )
        db.session.add(asset)
        db.session.commit()

        return jsonify({'success': True, 'data': {'asset': asset.to_dict()}})
    except Exception as e:
        try:
            if os.path.exists(out_path):
                os.remove(out_path)
        except Exception:
            pass
        return jsonify({'success': False, 'message': str(e)}), 500


@reader_bp.get('/assets')
def list_assets():
    user_id, err = _require_user_id()
    if err:
        return err

    book_id = (request.args.get('book_id') or '').strip()
    q = ReaderAsset.query.filter_by(user_id=user_id)
    if book_id:
        q = q.filter_by(book_id=book_id)

    items = q.order_by(ReaderAsset.created_at.desc()).limit(50).all()
    return jsonify({'success': True, 'data': {'items': [it.to_dict() for it in items]}})


@reader_bp.get('/assets/<int:asset_id>/meta')
def asset_meta(asset_id: int):
    user_id, err = _require_user_id()
    if err:
        return err

    it = ReaderAsset.query.filter_by(id=asset_id, user_id=user_id).first()
    if not it:
        return jsonify({'success': False, 'message': '资源不存在'}), 404

    return jsonify({'success': True, 'data': {'asset': it.to_dict()}})


@reader_bp.get('/assets/<int:asset_id>/file')
def asset_file(asset_id: int):
    user_id, err = _require_user_id()
    if err:
        return err

    it = ReaderAsset.query.filter_by(id=asset_id, user_id=user_id).first()
    if not it:
        return jsonify({'success': False, 'message': '资源不存在'}), 404

    path = it.file_path
    if not path or not os.path.exists(path):
        return jsonify({'success': False, 'message': '文件不存在'}), 404

    # Minimal safe content-type mapping
    mimetype = 'text/plain; charset=utf-8' if it.format == 'txt' else 'application/epub+zip'
    return send_file(path, mimetype=mimetype, as_attachment=False, download_name=os.path.basename(path))


@reader_bp.get('/assets/<int:asset_id>/progress')
def get_progress(asset_id: int):
    user_id, err = _require_user_id()
    if err:
        return err

    asset = ReaderAsset.query.filter_by(id=asset_id, user_id=user_id).first()
    if not asset:
        return jsonify({'success': False, 'message': '资源不存在'}), 404

    rows = ReaderProgress.query.filter_by(user_id=user_id, asset_id=asset_id).all()
    out = {}
    for r in rows:
        if r.kind == 'txt':
            try:
                out['txt'] = {'scrollY': int(r.value)}
            except Exception:
                out['txt'] = {'scrollY': 0}
        elif r.kind == 'epub':
            out['epub'] = {'cfi': r.value}

    return jsonify({'success': True, 'data': {'progress': out}})


@reader_bp.post('/assets/<int:asset_id>/progress')
def set_progress(asset_id: int):
    user_id, err = _require_user_id()
    if err:
        return err

    asset = ReaderAsset.query.filter_by(id=asset_id, user_id=user_id).first()
    if not asset:
        return jsonify({'success': False, 'message': '资源不存在'}), 404

    data = request.get_json(silent=True) or {}
    kind = (data.get('kind') or '').strip().lower()

    if kind not in ('txt', 'epub'):
        return jsonify({'success': False, 'message': 'kind 仅支持 txt/epub'}), 400

    if kind == 'txt':
        scroll_y = data.get('scrollY')
        try:
            scroll_y = int(scroll_y)
            if scroll_y < 0:
                scroll_y = 0
        except Exception:
            return jsonify({'success': False, 'message': 'scrollY 必须是整数'}), 400
        value = str(scroll_y)
    else:
        cfi = (data.get('cfi') or '').strip()
        if not cfi:
            return jsonify({'success': False, 'message': 'cfi 不能为空'}), 400
        value = cfi

    row = ReaderProgress.query.filter_by(user_id=user_id, asset_id=asset_id, kind=kind).first()
    if row:
        row.value = value
    else:
        row = ReaderProgress(user_id=user_id, asset_id=asset_id, kind=kind, value=value)
        db.session.add(row)

    db.session.commit()
    return jsonify({'success': True, 'data': {'progress': row.to_dict()}})
