#!/usr/bin/env python3
"""AnyRouter daily sign-in - uses Playwright to bypass Cloudflare WAF."""
import json, os, sys

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    os.system("pip install playwright")
    os.system("playwright install chromium 2>/dev/null || true")
    from playwright.sync_api import sync_playwright

accounts_json = os.environ.get("ACCOUNTS_JSON") or sys.stdin.read().strip()
try:
    accounts = json.loads(accounts_json)
except json.JSONDecodeError:
    accounts = [accounts_json]

if not isinstance(accounts, list):
    accounts = [accounts]

results = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 720}
    )
    page = context.new_page()

    # Handle WAF challenge by visiting the site first
    page.goto("https://anyrouter.top", wait_until="networkidle", timeout=30000)

    for acct in accounts:
        session = acct.get("cookies", {}).get("session", "")
        api_user = acct.get("api_user", "")

        if not session:
            print(f"ERROR: no session cookie for account")
            continue

        print(f"--- Signing in user: {api_user} ---")
        page.set_extra_http_headers({
            "New-Api-User": str(api_user),
            "Accept": "application/json, text/plain, */*",
        })

        context.add_cookies([{
            "name": "session",
            "value": session,
            "domain": ".anyrouter.top",
            "path": "/"
        }])

        resp = page.evaluate("""
            async () => {
                try {
                    const r = await fetch('/api/user/sign_in', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Accept': 'application/json, text/plain, */*',
                        },
                        body: JSON.stringify({})
                    });
                    const text = await r.text();
                    return { status: r.status, body: text.substring(0, 500) };
                } catch (e) {
                    return { status: 0, body: e.message };
                }
            }
        """)

        result = {
            "user": api_user,
            "status": resp.get("status"),
            "body": resp.get("body", ""),
            "success": False,
        }

        try:
            body = json.loads(resp.get("body", "{}"))
            if body.get("success"):
                result["success"] = True
                print(f"  SIGN-IN SUCCESS: {body.get('message', '')}")
            elif "已签到" in resp.get("body", ""):
                result["success"] = True
                print(f"  Already signed in today")
            else:
                print(f"  Response: {resp.get('body', '')[:200]}")
        except json.JSONDecodeError:
            print(f"  Raw: {resp.get('body', '')[:200]}")

        results.append(result)

    browser.close()

print(f"\n{'='*40}")
print(f"Results: {sum(1 for r in results if r['success'])}/{len(results)} successful")

sys.exit(0 if all(r['success'] for r in results) else 1)
