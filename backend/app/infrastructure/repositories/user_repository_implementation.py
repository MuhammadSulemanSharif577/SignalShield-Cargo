
from sqlalchemy.orm import Session

from app.domain.authentication.entities.user import User
from app.domain.authentication.interfaces.user_repository import UserRepository
from app.infrastructure.database.models.user_model import UserModel


class SQLAlchemyUserRepository(UserRepository):

    def __init__(self, db: Session):
        self.db = db

    def create(self, user: User) -> User:

        db_user = UserModel(
            full_name=user.full_name,
            email=user.email,
            hashed_password=user.hashed_password,
            is_active=user.is_active
        )

        try:
            self.db.add(db_user)
            self.db.commit()
            self.db.refresh(db_user)

            return self._to_entity(db_user)

        except Exception:
            self.db.rollback()
            raise

    def get_by_email(self, email: str) -> User | None:

        db_user = (
            self.db.query(UserModel)
            .filter(UserModel.email == email)
            .first()
        )

        if db_user is None:
            return None

        return self._to_entity(db_user)

    def get_by_id(self, user_id: int) -> User | None:

        db_user = self.db.get(UserModel, user_id)

        if db_user is None:
            return None

        return self._to_entity(db_user)

    @staticmethod
    def _to_entity(db_user: UserModel) -> User:

        return User(
            id=db_user.id,
            full_name=db_user.full_name,
            email=db_user.email,
            hashed_password=db_user.hashed_password,
            is_active=db_user.is_active,
            created_at=db_user.created_at
        )
