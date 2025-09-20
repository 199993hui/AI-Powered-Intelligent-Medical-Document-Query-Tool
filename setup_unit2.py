#!/usr/bin/env python3
"""
Setup script for Unit 2: Search Engine & Query Processing
Installs AWS services dependencies and configures the search engine
"""

import subprocess
import sys
import os

def install_requirements():
    """Install required packages"""
    requirements = [
        "boto3>=1.34.0",
        "opensearch-py>=2.4.0"
    ]
    
    for req in requirements:
        print(f"Installing {req}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--break-system-packages", req])

def check_aws_config():
    """Check AWS configuration"""
    try:
        import boto3
        
        # Test AWS credentials
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print(f"✅ AWS configured for account: {identity['Account']}")
        
        # Check required services availability
        services = {
            'bedrock-runtime': 'us-east-1',
            'comprehendmedical': 'us-east-1',
            's3': 'us-east-1'
        }
        
        for service, region in services.items():
            try:
                client = boto3.client(service, region_name=region)
                print(f"✅ {service} available in {region}")
            except Exception as e:
                print(f"⚠️  {service} not available: {e}")
        
    except Exception as e:
        print(f"❌ AWS configuration error: {e}")
        print("Please run: aws configure")

def main():
    print("🚀 Setting up Unit 2: Search Engine & Query Processing")
    print("=" * 50)
    
    # Install requirements
    print("\n📦 Installing Python packages...")
    install_requirements()
    
    # Check AWS configuration
    print("\n🔧 Checking AWS configuration...")
    check_aws_config()
    
    print("\n✅ Unit 2 setup complete!")
    print("\nNext steps:")
    print("1. Start backend: cd backend && python app.py")
    print("2. Start frontend: streamlit run app.py")
    print("3. Upload medical PDFs and test search functionality")

if __name__ == "__main__":
    main()