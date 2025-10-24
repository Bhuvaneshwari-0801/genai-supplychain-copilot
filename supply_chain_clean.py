#!/usr/bin/env python
# coding: utf-8

# Import configuration
from config import *
import config

from strands import Agent, tool
from strands.models import BedrockModel
import time
import uuid
from datetime import datetime, timezone
import json
import requests
import boto3
import pandas as pd
import sys
import math
from io import StringIO

# Gmail Integration Functions
import pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import base64
import email

import slack_sdk
from botocore.exceptions import ClientError
from strands.tools import tool
from strands.models.bedrock import BedrockModel
from urllib.parse import quote
from geopy.distance import geodesic

from IPython.display import HTML, display
from route_mapper_clean import create_route_map

# Validate configuration
config.validate_config()

# Model configurations
claude_sonnet_model = BedrockModel(model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0", temperature=0.0)
claude_haiku_model = BedrockModel(model_id="us.anthropic.claude-3-5-haiku-20241022-v1:0", temperature=0.0)

nova_pro_model = BedrockModel(
    model_id="us.amazon.nova-pro-v1:0",
    temperature=0.0,
    streaming=False
)

print(f"✅ Models configured: Nova Pro, Claude Haiku")

def authenticate_gmail():
    """Authenticate Gmail with manual OAuth for SageMaker"""
    creds = None
    
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except:
                creds = None
        
        if not creds:
            if not os.path.exists(CREDENTIALS_FILE):
                return None
            
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
            auth_url, _ = flow.authorization_url(prompt='consent')
            
            auth_code = input(f"Open URL: {auth_url}\nEnter code: ").strip()
            
            try:
                flow.fetch_token(code=auth_code)
                creds = flow.credentials
            except Exception as e:
                return None
        
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    
    return build('gmail', 'v1', credentials=creds)

def get_latest_email(service, query='in:inbox', max_results=1):
    """Fetch latest email from Gmail"""
    try:
        results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
        messages = results.get('messages', [])
        
        if not messages:
            return None
        
        message_id = messages[0]['id']
        message = service.users().messages().get(userId='me', id=message_id, format='full').execute()
        return message
        
    except Exception as e:
        return None

def extract_email_content(message):
    """Extract readable content from Gmail message"""
    if not message:
        return None
    
    try:
        payload = message['payload']
        headers = payload.get('headers', [])
        
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')
        
        body = extract_body(payload)
        
        email_content = f"From: {sender}\nDate: {date}\nSubject: {subject}\n\n{body}".strip()
        return email_content
        
    except Exception as e:
        return None

def extract_body(payload):
    """Extract body text from email payload"""
    body = ""
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                data = part['body']['data']
                body = base64.urlsafe_b64decode(data).decode('utf-8')
                break
    else:
        if payload['mimeType'] == 'text/plain':
            data = payload['body']['data']
            body = base64.urlsafe_b64decode(data).decode('utf-8')
    return body

print("✅ Gmail integration functions added")

# Initialize Salesforce connection
try:
    oauth_response = config.get_salesforce_auth()
    access_token = oauth_response['access_token']
    instance_url = oauth_response['instance_url']
    print(f"✅ Connected to Salesforce: {instance_url}")
except Exception as e:
    print(f"⚠️ Salesforce connection failed: {e}")
    access_token = None
    instance_url = None
