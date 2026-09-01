import argparse
import asyncio
import json

from .alibaba import AlibabaClient
from .config import get_settings
from .database import Database
from .scanner import discover


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
    args = parser.parse_args()
    settings = get_settings()
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
