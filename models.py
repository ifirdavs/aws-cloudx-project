from sqlalchemy import Column, Integer, String, BigInteger, DateTime
from sqlalchemy.sql import func
from database import Base

class Image(Base):
    __tablename__ = "image"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    name = Column(String(20), unique=True, index=True)
    image_size = Column(BigInteger)
    file_extension = Column(String(40))
    last_update = Column(DateTime, default=func.now())