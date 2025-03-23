import asyncio
import websockets
import os 
from fastapi.staticfiles import StaticFiles
from app.middlewares import setup_middlewares

from typing import Annotated
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException
from starlette import status
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from ocpp.v16.enums import AuthorizationStatus, RegistrationStatus
from ocpp.v16 import ChargePoint as cp_v16, call_result, call
from ocpp.routing import on
from .database import engine, SessionLocal
from .models import (
    Base,
    Charger, 
    Transaction, 
    StatusLog, 
    ChargerStatus, 
    TransactionStatus, 
    ChargerUser,
    User
    )

from .auth import(
    OAuth2PasswordRequestForm,
    CreateUserRequest,
    Token,
    create_access_token,
    authenticate_user,
    get_current_user,
    pwd_context,
)


import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# load environment variables
load_dotenv()

# Create tables in PostgreSQL
Base.metadata.create_all(bind=engine)

app = FastAPI()
setup_middlewares(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app.mount("/static", StaticFiles(directory=STATIC_DIR, html=True), name="static")

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
    def __init__(self, charge_point_id, websocket, db: Session):
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


# Websocket connection
async def on_connect(websocket, path):
    charge_point_id = path.strip('/')
    db = SessionLocal()
    protocol = websocket.subprotocol
    # handel both 
    if protocol == 'ocpp1.6':
        cp_instance = cp_v16(charge_point_id, websocket) 
        active_chargers[charge_point_id] = cp_instance
        logger.info(f"Charger {charge_point_id} connected with protocol {protocol}")
        await cp_instance.start()
    else:
        logger.warning(f"Unsupported protocol: {protocol}. Only OCPP 1.6 is supported.")
    db.close()

# register endpoint
@app.post("/auth/register", response_model=Token)
async def register(user_data: CreateUserRequest, db: Annotated[Session, Depends(get_db)]):
    hashed_password = pwd_context.hash(user_data.password)
    new_user = User(username=user_data.username, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    access_token = create_access_token(data={"sub": new_user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# Auth endpoint
@app.post("/auth/token", response_model=Token)
async def login( db: Annotated[Session, Depends(get_db)] , form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect Username OR password"
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

#charges endpoint
@app.post("/add-charger", response_model=dict)
async def add_charger(charger_id: str,db: Annotated[Session, Depends(get_db)], current_user: User = Depends(get_current_user)):
    # Check if charger already exists
    existing_charger = db.query(Charger).filter(Charger.id == charger_id).first()
    if existing_charger:
        raise HTTPException(status_code=400, detail="Charger already exists")
    
    # Add new charger
    new_charger = Charger(
        id=charger_id,
        model=f"Model-{charger_id}",
        vendor="TestVendor",
        status="Connected"
    )
    db.add(new_charger)
    db.commit()
    logger.info(f"Added charger {charger_id} via API")
    return {"status": "Charger added", "charger_id": charger_id}

@app.get("/chargers", response_model=dict)
async def get_chargers( db: Annotated[Session, Depends(get_db)] , current_user: User = Depends(get_current_user)):
    chargers = db.query(Charger).all()
    return {"active_chargers": [charge.id for charge in chargers]}

@app.post("/start/{charger_id}", response_model=dict)
async def start_charging(charger_id: str, db: Annotated[Session, Depends(get_db)], current_user: User = Depends(get_current_user)):
    # Check if the charger exists in the database
    charger = db.query(Charger).filter(Charger.id == charger_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail="Charger not found in database")

    # If the charger is actively connected, send RemoteStartTransaction
    if charger_id in active_chargers:
        cp_instance = active_chargers[charger_id]
        request = call.RemoteStartTransactionPayload(id_tag="user123", connector_id=1)
        response = await cp_instance.call(request)
        logger.info(f"Remote start sent to {charger_id}")
        return {"status": "Command Sent", "response": str(response)}
    else:
        # Simulate starting a charge by adding a transaction to the database
        transaction = Transaction(
            charger_id=charger_id,
            id_tag="user123",
            connector_id=1,
            meter_start=0,
            start_time=datetime.now(timezone.utc),
            status=TransactionStatus.STARTED
        )
        db.add(transaction)
        db.commit()
        logger.info(f"Simulated charging started for {charger_id}")
        return {"status": "Simulated charging started", "charger_id": charger_id}

@app.post("/stop/{charger_id}", response_model=dict)
async def stop_charging(charger_id: str, db: Annotated[Session, Depends(get_db)], current_user: User = Depends(get_current_user)):
    # Check if the charger exists in the database
    charger = db.query(Charger).filter(Charger.id == charger_id).first()
    if not charger:
        raise HTTPException(status_code=404, detail="Charger not found in database")

    # Check if there's an ongoing transaction for this charger
    ongoing_transaction = db.query(Transaction).filter(
        Transaction.charger_id == charger_id,
        Transaction.status == TransactionStatus.STARTED
    ).first()

    if not ongoing_transaction:
        raise HTTPException(status_code=400, detail="No ongoing transaction found for this charger")

    # If the charger is actively connected, send the stop command
    if charger_id in active_chargers:
        cp_instance = active_chargers[charger_id]
        request = call.RemoteStopTransactionPayload(transaction_id=ongoing_transaction.id)
        response = await cp_instance.call(request)
        logger.info(f"Remote stop sent to {charger_id} for transaction {ongoing_transaction.id}")
        # Update the transaction status in the database
        ongoing_transaction.stop_time = datetime.now(timezone.utc)
        ongoing_transaction.status = TransactionStatus.STOPPED
        db.commit()
        return {"status": "Command Sent", "response": str(response)}
    else:
        # If not connected, simulate stopping by updating the transaction
        ongoing_transaction.stop_time = datetime.now(timezone.utc)
        ongoing_transaction.status = TransactionStatus.STOPPED
        db.commit()
        logger.info(f"Simulated charging stopped for {charger_id}")
        return {"status": "Charging stopped (charger not connected)", "charger_id": charger_id}

@app.get("/transactions", response_model=dict)
async def get_transactions(db: Annotated[Session, Depends(get_db)],current_user: User = Depends(get_current_user)):
    transactions = db.query(Transaction).all()
    return {"transactions": [{"id": t.id, "charger_id": t.charger_id, "start_time": t.start_time} for t in transactions]}

async def main():
    server = websockets.serve(on_connect, "0.0.0.0", 9000)
    await server
    logger.info("WebSocket server running on ws://0.0.0.0:9000")
    await asyncio.Future()

if __name__ == "__main__":
    import uvicorn
    asyncio.run_coroutine_threadsafe(main(), asyncio.get_event_loop())
    uvicorn.run(app, host="0.0.0.0", port=8000)