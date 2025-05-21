import requests

IMDS_BASE = "http://169.254.169.254"
TOKEN_URL = f"{IMDS_BASE}/latest/api/token"
IID_URL   = f"{IMDS_BASE}/latest/dynamic/instance-identity/document"
TOKEN_TTL = "21600"  # seconds

def get_imds_token() -> str:
    headers = {"X-aws-ec2-metadata-token-ttl-seconds": TOKEN_TTL}
    resp = requests.put(TOKEN_URL, headers=headers, timeout=2)
    resp.raise_for_status()
    return resp.text

def get_instance_identity_document(token: str) -> dict:
    headers = {"X-aws-ec2-metadata-token": token}
    resp = requests.get(IID_URL, headers=headers, timeout=2)
    resp.raise_for_status()
    return resp.json()
