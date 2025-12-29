#!/usr/bin/env python3
"""
Deployment Verification Script

Run this script to verify that your deployment is configured correctly.
It checks all critical components before going live.
"""

import sys
import os
import requests
from pathlib import Path

# ANSI color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'='*80}{RESET}\n")

def print_success(text):
    print(f"{GREEN}✓ {text}{RESET}")

def print_error(text):
    print(f"{RED}✗ {text}{RESET}")

def print_warning(text):
    print(f"{YELLOW}⚠ {text}{RESET}")

def check_env_file():
    """Check if .env file exists and has required variables"""
    print_header("1. Checking Environment Configuration")

    env_path = Path(".env")
    if not env_path.exists():
        print_error(".env file not found!")
        print_warning("Copy .env.example to .env and fill in your values")
        return False

    print_success(".env file exists")

    # Check for critical variables
    required_vars = [
        "OPENAI_API_KEY",
        "PINECONE_API_KEY",
        "DB_USER",
        "DB_PASSWORD",
        "DB_NAME"
    ]

    missing_vars = []
    with open(env_path, 'r') as f:
        env_content = f.read()
        for var in required_vars:
            if f"{var}=" not in env_content or f"{var}=YOUR_" in env_content or f"{var}=sk-proj-YOUR_" in env_content:
                missing_vars.append(var)

    if missing_vars:
        print_error(f"Missing or placeholder values for: {', '.join(missing_vars)}")
        return False
    else:
        print_success("All required environment variables are set")
        return True

def check_code_changes():
    """Verify critical code changes are present"""
    print_header("2. Checking Critical Code Changes")

    checks_passed = True

    # Check 1: Config.py has the fix for load_dotenv
    config_path = Path("src/core/config.py")
    if config_path.exists():
        with open(config_path, 'r') as f:
            config_content = f.read()
            if "PROJECT_ROOT" in config_content and "ENV_PATH" in config_content:
                print_success("OpenAI API key loading fix is present (config.py)")
            else:
                print_error("OpenAI API key loading fix is MISSING in config.py")
                checks_passed = False
    else:
        print_error("config.py not found")
        checks_passed = False

    # Check 2: Main.py mounts static files
    main_path = Path("src/main.py")
    if main_path.exists():
        with open(main_path, 'r') as f:
            main_content = f.read()
            if "StaticFiles" in main_content and "/frontends" in main_content:
                print_success("Static files mounting is configured (main.py)")
            else:
                print_error("Static files mounting is MISSING in main.py")
                checks_passed = False
    else:
        print_error("main.py not found")
        checks_passed = False

    # Check 3: Agent passes clinic_name
    agent_path = Path("src/core/agent.py")
    if agent_path.exists():
        with open(agent_path, 'r') as f:
            agent_content = f.read()
            if "clinic_name: Optional[str]" in agent_content:
                print_success("Clinic name parameter added to agent (agent.py)")
            else:
                print_error("Clinic name parameter is MISSING in agent.py")
                checks_passed = False
    else:
        print_error("agent.py not found")
        checks_passed = False

    return checks_passed

def check_frontends_directory():
    """Check if frontends directory exists"""
    print_header("3. Checking Frontend Files")

    frontends_path = Path("frontends/clinical-ui")
    if not frontends_path.exists():
        print_error("frontends/clinical-ui directory not found")
        return False

    required_files = ["index.html", "clinical.js", "clinical.css"]
    missing_files = []

    for file in required_files:
        if not (frontends_path / file).exists():
            missing_files.append(file)

    if missing_files:
        print_error(f"Missing frontend files: {', '.join(missing_files)}")
        return False
    else:
        print_success("All frontend files are present")
        return True

def check_api_running(base_url="http://localhost:8000"):
    """Check if API is running and responding"""
    print_header("4. Checking API Status")

    try:
        # Check root endpoint
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            print_success(f"API is running at {base_url}")
        else:
            print_error(f"API returned status code: {response.status_code}")
            return False

        # Check config endpoint
        response = requests.get(f"{base_url}/config", timeout=5)
        if response.status_code == 200:
            config = response.json()
            if config.get("openai_api_key_set") == "Yes":
                print_success("OpenAI API key is loaded correctly")
            else:
                print_error("OpenAI API key is NOT loaded")
                return False
        else:
            print_warning("Could not check /config endpoint")

        # Check status endpoint
        response = requests.get(f"{base_url}/status", timeout=5)
        if response.status_code == 200:
            status = response.json()
            if status.get("api_status") == "ok" and status.get("db_status") == "ok":
                print_success("API and Database are healthy")
            else:
                print_error(f"Status check failed: {status}")
                return False
        else:
            print_warning("Could not check /status endpoint")

        return True

    except requests.exceptions.ConnectionError:
        print_error(f"Could not connect to API at {base_url}")
        print_warning("Make sure the API is running with: docker-compose up -d")
        return False
    except Exception as e:
        print_error(f"Error checking API: {e}")
        return False

def check_database_clients():
    """Check if database has clients with access tokens"""
    print_header("5. Checking Database Clients")

    try:
        from src.core.db import get_db
        from src.models.models import Client

        db = next(get_db())
        clients = db.query(Client).all()
        db.close()

        if not clients:
            print_error("No clients found in database")
            print_warning("Run: python -c 'from src.core.db import seed_test_data; seed_test_data()'")
            return False

        print_success(f"Found {len(clients)} client(s) in database:")

        has_tokens = True
        for client in clients:
            if client.access_token:
                print(f"  - {client.clinic_name} (Token: {client.access_token[:20]}...)")
            else:
                print_warning(f"  - {client.clinic_name} (NO ACCESS TOKEN)")
                has_tokens = False

        if not has_tokens:
            print_warning("Some clients missing access tokens. Generate URLs with: python generate_permanent_url.py")

        return True

    except Exception as e:
        print_error(f"Could not check database: {e}")
        print_warning("Make sure database is running and migrations are applied")
        return False

def main():
    print_header("Deployment Verification Tool")
    print("This script verifies your deployment is ready to go live.\n")

    all_checks = [
        ("Environment Configuration", check_env_file),
        ("Code Changes", check_code_changes),
        ("Frontend Files", check_frontends_directory),
        ("API Status", lambda: check_api_running()),
        ("Database Clients", check_database_clients),
    ]

    results = []
    for check_name, check_func in all_checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print_error(f"Error during {check_name}: {e}")
            results.append((check_name, False))

    # Summary
    print_header("Verification Summary")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for check_name, result in results:
        if result:
            print_success(f"{check_name}: PASSED")
        else:
            print_error(f"{check_name}: FAILED")

    print(f"\n{passed}/{total} checks passed\n")

    if passed == total:
        print_success("✓ All checks passed! Your deployment is ready.")
        print("\nNext steps:")
        print("1. Generate access URLs: python generate_permanent_url.py")
        print("2. Test the Clinical UI with a client")
        print("3. Monitor logs: docker-compose logs -f app")
        return 0
    else:
        print_error("✗ Some checks failed. Please fix the issues above before deploying.")
        print("\nSee DEPLOYMENT_CHECKLIST.md for detailed instructions.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
