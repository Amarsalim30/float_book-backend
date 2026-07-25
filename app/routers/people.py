from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.person import PersonCreate, PersonResponse, PersonList
from app.services import people_service

router = APIRouter(prefix="/people", tags=["People"])


@router.post("/", response_model=PersonResponse, status_code=status.HTTP_201_CREATED)
def create_person(request: PersonCreate, db: Session = Depends(get_db)):
    return people_service.create(db, request)


@router.get("/", response_model=PersonList)
def get_people(type: str = None, db: Session = Depends(get_db)):
    return people_service.get_all(db, type)


@router.get("/{id}", response_model=PersonResponse)
def get_person(id: int, db: Session = Depends(get_db)):
    person = people_service.get_by_id(db, id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found"
        )
    return person
