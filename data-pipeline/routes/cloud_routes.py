import base64
import json
import os
import uuid
from datetime import datetime
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


def _normalize_tags_payload(tags):
    """
    兼容两种 tags 结构：
    1) 扁平数组: [{lens, word_id, ...}]
    2) 分组对象: {texture: [...], source: [...]}
    """
    if isinstance(tags, list):
        return tags
    if not isinstance(tags, dict):
        return []

    flattened = []
    for lens, tag_list in tags.items():
        if not isinstance(tag_list, list):
            continue
        for tag in tag_list:
            if not isinstance(tag, dict):
                continue
            flattened.append({
                "lens": tag.get("lens") or tag.get("lens_id") or lens,
                "word_id": tag.get("word_id") or tag.get("id") or tag.get("word"),
                "word_cn": tag.get("word_cn") or tag.get("zh"),
                "word_en": tag.get("word_en") or tag.get("en") or tag.get("word"),
                "x": tag.get("x"),
                "y": tag.get("y"),
            })
    return flattened


def _extract_plugin_fields_from_metadata_obj(metadata_obj):
    """
    从 metadata.json 兼容提取插件信息，返回 (plugin_count, plugin_list)
    """
    if not isinstance(metadata_obj, dict):
        return 0, []

    plugin_list = metadata_obj.get("plugin_list")
    plugins_field = metadata_obj.get("plugins")
    info_obj = metadata_obj.get("info") if isinstance(metadata_obj.get("info"), dict) else {}
    info_plugins = info_obj.get("plugins") if isinstance(info_obj.get("plugins"), dict) else {}

    if plugin_list is None and isinstance(plugins_field, dict):
        plugin_list = plugins_field.get("list")
    if plugin_list is None and isinstance(plugins_field, list):
        plugin_list = plugins_field
    if plugin_list is None:
        plugin_list = info_plugins.get("list")

    if not isinstance(plugin_list, list):
        plugin_list = []

    plugin_count = metadata_obj.get("plugin_count")
    if plugin_count is None and isinstance(plugins_field, dict):
        plugin_count = plugins_field.get("count")
    if plugin_count is None and isinstance(plugins_field, list):
        plugin_count = len(plugins_field)
    if plugin_count is None:
        plugin_count = info_plugins.get("count")
    if plugin_count is None:
        plugin_count = len(plugin_list)

    try:
        plugin_count = int(plugin_count)
    except Exception:
        plugin_count = len(plugin_list)

    return plugin_count, plugin_list


def _normalize_cloud_metadata(raw_metadata):
    if isinstance(raw_metadata, str):
        try:
            raw_metadata = json.loads(raw_metadata)
        except Exception:
            raw_metadata = {}
    if not isinstance(raw_metadata, dict):
        raw_metadata = {}

    nested_metadata = raw_metadata.get("metadata")
    if not isinstance(nested_metadata, dict):
        nested_metadata = {}

    preview_audio = nested_metadata.get("preview_audio") or raw_metadata.get("preview_audio")
    rpp_file = nested_metadata.get("rpp_file") or raw_metadata.get("rpp_file")
    if preview_audio:
        nested_metadata["preview_audio"] = preview_audio
    if rpp_file:
        nested_metadata["rpp_file"] = rpp_file

    normalized = dict(raw_metadata)
    normalized["metadata"] = nested_metadata
    # 兼容策略：双写顶层与 metadata.metadata，避免旧链路漏读
    if preview_audio:
        normalized["preview_audio"] = preview_audio
    if rpp_file:
        normalized["rpp_file"] = rpp_file
    return normalized


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

    metadata = _normalize_cloud_metadata(capsule.get("metadata") or {})
    nested_metadata = metadata.get("metadata") if isinstance(metadata.get("metadata"), dict) else {}
    capsule_data = {
        "id": capsule.get("id"),
        "name": capsule.get("name") or folder,
        "file_path": folder,
        "capsule_type": capsule.get("capsule_type"),
        "keywords": capsule.get("keywords"),
        "description": capsule.get("description"),
        # 兼容旧读取口径：顶层同时写 preview_audio/rpp_file
        "preview_audio": nested_metadata.get("preview_audio") or ((files.get("preview") or {}).get("filename")),
        "rpp_file": nested_metadata.get("rpp_file") or ((files.get("rpp") or {}).get("filename")),
        "metadata": {
            **nested_metadata,
            "preview_audio": nested_metadata.get("preview_audio") or ((files.get("preview") or {}).get("filename")),
            "rpp_file": nested_metadata.get("rpp_file") or ((files.get("rpp") or {}).get("filename")),
        },
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


@cloud_bp.route("/capsules/<capsule_ref>/sync-tags", methods=["POST", "OPTIONS"])
@token_required
def sync_capsule_tags(current_user, capsule_ref):
    """
    云端显式关键词同步：
    - 写 cloud_capsule_tags
    - 更新 cloud_capsules.metadata.keywords
    """
    data = request.get_json(silent=True) or {}
    raw_tags = data.get("tags") or []
    tags = _normalize_tags_payload(raw_tags)
    keywords = data.get("keywords")

    owner_id = current_user.get("supabase_user_id") or str(current_user.get("id", ""))
    if not owner_id:
        raise APIError("用户 ID 不存在", 400)

    supabase = get_supabase_client()
    if not supabase:
        raise APIError("Supabase 客户端未初始化", 500)

    cloud_id = str(capsule_ref or "").strip()
    cloud_capsule = None

    # 1) 优先按 cloud_id + user_id 查
    if cloud_id:
        try:
            r = (
                supabase.client
                .table("cloud_capsules")
                .select("id, metadata")
                .eq("id", cloud_id)
                .eq("user_id", owner_id)
                .limit(1)
                .execute()
            )
            if r.data:
                cloud_capsule = r.data[0]
        except Exception:
            cloud_capsule = None

    # 2) 若 capsule_ref 不是 cloud_id，尝试按 local_id + user_id 查
    if not cloud_capsule:
        try:
            local_id = int(capsule_ref)
            r = (
                supabase.client
                .table("cloud_capsules")
                .select("id, metadata")
                .eq("local_id", local_id)
                .eq("user_id", owner_id)
                .limit(1)
                .execute()
            )
            if r.data:
                cloud_capsule = r.data[0]
                cloud_id = str(cloud_capsule.get("id") or "").strip()
        except Exception:
            pass

    if not cloud_capsule or not cloud_id:
        raise APIError("云端胶囊不存在或无权限", 404)

    tags_ok = supabase.upload_tags(owner_id, cloud_id, tags)
    if not tags_ok:
        raise APIError("上传 tags 到云端失败", 500)

    # 更新 metadata.keywords（可选）
    if keywords is not None:
        metadata = cloud_capsule.get("metadata") or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        metadata["keywords"] = keywords
        try:
            (
                supabase.client
                .table("cloud_capsules")
                .update({
                    "metadata": metadata,
                    "last_write_at": datetime.utcnow().isoformat(),
                })
                .eq("id", cloud_id)
                .eq("user_id", owner_id)
                .execute()
            )
        except Exception as e:
            raise APIError(f"更新 cloud_capsules.keywords 失败: {e}", 500)

    return jsonify({
        "success": True,
        "data": {
            "cloud_id": cloud_id,
            "tags_uploaded": len(tags),
            "keywords_updated": keywords is not None,
        },
        "error": None,
    })


@cloud_bp.route("/capsules/<capsule_ref>/sync-plugin-metadata", methods=["POST", "OPTIONS"])
@token_required
def sync_plugin_metadata(current_user, capsule_ref):
    """
    从 Storage 的 metadata.json 回填 cloud_capsules.metadata 的插件字段。
    """
    owner_id = current_user.get("supabase_user_id") or str(current_user.get("id", ""))
    if not owner_id:
        raise APIError("用户 ID 不存在", 400)

    supabase = get_supabase_client()
    if not supabase:
        raise APIError("Supabase 客户端未初始化", 500)

    cloud_id = str(capsule_ref or "").strip()
    cloud_capsule = None

    # 1) 优先按 cloud_id + user_id 查
    if cloud_id:
        try:
            r = (
                supabase.client
                .table("cloud_capsules")
                .select("id, user_id, name, metadata")
                .eq("id", cloud_id)
                .eq("user_id", owner_id)
                .limit(1)
                .execute()
            )
            if r.data:
                cloud_capsule = r.data[0]
        except Exception:
            cloud_capsule = None

    # 2) 若 capsule_ref 可能是 local_id，尝试 local_id + user_id
    if not cloud_capsule:
        try:
            local_id = int(capsule_ref)
            r = (
                supabase.client
                .table("cloud_capsules")
                .select("id, user_id, name, metadata")
                .eq("local_id", local_id)
                .eq("user_id", owner_id)
                .limit(1)
                .execute()
            )
            if r.data:
                cloud_capsule = r.data[0]
                cloud_id = str(cloud_capsule.get("id") or "").strip()
        except Exception:
            pass

    if not cloud_capsule or not cloud_id:
        raise APIError("云端胶囊不存在或无权限", 404)

    metadata = cloud_capsule.get("metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}

    folder = metadata.get("file_path") or cloud_capsule.get("name")
    if not folder:
        raise APIError("缺少 file_path/name，无法定位 metadata.json", 400)

    storage_path = f"{owner_id}/{folder}/metadata.json"
    metadata_bytes = None
    last_err = None

    # 兼容历史 bucket：优先 capsule-files，再回退 capsules
    for bucket in ("capsule-files", "capsules"):
        try:
            metadata_bytes = supabase.client.storage.from_(bucket).download(storage_path)
            if metadata_bytes:
                break
        except Exception as e:
            last_err = e
            metadata_bytes = None

    if not metadata_bytes:
        raise APIError(f"读取 Storage metadata.json 失败: {last_err or 'file_not_found'}", 404)

    try:
        metadata_file_obj = json.loads(metadata_bytes.decode("utf-8"))
    except Exception as e:
        raise APIError(f"metadata.json 解析失败: {e}", 400)

    plugin_count, plugin_list = _extract_plugin_fields_from_metadata_obj(metadata_file_obj)

    # 回填到 cloud_capsules.metadata，同时保留原字段
    merged_metadata = dict(metadata)
    merged_metadata["plugin_count"] = plugin_count
    merged_metadata["plugin_list"] = plugin_list
    merged_metadata["plugins"] = {"count": plugin_count, "list": plugin_list}

    try:
        (
            supabase.client
            .table("cloud_capsules")
            .update({
                "metadata": merged_metadata,
                "last_write_at": datetime.utcnow().isoformat(),
            })
            .eq("id", cloud_id)
            .eq("user_id", owner_id)
            .execute()
        )
    except Exception as e:
        raise APIError(f"回填插件信息失败: {e}", 500)

    return jsonify({
        "success": True,
        "data": {
            "cloud_id": cloud_id,
            "plugin_count": plugin_count,
            "plugin_list_len": len(plugin_list or []),
            "metadata_storage_path": storage_path,
        },
        "error": None,
    })


@cloud_bp.route("/capsules/<capsule_ref>/sync-file-metadata", methods=["POST", "OPTIONS"])
@token_required
def sync_file_metadata(current_user, capsule_ref):
    """
    上传文件后回写 cloud_capsules.metadata 里的轻资产路径信息：
    - metadata.file_path
    - metadata.metadata.preview_audio
    - metadata.metadata.rpp_file
    """
    data = request.get_json(silent=True) or {}
    owner_id = current_user.get("supabase_user_id") or str(current_user.get("id", ""))
    if not owner_id:
        raise APIError("用户 ID 不存在", 400)

    supabase = get_supabase_client()
    if not supabase:
        raise APIError("Supabase 客户端未初始化", 500)

    cloud_id = str(capsule_ref or "").strip()
    cloud_capsule = None

    if cloud_id:
        try:
            r = (
                supabase.client
                .table("cloud_capsules")
                .select("id,user_id,metadata")
                .eq("id", cloud_id)
                .eq("user_id", owner_id)
                .limit(1)
                .execute()
            )
            if r.data:
                cloud_capsule = r.data[0]
        except Exception:
            cloud_capsule = None

    if not cloud_capsule:
        try:
            local_id = int(capsule_ref)
            r = (
                supabase.client
                .table("cloud_capsules")
                .select("id,user_id,metadata")
                .eq("local_id", local_id)
                .eq("user_id", owner_id)
                .limit(1)
                .execute()
            )
            if r.data:
                cloud_capsule = r.data[0]
                cloud_id = str(cloud_capsule.get("id") or "").strip()
        except Exception:
            pass

    if not cloud_capsule or not cloud_id:
        raise APIError("云端胶囊不存在或无权限", 404)

    file_path = str(data.get("file_path") or "").strip()
    incoming_meta = data.get("metadata") or {}
    if not isinstance(incoming_meta, dict):
        incoming_meta = {}

    existing_metadata = _normalize_cloud_metadata(cloud_capsule.get("metadata") or {})
    nested_metadata = existing_metadata.get("metadata") if isinstance(existing_metadata.get("metadata"), dict) else {}
    nested_metadata = dict(nested_metadata)

    if "preview_audio" in incoming_meta:
        preview_name = incoming_meta.get("preview_audio")
        if preview_name is None:
            nested_metadata.pop("preview_audio", None)
            existing_metadata.pop("preview_audio", None)
        else:
            normalized_preview = str(preview_name).strip()
            nested_metadata["preview_audio"] = normalized_preview
            existing_metadata["preview_audio"] = normalized_preview

    if "rpp_file" in incoming_meta:
        rpp_name = incoming_meta.get("rpp_file")
        if rpp_name is None:
            nested_metadata.pop("rpp_file", None)
            existing_metadata.pop("rpp_file", None)
        else:
            normalized_rpp = str(rpp_name).strip()
            nested_metadata["rpp_file"] = normalized_rpp
            existing_metadata["rpp_file"] = normalized_rpp

    merged_metadata = dict(existing_metadata)
    merged_metadata["metadata"] = nested_metadata
    if file_path:
        merged_metadata["file_path"] = file_path

    try:
        (
            supabase.client
            .table("cloud_capsules")
            .update({
                "metadata": merged_metadata,
                "last_write_at": datetime.utcnow().isoformat(),
            })
            .eq("id", cloud_id)
            .eq("user_id", owner_id)
            .execute()
        )
    except Exception as e:
        raise APIError(f"更新文件元数据失败: {e}", 500)

    return jsonify({
        "success": True,
        "data": {
            "cloud_id": cloud_id,
            "file_path": merged_metadata.get("file_path"),
            "preview_audio": (merged_metadata.get("metadata") or {}).get("preview_audio"),
            "rpp_file": (merged_metadata.get("metadata") or {}).get("rpp_file"),
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
            metadata = _normalize_cloud_metadata(cap.get("metadata") or {})
            nested_metadata = metadata.get("metadata") if isinstance(metadata.get("metadata"), dict) else {}
            folder = metadata.get("file_path") or cap.get("name")
            if not owner_id or not folder:
                errors.append(f"{cloud_id}: missing owner/folder")
                continue

            plan = [("metadata", "metadata.json")]
            preview_name = nested_metadata.get("preview_audio") or metadata.get("preview_audio")
            if include_previews and preview_name:
                plan.append(("preview", preview_name))
            rpp_name = nested_metadata.get("rpp_file") or metadata.get("rpp_file") or f"{folder}.rpp"
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
