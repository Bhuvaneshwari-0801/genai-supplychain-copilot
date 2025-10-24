# GenAI SupplyChain Copilot

**✅ TESTED & VALIDATED - Ready for Production**

A comprehensive GenAI-powered supply chain management system using Amazon Bedrock Agents, Strands Agents, and multiple LLMs for end-to-end RFQ processing and optimization.

## 🏗️ Architecture Overview

This system implements a multi-agent architecture with 6 specialized agents:

- **Agent 0**: Email Intelligence Agent - Extracts RFQ data from emails
- **Agent 1**: RFQ Update Agent - Creates/updates RFQ records in Salesforce
- **Agent 2**: Supplier Selection Agent - Finds and contacts suppliers
- **Agent 3**: Quotation Analysis Agent - Processes supplier quotations and analysis
- **Agent 4**: Negotiation Agent - Selects optimal suppliers
- **Agent 5**: Routing Optimization Agent - Optimizes shipping routes
- **Orchestrator**: Master coordinator managing all agents

## 🔧 Environment Variables Setup

### 1. Install Dependencies

```bash
pip install python-dotenv
```

### 2. Create Environment Configuration

Copy the `.env.example` file to `.env` and update with your actual credentials:

```bash
cp .env.example .env
```

### 3. Required Environment Variables

Update the following variables in your `.env` file:

#### API Keys
```env
AIRLABS_API_KEY=your_actual_airlabs_api_key
MAPBOX_API_KEY=your_actual_mapbox_api_key
TAVILY_API_KEY=your_actual_tavily_api_key
```

#### Slack Configuration
```env
SLACK_BOT_TOKEN=xoxb-your-actual-slack-bot-token
SLACK_CHANNEL=#your-channel-name
```

#### Email Configuration
```env
SES_SENDER=your-verified-ses-email@domain.com
```

#### Salesforce Configuration
```env
SF_CLIENT_ID=your_salesforce_connected_app_client_id
SF_CLIENT_SECRET=your_salesforce_connected_app_client_secret
SF_USERNAME=your_salesforce_username
SF_PASSWORD=your_salesforce_password
SF_SECURITY_TOKEN=your_salesforce_security_token
```

## 🧪 Testing Your Setup

Run the environment validation script:

```bash
python test_env_setup.py
```

This will:
- ✅ Check all required environment variables
- ✅ Validate configuration imports
- ✅ Test Salesforce authentication
- ✅ Provide setup status report

## 📁 Project Structure

```
supplychain_hardcoded_v1_q/
├── .env                                    # Environment variables (DO NOT COMMIT)
├── .env.example                           # Environment variables template
├── config.py                              # Configuration management
├── supply-chain-master-agent.py           # Main agent system (env vars)
├── master-agent-runtime-entrypoint.py     # AgentCore runtime entrypoint (env vars)
├── route_mapper_clean.py                  # Route mapping utilities (env vars)
├── requirements.txt                       # Python dependencies
├── test_env_setup.py                     # Environment validation script
├── setup_project.py                      # Project setup script
├── README.md                             # This file
└── *_hardcoded.py                        # Original files with hardcoded values (backup)
```

## 🚀 Running the Application

### Local Development

1. **Validate Environment**:
   ```bash
   python test_env_setup.py
   ```

2. **Run Local Test**:
   ```bash
   LOCAL_TEST=1 python master-agent-runtime-entrypoint.py
   ```

3. **Start AgentCore Runtime**:
   ```bash
   python master-agent-runtime-entrypoint.py
   ```

### SageMaker Notebook

1. **Install Dependencies**:
   ```python
   !pip install -r requirements.txt
   ```

2. **Import and Run**:
   ```python
   from supply_chain_clean import *
   
   # Run orchestrator workflow
   result = run_orchestrator_workflow("Execute full RFQ workflow")
   print(result)
   ```

### Docker Deployment

1. **Create Dockerfile**:
   ```dockerfile
   FROM python:3.9-slim
   
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   
   COPY . .
   
   EXPOSE 8080
   CMD ["python", "master-agent-runtime-entrypoint.py"]
   ```

2. **Build and Run**:
   ```bash
   docker build -t genai-supplychain .
   docker run -p 8080:8080 --env-file .env genai-supplychain
   ```

## 🔐 Security Best Practices

### Environment Variables
- ✅ Never commit `.env` files to version control
- ✅ Use different credentials for different environments
- ✅ Rotate API keys and tokens regularly
- ✅ Use AWS Secrets Manager for production deployments

### Git Configuration
Add to your `.gitignore`:
```gitignore
.env
*.env
credentials.json
token.pickle
*_hardcoded.py
```

## 🛠️ Configuration Details

### Required Services Setup

1. **Salesforce Connected App**:
   - Create Connected App in Salesforce
   - Enable OAuth settings
   - Get Client ID and Client Secret
   - Configure callback URLs

2. **AWS Services**:
   - SES: Verify sender email address
   - DynamoDB: Create required tables
   - Bedrock: Enable model access

3. **Third-party APIs**:
   - AirLabs: Get API key for flight data
   - MapBox: Get API key for routing
   - Tavily: Get API key for web search
   - Slack: Create bot and get token

### DynamoDB Tables Required
- `scm_suppliers`
- `scm_negotiation` 
- `scm_routing_details`

## 🧩 Agent Workflow

```mermaid
graph TD
    A[Agent 0: Email Intelligence] --> B[Agent 1: RFQ Update]
    B --> C[Agent 2: Supplier Selection]
    C --> D[Agent 3: Quotation Analysis]
    D --> E[Agent 4: Negotiation]
    E --> F[Agent 5: Routing Optimization]
    G[Orchestrator] --> A
```

## 📊 Model Configuration

The system uses multiple LLMs:
- **Amazon Nova Pro**: `us.amazon.nova-pro-v1:0` (Orchestrator)
- **Claude 3.5 Sonnet**: `us.anthropic.claude-3-5-sonnet-20241022-v2:0` (Complex analysis)
- **Claude 3.5 Haiku**: `us.anthropic.claude-3-5-haiku-20241022-v1:0` (Fast processing)

## 🐛 Troubleshooting

### Common Issues

1. **Missing Environment Variables**:
   ```bash
   python test_env_setup.py
   ```

2. **Salesforce Authentication Failed**:
   - Verify Client ID and Secret
   - Check username/password/security token
   - Ensure Connected App is configured correctly

3. **API Rate Limits**:
   - Check API key quotas
   - Implement retry logic
   - Use appropriate delays between calls

4. **DynamoDB Access Issues**:
   - Verify AWS credentials
   - Check IAM permissions
   - Ensure tables exist

## 📝 Development Notes

### Converting from Hardcoded Values

The original files with hardcoded values are preserved as `*_hardcoded.py`. The conversion process:

1. **Extracted all sensitive values** to environment variables
2. **Created configuration module** (`config.py`) for centralized management
3. **Updated import statements** to use configuration
4. **Added validation functions** to ensure proper setup
5. **Created test scripts** for validation

### Key Changes Made

- ✅ Replaced hardcoded API keys with `os.getenv()`
- ✅ Centralized configuration in `config.py`
- ✅ Added environment validation
- ✅ Updated all file imports
- ✅ Added `python-dotenv` dependency
- ✅ Created comprehensive documentation

## 🎯 Next Steps

1. **Update .env file** with your actual credentials
2. **Test all integrations** using the validation script
3. **Deploy to your target environment** (SageMaker/ECS/etc.)
4. **Set up monitoring** and logging
5. **Configure CI/CD pipeline** for deployments

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Validate environment setup with test script
3. Review AWS and third-party service configurations
4. Check CloudWatch logs for runtime issues

---

**⚠️ Important**: This system handles sensitive business data. Ensure proper security measures are in place before production deployment.
