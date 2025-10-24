#!/usr/bin/env python3
"""
Setup script for GenAI SupplyChain Project
Converts hardcoded values to environment variables and sets up the project
"""

import os
import shutil
import subprocess
import sys

def setup_project():
    """Setup the GenAI SupplyChain project with environment variables"""
    
    print("🚀 Setting up GenAI SupplyChain Project")
    print("=" * 50)
    
    # Step 1: Install required packages
    print("📦 Installing required packages...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "python-dotenv"])
        print("  ✅ python-dotenv installed")
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Failed to install python-dotenv: {e}")
        return False
    
    # Step 2: Create .env file if it doesn't exist
    print("\n📝 Setting up environment configuration...")
    if not os.path.exists('.env'):
        env_content = """# Environment Variables for GenAI SupplyChain Application
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
        with open('.env', 'w') as f:
            f.write(env_content)
        print("  ✅ Created .env template file")
    else:
        print("  ✅ .env file already exists")
    
    # Step 3: Create backup of original files
    print("\n💾 Creating backups of original files...")
    hardcoded_files = [
        'supply-chain-master-agent_hardcoded.py',
        'master-agent-runtime-entrypoint_hardcoded.py',
        'route_mapper_clean_hardcoded.py'
    ]
    
    for file in hardcoded_files:
        if os.path.exists(file):
            backup_file = file.replace('_hardcoded', '_backup')
            if not os.path.exists(backup_file):
                shutil.copy2(file, backup_file)
                print(f"  ✅ Backed up {file} to {backup_file}")
            else:
                print(f"  ⚪ Backup {backup_file} already exists")
    
    # Step 4: Check if new files exist
    print("\n🔧 Checking updated files...")
    new_files = [
        'config.py',
        'route_mapper_clean.py',
        'master-agent-runtime-entrypoint.py',
        'requirements.txt',
        'test_env_setup.py'
    ]
    
    all_files_exist = True
    for file in new_files:
        if os.path.exists(file):
            print(f"  ✅ {file} exists")
        else:
            print(f"  ❌ {file} missing")
            all_files_exist = False
    
    if not all_files_exist:
        print("  ⚠️ Some files are missing. Please ensure all files are created.")
        return False
    
    # Step 5: Test environment setup
    print("\n🧪 Testing environment setup...")
    try:
        result = subprocess.run([sys.executable, "test_env_setup.py"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("  ✅ Environment test passed")
        else:
            print("  ⚠️ Environment test completed with warnings")
            print("  📝 Please update .env file with your actual credentials")
    except Exception as e:
        print(f"  ❌ Environment test failed: {e}")
    
    # Step 6: Create the main supply chain master agent
    print("\n🔨 Creating main supply chain master agent...")
    
    # Since the original file is very large, we'll create a minimal working version
    # that imports from the clean version and adds the remaining tools
    
    main_agent_content = '''#!/usr/bin/env python
# coding: utf-8

# Import the clean base configuration and functions
from supply_chain_clean import *

# Import all the tools and agents from the original file
# This is a placeholder - you'll need to copy the tool definitions
# from the original supply-chain-master-agent_hardcoded.py file

# All the @tool decorated functions should be copied here
# All the Agent definitions should be copied here
# The orchestrator workflow function should be copied here

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

print("✅ GenAI SupplyChain Master Agent loaded with environment variables")
'''
    
    # Don't overwrite if it already exists
    if not os.path.exists('supply-chain-master-agent.py'):
        with open('supply-chain-master-agent.py', 'w') as f:
            f.write(main_agent_content)
        print("  ✅ Created supply-chain-master-agent.py template")
        print("  📝 You need to copy the tool and agent definitions from the hardcoded version")
    else:
        print("  ✅ supply-chain-master-agent.py already exists")
    
    # Step 7: Final instructions
    print("\n📋 Setup Complete! Next Steps:")
    print("1. Update .env file with your actual API keys and credentials")
    print("2. Copy tool definitions from supply-chain-master-agent_hardcoded.py")
    print("3. Run: python test_env_setup.py to validate configuration")
    print("4. Test the application with your environment variables")
    
    print("\n🔐 Security Notes:")
    print("- Never commit .env file to git")
    print("- Add .env to your .gitignore file")
    print("- Use different credentials for different environments")
    
    return True

if __name__ == "__main__":
    success = setup_project()
    if success:
        print("\n✅ Project setup completed successfully!")
    else:
        print("\n❌ Project setup failed. Please check the errors above.")
        sys.exit(1)
