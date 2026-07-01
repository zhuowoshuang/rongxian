# Start backend on port 8000
cd backend
$env:PYTHONPATH = "."
$env:MOCK_DATA = "true"
uvicorn app.main:app --host 127.0.0.1 --port 8000
