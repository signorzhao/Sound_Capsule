import uuid
from functools import wraps

from flask import Blueprint, jsonify, request

from auth import get_auth_manager
from common import APIError
from supabase_client import get_supabase_client
import os


admin_bp = Blueprint("admin_bp", __name__)


def _get_current_user():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise APIError("需要认证", 401)

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise APIError("Token 为空", 401)

    auth_manager = get_auth_manager()
    payload = auth_manager.verify_access_token(token)
    if not payload:
        raise APIError("Token 无效或已过期", 401)

    user = None
    if "supabase_user_id" in payload:
        user = auth_manager.get_user_by_supabase_id(payload["supabase_user_id"]) or {
            "supabase_user_id": payload["supabase_user_id"],
            "id": payload["supabase_user_id"],
            "username": payload.get("username"),
            "email": payload.get("email"),
        }
    elif "user_id" in payload:
        user = auth_manager.get_user_by_id(payload["user_id"])

    if not user:
        raise APIError("用户不存在", 401)
    return user


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == "OPTIONS":
            return jsonify({"success": True}), 200
        user = _get_current_user()
        return f(current_user=user, *args, **kwargs)

    return decorated


def _allowed_tables():
    raw = os.getenv("ADMIN_ALLOWED_TABLES", "").strip()
    return {x.strip() for x in raw.split(",") if x.strip()}


def _allowed_methods():
    raw = os.getenv("ADMIN_ALLOWED_METHODS", "GET,POST,PATCH,DELETE").strip()
    return {x.strip().upper() for x in raw.split(",") if x.strip()}


@admin_bp.route("/rest/<path:table_name>", methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"])
@token_required
def admin_rest_proxy(current_user, table_name):
    request_id = str(uuid.uuid4())
    table_name = table_name.strip().split("/")[0]

    allowed_tables = _allowed_tables()
    if table_name not in allowed_tables:
        raise APIError(f"forbidden_table: {table_name}", 403)

    method = request.method.upper()
    if method not in _allowed_methods():
        raise APIError(f"forbidden_method: {method}", 403)

    supabase = get_supabase_client()
    if not supabase:
        raise APIError("Supabase 客户端未初始化", 500)

    max_limit = int(os.getenv("ADMIN_MAX_LIMIT", "500"))

    try:
        if method == "GET":
            select_expr = request.args.get("select", "*")
            query = supabase.client.table(table_name).select(select_expr)

            for key, value in request.args.items():
                if key in {"select", "limit", "offset", "order"}:
                    continue
                query = query.eq(key, value)

            order_expr = request.args.get("order")
            if order_expr:
                descending = order_expr.startswith("-")
                order_col = order_expr[1:] if descending else order_expr
                query = query.order(order_col, desc=descending)

            limit_value = request.args.get("limit")
            if limit_value is not None:
                limit_num = int(limit_value)
                if limit_num > max_limit:
                    return jsonify({
                        "success": False,
                        "error": "limit_exceeded",
                        "request_id": request_id,
                    }), 400
                query = query.limit(limit_num)
            else:
                query = query.limit(min(100, max_limit))

            offset_value = request.args.get("offset")
            if offset_value is not None:
                offset_num = int(offset_value)
                query = query.range(offset_num, offset_num + (int(limit_value or 100) - 1))

            result = query.execute()
            return jsonify({
                "success": True,
                "data": result.data or [],
                "request_id": request_id,
            })

        body = request.get_json(silent=True) or {}

        if method == "POST":
            result = supabase.client.table(table_name).insert(body).execute()
        elif method == "PATCH":
            filters = body.pop("_filters", {}) if isinstance(body, dict) else {}
            query = supabase.client.table(table_name).update(body)
            for key, value in (filters or {}).items():
                query = query.eq(key, value)
            result = query.execute()
        else:  # DELETE
            filters = body.get("_filters", {}) if isinstance(body, dict) else {}
            query = supabase.client.table(table_name).delete()
            for key, value in (filters or {}).items():
                query = query.eq(key, value)
            result = query.execute()

        return jsonify({
            "success": True,
            "data": result.data or [],
            "request_id": request_id,
        })
    except ValueError:
        raise APIError("请求参数错误", 400)
    except APIError:
        raise
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "request_id": request_id,
        }), 500
