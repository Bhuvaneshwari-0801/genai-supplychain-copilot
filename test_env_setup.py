#!/usr/bin/env python3
"""
Test script to validate environment variable setup for GenAI SupplyChain Application
"""

import os
import sys
from dotenv import load_dotenv

def test_environment_setup():
    """Test that all environment variables are properly configured"""
    
    print("🧪 Testing Environment Variable Setup")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
    # Define required variables
    required_vars = {
        'AIRLABS_API_KEY': 'AirLabs API Key for flight data',
        'MAPBOX_API_KEY': 'MapBox API Key for routing',
        'TAVILY_API_KEY': 'Tavily API Key for web search',
        'SLACK_BOT_TOKEN': 'Slack Bot Token for notifications',
        'SES_SENDER': 'AWS SES sender email address',
        'SF_CLIENT_ID': 'Salesforce Client ID',
        'SF_CLIENT_SECRET': 'Salesforce Client Secret',
        'SF_USERNAME': 'Salesforce Username',
        'SF_PASSWORD': 'Salesforce Password',
        'SF_SECURITY_TOKEN': 'Salesforce Security Token'
    }
    
    optional_vars = {
        'AWS_REGION': 'AWS Region (default: us-east-1)',
        'SLACK_CHANNEL': 'Slack Channel (default: #supply-chain-v1)',
        'SF_DOMAIN': 'Salesforce Domain (default: login.salesforce.com)',
        'SF_API_VERSION': 'Salesforce API Version (default: v64.0)',
        'SUPPLIERS_TABLE': 'DynamoDB Suppliers Table (default: scm_suppliers)',
        'NEGOTIATION_TABLE': 'DynamoDB Negotiation Table (default: scm_negotiation)',
        'ROUTING_TABLE': 'DynamoDB Routing Table (default: scm_routing_details)',
        'MIN_SUSTAINABILITY_SCORE': 'Minimum Sustainability Score (default: 60)',
        'MIN_REPUTATION_SCORE': 'Minimum Reputation Score (default: 75)'
    }
    
    # Test required variables
    print("📋 Required Environment Variables:")
    missing_required = []
    
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if 'TOKEN' in var or 'SECRET' in var or 'PASSWORD' in var:
                display_value = f"{value[:8]}..." if len(value) > 8 else "***"
            else:
                display_value = value[:20] + "..." if len(value) > 20 else value
            print(f"  ✅ {var}: {display_value}")
        else:
            print(f"  ❌ {var}: NOT SET - {description}")
            missing_required.append(var)
    
    print(f"\n📋 Optional Environment Variables (with defaults):")
    for var, description in optional_vars.items():
        value = os.getenv(var)
        if value:
            print(f"  ✅ {var}: {value}")
        else:
            print(f"  ⚪ {var}: Using default - {description}")
    
    # Test configuration import
    print(f"\n🔧 Testing Configuration Import:")
    try:
        import config
        print("  ✅ config.py imported successfully")
        
        # Test validation function
        is_valid = config.validate_config()
        if is_valid:
            print("  ✅ Configuration validation passed")
        else:
            print("  ❌ Configuration validation failed")
            
    except ImportError as e:
        print(f"  ❌ Failed to import config.py: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Configuration error: {e}")
        return False
    
    # Test Salesforce authentication
    print(f"\n🔐 Testing Salesforce Authentication:")
    try:
        if all(os.getenv(var) for var in ['SF_CLIENT_ID', 'SF_CLIENT_SECRET', 'SF_USERNAME', 'SF_PASSWORD', 'SF_SECURITY_TOKEN']):
            auth_response = config.get_salesforce_auth()
            if auth_response.get('access_token'):
                print("  ✅ Salesforce authentication successful")
            else:
                print("  ❌ Salesforce authentication failed - no access token")
        else:
            print("  ⚠️ Salesforce credentials incomplete - skipping auth test")
    except Exception as e:
        print(f"  ❌ Salesforce authentication failed: {e}")
    
    # Summary
    print(f"\n📊 Summary:")
    if missing_required:
        print(f"  ❌ Missing {len(missing_required)} required variables: {', '.join(missing_required)}")
        print(f"  📝 Please update your .env file with the missing variables")
        return False
    else:
        print(f"  ✅ All required environment variables are configured")
        print(f"  🚀 Ready to run the GenAI SupplyChain application")
        return True

def create_sample_env_file():
    """Create a sample .env file with placeholder values"""
    
    sample_content = """# Environment Variables for GenAI SupplyChain Application
# Replace placeholder values with your actual credentials

# API Keys
AIRLABS_API_KEY=your_airlabs_api_key_here
MAPBOX_API_KEY=your_mapbox_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here

# Slack Configuration
SLACK_BOT_TOKEN=your_slack_bot_token_here
SLACK_CHANNEL=#supply-chain-v1

# Email Configuration
SES_SENDER=your_email@domain.com

# AWS Configuration
AWS_REGION=us-east-1

# Salesforce Configuration
SF_DOMAIN=login.salesforce.com
SF_API_VERSION=v64.0
SF_CLIENT_ID=your_salesforce_client_id_here
SF_CLIENT_SECRET=your_salesforce_client_secret_here
SF_USERNAME=your_salesforce_username_here
SF_PASSWORD=your_salesforce_password_here
SF_SECURITY_TOKEN=your_salesforce_security_token_here
RFQ_OBJ=RFQ__c

# DynamoDB Table Names
SUPPLIERS_TABLE=scm_suppliers
NEGOTIATION_TABLE=scm_negotiation
ROUTING_TABLE=scm_routing_details

# Decision Thresholds
MIN_SUSTAINABILITY_SCORE=60
MIN_REPUTATION_SCORE=75

# Gmail Configuration
GMAIL_CREDENTIALS_FILE=credentials.json
GMAIL_TOKEN_FILE=token.pickle
"""
    
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write(sample_content)
        print("📝 Created sample .env file - please update with your actual values")
    else:
        print("📝 .env file already exists")

if __name__ == "__main__":
    # Create sample .env if it doesn't exist
    create_sample_env_file()
    
    # Run tests
    success = test_environment_setup()
    
    if not success:
        print(f"\n❌ Environment setup incomplete. Please check the issues above.")
        sys.exit(1)
    else:
        print(f"\n✅ Environment setup complete and validated!")
        sys.exit(0)
