"""
Configuration module for GenAI SupplyChain Application
Loads environment variables and provides configuration constants
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Keys
AIRLABS_API_KEY = os.getenv('AIRLABS_API_KEY')
MAPBOX_API_KEY = os.getenv('MAPBOX_API_KEY') 
TAVILY_API_KEY = os.getenv('TAVILY_API_KEY')

# Slack Configuration
SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')
SLACK_CHANNEL = os.getenv('SLACK_CHANNEL', '#supply-chain-v1')

# AWS Configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
SES_SENDER = os.getenv('SES_SENDER')

# Salesforce Configuration
SF_DOMAIN = os.getenv('SF_DOMAIN', 'login.salesforce.com')
SF_API_VERSION = os.getenv('SF_API_VERSION', 'v64.0')
SF_CLIENT_ID = os.getenv('SF_CLIENT_ID')
SF_CLIENT_SECRET = os.getenv('SF_CLIENT_SECRET')
SF_USERNAME = os.getenv('SF_USERNAME')
SF_PASSWORD = os.getenv('SF_PASSWORD')
SF_SECURITY_TOKEN = os.getenv('SF_SECURITY_TOKEN')
RFQ_OBJ = os.getenv('RFQ_OBJ', 'RFQ__c')

# DynamoDB Table Names
SUPPLIERS_TABLE = os.getenv('SUPPLIERS_TABLE', 'scm_suppliers')
NEGOTIATION_TABLE = os.getenv('NEGOTIATION_TABLE', 'scm_negotiation')
ROUTING_TABLE = os.getenv('ROUTING_TABLE', 'scm_routing_details')
TABLE_NAME = os.getenv('ROUTING_TABLE', 'scm_routing_details')

# Decision Thresholds
MIN_SUSTAINABILITY_SCORE = int(os.getenv('MIN_SUSTAINABILITY_SCORE', '60'))
MIN_REPUTATION_SCORE = int(os.getenv('MIN_REPUTATION_SCORE', '75'))

# Gmail Configuration
CREDENTIALS_FILE = os.getenv('GMAIL_CREDENTIALS_FILE', 'credentials.json')
TOKEN_FILE = os.getenv('GMAIL_TOKEN_FILE', 'token.pickle')
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def validate_config():
    """Validate that all required environment variables are set"""
    required_vars = [
        'AIRLABS_API_KEY', 'MAPBOX_API_KEY', 'TAVILY_API_KEY', 'SLACK_BOT_TOKEN',
        'SES_SENDER', 'SF_CLIENT_ID', 'SF_CLIENT_SECRET', 'SF_USERNAME', 
        'SF_PASSWORD', 'SF_SECURITY_TOKEN'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"⚠️ Missing environment variables: {', '.join(missing_vars)}")
        print("Please check your .env file or environment configuration")
        return False
    
    print("✅ All required environment variables are configured")
    return True

def get_salesforce_auth():
    """Get Salesforce authentication token"""
    import requests
    
    url = f"https://{SF_DOMAIN}/services/oauth2/token"
    data = {
        'grant_type': 'password',
        'client_id': SF_CLIENT_ID,
        'client_secret': SF_CLIENT_SECRET,
        'username': SF_USERNAME,
        'password': SF_PASSWORD + SF_SECURITY_TOKEN
    }
    
    response = requests.post(url, data=data)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Salesforce OAuth failed: {response.text}")
