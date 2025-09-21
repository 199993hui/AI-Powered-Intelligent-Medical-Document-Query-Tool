# Unit 6: Testing & Monitoring

## Overview
Comprehensive testing suite, monitoring, logging, and performance optimization for production-ready system.

## User Stories
- **US-B6.1**: As a developer, I want comprehensive tests so that code quality is maintained
- **US-B6.2**: As a system admin, I want health checks so that system status is monitored
- **US-B6.3**: As a developer, I want logging so that issues can be debugged
- **US-B6.4**: As a system admin, I want performance monitoring so that bottlenecks are identified

## Files to Create

### Testing Framework
```
tests/
├── __init__.py
├── conftest.py                 # Pytest configuration and fixtures
├── test_upload.py             # Upload API tests
├── test_services.py           # Service layer tests
├── test_api.py                # API endpoint tests
├── test_integration.py        # Integration tests
├── test_performance.py        # Performance and load tests
└── fixtures/
    ├── sample_documents/      # Test PDF files
    └── mock_responses/        # Mock API responses
```

### Monitoring Configuration
```
monitoring/
├── cloudwatch_config.json     # CloudWatch metrics and alarms
├── alerts.yml                 # Alert configurations
├── dashboards/
│   ├── application.json       # Application performance dashboard
│   └── infrastructure.json    # Infrastructure monitoring dashboard
└── scripts/
    └── health_check.py        # Custom health check script
```

### Logging Configuration
```
logging/
├── logging_config.py          # Structured logging setup
├── formatters.py             # Custom log formatters
└── handlers.py               # Custom log handlers
```

## Implementation Tasks

### Task 6.1: Unit Testing Suite
**Acceptance Criteria:**
- >80% code coverage across all modules
- Fast test execution (<30 seconds total)
- Isolated tests with proper mocking
- Comprehensive edge case coverage

**Test Categories:**
- Service layer unit tests
- API endpoint tests
- Data model validation tests
- Utility function tests
- Error handling tests

### Task 6.2: Integration Testing
**Acceptance Criteria:**
- End-to-end API workflow tests
- Database integration tests
- S3 integration tests
- AI service integration tests (with mocking)
- Cross-service interaction tests

**Integration Scenarios:**
- Complete document upload and processing flow
- Search functionality with real data
- Bulk operations with multiple documents
- Error recovery and rollback scenarios

### Task 6.3: Performance Testing
**Acceptance Criteria:**
- Load testing for concurrent users
- Stress testing for system limits
- Performance benchmarking
- Memory and CPU profiling
- Database query optimization

**Performance Targets:**
- API response time: <500ms (95th percentile)
- Upload throughput: >10 files/minute
- Search response: <200ms
- Concurrent users: >100 simultaneous

### Task 6.4: Health Monitoring
**Acceptance Criteria:**
- Comprehensive health check endpoints
- Real-time system status monitoring
- Dependency health verification
- Automated alerting for failures
- Health dashboard with metrics

**Health Checks:**
- Application server status
- Database connectivity
- S3 bucket access
- AI service availability
- Memory and CPU usage

### Task 6.5: Logging and Observability
**Acceptance Criteria:**
- Structured logging with JSON format
- Centralized log aggregation
- Log level configuration
- Request tracing and correlation IDs
- Security event logging

**Logging Features:**
- Request/response logging
- Error tracking with stack traces
- Performance metrics logging
- Security audit logs
- Business event logging

### Task 6.6: Monitoring and Alerting
**Acceptance Criteria:**
- CloudWatch metrics and alarms
- Custom business metrics
- Performance monitoring dashboards
- Automated incident response
- SLA monitoring and reporting

**Monitoring Metrics:**
- Application performance (response time, throughput)
- Error rates and types
- Resource utilization (CPU, memory, disk)
- Business metrics (uploads, searches, users)
- Cost and usage metrics

## Testing Implementation

### Unit Test Structure
```python
# tests/test_services.py
import pytest
from unittest.mock import Mock, patch
from services.s3_service import S3Service

class TestS3Service:
    @pytest.fixture
    def s3_service(self):
        return S3Service()
    
    @patch('boto3.client')
    def test_upload_file_success(self, mock_boto3, s3_service):
        # Test successful file upload
        mock_s3 = Mock()
        mock_boto3.return_value = mock_s3
        
        result = s3_service.upload_file('test.pdf', b'content')
        
        assert result['success'] is True
        mock_s3.put_object.assert_called_once()
    
    def test_upload_file_invalid_type(self, s3_service):
        # Test file type validation
        with pytest.raises(ValueError):
            s3_service.upload_file('test.txt', b'content')
```

### Integration Test Example
```python
# tests/test_integration.py
import pytest
import requests
from tests.conftest import test_client

class TestDocumentWorkflow:
    def test_complete_document_lifecycle(self, test_client):
        # Upload document
        with open('tests/fixtures/sample.pdf', 'rb') as f:
            response = test_client.post('/api/documents/upload', 
                                      files={'file': f})
        assert response.status_code == 200
        doc_id = response.json()['document_id']
        
        # List documents
        response = test_client.get('/api/documents')
        assert response.status_code == 200
        assert len(response.json()['documents']) > 0
        
        # Search documents
        response = test_client.post('/api/search', 
                                   json={'query': 'test'})
        assert response.status_code == 200
        
        # Delete document
        response = test_client.delete(f'/api/documents/{doc_id}')
        assert response.status_code == 200
```

### Performance Test Example
```python
# tests/test_performance.py
import pytest
import time
import concurrent.futures
from tests.conftest import test_client

class TestPerformance:
    def test_concurrent_uploads(self, test_client):
        def upload_file():
            with open('tests/fixtures/sample.pdf', 'rb') as f:
                response = test_client.post('/api/documents/upload', 
                                          files={'file': f})
            return response.status_code == 200
        
        # Test 10 concurrent uploads
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(upload_file) for _ in range(10)]
            results = [f.result() for f in futures]
        
        assert all(results), "Some uploads failed under load"
    
    def test_search_performance(self, test_client):
        start_time = time.time()
        response = test_client.post('/api/search', 
                                   json={'query': 'medical'})
        end_time = time.time()
        
        assert response.status_code == 200
        assert (end_time - start_time) < 0.5, "Search took too long"
```

## Health Check Implementation

### Health Check Endpoint
```python
# app.py - Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0',
        'checks': {}
    }
    
    # Database connectivity
    try:
        db_service.health_check()
        health_status['checks']['database'] = 'healthy'
    except Exception as e:
        health_status['checks']['database'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'unhealthy'
    
    # S3 connectivity
    try:
        s3_service.health_check()
        health_status['checks']['s3'] = 'healthy'
    except Exception as e:
        health_status['checks']['s3'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'unhealthy'
    
    # AI service availability
    try:
        bedrock_service.health_check()
        health_status['checks']['ai_service'] = 'healthy'
    except Exception as e:
        health_status['checks']['ai_service'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'unhealthy'
    
    status_code = 200 if health_status['status'] == 'healthy' else 503
    return jsonify(health_status), status_code
```

## Logging Configuration

### Structured Logging Setup
```python
# logging/logging_config.py
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('app.log')
        ]
    )
    
    # Apply JSON formatter
    for handler in logging.root.handlers:
        handler.setFormatter(JSONFormatter())
```

## Monitoring Configuration

### CloudWatch Metrics
```json
{
  "metrics": [
    {
      "name": "DocumentUploads",
      "namespace": "MedicalDocAPI",
      "dimensions": [{"name": "Environment", "value": "production"}],
      "unit": "Count"
    },
    {
      "name": "SearchQueries",
      "namespace": "MedicalDocAPI", 
      "dimensions": [{"name": "Environment", "value": "production"}],
      "unit": "Count"
    },
    {
      "name": "ResponseTime",
      "namespace": "MedicalDocAPI",
      "dimensions": [{"name": "Endpoint", "value": "/api/documents"}],
      "unit": "Milliseconds"
    }
  ],
  "alarms": [
    {
      "name": "HighErrorRate",
      "metric": "ErrorRate",
      "threshold": 5,
      "comparison": "GreaterThanThreshold",
      "evaluation_periods": 2,
      "actions": ["arn:aws:sns:region:account:alert-topic"]
    }
  ]
}
```

## Performance Optimization

### Database Query Optimization
- Index optimization for common queries
- Query result caching with Redis
- Connection pooling configuration
- Batch operations for bulk updates

### API Response Optimization
- Response compression (gzip)
- Pagination for large datasets
- Async processing for heavy operations
- CDN integration for static assets

### Memory and CPU Optimization
- Memory profiling and leak detection
- CPU usage monitoring
- Garbage collection tuning
- Resource limit configuration

## Testing Commands

### Run Test Suite
```bash
# Run all tests
pytest tests/ -v --cov=. --cov-report=html

# Run specific test categories
pytest tests/test_services.py -v
pytest tests/test_integration.py -v
pytest tests/test_performance.py -v

# Run with coverage
pytest --cov=services --cov=models --cov-report=term-missing

# Run performance tests
pytest tests/test_performance.py -v --benchmark-only
```

### Load Testing
```bash
# Install load testing tools
pip install locust

# Run load tests
locust -f tests/load_test.py --host=http://localhost:8000
```

## Monitoring Dashboard

### Key Metrics to Track
- **Application Metrics**: Response time, throughput, error rate
- **Business Metrics**: Document uploads, searches, user activity
- **Infrastructure Metrics**: CPU, memory, disk usage
- **Cost Metrics**: AWS service costs, resource utilization

### Alert Thresholds
- Response time > 1 second (95th percentile)
- Error rate > 5%
- CPU usage > 80%
- Memory usage > 85%
- Disk usage > 90%

## Dependencies
- Units 2-5 completion (Full backend with deployment)
- Testing frameworks (pytest, locust)
- Monitoring tools (CloudWatch, custom dashboards)

## Estimated Effort: 2-3 days

## Definition of Done
- [ ] Comprehensive test suite with >80% coverage
- [ ] Integration tests for all major workflows
- [ ] Performance tests with benchmarks
- [ ] Health check endpoints implemented
- [ ] Structured logging configured
- [ ] Monitoring dashboards created
- [ ] Alerting rules configured
- [ ] Performance optimization completed
- [ ] Documentation for testing and monitoring
- [ ] CI/CD pipeline integration (optional)