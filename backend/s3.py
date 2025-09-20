import boto3

s3 = boto3.client("s3")  # uses ~/.aws/credentials or env vars
bucket = "echomind-pdf-storage"

# Upload PDF file
def upload_pdf(file_path, s3_key=None):
    if s3_key is None:
        s3_key = file_path.split('/')[-1]  # use filename as key
    
    try:
        s3.upload_file(file_path, bucket, s3_key)
        print(f"Successfully uploaded {file_path} to s3://{bucket}/{s3_key}")
        return True
    except Exception as e:
        print(f"Error uploading file: {e}")
        return False

# Example usage:
# upload_pdf("path/to/your/document.pdf")
# upload_pdf("local_file.pdf", "medical-records/patient-123.pdf")

# List existing files
resp = s3.list_objects_v2(Bucket=bucket)
for obj in resp.get("Contents", []):
    print(obj["Key"])