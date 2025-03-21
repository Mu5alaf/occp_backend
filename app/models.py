from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()

# user table
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

class ChargerUser(Base):
    __tablename__ = "charger_users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_tag = Column(String, unique=True, nullable=False)
    name = Column(String)

# Charger Status
class ChargerStatus(str, enum.Enum):
    AVAILABLE = "Available"
    CHARGING = "Charging"
    FAULTED = "Faulted"
    UNAVAILABLE = "Unavailable"
    DISCONNECTED = "Disconnected"
    CONNECTED = "Connected"

# Charges model
class Charger(Base):
    __tablename__ = 'chargers'
    # Using string insted of Integer Because occp have unique string rather than numric ID's
    id = Column(String, primary_key=True)
    model = Column(String)
    vendor = Column(String)
    status = Column(Enum(ChargerStatus), default=ChargerStatus.DISCONNECTED, nullable=False)
    last_seen = Column(DateTime(timezone=True),server_default=func.now())

# Charger Status

class TransactionStatus(str, enum.Enum):
    STARTED = "Started"
    STOPPED = "Stopped"
    FAILED = "Failed"

# Transaction
class Transaction(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True, autoincrement=True) # autoincrement for auto incerment num of id's
    charger_id = Column(String)
    id_tag = Column(String, nullable=False)
    connector_id = Column(Integer, nullable=False)
    meter_start = Column(Integer, nullable=False)
    meter_stop = Column(Integer, nullable=True) 
    start_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    stop_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(Enum(TransactionStatus), default=TransactionStatus.STARTED, nullable=False) 

# logs status
class StatusLog(Base):
    __tablename__ = "status_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    charger_id = Column(String)
    status = Column(Enum(ChargerStatus), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)