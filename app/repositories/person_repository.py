from sqlalchemy.orm import Session
from app.models.person import Person


def create(db: Session, person_data: dict):
    person = Person(**person_data)
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


def get_by_id(db: Session, person_id: int):
    return db.query(Person).filter(Person.id == person_id).first()


def get_all(db: Session, type: str = None):
    query = db.query(Person)
    
    if type:
        query = query.filter(Person.type == type)
    
    return query.all()
