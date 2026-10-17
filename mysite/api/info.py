from fastapi import APIRouter, Depends, File as FastFile, Form, HTTPException, UploadFile
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy_file import File

from mysite.db.db import SessionLocal  # поправьте под ваш проект
from mysite.db.model import Info, UserRole
from mysite.db.schema import InfoOut, InfoUpdate, MessageOut  # поправьте путь

router = APIRouter(prefix="/info", tags=["info"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_or_404(db: Session, info_id: int) -> Info:
    obj = db.get(Info, info_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return obj


def make_file(upload: UploadFile) -> File:
    return File(
        content=upload.file.read(),
        filename=upload.filename,
        content_type=upload.content_type,
    )


@router.get("/", response_model=list[InfoOut])
def get_all(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return db.scalars(select(Info).offset(skip).limit(limit)).all()


@router.get("/{info_id}", response_model=InfoOut)
def get_one(info_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, info_id)

@router.post("/", response_model=MessageOut, status_code=201)
def create(
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(..., min_length=8),
    role: UserRole = Form(UserRole.JUNIOR),
    resume: UploadFile | None = FastFile(None),
    db: Session = Depends(get_db),
):
    if db.scalar(select(Info).where(Info.email == email)):
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

    obj = Info(
        full_name=full_name,
        email=email,
        password=pwd_context.hash(password),
        role=role.value,
        resume=make_file(resume) if resume else None,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return MessageOut(message="Пользователь добавлен", data=obj)


@router.patch("/{info_id}", response_model=MessageOut)
def update(info_id: int, data: InfoUpdate, db: Session = Depends(get_db)):
    obj = get_or_404(db, info_id)
    changes = data.model_dump(exclude_unset=True)

    if "email" in changes and changes["email"] != obj.email:
        if db.scalar(select(Info).where(Info.email == changes["email"])):
            raise HTTPException(status_code=400, detail="Email уже занят")

    if "password" in changes:
        changes["password"] = pwd_context.hash(changes["password"])
    if "role" in changes:
        changes["role"] = changes["role"].value

    for field, value in changes.items():
        setattr(obj, field, value)

    db.commit()
    db.refresh(obj)
    return MessageOut(message="Пользователь изменён", data=obj)


@router.put("/{info_id}/resume", response_model=MessageOut)
def update_resume(
    info_id: int,
    resume: UploadFile = FastFile(...),
    db: Session = Depends(get_db),
):
    obj = get_or_404(db, info_id)
    obj.resume = make_file(resume)
    db.commit()
    db.refresh(obj)
    return MessageOut(message="Резюме изменено", data=obj)


@router.delete("/{info_id}", response_model=MessageOut)
def delete(info_id: int, db: Session = Depends(get_db)):
    obj = get_or_404(db, info_id)
    db.delete(obj)
    db.commit()
    return MessageOut(message="Пользователь удалён")