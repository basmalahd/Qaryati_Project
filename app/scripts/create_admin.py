"""Create (or promote) an admin user.

    docker compose exec api python -m app.scripts.create_admin --email you@example.com --name "Your Name"

The password is prompted interactively so it doesn't end up in shell history.
"""
import argparse
import getpass
import sys

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import Role, User
from app.repositories.user_repository import UserRepository


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--password", help="optional; prompted if omitted")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Password (min 8 chars): ")
    if len(password) < 8:
        print("Password must be at least 8 characters", file=sys.stderr)
        return 1

    with SessionLocal() as db:
        repo = UserRepository(db)
        email = args.email.lower()
        user = repo.get_by_email(email)
        if user:
            user.role = Role.ADMIN.value
            print(f"Existing user {email} promoted to admin")
        else:
            repo.add(User(email=email, full_name=args.name,
                          hashed_password=hash_password(password), role=Role.ADMIN.value))
            print(f"Admin {email} created")
        db.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
