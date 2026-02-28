import base64
import json
import os
import uuid
from functools import wraps

from flask import Blueprint, jsonify, request

from auth import get_auth_manager
from common import APIError
from supabase_client import get_supabase_client


cloud_bp = Blueprint("cloud_bp", __name__)


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


def _decode_base64(content: str) -> bytes:
    if not content:
        return b""
    if "," in content and "base64" in content[:32]:
        content = content.split(",", 1)[1]
    return base64.b64decode(content)


def _upload_bytes_to_storage(supabase, owner_id: str, folder: str, relative_path: str, file_bytes: bytes):
    storage_path = f"{owner_id}/{folder}/{relative_path}"
    result = supabase.client.storage.from_("capsule-files").upload(
        path=storage_path,
        file=file_bytes,
        file_options={"upsert": "true"},
    )
    return {
        "path": storage_path,
        "result": result,
    }


@cloud_bp.route("/signed-upload-url", methods=["POST", "OPTIONS"])
@token_required
def signed_upload_url(current_user):
    data = request.get_json(silent=True) or {}
    folder = data.get("capsule_folder_name") or data.get("folder")
    files = data.get("files") or []
    if not folder:
        raise APIError("缺少 capsule_folder_name", 400)
    if not isinstance(files, list) or not files:
        raise APIError("files 必须是非空数组", 400)

    supabase = get_supabase_client()
    if not supabase:
        raise APIError("Supabase 客户端未初始化", 500)

    owner_id = current_user.get("supabase_user_id") or str(current_user.get("id", ""))
    signed_items = []
    for item in files:
        filename = (item or {}).get("filename")
        file_type = (item or {}).get("type", "file")
        if not filename:
            continue

        if file_type == "audio":
            relative_path = f"Audio/{filename}"
        else:
            relative_path = filename

        full_path = f"{owner_id}/{folder}/{relative_path}"
        signed = supabase.create_signed_upload_url(full_path)
        signed_items.append({
            "type": file_type,
            "filename": filename,
            "path": full_path,
            "signed": signed,
        })

    return jsonify({
        "success": True,
        "data": {
            "bucket": "capsule-files",
            "items": signed_items,
        },
        "error": None,
    })


@cloud_bp.route("/upload-capsule", methods=["POST", "OPTIONS"])
@token_required
def upload_capsule(current_user):
    data = request.get_json(silent=True) or {}
    capsule = data.get("capsule") or {}
    files = data.get("files") or {}

    if not isinstance(capsule, dict):
        raise APIError("capsule 格式错误", 400)

    owner_id = current_user.get("supabase_user_id") or str(current_user.get("id", ""))
    folder = data.get("capsule_folder_name") or capsule.get("file_path") or capsule.get("name")
    if not folder:
        raise APIError("缺少 capsule_folder_name/file_path/name", 400)

    supabase = get_supabase_client()
    if not supabase:
        raise APIError("Supabase 客户端未初始化", 500)

    metadata = capsule.get("metadata") or {}
    capsule_data = {
        "id": capsule.get("id"),
        "name": capsule.get("name") or folder,
        "file_path": capsule.get("file_path") or folder,
        "capsule_type": capsule.get("capsule_type"),
        "keywords": capsule.get("keywords"),
        "description": capsule.get("description"),
        "preview_audio": (metadata or {}).get("preview_audio") or ((files.get("preview") or {}).get("filename")),
        "metadata": metadata,
    }

    cloud_capsule = supabase.upload_capsule(owner_id, capsule_data)
    if not cloud_capsule or not cloud_capsule.get("id"):
        raise APIError("上传 cloud_capsule 失败", 500)
    cloud_id = cloud_capsule["id"]

    tags = data.get("tags")
    if tags is None:
        tags = capsule.get("tags") or []

    coordinates = data.get("coordinates")
    if coordinates is None:
        coordinates = capsule.get("coordinates") or []

    sync_uploaded = []
    sync_errors = []

    try:
        if tags:
            ok = supabase.upload_tags(owner_id, cloud_id, tags)
            if ok:
                sync_uploaded.append({"type": "tags", "count": len(tags)})
            else:
                sync_errors.append("tags_upload_failed")
        if coordinates:
            ok = supabase.upload_coordinates(owner_id, cloud_id, coordinates)
            if ok:
                sync_uploaded.append({"type": "coordinates", "count": len(coordinates)})
            else:
                sync_errors.append("coordinates_upload_failed")
    except Exception as e:
        sync_errors.append(str(e))

    storage_uploaded = []
    storage_errors = []

    try:
        preview = files.get("preview")
        if preview and preview.get("content_base64"):
            payload = _decode_base64(preview.get("content_base64"))
            uploaded = _upload_bytes_to_storage(
                supabase, owner_id, folder, preview.get("filename") or "preview.ogg", payload
            )
            storage_uploaded.append({"type": "preview", "path": uploaded["path"]})
    except Exception as e:
        storage_errors.append({"type": "preview", "error": str(e)})

    try:
        rpp = files.get("rpp")
        if rpp and rpp.get("content_base64"):
            payload = _decode_base64(rpp.get("content_base64"))
            uploaded = _upload_bytes_to_storage(
                supabase, owner_id, folder, rpp.get("filename") or "project.rpp", payload
            )
            storage_uploaded.append({"type": "rpp", "path": uploaded["path"]})
    except Exception as e:
        storage_errors.append({"type": "rpp", "error": str(e)})

    try:
        audio_files = files.get("audio") or []
        if isinstance(audio_files, list) and audio_files:
            uploaded_count = 0
            total_size = 0
            for item in audio_files:
                filename = (item or {}).get("filename")
                content = (item or {}).get("content_base64")
                if not filename or not content:
                    continue
                payload = _decode_base64(content)
                _upload_bytes_to_storage(supabase, owner_id, folder, f"Audio/{filename}", payload)
                uploaded_count += 1
                total_size += len(payload)

            storage_uploaded.append({
                "type": "audio_folder",
                "files_uploaded": uploaded_count,
                "total_size": total_size,
            })
    except Exception as e:
        storage_errors.append({"type": "audio", "error": str(e)})

    return jsonify({
        "success": True,
        "cloud_id": cloud_id,
        "data": {
            "cloud_capsule": cloud_capsule,
            "sync": {
                "uploaded": sync_uploaded,
                "errors": sync_errors,
                "tags_uploaded": len(tags or []),
                "coordinates_uploaded": len(coordinates or []),
            },
            "storage": {
                "uploaded": storage_uploaded,
                "errors": storage_errors,
            },
        },
        "error": None,
    })


@cloud_bp.route("/lightweight-assets", methods=["POST", "OPTIONS"])
@token_required
def lightweight_assets(current_user):
    """
    由云端侧打包并返回轻量文件内容（metadata/preview/rpp）。
    供本地 sidecar 在无 service_role 模式下落盘使用。
    """
    data = request.get_json(silent=True) or {}
    include_previews = bool(data.get("include_previews", True))
    capsules = data.get("capsules") or []
    if not isinstance(capsules, list):
        raise APIError("capsules 必须是数组", 400)

    supabase = get_supabase_client()
    if not supabase:
        raise APIError("Supabase 客户端未初始化", 500)

    items = []
    errors = []

    for row in capsules:
        cloud_id = (row or {}).get("cloud_id")
        if not cloud_id:
            continue
        try:
            resp = (
                supabase.client
                .table("cloud_capsules")
                .select("id,user_id,name,metadata")
                .eq("id", cloud_id)
                .is_("deleted_at", None)
                .single()
                .execute()
            )
            cap = resp.data or {}
            owner_id = cap.get("user_id")
            metadata = cap.get("metadata") or {}
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except Exception:
                    metadata = {}
            folder = metadata.get("file_path") or cap.get("name")
            if not owner_id or not folder:
                errors.append(f"{cloud_id}: missing owner/folder")
                continue

            plan = [("metadata", "metadata.json")]
            preview_name = metadata.get("preview_audio")
            if include_previews and preview_name:
                plan.append(("preview", preview_name))
            rpp_name = metadata.get("rpp_file") or f"{folder}.rpp"
            plan.append(("rpp", rpp_name))

            files = []
            for file_type, filename in plan:
                storage_path = f"{owner_id}/{folder}/{filename}"
                try:
                    blob = supabase.client.storage.from_("capsule-files").download(storage_path)
                    if not blob:
                        continue
                    files.append({
                        "type": file_type,
                        "filename": filename,
                        "content_base64": base64.b64encode(blob).decode("ascii"),
                    })
                except Exception as e:
                    errors.append(f"{cloud_id}/{filename}: {e}")

            items.append({
                "cloud_id": cloud_id,
                "folder": folder,
                "files": files,
            })
        except Exception as e:
            errors.append(f"{cloud_id}: {e}")

    return jsonify({
        "success": True,
        "data": {
            "items": items,
            "errors": errors,
        },
        "error": None,
    })


@cloud_bp.route("/audio-signed-urls", methods=["POST", "OPTIONS"])
@token_required
def audio_signed_urls(current_user):
    """
    为指定云胶囊返回 Audio/*.wav 的签名下载链接。
    供本地 sidecar 在无 service_role 模式下下载 WAV 资源。
    """
    data = request.get_json(silent=True) or {}
    cloud_id = (data.get("cloud_id") or "").strip()
    expires_in = int(data.get("signed_url_expires_in", 900) or 900)
    expires_in = max(60, min(3600, expires_in))

    if not cloud_id:
        raise APIError("缺少 cloud_id", 400)

    supabase = get_supabase_client()
    if not supabase:
        raise APIError("Supabase 客户端未初始化", 500)

    resp = (
        supabase.client
        .table("cloud_capsules")
        .select("id,user_id,name,metadata")
        .eq("id", cloud_id)
        .is_("deleted_at", None)
        .single()
        .execute()
    )
    cap = resp.data or {}
    owner_id = cap.get("user_id")
    metadata = cap.get("metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}
    folder = metadata.get("file_path") or cap.get("name")
    if not owner_id or not folder:
        raise APIError("缺少 owner_id/folder", 400)

    files = []
    errors = []
    seen = set()
    for bucket_name in ("capsule-files", "capsules"):
        for audio_dir in ("Audio", "audio"):
            prefix = f"{owner_id}/{folder}/{audio_dir}"
            try:
                rows = supabase.client.storage.from_(bucket_name).list(prefix) or []
            except Exception as e:
                errors.append(f"list {bucket_name}/{prefix} failed: {e}")
                continue

            for row in rows:
                name = (row or {}).get("name")
                if not isinstance(name, str):
                    continue
                if not name.lower().endswith(".wav"):
                    continue
                storage_path = f"{prefix}/{name}"
                dedup_key = f"{bucket_name}:{storage_path}"
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                signed = supabase.create_signed_download_url(
                    storage_path,
                    expires_in=expires_in,
                    bucket_name=bucket_name,
                )
                signed_url = signed.get("signed_url")
                if not signed_url:
                    errors.append(f"signed url failed for {bucket_name}/{storage_path}")
                    continue
                files.append({
                    "filename": name,
                    "url": signed_url,
                    "bucket": bucket_name,
                    "storage_path": storage_path,
                })

    return jsonify({
        "success": True,
        "data": {
            "cloud_id": cloud_id,
            "files": files,
            "errors": errors,
        },
        "error": None,
    })
