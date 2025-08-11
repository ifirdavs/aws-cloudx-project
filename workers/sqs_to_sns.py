import json, logging, threading, boto3, time, os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
SNS_UPLOAD_TOPIC_ARN = os.environ.get("SNS_UPLOAD_TOPIC_ARN")
SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL")
HOST = os.environ.get("HOST", "http://localhost:8000")

sns = boto3.client("sns", region_name=AWS_REGION)
sqs = boto3.client("sqs", region_name=AWS_REGION)

log = logging.getLogger("sqs-worker")

class SQSToSNSWorker:
    def __init__(self):
        self.queue_url = SQS_QUEUE_URL
        self.topic_arn = SNS_UPLOAD_TOPIC_ARN
        self.base_url = HOST
        self._stop = threading.Event()
        self._t: Optional[threading.Thread] = None

    def _build_plaintext(self, payload: dict) -> str:
        return (
            "An image has been uploaded.\n"
            f"Name: {payload.get('name')}\n"
            f"File extension: {payload.get('file_extension')}\n"
            f"Size (bytes): {payload.get('size')}\n"
            f"Uploaded at: {payload.get('uploaded_at')}\n"
            f"Download link: {self.base_url}/images?name={payload.get('name')}\n"
        )

    def _process_queue_until_empty(self):
        """Process all messages in the queue until it's empty"""
        messages_processed = 0
        
        while not self._stop.is_set():
            try:
                # Short polling - don't wait if no messages
                resp = sqs.receive_message(
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=10,
                    WaitTimeSeconds=1,  # Short wait to check if queue is empty
                    MessageAttributeNames=["All"],
                )
                
                msgs = resp.get("Messages", [])
                if not msgs:
                    # Queue is empty, break out of processing loop
                    break

                deletes = []
                for m in msgs:
                    payload = json.loads(m["Body"])
                    text = self._build_plaintext(payload)
                    file_extension = (payload.get("file_extension") or " ").lower()

                    sns.publish(
                        TopicArn=self.topic_arn,
                        Subject="Image upload",
                        Message=text,
                        MessageAttributes={
                            "file_extension": {"DataType": "String", "StringValue": file_extension}
                        },
                    )
                    deletes.append({"Id": m["MessageId"], "ReceiptHandle": m["ReceiptHandle"]})
                    messages_processed += 1

                if deletes:
                    sqs.delete_message_batch(QueueUrl=self.queue_url, Entries=deletes)
                    log.info(f"Processed batch of {len(deletes)} messages")

            except Exception as e:
                log.exception("SQS worker error during processing: %s", e)
                time.sleep(2)
        
        if messages_processed > 0:
            log.info(f"Finished processing {messages_processed} messages. Queue is now empty.")
    
    def _loop(self):
        while not self._stop.is_set():
            try:
                # Sleep for 20 seconds (or until stop signal)
                if self._stop.wait(timeout=20.0):
                    # Stop signal received during sleep
                    break
                
                # After sleep, process queue until empty
                log.debug("Checking queue for messages...")
                self._process_queue_until_empty()

            except Exception as e:
                log.exception("SQS worker error in main loop: %s", e)
                time.sleep(2)

        log.info("SQS worker loop stopped")

    def start(self):
        if self._t and self._t.is_alive():
            return
        self._t = threading.Thread(target=self._loop, name="sqs-to-sns", daemon=True)
        self._t.start()
        log.info("SQS worker thread started")

    def stop(self, timeout: float = 5.0):
        self._stop.set()
        if self._t:
            self._t.join(timeout)

# Optional: run the worker as a standalone process instead of inside FastAPI
if __name__ == "__main__":
    w = SQSToSNSWorker()
    w.start()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        w.stop()
