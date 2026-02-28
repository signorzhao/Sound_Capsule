#!/usr/bin/env bash
set -euo pipefail

# 最小联调闭环脚本（服务端托管 service_role 版本）
# 用法：
#   API_ORIGIN=http://192.168.31.71:5002 \
#   LOCAL_API_BASE=http://127.0.0.1:5003/api \
#   LOGIN_EMAIL=xxx LOGIN_PASSWORD=xxx \
#   ./scripts/minimal_e2e_alignment.sh

API_ORIGIN="${API_ORIGIN:-http://192.168.31.71:5002}"
API_BASE="${API_BASE:-${API_ORIGIN}/api}"
LOCAL_API_BASE="${LOCAL_API_BASE:-http://127.0.0.1:5003/api}"
LOGIN_EMAIL="${LOGIN_EMAIL:-}"
LOGIN_PASSWORD="${LOGIN_PASSWORD:-}"

if [[ -z "${LOGIN_EMAIL}" || -z "${LOGIN_PASSWORD}" ]]; then
  echo "ERROR: LOGIN_EMAIL / LOGIN_PASSWORD 不能为空"
  exit 1
fi

echo "[1/10] health"
curl -sS "${API_BASE}/health" | python3 -m json.tool

echo "[2/10] login"
LOGIN_RESP="$(curl -sS -X POST "${API_BASE}/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${LOGIN_EMAIL}\",\"password\":\"${LOGIN_PASSWORD}\"}")"
echo "${LOGIN_RESP}" | python3 -m json.tool

ACCESS_TOKEN="$(LOGIN_RESP="${LOGIN_RESP}" python3 - <<'PY'
import json,os
d=json.loads(os.environ["LOGIN_RESP"])
print(d.get("access_token") or d.get("data",{}).get("access_token",""))
PY
)"
REFRESH_TOKEN="$(LOGIN_RESP="${LOGIN_RESP}" python3 - <<'PY'
import json,os
d=json.loads(os.environ["LOGIN_RESP"])
print(d.get("refresh_token") or d.get("data",{}).get("refresh_token",""))
PY
)"
echo "ACCESS_TOKEN_LEN=${#ACCESS_TOKEN}"
echo "REFRESH_TOKEN_LEN=${#REFRESH_TOKEN}"

echo "[3/10] auth/me"
curl -sS "${API_BASE}/auth/me" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" | python3 -m json.tool

echo "[4/10] admin/rest"
curl -sS "${API_BASE}/admin/rest/cloud_capsules?select=id,name,updated_at&limit=5" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" | python3 -m json.tool

echo "[5/10] lightweight-page first page"
PAGE1="$(curl -sS -X POST "${API_BASE}/sync/lightweight-page" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"include_previews":true,"page_size":50,"cursor":null}')"
echo "${PAGE1}" | python3 -m json.tool

NEXT_CURSOR="$(PAGE1="${PAGE1}" python3 - <<'PY'
import json,os
d=json.loads(os.environ["PAGE1"])
print((d.get("data") or {}).get("next_cursor") or "")
PY
)"
ITEMS_JSON="$(PAGE1="${PAGE1}" python3 - <<'PY'
import json,os
d=json.loads(os.environ["PAGE1"])
print(json.dumps((d.get("data") or {}).get("items",[]), ensure_ascii=False))
PY
)"

echo "[6/10] apply-lightweight-page local"
curl -sS -X POST "${LOCAL_API_BASE}/sync/apply-lightweight-page" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"items\":${ITEMS_JSON},\"include_previews\":true}" | python3 -m json.tool

echo "[7/10] next page (optional)"
if [[ -n "${NEXT_CURSOR}" ]]; then
  curl -sS -X POST "${API_BASE}/sync/lightweight-page" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"include_previews\":true,\"page_size\":50,\"cursor\":\"${NEXT_CURSOR}\"}" | python3 -m json.tool
else
  echo "No NEXT_CURSOR, skip."
fi

echo "[8/10] upload-capsule smoke"
curl -sS -X POST "${API_BASE}/cloud/upload-capsule" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "capsule_folder_name":"smoke_test_capsule",
    "capsule":{"id":900001,"name":"smoke_test_capsule","file_path":"smoke_test_capsule","capsule_type":"magic"},
    "files":{}
  }' | python3 -m json.tool

echo "[9/10] refresh"
curl -sS -X POST "${API_BASE}/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"${REFRESH_TOKEN}\"}" | python3 -m json.tool

echo "[10/10] done"
