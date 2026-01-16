{\rtf1\ansi\ansicpg936\cocoartf2822
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 -- 1. \uc0\u26865 \u38236 \u37197 \u32622 \u20027 \u34920  (Source of Truth)\
CREATE TABLE IF NOT EXISTS prisms (\
    id TEXT PRIMARY KEY,          -- \uc0\u26865 \u38236  ID (\u22914  'texture', 'mechanics')\
    name TEXT NOT NULL,           -- \uc0\u26174 \u31034 \u21517 \u31216  (\u22914  'Texture / (\u36136 \u24863 )')\
    description TEXT,             -- \uc0\u25551 \u36848 \
    \
    -- \uc0\u36724 \u26631 \u31614 \u37197 \u32622  (JSON \u23384 \u20648 )\
    axis_config TEXT DEFAULT '\{\}', \
    \
    -- \uc0\u38170 \u28857 \u25968 \u25454  (JSON \u23384 \u20648 \u65292 \u26680 \u24515 \u25968 \u25454 )\
    anchors TEXT DEFAULT '[]',     \
    \
    -- \uc0\u29256 \u26412 \u25511 \u21046 \u23383 \u27573 \
    version INTEGER DEFAULT 1,     -- \uc0\u24403 \u21069 \u29256 \u26412 \u21495 \
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,\
    updated_by TEXT,               -- \uc0\u20462 \u25913 \u32773  (device_id \u25110  user_id)\
    \
    -- \uc0\u29366 \u24577 \
    is_deleted BOOLEAN DEFAULT 0\
);\
\
-- 2. \uc0\u26865 \u38236 \u29256 \u26412 \u21382 \u21490 \u34920  (\u29992 \u20110 \u22238 \u28378 \u21644 \u20914 \u31361 \u35299 \u20915 )\
CREATE TABLE IF NOT EXISTS prism_versions (\
    version_id INTEGER PRIMARY KEY AUTOINCREMENT,\
    prism_id TEXT NOT NULL,\
    version INTEGER NOT NULL,\
    \
    -- \uc0\u27492 \u26102 \u21051 \u30340 \u23436 \u25972 \u37197 \u32622 \u24555 \u29031 \
    snapshot_data TEXT NOT NULL,   -- JSON \uc0\u26684 \u24335 \
    \
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,\
    created_by TEXT,\
    change_reason TEXT,            -- \uc0\u20462 \u25913 \u21407 \u22240  (e.g. 'user_edit', 'sync_merge')\
    \
    FOREIGN KEY (prism_id) REFERENCES prisms (id)\
);\
\
-- 3. \uc0\u21516 \u27493 \u26085 \u24535  (\u29992 \u20110 \u35843 \u35797 )\
CREATE TABLE IF NOT EXISTS prism_sync_log (\
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,\
    prism_id TEXT,\
    action TEXT,                   -- 'upload', 'download', 'conflict_resolve'\
    status TEXT,                   -- 'success', 'failed'\
    details TEXT,\
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP\
);\
\
-- \uc0\u32034 \u24341 \u20248 \u21270 \
CREATE INDEX IF NOT EXISTS idx_prism_version ON prism_versions(prism_id, version);}