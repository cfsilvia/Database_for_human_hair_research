# Database_for_human_hair_research

Run `start_server.bat` (or `restart_server.bat` for a running server), then open
http://132.77.72.102:8000.

Login protects the homepage, static HTML pages, API endpoints, and API docs.
Set `LOGIN_USERNAME` and `LOGIN_PASSWORD_HASH` in `.env`. Generate a password hash
without displaying the password using:

```powershell
python -c "from getpass import getpass; from app.auth import hash_password; print(hash_password(getpass('Password: ')))"
```

Sessions expire after eight hours, on logout, or when the server restarts. Run a
single Uvicorn worker because sessions are stored in memory. HTTP does not encrypt
passwords or session cookies.
