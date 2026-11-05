"""Lệnh quản trị: python -m app.cli create-admin --email X [--role admin|editor]

Mật khẩu: nhập qua prompt, hoặc đặt biến môi trường ADMIN_PASSWORD để chạy không tương tác.
Không có tham số dòng lệnh cho mật khẩu vì sẽ lộ trong lịch sử shell và danh sách tiến trình.
"""
import argparse
import getpass
import os
import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.models import ROLES, AdminUser
from app.security import hash_password, revoke_sessions


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):  # console Windows mặc định cp1252
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _has_console() -> bool:
    """Không dùng isatty(): trên Windows NUL cũng báo là tty, rồi getpass treo vô hạn."""
    try:
        os.get_terminal_size(sys.stdin.fileno())
        return True
    except (OSError, ValueError, AttributeError):
        return False


def create_admin(email: str, role: str | None = None, password: str | None = None) -> int:
    """Tạo tài khoản (mặc định role admin) hoặc đặt lại mật khẩu (role giữ nguyên trừ khi truyền rõ)."""
    _utf8_console()
    email = email.strip().lower()
    if "@" not in email:
        print("Email không hợp lệ.", file=sys.stderr)
        return 2
    password = password or os.environ.get("ADMIN_PASSWORD") or None
    if password is None:
        if not _has_console():
            print("Không có console để nhập mật khẩu: đặt biến môi trường ADMIN_PASSWORD.", file=sys.stderr)
            return 2
        password = getpass.getpass("Mật khẩu (tối thiểu 10 ký tự): ")
        if password != getpass.getpass("Nhập lại mật khẩu: "):
            print("Hai lần nhập không khớp.", file=sys.stderr)
            return 2
    if len(password) < 10:
        print("Mật khẩu tối thiểu 10 ký tự.", file=sys.stderr)
        return 2
    with SessionLocal() as db:
        user = db.scalar(select(AdminUser).where(AdminUser.email == email))
        if user:
            user.password_hash, user.is_active = hash_password(password), True
            user.role = role or user.role
            revoke_sessions(db, user.id)
            action = "Đã cập nhật mật khẩu (và đăng xuất mọi phiên) cho"
        else:
            user = AdminUser(email=email, password_hash=hash_password(password), role=role or "admin")
            db.add(user)
            action = "Đã tạo tài khoản"
        db.commit()
        print(f"{action} {email} ({user.role}).")
    return 0


def main(argv: list[str] | None = None) -> int:
    _utf8_console()
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("create-admin", help="Tạo hoặc đặt lại mật khẩu tài khoản quản trị")
    p.add_argument("--email", required=True)
    p.add_argument("--role", choices=ROLES, help="mặc định: admin khi tạo mới, giữ nguyên khi đặt lại mật khẩu")
    args = parser.parse_args(argv)
    if args.cmd == "create-admin":
        return create_admin(args.email, args.role)
    return 1


if __name__ == "__main__":
    sys.exit(main())
