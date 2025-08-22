import os
import enum
from contextlib import asynccontextmanager
from datetime import timedelta, datetime, timezone
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy import (Column, Integer, String, Enum,
                        DECIMAL, TIMESTAMP, Text, ForeignKey,
                        UniqueConstraint, func, or_, select, text)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, relationship, DeclarativeBase, selectinload, aliased
from sqlalchemy.dialects.mysql import insert as mysql_insert
from dotenv import load_dotenv
from jose import JWTError, jwt
from sqlalchemy.future import select
import string
import random
from passlib.context import CryptContext
import google.generativeai as genai
import logging
from logging.config import dictConfig
from fastapi.concurrency import run_in_threadpool
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import time
from starlette.middleware.base import BaseHTTPMiddleware
from zoneinfo import ZoneInfo

load_dotenv()

scheduler = AsyncIOScheduler(timezone=ZoneInfo("Asia/Tashkent"))

DATABASE_URL = os.getenv("DATABASE")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE"))
genai.configure(api_key=os.getenv("API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Приложение запускается...")
    scheduler.start()
    yield
    print("Приложение останавливается...")
    scheduler.shutdown()
    await engine.dispose()

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "fmt": "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
    },
    "loggers": {
        "uvicorn.error": {"handlers": ["default"], "level": "INFO"},
        "uvicorn.access": {"handlers": ["default"], "level": "INFO"},
    },
}

dictConfig(LOGGING_CONFIG)

LOG_FILE_PATH = "/var/log/uvicorn/access.log"

app = FastAPI(title="Hotel Service API", docs_url=None, redoc_url=None)

class Fail2BanLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        if 400 <= response.status_code < 600:
            log_message = (
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - FAIL2BAN_ATTEMPT: "
            f"IP={request.client.host} "
            f'"{request.method} {request.url.path}" '
            f"Status={response.status_code}\n"

            )

            try:
                with open(LOG_FILE_PATH, "a") as log_file:
                    log_file.write(log_message)
            except Exception as e:
                print(f"ERROR while writing to log_file {e} !!!")

        return response

app.add_middleware(Fail2BanLoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Заменить на домен фронтенда. Пример ["http://my-hotel-app.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
engine = create_async_engine(DATABASE_URL)
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
oauth2 = OAuth2PasswordBearer(tokenUrl="auth/verify-code")
crypt = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def get_db():
    async with async_session_maker() as session:
        yield session

# JWT токен
def access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    
    if expires_delta: 
        expire = datetime.now(timezone.utc) + expires_delta
    else: 
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt

# Модели SQLAlchemy
class Base(DeclarativeBase): 
    pass

class LanguageCodeEnum(str, enum.Enum):
    ru = "ru"
    en = "en"
    uz = "uz"

class Token(BaseModel):
    access_token: str
    token_type: str

class UserStatusEnum(str, enum.Enum):
    active = "active"
    archived = "archived"

class EmployeeRoleEnum(str, enum.Enum):
    admin = "admin"
    reception = "reception"
    manager = "manager"

class EmployeeLoginRequest(BaseModel):
    username: str
    password: str

class EmployeeSchema(BaseModel):
    id: int
    first_name: str
    last_name: str
    patronymic: Optional[str] = None
    username: str
    role: EmployeeRoleEnum
    salary: Optional[float] = None
    status: UserStatusEnum
    class Config:
        from_attributes = True

class EmployeeCreate(BaseModel):
    first_name: str
    last_name: str
    patronymic: Optional[str] = None
    username: str
    role: EmployeeRoleEnum
    password: str
    salary: Optional[float] = None

class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    patronymic: Optional[str] = None
    username: Optional[str] = None
    role: Optional[EmployeeRoleEnum] = None
    salary: Optional[float] = None
    status: Optional[UserStatusEnum] = None

class RoomStatusEnum(str, enum.Enum):
    available = "available"
    occupied = "occupied"
    maintenance = "maintenance"

class RoomTypeTranslationSchema(BaseModel):
    language_code: LanguageCodeEnum
    name: str

    class Config:
        from_attributes = True 

class RoomTypeCreate(BaseModel):
    code: str
    translations: List[RoomTypeTranslationSchema]

class RoomTypeSchema(BaseModel):
    id: int
    code: str
    translations: List[RoomTypeTranslationSchema]

    class Config:
        from_attributes = True

class RoomSchema(BaseModel):
    id: int
    room_number: str
    status: RoomStatusEnum
    current_price_per_night: float
    room_type: RoomTypeSchema

    class Config:
        from_attributes = True

class RoomCreate(BaseModel):
    room_number: str
    room_type_id: int
    current_price_per_night: float

class RoomUpdate(BaseModel):
    room_number: Optional[str] = None
    room_type_id: Optional[int] = None
    current_price_per_night: Optional[float] = None
    status: Optional[RoomStatusEnum] = None

class BookingStatusEnum(str, enum.Enum):
    confirmed = "confirmed"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"
    
class BookingUpdate(BaseModel):
    status: Optional[BookingStatusEnum] = None
    check_out_date: Optional[datetime] = None

class UserInBookingSchema(BaseModel):
    id: int
    first_name: str
    last_name: str
    patronymic: Optional[str] = None
    phone_number: str
    check_out_date: Optional[str] = None

    class Config:
        from_attributes = True

class RoomInBookingSchema(BaseModel):
    id: int
    room_number: str
    class Config:
        from_attributes = True

class EmployeeInBookingSchema(BaseModel):
    id: int
    first_name: str
    last_name: str
    patronymic: Optional[str] = None
    class Config:
        from_attributes = True

class BookingSchema(BaseModel):
    id: int
    check_in_date: datetime
    check_out_date: datetime
    price_per_night: float
    status: BookingStatusEnum
    user: UserInBookingSchema
    room: RoomInBookingSchema
    employee: EmployeeInBookingSchema
    reception_chat_id: Optional[int] = None

    class Config:
        from_attributes = True


class GetUserSchema(BaseModel):
    booking_id: int
    booking_status: BookingStatusEnum
    generated_password: Optional[str] = None
    user_id: int
    user_status: UserStatusEnum
    first_name: str
    last_name: str
    patronymic: Optional[str] = None
    phone_number: str
    check_out_date: Optional[str] = None
    
    class Config:
        from_attributes = True


class BookingCreate(BaseModel):
    user_id: int
    room_id: int
    check_in_date: datetime
    check_out_date: datetime

class ServiceStatusEnum(str, enum.Enum):
    available = "available"
    archived = "archived"

class ServiceRequestStatusEnum(str, enum.Enum):
    requested = "requested"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"

class ServiceTranslationSchema(BaseModel):
    language_code: LanguageCodeEnum
    name: str
    description: Optional[str]

    class Config:
        from_attributes = True

class ServiceSchema(BaseModel):
    id: int
    price: float
    translations: List[ServiceTranslationSchema]

    class Config:
        from_attributes = True

class ServiceRequestCreate(BaseModel):
    booking_id: int
    service_id: int

class ServiceRequestSchema(BaseModel):
    id: int
    status: ServiceRequestStatusEnum
    price: float
    created_at: datetime
    service: ServiceSchema
    
    class Config:
        from_attributes = True

class ServiceRequestStatusUpdate(BaseModel):
    status: ServiceRequestStatusEnum

class ServiceRequestForEmployeeSchema(BaseModel):
    id: int
    status: ServiceRequestStatusEnum
    price: float
    created_at: datetime
    service: ServiceSchema
    booking: BookingSchema

    class Config:
        from_attributes = True

class ChatTypeEnum(str, enum.Enum):
    AI = "AI"
    RECEPTION = "RECEPTION"

class ChatStatusEnum(str, enum.Enum):
    open = "open"
    claimed = "claimed"
    closed = "closed"

class SenderInfo(BaseModel):
    id: int
    first_name: str
    last_name: str
    patronymic: Optional[str] = None
    type: str # "user" или "employee"

class MessageSchema(BaseModel):
    id: int
    content: str
    created_at: datetime
    sender: Optional[SenderInfo] = None
    
    class Config:
        from_attributes = True

class SenderTypeEnum(str, enum.Enum):
    user = "user"
    employee = "employee"
    ai = "ai"

class ChatSchema(BaseModel):
    id: int
    type: ChatTypeEnum
    booking: BookingSchema
    messages: List[MessageSchema]

    class Config:
        from_attributes = True

class MessageCreate(BaseModel):
    content: str

class ChatTypeRequest(BaseModel):
    type: ChatTypeEnum

class ChatClaimResponse(BaseModel):
    id: int
    status: ChatStatusEnum
    assigned_employee_id: int

class LastMessageSchema(BaseModel):
    content: str
    created_at: datetime
    sender_type: SenderTypeEnum

    class Config:
        from_attributes = True

class ChatForReceptionSchema(BaseModel):
    id: int
    user: UserInBookingSchema
    last_message: Optional[LastMessageSchema] = None

    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    first_name: str
    last_name: str
    patronymic: Optional[str] = None
    phone_number: str

    room_id: Optional[int] = None
    check_in_date: Optional[datetime] = None
    check_out_date: Optional[datetime] = None

class RoomForDashboardSchema(BaseModel):
    id: int
    room_number: str
    status: RoomStatusEnum
    current_price_per_night: float
    room_type: RoomTypeSchema
    
    current_booking: Optional[BookingSchema] = None

    class Config:
        from_attributes = True

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)    
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    patronymic = Column(String(100), nullable=True)
    phone_number = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=True)
    status = Column(Enum(UserStatusEnum), nullable=False, default=UserStatusEnum.active)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    archived_at = Column(TIMESTAMP, nullable=True)
    
    bookings = relationship("Booking", back_populates="user")

class UserLoginRequest(BaseModel):
    phone_number: str
    password: str

class Employee(Base):
    __tablename__ = 'employees'
    id = Column(Integer, primary_key=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    patronymic = Column(String(100), nullable=True)
    username = Column(String(100), unique=True, nullable=False)
    role = Column(Enum(EmployeeRoleEnum), nullable=False)
    password_hash = Column(String(255), nullable=False)
    salary = Column(DECIMAL(10, 2), nullable=True)
    status = Column(Enum(UserStatusEnum), nullable=False, default=UserStatusEnum.active)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    archived_at = Column(TIMESTAMP, nullable=True)

    bookings = relationship("Booking", back_populates="employee")

class RoomType(Base):
    __tablename__ = 'room_types'
    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    
    rooms = relationship("Room", back_populates="room_type")
    translations = relationship("RoomTypeTranslation", back_populates="room_type")

class RoomTypeTranslation(Base):
    __tablename__ = 'room_type_translations'
    room_type_id = Column(Integer, ForeignKey('room_types.id', ondelete="CASCADE"), primary_key=True)
    language_code = Column(Enum(LanguageCodeEnum), primary_key=True)
    name = Column(String(255), nullable=False)

    room_type = relationship("RoomType", back_populates="translations")

class Room(Base):
    __tablename__ = 'rooms'
    id = Column(Integer, primary_key=True)
    room_number = Column(String(10), nullable=False)
    room_type_id = Column(Integer, ForeignKey('room_types.id'), nullable=False)
    status = Column(Enum(RoomStatusEnum), nullable=False, default=RoomStatusEnum.available)
    current_price_per_night = Column(DECIMAL(10, 2), nullable=False)
    
    room_type = relationship("RoomType", back_populates="rooms")
    bookings = relationship("Booking", back_populates="room")

class Booking(Base):
    __tablename__ = 'bookings'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    room_id = Column(Integer, ForeignKey('rooms.id'), nullable=False)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    price_per_night = Column(DECIMAL(10, 2), nullable=False)
    check_in_date = Column(TIMESTAMP, nullable=False)
    check_out_date = Column(TIMESTAMP, nullable=False)
    status = Column(Enum(BookingStatusEnum), nullable=False, default=BookingStatusEnum.confirmed)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    
    user = relationship("User", back_populates="bookings")
    room = relationship("Room", back_populates="bookings")
    employee = relationship("Employee", back_populates="bookings")
    service_requests = relationship("ServiceRequest", back_populates="booking")
    
class Service(Base):
    __tablename__ = 'services'
    id = Column(Integer, primary_key=True)
    price = Column(DECIMAL(10, 2), nullable=False)
    status = Column(Enum(ServiceStatusEnum), nullable=False, default=ServiceStatusEnum.available)
    archived_at = Column(TIMESTAMP, nullable=True)

    translations = relationship("ServiceTranslation", back_populates="service")

class ServiceTranslation(Base):
    __tablename__ = 'service_translations'
    service_id = Column(Integer, ForeignKey('services.id', ondelete="CASCADE"), primary_key=True)
    language_code = Column(Enum(LanguageCodeEnum), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    service = relationship("Service", back_populates="translations")

class ServiceRequest(Base):
    __tablename__ = 'service_requests'
    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey('bookings.id', ondelete="CASCADE"), nullable=False)
    service_id = Column(Integer, ForeignKey('services.id'), nullable=False)
    price = Column(DECIMAL(10, 2), nullable=False)
    assigned_employee_id = Column(Integer, ForeignKey('employees.id'), nullable=True)
    status = Column(Enum(ServiceRequestStatusEnum), nullable=False, default=ServiceRequestStatusEnum.requested)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    
    
    booking = relationship("Booking", back_populates="service_requests")
    service = relationship("Service")
    assigned_employee = relationship("Employee")

class Chat(Base):
    __tablename__ = 'chats'
    id = Column(Integer, primary_key=True)
    # user_id = Column(Integer, ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    booking_id = Column(Integer, ForeignKey('bookings.id', ondelete="CASCADE"), nullable=False)
    booking = relationship("Booking")
    type = Column(Enum(ChatTypeEnum), nullable=False)
    status = Column(Enum(ChatStatusEnum), nullable=False, default=ChatStatusEnum.open)
    assigned_employee_id = Column(Integer, ForeignKey('employees.id'), nullable=True)
    
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    messages = relationship("Message", back_populates="chat")
    
    assigned_employee = relationship("Employee", foreign_keys=[assigned_employee_id])

class BookingInfoForChat(BaseModel):
    id: int
    check_in_date: datetime
    user: UserInBookingSchema
    room: RoomInBookingSchema

    class Config:
        from_attributes = True

class ChatForReceptionSchema(BaseModel):
    id: int
    booking: BookingInfoForChat
    last_message: Optional[LastMessageSchema] = None

    class Config:
        from_attributes = True

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey('chats.id', ondelete="CASCADE"), nullable=False)
    sender_type = Column(Enum(SenderTypeEnum), nullable=False)
    sender_user_id = Column(Integer, ForeignKey('users.id', ondelete="CASCADE"), nullable=True)
    sender_employee_id = Column(Integer, ForeignKey('employees.id', ondelete="CASCADE"), nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    
    chat = relationship("Chat", back_populates="messages")
    sender_user = relationship("User")
    sender_employee = relationship("Employee")

class UserSchema(BaseModel):
    id: int
    first_name: str
    last_name: str
    patronymic: Optional[str] = None
    phone_number: str
    status: UserStatusEnum
    class Config:
        from_attributes = True

class UserBookingResponse(BaseModel):
    user: UserSchema
    booking: Optional[BookingSchema] = None
    generated_password: Optional[str] = None

class RateLimiter:
    def __init__(self, redis, key_prefix, limit, period, block_time):
        self.redis = redis
        self.key_prefix = key_prefix
        self.limit = limit
        self.period = period
        self.block_time = block_time

    async def _get_key(self, client_id):
        return f"{self.key_prefix}:{client_id}"

    async def check(self, client_id):
        key = await self._get_key(client_id)
        data = await self.redis.hgetall(key)
        
        if not data:
            return False, 0
        
        attempts = int(data.get(b'attempts', 0))
        last_attempt = float(data.get(b'last_attempt', 0))
        blocked_until = float(data.get(b'blocked_until', 0))
        
        current_time = datetime.now().timestamp()
        
        if blocked_until and current_time < blocked_until:
            return True, int(blocked_until - current_time)
        
        if last_attempt and current_time - last_attempt > self.period:
            await self.reset(client_id)
            return False, 0
            
        return attempts >= self.limit, 0

    async def increment(self, client_id):
        key = await self._get_key(client_id)
        current_time = datetime.now().timestamp()
        
        async with self.redis.pipeline() as pipe:
            pipe.hincrby(key, "attempts", 1)
            pipe.hset(key, "last_attempt", current_time)
            
            results = await pipe.execute()
        
        attempts = results[0]
        
        if attempts >= self.limit:
            async with self.redis.pipeline() as pipe:
                blocked_until = current_time + self.block_time
                pipe.hset(key, "blocked_until", blocked_until)
                pipe.expire(key, self.block_time)
                await pipe.execute()
        else:
            await self.redis.expire(key, self.period)


    async def reset(self, client_id):
        key = await self._get_key(client_id)
        await self.redis.delete(key)

# Получение текущего пользователя по токеу
async def get_current_user(token: str = Depends(oauth2), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if "role" in payload:
            raise credentials_exception
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await db.get(User, int(user_id))

    if user is None:
        raise credentials_exception

    return user

def verify_password(plain_password, hashed_password):
    return crypt.verify(plain_password, hashed_password)

def get_password_hash(password):
    return crypt.hash(password)

# Проверки роли сотрудника
def require_role(required_roles: List[EmployeeRoleEnum]):
    async def get_current_employee_with_role(
        token: str = Depends(oauth2),
        db: AsyncSession = Depends(get_db)
    ) -> Employee:
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            employee_id = payload.get("sub")
            employee_role_str = payload.get("role")

            if employee_id is None or employee_role_str is None:
                raise credentials_exception

            token_role = EmployeeRoleEnum(employee_role_str)
        except (JWTError, ValueError):
            raise credentials_exception
        
        if token_role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        
        employee = await db.get(Employee, int(employee_id))
        if not employee or employee.status != UserStatusEnum.active:
            raise credentials_exception
        
        return employee
    
    return get_current_employee_with_role

@app.get("/")
async def root():
    return {"message": "Welcome to the API!"}

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Приложение запускается...")
    yield
    print("Приложение останавливается...")
    await engine.dispose()

from redis.asyncio import Redis

redis_client = Redis.from_url("redis://localhost:6379/0")

login_rate_limiter = RateLimiter(
    redis=redis_client,
    key_prefix="login_attempt",
    limit=10,
    period=60,  # 1 минута
    block_time=180  # 3 минуты
)

@app.post("/auth/login", tags=["Auth"], response_model=Token)
async def login_for_user_access_token(
    form_data: UserLoginRequest, db: AsyncSession = Depends(get_db)
):
    client_id = f"{form_data.phone_number}"
    
    is_blocked, remaining = await login_rate_limiter.check(client_id)
    
    if is_blocked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Try again in {remaining} seconds"
        )

    query = select(User).where(User.phone_number == form_data.phone_number)
    user = (await db.execute(query)).scalar_one_or_none()

    if not user or not user.password_hash:
        await login_rate_limiter.increment(client_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect phone number or password"
        )

    if user.status != UserStatusEnum.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect phone number or password"
        )

    is_password_valid = (form_data.password == user.password_hash)
    
    if not is_password_valid:
        await login_rate_limiter.increment(client_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect phone number or password"
        )

    await login_rate_limiter.reset(client_id)

    access_token_expires = timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    access_token_value = access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )

    return {"access_token": access_token_value, "token_type": "bearer"}

@app.get("/user/profile", tags=["USer"], response_model=UserSchema)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

# Получение всех бронирований текущего пользователя
@app.get("/user/bookings", tags=["USer"], response_model=List[BookingSchema])
async def get_my_bookings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(Booking).options(
        selectinload(Booking.user),
        selectinload(Booking.room),
        selectinload(Booking.employee)
    ).where(Booking.user_id == current_user.id).order_by(Booking.check_in_date.desc())
    
    result = await db.execute(query)
    return result.scalars().all()

# Получение деталей конкретного бронирования пользователя
@app.get("/user/bookings/{booking_id}", tags=["USer"], response_model=BookingSchema)
async def get_my_booking_details(
    booking_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    query = select(Booking).options(
        selectinload(Booking.user),
        selectinload(Booking.room),
        selectinload(Booking.employee)
    ).where(
        Booking.id == booking_id,
        Booking.user_id == current_user.id
    )
    
    result = await db.execute(query)
    booking = result.scalar_one_or_none()
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found or you do not have permission to view it"
        )
        
    return booking

# Получение доступных сервисов для пользователя
@app.get("/user/services", tags=["USer"], response_model=List[ServiceSchema])
async def get_available_services(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(Service).options(
        selectinload(Service.translations)
    ).where(Service.status == ServiceStatusEnum.available)
    
    result = await db.execute(query)
    return result.scalars().all()

# Создание заявки на сервис (только для активного бронирования)
@app.post("/user/service-requests", tags=["USer"], response_model=ServiceRequestSchema, status_code=status.HTTP_200_OK)
async def create_service_request(
    request_data: ServiceRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    booking = await db.get(Booking, request_data.booking_id)
    if not booking or booking.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found or access denied")
    
    if booking.status != BookingStatusEnum.active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Services can only be ordered for an active booking")

    service = await db.get(Service, request_data.service_id)
    if not service or service.status != ServiceStatusEnum.available:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found or is unavailable")

    new_request = ServiceRequest(
        booking_id=booking.id,
        service_id=service.id,
        price=service.price
    )
    
    db.add(new_request)
    await db.commit()

    query = select(ServiceRequest).options(
        selectinload(ServiceRequest.service).selectinload(Service.translations)
    ).where(ServiceRequest.id == new_request.id)
    
    result = await db.execute(query)
    return result.scalar_one()

# Получение всех заявок пользователя на сервисы
@app.get("/user/service-requests", tags=["USer"], response_model=List[ServiceRequestSchema])
async def get_my_service_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    query = select(ServiceRequest).options(
        selectinload(ServiceRequest.service).selectinload(Service.translations)
    ).join(ServiceRequest.booking).where(Booking.user_id == current_user.id).order_by(ServiceRequest.created_at.desc())
    
    result = await db.execute(query)
    return result.scalars().all()

# Получение/создание чата пользователя с ресепшн или AI
@app.post("/user/chats", tags=["USer"], response_model=ChatSchema)
async def get_or_create_chat_with_reception(
    request_data: ChatTypeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    active_booking_query = select(Booking).where(
        Booking.user_id == current_user.id,
        or_(Booking.status == BookingStatusEnum.active, Booking.status == BookingStatusEnum.confirmed)
    ).order_by(Booking.created_at.desc()).limit(1)
    
    active_booking = (await db.execute(active_booking_query)).scalar_one_or_none()

    if not active_booking and request_data.type == ChatTypeEnum.RECEPTION:
         raise HTTPException(status_code=400, detail="No active booking found to create a reception chat.")

    chat = None

    if active_booking:
        query = select(Chat).where(
            Chat.booking_id == active_booking.id,
            Chat.type == request_data.type
        ).options(
            selectinload(Chat.booking).options(
                selectinload(Booking.user),
                selectinload(Booking.room),
                selectinload(Booking.employee)
            ),
            selectinload(Chat.messages).options(
                selectinload(Message.sender_user),
                selectinload(Message.sender_employee)
            )
        )
        result = await db.execute(query)
        chat = result.scalar_one_or_none()

    if not chat:
        if not active_booking:
             raise HTTPException(status_code=400, detail="A booking is required to create a new chat.")

        new_chat = Chat(booking_id=active_booking.id, type=request_data.type)
        db.add(new_chat)
        await db.commit()

        result = await db.execute(query)
        chat = result.scalar_one()

    messages_with_sender = []
    for msg in sorted(chat.messages, key=lambda m: m.created_at):
        sender_info = None
        
        if msg.sender_type == SenderTypeEnum.user and msg.sender_user:
            sender_info = SenderInfo(
                id=msg.sender_user.id, 
                first_name=msg.sender_user.first_name, 
                last_name=msg.sender_user.last_name,
                patronymic=msg.sender_user.patronymic,
                type="user"
          )
        elif msg.sender_type == SenderTypeEnum.employee and msg.sender_employee:
            sender_info = SenderInfo(
                id=msg.sender_employee.id, 
                first_name=msg.sender_employee.first_name, 
                last_name=msg.sender_employee.last_name,
                patronymic=msg.sender_employee.patronymic,
                type="employee"
            )
        elif msg.sender_type == SenderTypeEnum.ai:
            sender_info = SenderInfo(id=0, first_name="AI", last_name="Assistant", type="ai")
        
        messages_with_sender.append(MessageSchema(
            id=msg.id, content=msg.content, created_at=msg.created_at, sender=sender_info
        ))

    return ChatSchema(id=chat.id, type=chat.type, booking=chat.booking, messages=messages_with_sender)

# Отправка сообщения в чат от пользователя (и генерация ответа AI)
@app.post("/user/chats/{chat_id}/messages", tags=["USer"], response_model=MessageSchema)
async def send_message_as_user(
    chat_id: int,
    message_data: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(Chat).options(
        selectinload(Chat.booking)
    ).where(Chat.id == chat_id)
    
    result = await db.execute(query)
    chat = result.scalar_one_or_none()

    if not chat or chat.booking.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found or access denied")

    if chat.type == ChatTypeEnum.RECEPTION:
        chat.status = ChatStatusEnum.open
        chat.assigned_employee_id = None
        db.add(chat)

    user_message = Message(
        chat_id=chat_id,
        content=message_data.content,
        sender_type=SenderTypeEnum.user,
        sender_user_id=current_user.id
    )
    db.add(user_message)
    
    db.add(user_message)
    await db.commit()
    await db.refresh(user_message, attribute_names=['sender_user', 'id', 'created_at'])

    if chat.type == ChatTypeEnum.AI:
        try:
            response = await model.generate_content_async(message_data.content)
            ai_message_content = response.text
        except Exception as e:
            logging.error(f"AI generation failed for chat {chat_id}: {e}", exc_info=True)
            ai_message_content = "Произошла ошибка при обращении к ассистенту. Пожалуйста, попробуйте позже."

        ai_message = Message(
            chat_id=chat_id,
            content=ai_message_content,
            sender_type=SenderTypeEnum.ai
        )
        db.add(ai_message)
        await db.commit()        

    return MessageSchema(
        id=user_message.id,
        content=user_message.content,
        created_at=user_message.created_at,
        sender=SenderInfo(
            id=current_user.id,
            first_name=current_user.first_name,
            last_name=current_user.last_name,
            patronymic=current_user.patronymic,
            type="user"
        )
    )


@app.get("/user/chats/{chat_id}/messages", tags=["USer"], response_model=List[MessageSchema])
async def get_chat_messages(
    chat_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    since_id: Optional[int] = None,
    limit: int = 20
):
    query = select(Chat).options(
        selectinload(Chat.booking)
    ).where(Chat.id == chat_id)
    
    result = await db.execute(query)
    chat = result.scalar_one_or_none()

    if not chat or chat.booking.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found or access denied")

    query = (
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at.asc())
        .options(
            selectinload(Message.sender_user),
            selectinload(Message.sender_employee)
        )
    )

    if since_id:
        query = query.where(Message.id > since_id)
    else:
        subquery = (
            select(Message.id)
            .where(Message.chat_id == chat_id)
            .order_by(Message.id.desc())
            .limit(limit)
            .subquery()
        )
        query = (
            select(Message)
            .where(Message.id.in_(select(subquery)))
            .order_by(Message.id.asc())
            .options(
                selectinload(Message.sender_user),
                selectinload(Message.sender_employee)
            )
        )

    result = await db.execute(query)
    messages = result.scalars().all()

    messages_with_sender = []
    for msg in messages:
        sender_info = None
        if msg.sender_type == SenderTypeEnum.user and msg.sender_user:
            sender_info = SenderInfo(
                id=msg.sender_user.id, 
                first_name=msg.sender_user.first_name, 
                last_name=msg.sender_user.last_name,
                patronymic=msg.sender_user.patronymic,
                type="user"
            )
        elif msg.sender_type == SenderTypeEnum.employee and msg.sender_employee:
            sender_info = SenderInfo(
                id=msg.sender_employee.id, 
                first_name=msg.sender_employee.first_name, 
                last_name=msg.sender_employee.last_name,
                patronymic=msg.sender_employee.patronymic,
                type="employee"
            )
        elif msg.sender_type == SenderTypeEnum.ai:
            sender_info = SenderInfo(id=0, first_name="AI", last_name="Assistant", type="ai")

        messages_with_sender.append(
            MessageSchema(
                id=msg.id,
                content=msg.content,
                created_at=msg.created_at,
                sender=sender_info,
            )
        )

    return messages_with_sender

# Получение всех номеров (для админа/ресепшн)
@app.get("/reception/rooms", tags=["Reception"], response_model=List[RoomForDashboardSchema])
async def get_all_rooms_for_dashboard(
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(require_role([EmployeeRoleEnum.admin, EmployeeRoleEnum.reception]))
):
    rooms_query = select(Room).options(
        selectinload(Room.room_type).selectinload(RoomType.translations)
    )
    all_rooms = (await db.execute(rooms_query)).scalars().all()

    current_bookings_query = select(Booking).where(
        or_(
            Booking.status == BookingStatusEnum.active,
            Booking.status == BookingStatusEnum.confirmed
        )
    ).options(
        selectinload(Booking.user),
        selectinload(Booking.room),
        selectinload(Booking.employee)
    )
    active_bookings = (await db.execute(current_bookings_query)).scalars().all()
    
    bookings_map = {booking.room_id: booking for booking in active_bookings}

    active_booking_ids = [b.id for b in active_bookings]
    reception_chats_query = select(Chat).where(
        Chat.booking_id.in_(active_booking_ids),
        Chat.type == ChatTypeEnum.RECEPTION
    )
    reception_chats = (await db.execute(reception_chats_query)).scalars().all()
    chats_map = {chat.booking_id: chat.id for chat in reception_chats}

    dashboard_data = []
    for room in all_rooms:
        room_dto = RoomForDashboardSchema.from_orm(room)
        
        if room.id in bookings_map:
            booking_obj = bookings_map[room.id]
            booking_dto = BookingSchema.from_orm(booking_obj)
            booking_dto.reception_chat_id = chats_map.get(booking_obj.id)
            room_dto.current_booking = booking_dto
        
        dashboard_data.append(room_dto)
        
    return dashboard_data

# Получение всех заявок на сервис (ресепшн/админ)
@app.get("/reception/service-requests", tags=["Reception"], response_model=List[ServiceRequestForEmployeeSchema])
async def get_all_service_requests(
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(require_role([EmployeeRoleEnum.admin, EmployeeRoleEnum.reception]))
):
    query = select(ServiceRequest).options(
        selectinload(ServiceRequest.booking).options(
            selectinload(Booking.user),
            selectinload(Booking.room),
            selectinload(Booking.employee)
        ),
        selectinload(ServiceRequest.service).selectinload(Service.translations)
    ).order_by(ServiceRequest.created_at.desc())
    
    result = await db.execute(query)
    return result.scalars().all()

@app.get("/reception/service-requests/{request_id}", tags=["Reception"], response_model=ServiceRequestForEmployeeSchema)
async def get_service_request_details(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(require_role([EmployeeRoleEnum.admin, EmployeeRoleEnum.reception]))
):
    query = (
        select(ServiceRequest)
        .where(ServiceRequest.id == request_id)
        .options(
            selectinload(ServiceRequest.booking).options(
                selectinload(Booking.user),
                selectinload(Booking.room).selectinload(Room.room_type),
                selectinload(Booking.employee)
            ),
            selectinload(ServiceRequest.service).selectinload(Service.translations)
        )
    )

    result = await db.execute(query)
    service_request = result.scalar_one_or_none()

    if not service_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service request not found"
        )

    return service_request

# Обновление статуса заявки на сервис (ресепшн/админ)
@app.patch("/reception/service-requests/{request_id}", tags=["Reception"], response_model=ServiceRequestForEmployeeSchema)
async def update_service_request_status(
    request_id: int,
    status_update: ServiceRequestStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(require_role([EmployeeRoleEnum.admin, EmployeeRoleEnum.reception]))
):
    query = select(ServiceRequest).options(
        selectinload(ServiceRequest.booking).options(
            selectinload(Booking.user),
            selectinload(Booking.room),
            selectinload(Booking.employee)
        ),
        selectinload(ServiceRequest.service).selectinload(Service.translations)
    ).where(ServiceRequest.id == request_id)

    result = await db.execute(query)
    service_request = result.scalar_one_or_none()

    if not service_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service request not found")

    service_request.status = status_update.status
    service_request.assigned_employee_id = current_employee.id
    
    db.add(service_request)
    await db.commit()
    await db.refresh(service_request)
    
    return service_request

# Отправка сообщения в чат от сотрудника (ресепшн/админ)
@app.post("/reception/chats/{chat_id}/messages", tags=["Reception"], response_model=MessageSchema)
async def send_message_as_employee(
    chat_id: int,
    message_data: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(require_role([EmployeeRoleEnum.admin, EmployeeRoleEnum.reception]))
):
    chat = await db.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    new_message = Message(
        chat_id=chat_id,
        content=message_data.content,
        sender_type=SenderTypeEnum.employee,
        sender_employee_id=current_employee.id
    )
    db.add(new_message)
    await db.commit()
    await db.refresh(new_message, attribute_names=['sender_employee', 'id', 'created_at'])
    
    return MessageSchema(
        id=new_message.id,
        content=new_message.content,
        created_at=new_message.created_at,
        sender=SenderInfo(
            id=current_employee.id,
            first_name=current_employee.first_name,
            last_name=current_employee.last_name,
            patronymic=current_employee.patronymic,
            type="employee"
        )
    )

@app.get("/reception/chats", tags=["Reception"], response_model=List[ChatForReceptionSchema])
async def get_all_chats(
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(require_role([EmployeeRoleEnum.admin, EmployeeRoleEnum.reception]))
):
    last_message_subquery = (
        select(
            Message,
            func.row_number()
            .over(partition_by=Message.chat_id, order_by=Message.id.desc())
            .label("rn"),
        )
        .subquery("last_message_subquery")
    )

    last_message_cte = select(last_message_subquery).where(
        last_message_subquery.c.rn == 1
    ).cte("last_message_cte")

    LastMessage = aliased(Message, last_message_cte)

    query = (
        select(Chat, LastMessage)
        .outerjoin(
            LastMessage, LastMessage.chat_id == Chat.id
        )
        .options(
            selectinload(Chat.booking).options(
                selectinload(Booking.user),
                selectinload(Booking.room)
            )
        )
        .where(Chat.status == ChatStatusEnum.open)
        .order_by(Chat.id)
    )

    result = await db.execute(query)

    response_data = []
    for chat, last_message_data in result:
        chat_schema = ChatForReceptionSchema.from_orm(chat)

        if last_message_data and last_message_data.id is not None:
            chat_schema.last_message = LastMessageSchema.from_orm(last_message_data)

        response_data.append(chat_schema)

    return response_data


@app.get("/reception/chats/{chat_id}/messages", tags=["Reception"], response_model=List[MessageSchema])
async def get_chat_messages_for_employee(
    chat_id: int,
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(require_role([EmployeeRoleEnum.admin, EmployeeRoleEnum.reception])),
    since_id: Optional[int] = None,
    limit: int = 35
):
    chat = await db.get(Chat, chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found"
        )

    query = (
        select(Message)
        .where(Message.chat_id == chat_id)
        .options(
            selectinload(Message.sender_user),
            selectinload(Message.sender_employee)
        )
    )

    if since_id:
        query = query.where(Message.id > since_id).order_by(Message.id.asc())
    else:
        subquery = (
            select(Message.id)
            .where(Message.chat_id == chat_id)
            .order_by(Message.id.desc())
            .limit(limit)
            .subquery()
        )
        query = (
            query.where(Message.id.in_(select(subquery)))
            .order_by(Message.id.asc())
        )

    result = await db.execute(query)
    messages = result.scalars().all()

    messages_with_sender = []
    for msg in messages:
        sender_info = None
        if msg.sender_type == SenderTypeEnum.user and msg.sender_user:
            sender_info = SenderInfo(
                id=msg.sender_user.id, 
                first_name=msg.sender_user.first_name, 
                last_name=msg.sender_user.last_name,
                patronymic=msg.sender_user.patronymic,
                type="user"
            )
        elif msg.sender_type == SenderTypeEnum.employee and msg.sender_employee:
            sender_info = SenderInfo(
                id=msg.sender_employee.id, 
                first_name=msg.sender_employee.first_name, 
                last_name=msg.sender_employee.last_name,
                patronymic=msg.sender_employee.patronymic,
                type="employee"
            )
        elif msg.sender_type == SenderTypeEnum.ai:
            sender_info = SenderInfo(id=0, first_name="AI", last_name="Assistant", type="ai")

        messages_with_sender.append(
            MessageSchema(
                id=msg.id,
                content=msg.content,
                created_at=msg.created_at,
                sender=sender_info,
            )
        )

    return messages_with_sender

# Создание бронирования (ресепшн/админ)
@app.post("/reception/bookings", tags=["Reception"], response_model=BookingSchema, status_code=status.HTTP_200_OK)
async def create_booking(
    booking_data: BookingCreate,
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(require_role([EmployeeRoleEnum.admin, EmployeeRoleEnum.reception]))
):

    if booking_data.check_in_date > booking_data.check_out_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Check-out date must be after check-in date")

    user = await db.get(User, booking_data.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    room = await db.get(Room, booking_data.room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    if room.status != RoomStatusEnum.available:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Room is not available")

    overlapping_booking_query = select(Booking.id).where(
        Booking.room_id == booking_data.room_id,
        Booking.status != BookingStatusEnum.cancelled,
        or_(
            # Новое бронирование начинается во время существующего
            (Booking.check_in_date <= booking_data.check_in_date) & (booking_data.check_in_date < Booking.check_out_date),
            # Новое бронирование заканчивается во время существующего
            (Booking.check_in_date < booking_data.check_out_date) & (booking_data.check_out_date <= Booking.check_out_date),
            # Новое бронирование полностью "поглощает" существующее
            (booking_data.check_in_date <= Booking.check_in_date) & (booking_data.check_out_date >= Booking.check_out_date)
        )
    ).limit(1)
    
    
    result = await db.execute(overlapping_booking_query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The room is already booked for the selected dates"
        )

    new_booking = Booking(
        user_id=booking_data.user_id,
        room_id=booking_data.room_id,
        check_in_date=booking_data.check_in_date,
        check_out_date=booking_data.check_out_date,
        employee_id=current_employee.id,
        price_per_night=room.current_price_per_night
    )
    
    room.status = RoomStatusEnum.occupied
    
    db.add(new_booking)
    db.add(room)
    await db.commit()
    
    query = select(Booking).options(
        selectinload(Booking.user),
        selectinload(Booking.room),
        selectinload(Booking.employee)
    ).where(Booking.id == new_booking.id)
    
    result = await db.execute(query)
    created_booking = result.scalar_one()

    return created_booking

# Получение всех бронирований (ресепшн/админ)
@app.get("/reception/getusers", tags=["Reception"], response_model=List[GetUserSchema])
async def get_all_bookings(
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(require_role([EmployeeRoleEnum.admin, EmployeeRoleEnum.reception]))
):
    query = select(Booking).options(
        selectinload(Booking.user),
        selectinload(Booking.room),
        selectinload(Booking.employee)
    ).order_by(Booking.check_in_date.desc())
    
    result = await db.execute(query)
    # bookings = result.scalars().all()
    # return [    
    #     {
    #         "booking_id": booking.id,
    #         "booking_status": booking.status,
    #         "user_id": booking.user.id,
    #         "user_status": booking.user.status,
    #         "first_name": booking.user.first_name,
    #         "last_name": booking.user.last_name,
    #         "phone_number": booking.user.phone_number,
    #         "check_out_date": booking.check_out_date.isoformat()
    #     }
    #     for booking in bookings
    # ]
    
    bookings = result.scalars().all() 
    
    response_data = []
    for booking in bookings:
        password_to_return = booking.user.password_hash 
        
        response_data.append({
            "booking_id": booking.id,
            "booking_status": booking.status,
            "user_id": booking.user.id,
            "user_status": booking.user.status,
            "first_name": booking.user.first_name,
            "last_name": booking.user.last_name,
            "phone_number": booking.user.phone_number,
            "check_out_date": booking.check_out_date.isoformat(),
            "generated_password": password_to_return  
        })
        
    return response_data
    

# Получение бронирования по id (ресепшн/админ)
@app.get("/reception/bookings/{booking_id}", tags=["Reception"], response_model=GetUserSchema)
async def get_booking_by_id(
    booking_id: int,
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(require_role([EmployeeRoleEnum.admin, EmployeeRoleEnum.reception]))
):
    booking = await db.scalar(
        select(Booking).options(
            selectinload(Booking.user),
            selectinload(Booking.room),
            selectinload(Booking.employee)
        ).where(Booking.id == booking_id)
    )
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    return {        
        "booking_id": booking.id,
        "booking_status": booking.status,
        "user_id": booking.user.id,
        "user_status": booking.user.status,
        "first_name": booking.user.first_name,
        "last_name": booking.user.last_name,
        "phone_number": booking.user.phone_number,
        "check_out_date": booking.check_out_date.isoformat()
    }

# Cтатус бронирования (ресепшн/админ)
@app.patch("/reception/bookings/{booking_id}", tags=["Reception"], response_model=BookingSchema)
async def update_booking(
    booking_id: int,
    update_data: BookingUpdate,
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(require_role([EmployeeRoleEnum.admin, EmployeeRoleEnum.reception]))
):
    try:
        booking = await db.get(
            Booking, 
            booking_id, 
            options=[selectinload(Booking.room), selectinload(Booking.user)]
        )
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Booking with ID {booking_id} not found"
            )

        if not booking.room:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Associated room not found"
            )

        if update_data.status:
            booking.status = update_data.status
            
            if update_data.status in [BookingStatusEnum.completed, BookingStatusEnum.cancelled]:
                booking.room.status = RoomStatusEnum.available
                
                if booking.user:
                    booking.user.status = UserStatusEnum.archived
                    booking.user.archived_at = datetime.now(timezone.utc)
            
            elif update_data.status in [BookingStatusEnum.active, BookingStatusEnum.confirmed]:
                booking.room.status = RoomStatusEnum.occupied

        if update_data.check_out_date:
            check_in = booking.check_in_date.replace(tzinfo=timezone.utc) if booking.check_in_date.tzinfo is None else booking.check_in_date
            check_out = update_data.check_out_date.replace(tzinfo=timezone.utc) if update_data.check_out_date.tzinfo is None else update_data.check_out_date
            
            if check_out <= check_in:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="New check-out date must be after check-in date"
                )
            booking.check_out_date = update_data.check_out_date

        db.add(booking)
        await db.commit()
        await db.refresh(booking)
        
        return booking

    except TypeError as e:
        if "can't compare offset-naive and offset-aware datetimes" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Datetime comparison error: please provide timezone-aware datetimes"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )


@app.post("/reception/users", tags=["Reception"], response_model=UserBookingResponse, status_code=status.HTTP_201_CREATED)
async def create_user_and_book_room(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(require_role([EmployeeRoleEnum.admin, EmployeeRoleEnum.reception])),
    
):
    user_query = select(User).where(User.phone_number == user_data.phone_number)
    user = (await db.execute(user_query)).scalar_one_or_none()
    
    generated_password = None

    if user:
        if user.status == UserStatusEnum.archived:
            user.status = UserStatusEnum.active
            user.archived_at = None
            
            digits = ''.join(random.choice(string.digits) for i in range(4))
            password_list = list(digits)
            random.shuffle(password_list)
            generated_password = "".join(password_list)
            
            user.password_hash = generated_password
            db.add(user)


    else:
        digits = ''.join(random.choice(string.digits) for i in range(4))
        password_list = list(digits)
        random.shuffle(password_list)
        generated_password = "".join(password_list)
        password_to_store = generated_password
        
        user = User(
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            patronymic=user_data.patronymic,
            phone_number=user_data.phone_number,
            password_hash=password_to_store
        )
        db.add(user)
        await db.flush()

    if not user_data.room_id:
        await db.commit()
        return UserBookingResponse(user=user, booking=None, generated_password=generated_password)

    room = await db.get(Room, user_data.room_id)
    if not room:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Room with id {user_data.room_id} not found.")

    
    check_in_date = user_data.check_in_date if user_data.check_in_date else datetime.now()
    
    if not user_data.check_out_date:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "check_out_date is required")
    
    if room.status == RoomStatusEnum.available:
        overlapping_booking_query = select(Booking.id).where(
            Booking.room_id == user_data.room_id,
            Booking.status.in_([BookingStatusEnum.confirmed, BookingStatusEnum.active]),
            or_(
                (Booking.check_in_date <= check_in_date) & (check_in_date < Booking.check_out_date),
                (Booking.check_in_date < user_data.check_out_date) & (user_data.check_out_date <= Booking.check_out_date)
            )
        ).limit(1)
        
        if (await db.execute(overlapping_booking_query)).scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The room is already booked for the selected dates")

        new_booking = Booking(
            user_id=user.id,
            room_id=user_data.room_id,
            employee_id=current_employee.id,
            price_per_night=room.current_price_per_night,
            check_in_date=check_in_date,
            check_out_date=user_data.check_out_date,
            status=BookingStatusEnum.confirmed
        )
        db.add(new_booking)
        room.status = RoomStatusEnum.occupied
        db.add(room)
        await db.commit()

        query = select(Booking).options(
            selectinload(Booking.user),
            selectinload(Booking.room).selectinload(Room.room_type),
            selectinload(Booking.employee)
        ).where(Booking.id == new_booking.id)
        created_booking = (await db.execute(query)).scalar_one()

        return UserBookingResponse(user=created_booking.user, booking=created_booking, generated_password=generated_password)

    elif room.status == RoomStatusEnum.occupied:
        current_booking_query = select(Booking).options(selectinload(Booking.user)).where(
            Booking.room_id == user_data.room_id,
            Booking.status.in_([BookingStatusEnum.active, BookingStatusEnum.confirmed])
        ).order_by(Booking.check_in_date.desc()).limit(1)
        
        current_booking = (await db.execute(current_booking_query)).scalar_one_or_none()

        if not current_booking:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Room status is 'occupied', but no active booking found. Please check manually.")

        if current_booking.user.phone_number == user_data.phone_number:
            digits = ''.join(random.choice(string.digits) for i in range(4))
            password_list = list(digits)
            random.shuffle(password_list)
            new_password = "".join(password_list)
            
            user.password_hash = new_password
            db.add(user)
            await db.commit()
            
            return UserBookingResponse(user=user, booking=current_booking, generated_password=new_password)
        else:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This room is already occupied by another guest.")

    else:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Room is currently unavailable (Status: {room.status.value})")

@app.patch("/reception/chats/{chat_id}/claim", tags=["Reception"], response_model=ChatClaimResponse)
async def claim_chat(
    chat_id: int,
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(require_role([EmployeeRoleEnum.admin, EmployeeRoleEnum.reception]))
):
    chat = await db.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    if chat.status != ChatStatusEnum.open:
        raise HTTPException(status_code=409, detail="Chat is already claimed or closed")

    chat.status = ChatStatusEnum.claimed
    chat.assigned_employee_id = current_employee.id
    
    await db.commit()
    await db.refresh(chat)
    
    return chat

# Логин для сотрудников (админ/ресепшн)
@app.post("/admin/login", tags=["Admin"], response_model=Token)
async def login_for_employee_access_token(form_data: EmployeeLoginRequest, db: AsyncSession = Depends(get_db)):
    query = select(Employee).where(Employee.username == form_data.username)
    result = await db.execute(query)
    employee = result.scalar_one_or_none()

    if not employee:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    is_password_valid = await run_in_threadpool(verify_password, form_data.password, employee.password_hash)
    if not employee or not is_password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if employee.status != UserStatusEnum.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    access_token_expires = timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    access_token_value = access_token(
        data={"sub": str(employee.id), "role": employee.role.value},
        expires_delta=access_token_expires
    )

    return {"access_token": access_token_value, "token_type": "bearer"}

# Создание нового сотрудника 
@app.post("/admin/employees", tags=["Admin"], response_model=EmployeeSchema, status_code=status.HTTP_200_OK)
async def create_employee(
    employee_data: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: Employee = Depends(require_role([EmployeeRoleEnum.admin]))
):
    query = select(Employee).where(Employee.username == employee_data.username)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee with this username already exists",
        )
    
    hashed_password = await run_in_threadpool(get_password_hash, employee_data.password)
    
    new_employee = Employee(
        **employee_data.dict(exclude={"password"}),
        password_hash=hashed_password
    )
    
    db.add(new_employee)
    await db.commit()
    await db.refresh(new_employee)
    
    return new_employee

# Получение списка всех сотрудников 
@app.get("/admin/employees", tags=["Admin"], response_model=List[EmployeeSchema])
async def get_all_employees(
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(require_role([EmployeeRoleEnum.admin]))
):
    query = select(Employee)
    result = await db.execute(query)
    employees = result.scalars().all()
    return employees

# Получение сотрудника по id 
@app.get("/admin/employees/{employee_id}", tags=["Admin"], response_model=EmployeeSchema)
async def get_employee_by_id(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: Employee = Depends(require_role([EmployeeRoleEnum.admin]))
):
    employee = await db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return employee

# Обновление данных сотрудника 
@app.put("/admin/employees/{employee_id}", tags=["Admin"], response_model=EmployeeSchema)
async def update_employee_details(
    employee_id: int,
    employee_data: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: Employee = Depends(require_role([EmployeeRoleEnum.admin]))
):
    employee = await db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    update_data = employee_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(employee, key, value)

    db.add(employee)
    await db.commit()
    await db.refresh(employee)
    return employee

# Архивация сотрудника 
@app.delete("/admin/employees/{employee_id}", tags=["Admin"], status_code=status.HTTP_200_OK)
async def archive_employee(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: Employee = Depends(require_role([EmployeeRoleEnum.admin]))
):
    employee = await db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    
    if employee.id == current_admin.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot archive yourself")

    employee.status = UserStatusEnum.archived
    employee.archived_at = datetime.now(timezone.utc)
    
    db.add(employee)
    await db.commit()
    
    return None

# Создание типа номера 
@app.post("/admin/room-types", tags=["Admin"], response_model=RoomTypeSchema, status_code=status.HTTP_200_OK)
async def create_room_type(
    room_type_data: RoomTypeCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: Employee = Depends(require_role([EmployeeRoleEnum.admin]))
):
    query = select(RoomType).where(RoomType.code == room_type_data.code)
    if (await db.execute(query)).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Room type code already exists")

    new_room_type = RoomType(code=room_type_data.code)
    db.add(new_room_type)
    await db.commit()
    await db.refresh(new_room_type)

    for trans_data in room_type_data.translations:
        new_translation = RoomTypeTranslation(
            room_type_id=new_room_type.id,
            **trans_data.dict()
        )
        db.add(new_translation)
    
    await db.commit()
    await db.refresh(new_room_type, attribute_names=['translations'])

    return new_room_type

# Получение всех типов номеров 
@app.get("/admin/room-types", tags=["Admin"], response_model=List[RoomTypeSchema])
async def get_all_room_types(
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(require_role([EmployeeRoleEnum.admin]))
):
    query = select(RoomType)
    result = await db.execute(query)
    roomtype = result.scalars().all()
    return roomtype

# Создание номера 
@app.post("/admin/rooms", tags=["Admin"], response_model=RoomSchema, status_code=status.HTTP_200_OK)
async def create_room(
    room_data: RoomCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: Employee = Depends(require_role([EmployeeRoleEnum.admin]))
):
    if not await db.get(RoomType, room_data.room_type_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room type not found")

    new_room = Room(**room_data.dict())
    db.add(new_room)
    await db.commit()
    
    query = select(Room).options(selectinload(Room.room_type).selectinload(RoomType.translations)).where(Room.id == new_room.id)
    result = await db.execute(query)
    
    return result.scalar_one()

# Обновление данных номера 
@app.put("/admin/rooms/{room_id}", tags=["Admin"], response_model=RoomSchema)
async def update_room(
    room_id: int,
    room_data: RoomUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: Employee = Depends(require_role([EmployeeRoleEnum.admin]))
):
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
        
    update_data = room_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(room, key, value)
        
    db.add(room)
    await db.commit()
    
    query = select(Room).options(selectinload(Room.room_type).selectinload(RoomType.translations)).where(Room.id == room.id)
    result = await db.execute(query)
    
    return result.scalar_one()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0", 
        port=8000,
        log_config=LOGGING_CONFIG
)
