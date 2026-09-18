from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Alarm, MachineModel, MaintenanceCase, Part, User
from app.schemas import AlarmOut, CaseOut, MachineOut, PartOut

router = APIRouter(tags=["产品与知识"])


@router.get("/products", response_model=list[MachineOut])
def products(
    query: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    statement = select(MachineModel).options(selectinload(MachineModel.series)).order_by(MachineModel.code)
    if query:
        statement = statement.where(
            or_(MachineModel.code.ilike(f"%{query}%"), MachineModel.name.ilike(f"%{query}%"))
        )
    return db.scalars(statement).all()


@router.get("/products/{code}", response_model=MachineOut)
def product_detail(
    code: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    machine = db.scalar(
        select(MachineModel)
        .options(selectinload(MachineModel.series))
        .where(MachineModel.code == code)
    )
    if not machine:
        raise HTTPException(status_code=404, detail="未找到机型")
    return machine


@router.get("/alarms", response_model=list[AlarmOut])
def alarms(
    model_code: str | None = None,
    query: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    rows = db.scalars(select(Alarm).where(Alarm.review_status == "published").order_by(Alarm.code)).all()
    if model_code:
        rows = [row for row in rows if not row.applies_to or model_code in row.applies_to]
    if query:
        needle = query.lower()
        rows = [row for row in rows if needle in f"{row.code} {row.title} {row.system}".lower()]
    return rows


@router.get("/parts", response_model=list[PartOut])
def parts(
    model_code: str | None = None,
    query: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    rows = db.scalars(select(Part).where(Part.review_status == "published").order_by(Part.part_no)).all()
    if model_code:
        rows = [row for row in rows if not row.applies_to or model_code in row.applies_to]
    if query:
        needle = query.lower()
        rows = [row for row in rows if needle in f"{row.part_no} {row.name} {row.category}".lower()]
    return rows


@router.get("/cases", response_model=list[CaseOut])
def cases(
    model_code: str | None = None,
    query: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    statement = select(MaintenanceCase).where(MaintenanceCase.review_status == "published")
    if model_code:
        statement = statement.where(MaintenanceCase.model_code == model_code)
    if query:
        statement = statement.where(
            or_(
                MaintenanceCase.case_no.ilike(f"%{query}%"),
                MaintenanceCase.title.ilike(f"%{query}%"),
                MaintenanceCase.symptom.ilike(f"%{query}%"),
            )
        )
    return db.scalars(statement.order_by(MaintenanceCase.created_at.desc())).all()

