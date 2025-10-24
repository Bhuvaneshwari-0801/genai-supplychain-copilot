# Local Testing Guide

## 🧪 Before Pushing to GitHub

### 1. Environment Setup
```bash
# Copy your .env file (not in GitHub)
cp ../.env .

# Validate environment
python test_env_setup.py
```

### 2. Local Testing Options

#### Option A: Quick Workflow Test
```bash
LOCAL_TEST=1 python master-agent-runtime-entrypoint.py
```

#### Option B: Individual Component Tests
```bash
# Test configuration
python -c "import config; config.validate_config()"

# Test route mapper
python -c "from route_mapper import create_route_map; print('Route mapper OK')"

# Test main agent
python -c "from supply_chain_clean import *; print('Supply chain OK')"
```

#### Option C: Full Environment Validation
```bash
python test_env_setup.py
```

### 3. Git Workflow for Changes

#### Make Changes and Test
```bash
# 1. Make your changes to files
nano supply-chain-master-agent.py

# 2. Test locally first
LOCAL_TEST=1 python master-agent-runtime-entrypoint.py

# 3. Validate environment still works
python test_env_setup.py

# 4. Check git status
git status

# 5. Add changes
git add .

# 6. Commit with message
git commit -m "Your change description"

# 7. Push to GitHub
git push origin master
```

### 4. Common Test Commands
```bash
# Full system test
LOCAL_TEST=1 python master-agent-runtime-entrypoint.py

# Environment validation
python test_env_setup.py

# Configuration test
python -c "import config; print('Config OK')"

# Import test
python -c "from supply_chain_clean import *; print('All imports OK')"
```

## ⚠️ Important Notes
- Always test locally before pushing
- Never commit .env file (it's in .gitignore)
- Use LOCAL_TEST=1 for workflow testing
- Validate environment after changes
