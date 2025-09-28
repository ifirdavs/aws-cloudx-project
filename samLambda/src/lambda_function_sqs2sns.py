import os
import json
import logging
import boto3

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
SNS_UPLOAD_TOPIC_ARN = os.environ["SNS_UPLOAD_TOPIC_ARN"]  # required
HOST = os.getenv("HOST", "http://localhost:8000")          # used in email body

sns = boto3.client("sns", region_name=AWS_REGION)

log = logging.getLogger()
log.setLevel(logging.INFO)

def _build_plaintext(payload: dict) -> str:
    return (
        "An image has been uploaded.\n"
        f"Name: {payload.get('name')}\n"
        f"File extension: {payload.get('file_extension')}\n"
        f"Size (bytes): {payload.get('size')}\n"
        f"Uploaded at: {payload.get('uploaded_at')}\n"
        f"Download link: {HOST}/images?name={payload.get('name')}\n"
    )

def lambda_handler(event, context):
    """
    Processes SQS records → publishes one SNS message per record.
    Uses partial batch failure so only failed records are retried.
    """
    failures = []

    for record in event.get("Records", []):
        msg_id = record.get("messageId")
        try:
            payload = json.loads(record["body"])
            text = _build_plaintext(payload)

            file_extension = (payload.get("file_extension") or " ").lower()

            sns.publish(
                TopicArn=SNS_UPLOAD_TOPIC_ARN,
                Subject="Image upload",
                Message=text,
                MessageAttributes={
                    "file_extension": {"DataType": "String", "StringValue": file_extension}
                },
            )
            log.info("Published SNS for messageId=%s name=%s", msg_id, payload.get("name"))

        except Exception as e:
            log.exception("Failed to process messageId=%s: %s", msg_id, e)
            if msg_id:
                failures.append({"itemIdentifier": msg_id})

    # SQS/Lambda partial batch response contract
    return {"batchItemFailures": failures}
