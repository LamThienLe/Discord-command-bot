from __future__ import annotations

import argparse
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials


SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Google OAuth login to save a token for a Discord user.")
    parser.add_argument("--discord-user-id", required=True, type=int, help="Your Discord user ID")
    parser.add_argument(
        "--client-secrets",
        default="credentials.json",
        help="Path to OAuth client secrets JSON downloaded from Google Cloud",
    )
    args = parser.parse_args()

    flow = InstalledAppFlow.from_client_secrets_file(args.client_secrets, SCOPES)
    creds: Credentials = flow.run_local_server(port=0)

    # Save token to app/tokens/<discord_user_id>.json so the bot can use it
    tokens_dir = Path(__file__).resolve().parents[1] / "app" / "tokens"
    tokens_dir.mkdir(exist_ok=True)
    token_path = tokens_dir / f"{args.discord_user_id}.json"
    token_path.write_text(creds.to_json())
    print(f"Saved token for Discord user {args.discord_user_id} at {token_path}")


if __name__ == "__main__":
    main()


