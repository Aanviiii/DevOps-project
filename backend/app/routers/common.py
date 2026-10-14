from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..core.database import Base


def get_or_404[ModelT: Base](db: Session, model: type[ModelT], entity_id: int) -> ModelT:
    entity = db.get(model, entity_id)
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{model.__name__} {entity_id} not found")
    return entity
