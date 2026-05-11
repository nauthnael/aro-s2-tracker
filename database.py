from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date, DateTime, Float, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import datetime
import os

# Database path
DB_DIR = "data"
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

DB_URL = f"sqlite:///./{DB_DIR}/aro_tracker.db"

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Snapshot(Base):
    __tablename__ = "snapshots"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, nullable=False)
    is_delayed = Column(Boolean, default=False)
    note = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    rankings = relationship("Ranking", back_populates="snapshot", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="snapshot", cascade="all, delete-orphan")

class Ranking(Base):
    __tablename__ = "rankings"
    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(Integer, ForeignKey("snapshots.id"))
    rank = Column(Integer)
    username = Column(String, index=True)
    alias = Column(String)
    jade = Column(Integer)
    t1_refs = Column(Integer)
    t2_refs = Column(Integer)
    delta = Column(Integer, nullable=True)
    w_rate = Column(Float, nullable=True)
    proj_may31 = Column(Integer, nullable=True)
    prize_est = Column(String, nullable=True)
    is_team = Column(Boolean, default=False)
    team_role = Column(String, nullable=True)
    
    snapshot = relationship("Snapshot", back_populates="rankings")

class TeamMember(Base):
    __tablename__ = "team_members"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    alias = Column(String)
    role = Column(String) # "LEADER", "T1", "T2"
    bxh_rank = Column(Integer, nullable=True)
    join_date = Column(Date)
    note = Column(Text)

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(Integer, ForeignKey("snapshots.id"))
    level = Column(String) # "RED", "YELLOW", "INFO"
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    snapshot = relationship("Snapshot", back_populates="alerts")

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
