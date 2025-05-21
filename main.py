from fastapi import FastAPI, HTTPException
from metadata import get_imds_token, get_instance_identity_document

app = FastAPI()

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
