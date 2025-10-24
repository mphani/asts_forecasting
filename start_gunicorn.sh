#!/bin/bash
# Start MetricForecastorAPI server using Gunicorn

echo "🚀 Starting MetricForecastorAPI server with Gunicorn..."
echo "📦 Using tsenv virtual environment"

# Activate tsenv environment
source ~/pscripts/activate_py_tsenv.sh

# Check if we're in the right directory
if [ ! -f "configs/config.yaml" ]; then
    echo "❌ Error: configs/config.yaml not found. Please run from project root."
    exit 1
fi

# Check if wsgi.py exists
if [ ! -f "wsgi.py" ]; then
    echo "❌ Error: wsgi.py not found. Please ensure WSGI file exists."
    exit 1
fi

# Start the server with Gunicorn
echo "🌐 Starting Gunicorn server on port 6060..."
echo "📋 Available endpoints:"
echo "   - http://localhost:6060/health"
echo "   - http://localhost:6060/api/v1/query?query=up"
echo "   - http://localhost:6060/api/v1/query_range"
echo "   - http://localhost:6060/api/v1/label/job/values"
echo "   - http://localhost:6060/api/v1/series"
echo "   - http://localhost:6060/api/v1/labels"
echo "   - http://localhost:6060/api/v1/metadata"
echo ""
echo "🔄 Server is running... Press Ctrl+C to stop"

# Run with Gunicorn
gunicorn --config gunicorn.conf.py wsgi:application
