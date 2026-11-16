
from app.domain.authentication.interfaces.user_repository import UserRepository
from app.core.security import verify_password


class LoginUser:

    def __init__(self, repository: UserRepository):
        self.repository = repository

    def execute(
        self,
        identifier: str,
        password: str
    ):

        email = identifier.strip().lower()

        user = self.repository.get_by_email(email)

        if user is None:
            raise ValueError("Invalid email or password.")

        if not verify_password(
            password,
            user.hashed_password
        ):
            raise ValueError("Invalid email or password.")

        if not user.is_active:
            raise ValueError("This account is inactive.")

        return user
