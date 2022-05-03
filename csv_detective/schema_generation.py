from botocore.exceptions import ClientError
from datetime import datetime
import filecmp
import json
import os
import tempfile

from csv_detective.s3_utils import get_s3_client, download_from_minio, upload_to_minio

def generate_table_schema(analysis_report: dict, url: str, bucket="tableschema", key=None, minio_user=None, minio_pwd=None) -> None:
    fields = [{"name": header,
        "description": "",
        "example": "",
        "type": field_report["format"],
        "constraints": {
          "required": False
        }
    } for header, field_report in analysis_report["columns"].items()]

    schema = {
        "$schema": "https://frictionlessdata.io/schemas/table-schema.json",
        "name": "",
        "title": "",
        "description": "",
        "countryCode": "FR",
        "homepage": "",
        "path": "",
        "resources": [
          {
            "title": "",
            "path": ""
          }
        ],
        "sources": [],
        "created": datetime.today().strftime('%Y-%m-%d'),
        "lastModified": datetime.today().strftime('%Y-%m-%d'),
        "version": "0.0.0",
        "contributors": [
          {
            "title": "Table schema bot",
            "email": "",
            "organisation": "Etalab",
            "role": "author"
          },
        ],
        "fields": fields,
        "missingValues": [
          ""
        ]
    }

    # Create bucket if does not exist
    client = get_s3_client(url, minio_user, minio_pwd)
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        client.create_bucket(Bucket=bucket)

    tableschema_file = tempfile.NamedTemporaryFile(delete=False)
    with open(tableschema_file.name, 'w') as fp:
        json.dump(schema, fp,  indent=4)

    tableschema_objects = client.list_objects(Bucket=bucket, Prefix=key, Delimiter='/')
    if 'Contents' in tableschema_objects:
        tableschema_keys = [tableschema['Key'] for tableschema in client.list_objects(Bucket=bucket, Prefix=key, Delimiter='/')['Contents']]
        tableschema_versions = [os.path.splitext(tableschema_key)[0].split('_')[-1] for tableschema_key in tableschema_keys]
        latest_version = max(tableschema_versions)

        with tempfile.NamedTemporaryFile() as latest_schema_file:
            with open(latest_schema_file.name, 'w') as fp:
                download_from_minio(url, bucket, f"{key}_{latest_version}.json", latest_schema_file.name, minio_user, minio_pwd)
                # Check if files are different
                if not filecmp.cmp(tableschema_file.name, latest_schema_file.name):
                    latest_version_split = latest_version.split('.')
                    new_version = latest_version_split[0] + '.' + latest_version_split[1] + '.' + str(int(latest_version_split[2]) + 1)
                    upload_to_minio(url, bucket, f'{key}_{new_version}.json', tableschema_file.name, minio_user, minio_pwd)
    else:
        upload_to_minio(url, bucket, f'{key}_0.0.1.json', tableschema_file.name, minio_user, minio_pwd)

    

    os.unlink(tableschema_file.name)
