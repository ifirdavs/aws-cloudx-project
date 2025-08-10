from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import os

# Get database connection details from environment variables
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "images_db")

DB_REGION = os.environ.get("DB_REGION", "us-east-1")
USE_IAM_AUTH = os.environ.get("USE_IAM_AUTH", "false").lower() == "true"

def create_engine_with_iam():
    """Create engine with IAM authentication"""
    import boto3
    
    # Create RDS client (using EC2 instance role, not profile)
    rds_client = boto3.client('rds', region_name=DB_REGION)
    
    # Generate auth token
    auth_token = rds_client.generate_db_auth_token(
        DBHostname=DB_HOST,
        Port=int(DB_PORT),
        DBUsername=DB_USER,
        Region=DB_REGION
    )
    
    # Create connection string with SSL required
    connection_string = f"postgresql://{DB_USER}:{auth_token}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    return create_engine(
        connection_string,
        poolclass=NullPool,  # Avoid pooling due to token expiration every 15 minutes, thus, IAM auth is only for an employee access (or temporary access) and is not suitable for production.
        connect_args={
            "sslmode": "require"  # SSL is required for IAM auth
        }
    )

# Create engine based on authentication method
if USE_IAM_AUTH:
    engine = create_engine_with_iam()
else:
    SQLALCHEMY_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()