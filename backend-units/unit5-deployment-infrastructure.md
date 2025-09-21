# Unit 5: Deployment Infrastructure

## Overview
Prepare production-ready deployment configurations for AWS with containerization, environment management, and automated deployment.

## User Stories
- **US-B5.1**: As a DevOps engineer, I want containerization so that deployment is consistent
- **US-B5.2**: As a developer, I want local development environment so that I can test easily
- **US-B5.3**: As a system admin, I want AWS deployment configs so that production deployment is automated
- **US-B5.4**: As a security admin, I want proper IAM roles so that access is controlled
- **US-B5.5**: As a developer, I want environment management so that secrets are secure

## Files to Create

### Docker Configuration
```
deployment/
├── Dockerfile                  # Multi-stage production build
├── docker-compose.yml          # Local development environment
├── docker-compose.prod.yml     # Production configuration
└── .dockerignore              # Docker build exclusions
```

### AWS Elastic Beanstalk
```
deployment/eb-config/
├── .ebextensions/
│   ├── 01-python.config       # Python environment setup
│   ├── 02-environment.config  # Environment variables
│   └── 03-https.config        # SSL/HTTPS configuration
└── .platform/
    └── hooks/
        └── postdeploy/
            └── 01-migrate.sh   # Post-deployment scripts
```

### AWS Lambda (Alternative)
```
deployment/lambda/
├── lambda_function.py          # Lambda handler
├── serverless.yml             # Serverless framework config
├── requirements.txt           # Lambda-specific dependencies
└── layers/                    # Lambda layers for dependencies
```

### Infrastructure as Code
```
deployment/terraform/           # Terraform configurations
├── main.tf                    # Main infrastructure
├── variables.tf               # Input variables
├── outputs.tf                 # Output values
└── modules/
    ├── s3/                    # S3 bucket configuration
    ├── dynamodb/              # DynamoDB table setup
    └── iam/                   # IAM roles and policies
```

### Environment Management
```
.env.example                   # Environment variables template
.gitignore                     # Git exclusions
README.md                      # Deployment instructions
```

## Implementation Tasks

### Task 5.1: Docker Containerization
**Acceptance Criteria:**
- Multi-stage Dockerfile for optimized production builds
- Local development environment with docker-compose
- Health checks and proper signal handling
- Minimal image size (<500MB)

**Dockerfile Features:**
- Python 3.11 slim base image
- Multi-stage build (build + runtime)
- Non-root user for security
- Health check endpoint
- Proper signal handling for graceful shutdown

### Task 5.2: Local Development Environment
**Acceptance Criteria:**
- Complete local stack with docker-compose
- Hot reloading for development
- Local AWS services simulation (LocalStack)
- Database seeding and migration scripts

**Services:**
- Flask application with hot reload
- LocalStack for AWS services simulation
- Redis for caching (optional)
- Nginx for reverse proxy (production)

### Task 5.3: AWS Elastic Beanstalk Configuration
**Acceptance Criteria:**
- Automated deployment with EB CLI
- Environment-specific configurations
- Auto-scaling and load balancing setup
- SSL/HTTPS configuration
- Health monitoring and alerts

**EB Extensions:**
- Python environment configuration
- Environment variables management
- HTTPS redirect and SSL setup
- CloudWatch logging configuration

### Task 5.4: AWS Lambda Deployment (Alternative)
**Acceptance Criteria:**
- Serverless framework configuration
- API Gateway integration
- Lambda layers for dependencies
- Environment-specific deployments

**Lambda Features:**
- Cold start optimization
- Memory and timeout configuration
- VPC configuration (if needed)
- Dead letter queue setup

### Task 5.5: Infrastructure as Code
**Acceptance Criteria:**
- Terraform configurations for all AWS resources
- Environment-specific variable files
- State management with S3 backend
- Resource tagging and cost allocation

**Resources:**
- S3 bucket with versioning and encryption
- DynamoDB table with backup configuration
- IAM roles with least privilege access
- CloudWatch log groups and alarms

### Task 5.6: Security and IAM Configuration
**Acceptance Criteria:**
- Least privilege IAM roles
- Secrets management with AWS Secrets Manager
- VPC configuration for network isolation
- Security group rules for minimal access

**Security Features:**
- Application-specific IAM roles
- Encrypted environment variables
- Network security groups
- Access logging and monitoring

## Configuration Files

### Dockerfile
```dockerfile
# Multi-stage build for production
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim as runtime
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY . .
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "app:app"]
```

### docker-compose.yml
```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - FLASK_ENV=development
      - AWS_ENDPOINT_URL=http://localstack:4566
    volumes:
      - .:/app
    depends_on:
      - localstack
  
  localstack:
    image: localstack/localstack
    ports:
      - "4566:4566"
    environment:
      - SERVICES=s3,dynamodb
      - DEBUG=1
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock"
```

### Elastic Beanstalk Configuration
```yaml
# .ebextensions/01-python.config
option_settings:
  aws:elasticbeanstalk:container:python:
    WSGIPath: app:app
  aws:elasticbeanstalk:application:environment:
    FLASK_ENV: production
    PYTHONPATH: /var/app/current
  aws:autoscaling:launchconfiguration:
    InstanceType: t3.small
    IamInstanceProfile: aws-elasticbeanstalk-ec2-role
```

## Environment Variables

### Production Environment
```bash
# AWS Configuration
AWS_REGION=ap-southeast-1
S3_BUCKET=echomind-pdf-storage-sg
DYNAMODB_TABLE=medical-documents

# Application Configuration
FLASK_ENV=production
SECRET_KEY=${SECRET_KEY}
MAX_FILE_SIZE=52428800
ALLOWED_EXTENSIONS=pdf

# AI Services
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
BEDROCK_REGION=us-east-1

# Security
ENABLE_RATE_LIMITING=true
MAX_REQUESTS_PER_MINUTE=100
CORS_ORIGINS=https://yourdomain.com

# Monitoring
LOG_LEVEL=INFO
ENABLE_METRICS=true
```

## Deployment Commands

### Docker Deployment
```bash
# Build and run locally
docker-compose up --build

# Production build
docker build -t medical-doc-api:latest .
docker run -p 8000:8000 medical-doc-api:latest
```

### Elastic Beanstalk Deployment
```bash
# Initialize EB application
eb init medical-document-api --region ap-southeast-1 --platform python-3.11

# Create environment
eb create production --instance-type t3.small --envvars SECRET_KEY=your-secret

# Deploy application
eb deploy

# Check status
eb status
eb logs
```

### Lambda Deployment
```bash
# Install Serverless Framework
npm install -g serverless

# Deploy to AWS
cd deployment/lambda
serverless deploy --stage production

# Check function logs
serverless logs -f api --stage production
```

### Terraform Deployment
```bash
# Initialize Terraform
cd deployment/terraform
terraform init

# Plan deployment
terraform plan -var-file="production.tfvars"

# Apply changes
terraform apply -var-file="production.tfvars"
```

## Monitoring and Logging

### CloudWatch Configuration
- Application logs with structured logging
- Performance metrics (response time, error rate)
- Custom metrics for business logic
- Alarms for critical issues

### Health Checks
- Application health endpoint
- Database connectivity check
- S3 access verification
- AI service availability

## Cost Optimization

### Resource Sizing
- **Elastic Beanstalk**: t3.small instances with auto-scaling
- **Lambda**: 512MB memory, 30-second timeout
- **DynamoDB**: On-demand billing for variable workloads
- **S3**: Intelligent tiering for cost optimization

### Monitoring
- AWS Cost Explorer integration
- Budget alerts for cost control
- Resource utilization monitoring
- Right-sizing recommendations

## Security Checklist
- [ ] IAM roles with minimal permissions
- [ ] Secrets stored in AWS Secrets Manager
- [ ] VPC configuration for network isolation
- [ ] Security groups with restrictive rules
- [ ] SSL/TLS encryption in transit
- [ ] Data encryption at rest
- [ ] Access logging enabled
- [ ] Regular security updates

## Dependencies
- Units 2-4 completion (Full backend functionality)
- AWS account with appropriate permissions
- Domain name and SSL certificate (optional)
- CI/CD pipeline setup (optional)

## Estimated Effort: 3-4 days

## Definition of Done
- [ ] Docker containerization complete
- [ ] Local development environment working
- [ ] AWS deployment configurations ready
- [ ] Infrastructure as Code implemented
- [ ] Security measures in place
- [ ] Monitoring and logging configured
- [ ] Deployment documentation complete
- [ ] Cost optimization implemented
- [ ] Production deployment successful