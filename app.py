import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from azure.storage.blob import BlobServiceClient, BlobClient
from azure.storage.blob import generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta, timezone
import re
from urllib.parse import quote

app = Flask(__name__)
CORS(app)
# Azure Blob Storage credentials
AZURE_STORAGE_CONNECTION_STRING = os.getenv('AZURE_WEBVIEW_STORAGE_CONNECTION_STRING')
BLOB_CONTAINER_NAME = 'weez-file-webview'

# Initialize Azure Blob Service Client
blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)


# **1. Upload File Automatically when Opened**
@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        username = request.form.get('username')
        file = request.files.get('file')  # File received from the client

        if not username or not file:
            return jsonify({'error': 'Username or file missing'}), 400

        filename = file.filename  # Get the filename
        blob_path = f"{username}/{filename}"  # Store under username directory

        # Get container client & upload file to Azure Blob Storage
        container_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)
        blob_client = container_client.get_blob_client(blob_path)

        blob_client.upload_blob(file, overwrite=True)  # Upload file

        return jsonify({'message': 'File uploaded successfully', 'filename': filename}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# **2. Generate SAS Token for File**
def parse_connection_string(conn_str):
    return {
        "account_name": re.search(r"AccountName=([^;]+)", conn_str).group(1),
        "account_key": re.search(r"AccountKey=([^;]+)", conn_str).group(1)
    }

storage_config = parse_connection_string(os.getenv('AZURE_WEBVIEW_STORAGE_CONNECTION_STRING'))

@app.route('/generate-sas', methods=['POST'])
def generate_sas():
    try:
        # Handle both JSON and form data
        data = request.get_json(silent=True) or request.form
        username = data.get('username', '').strip()
        filename = data.get('filename', '').strip()

        if not username or not filename:
            return jsonify({'error': 'Username and filename required'}), 400

        
        blob_path = f"{username}/{filename}"

        # Verify blob exists
        blob_client = blob_service_client.get_blob_client(BLOB_CONTAINER_NAME, blob_path)
        if not blob_client.exists():
            return jsonify({'error': 'File not found in storage'}), 404

        # Generate SAS token with explicit permissions
        sas_token = generate_blob_sas(
            account_name=storage_config['account_name'],
            container_name=BLOB_CONTAINER_NAME,
            blob_name=blob_path,
            account_key=storage_config['account_key'],
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + timedelta(hours=1)
        )

        sas_url = f"{blob_client.url}?{sas_token}"
        return jsonify({'sas_url': sas_url}), 200

    except Exception as e:
        app.logger.error(f'SAS Generation Error: {str(e)}')
        return jsonify({'error': 'Failed to generate access URL', 'details': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, threaded=True)
