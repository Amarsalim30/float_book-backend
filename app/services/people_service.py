from sqlalchemy.orm import Session
from app.repositories import person_repository
from app.schemas.person import PersonCreate, PersonResponse, PersonList


def create(db: Session, request: PersonCreate) -> PersonResponse:
    person_data = {
        "name": request.name,
        "phone": request.phone,
        "type": request.type,
        "notes": request.notes,
        "created_by": 1  # TODO: Get from auth
    }
    
    person = person_repository.create(db, person_data)
    return person


def get_all(db: Session, type: str = None) -> PersonList:
    items = person_repository.get_all(db, type)
    
    return PersonList(
        items=items,
        total=len(items)
    )


def get_by_id(db: Session, person_id: int) -> PersonResponse:
    return person_repository.get_by_id(db, person_id)
