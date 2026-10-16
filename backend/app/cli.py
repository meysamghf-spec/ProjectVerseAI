"""Operator commands. Passwords are read from the environment, never from argv.

    CREATE_USER_EMAIL=a@b.com CREATE_USER_PASSWORD='...' CREATE_USER_ROLE=admin python -m app.cli create-user
"""

from __future__ import annotations

import os
import sys

from app.auth import create_user
from app.db import get_sessionmaker


def main(argv: list[str]) -> int:
    if argv[:1] != ["create-user"]:
        print(__doc__, file=sys.stderr)
        return 2
    email = os.environ.get("CREATE_USER_EMAIL", "")
    password = os.environ.get("CREATE_USER_PASSWORD", "")
    role = os.environ.get("CREATE_USER_ROLE", "user")
    session = get_sessionmaker()()
    try:
        user = create_user(session, email, password, role=role)
    except (ValueError, LookupError) as exc:
        print(f"Not created: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()
    print(f"Created {user.role} account {user.email}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
