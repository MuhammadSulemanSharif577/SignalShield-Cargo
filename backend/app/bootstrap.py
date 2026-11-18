"""Create the first administrator without exposing a public registration endpoint."""

import argparse
import getpass
from uuid import uuid4

from pydantic import TypeAdapter, EmailStr

from app.application.authentication.use_cases.access_service import validate_password
from app.core.security import hash_password
from app.domain.authentication.entities.access import Role
from app.domain.authentication.entities.user import User
from app.domain.authentication.permissions import PERMISSIONS
from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.repositories.access_repository_implementation import SQLAlchemyAccessRepository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    email = str(TypeAdapter(EmailStr).validate_python(args.email.strip())).lower()
    name = args.name.strip()
    if len(name) < 2 or len(name) > 150:
        parser.error("Name must be 2–150 characters.")
    password = getpass.getpass("Administrator password: ")
    validate_password(password)
    if password != getpass.getpass("Confirm password: "):
        parser.error("Passwords do not match.")
    with SessionLocal() as db:
        repository = SQLAlchemyAccessRepository(db)
        if any(user.role_ids for user in repository.list_users() if not user.driver_id):
            parser.error("Access management has already been initialized.")
        role = Role(str(uuid4()), "Administrator", "Built-in platform administrator",
                    sorted(PERMISSIONS), True, ["users:manage", "roles:manage"])
        repository.save_role(role)
        user = repository.get_by_email(email) or User(None, name, email, "")
        if user.driver_id:
            parser.error("This email belongs to a linked driver. Use a separate administrator email.")
        user.full_name, user.hashed_password = name, hash_password(password)
        user.status, user.role_ids = "active", [role.id]
        user.failed_logins, user.locked_until = 0, None
        repository.save_user(user)
        repository.commit()
    print("Administrator created.")


if __name__ == "__main__":
    main()
