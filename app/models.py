from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base


class SMSConfig(Base):
    __tablename__ = "sms_configs"

    id = Column(Integer, primary_key=True, index=True)
    to_number = Column(String(20), unique=True, nullable=False, index=True)
    sms_text = Column(String(500), nullable=False)

    # logs = relationship("SMSLog", back_populates="template")

class SMSLog(Base):
    __tablename__ = "sms_logs"

    id = Column(Integer, primary_key=True, index=True)

    from_number = Column(String(20), nullable=False)
    to_number = Column(String(20), nullable=False)

    sms_text = Column(Text, nullable=False)

    status = Column(String(20), default="pending")  # pending, sent, failed
    gateway_response = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())