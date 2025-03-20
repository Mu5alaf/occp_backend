import asyncio
import websockets
import os 

from datetime import datetime, timezone
from fastapi import FastAPI, Depends
from sqlalchemy.orm import session
from dotenv import load_dotenv

from ocpp.v16.enums import AuthorizationStatus, RegistrationStatus
from ocpp.v16 import ChargePoint as cp_v16, call_result, call
from ocpp.routing import on
from database import engine, SessionLocal

from .models import (
    Base,
    Charger, 
    Transaction, 
    StatusLog, 
    ChargerStatus, 
    TransactionStatus, 
    ChargerUser,
    User)

from auth import(
    OAuth2PasswordBearer,
    CreateUserRequest,
    Token,
    create_access_token,
    authenticate_user,
    get_current_user,
    pwd_context,
    db_dependency
)

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# load environment variables
load_dotenv()

# Create tables in PostgreSQL
Base.metadata.create_all(bind=engine)

app = FastAPI()

# dict for active chargers
active_chargers = {}

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ChargePoint(cp_v16):
    def __init__(self, charge_point_id, websocket, db: session):
        super().__init__(charge_point_id, websocket)
        self.db = db

# Check 
    @on("BootNotification")
    async def on_boot_notification(self, charge_point_model, charge_point_vendor, **kwargs):
        charger = Charger(
            id = self.id, 
            model = charge_point_model,
            vendor = charge_point_vendor,
            status = ChargerStatus.CONNECTED,
            last_seen = datetime.now(timezone.utc)
        )
        self.db.merge(charger)
        self.db.commit()
        logger.info(f"BootNotification from {charge_point_model}")
        return call_result.BootNotification(
            current_time = datetime.now(timezone.utc).isoformat(),
            interval=10, 
            status= RegistrationStatus.accepted
        )

# Check
    @on("Heartbeat")
    async def on_heartbeat(self, **kwargs):
        log = StatusLog(charger_id = self.id, status=ChargerStatus.AVAILABLE)
        self.db.add(log)
        self.db.commit()
        logger.info(f"Heartbeat from {self.id}")
        return call_result.Heartbeat(
            current_time = datetime.now(timezone.utc).isoformat(),
        )

# Check
    @on("Authorize")
    async def on_authorize(self, id_tag, **kwargs):
        charger_user = self.db.query(ChargerUser).filter(
            ChargerUser.id_tag == id_tag,
            ChargerUser.charger_id == self.id
            ).first()
        status = AuthorizationStatus.accepted if charger_user else AuthorizationStatus.invalid
        logger.info(f"Authorize request for ID {id_tag}: {status}")
        return call_result.Authorize(id_tag_info={"status": status})

# Check
    @on("StartTransaction")
    async def on_start_transaction(self, id_tag, connector_id, meter_start, **kwargs):
        transaction = Transaction(
            charger_id=self.id, 
            id_tag=id_tag, 
            connector_id=connector_id, 
            start_time=datetime.now(timezone.utc),
            status = TransactionStatus.STARTED
        )
        self.db.add(transaction)
        self.db.commit()
        print(f"")
        logger.info(f"Charging started: Connector {connector_id} - ID {id_tag}")
        return call_result.StartTransaction(
            transaction_id=transaction.id, 
            id_tag_info={"status": AuthorizationStatus.accepted} 
        )
    
# Check
    @on("StopTransaction")
    async def on_stop_transaction(self, transaction_id, meter_stop, **kwargs):
        transaction = self.db.query(Transaction).filter(Transaction.id == transaction_id).first()
        if transaction:
            transaction.stop_time = datetime.now(timezone.utc)
            transaction.meter_stop = meter_stop 
            transaction.status = TransactionStatus.STOPPED 
            self.db.commit()
            logger.info(f"Charging stopped for transaction {transaction_id}")
        return call_result.StopTransaction(
            id_tag_info={"status": AuthorizationStatus.accepted} 
            )
