import argparse
import asyncio
import getpass
import hashlib
import json

from .alibaba import AlibabaClient
from .config import get_settings
from .database import Database
from .password_auth import hash_password, normalize_username, verify_password_or_dummy
from .portal_db import PortalDatabase
from .scanner import discover


def bootstrap_local_operator(repository: PortalDatabase, username: str, password: str):
    normalized = normalize_username(username)
    return repository.create_first_local_operator(
        username=username.strip(), normalized_username=normalized, password_hash=hash_password(password)
    )


def adopt_local_operator(repository: PortalDatabase, user_id: str, username: str, password: str):
    normalized = normalize_username(username)
    return repository.adopt_existing_operator(
        user_id=user_id,
        username=username.strip(),
        normalized_username=normalized,
        password_hash=hash_password(password),
    )


def operator_reset_password(
    repository: PortalDatabase, operator_username: str, operator_password: str, username: str, new_password: str
):
    try:
        operator_normalized = normalize_username(operator_username)
        target_normalized = normalize_username(username)
    except ValueError as exc:
        raise PermissionError("Operator credentials are invalid") from exc
    operator = repository.get_local_user_by_username(operator_normalized)
    if (
        not operator
        or operator["role"] != "operator"
        or operator["status"] != "active"
        or not verify_password_or_dummy(operator_password, operator.get("password_hash"))
    ):
        raise PermissionError("Operator credentials are invalid")
    target = repository.get_local_user_by_username(target_normalized)
    if not target or target["status"] != "active":
        raise ValueError("Active local account not found")
    encoded = hash_password(new_password)
    if not repository.reset_local_password(user_id=target["id"], password_hash=encoded):
        raise ValueError("Active local account not found")
    return repository.get_user(target["id"])


def main():
    parser = argparse.ArgumentParser(prog="provider")
    sub = parser.add_subparsers(dest="command", required=True)
    keys = sub.add_parser("keys")
    keys_sub = keys.add_subparsers(dest="action", required=True)
    create = keys_sub.add_parser("create")
    create.add_argument("--label", default="client")
    keys_sub.add_parser("list")
    for action in ("disable", "enable", "revoke"):
        item = keys_sub.add_parser(action)
        item.add_argument("--id", type=int, required=True)
    scan = sub.add_parser("scan")
    scan.add_argument("--no-probe", action="store_true")
    auth = sub.add_parser("auth")
    auth_sub = auth.add_subparsers(dest="auth_action", required=True)
    auth_sub.add_parser("bootstrap")
    adopt = auth_sub.add_parser("adopt-operator")
    adopt.add_argument("--user-id", required=True)
    reset = auth_sub.add_parser("reset")
    reset.add_argument("--username", required=True)
    args = parser.parse_args()
    settings = get_settings()
    if args.command == "auth":
        portal_pepper = hashlib.sha256(("sponsored-provider:portal:v1:" + settings.provider_key_pepper).encode()).hexdigest()
        repository = PortalDatabase(settings.database_path, key_pepper=portal_pepper)
        if args.auth_action == "bootstrap":
            username = input("First operator username: ")
            password = getpass.getpass("First operator password: ")
            confirmation = getpass.getpass("Repeat password: ")
            if password != confirmation:
                raise SystemExit("Passwords did not match")
            bootstrap_local_operator(repository, username, password)
            print("First operator created.")
        elif args.auth_action == "adopt-operator":
            username = input("Operator username: ")
            password = getpass.getpass("Operator password: ")
            confirmation = getpass.getpass("Repeat password: ")
            if password != confirmation:
                raise SystemExit("Passwords did not match")
            adopt_local_operator(repository, args.user_id, username, password)
            print("Operator account adopted.")
        elif args.auth_action == "reset":
            operator_username = input("Current operator username: ")
            operator_password = getpass.getpass("Current operator password: ")
            new_password = getpass.getpass("New account password: ")
            confirmation = getpass.getpass("Repeat new password: ")
            if new_password != confirmation:
                raise SystemExit("Passwords did not match")
            operator_reset_password(repository, operator_username, operator_password, args.username, new_password)
            print("Account password reset; all of its sessions were revoked.")
        return
    db = Database(settings.database_path, settings.provider_key_pepper)
    if args.command == "keys":
        if args.action == "create":
            raw, metadata = db.create_key(args.label)
            print(json.dumps({"key": raw, **metadata}, indent=2))
        elif args.action == "list":
            print(json.dumps(db.list_keys(), indent=2))
        else:
            db.set_key_state(args.id, args.action == "enable", args.action == "revoke")
            print(json.dumps({"ok": True, "id": args.id, "action": args.action}))
    elif args.command == "scan":
        if not settings.alibaba_api_key:
            raise SystemExit("ALIBABA_API_KEY is required for scanning")
        results = asyncio.run(discover(AlibabaClient(settings.normalized_base_url, settings.alibaba_api_key)))
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
