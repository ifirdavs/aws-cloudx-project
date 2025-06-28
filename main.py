from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
import io
import boto3
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Previous task EC2 metadata retrieval
from metadata import get_imds_token, get_instance_identity_document

# Database setup
from database import get_db, Base, engine
from models import Image

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI()

# S3 Configuration
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "your-bucket-name")
s3_client = boto3.client('s3')

@app.get("/location")
async def location():
    try:
        token = get_imds_token()
        doc = get_instance_identity_document(token)
        return {
            "region": doc.get("region"),
            "availabilityZone": doc.get("availabilityZone")
        }
    except Exception as e:
        # Return a 500 if metadata fetch fails
        raise HTTPException(status_code=500, detail=str(e))

# Image management endpoints
@app.get("/images")
async def get_images(
    name: Optional[str] = None,
    metadata: bool = False,
    db: Session = Depends(get_db)
):
    try:
        if name:
            # Get specific image
            image = db.query(Image).filter(Image.name == name).first()
            if not image:
                raise HTTPException(status_code=404, detail=f"Image with name {name} not found")
            
            if metadata:
                # Return only metadata
                return {
                    "id": image.id,
                    "name": image.name,
                    "image_size": image.image_size,
                    "file_extension": image.file_extension,
                    "last_update": image.last_update
                }
            else:
                # Return image file
                try:
                    s3_response = s3_client.get_object(
                        Bucket=S3_BUCKET_NAME,
                        Key=f"{image.name}.{image.file_extension}"
                    )
                    
                    return StreamingResponse(
                        io.BytesIO(s3_response['Body'].read()),
                        media_type=f"image/{image.file_extension}"
                    )
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Error retrieving image from S3: {str(e)}")
        else:
            # Get all images (metadata only)
            images = db.query(Image).all()
            return [
                {
                    "id": img.id,
                    "name": img.name,
                    "image_size": img.image_size,
                    "file_extension": img.file_extension,
                    "last_update": img.last_update
                }
                for img in images
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/images")
async def upload_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        # Extract file information
        file_content = await file.read()
        file_size = len(file_content)
        file_name = file.filename.split('.')[0]
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else ''
        
        # Check if an image with this name already exists
        existing_image = db.query(Image).filter(Image.name == file_name).first()
        if existing_image:
            raise HTTPException(status_code=400, detail=f"Image with name {file_name} already exists")
        
        # Upload to S3
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=f"{file_name}.{file_extension}",
            Body=file_content
        )
        
        # Store metadata in database
        new_image = Image(
            name=file_name,
            image_size=file_size,
            file_extension=file_extension,
            last_update=datetime.now()
        )
        
        db.add(new_image)
        db.commit()
        db.refresh(new_image)
        
        return {
            "id": new_image.id,
            "name": new_image.name,
            "message": "Image uploaded successfully"
        }
    except Exception as e:
        # Cleanup in case of error (if file was uploaded to S3)
        try:
            s3_client.delete_object(
                Bucket=S3_BUCKET_NAME,
                Key=f"{file_name}.{file_extension}"
            )
        except:
            pass
    
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/images")
async def delete_image(
    name: str,
    db: Session = Depends(get_db)
):
    try:
        # Get image from database
        image = db.query(Image).filter(Image.name == name).first()
        if not image:
            raise HTTPException(status_code=404, detail=f"Image with name {name} not found")
        
        # Delete from S3
        try:
            s3_client.delete_object(
                Bucket=S3_BUCKET_NAME,
                Key=f"{image.name}.{image.file_extension}"
            )
        except Exception as s3_error:
            raise HTTPException(status_code=500, detail=f"Error deleting from S3: {str(s3_error)}")
        
        # Delete from database
        db.delete(image)
        db.commit()
        
        return {"message": f"Image {name} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))