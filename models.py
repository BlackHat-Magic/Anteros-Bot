from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Float, Boolean, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()
DATABASE_NAME = os.getenv("SQLITE_DATABASE_NAME")

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    is_admin = Column(Boolean, default=False)
    requests = relationship("Request", back_populates="user")
    created_channels = relationship("Channel", back_populates="user")
    messages = relationship("Message", back_populates="user")


class Request(Base):
    __tablename__ = "requests"
    id = Column(Integer, primary_key=True)
    userid = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="requests")
    date = Column(Float)

class Channel(Base):
    __tablename__ = "channels"
    id = Column(Integer, primary_key=True)
    userid = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="created_channels")
    messages = relationship("Message", back_populates="channel")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    discord_id = Column(Integer)
    channelid = Column(Integer, ForeignKey("channels.id"))
    channel = relationship("Channel", back_populates="messages")
    userid = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="messages")
    selected_variant = Column(Integer)
    variants = relationship("Variant", back_populates="message")

class Variant(Base):
    __tablename__ = "variants"
    id = Column(Integer, primary_key=True)
    messageid = Column(Integer, ForeignKey("messages.id"))
    message = relationship("Message", back_populates="variants")
    text = Column(String)

def create_database():
    database = create_engine(f"sqlite:///{DATABASE_NAME}")
    Base.metadata.create_all(database)
    Session = sessionmaker(bind=database)
    session = Session()
    return(session)