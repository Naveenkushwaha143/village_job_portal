from __future__ import annotations

import argparse

from .service import VillageJobPortalService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Village job portal SMS demo")
    parser.add_argument("--db-path", default="data/village_jobs.db", help="Path to SQLite database")

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-db", help="Initialize the database")
    init_parser.add_argument("--seed", action="store_true", help="Insert sample worker data")

    sms_parser = subparsers.add_parser("sms", help="Process an incoming SMS message")
    sms_parser.add_argument("--from-phone", required=True, help="Sender phone number")
    sms_parser.add_argument("message", help="SMS content")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    service = VillageJobPortalService(db_path=args.db_path)

    if args.command == "init-db":
        service.initialize(seed=args.seed)
        print(f"Database ready at {args.db_path}")
        return

    if args.command == "sms":
        service.initialize(seed=False)
        print(service.process_message(args.from_phone, args.message))
        return

    parser.error("Unsupported command")


if __name__ == "__main__":
    main()