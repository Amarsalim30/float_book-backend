from sqlalchemy.orm import Session
from app.models.person import Person
from app.repositories import person_repository, tracked_account_repository
from app.schemas.person import PersonCreate, PersonList, PersonResponse, PositionSummary


def _build_person_response(db: Session, person: Person) -> PersonResponse:
    tracked_summary = None
    if person.tracked_account:
        balance = tracked_account_repository.get_balance(
            db, person.tracked_account.business_id, person.tracked_account.id
        )
        tracked_summary = PositionSummary(
            account_id=person.tracked_account.id,
            balance=balance,
        )

    held_summary = None
    if person.held_account:
        balance = tracked_account_repository.get_balance(
            db, person.held_account.business_id, person.held_account.id
        )
        held_summary = PositionSummary(
            account_id=person.held_account.id,
            balance=balance,
        )

    return PersonResponse(
        id=person.id,
        name=person.name,
        phone=person.phone,
        type=person.type,
        notes=person.notes,
        created_at=person.created_at,
        money_i_track=tracked_summary,
        money_held=held_summary,
    )


def create(db: Session, request: PersonCreate) -> PersonResponse:
    person_data = {
        "name": request.name,
        "phone": request.phone,
        "type": request.type,
        "notes": request.notes,
        "created_by": 1,  # TODO: Get from auth
    }

    person = person_repository.create(db, person_data)
    return _build_person_response(db, person)


def get_all(db: Session, type: str = None) -> PersonList:
    people = person_repository.get_all(db, type)
    items = [_build_person_response(db, p) for p in people]

    return PersonList(
        items=items,
        total=len(items),
    )


def get_by_id(db: Session, person_id: int) -> PersonResponse | None:
    person = person_repository.get_by_id(db, person_id)
    if not person:
        return None
    return _build_person_response(db, person)

