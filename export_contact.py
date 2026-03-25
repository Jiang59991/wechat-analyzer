#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
export_contact.py — 从解密后的 Mac 微信 SQLite 数据库导出指定联系人的消息

用法：
  python export_contact.py --list-contacts
  python export_contact.py --contact "姓名或备注"
  python export_contact.py --contact "姓名" --output ./my_chat.csv
"""

import argparse
import csv
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent
_CONFIG_PATH = _SCRIPT_DIR / 'config.json'


def load_config() -> dict:
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH) as f:
            return json.load(f)
    return {}


def get_db_dir() -> Path:
    cfg = load_config()
    db_dir = cfg.get('decrypted_db_dir', '')
    if db_dir:
        p = Path(os.path.expanduser(db_dir))
        if p.exists():
            return p
    default = Path.home() / 'Documents/wechat-db-decrypt-macos/decrypted'
    if default.exists():
        return default
    print("❌ 找不到解密数据库目录。请检查 config.json 中的 decrypted_db_dir 路径。")
    sys.exit(1)


def md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def list_contacts(db_dir: Path):
    contact_db = db_dir / 'contact' / 'contact.db'
    conn = sqlite3.connect(contact_db)
    rows = conn.execute(
        "SELECT username, remark, nick_name FROM contact "
        "WHERE local_type != 4 ORDER BY remark, nick_name"
    ).fetchall()
    conn.close()
    print(f"{'备注名':<20} {'昵称':<20} {'微信ID'}")
    print("-" * 60)
    for username, remark, nick in rows:
        print(f"{(remark or ''):<20} {(nick or ''):<20} {username}")


def find_contact(db_dir: Path, name: str):
    contact_db = db_dir / 'contact' / 'contact.db'
    conn = sqlite3.connect(contact_db)
    rows = conn.execute(
        "SELECT username, remark, nick_name FROM contact "
        "WHERE remark LIKE ? OR nick_name LIKE ? OR username LIKE ?",
        (f'%{name}%', f'%{name}%', f'%{name}%')
    ).fetchall()
    conn.close()
    return rows


def get_self_wxid(db_dir: Path) -> str:
    """推断自己的 wxid：先查 WeChat 数据目录，再从 Name2Id 找"""
    import glob

    # 方法1：从 WeChat 原始数据目录找 wxid_ 开头的文件夹
    wechat_dir = Path.home() / 'Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files'
    if wechat_dir.exists():
        candidates = [d.name.split('_0ad')[0] for d in wechat_dir.iterdir()
                      if d.is_dir() and d.name.startswith('wxid_')]
        if len(candidates) == 1:
            return candidates[0]

    # 方法2：从 Name2Id 表中找唯一的 wxid_ 账号（排除联系人）
    msg_db = db_dir / 'message' / 'message_0.db'
    contact_db = db_dir / 'contact' / 'contact.db'
    conn = sqlite3.connect(msg_db)
    rows = conn.execute("SELECT user_name FROM Name2Id").fetchall()
    conn.close()

    # 所有联系人的 wxid
    conn2 = sqlite3.connect(contact_db)
    contacts = {r[0] for r in conn2.execute("SELECT username FROM contact").fetchall()}
    conn2.close()

    # 在 Name2Id 里，不是联系人的 wxid_ 账号就是自己
    own_wxids = [u for (u,) in rows if u and u.startswith('wxid_') and u not in contacts]
    if len(own_wxids) == 1:
        return own_wxids[0]
    if own_wxids:
        return own_wxids[0]
    return None


def get_sender_rowids(msg_db: Path, self_wxid: str, contact_wxid: str):
    """通过 Name2Id 表的 rowid 获取 real_sender_id"""
    conn = sqlite3.connect(msg_db)
    rows = conn.execute("SELECT rowid, user_name FROM Name2Id").fetchall()
    conn.close()
    self_id, contact_id = None, None
    for rowid, user_name in rows:
        if user_name == self_wxid:
            self_id = rowid
        if user_name == contact_wxid:
            contact_id = rowid
    return self_id, contact_id


def export_messages(db_dir: Path, contact_wxid: str, contact_name: str,
                    self_wxid: str, output_path: Path):
    table = f"Msg_{md5(contact_wxid)}"
    msg_db = db_dir / 'message' / 'message_0.db'

    conn = sqlite3.connect(msg_db)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    if table not in tables:
        print(f"❌ 找不到消息表 {table}，可能没有与此联系人的消息记录。")
        conn.close()
        sys.exit(1)

    self_id, _ = get_sender_rowids(msg_db, self_wxid, contact_wxid)

    rows = conn.execute(
        f"SELECT create_time, real_sender_id, local_type, message_content "
        f"FROM {table} ORDER BY create_time ASC"
    ).fetchall()
    conn.close()

    msg_count = len(rows)
    print(f"[*] 找到 {msg_count} 条消息")

    try:
        import zstd
        _zstd_available = True
    except ImportError:
        _zstd_available = False

    ZSTD_MAGIC = b'\x28\xb5\x2f\xfd'

    def decode_content(raw) -> str:
        if raw is None:
            return ''
        if isinstance(raw, bytes):
            if _zstd_available and raw[:4] == ZSTD_MAGIC:
                try:
                    return zstd.decompress(raw).decode('utf-8', errors='replace')
                except Exception:
                    pass
            return raw.decode('utf-8', errors='replace')
        return str(raw)

    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'datetime', 'sender', 'is_sender', 'type', 'content'])
        for create_time, sender_id, local_type, content in rows:
            dt = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S')
            is_self = 1 if sender_id == self_id else 0
            sender_name = '我' if is_self else contact_name
            writer.writerow([create_time, dt, sender_name, is_self, local_type, decode_content(content)])

    print(f"EXPORT_PATH:{output_path}")
    return msg_count


def get_self_nick(db_dir: Path, self_wxid: str) -> str | None:
    """尝试从 contact.db 或微信文件目录获取自己的昵称"""
    # 方法1：contact.db 里可能有自己的记录
    try:
        contact_db = db_dir / 'contact' / 'contact.db'
        conn = sqlite3.connect(contact_db)
        row = conn.execute(
            "SELECT nick_name FROM contact WHERE username = ?", (self_wxid,)
        ).fetchone()
        conn.close()
        if row and row[0]:
            return row[0]
    except Exception:
        pass

    # 方法2：从微信文件目录名提取（形如 wxid_xxx_0ad...）
    wechat_dir = Path.home() / 'Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files'
    if wechat_dir.exists():
        for d in wechat_dir.iterdir():
            if d.is_dir() and d.name.startswith(self_wxid):
                # 有时目录名就包含昵称信息，但通常只有 wxid
                break
    return None


def get_avatar_path(wxid: str) -> str | None:
    """在 Mac 微信文件目录中搜索头像图片，返回路径或 None"""
    import glob as _glob
    wechat_base = Path.home() / 'Library/Containers/com.tencent.xinWeChat'
    if not wechat_base.exists():
        return None

    wxid_md5 = hashlib.md5(wxid.encode()).hexdigest()

    # 常见头像缓存路径
    patterns = [
        str(wechat_base / 'Data/Documents/xwechat_files/*/Avatars' / wxid_md5),
        str(wechat_base / 'Data/Documents/xwechat_files/*/Avatars' / f'{wxid_md5}*'),
        str(wechat_base / 'Data/Library/Application Support/com.tencent.xinWeChat/*/Avatars' / wxid_md5),
        str(wechat_base / 'Data/Library/Application Support/com.tencent.xinWeChat/*/Avatars' / f'{wxid_md5}*'),
    ]
    IMAGE_MAGIC = (b'\xff\xd8\xff', b'\x89PNG', b'GIF8', b'RIFF', b'\x00\x00\x01\x00')
    for pattern in patterns:
        for m in _glob.glob(pattern):
            try:
                with open(m, 'rb') as f:
                    header = f.read(8)
                if any(header.startswith(sig) for sig in IMAGE_MAGIC):
                    return m
            except Exception:
                continue
    return None


def main():
    parser = argparse.ArgumentParser(description='导出微信聊天记录 (Mac 版)')
    parser.add_argument('--contact', help='联系人备注名或昵称')
    parser.add_argument('--list-contacts', action='store_true', help='列出所有联系人')
    parser.add_argument('--output', help='输出 CSV 路径')
    parser.add_argument('--db-dir', help='解密数据库目录（覆盖 config.json）')
    args = parser.parse_args()

    db_dir = Path(os.path.expanduser(args.db_dir)) if args.db_dir else get_db_dir()

    if args.list_contacts:
        list_contacts(db_dir)
        return

    if not args.contact:
        parser.print_help()
        sys.exit(1)

    matches = find_contact(db_dir, args.contact)
    if not matches:
        print(f"❌ 找不到联系人：{args.contact}")
        print("提示：使用 --list-contacts 查看所有联系人")
        sys.exit(1)

    if len(matches) > 1:
        print(f"找到 {len(matches)} 个匹配联系人：")
        for i, (username, remark, nick) in enumerate(matches):
            print(f"  [{i+1}] {remark or nick} ({username})")
        choice = input("请输入编号：").strip()
        try:
            idx = int(choice) - 1
            username, remark, nick = matches[idx]
        except (ValueError, IndexError):
            print("无效选择")
            sys.exit(1)
    else:
        username, remark, nick = matches[0]

    contact_name = remark or nick or username
    print(f"[*] 分析联系人：{contact_name} ({username})")

    self_wxid = get_self_wxid(db_dir)
    if not self_wxid:
        print("❌ 无法确定自己的微信 ID")
        sys.exit(1)
    print(f"[*] 自己的 wxid：{self_wxid}")

    if args.output:
        output_path = Path(args.output)
    else:
        safe_name = contact_name.encode('ascii', 'ignore').decode() or 'contact'
        safe_name = safe_name.replace('/', '_').replace(' ', '_')[:20] or 'contact'
        output_path = _SCRIPT_DIR / f"export_{safe_name}.csv"

    export_messages(db_dir, username, contact_name, self_wxid, output_path)

    # 写 meta sidecar JSON（昵称 + 头像路径）
    self_nick = get_self_nick(db_dir, self_wxid) or '我'
    self_avatar = get_avatar_path(self_wxid)
    partner_avatar = get_avatar_path(username)
    meta = {
        'self_wxid': self_wxid,
        'self_name': self_nick,
        'self_avatar_path': self_avatar,
        'partner_wxid': username,
        'partner_name': contact_name,
        'partner_avatar_path': partner_avatar,
    }
    meta_path = output_path.with_suffix('.meta.json')
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"META_PATH:{meta_path}")


if __name__ == '__main__':
    main()
