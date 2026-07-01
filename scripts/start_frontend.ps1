# Start frontend on port 4101
cd frontend
$env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:8000"
npm run dev -- -p 4101
