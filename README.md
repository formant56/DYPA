# DYPA Playwright Starter

This project opens a site in Chromium, checks whether the user is already logged in, and logs in only when needed.

## Files to update

- `main.py`: replace the `CONFIG` values with the real URLs and selectors for your site.
- `.env`: create this from `.env.example` and add the real credentials.

## Setup

```powershell
cd C:\Users\Alex\Documents\Playground\DYPA
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
```

## Run

```powershell
python .\main.py
```

## Typical selector updates

- `logged_in_selector`: something visible only after login, such as `text="Logout"` or `[data-testid="user-menu"]`
- `username_selector`: the email or username input
- `password_selector`: the password input
- `submit_selector`: the login button
- `login_link_selector`: optional, only if you must click a sign-in link before reaching the form
