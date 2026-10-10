# Google Apps Script backend for SSE Community

This folder contains the source for the community backend. The main GitHub repository and the existing Python index-analysis pipeline remain in GitHub. No Supabase is required.

## What it supports
- Email + password registration and login
- New account starting balance: 3000 P coins
- Profile nickname updates
- One 100-P bull/bear vote per account and target date
- Balance and vote leaderboard
- Admin-only vote settlement and AI prediction syncing

Data is stored in a Google Spreadsheet. This is intended for an early-stage community; Google Sheets is not a high-scale transactional database.

## Set up (one-time)
1. Open https://script.google.com/ and create a new Apps Script project.
2. Copy the full contents of `Code.gs` from this folder into the editor's `Code.gs`.
3. Create a Google Spreadsheet for the database. Copy the ID from its URL (the long string between `/d/` and `/edit`).
4. In Apps Script, open **Project Settings → Script Properties** and add:
   - `SPREADSHEET_ID` = your spreadsheet ID
   - `ADMIN_KEY` = a long random secret (do not put this in GitHub or the website)
5. Run `doGet` once in the editor and approve the Google permission prompts. The script creates its data sheets automatically when first used.
6. Click **Deploy → New deployment → Web app**:
   - Execute as: **Me**
   - Who has access: **Anyone**
7. Copy the deployed web app URL ending in `/exec`. Do not paste the `ADMIN_KEY` into the frontend.

## Important before going live
- This file is source code only; it is not deployed to your Google account automatically.
- The current site frontend still needs its Supabase client calls replaced with the Apps Script API and the deployment URL configured. Do not consider the migration complete until this is done and tested.
- Cross-origin requests from GitHub Pages to Apps Script can behave differently depending on browser redirects and deployment settings. Test register/login/vote in the actual browser before announcing the site. If CORS prevents the frontend from reading responses, use a Google Apps Script-hosted HTML frontend or another approved same-origin bridge; do not work around it by sending passwords in URL query strings.
- Admin settlement requires calling the `settle` action with `adminKey`, `tradingDate`, and `outcome`. Keep the admin key private. Before production, connect settlement to verified SSE closing data rather than manually guessing the result.
- Passwords are salted and hashed, but Apps Script/Sheets is a lightweight starter setup, not a substitute for a professionally audited authentication service.
- Apps Script quotas apply. Monitor usage as the community grows.

## API request shape
Send JSON in a POST body, for example:
```json
{"action":"register","email":"you@example.com","password":"at-least-8-characters","nickname":"玩家"}
```
Supported actions: `register`, `login`, `me`, `profile`, `vote`, `leaderboard`, `logout`. Admin actions: `syncAi`, `settle`.

Successful response shape: `{"ok":true,"data":...}`.
Error response shape: `{"ok":false,"error":"..."}`.
