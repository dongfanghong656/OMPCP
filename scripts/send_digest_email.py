#!/usr/bin/env python
import argparse
import smtplib
from email.message import EmailMessage
from pathlib import Path

from secure_config import load_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--digest", required=True)
    args = parser.parse_args()

    config = load_json(Path(args.config))
    email_cfg = config["delivery"]["email"]
    if not email_cfg["send_enabled"]:
        raise SystemExit("Email delivery is disabled in config.json")

    digest_path = Path(args.digest)
    msg = EmailMessage()
    msg["Subject"] = f"{email_cfg['subject_prefix']} {digest_path.stem}"
    msg["From"] = email_cfg["sender"]
    msg["To"] = ", ".join(email_cfg["recipients"])
    msg.set_content(digest_path.read_text(encoding="utf-8"))

    if email_cfg["tls_mode"] == "ssl":
        server = smtplib.SMTP_SSL(email_cfg["smtp_server"], email_cfg["smtp_port"])
    else:
        server = smtplib.SMTP(email_cfg["smtp_server"], email_cfg["smtp_port"])
        server.starttls()

    with server:
        if email_cfg["smtp_user"]:
            server.login(email_cfg["smtp_user"], email_cfg["smtp_pass"])
        server.send_message(msg)
    print(f"Sent {digest_path}")


if __name__ == "__main__":
    main()
