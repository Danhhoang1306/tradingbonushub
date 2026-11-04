"""Lệnh quản trị: python -m app.cli create-admin --email X [--role admin|editor]"""
import argparse
import getpass
import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.models import ROLES, AdminUser
from app.security import hash_password, revoke_sessions


def create_admin(email: str, role: str, password: str | None = None) -> int:
    email = email.strip().lower()
    if "@" not in email:
        print("Email không hợp lệ.", file=sys.stderr)
        return 2
    if password is None:
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
            user.password_hash, user.role, user.is_active = hash_password(password), role, True
            revoke_sessions(db, user.id)
            action = "Đã cập nhật mật khẩu (và đăng xuất mọi phiên) cho"
        else:
            db.add(AdminUser(email=email, password_hash=hash_password(password), role=role))
            action = "Đã tạo tài khoản"
        db.commit()
    print(f"{action} {email} ({role}).")
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # console Windows mặc định cp1252
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("create-admin", help="Tạo hoặc đặt lại mật khẩu tài khoản quản trị")
    p.add_argument("--email", required=True)
    p.add_argument("--role", choices=ROLES, default="admin")
    args = parser.parse_args(argv)
    if args.cmd == "create-admin":
        return create_admin(args.email, args.role)
    return 1


if __name__ == "__main__":
    sys.exit(main())
