from dataclasses import asdict
from uuid import uuid4

from sqlalchemy import delete, func, insert, select

from app.core.time import aware, utcnow
from app.domain.authentication.entities.access import AccessSession, Role
from app.domain.authentication.entities.user import User
from app.infrastructure.database.models.access_model import (
    RoleModel, SessionModel, user_roles,
)
from app.infrastructure.database.models.user_model import UserModel
from app.infrastructure.database.models.dashboard_model import ActivityModel
from app.infrastructure.repositories.user_repository_implementation import SQLAlchemyUserRepository


class SQLAlchemyAccessRepository(SQLAlchemyUserRepository):
    def commit(self):
        self.db.commit()

    def lock_user(self, user_id: int) -> User | None:
        model = self.db.scalar(select(UserModel).where(UserModel.id == user_id).with_for_update()
                               .execution_options(populate_existing=True))
        return self._to_entity(model) if model else None

    def list_users(self) -> list[User]:
        return [self._to_entity(model) for model in self.db.scalars(select(UserModel).order_by(UserModel.id))]

    def save_user(self, user: User) -> User:
        model = self.db.get(UserModel, user.id) if user.id else UserModel()
        for key in ("full_name", "email", "hashed_password", "status",
                    "last_login", "failed_logins", "locked_until"):
            setattr(model, key, getattr(user, key))
        model.is_active = user.status == "active"
        self.db.add(model)
        self.db.flush()
        user.id = model.id
        self.db.execute(delete(user_roles).where(user_roles.c.user_id == user.id))
        if user.role_ids:
            self.db.execute(insert(user_roles), [
                {"user_id": user.id, "role_id": role_id} for role_id in sorted(set(user.role_ids))
            ])
        return user

    def _role(self, model: RoleModel) -> Role:
        count = self.db.scalar(select(func.count()).select_from(user_roles).where(user_roles.c.role_id == model.id))
        return Role(model.id, model.name, model.description, model.permissions,
                    model.built_in, model.locked_permissions, count)

    def list_roles(self) -> list[Role]:
        return [self._role(model) for model in self.db.scalars(select(RoleModel).order_by(RoleModel.name))]

    def get_role(self, role_id: str, lock: bool = False) -> Role | None:
        query = select(RoleModel).where(RoleModel.id == role_id)
        model = self.db.scalar(query.with_for_update() if lock else query)
        return self._role(model) if model else None

    def save_role(self, role: Role) -> Role:
        model = self.db.get(RoleModel, role.id) or RoleModel(id=role.id)
        for key in ("name", "description", "permissions", "built_in", "locked_permissions"):
            setattr(model, key, getattr(role, key))
        model.name_key = role.name.casefold()
        self.db.add(model)
        self.db.flush()
        return role

    def delete_role(self, role_id: str):
        self.db.execute(delete(RoleModel).where(RoleModel.id == role_id))

    def add_session(self, session: AccessSession):
        self.db.add(SessionModel(**asdict(session)))

    def get_session(self, token_hash: str) -> AccessSession | None:
        model = self.db.get(SessionModel, token_hash)
        if model is None or aware(model.expires_at) <= utcnow():
            return None
        return AccessSession(model.token_hash, model.user_id, aware(model.expires_at))

    def consume_session(self, token_hash: str) -> bool:
        return self.db.execute(delete(SessionModel).where(
            SessionModel.token_hash == token_hash, SessionModel.expires_at > utcnow()
        )).rowcount == 1

    def revoke_user_sessions(self, user_id: int):
        self.db.execute(delete(SessionModel).where(SessionModel.user_id == user_id))

    def record_activity(self, actor: str, text: str):
        self.db.add(ActivityModel(id=str(uuid4()), at=utcnow(), actor=actor, text=text, kind="user"))
