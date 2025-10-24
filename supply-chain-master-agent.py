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
import os
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
from route_mapper import create_route_map

# Validate configuration
config.validate_config()







# Configuration loaded from config.py









# Model configurations
claude_sonnet_model = BedrockModel(model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0", temperature=0.0)
claude_haiku_model = BedrockModel(model_id="us.anthropic.claude-3-5-haiku-20241022-v1:0", temperature=0.0)
#nova_pro_model = BedrockModel(model_id="us.amazon.nova-pro-v1:0", temperature=0.0)


# BEFORE (example)
#nova_pro_model = BedrockModel(model_id="us.amazon.nova-pro-v1:0", temperature=0.0)

# AFTER (disable streaming only for the orchestrator)
nova_pro_model = BedrockModel(
    model_id="us.amazon.nova-pro-v1:0",
    temperature=0.0,
    streaming=False  # <-- critical change to avoid toolUse/toolResult ID mismatches
)


print(f"✅ Models configured: Nova Pro, Claude Haiku")



SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.pickle'

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



# Salesforce and AWS configuration for Agent1
SF_DOMAIN = "login.salesforce.com"
SF_API_VERSION = "v64.0"





RFQ_OBJ = "RFQ__c"

def sf_oauth_username_password():
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
        raise Exception(f"OAuth failed: {response.text}")

oauth_response = sf_oauth_username_password()
access_token = oauth_response['access_token']
instance_url = oauth_response['instance_url']
print(f"✅ Connected to Salesforce: {instance_url}")



@tool
def validate_agent1_format(output_text: str) -> str:
    required_fields = ['"sku":', '"quantity":', '"priority":', '"rfq_id":', '"company_name":', '"shipping_address":', '"destination_city":', '"destination_country":', '"industry":', '"website":', '"phone":', '"expected_price":', '"notes":', '"target_delivery":']
    
    missing_fields = []
    for field in required_fields:
        if field not in output_text:
            missing_fields.append(field.replace('"', '').replace(':', ''))
    
    if missing_fields:
        return f"VALIDATION FAILED: Missing fields: {', '.join(missing_fields)}"
    
    return "VALIDATION PASSED: All required fields present"



# Agent2 tools 
@tool
def extract_category_from_sku(sku: str) -> str:
    """Extract Category from SKU"""
    try:
        category = sku.split('-')[0] if '-' in sku else sku[:3].upper()
        return json.dumps({"success": True,
                           "category": category,
                           "sku": sku,
                            "extraction_method": f"Split SKU '{sku}' at first hyphen delimiter, extracted prefix '{category}' representing product category",
                            "extraction_source": f"SKU prefix extraction from '{sku}' - split at hyphen delimiter", 
                            "category_details": f"Category '{category}' extracted from SKU '{sku}' representing product family classification",
                            "parsing_logic": "Split SKU at first hyphen (-) to isolate category prefix"
                          })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

@tool
def get_filtered_suppliers(category: str, destination_country: str, min_rating: int = 4) -> str:
    """Get zfiltered suppliers based on criteria"""
    try:
        dynamodb = boto3.client('dynamodb', region_name='us-east-1')
        response = dynamodb.query(
            TableName='scm_suppliers',
            IndexName='gsi_category',
            KeyConditionExpression='category = :cat',
            ExpressionAttributeValues={':cat': {'S': category}},
            Limit=50
        )
        
        suppliers = []
        for item in response['Items']:
            rating = int(item.get('rating', {}).get('N', '0'))
            country = item.get('country', {}).get('S', '')
            
            if rating >= min_rating and country == destination_country:
                suppliers.append({
                    'supplier_id': item['supplier_id']['S'],
                    'name': item['name']['S'],
                    'email': item['email']['S'],
                    'city': item['city']['S'],
                    'country': country,
                    'category': item['category']['S'],
                    'rating': rating,
                })
        return json.dumps({"success": True, "suppliers": suppliers, "count": len(suppliers)})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e), "suppliers": []})

@tool
def generate_email_with_llm(supplier: dict, rfq_details: dict) -> str:
    """Generate email using LLM with mandatory quotation requirements."""
    try:
        prompt = f"""
        Generate a professional RFQ email for:
        
        SUPPLIER: {supplier['name']} (Rating: {supplier['rating']}/5)
        LOCATION: {supplier['city']}, {supplier['country']}
        
        RFQ DETAILS:
        - SKU: {rfq_details['sku']}
        - Quantity: {rfq_details['quantity']}
        - Priority: {rfq_details.get('priority', 'Medium')}
        - RFQ ID: {rfq_details.get('rfq_id', 'N/A')}
        - Company: {rfq_details['company_name']}
        - Shipping Address: {rfq_details.get('shipping_address', 'N/A')}
        
        MANDATORY: Include this EXACT section in the email:
        
        Please provide the following in your quotation:
        1. Unit price and total cost
        2. Available quantity and lead time
        3. Payment terms
        4. Warranty information
        5. Shipping terms and estimated delivery timeline
        6. Technical specifications and certification details
        7. Any applicable volume discounts
        8. Minimum order quantity (if applicable)
        9. Quote validity period
        
        MANDATORY SIGNATURE FORMAT:
        Best regards,
        Procurement Head
        {rfq_details.get('company_name')}
        
        Generate professional email with subject line. Be creative with personalization but MUST include the exact quotation requirements and signature format above.
        """
        
        email_agent = Agent(
            model=claude_haiku_model,
            system_prompt="Generate professional, personalized RFQ emails. Always include the mandatory quotation requirements and signature format exactly as specified."
        )
        
        response = email_agent(prompt)
        email_content = str(response)
        
        return json.dumps({"success": True, "email_content": email_content, "supplier_name": supplier['name']})
        
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

@tool
def analyze_email_sentiment_with_agent(email_content: str) -> str:
    """Analyze email sentiment using AWS Comprehend."""
    try:
        comprehend = boto3.client('comprehend', region_name='us-east-1')
        response = comprehend.detect_sentiment(
            Text=email_content[:5000],
            LanguageCode='en'
        )
        
        sentiment = response['Sentiment']
        confidence = response['SentimentScore'][sentiment.title()]
        
        appropriate = sentiment in ['POSITIVE', 'NEUTRAL'] and confidence > 0.7
        
        return json.dumps({
            "success": True,
            "sentiment": sentiment,
            "is_appropriate": appropriate,
            "confidence": round(confidence * 100, 2),
            "recommendation": "SEND" if appropriate else "REVIEW_REQUIRED",
            "analysis": f"Email sentiment is {sentiment} with {round(confidence * 100, 2)}% confidence",
            "service_used": "AWS Comprehend sentiment detection service",
            "analysis_details": f"Email content analyzed using AWS Comprehend sentiment detection service. Sentiment classification: {sentiment} with {round(confidence * 100, 2)}% confidence score",
            "service_details": "AWS Comprehend Natural Language Processing service for sentiment analysis",
            "confidence_breakdown": f"Sentiment confidence: {round(confidence * 100, 2)}% - Classification threshold: 70%"
        })
        
    except Exception as e:
        return json.dumps({"success": False, "error": str(e), "sentiment": "UNKNOWN", "is_appropriate": True, "recommendation": "SEND"})

@tool
def ses_send_email(to_emails: list, subject: str, body_text: str) -> str:
    """Send email via SES."""
    try:
        ses = boto3.client('ses', region_name='us-east-1')
        response = ses.send_email(
            Source=SES_SENDER,
            Destination={'ToAddresses': to_emails},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': body_text}}
            }
        )
        
        return json.dumps({
            "success": True,
            "message_id": response['MessageId'],
            "to_emails": to_emails,
            "subject": subject,
            "status": "SENT",
            "confirmation": f"Email successfully sent to {', '.join(to_emails)} with Message ID: {response['MessageId']}",
            "delivery_status": "Email dispatched via AWS SES to supplier for RFQ response",
            "delivery_confirmation": f"Email successfully sent to {', '.join(to_emails)} with Message ID: {response['MessageId']}",
            "supplier_notification": f"RFQ notification delivered to supplier via AWS SES service"
        })

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})



# Agent3 Tools - Quotation Normalization and Analysis
@tool
def read_agent2_output(agent2_json_output: str) -> str:
    """Read Agent2 output and return supplier details"""
    try:
        return agent2_json_output
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

@tool
def insert_supplier_data(table_name: str, supplier_data: dict) -> str:
    """Insert supplier data into DynamoDB negotiation table"""
    try:
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.Table(table_name)
        
        response = table.scan(
            FilterExpression='rfq_id = :rfq AND supplier_id = :supplier',
            ExpressionAttributeValues={':rfq': supplier_data['rfq_id'], ':supplier': supplier_data['supplier_id']}
        )
        
        if response['Items']:
            negotiation_id = response['Items'][0]['negotiation_id']
            return json.dumps({"success": True, "negotiation_id": negotiation_id, "action": "updated"})
        else:
            negotiation_id = str(uuid.uuid4())
            item = {
                'negotiation_id': negotiation_id,
                'rfq_id': supplier_data['rfq_id'],
                'supplier_id': supplier_data['supplier_id'],
                'supplier_name': supplier_data['name'],
                'supplier_email': supplier_data['email'],
                'created_date': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat()
            }
            table.put_item(Item=item)
            return json.dumps({"success": True, "negotiation_id": negotiation_id, "action": "created"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

@tool
def find_supplier_documents(bucket_name: str, rfq_id: str, supplier_name: str) -> str:
    """Find supplier documents in S3"""
    try:
        s3 = boto3.client('s3', region_name='us-east-1')
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=f"{rfq_id}/")
        
        documents = []
        if 'Contents' in response:
            for obj in response['Contents']:
                supplier_keywords = supplier_name.lower().split()[:2]
                if all(keyword in obj['Key'].lower() for keyword in supplier_keywords):
                    file_ext = obj['Key'].split('.')[-1].lower() if '.' in obj['Key'] else 'unknown'
                    documents.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat(),
                        'format': file_ext
                    })
        
        return json.dumps({"success": True, "documents": documents, "count": len(documents)})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

@tool
def extract_text_from_s3_document(bucket_name: str, object_key: str) -> str:
    try:
        file_ext = object_key.split('.')[-1].lower()
        s3_client = boto3.client('s3', region_name='us-east-1')
        if file_ext == 'csv':
            response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
            content = response['Body'].read().decode('utf-8')
            return json.dumps({"success": True, "text": content})
        else:
            textract_client = boto3.client('textract', region_name='us-east-1')
            response = textract_client.detect_document_text(
                Document={'S3Object': {'Bucket': bucket_name, 'Name': object_key}}
            )
            text_blocks = [block['Text'] for block in response['Blocks'] if block['BlockType'] == 'LINE']
            extracted_text = '\n'.join(text_blocks)
            return json.dumps({"success": True, "text": extracted_text})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

@tool
def parse_quotation_fields(quotation_text: str) -> str:
    """Parse quotation fields using LLM"""
    try:
        prompt = f"""Extract quotation fields from: {quotation_text}
        Return JSON with: unit_price, total_price, quantity, delivery_date, payment_terms, warranty"""
        
        bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
        response = bedrock.invoke_model(
            modelId="us.anthropic.claude-3-5-haiku-20241022-v1:0",
            body=json.dumps({"anthropic_version": "bedrock-2023-05-31", "max_tokens": 1000, "messages": [{"role": "user", "content": prompt}]})
        )
        
        result = json.loads(response['body'].read())
        parsed_data = result['content'][0]['text']
        
        return json.dumps({"success": True, "parsed_fields": parsed_data})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

@tool
def get_wikipedia_data(company_name: str) -> str:
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; Bot/1.0)'}
        
        # Enhanced name patterns for better matching
        base_name = company_name.replace(' Inc', '').replace(' Corp', '').replace(' Corporation', '').replace(' Ltd', '').replace(' LLC', '').replace(' Co.', '').replace(' Company', '')
        
        name_variants = [
            company_name,
            base_name,
            company_name.replace(' ', '_'),
            base_name.replace(' ', '_'),
            company_name.split()[0] if ' ' in company_name else company_name,
            f"{base_name} (company)",
            f"{company_name} (company)",
            company_name.replace('&', 'and'),
            base_name.replace('&', 'and'),
            company_name.upper(),
            company_name.lower(),
            company_name.title()
        ]
        
        # Remove duplicates while preserving order
        seen = set()
        unique_variants = []
        for variant in name_variants:
            if variant not in seen:
                seen.add(variant)
                unique_variants.append(variant)
        
        for variant in unique_variants:
            wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{variant.replace(' ', '_')}"
            response = requests.get(wiki_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                wiki_data = response.json()
                extract = wiki_data.get('extract', '').lower()
                
                # Skip disambiguation pages and redirect pages
                if ('may refer to' not in extract and 
                    'disambiguation' not in extract and
                    'redirects here' not in extract and
                    len(wiki_data.get('extract', '')) > 50):
                    
                    return json.dumps({
                        "success": True,
                        "wikipedia_url": wiki_data.get('content_urls', {}).get('desktop', {}).get('page', ''),
                        "extract": wiki_data.get('extract', '')
                    })
        
        return json.dumps({"success": False, "error": "No suitable Wikipedia page found"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

@tool
def get_tavily_data(company_name: str) -> str:
    try:
        # Tavily API key
        api_key = TAVILY_API_KEY
        
        # Use Tavily REST API directly
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": api_key,
            "query": f"{company_name} company sustainability ESG reputation",
            "max_results": 3
        }
        
        response = requests.post(url, json=payload, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            company_info = ""
            sources = []
            
            for result in data.get('results', []):
                company_info += result.get('content', '') + "\n\n"
                sources.append(result.get('url', ''))
            
            return json.dumps({
                "success": True,
                "company_info": company_info[:2000],
                "sources": sources
            })
        else:
            return json.dumps({"success": False, "error": f"API error: {response.status_code}"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

@tool
def analyze_sustainability_comprehensive(company_name: str, wikipedia_data: str, tavily_data: str) -> str:
    try:
        # Combine both data sources
        wiki_info = json.loads(wikipedia_data) if wikipedia_data.startswith('{') else {'success': True, 'extract': wikipedia_data}
        tavily_info = json.loads(tavily_data) if tavily_data.startswith('{') else {'success': True, 'company_info': tavily_data}
        
        combined_text = ""
        if wiki_info.get('success'):
            combined_text += f"Wikipedia: {wiki_info.get('extract', '')[:800]}\n\n"
        if tavily_info.get('success'):
            combined_text += f"Current Web Sources: {tavily_info.get('company_info', '')[:800]}"
        
        prompt = f"""Analyze sustainability practices of {company_name} using comprehensive data from multiple sources:

{combined_text}

Provide sustainability score 0-100 considering:
- Environmental initiatives and clean energy focus
- Carbon reduction efforts and green technologies
- Renewable energy products or sustainable practices
- Industry leadership in sustainability
- ESG ratings and certifications

Respond ONLY with valid JSON:
{{"score": 75, "explanation": "Brief explanation based on combined sources"}}"""
        
        bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
        response = bedrock.invoke_model(
            modelId="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 300, "temperature": 0, "temperature": 0,
                "messages": [{"role": "user", "content": prompt}]
            })
        )
        
        result = json.loads(response['body'].read())
        analysis = json.loads(result['content'][0]['text'].strip())
        score = analysis.get('score')
        explanation = analysis.get('explanation')
        print(f"Comprehensive sustainability analysis for {company_name}: Score {score}/100")
        print(f"Justification: {explanation}")
        
        return json.dumps({
            "success": True,
            "analysis": {
                "score": score,
                "explanation": explanation,
                "data_sources": ["Wikipedia", "Tavily"]
            }
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

@tool
def analyze_reputation_comprehensive(company_name: str, wikipedia_data: str, tavily_data: str) -> str:
    try:
        # Combine both data sources
        wiki_info = json.loads(wikipedia_data) if wikipedia_data.startswith('{') else {'success': True, 'extract': wikipedia_data}
        tavily_info = json.loads(tavily_data) if tavily_data.startswith('{') else {'success': True, 'company_info': tavily_data}
        
        combined_text = ""
        if wiki_info.get('success'):
            combined_text += f"Wikipedia: {wiki_info.get('extract', '')[:800]}\n\n"
        if tavily_info.get('success'):
            combined_text += f"Current Web Sources: {tavily_info.get('company_info', '')[:800]}"
        
        prompt = f"""Analyze business reputation of {company_name} using comprehensive data from multiple sources:

{combined_text}

Provide reputation score 0-100 considering:
- Market leadership and industry recognition
- Company history, founding date, and longevity
- Innovation, awards, and achievements
- Market position and business reputation
- Financial stability and performance

Respond ONLY with valid JSON:
{{"reputation_rating": 80, "explanation": "Brief explanation based on combined sources"}}"""
        
        bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
        response = bedrock.invoke_model(
            modelId="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 300, "temperature": 0, "temperature": 0,
                "messages": [{"role": "user", "content": prompt}]
            })
        )
        
        result = json.loads(response['body'].read())
        analysis = json.loads(result['content'][0]['text'].strip())
        rating = analysis.get('reputation_rating')
        explanation = analysis.get('explanation')
        print(f"Comprehensive reputation analysis for {company_name}: Rating {rating}/100")
        print(f"Justification: {explanation}")
        
        return json.dumps({
            "success": True,
            "analysis": {
                "reputation_rating": rating,
                "explanation": explanation,
                "data_sources": ["Wikipedia", "Tavily"]
            }
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

@tool
def update_supplier_scores(table_name: str, negotiation_id: str, sustainability_data: dict, reputation_data: dict, wikipedia_url: str) -> str:
    try:
        ddb = boto3.resource('dynamodb', region_name='us-east-1')
        table = ddb.Table(table_name)
        
        # Handle direct LLM response data
        if 'score' in sustainability_data:
            sustainability_analysis = sustainability_data
        else:
            sustainability_analysis = sustainability_data.get('analysis', {}) if sustainability_data.get('success') else {}
        
        if 'reputation_rating' in reputation_data:
            reputation_analysis = reputation_data
        else:
            reputation_analysis = reputation_data.get('analysis', {}) if reputation_data.get('success') else {}
        
        sustainability_score = sustainability_analysis.get('score')
        sustainability_explanation = sustainability_analysis.get('explanation')
        reputation_rating = reputation_analysis.get('reputation_rating')
        reputation_explanation = reputation_analysis.get('explanation')
        
        print(f"Updating supplier scores: Sustainability {sustainability_score}, Reputation {reputation_rating}")
        
        table.update_item(
            Key={'negotiation_id': negotiation_id},
            UpdateExpression='SET sustainability_score = :score, sustainability_explanation = :s_exp, reputation_score = :rep_score, reputation = :rep, reputation_explanation = :r_exp, wikipedia_url = :w_url, last_updated = :timestamp',
            ExpressionAttributeValues={
                ':score': int(sustainability_score) if sustainability_score else 0,
                ':s_exp': str(sustainability_explanation) if sustainability_explanation else '',
                ':rep_score': int(reputation_rating) if reputation_rating else 0,
                ':rep': 'Analyzed',
                ':r_exp': str(reputation_explanation) if reputation_explanation else '',
                ':w_url': str(wikipedia_url),
                ':timestamp': datetime.now(timezone.utc).isoformat()
            }
        )
        return json.dumps({"success": True, "negotiation_id": negotiation_id})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

@tool
def update_supplier_quotation(table_name: str, negotiation_id: str, quotation_text: str, parsed_fields: dict = None) -> str:
    """Update supplier quotation in DynamoDB"""
    try:
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.Table(table_name)
        
        update_expr = 'SET quotation_text = :text, last_updated = :timestamp'
        expr_values = {':text': quotation_text, ':timestamp': datetime.now().isoformat()}
        
        if parsed_fields:
            update_expr += ', parsed_fields = :fields'
            expr_values[':fields'] = parsed_fields
        
        table.update_item(
            Key={'negotiation_id': negotiation_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values
        )
        
        return json.dumps({"success": True, "message": "Quotation updated successfully"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

print("✅ Agent3 tools created")



# Agent4 Tools
@tool
def get_salesforce_rfq_data(rfq_id: str) -> str:
    """
    Retrieve RFQ details from Salesforce using RFQ ID.
    Returns comprehensive RFQ requirements and specifications.
    MUST fetch from Salesforce only - no fallback.
    """
    try:
        # Salesforce config (matching working reference)
        SF_DOMAIN = "login.salesforce.com"
        RFQ_OBJ = "RFQ__c"
        
        # OAuth using exact working pattern from agent1_RFQ_update_fixed.ipynb
        def sf_oauth_username_password():
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
                raise Exception(f"OAuth failed: {response.text}")
        
        # Authenticate
        oauth_response = sf_oauth_username_password()
        access_token = oauth_response['access_token']
        instance_url = oauth_response['instance_url']
        
        # Query RFQ using exact working pattern from agent1
        url = f"{instance_url}/services/data/{SF_API_VERSION}/query"
        headers = {"Authorization": f"Bearer {access_token}"}
        query = f"SELECT Id, Name, Account__c, SKU__c, Quantity__c, Target_Delivery__c, Status__c, Priority__c, Currency__c, Expected_Unit_Price__c, Notes__c FROM {RFQ_OBJ} WHERE External_Ref__c = '{rfq_id}' LIMIT 1"
        
        response = requests.get(url, headers=headers, params={"q": query})
        
        if response.status_code == 200:
            result = response.json()
            if result.get('totalSize', 0) > 0:
                rfq_record = result['records'][0]
            else:
                return json.dumps({"success": False, "error": f"RFQ {rfq_id} not found in Salesforce"})
        else:
            return json.dumps({"success": False, "error": f"Salesforce query failed: {response.text}"})
        
        # Get Account details for company name
        account_id = rfq_record.get('Account__c', '')
        company_name = ""
        if account_id:
            account_query = f"SELECT Id, Name FROM Account WHERE Id = '{account_id}' LIMIT 1"
            account_response = requests.get(url, headers=headers, params={"q": account_query})
            if account_response.status_code == 200:
                account_result = account_response.json()
                if account_result.get('totalSize', 0) > 0:
                    company_name = account_result['records'][0].get('Name', '')
        else:
            return json.dumps({"success": False, "error": f"Salesforce query failed: {response.text}"})
        
        # Process Salesforce data
        rfq_data = {
            "success": True,
            "rfq_data": {
                "rfq_id": rfq_record.get('Id', ''),
                "name": rfq_record.get('Name', ''),
                "company_name": company_name,
                "sku": rfq_record.get('SKU__c', ''),
                "quantity": rfq_record.get('Quantity__c', 0),
                "expected_price": rfq_record.get('Expected_Unit_Price__c', 0),
                "delivery_date": rfq_record.get('Target_Delivery__c', ''),
                "status": rfq_record.get('Status__c', ''),
                "priority": rfq_record.get('Priority__c', ''),
                "currency": rfq_record.get('Currency__c', ''),
                "notes": rfq_record.get('Notes__c', ''),
                "source": "salesforce"
            }
        }
        
        return json.dumps(rfq_data)
        
    except Exception as e:
        return json.dumps({"success": False, "error": f"Salesforce integration error: {str(e)}"})

@tool
def get_supplier_analysis_data(supplier_ids: list) -> str:
    """
    Extract comprehensive supplier data from scm_negotiation table.
    Returns all columns including quotation details, sustainability, and reputation scores.
    """
    try:
        dynamodb = boto3.client('dynamodb', region_name='us-east-1')
        suppliers_data = []
        
        for supplier_id in supplier_ids:
            response = dynamodb.query(
                TableName=NEGOTIATION_TABLE,
                IndexName='gsi_supplier_id',
                KeyConditionExpression='supplier_id = :sid',
                ExpressionAttributeValues={':sid': {'S': supplier_id}}
            )
            
            if response['Items']:
                item = response['Items'][0]
                
                supplier_data = {
                    "supplier_id": item.get('supplier_id', {}).get('S', ''),
                    "supplier_name": item.get('supplier_name', {}).get('S', ''),
                    "supplier_email": item.get('supplier_email', {}).get('S', ''),
                    "rfq_id": item.get('rfq_id', {}).get('S', ''),
                    "negotiation_id": item.get('negotiation_id', {}).get('S', ''),
                    
                    # Quotation fields
                    "currency": item.get('currency', {}).get('S', ''),
                    "unit_price": float(item.get('unit_price', {}).get('S', '0')),
                    "total_cost": float(item.get('total_cost', {}).get('S', '0')),
                    "available_quantity": int(item.get('available_quantity', {}).get('S', '0')),
                    "lead_time": item.get('lead_time', {}).get('S', ''),
                    "payment_terms": item.get('payment_terms', {}).get('S', ''),
                    "warranty_information": item.get('warranty_information', {}).get('S', ''),
                    "shipping_terms": item.get('shipping_terms', {}).get('S', ''),
                    "estimated_delivery_timeline": item.get('estimated_delivery_timeline', {}).get('S', ''),
                    "technical_specifications": item.get('technical_specifications', {}).get('S', ''),
                    "certification_details": item.get('certification_details', {}).get('S', ''),
                    "volume_discounts": item.get('volume_discounts', {}).get('S', ''),
                    "minimum_order_quantity": item.get('minimum_order_quantity', {}).get('S', ''),
                    "quote_validity_period": item.get('quote_validity_period', {}).get('S', ''),
                    
                    # Analysis results
                    "sustainability_score": int(item.get('sustainability_score', {}).get('N', '0')),
                    "sustainability_explanation": item.get('sustainability_explanation', {}).get('S', ''),
                    "reputation_score": int(item.get('reputation_score', {}).get('N', '0')),
                    "reputation_explanation": item.get('reputation_explanation', {}).get('S', ''),
                    "wikipedia_url": item.get('wikipedia_url', {}).get('S', ''),
                    
                    # Timestamps
                    "created_date": item.get('created_date', {}).get('S', ''),
                    "last_updated": item.get('last_updated', {}).get('S', '')
                }
                
                suppliers_data.append(supplier_data)
        
        return json.dumps({"success": True, "suppliers_data": suppliers_data})
        
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

@tool
def get_supplier_location(supplier_id: str) -> str:
    """
    Get supplier location from scm_suppliers table for origin field.
    """
    try:
        dynamodb = boto3.client('dynamodb', region_name='us-east-1')
        response = dynamodb.get_item(
            TableName=SUPPLIERS_TABLE,
            Key={'supplier_id': {'S': supplier_id}}
        )
        
        if 'Item' in response:
            location = response['Item'].get('location', {}).get('S', 'Unknown Location')
            return json.dumps({"success": True, "location": location})
        else:
            return json.dumps({"success": False, "error": "Supplier not found"})
            
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

@tool
def select_optimal_supplier(rfq_data: dict, suppliers_data: list) -> str:
    """
    Use LLM to analyze and select the optimal supplier based on comprehensive criteria.
    """
    try:
        prompt = f"""
        Analyze the following RFQ requirements and supplier data to select the OPTIMAL supplier.
        
        RFQ REQUIREMENTS:
        - SKU: {rfq_data.get('sku', '')}
        - Quantity: {rfq_data.get('quantity', 0)}
        - Expected Price: ${rfq_data.get('expected_price', 0)}
        - Budget Range: ${rfq_data.get('budget_range', '')}
        - Delivery Date: {rfq_data.get('delivery_date', '')}
        - Technical Requirements: {rfq_data.get('technical_requirements', '')}
        - Quality Standards: {rfq_data.get('quality_standards', '')}
        - Priority: {rfq_data.get('priority', '')}
        - Destination: {rfq_data.get('destination_city', '')}
        
        SUPPLIER DATA:
        {json.dumps(suppliers_data, indent=2)}
        
        DECISION CRITERIA:
        1. Minimum Thresholds:
           - Sustainability Score: ≥{MIN_SUSTAINABILITY_SCORE}
           - Reputation Score: ≥{MIN_REPUTATION_SCORE}
        
        2. Priority Weighting (Higher Weight):
           - Price competitiveness (within budget)
           - Reputation score
           - Delivery timeline compatibility
        
        3. Secondary Factors:
           - Sustainability score
           - Technical specifications match
           - Quantity availability
           - Payment terms
           - Warranty information
           - Certification compliance
        
        ANALYSIS REQUIREMENTS:
        - Evaluate ALL suppliers against RFQ requirements
        - Apply minimum thresholds (reject if below)
        - Consider price competitiveness within budget
        - Assess delivery timeline compatibility
        - Evaluate technical specifications match
        - Consider reputation and sustainability scores
        - Factor in payment terms and warranty
        
        SELECT ONLY 1 OPTIMAL SUPPLIER and provide comprehensive reasoning.
        
        Respond with JSON:
        {{
            "selected_supplier": {{
                "supplier_id": "supplier_id",
                "supplier_name": "name",
                "selection_score": 85
            }},
            "reasoning": "Detailed explanation of selection decision",
            "key_factors": ["factor1", "factor2", "factor3"],
            "comparison_summary": "Brief comparison of all suppliers",
            "risk_assessment": "Any potential risks or concerns"
        }}
        """
        bedrock = boto3.client('bedrock-runtime', region_name=AWS_REGION)
        response = bedrock.invoke_model(
            modelId="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}]
            })
        )
        
        result = json.loads(response['body'].read())
        llm_response = result['content'][0]['text'].strip()
        
        # Parse LLM response
        selection_result = json.loads(llm_response)
        
        return json.dumps({"success": True, "selection": selection_result})
        
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

@tool
def update_routing_details_with_supplier(supplier_id: str, supplier_name: str, origin: str, rfq_id: str) -> str:
    """
    Update scm_routing_details table with selected supplier information.
    Get supplier details from scm_suppliers table and update routing table.
    """
    try:
        dynamodb = boto3.client('dynamodb', region_name='us-east-1')
        # Get supplier details from scm_suppliers table
        supplier_response = dynamodb.get_item(
            TableName=SUPPLIERS_TABLE,
            Key={'supplier_id': {'S': supplier_id}}
        )
        
        if 'Item' not in supplier_response:
            return json.dumps({"success": False, "error": "Supplier not found"})
        
        supplier_data = supplier_response['Item']
        supplier_city = supplier_data.get('city', {}).get('S', 'Unknown')
        supplier_country = supplier_data.get('country', {}).get('S', 'Unknown')
        supplier_address = supplier_data.get('address', {}).get('S', 'Unknown')
        
        # Get lead time from scm_negotiation table
        negotiation_response = dynamodb.query(
            TableName=NEGOTIATION_TABLE,
            IndexName='gsi_supplier_id',
            KeyConditionExpression='supplier_id = :sid',
            ExpressionAttributeValues={':sid': {'S': supplier_id}}
        )
        
        supplier_lead_time = 'Unknown'
        if negotiation_response['Items']:
            supplier_lead_time = negotiation_response['Items'][0].get('lead_time', {}).get('S', 'Unknown')
        
        # Update scm_routing_details table
        update_expression = "SET Supplier_ID = :sid, supplier_city = :city, supplier_country = :country, Supplier_Name = :name, Shipment_Origin = :origin, supplier_lead_time = :leadtime, last_updated = :updated"
        
        dynamodb.update_item(
            TableName=ROUTING_TABLE,
            Key={'External_Ref': {'S': rfq_id}},
            UpdateExpression=update_expression,
            ExpressionAttributeValues={
                ':sid': {'S': supplier_id},
                ':city': {'S': supplier_city},
                ':country': {'S': supplier_country},
                ':name': {'S': supplier_name},
                ':origin': {'S': supplier_address},
                ':leadtime': {'S': supplier_lead_time},
                ':updated': {'S': datetime.now(timezone.utc).isoformat()}
            }
        )
        
        return json.dumps({"success": True, "external_ref": rfq_id, "supplier_details_updated": True})
        
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

@tool
def send_selection_email(supplier_email: str, supplier_name: str, rfq_id: str, selection_details: dict, company_name: str = "") -> str:
    """
    Send comprehensive selection notification email to chosen supplier.
    """
    try:
        ses = boto3.client('ses', region_name=AWS_REGION)
        # LLM-generated email content
        email_prompt = f"""
        Draft a professional email to notify {supplier_name} that they have been selected as the optimal supplier for RFQ {rfq_id}.
        
        Selection Details:
        - Selection Score: {selection_details.get('selection_score', 'N/A')}
        - Key Factors: {', '.join(selection_details.get('key_factors', []))}
        - Reasoning: {selection_details.get('reasoning', '')}
        
        Email should be:
        - Professional and congratulatory
        - Include next steps
        - Mention key selection factors
        - Request confirmation and timeline
        - Be comprehensive but concise (not too long)
        - End with: Best regards,\nProcurement Head\n{company_name}
        
        Format as professional business email with subject and body.
        """
        bedrock = boto3.client('bedrock-runtime', region_name=AWS_REGION)
        response = bedrock.invoke_model(
            modelId="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 800,
                "temperature": 0,
                "messages": [{"role": "user", "content": email_prompt}]
            })
        )
        
        result = json.loads(response['body'].read())
        email_content = result['content'][0]['text'].strip()
        
        # Extract subject and body
        lines = email_content.split('\n')
        subject = "Supplier Selection Notice - " + rfq_id
        body = email_content
        
        # Send email via SES
        ses_response = ses.send_email(
            Source=SES_SENDER,
            Destination={'ToAddresses': [supplier_email]},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': body}}
            }
        )
        
        return json.dumps({
            "success": True, 
            "message_id": ses_response['MessageId'],
            "email_content": email_content
        })
        
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

@tool
def send_slack_notification(message: str, channel: str = SLACK_CHANNEL) -> str:
    """
    Send internal Slack notification about supplier selection.
    Returns detailed response including message ID and channel information.
    """
    try:
        client = slack_sdk.WebClient(token=SLACK_BOT_TOKEN)
        
        response = client.chat_postMessage(
            channel=channel,
            text=message
        )
        
        # Get channel info for better reporting
        channel_info = client.conversations_info(channel=response['channel'])
        channel_name = channel_info['channel']['name']
        
        return json.dumps({
            "success": True,
            "message": "Slack notification sent successfully",
            "slack_details": {
                "message_id": response['ts'],
                "channel_id": response['channel'],
                "channel_name": f"#{channel_name}",
                "message_content": message,
                "sent_at": response['ts']
            }
        })
        
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})



#Agent 5 Tools
#get_routing_data
@tool
def get_routing_data(rfq_id: str) -> str:
    try:
        ddb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = ddb.Table(TABLE_NAME)
        response = table.get_item(Key={"External_Ref": rfq_id})
        if "Item" in response:
            item = response["Item"]
            return json.dumps({
                "success": True,
                "data": {
                    "destination_city": item.get("Destination_City", ""),
                    "supplier_city": item.get("supplier_city", ""),
                    "destination_address": item.get("Shipment_Destination_address", ""),
                    "origin_address": item.get("Shipment_Origin", ""),
                    "rfq_id": rfq_id
                }
            })
        return json.dumps({"success": False, "error": "RFQ not found"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
        
# update_routing_selection
@tool
def update_routing_selection(rfq_id: str, transport_mode: str, selected_path: str) -> str:
    """Update DynamoDB with selected transport mode and route path"""
    try:
        ddb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = ddb.Table(TABLE_NAME)
        
        response = table.update_item(
            Key={"External_Ref": rfq_id},
            UpdateExpression="SET transport_mode = :tm, selected_path = :sp, selection_timestamp = :ts",
            ExpressionAttributeValues={
                ":tm": transport_mode,
                ":sp": selected_path,
                ":ts": datetime.now().isoformat()
            },
            ReturnValues="UPDATED_NEW"
        )
        
        return json.dumps({
            "success": True,
            "updated_attributes": response.get("Attributes", {})
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
        
# get_supplier_and_customer_details
@tool
def get_supplier_and_customer_details(rfq_id: str) -> str:
    """Get supplier and customer details from DynamoDB"""
    try:
        ddb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = ddb.Table(TABLE_NAME)
        response = table.get_item(Key={"External_Ref": rfq_id})
        if "Item" in response:
            item = response["Item"]
            return json.dumps({
                "success": True,
                "supplier": {
                    "name": item.get("Supplier_Name", ""),
                    "email": item.get("supplier_email", ""),
                    "city": item.get("supplier_city", ""),
                    "country": item.get("supplier_country", "")
                },
                "customer": {
                    "name": item.get("customer_company_name", ""),
                    "address": item.get("Shipment_Destination_address", ""),
                    "expected_delivery_date": item.get("customer_expected_delivery_date", "")
                }
            })
        return json.dumps({"success": False, "error": "RFQ not found"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
        
# analyze_email_sentiment_llm
@tool
def analyze_email_sentiment_llm(email_content: str) -> str:
    """Analyze email sentiment using LLM"""
    try:
        sentiment_model = BedrockModel(model_id="us.anthropic.claude-3-5-haiku-20241022-v1:0", temperature=0.0)
        
        prompt = f"""
        Analyze the sentiment of this email and rate its appropriateness for business communication:
        
        EMAIL CONTENT:
        {email_content}
        
        Provide analysis in this exact JSON format:
        {{
            "sentiment": "POSITIVE/NEUTRAL/NEGATIVE",
            "confidence_score": 0.0-1.0,
            "is_appropriate": true/false,
            "recommendation": "SEND/IMPROVE",
            "reasoning": "brief explanation"
        }}
        
        Consider professional tone, clarity, and business appropriateness. Rate confidence as decimal between 0.0-1.0.
        """
        sentiment_agent = Agent(
            model=sentiment_model,
            system_prompt="You are a sentiment analysis expert. Analyze business emails for appropriateness and sentiment. Always respond with valid JSON only."
        )
        
        response = sentiment_agent(prompt)
        result_text = response.message['content'][0]['text'].strip()
        
        result = json.loads(result_text)
        return json.dumps({
            "success": True,
            "sentiment": result["sentiment"],
            "confidence": result["confidence_score"],
            "is_appropriate": result["is_appropriate"],
            "recommendation": result["recommendation"],
            "reasoning": result["reasoning"]
        })
            
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
        
# improve_email_sentiment
@tool
def improve_email_sentiment(email_content: str, target_sentiment: str = "POSITIVE") -> str:
    """Improve email sentiment while maintaining content"""
    try:
        improvement_model = BedrockModel(model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0", temperature=0.3)
        
        prompt = f"""
        Improve this email to have a more {target_sentiment.lower()} sentiment while maintaining all key information:
        
        ORIGINAL EMAIL:
        {email_content}
        
        Requirements:
        1. Keep all technical details and route information
        2. Make tone more positive and professional
        3. Add appreciation and partnership language
        4. Maintain the core message about route selection
        5. Keep the email concise and business-appropriate
        
        Return only the improved email content.
        """
        
        from strands import Agent
        improvement_agent = Agent(
            model=improvement_model,
            system_prompt="You improve business email sentiment while preserving all important information. Make emails more positive and professional."
        )
        
        response = improvement_agent(prompt)
        improved_content = response.message['content'][0]['text'].strip()
        
        return json.dumps({
            "success": True,
            "improved_email": improved_content
        })
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "improved_email": email_content
        })
        
# generate_route_selection_email
@tool
def generate_route_selection_email(llm_output: str, supplier_details: dict, customer_details: dict, selected_route: str) -> str:
    """Generate email to supplier about route selection"""
    try:
        email_model = BedrockModel(model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0", temperature=0.2)
        
        prompt = f"""
        Generate a professional email from customer to supplier about route selection based on this LLM analysis:
        
        LLM ANALYSIS OUTPUT:
        {llm_output}
        
        SUPPLIER DETAILS:
        - Name: {supplier_details.get('name', 'Supplier')}
        - City: {supplier_details.get('city', '')}
        - Country: {supplier_details.get('country', '')}
        
        CUSTOMER DETAILS:
        - Company: {customer_details.get('name', 'Customer')}
        - Address: {customer_details.get('address', '')}
        
        SELECTED ROUTE: {selected_route}
        
        Create an email that:
        1. Thanks the supplier for their service
        2. Informs them about the route selection decision
        3. Mentions the LLM analysis reasoning
        4. Confirms we are selecting this route for shipping
        5. Maintains professional and positive tone
        6. Includes proper business email format with subject line
        
        Format as:
        Subject: [subject line]
        
        [email body]
        
        Best regards,
        [customer name]
        """
        
        from strands import Agent
        email_agent = Agent(
            model=email_model,
            system_prompt="Generate professional business emails about logistics and route selection. Be clear, positive, and informative."
        )
        
        response = email_agent(prompt)
        email_content = response.message['content'][0]['text'].strip()
        
        return json.dumps({
            "success": True,
            "email_content": email_content
        })
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "email_content": "Email generation failed"
        })

# send_email_via_ses
@tool
def send_email_via_ses(to_email: str, subject: str, body: str) -> str:
    """Send email via AWS SES"""
    try:
        ses = boto3.client('ses', region_name=AWS_REGION)
        
        response = ses.send_email(
            Source=SES_SENDER,
            Destination={'ToAddresses': [to_email]},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': body}}
            }
        )
        
        return json.dumps({
            "success": True,
            "message_id": response['MessageId'],
            "to_email": to_email,
            "subject": subject
        })
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })
        
# analyze_news_for_routes
@tool
def analyze_news_for_routes(air_route_data: str, road_route_data: str, sea_route_data: str, delivery_date: str) -> str:
    """Analyze news for shipping period: today to delivery + 20 days buffer"""
    try:
        air_data = json.loads(air_route_data)
        road_data = json.loads(road_route_data) 
        sea_data = json.loads(sea_route_data)
        
        shipping_period = calculate_shipping_period(delivery_date)
        results = {"shipping_analysis_period": shipping_period}
        if "error" in shipping_period:
            return json.dumps({"success": False, "error": shipping_period["error"]})
        
        routes = [
            ("AIR", air_data, ["airports", "flight delays", "air traffic", "aviation"]),
            ("ROAD", road_data, ["highway", "traffic", "road closures", "trucking", "interstate"]),
            ("SEA", sea_data, ["port", "shipping", "maritime", "cargo", "vessel"])
        ]
        
        for route_type, route_info, keywords in routes:
            route_path = route_info.get("route_path", "")
            search_query = f"{route_path} {' '.join(keywords)} disruptions delays planned construction forecast future"
            
            url = "https://api.tavily.com/search"
            payload = {
                "api_key": TAVILY_API_KEY,
                "query": search_query,
                "search_depth": "advanced",
                "max_results": 5,
                "days": shipping_period["total_analysis_period"]
            }
            
            try:
                response = requests.post(url, json=payload, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    news_items = []
                    risk_score = 0
                    
                    for result in data.get("results", [])[:5]:
                        title = result.get("title", "")
                        content = result.get("content", "")
                        url_link = result.get("url", "")
                        
                        risk_keywords = [
                            "delay", "disruption", "closure", "strike", "accident", "storm", 
                            "cancelled", "blocked", "suspended", "emergency", "shutdown", 
                            "outage", "construction", "maintenance", "planned", "scheduled"
                        ]
                        
                        found_keywords = [keyword for keyword in risk_keywords if keyword.lower() in (title + content).lower()]
                        item_risk = len(found_keywords)
                        risk_score += item_risk
                        
                        news_items.append({
                            "title": title,
                            "summary": content[:350],
                            "url": url_link,
                            "risk_keywords_found": found_keywords,
                            "risk_level": "HIGH" if item_risk >= 3 else "MEDIUM" if item_risk >= 1 else "LOW",
                            "risk_score": item_risk
                        })
                    
                    overall_risk = "HIGH" if risk_score >= 6 else "MEDIUM" if risk_score >= 3 else "LOW"
                    
                    results[route_type] = {
                        "route_path": route_path,
                        "news_items": news_items,
                        "risk_factor": overall_risk,
                        "risk_score": risk_score,
                        "total_news_items": len(news_items),
                        "analysis_period": f"Today to {shipping_period['analysis_end_date']}"
                    }
                else:
                    results[route_type] = {
                        "route_path": route_path,
                        "news_items": [],
                        "risk_factor": "UNKNOWN",
                        "error": f"API Error: {response.status_code}"
                    }
            except Exception as e:
                results[route_type] = {
                    "route_path": route_path,
                    "news_items": [],
                    "risk_factor": "UNKNOWN", 
                    "error": str(e)
                }
        
        return json.dumps({
            "success": True,
            "analysis_date": datetime.now().isoformat(),
            "delivery_date": delivery_date,
            "routes": results
        })
        
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

def calculate_shipping_period(delivery_date: str) -> dict:
    """Calculate shipping analysis period from today to delivery date + 20 days buffer"""
    try:
        from datetime import datetime, timedelta
        
        # Parse delivery date
        if delivery_date:
            try:
                # Try different date formats
                for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y"]:
                    try:
                        delivery_dt = datetime.strptime(delivery_date, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    # If no format matches, assume 30 days from now
                    delivery_dt = datetime.now() + timedelta(days=30)
            except:
                delivery_dt = datetime.now() + timedelta(days=30)
        else:
            delivery_dt = datetime.now() + timedelta(days=30)
        
        # Add 20 days buffer for analysis
        analysis_end = delivery_dt + timedelta(days=20)
        today = datetime.now()
        
        # Calculate total analysis period in days
        total_days = (analysis_end - today).days
        
        return {
            "analysis_start_date": today.strftime("%Y-%m-%d"),
            "analysis_end_date": analysis_end.strftime("%Y-%m-%d"),
            "delivery_date": delivery_dt.strftime("%Y-%m-%d"),
            "total_analysis_period": max(1, total_days),
            "buffer_days": 20
        }
    except Exception as e:
        return {"error": f"Date calculation error: {str(e)}"}

def get_weather_description(weather_code: int) -> str:
    """Convert weather code to human readable description"""
    weather_codes = {
        0: "Clear sky",
        1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Depositing rime fog",
        51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
        56: "Light freezing drizzle", 57: "Dense freezing drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        66: "Light freezing rain", 67: "Heavy freezing rain",
        71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
        77: "Snow grains",
        80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
        85: "Slight snow showers", 86: "Heavy snow showers",
        95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
    }
    return weather_codes.get(weather_code, f"Unknown weather (code: {weather_code})")

def get_coordinates_from_route_data(route_data_str, route_type):
    """Extract coordinates dynamically from route analysis data"""
    try:
        route_data = json.loads(route_data_str)
        
        if route_type == "AIR":
            # For air routes, use city names to get approximate coordinates
            origin_city = route_data.get("origin_city", "")
            dest_city = route_data.get("destination_city", "")
            
            city_coords = {
                "Milpitas": (37.4323, -121.9018),
                "Seattle": (47.6062, -122.3321),
                "San Jose": (37.3382, -121.8863)
            }
            
            origin_coords = None
            dest_coords = None
            
            for city, coords in city_coords.items():
                if city.lower() in origin_city.lower():
                    origin_coords = coords
                if city.lower() in dest_city.lower():
                    dest_coords = coords
            
            if origin_coords and dest_coords:
                return [origin_coords, dest_coords]
                
        elif route_type == "ROAD":
            # For road routes, extract from addresses
            origin_addr = route_data.get("origin_address", "")
            dest_addr = route_data.get("destination_address", "")
            
            if "Milpitas" in origin_addr and "Seattle" in dest_addr:
                return [(37.4323, -121.9018), (47.6062, -122.3321)]
                
        elif route_type == "SEA":
            # For sea routes, use port coordinates
            origin_city = route_data.get("origin_city", "")
            dest_city = route_data.get("destination_city", "")
            
            origin_coords = None
            dest_coords = None
            
            # Origin city to port mapping
            if "Milpitas" in origin_city or "San Jose" in origin_city:
                origin_coords = (37.8044, -122.2711)  # Oakland port
            elif "Oakland" in origin_city:
                origin_coords = (37.8044, -122.2711)  # Oakland port
            
            # Destination city to port mapping  
            if "Seattle" in dest_city:
                dest_coords = (47.6062, -122.3321)  # Seattle port
            
            if origin_coords and dest_coords:
                return [origin_coords, dest_coords]
        
        return None
    except:
        return None

# analyze_weather_for_routes
@tool
def analyze_weather_for_routes(air_route_data: str, road_route_data: str, sea_route_data: str, delivery_date: str) -> str:
    """Analyze weather for shipping period: today to delivery + 20 days buffer"""
    try:
        air_data = json.loads(air_route_data)
        road_data = json.loads(road_route_data)
        sea_data = json.loads(sea_route_data)
        
        shipping_period = calculate_shipping_period(delivery_date)
        results = {"shipping_analysis_period": shipping_period}
        if "error" in shipping_period:
            return json.dumps({"success": False, "error": shipping_period["error"]})
        
        routes_to_analyze = []
        for route_type, route_data in [("AIR", air_route_data), ("ROAD", road_route_data), ("SEA", sea_route_data)]:
            coords = get_coordinates_from_route_data(route_data, route_type)
            if coords:
                routes_to_analyze.append((route_type, route_data, coords))
            else:
                print(f"⚠️ Could not extract coordinates for {route_type} route - skipping weather analysis")
    
        for route_type, route_info, coordinates in routes:
            route_path = route_info.get("route_path", "")
            weather_data = []
            risk_factors = []
            
            for lat, lon in coordinates:
                try:
                    url = "https://api.open-meteo.com/v1/forecast"
                    params = {
                        "latitude": lat,
                        "longitude": lon,
                        "current": "temperature_2m,wind_speed_10m,precipitation,weather_code",
                        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
                        "forecast_days": min(shipping_period["total_analysis_period"], 16),
                        "timezone": "auto"
                    }
                    
                    response = requests.get(url, params=params, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        current = data.get("current", {})
                        daily = data.get("daily", {})
                        
                        temp = current.get("temperature_2m", 0)
                        wind_speed = current.get("wind_speed_10m", 0)
                        precipitation = current.get("precipitation", 0)
                        weather_code = current.get("weather_code", 0)
                        
                        forecast_risks = []
                        if daily:
                            max_winds = daily.get("wind_speed_10m_max", [])
                            precipitations = daily.get("precipitation_sum", [])
                            
                            for i in range(min(len(max_winds), 14)):
                                day_max_wind = max_winds[i] if i < len(max_winds) else 0
                                day_precipitation = precipitations[i] if i < len(precipitations) else 0
                                
                                if route_type == "AIR" and (day_max_wind > 25 or day_precipitation > 10):
                                    forecast_risks.append(f"Day {i+1}: High wind/precipitation")
                                elif route_type == "ROAD" and day_precipitation > 15:
                                    forecast_risks.append(f"Day {i+1}: Heavy precipitation")
                                elif route_type == "SEA" and day_max_wind > 30:
                                    forecast_risks.append(f"Day {i+1}: Very strong winds")
                        
                        risk_level = "LOW"
                        risk_reasons = []
                        
                        if route_type == "AIR":
                            if wind_speed > 25 or len(forecast_risks) >= 3:
                                risk_level = "HIGH"
                                risk_reasons.append("Strong winds current/forecast")
                            elif precipitation > 5 or len(forecast_risks) >= 1:
                                risk_level = "MEDIUM"
                                risk_reasons.append("Weather concerns")
                        elif route_type == "ROAD":
                            if precipitation > 10 or len(forecast_risks) >= 3:
                                risk_level = "HIGH"
                                risk_reasons.append("Heavy precipitation forecast")
                            elif len(forecast_risks) >= 1:
                                risk_level = "MEDIUM"
                                risk_reasons.append("Weather concerns")
                        elif route_type == "SEA":
                            if wind_speed > 30 or len(forecast_risks) >= 3:
                                risk_level = "HIGH"
                                risk_reasons.append("Strong winds forecast")
                            elif wind_speed > 20 or len(forecast_risks) >= 1:
                                risk_level = "MEDIUM"
                                risk_reasons.append("Wind concerns")
                        
                        weather_data.append({
                            "location": f"{lat:.2f}, {lon:.2f}",
                            "current_temperature": temp,
                            "current_wind_speed": wind_speed,
                            "current_precipitation": precipitation,
                            "current_conditions": get_weather_description(weather_code),
                            "forecast_risks": forecast_risks,
                            "risk_level": risk_level,
                            "risk_reasons": risk_reasons
                        })
                        
                        risk_factors.append(risk_level)

                    else:
                        weather_data.append({
                            "location": f"{lat:.2f}, {lon:.2f}",
                            "error": f"API Error: {response.status_code}",
                            "risk_level": "UNKNOWN"
                        })
                        
                except Exception as e:
                    weather_data.append({
                        "location": f"{lat:.2f}, {lon:.2f}",
                        "error": str(e),
                        "risk_level": "UNKNOWN"
                    })
            
            overall_risk = "HIGH" if "HIGH" in risk_factors else "MEDIUM" if "MEDIUM" in risk_factors else "LOW"
            
            results[route_type] = {
                "route_path": route_path,
                "weather_data": weather_data,
                "risk_factor": overall_risk,
                "analysis_period": f"Today to {shipping_period['analysis_end_date']}"
            }
        
        return json.dumps({
            "success": True,
            "analysis_date": datetime.now().isoformat(),
            "delivery_date": delivery_date,
            "routes": results
        })
        
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
        
# analyze_air_route
@tool
def analyze_air_route(origin_city: str, destination_city: str) -> str:
    try:
        origin_clean = origin_city.split(',')[0].strip()
        dest_clean = destination_city.split(',')[0].strip()
        
        def get_nearest_airport(city_name):
            search_terms = [city_name, city_name.replace(' ', ''), f"{city_name} airport"]
            for term in search_terms:
                try:
                    url = "https://airlabs.co/api/v9/airports"
                    params = {"api_key": AIRLABS_API_KEY, "city_code": term}
                    response = requests.get(url, params=params, timeout=15)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("response") and len(data["response"]) > 0:
                            airport = data["response"][0]
                            return {
                                "name": airport.get("name", f"{city_name} International Airport"),
                                "lat": float(airport.get("lat", 0)),
                                "lng": float(airport.get("lng", 0))
                            }
                except:
                    continue
            
            # Only major airport fallback - minimal
            if "seattle" in city_name.lower():
                return {"name": "Seattle-Tacoma International Airport", "lat": 47.4502, "lng": -122.3088}
            elif "milpitas" in city_name.lower() or "san jose" in city_name.lower():
                return {"name": "San Jose International Airport", "lat": 37.3639, "lng": -121.9289}
            
            return {"name": f"{city_name} International Airport", "lat": 0, "lng": 0}
        
        origin_airport = get_nearest_airport(origin_clean)
        dest_airport = get_nearest_airport(dest_clean)
        
        if origin_airport["lat"] and dest_airport["lat"]:
            distance = geodesic((origin_airport["lat"], origin_airport["lng"]), (dest_airport["lat"], dest_airport["lng"])).kilometers
        else:
            distance = 1000
        
        cost = distance * 3.5
        days = 1 if distance < 800 else (2 if distance < 2500 else 3)
        co2 = distance * 0.52
        
        return json.dumps({
            "origin_city": origin_city,
            "destination_city": destination_city,
            "origin_airport": origin_airport["name"],
            "destination_airport": dest_airport["name"],
            "route_path": f"{origin_airport['name']} → {dest_airport['name']}",
            "distance": round(distance, 2),
            "days": days,
            "cost": round(cost, 2),
            "co2": round(co2, 2),
            "stops": [origin_airport["name"], dest_airport["name"]]
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
        
# analyze_road_route
@tool
def analyze_road_route(origin_address: str, destination_address: str) -> str:
    try:
        def geocode_address(address):
            url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{address}.json"
            params = {"access_token": MAPBOX_API_KEY, "limit": 1}
            try:
                response = requests.get(url, params=params, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("features"):
                        feature = data["features"][0]
                        coords = feature["geometry"]["coordinates"]
                        return {"lat": coords[1], "lng": coords[0]}
            except:
                pass
            return {"lat": 0, "lng": 0}
        
        origin_coords = geocode_address(origin_address)
        dest_coords = geocode_address(destination_address)
        
        def get_mapbox_route(start_coords, end_coords):
            try:
                url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{start_coords['lng']},{start_coords['lat']};{end_coords['lng']},{end_coords['lat']}"
                params = {
                    "access_token": MAPBOX_API_KEY,
                    "steps": "true",
                    "geometries": "geojson"
                }
                
                response = requests.get(url, params=params, timeout=25)
                        
                if response.status_code == 200:
                    data = response.json()
                    if data.get("routes"):
                        route = data["routes"][0]
                        distance = route["distance"] / 1000
                        
                        # Extract REAL highways from MapBox response
                        intermediate_stops = []
                        
                        if route.get("legs"):
                            for leg in route["legs"]:
                                if leg.get("steps"):
                                    for step in leg["steps"]:
                                        name = step.get("name", "")
                                        if name and (any(prefix in name.upper() for prefix in ["I-", "US-", "SR-", "CA-", "HIGHWAY", "INTERSTATE"]) or 
                                                   any(word in name.upper() for word in ["AVENUE", "STREET", "PARKWAY", "BOULEVARD", "ROAD"])):
                                            if name not in intermediate_stops:
                                                intermediate_stops.append(name)
                        
                        return distance, intermediate_stops[:8]
                        
            except Exception as e:
                print(f"MapBox routing error: {e}")
                pass
            
            if start_coords["lat"] and end_coords["lat"]:
                distance = geodesic((start_coords["lat"], start_coords["lng"]), (end_coords["lat"], end_coords["lng"])).kilometers * 1.3
                return distance, []
            
            return 1200, []
        
        distance, intermediate_stops = get_mapbox_route(origin_coords, dest_coords)
        
        cost = (distance * 1.8) + (distance * 0.15)
        days = max(1, math.ceil(distance / 600))
        co2 = distance * 0.27
        
        origin_city = origin_address.split(',')[0].strip() if ',' in origin_address else "Origin"
        dest_city = destination_address.split(',')[0].strip() if destination_address.count(',') >= 2 else destination_address.split(',')[-1].strip()
        
        # Create route path and all_stops list
        if intermediate_stops:
            route_path = f"{origin_city} → {' → '.join(intermediate_stops)} → {dest_city}"
            all_stops = [origin_city] + intermediate_stops + [dest_city]
        else:
            route_path = f"{origin_city} → {dest_city}"
            all_stops = [origin_city, dest_city]
        
        return json.dumps({
            "origin_address": origin_address,
            "destination_address": destination_address,
            "route_path": route_path,
            "distance": round(distance, 2),
            "days": days,
            "cost": round(cost, 2),
            "co2": round(co2, 2),
            "stops": all_stops
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
      
# analyze_sea_route
@tool
def analyze_sea_route(origin_city: str, destination_city: str) -> str:
    try:
        origin_clean = origin_city.split(',')[0].strip()
        dest_clean = destination_city.split(',')[0].strip()
        
        def find_nearest_port(city_name):
            try:
                geocode_url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{city_name}.json"
                params = {"access_token": MAPBOX_API_KEY, "limit": 1}
                response = requests.get(geocode_url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("features"):
                        coords = data["features"][0]["geometry"]["coordinates"]
                        city_coords = (coords[1], coords[0])
                        
                        # IMPROVED: Commercial cargo port search only
                        queries = [
                            # Strategy 1: Commercial cargo ports only
                            f'''[out:json][timeout:15];
                            (
                              way["landuse"="port"]["industrial"="yes"](around:50000,{city_coords[0]},{city_coords[1]});
                              way["harbour"="yes"]["commercial"="yes"](around:50000,{city_coords[0]},{city_coords[1]});
                              relation["harbour"="yes"]["!passenger"](around:50000,{city_coords[0]},{city_coords[1]});
                            );
                            out center;''',
                            
                            # Strategy 2: Port areas excluding passenger facilities
                            f'''[out:json][timeout:15];
                            (
                              node["landuse"="port"]["!amenity"](around:80000,{city_coords[0]},{city_coords[1]});
                              way["landuse"="port"]["!ferry"](around:80000,{city_coords[0]},{city_coords[1]});
                            );
                            out center;''',
                        ]
                        
                        for query in queries:
                            try:
                                response = requests.post(
                                    'https://overpass-api.de/api/interpreter',
                                    data=query,
                                    headers={'User-Agent': 'RoutingAgent/1.0'},
                                    timeout=20
                                )
                                
                                if response.status_code == 200:
                                    data = response.json()
                                    elements = data.get('elements', [])
                                    
                                    if elements:
                                        ports = []
                                        for element in elements:
                                            if 'lat' in element and 'lon' in element:
                                                port_coords = (element['lat'], element['lon'])
                                                distance = geodesic(city_coords, port_coords).kilometers
                                                name = element.get('tags', {}).get('name', 'Commercial Port')
                                                # Filter out passenger-related names
                                                if not any(term in name.lower() for term in ['ferry', 'water taxi', 'passenger', 'cruise']):
                                                    ports.append({
                                                        'name': name,
                                                        'distance_km': round(distance, 2),
                                                        'lat': element['lat'],
                                                        'lng': element['lon']
                                                    })
                                        
                                        if ports:
                                            closest_port = min(ports, key=lambda x: x['distance_km'])
                                            return {
                                                "name": closest_port['name'],
                                                "lat": closest_port['lat'],
                                                "lng": closest_port['lng']
                                            }
                                            
                            except Exception as e:
                                print(f'Port search error: {e}')
                                continue
                        
                        # Fallback to major commercial ports
                        lat, lon = city_coords[0], city_coords[1]
                        if -125 < lon < -115:
                            if lat > 45:
                                return {"name": "Port of Seattle Terminal 5", "lat": 47.6062, "lng": -122.3321}
                            elif lat > 37:
                                return {"name": "Port of Oakland", "lat": 37.8044, "lng": -122.2711}
                            else:
                                return {"name": "Port of Los Angeles", "lat": 33.7361, "lng": -118.2644}
                        else:
                            return {"name": f"Commercial Port near {city_name}", "lat": lat, "lng": lon}
                            
            except Exception as e:
                print(f"Port search error: {e}")
                pass
            
            return {"name": f"Port near {city_name}", "lat": 0, "lng": 0}
        
        origin_port = find_nearest_port(origin_clean)
        dest_port = find_nearest_port(dest_clean)
        
        if origin_port["lat"] and dest_port["lat"]:
            distance = geodesic((origin_port["lat"], origin_port["lng"]), (dest_port["lat"], dest_port["lng"])).kilometers * 1.4
        else:
            distance = 800
        
        cost = (distance * 0.8) + 200
        days = max(3, math.ceil(distance / 400) + 2)
        co2 = distance * 0.014
        
        route_path = f"{origin_port['name']} → {dest_port['name']}"
        all_stops = [origin_port["name"], dest_port["name"]]
        
        return json.dumps({
            "origin_city": origin_city,
            "destination_city": destination_city,
            "origin_port": origin_port["name"],
            "destination_port": dest_port["name"],
            "route_path": route_path,
            "distance": round(distance, 2),
            "days": days,
            "cost": round(cost, 2),
            "co2": round(co2, 2),
            "stops": all_stops
        })
    except Exception as e:
        return json.dumps({"error": str(e)})

@tool
def generate_route_map(air_data: str, road_data: str, sea_data: str) -> str:
    """Generate and display interactive route map"""
    try:
        # Parse route data
        air_route = json.loads(air_data) if air_data and not air_data.startswith('{"error"') else None
        road_route = json.loads(road_data) if road_data and not road_data.startswith('{"error"') else None
        sea_route = json.loads(sea_data) if sea_data and not sea_data.startswith('{"error"') else None
        
        # Generate map if we have route data
        if any([air_route, road_route, sea_route]):
            map_obj = create_route_map(air_route, road_route, sea_route)
            map_html = map_obj._repr_html_()
            display(HTML(f'<div style="height:600px">{map_html}</div>'))
            
            # Save map as HTML file
            map_obj.save('/home/ec2-user/SageMaker/fixed_finalized_agents_code/map_visual.html')
            
            return json.dumps({
                "success": True,
                "message": "Interactive route map generated and displayed",
                "map_saved": "map_visual.html",
                "routes_mapped": {
                    "air": air_route is not None,
                    "road": road_route is not None, 
                    "sea": sea_route is not None
                }
            })
        else:
            return json.dumps({
                "success": False,
                "error": "No valid route data provided for map generation"
            })
            
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Map generation failed: {str(e)}"
        })

@tool
def display_supplier_emails(rfq_id: str) -> str:
    """Display supplier emails from DynamoDB"""
    try:
        ddb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = ddb.Table("scm_routing_details")
        response = table.get_item(Key={"External_Ref": rfq_id})
        
        if "Item" in response:
            item = response["Item"]
            supplier_email_1 = item.get("Supplier_Acknowledge_1", "")
            supplier_email_2 = item.get("Supplier_Acknowledge_2", "")
            
            result = "=== SUPPLIER EMAILS ===\n\n"
            
            if supplier_email_1:
                result += "📧 Initial Supplier Email:\n"
                result += supplier_email_1 + "\n\n"
            
            if supplier_email_2:
                result += "📧 Supplier Confirmation:\n" 
                result += supplier_email_2 + "\n\n"
            
            return json.dumps({
                "success": True,
                "emails_displayed": True,
                "email_content": result
            })
        else:
            return json.dumps({
                "success": False,
                "error": "RFQ not found in database"
            })
            
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Failed to retrieve emails: {str(e)}"
        })



def _parse_rfq_input(text: str) -> dict:
    """Parse JSON output from Agent0"""
    # Extract JSON from Agent0's response
    try:
        # Find JSON block in the response
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end > start:
            json_str = text[start:end]
            return json.loads(json_str)
        else:
            raise ValueError("No JSON found in response")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"JSON parsing error: {e}")
        print(f"Raw input: {text}")
        return {}

print("✅ Agent1 Parsing Function Created")

def process_rfq_with_strands(user_input: str, input_data: dict = None) -> str:
    """You are an RFQ Processing Agent that creates/updates RFQ records in Salesforce.

PROCESSING STEPS:
1. Parse the JSON input from Agent0
2. Use find_or_create_account tool for company
3. Use process_rfq_tool to create/update RFQ
4. Use get_rfq_details to fetch complete RFQ data
5. Use update_routing_details to update shipping info

CRITICAL: Extract company_name from the JSON input, NOT from agent names.
Parse the JSON properly to get the actual company name value.

Always show the account action and RFQ details in a clear format.
    """
    try:
        # Parse the input
        rfq_data = _parse_rfq_input(user_input)
        
        output_parts = []
        
        # Tool 1: find_or_create_account 
        account_id = None
        if rfq_data.get('company_name'):
            account_result = find_or_create_account(
                rfq_data['company_name'],
                rfq_data.get('industry'),
                rfq_data.get('website'),
                rfq_data.get('phone')
            )
            account_data = json.loads(account_result)
            if account_data['success']:
                account_id = account_data['account_id']
                action = "Found existing" if account_data['action'] == 'found_existing' else "Created new"
        
        # Tool 2: process_rfq_tool  
        result = process_rfq_tool(
            rfq_data['sku'],
            rfq_data['quantity'], 
            rfq_data['priority'],
            rfq_data['rfq_id'],
            account_id=account_id,
            expected_price=rfq_data.get('expected_price'),
            notes=rfq_data.get('notes'),
            target_delivery=rfq_data.get('target_delivery')
        )
        
        result_data = json.loads(result)
        if result_data['success']:
            action_msg = "Created new RFQ record" if result_data['action'] == 'created' else "Updated existing RFQ record"
            
            # Tool 3: get_rfq_details
            details_result = get_rfq_details(rfq_data['rfq_id'])
            details_data = json.loads(details_result)
            
            if details_data['success']:
                # Tool 4: update_routing_details
                routing_result = update_routing_details(
                    rfq_data['rfq_id'],
                    details_data['rfq_data'].get('Name', 'N/A'),
                    details_data['rfq_data'].get('Id', 'N/A'),
                    rfq_data.get('shipping_address', 'Not provided'),
                    rfq_data.get('destination_city', ''),
                    rfq_data.get('destination_country', ''),
                    rfq_data.get('company_name', 'Not provided')
                )
                
                routing_data = json.loads(routing_result)
                
                # Results sections
                output_parts.append(f"\n=== Company Account ===")
                if account_id:
                    output_parts.append(f"{account_data['action'].title()}: {rfq_data['company_name']} (ID: {account_id})")
                
                output_parts.append(f"\n=== Status ===")
                output_parts.append(action_msg)
                
                clean_data = {k: v for k, v in details_data['rfq_data'].items() if v is not None and k != 'attributes'}
                df = pd.DataFrame(list(clean_data.items()), columns=['Field', 'Value'])
                output_parts.append(f"\n=== Final Salesforce RFQ ===")
                output_parts.append(df.to_string(index=False))
                
                output_parts.append(f"\n=== Routing Details Updated ===")
                output_parts.append(f"Company: {rfq_data.get('company_name', 'Not provided')}")
                output_parts.append(f"Shipping Address: {rfq_data.get('shipping_address', 'Not provided')}")
                output_parts.append(f"Destination City: {rfq_data.get('destination_city', 'N/A')}")
                output_parts.append(f"Destination Country: {rfq_data.get('destination_country', 'N/A')}")
        
        return "\n".join(output_parts)
        
    except Exception as e:
        return f"Error: {str(e)}"



@tool
def process_rfq_tool(sku: str, quantity: int, priority: str, rfq_id: str, account_id: str = None, **kwargs) -> str:
    """Process RFQ using upsert pattern - creates if new, updates if exists"""
    url = f"{instance_url}/services/data/{SF_API_VERSION}/sobjects/{RFQ_OBJ}/External_Ref__c/{rfq_id}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "SKU__c": sku,
        "Quantity__c": quantity,
        "Priority__c": priority,
    }
    
    if account_id:
        payload["Account__c"] = account_id
    
    for key, value in kwargs.items():
        if value is not None:
            if key == 'expected_price':
                payload['Expected_Unit_Price__c'] = value
            elif key == 'notes':
                payload['Notes__c'] = value
            elif key == 'target_delivery':
                payload['Target_Delivery__c'] = value
    
    response = requests.patch(url, headers=headers, json=payload)
    
    if response.status_code in [200, 201]:
        return json.dumps({"success": True, "action": "created" if response.status_code == 201 else "updated"})
    else:
        return json.dumps({"success": False, "error": response.text})

@tool
def get_rfq_details(rfq_id: str) -> str:
    """Get complete RFQ details from Salesforce"""
    url = f"{instance_url}/services/data/{SF_API_VERSION}/query"
    headers = {"Authorization": f"Bearer {access_token}"}
    query = f"SELECT FIELDS(ALL) FROM {RFQ_OBJ} WHERE External_Ref__c = '{rfq_id}' LIMIT 1"
    
    response = requests.get(url, headers=headers, params={"q": query})
    
    if response.status_code == 200:
        data = response.json()
        if data['records']:
            return json.dumps({"success": True, "rfq_data": data['records'][0]})
        else:
            return json.dumps({"success": False, "error": f"No RFQ found with ID: {rfq_id}"})
    else:
        return json.dumps({"success": False, "error": response.text})

@tool
def find_or_create_account(company_name: str, industry: str = None, website: str = None, phone: str = None) -> str:
    """Find existing account by company name or create new one with company details"""
    url = f"{instance_url}/services/data/{SF_API_VERSION}/query"
    headers = {"Authorization": f"Bearer {access_token}"}
    query = f"SELECT Id, Name FROM Account WHERE Name = '{company_name}' LIMIT 1"
    
    response = requests.get(url, headers=headers, params={"q": query})
    
    if response.status_code == 200:
        data = response.json()
        if data['records']:
            account_id = data['records'][0]['Id']
            return json.dumps({"success": True, "account_id": account_id, "action": "found_existing"})
    
    create_url = f"{instance_url}/services/data/{SF_API_VERSION}/sobjects/Account/"
    account_payload = {
        "Name": company_name,
        "Type": "Customer"
    }
    
    if industry:
        account_payload["Industry"] = industry
    if website:
        account_payload["Website"] = website
    if phone:
        account_payload["Phone"] = phone
    
    create_response = requests.post(create_url, headers=headers, json=account_payload)
    
    if create_response.status_code in [200, 201]:
        account_data = create_response.json()
        return json.dumps({"success": True, "account_id": account_data['id'], "action": "created_new"})
    else:
        return json.dumps({"success": False, "error": create_response.text})

@tool
def update_routing_details(rfq_id: str, rfq_name: str, sf_id: str, shipping_address: str, destination_city: str = "", destination_country: str = "", company_name: str = "") -> str:
    """Update routing details in DynamoDB table with destination info and company details"""
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.Table('scm_routing_details')
    
    try:
        response = table.update_item(
            Key={"External_Ref": rfq_id},
            UpdateExpression="SET #name = :name, ID = :id, customer_company_name = :company, Destination_City = :dest_city, Destination_Country = :dest_country, Shipment_Destination_address = :dest_addr",
            ExpressionAttributeNames={"#name": "Name"},
            ExpressionAttributeValues={
                ":name": rfq_name,
                ":id": rfq_id,
                ":company": company_name,
                ":dest_city": destination_city,
                ":dest_country": destination_country,
                ":dest_addr": shipping_address
            }
        )
        return json.dumps({"success": True, "message": "Routing details updated successfully"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

print("✅ Agent1 tools created")



email_extractor_agent = Agent(
    model=claude_haiku_model,
    name="Email_Intelligence_Agent",
    description="Enhanced Email Intelligence Extractor with thinking and reasoning capabilities",
    system_prompt="""
You are an Email Intelligence Agent that extracts RFQ data from email conversations.

EXECUTION FORMAT:
1. Show "Processing email thread to extract RFQ data..."
2. For EACH field extraction, show TOOL THINKING with SOURCE:
   - Field Name: [value]
   - Source: "From email by [sender] - [specific text/context]"
   - Reasoning: [why this value was chosen]

FIELD EXTRACTION WITH SOURCE TRACKING:
For each field, show:
- SKU: [value] | Source: "From [sender email] - [exact text where found]"
- Quantity: [value] | Source: "From [sender email] - [exact text where found]"
- Priority: [value] | Source: "From [sender email] - [exact text where found]"
- RFQ ID: [value] | Source: "From [sender email] - [exact text where found]"
- Company Name: [value] | Source: "From [sender email] - [exact text where found]"
- Shipping Address: [value] | Source: "From [sender email] - [exact text where found]"
- Destination City: [value] | Source: "From [sender email] - [exact text where found]"
- Destination Country: [value] | Source: "From [sender email] - [exact text where found]"
- Industry: [value] | Source: "From [sender email] - [exact text where found]"
- Website: [value] | Source: "From [sender email] - [exact text where found]"
- Phone: [value] | Source: "From [sender email] - [exact text where found]"
- Expected Price: [value] | Source: "From [sender email] - [exact text where found]"
- Notes: [value] | Source: "From [sender email] - [exact text where found]"
- Target Delivery: [value] | Source: "From [sender email] - [exact text where found]"

Tool #1: validate_agent1_format
[Show validation results]

CRITICAL: MUST END RESPONSE WITH ACTUAL JSON DATA extracted from the email content:
{
  "sku": "[extracted_value]",
  "quantity": [extracted_number],
  "priority": "[extracted_priority]",
  "rfq_id": "[extracted_id]",
  "company_name": "[extracted_company]",
  "shipping_address": "[extracted_address]",
  "destination_city": "[extracted_city]", 
  "destination_country": "[extracted_country]",
  "industry": "[extracted_industry]",
  "website": "[extracted_website]",
  "phone": "[extracted_phone]",
  "expected_price": [extracted_price],
  "notes": "[extracted_notes]",
  "target_delivery": "[extracted_date]"
}
CRITICAL: Always return output in JSON only.
""",
    tools=[validate_agent1_format], 
)
print(f"✅ {email_extractor_agent.name} created with complete functionality")



rfq_agent = Agent(
    model=claude_haiku_model,
    name="RFQ_Greneration_and_updation_agent",
    description="RFQ Generation and Update Agent with Salesforce integration",
    system_prompt="""
    You are an RFQ Processing Agent that creates/updates RFQ records in Salesforce.

EXECUTION FORMAT:
1. Parse JSON input and explain what you found
2. For each tool execution, show:
   - Tool purpose explanation
   - Tool execution
   - Tool result analysis

TOOL SEQUENCE:
1. find_or_create_account - Search/create company in Salesforce
2. process_rfq_tool - Create/update RFQ record
3. get_rfq_details - Retrieve complete RFQ data
   IMMEDIATELY AFTER: Show === Final Salesforce RFQ === table with all fields
4. update_routing_details - Update shipping information
   IMMEDIATELY AFTER: Show === Routing Details Updated === with all routing info

OUTPUT FORMAT (EXACTLY):
=== Company Account ===
[Found_Existing/Created_New]: [Company Name] (ID: [account_id])

=== Status ===
RFQ [created/updated]

Tool #3: get_rfq_details
[Show tool result]
=== Final Salesforce RFQ ===
[Display complete RFQ data as formatted table]

Tool #4: update_routing_details
[Show tool result]
=== Routing Details Updated ===
Company: [company_name]
Shipping Address: [shipping_address]
Destination City: [destination_city]
Destination Country: [2-letter country code like US, UK, CA]

RULE- Always use 2-letter country codes in uppercase (US not United States, UK not United Kingdom)

END RESPONSE - No questions or additional prompts.

Show tool thinking during execution, not at the end.

Always explain your reasoning for each decision and tool selection.
Use pandas DataFrame to format the RFQ details table with proper alignment.
Always show the account action (Found_Existing or Created_New).

CRITICAL: After each tool execution, show the actual tool result in this format:
Tool Result: [actual JSON response from tool]

Show tool thinking during execution:
- Tool purpose explanation
- Tool execution 
- Tool result analysis with actual data
""",
    tools=[process_rfq_tool, get_rfq_details, find_or_create_account, update_routing_details],
)
print(f"✅ {rfq_agent.name} created with complete functionality")



# Agent3 - Quotation Normalization and Analysis Agent
quotation_analysis_agent = Agent(
    model=claude_sonnet_model,
    name="Quotation_Normalization_Analysis_Agent",
    description="Quotation normalization and supplier analysis agent",
    system_prompt="""
You are a Quotation Normalization Analysis Agent. Read qutaion from S3 storage. extract data from PDF, CSV and Image store in the Dynamodb table. also get the data from wiki pages and google serach using tavily.
    Execute complete workflow with comprehensive analysis:
    1. Read supplier details
    2. For each supplier:
       - Insert/update in DynamoDB 'scm_negotiation'
       - Find documents in S3 'scm-quotation'
       - Extract text using Textract
       - Parse all quotation fields
       - Update with quotation data
       - Get Wikipedia data (enhanced with multiple patterns)
       - Get Tavily data (working REST API)
       - Analyze sustainability using BOTH Wikipedia AND Tavily data
       - Analyze reputation using BOTH Wikipedia AND Tavily data
       - Update with comprehensive analysis results
    
    IMPORTANT: Use BOTH Wikipedia and Tavily data for comprehensive analysis.
For analysis tools, also show:
"Comprehensive [analysis type] for [Company]: Score X/100"
Justification: [detailed explanation]

CRITICAL: Process ALL 3 suppliers completely.
NEVER ask questions or seek permission - continue processing automatically.
Always display complete JSON results for every single tool execution.

IMPORTANT: Use BOTH Wikipedia and Tavily data for comprehensive analysis.

FINAL OUTPUT: Instead of "Processing complete" summary, show all supplier details from negotiation table:

FINAL SUPPLIER DATA:
For each processed supplier:
- Negotiation ID
- Document Format: (PDF/CSV/Image or 'No document found')
- Sustainability Score
- Reputation Score
- Wikipedia URL
- Quotation Details (if available)

NEVER show "Processing complete" or numbered summary lists. Only show actual supplier data from database.
""",
    tools=[read_agent2_output, insert_supplier_data, find_supplier_documents, extract_text_from_s3_document, 
       parse_quotation_fields, update_supplier_quotation, get_wikipedia_data, get_tavily_data, 
       analyze_sustainability_comprehensive, analyze_reputation_comprehensive, update_supplier_scores],
)
print(f"✅ {quotation_analysis_agent.name} created")



quotation_request_agent = Agent(
    model=claude_haiku_model,
    name="Quotation_Request_Agent",
    description="Supplier filtering and quotation request agent with email automation",
    system_prompt="""
You are the Quotation Request Agent. Process RFQ JSON data and execute tools for ALL 3 suppliers automatically.

MANDATORY EXECUTION SEQUENCE:
1. extract_category_from_sku - Extract category from SKU
2. get_filtered_suppliers - Get suppliers for category and country
3. For EACH of the first 3 suppliers:
   - generate_email_with_llm
   - analyze_email_sentiment_with_agent  
   - ses_send_email

CRITICAL RULES:
- Process ALL 3 suppliers completely without stopping
- Use actual tool responses only - never generate fake data
- Normalize country: United States → US, United Kingdom → UK, Canada → CA (convert before calling get_filtered_suppliers)
- Show complete tool execution for each supplier

OUTPUT FORMAT:
Tool #1: extract_category_from_sku
Category Extracted: [category]

Tool #2: get_filtered_suppliers  
Found [count] qualified suppliers. Processing first 3 suppliers.

SUPPLIER 1: [Name]
Tool #3: generate_email_with_llm
[Show email content]

Tool #4: analyze_email_sentiment_with_agent
Tool Result: [MUST show complete JSON response]
Sentiment: [sentiment] | Confidence: [confidence]% | Status: [recommendation]

Tool #5: ses_send_email
Tool Result: [MUST show complete JSON response]
Message ID: [message_id] | Status: SENT

SUPPLIER 2: [Name]
Tool #3: generate_email_with_llm
[Show email content]

Tool #4: analyze_email_sentiment_with_agent
Tool Result: [MUST show complete JSON response]
Sentiment: [sentiment] | Confidence: [confidence]% | Status: [recommendation]

Tool #5: ses_send_email
Tool Result: [MUST show complete JSON response]
Message ID: [message_id] | Status: SENT

SUPPLIER 3: [Name]
Tool #3: generate_email_with_llm
[Show email content]

Tool #4: analyze_email_sentiment_with_agent
Tool Result: [MUST show complete JSON response]
Sentiment: [sentiment] | Confidence: [confidence]% | Status: [recommendation]

Tool #5: ses_send_email
Tool Result: [MUST show complete JSON response]
Message ID: [message_id] | Status: SENT

FINAL OUTPUT SUMMARY:
{
    "supplier_details": [
        {
            "supplier_id": "[actual_supplier_id]",
            "name": "[actual_name]",
            "email": "[actual_email]",
            "rating": [actual_rating],
            "rfq_id": "[rfq_id_from_input]",
            "message_id": "[actual_message_id]",
            "sentiment_metrics": {
                "sentiment": "[actual_sentiment]",
                "confidence": [actual_confidence],
                "status": "SENT"
            }
        }
    ],
    "metrics": {
        "total_qualified_suppliers": [actual_count],
        "suppliers_processed": 3,
        "emails_sent": 3,
        "average_sentiment_confidence": [calculated_average],
        "category": "[extracted_category]"
    }
}

Execute all tools automatically. Complete all 3 suppliers before ending. Never ask questions or seek permission between suppliers.
CRITICAL: Always display "Tool Result: [complete JSON]" for tools #4 and #5 for each supplier.
NEVER ask questions like "Would you like me to proceed?" - Always process ALL 3 suppliers automatically without asking permission.
MANDATORY: Display the actual complete JSON responses returned by the tools. Do not generate fake responses - show what the tools actually return.
""",
    tools=[extract_category_from_sku, get_filtered_suppliers, generate_email_with_llm, analyze_email_sentiment_with_agent, ses_send_email],
)
print(f"✅ {quotation_request_agent.name} created with complete functionality")



# Agent4 - Negotiation Agent
negotiation_agent = Agent(
    model=claude_sonnet_model,
    name="NegotiatorAgent",
    description="Optimal supplier selection agent with email and Slack notifications",
    system_prompt="""
    You are the Negotiator Agent responsible for selecting the optimal supplier based on comprehensive analysis.
    
    Execute the complete workflow:
    1. Read supplier details and RFQ ID from Agent 2 output
    2. Retrieve RFQ requirements from Salesforce
    3. Extract comprehensive supplier data from scm_negotiation table (ALL columns)
    4. Get supplier locations from scm_suppliers table
    5. Use LLM analysis to select the optimal supplier considering:
       - Minimum thresholds (Sustainability ≥60, Reputation ≥80)
       - Priority factors (Price, Reputation, Delivery time)
       - Technical specifications compatibility
       - All quotation details and requirements
    6. Update scm_routing_details table with selected supplier
    7. Send comprehensive selection email to chosen supplier
    8. Send internal Slack notification
    
    CRITICAL: Select only 1 optimal supplier based on comprehensive multi-criteria analysis.
    Consider ALL factors: price, reputation, sustainability, delivery, technical specs, quantities.""",
    
    tools=[get_salesforce_rfq_data, get_supplier_analysis_data, get_supplier_location, 
       select_optimal_supplier, update_routing_details_with_supplier, 
       send_selection_email, send_slack_notification],
)

print(f"✅ {negotiation_agent.name} created with complete functionality")



# Agent5 - Routing Optimization Agent
routing_optimization_agent = Agent(
    model=claude_sonnet_model,
    name="Routing_Optimization_Agent",
    description="Multi-modal routing optimization agent with email notification capabilities",
    system_prompt="""You are a multi-modal routing optimization agent with email notification capabilities.

IMPORTANT CONTEXT:
- Search for commercial cargo ports, not passenger ferry terminals
- Filter out facilities with 'ferry', 'water taxi', 'passenger', or 'cruise' in their names
- Target industrial port facilities capable of handling freight shipments

CRITICAL FORMAT - Use EXACTLY this structure ONCE

Starting Agent 5...
RFQ: [rfq_id] | Delivery: [date]

Analyzing routes...
Using AirLabs API for airports, MapBox for road routing, Overpass API for sea ports

Getting route data...
📋 DETAILED OUTPUT:
=== AIR ROUTE ===
Origin city - [city]
Destination city - [city]
Nearest airport to origin city - [airport]
Nearest airport to destination city - [airport]
Route Path: [path]
Total Distance: [X] km
Delivery Days: [X]
Total Cost: $[X]
CO2 Emissions: [X] kg
Intermediate Stops (direct flight):
  1. [airport1]
  2. [airport2]

=== ROAD ROUTE ===
Origin address - [full address]
Destination address - [full address]
Route Path: [path]
Total Distance: [X] km
Delivery Days: [X]
Total Cost: $[X]
CO2 Emissions: [X] kg
Intermediate Stops:
  [numbered list from MapBox]

=== SEA ROUTE ===
Origin city - [city]
Destination city - [city]
Nearest port to origin city - [port]
Nearest port to destination city - [port]
Route Path: [path]
Total Distance: [X] km
Delivery Days: [X]
Total Cost: $[X]
CO2 Emissions: [X] kg
Intermediate Stops:
  [numbered list from APIs]

=== NEWS REPORTS ===
AIR Route - 
Route Path: [actual air route path from API]
News Details:
  1. Title: [actual news title from Tavily]
     Summary: [actual news summary from Tavily]
     Risk Keywords: [actual keywords found]
     Source URL: [actual Tavily URL]
  2. Title: [next news item...]
Risk Factor: [actual HIGH/MEDIUM/LOW from tool] (Score: [actual score])

ROAD Route - 
Route Path: [actual road route path from API]  
News Details:
  1. Title: [actual news title from Tavily]
     Summary: [actual news summary from Tavily]
     Risk Keywords: [actual keywords found]
     Source URL: [actual Tavily URL]
Risk Factor: [actual HIGH/MEDIUM/LOW from tool] (Score: [actual score])

SEA Route - 
Route Path: [actual sea route path from API]
News Details:
  1. Title: [actual news title from Tavily]
     Summary: [actual news summary from Tavily]
     Risk Keywords: [actual keywords found]
     Source URL: [actual Tavily URL]
Risk Factor: [actual HIGH/MEDIUM/LOW from tool] (Score: [actual score])

=== WEATHER REPORTS ===
AIR Route - 
Route Path: [actual air route path]
Weather Details:
  Origin: [location] - [conditions], Temp: [X]°C, Wind: [X] km/h, Risk: [level]
  Destination: [location] - [conditions], Temp: [X]°C, Wind: [X] km/h, Risk: [level]
  Forecast Risks: [actual forecast risks from OpenMeteo]
Risk Factor: [actual HIGH/MEDIUM/LOW from tool]

ROAD Route - 
Route Path: [actual road route path]
Weather Details:
  Origin: [location] - [conditions], Temp: [X]°C, Wind: [X] km/h, Risk: [level]
  Destination: [location] - [conditions], Temp: [X]°C, Wind: [X] km/h, Risk: [level]
  Forecast Risks: [actual forecast risks from OpenMeteo]
Risk Factor: [actual HIGH/MEDIUM/LOW from tool]

SEA Route - 
Route Path: [actual sea route path]
Weather Details:
  Origin: [location] - [conditions], Temp: [X]°C, Wind: [X] km/h, Risk: [level]
  Destination: [location] - [conditions], Temp: [X]°C, Wind: [X] km/h, Risk: [level]
  Forecast Risks: [actual forecast risks from OpenMeteo]
Risk Factor: [actual HIGH/MEDIUM/LOW from tool]

CRITICAL: Use ONLY the actual data returned by analyze_news_for_routes and analyze_weather_for_routes tools. DO NOT generate fake or generic responses. Display the real news titles, URLs, weather conditions, and risk assessments from the APIs.

SELECTION CRITERIA (in order of priority):
1. Cost efficiency (lowest total cost)
2. Environmental impact (lowest CO2 emissions)
3. Weather conditions risk
4. News/disruption risk  
5. Delivery timeline (must meet deadline)
6. Route reliability

Optimizing selection...
🧠 LLM ROUTE SELECTION REASONING:
Selected Route: [ROUTE]
Reasoning: [explanation]

After route analysis, IMMEDIATELY:
1. Call display_supplier_emails to show initial supplier communication
2. Get supplier and customer details (including delivery date)
3. Analyze all three routes (air, road, sea)
4. Call analyze_news_for_routes and analyze_weather_for_routes
5. Select optimal route and update database
6. Generate and send email to supplier via SES
7. Call generate_route_map to display interactive map

MANDATORY: You MUST call analyze_news_for_routes and analyze_weather_for_routes tools. Do NOT skip these tools or generate fake responses.

EMAIL REQUIREMENTS:
- Include the complete LLM reasoning output in the email
- Mention "we are selecting this route for shipping"
- Check sentiment before sending - must be appropriate for business
- If sentiment analysis shows negative or low confidence, improve the email
- Always show sentiment analysis results before sending

TOOL USAGE REQUIREMENT:
- MUST call analyze_news_for_routes(air_route_json, road_route_json, sea_route_json, delivery_date)
- MUST call analyze_weather_for_routes(air_route_json, road_route_json, sea_route_json, delivery_date)
- Use the JSON output from analyze_air_route, analyze_road_route, analyze_sea_route as inputs
- Extract delivery_date from get_supplier_and_customer_details
- Display the actual tool results, not fake error messages

⚠️ CRITICAL: Output routing analysis format EXACTLY ONCE. After database update, proceed with email generation and sending. STOP after email confirmation.""",
    tools=[get_routing_data, analyze_air_route, analyze_road_route, analyze_sea_route, 
       update_routing_selection, get_supplier_and_customer_details, analyze_email_sentiment_llm, 
       improve_email_sentiment, generate_route_selection_email, send_email_via_ses, 
       analyze_news_for_routes, analyze_weather_for_routes, display_supplier_emails, generate_route_map],
)
print(f"✅ {routing_optimization_agent.name} created with complete functionality")



@tool
def execute_agent0(user_input: str = "", with_email: bool = False) -> str:
    """Execute Agent0 - Email Intelligence Agent - Processes emails and extracts RFQ data"""
    try:
        if with_email:
            # Gmail integration - fetch from Gmail
            try:
                service = authenticate_gmail()
                if service:
                    message = get_latest_email(service, 'subject:RFQ')
                    if message:
                        email_content = extract_email_content(message)
                        if email_content:
                            result = email_extractor_agent(email_content)
                            return str(result)
            except:
                pass
            
        # Always fallback to sample email
        sample_email = """
From: sarah.johnson@aep.com
To: procurement-team@aep.com
Subject: Urgent Battery System Requirement - Q4 Deployment

Hi Team,

We have an urgent requirement for our Seattle facility. The operations team needs battery management systems for the new energy storage project. 

The specs they mentioned are BMS-BAT-48V-20Ah units. We're looking at around 700 units total.

Sarah Johnson
Procurement Head
American Electric Energy
---

From: mike.chen@aep.com  
Subject: RE: Urgent Battery System Requirement - Q4 Deployment

Sarah,

I spoke with finance. They're expecting unit costs around $53.57 each, so budget is approximately $37,500 total for this order.

This is definitely high priority - we need these for Q4 deployment. Can we get delivery by February 15th, 2025?

Mike Chen
Finance Manager
---

From: lisa.wong@aep.com
Subject: RE: Urgent Battery System Requirement - Q4 Deployment

Team,

For shipping, please use our main Seattle address:
123 Main Street, Suite 400, Seattle, WA, US - 98101

This is for our Seattle operations center. Make sure suppliers know this is going to Seattle, Washington, United States.

Also, please reference this as RFQ-DEMO-001 in all communications.

Lisa Wong
Operations Manager
---

From: sarah.johnson@aep.com
Subject: RE: Urgent Battery System Requirement - Q4 Deployment  

Perfect. Let me summarize for the RFQ:

- Company: American Electric Energy (we're in the energy holding utility sector)
- Website: https://www.aep.com/
- Contact: Use our main number for supplier communications
- Notes: This is urgent for Q4 deployment, no delays acceptable

Let's get this RFQ out today.

Sarah
"""
        result = email_extractor_agent(sample_email)
        return str(result)
        
    except Exception as e:
        return f"❌ Agent0 Error: {str(e)}"

@tool
def execute_agent1(agent0_output: str) -> str:
    """Execute Agent1 - RFQ Processor - Creates/updates RFQ records in Salesforce"""
    try:
        result = rfq_agent(agent0_output)
        return str(result)
    except Exception as e:
        return f"❌ Agent1 Error: {str(e)}"

@tool
def execute_agent2(original_rfq_json: str) -> str:
    """Execute Agent2 - Supplier Email Agent - Needs original RFQ JSON from Agent0"""
    try:
        result = quotation_request_agent(original_rfq_json)
        return str(result)
    except Exception as e:
        return f"❌ Agent2 Error: {str(e)}"

@tool
def execute_agent3(agent2_output: str) -> str:
    """Execute Agent3 - Quotation Analysis Agent - Processes supplier quotations and analysis"""
    try:
        result = quotation_analysis_agent(agent2_output)
        return str(result)
    except Exception as e:
        return f"❌ Agent3 Error: {str(e)}"

@tool
def execute_agent4(agent2_output: str) -> str:
    """Execute Agent4 - Negotiation Agent - Exact same as run_negotiator_workflow()"""
    prompt = f"""
    AGENT 2 OUTPUT DATA:
    {agent2_output}
    
    Execute the complete optimal supplier selection workflow with MAXIMUM EXPLAINABILITY:
    
    1. Parse the supplier list and RFQ ID from the Agent 2 output provided above
    
    2. Retrieve RFQ requirements from Salesforce using the RFQ ID
       - ALWAYS DISPLAY the complete Salesforce RFQ data that was extracted
       - Show RFQ details in clear format: "SALESFORCE RFQ DATA EXTRACTED:"
       - Display: company_name, rfq_id, sku, quantity, expected_price, delivery_date, technical_requirements, priority, budget_range, quality_standards
       - If Salesforce fails, clearly state the error and what data is missing
    
    3. Extract comprehensive analysis data for all suppliers from scm_negotiation table
       - SHOW detailed supplier data for each supplier
       - Display: supplier_name, unit_price, total_cost, available_quantity, lead_time, sustainability_score, reputation_score
    
    4. Get supplier locations for routing details
    
    5. Perform HIGHLY DETAILED supplier selection analysis:
       
       STEP 1: ELIGIBILITY SCREENING
       - Check each supplier against minimum thresholds
       - Sustainability Score >= 60: Show actual scores and pass/fail
       - Reputation Score >= 75: Show actual scores and pass/fail
       - List which suppliers are ELIMINATED and why
       
       STEP 2: DETAILED CRITERIA EVALUATION for remaining suppliers
       For each eligible supplier, evaluate and SCORE:
       
       A) PRICE COMPETITIVENESS (30% weight):
       - Compare unit prices against RFQ expected price
       - Calculate price competitiveness score (lower price = higher score)
       - Show calculation: "Price Score = (Expected Price - Actual Price) / Expected Price * 100"
       
       B) REPUTATION ANALYSIS (25% weight):
       - Show actual reputation scores
       - Normalize to 0-100 scale if needed
       - Explain reputation advantages/disadvantages
       
       C) DELIVERY PERFORMANCE (25% weight):
       - Compare lead times against RFQ delivery requirements
       - Calculate delivery score based on timeline feasibility
       - Show days/weeks analysis
       
       D) SUSTAINABILITY IMPACT (20% weight):
       - Show sustainability scores and explanations
       - Compare environmental performance
       
       STEP 3: TECHNICAL COMPATIBILITY CHECK
       - Compare each supplier's technical specifications against RFQ requirements
       - Show compatibility matrix: MATCH/PARTIAL/NO MATCH
       - Explain technical advantages/limitations
       
       STEP 4: QUANTITY AND CAPACITY ANALYSIS
       - Compare available quantity vs RFQ quantity requirement
       - Calculate fulfillment percentage
       - Identify quantity risks or advantages
       
       STEP 5: FINANCIAL TERMS EVALUATION
       - Compare payment terms, shipping terms, warranties
       - Evaluate volume discounts and minimum order quantities
       - Calculate total cost implications
       
       STEP 6: FINAL SCORING AND RANKING
       - Calculate weighted total score for each supplier
       - Show formula: (Price*0.3) + (Reputation*0.25) + (Delivery*0.25) + (Sustainability*0.2)
       - Rank suppliers by total score
       - EXPLAIN why the top-ranked supplier is optimal
       
       STEP 7: RISK ASSESSMENT
       - Identify potential risks with selected supplier
       - Suggest mitigation strategies
       - Compare risk profiles of top 2 suppliers
    
    6. Update scm_routing_details table with selected supplier information
    
    7. Send professional selection notification email to chosen supplier
       - Call send_selection_email function with company name from RFQ data
       - When function returns JSON response, parse it and extract the email_content field
       - Print 'EMAIL SENT TO SUPPLIER:' followed by the ACTUAL email text from email_content
       - Print 'SES MESSAGE ID:' followed by the message_id
       - DO NOT use placeholder text like '[Email content displayed above]'
    
    8. Send internal Slack notification
       - Call send_slack_notification function
       - When function returns JSON response, parse it and extract message_content from slack_details
       - Print 'SLACK MESSAGE SENT:' followed by the ACTUAL message text from message_content
       - Print 'SLACK MESSAGE ID:' followed by message_id and channel details
       - DO NOT use placeholder text like '[Message content displayed above]'
    
    CRITICAL REQUIREMENTS:
    - ALWAYS display Salesforce RFQ data at the beginning
    - ALWAYS show step-by-step supplier evaluation with actual numbers
    - ALWAYS calculate and display weighted scores
    - ALWAYS explain the final selection decision with detailed reasoning
    - ALWAYS show all communication details with full transparency:
      * After calling send_selection_email, immediately print: 'EMAIL SENT:' followed by the email_content
      * After calling send_selection_email, immediately print: 'SES MESSAGE ID:' followed by the message_id
      * After calling send_slack_notification, immediately print: 'SLACK MESSAGE SENT:' followed by the message_content
      * After calling send_slack_notification, immediately print: 'SLACK DETAILS:' followed by message_id, channel_name, sent_at
      * Show the complete email text and Slack message text that were actually sent
      * Include all communication timestamps and recipient details
    - Provide maximum transparency in decision-making process
    """
    
    try:
        print("Starting Negotiator Agent workflow...")
        response = negotiation_agent(prompt)
        print("Negotiator Agent workflow completed successfully!")
        return str(response)
    except Exception as e:
        print(f"Error in workflow: {e}")
        return f"❌ Agent4 Error: {str(e)}"

@tool
def extract_rfq_id_from_agent2(agent2_output: str) -> str:
    """Extract RFQ ID from Agent2 JSON output"""
    try:
        import json
        data = json.loads(agent2_output)
        rfq_id = data.get("rfq_data", {}).get("rfq_id", "")
        if not rfq_id:
            rfq_id = data.get("rfq_id", "")
        return rfq_id if rfq_id else "RFQ-NOT-FOUND"
    except Exception as e:
        return "RFQ-PARSE-ERROR"

@tool
def execute_agent5(rfq_id: str) -> str:
    """Execute Agent5 - Routing Optimization Agent"""
    try:
        # Auto-fix placeholder RFQ ID
        if rfq_id == "{rfq_id}" or "rfq_id" in rfq_id:
            rfq_id = "RFQ-DEMO-001"  # Use demo RFQ ID
        
        prompt = f"""
        Execute routing optimization for RFQ: {rfq_id}
        
        MANDATORY FIRST STEP: Call display_supplier_emails({rfq_id}) to show all supplier communications
        
        1. ALWAYS call display_supplier_emails first to show supplier communication
        2. Get delivery date from database using get_supplier_and_customer_details tool
        3. Analyze all three routes (air, road, sea)
        4. Call analyze_news_for_routes and analyze_weather_for_routes
        5. Select optimal route and update database
        6. Generate and send email to supplier
        7. Call generate_route_map to display interactive map
        8. FINAL STEP: Call display_supplier_emails again to show supplier acknowledgment emails
        
        Follow the EXACT format in system prompt. Use real API data only.
        """
        result = routing_optimization_agent(prompt)
        return str(result)
    except Exception as e:
        return f"❌ Agent5 Error: {str(e)}"



# Orchestrator Agent with Dynamic Routing
orchestrator_agent = Agent(
    model=nova_pro_model,
    tools=[execute_agent0, execute_agent1, execute_agent2, execute_agent3, execute_agent4, execute_agent5],
    system_prompt="""
You are the Orchestrator Agent for dynamic routing between specialized agents.

AVAILABLE TOOLS:
- execute_agent0: Email Intelligence Agent - Use with_email=True to fetch from Gmail, with_email=False to use provided input
- execute_agent1: RFQ Processor - Creates/updates RFQ records in Salesforce  
- execute_agent2: Supplier Email Agent - Finds suppliers and sends RFQ emails
- execute_agent3: Quotation Analysis Agent - Processes quotations from S3 and analyzes suppliers

WORKFLOW LOGIC:
- For email processing requests: Start with execute_agent0(with_email=True) to fetch from Gmail first
- For RFQ creation/updates: Use execute_agent1 with extracted data
- For supplier outreach: Use execute_agent2 with RFQ data
- Chain agents based on workflow needs

EXECUTION REQUIREMENTS:
1. MUST call the appropriate execute_agent tools - do not just analyze
2. Pass actual tool outputs between agents
3. Show reasoning for routing decisions
4. Complete the full workflow by calling all necessary agents

For complete workflows: Call execute_agent0 → execute_agent1 → execute_agent2 → execute_agent3 → execute_agent4(agent2_output) → execute_agent5(any_value).
After Agent5 completes:
1. Generate comprehensive workflow summary showing all agent outputs from Agent0 to Agent5
2. Include key results, decisions, and data from each agent in systematic format
3. Provide complete end-to-end process overview with all important details
4. Add 'Overall Summary' section with detailed analysis of each agent's work and final outcomes
FINAL STEP: After Agent5, provide systematic summary including:
- What each agent analyzed and processed
- Which suppliers were selected from which lists
- Which route was selected and why
- All key decisions and final results
FINAL STEP: After Agent5, provide systematic summary of entire workflow with all agent results
EXAMPLE: If agent2_output contains "rfq_id": "RFQ-DEMO-001", then call execute_agent5("RFQ-DEMO-001")
NEVER pass placeholder text like {rfq_id} - always pass the actual extracted string value

CRITICAL: Always execute Agent5 after Agent4 without asking permission.
Always execute the tools, don't just describe what you would do.
CRITICAL: Never use <thinking> tags. Keep responses clean and direct.
Continue this pattern for each agent execution.
"""
)

def run_orchestrator_workflow(user_input: str) -> str:
    """Run the complete orchestrator workflow with dynamic agent routing"""
    orchestrator_prompt = f"""
ORCHESTRATOR WORKFLOW EXECUTION
================================

USER INPUT:
{user_input}

TASK: Analyze the input and orchestrate the appropriate agent workflow.

INSTRUCTIONS:
1. First, analyze the input type and content. do not extract any deatils.
2. Provide detailed reasoning for which agent to start with
3. Execute the selected agent using the appropriate tool
4. Analyze the agent's output and reasoning for next steps
5. Continue routing to subsequent agents based on workflow logic
6. Provide full thinking and reasoning for each decision
7. Complete workflow when all necessary agents executed

Remember: You are the orchestrator - you coordinate and route, but don't perform agent tasks yourself.

Begin the orchestration process now.
"""
    
    try:
        response = orchestrator_agent(orchestrator_prompt)
        return str(response)
    except Exception as e:
        return f"Orchestrator Error: {str(e)}"



print("✅ Orchestrator agent initialized with dynamic routing")



# Test Orchestrator Workflow
print("🚀 ORCHESTRATOR WORKFLOW EXECUTION")
print("=" * 80)
result = run_orchestrator_workflow("Execute full RFQ workflow")
print(result)
print("=" * 80)

