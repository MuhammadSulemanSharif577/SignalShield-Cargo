
from app.domain.authentication.entities.user import User
from app.domain.authentication.interfaces.user_repository import UserRepository
from app.core.security import hash_password


class RegisterUser:

    def __init__(self, repository: UserRepository):
        self.repository = repository

    def execute(
        self,
        full_name: str,
        email: str,
        password: str
    ) -> User:

        email = email.strip().lower()

        existing_user = self.repository.get_by_email(email)

        if existing_user:
            raise ValueError("Email is already registered.")

        user = User(
            id=None,
            full_name=full_name.strip(),
            email=email,
            hashed_password=hash_password(password)
        )

        return self.repository.create(user)
