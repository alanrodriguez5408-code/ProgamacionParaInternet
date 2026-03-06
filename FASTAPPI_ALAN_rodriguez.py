from datetime import datetime, timedelta, timezone, date
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from sqlalchemy import create_engine, ForeignKey, String, Integer
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column, relationship, Session
import jwt
from passlib.context import CryptContext

SQLALCHEMY_DATABASE_URL = "sqlite:///./biblioteca_avanzada.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase): pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

SECRET_KEY = "super_secreto_para_desarrollo_cambiar_en_produccion"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    reading_history: Mapped[List["ReadHistory"]] = relationship(back_populates="user")

class Book(Base):
    __tablename__ = "books"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    genre: Mapped[str] = mapped_column(String(50), index=True)

class ReadHistory(Base):
    __tablename__ = "read_history"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    read_date: Mapped[date] = mapped_column(default=date.today)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"))
    
    user: Mapped["User"] = relationship(back_populates="reading_history")
    book: Mapped["Book"] = relationship()

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)

class BookCreate(BaseModel):
    title: str = Field(max_length=200)
    genre: str = Field(max_length=50)

class BookResponse(BookCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

def get_suggestions_for_user(db: Session, user_id: int):
    
    history = db.query(ReadHistory).filter(ReadHistory.user_id == user_id).all()
    if not history:
        return [] 
    
    read_book_ids = [h.book_id for h in history]
    
    read_books = db.query(Book).filter(Book.id.in_(read_book_ids)).all()
    favorite_genres = list(set([book.genre for book in read_books]))
    
    suggestions = db.query(Book).filter(
        Book.genre.in_(favorite_genres),
        ~Book.id.in_(read_book_ids)
    ).limit(5).all()
    
    return suggestions



Base.metadata.create_all(bind=engine)

app = FastAPI(title="Biblioteca API", version="1.0.0")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detalle": "Error de validación", "errores": exc.errors()},
    )

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None: raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception
    
    user = get_user_by_email(db, email=email)
    if user is None: raise credentials_exception
    return user

@app.post("/register", response_model=UserCreate)
def register(user: UserCreate, db: Session = Depends(get_db)):
    if get_user_by_email(db, email=user.email):
        raise HTTPException(status_code=400, detail="El email ya existe")
    db_user = User(email=user.email, hashed_password=get_password_hash(user.password))
    db.add(db_user)
    db.commit()
    return db_user

@app.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = get_user_by_email(db, email=form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/books/", response_model=BookResponse)
def create_book(book: BookCreate, db: Session = Depends(get_db)):
    db_book = Book(title=book.title, genre=book.genre)
    db.add(db_book)
    db.commit()
    db.refresh(db_book)
    return db_book

@app.post("/users/me/read/{book_id}")
def read_book(book_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    history = ReadHistory(user_id=current_user.id, book_id=book_id)
    db.add(history)
    db.commit()
    return {"message": "Libro añadido al historial"}

@app.get("/users/me/suggestions", response_model=List[BookResponse])
def get_suggestions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_suggestions_for_user(db, current_user.id)
import uvicorn

if __name__ == "__main__":
    uvicorn.run("FASTAPPI_ALAN_rodriguez:app", host="127.0.0.1", port=8000, reload=True)