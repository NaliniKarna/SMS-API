import os
import logging
import requests
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from .database import SessionLocal, engine
from .models import SMSConfig
from .database import Base

# Create tables
Base.metadata.create_all(bind=engine)

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SMS Forwarding API")

API_KEY = os.getenv("API_KEY")
SMS_AUTH_TOKEN = os.getenv("SMS_AUTH_TOKEN")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class SMSRequest(BaseModel):
    from_number: str
    to_number: str
    api_key: str


class SMSCreate(BaseModel):
    to_number: str
    sms_text: str

class TemplateUpdate(BaseModel):
    to_number: str
    sms_text: str
    api_key: str


@app.post("/add-template")
def add_template(data: SMSCreate, db: Session = Depends(get_db)):

    existing = db.query(SMSConfig).filter(
        SMSConfig.to_number == data.to_number
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="to_number already exists")

    sms = SMSConfig(
        to_number=data.to_number,
        sms_text=data.sms_text
    )

    db.add(sms)
    db.commit()
    db.refresh(sms)

    return {"status": "template added"}

@app.put("/update-template")
def update_template(data: TemplateUpdate, db: Session = Depends(get_db)):

    if data.api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    template = db.query(SMSConfig).filter(
        SMSConfig.to_number == data.to_number
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    template.sms_text = data.sms_text
    db.commit()
    db.refresh(template)

    return {"status": "template updated"}

@app.post("/send-sms")
def send_sms(data: SMSRequest, db: Session = Depends(get_db)):

    if data.api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    template = db.query(SMSConfig).filter(
        SMSConfig.to_number == data.to_number
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="to_number not found")

    from .models import SMSLog

    # Create initial log entry
    log_entry = SMSLog(
        from_number=data.from_number,
        to_number=data.to_number,
        sms_text=template.sms_text,
        status="pending"
    )

    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)

    try:
        response = requests.post(
            "https://sms.aakashsms.com/sms/v3/send/",
            data={
                "auth_token": SMS_AUTH_TOKEN,
                "to": data.from_number,
                "text": template.sms_text
            },
            timeout=10
        )

        log_entry.gateway_response = response.text

        if response.status_code == 200:
            log_entry.status = "sent"
        else:
            log_entry.status = "failed"

        db.commit()

        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="SMS sending failed")

    except requests.exceptions.RequestException as e:
        log_entry.status = "failed"
        log_entry.gateway_response = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail="SMS gateway error")

    return {
        "status": log_entry.status,
        "from_number": data.from_number,
        "to_number": data.to_number,
        "message": template.sms_text
    }