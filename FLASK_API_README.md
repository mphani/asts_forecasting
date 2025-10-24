# MetricForecastorAPI

This Flask API server provides forecasting endpoints following Prometheus HTTP API standards. It can be used as a datasource in Grafana for time series forecasting and metric analysis.

## 🚀 Quick Start

### Prerequisites

This project uses the `tsenv` virtual environment. Make sure you have the activation script:
```bash
~/pscripts/activate_py_tsenv.sh
```

#### Virtual Environment Setup

The project is configured to use your `tsenv` virtual environment:
- **Python Version**: 3.10.18
- **Environment Path**: `/Users/phaniram/tsenv/`
- **Activation Script**: `~/pscripts/activate_py_tsenv.sh`

All Python commands should be run with the `tsenv` environment activated.

### Start the Server

#### Production Server (Gunicorn) - Recommended
```bash
# Using Gunicorn with configuration file
./start_gunicorn.sh

# Manual Gunicorn command
source ~/pscripts/activate_py_tsenv.sh
gunicorn --bind 0.0.0.0:5050 --workers 4 --timeout 30 wsgi:application
```

### Test the Server

```bash
# Test API endpoints (make sure server is running first)
python test_api.py

# Or run directly
./test_api.py
```

## 📡 Available Endpoints

The server runs on `http://localhost:5050` by default and provides the following Prometheus HTTP API standard endpoints:

### 1. Root Endpoint
- **URL**: `/`
- **Method**: `GET`
- **Description**: Welcome message and API information
- **Response**: Server information and available endpoints

### 2. Health Check
- **URL**: `/health`
- **Method**: `GET`
- **Description**: Health check endpoint
- **Response**: `{"status": "healthy", "timestamp": "2025-01-14T..."}`

### 2. Instant Query
- **URL**: `/api/v1/query`
- **Method**: `GET`
- **Parameters**:
  - `query`: PromQL query string (e.g., `up`, `aerospike_namespace_master_objects`)
  - `time`: Unix timestamp (optional, defaults to current time)
- **Example**: `/api/v1/query?query=up&time=1640995200`

### 3. Range Query
- **URL**: `/api/v1/query_range`
- **Method**: `GET`
- **Parameters**:
  - `query`: PromQL query string
  - `start`: Start time (Unix timestamp)
  - `end`: End time (Unix timestamp)
  - `step`: Step size in seconds
- **Example**: `/api/v1/query_range?query=up&start=1640995200&end=1640998800&step=60`

### 4. Label Values
- **URL**: `/api/v1/label/{label_name}/values`
- **Method**: `GET`
- **Description**: Get all values for a specific label
- **Examples**:
  - `/api/v1/label/job/values`
  - `/api/v1/label/cluster_name/values`
  - `/api/v1/label/namespace/values`

### 5. Series Discovery
- **URL**: `/api/v1/series`
- **Method**: `GET`
- **Parameters**:
  - `match[]`: Series selector (optional)
  - `start`: Start time (optional)
  - `end`: End time (optional)
- **Example**: `/api/v1/series?match[]=aerospike_namespace_master_objects`

### 6. Labels Discovery
- **URL**: `/api/v1/labels`
- **Method**: `GET`
- **Description**: Get all available label names
- **Response**: List of all label names from configured metrics

### 7. Metadata
- **URL**: `/api/v1/metadata`
- **Method**: `GET`
- **Description**: Get metadata for all configured metrics
- **Response**: Metric metadata including type, help text, and unit

## 🔧 Configuration

The server configuration is managed through `configs/config.yaml`:

```yaml
# Server configuration
host: 0.0.0.0
port: 5050
debug: false

# Metrics configuration
metrics:
  aerospike_namespace_master_objects:
    description: "Aerospike namespace client read throughput"
    metric_labels:
      cluster_name: as80_cluster_1
      job: aerospike
      namespace: test
    # ... other metric configuration
```

## 📊 Supported Queries

### Built-in Queries

1. **`up`**: Returns server health status
   - Instant: Returns current status
   - Range: Returns status over time range

2. **`aerospike_namespace_master_objects`**: Returns actual metric data
   - Instant: Returns latest value
   - Range: Returns time series data

### Custom Queries

You can extend the server to support additional queries by modifying the query handlers in `src/api/flask_server.py`.

## 🎯 Grafana Integration

### Adding as Prometheus Datasource

1. In Grafana, go to **Configuration** → **Data Sources**
2. Click **Add data source**
3. Select **Prometheus**
4. Configure:
   - **URL**: `http://localhost:5050`
   - **Access**: Server (default)
   - **HTTP Method**: GET
5. Click **Save & Test**

### Example Queries for Grafana

```promql
# Health check
up

# Metric data
aerospike_namespace_master_objects

# With labels
aerospike_namespace_master_objects{cluster_name="as80_cluster_1"}

# Rate calculation
rate(aerospike_namespace_master_objects[5m])
```

## 🏗️ Architecture

The MetricForecastorAPI server consists of:

- **`MetricForecastorAPI`**: Main Flask application class
- **Route Handlers**: Individual handlers for each endpoint
- **Query Processors**: Logic for processing different query types
- **Data Integration**: Integration with `DataManager` and `ModelManager`

## 🔍 Response Format

All endpoints return JSON responses following Prometheus HTTP API standards:

### Instant Query Response
```json
{
  "status": "success",
  "data": {
    "resultType": "vector",
    "result": [
      {
        "metric": {
          "__name__": "up",
          "job": "aerospike",
          "instance": "localhost:7090"
        },
        "value": [1640995200, "1"]
      }
    ]
  }
}
```

### Range Query Response
```json
{
  "status": "success",
  "data": {
    "resultType": "matrix",
    "result": [
      {
        "metric": {
          "__name__": "up",
          "job": "aerospike",
          "instance": "localhost:7090"
        },
        "values": [
          [1640995200, "1"],
          [1640995260, "1"],
          [1640995320, "1"]
        ]
      }
    ]
  }
}
```

## 🛠️ Development

### Adding New Endpoints

1. Add route handler in `_register_routes()`
2. Implement handler method
3. Update this documentation

### Adding New Query Types

1. Modify `_handle_query()` or `_handle_query_range()`
2. Add query-specific logic
3. Test with Grafana

### Error Handling

All endpoints include comprehensive error handling:
- Invalid parameters
- Missing data
- Server errors
- Timeout handling

## 📝 Logging

The server uses the application's logging system:
- **INFO**: Normal operations
- **ERROR**: Error conditions
- **DEBUG**: Detailed debugging information

## 🔒 Security

- CORS enabled for Grafana integration
- Input validation on all parameters
- Error messages don't expose internal details

## 🚀 Production Deployment

### Gunicorn Configuration

The project includes a complete Gunicorn setup:

#### Files Created:
- **`wsgi.py`**: WSGI application entry point
- **`gunicorn.conf.py`**: Gunicorn configuration file
- **`start_gunicorn.sh`**: Production startup script
- **`test_api.py`**: API endpoint testing script

#### Configuration Options:
- **Workers**: 4 worker processes
- **Timeout**: 30 seconds
- **Bind**: 0.0.0.0:5050
- **Logging**: Console output
- **Process Management**: Auto-restart workers

#### Production Considerations:

1. **WSGI Server**: ✅ Gunicorn configured
2. **Reverse Proxy**: Use Nginx for load balancing
3. **SSL/TLS**: Enable HTTPS for secure connections
4. **Authentication**: Add authentication if needed
5. **Monitoring**: Add health checks and metrics
6. **Process Management**: Use systemd or supervisor

### Example Production Commands

```bash
# Start with full configuration
./start_gunicorn.sh

# Manual Gunicorn command
gunicorn --config gunicorn.conf.py wsgi:application
```

## 📚 Examples

### cURL Examples

```bash
# Health check
curl http://localhost:5050/health

# Instant query
curl "http://localhost:5050/api/v1/query?query=up"

# Range query
curl "http://localhost:5050/api/v1/query_range?query=up&start=1640995200&end=1640998800&step=60"

# Label values
curl http://localhost:5050/api/v1/label/job/values

# Series discovery
curl http://localhost:5050/api/v1/series

# Labels discovery
curl http://localhost:5050/api/v1/labels

# Metadata
curl http://localhost:5050/api/v1/metadata
```

### Python Client Example

```python
import requests

# Health check
response = requests.get("http://localhost:5050/health")
print(response.json())

# Query data
response = requests.get("http://localhost:5050/api/v1/query?query=up")
data = response.json()
print(f"Status: {data['status']}")
print(f"Results: {len(data['data']['result'])}")
```

## 🐛 Troubleshooting

### Common Issues

1. **Port Already in Use**: Change port in config or kill existing process
2. **Import Errors**: Ensure all dependencies are installed
3. **Configuration Errors**: Check `configs/config.yaml` syntax
4. **Data Not Available**: Verify metric configuration and data availability

### Debug Mode

Enable debug mode in `configs/config.yaml`:
```yaml
debug: true
```

This provides more detailed error messages and auto-reload on code changes.

## 📈 Performance

- **Concurrent Requests**: Handles multiple concurrent requests
- **Caching**: Consider adding Redis caching for frequently accessed data
- **Connection Pooling**: Uses connection pooling for database operations
- **Async Support**: Can be extended with async/await for better performance
