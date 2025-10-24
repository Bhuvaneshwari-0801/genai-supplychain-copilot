# GitHub Workflow Guide

## 📋 Files in This Folder (Pushed to GitHub)

### Core Files
- `supply-chain-master-agent.py` - Main orchestrator with 6 agents
- `master-agent-runtime-entrypoint.py` - AgentCore runtime entrypoint
- `route_mapper.py` - Route mapping utilities
- `config.py` - Configuration management
- `supply_chain_clean.py` - Clean utility functions

### Configuration
- `.env.example` - Environment template (safe for GitHub)
- `.gitignore` - Protects sensitive files
- `requirements.txt` - Python dependencies

### Documentation & Testing
- `README.md` - Main documentation
- `PROJECT_SUMMARY.md` - Project overview
- `test_env_setup.py` - Environment validation
- `setup_project.py` - Setup utilities

## 🔄 Workflow for Future Changes

### Step 1: Setup Local Environment
```bash
cd github-repo-files
cp ../.env .  # Copy your credentials (not in git)
```

### Step 2: Make Changes
```bash
# Edit any file
nano supply-chain-master-agent.py
```

### Step 3: Test Locally
```bash
# Quick test
LOCAL_TEST=1 python master-agent-runtime-entrypoint.py

# Environment test
python test_env_setup.py
```

### Step 4: Git Operations
```bash
# Initialize git (if not done)
git init
git remote add origin https://github.com/khan-cloudgeek/genai-supplychain-copilot.git

# Check status
git status

# Add changes
git add .

# Commit
git commit -m "Description of your changes"

# Push using your token
git push https://YOUR_GITHUB_TOKEN@github.com/khan-cloudgeek/genai-supplychain-copilot.git master
```

## 🛡️ Security Checklist
- ✅ .env file is in .gitignore
- ✅ No hardcoded secrets in code
- ✅ Only .env.example in repository
- ✅ GitHub token not in committed files

## 🧪 Testing Checklist
- ✅ Environment validation passes
- ✅ Local workflow test succeeds
- ✅ No import errors
- ✅ Configuration loads correctly
