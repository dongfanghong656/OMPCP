#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from secure_config import (
    SecureConfigError,
    all_secret_bindings,
    migrate_config_secrets,
    secret_status,
    set_secret,
    unset_secret,
)


def read_secret_value(args: argparse.Namespace) -> str:
    provided = [
        bool(args.value),
        bool(args.value_file),
        bool(args.stdin),
    ]
    if sum(1 for item in provided if item) != 1:
        raise SecureConfigError("Choose exactly one of --value, --value-file, or --stdin.")

    if args.value:
        return args.value
    if args.value_file:
        return Path(args.value_file).read_text(encoding="utf-8").rstrip("\r\n")
    return sys.stdin.read().rstrip("\r\n")


def command_status(args: argparse.Namespace) -> None:
    print(json.dumps(secret_status(Path(args.config)), ensure_ascii=False, indent=2))


def command_migrate(args: argparse.Namespace) -> None:
    print(json.dumps(migrate_config_secrets(Path(args.config)), ensure_ascii=False, indent=2))


def command_set(args: argparse.Namespace) -> None:
    value = read_secret_value(args)
    print(json.dumps(set_secret(Path(args.config), args.secret_id, value), ensure_ascii=False, indent=2))


def command_unset(args: argparse.Namespace) -> None:
    print(json.dumps(unset_secret(Path(args.config), args.secret_id), ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage the local DPAPI-backed secret store for oct-research-assist."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Show secure-config status without revealing values.")
    status_parser.add_argument("--config", required=True)
    status_parser.set_defaults(func=command_status)

    migrate_parser = subparsers.add_parser(
        "migrate-config",
        help="Move inline plaintext secrets from config.json into the local encrypted store.",
    )
    migrate_parser.add_argument("--config", required=True)
    migrate_parser.set_defaults(func=command_migrate)

    set_parser = subparsers.add_parser("set", help="Store one secret locally and bind config.json to its secure ref.")
    set_parser.add_argument("--config", required=True)
    set_parser.add_argument(
        "--secret-id",
        required=True,
        choices=[binding.secret_id for binding in all_secret_bindings()],
    )
    set_parser.add_argument("--value")
    set_parser.add_argument("--value-file")
    set_parser.add_argument("--stdin", action="store_true")
    set_parser.set_defaults(func=command_set)

    unset_parser = subparsers.add_parser("unset", help="Delete one locally stored secret value.")
    unset_parser.add_argument("--config", required=True)
    unset_parser.add_argument(
        "--secret-id",
        required=True,
        choices=[binding.secret_id for binding in all_secret_bindings()],
    )
    unset_parser.set_defaults(func=command_unset)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except SecureConfigError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
