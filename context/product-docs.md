# SyncFlow Product Documentation

**Product:** SyncFlow by NovaSync Technologies
**Version:** 3.4.1
**Last Updated:** March 2026

---

## Table of Contents

1. [Account Management](#1-account-management)
2. [Password & Security](#2-password--security)
3. [Billing & Subscriptions](#3-billing--subscriptions)
4. [API Usage](#4-api-usage)
5. [Integrations](#5-integrations)
6. [Workflows & Automations](#6-workflows--automations)
7. [Troubleshooting](#7-troubleshooting)
8. [Data & Privacy](#8-data--privacy)

---

## 1. Account Management

### Creating an Account

1. Visit `app.syncflow.io/signup`
2. Enter your work email and create a password (minimum 12 characters)
3. Verify your email address via the confirmation link (expires in 24 hours)
4. Complete your profile: name, company, role, timezone
5. Choose a plan or begin your 14-day free trial (no credit card required)

### Managing Team Members

**To invite a team member:**
- Settings → Team → Invite Members
- Enter email and select a role:
  - **Admin** – Full access including billing
  - **Member** – Access to assigned workspaces only
  - **Viewer** – Read-only access to shared dashboards
- Invites expire after 7 days

**To remove a team member:**
- Settings → Team → Find member → Remove
- Access is revoked immediately
- Their owned workflows are reassigned to the account Admin

**Seat Limits by Plan:**

| Plan       | Seats     |
|------------|-----------|
| Starter    | 5         |
| Growth     | 25        |
| Business   | 100       |
| Enterprise | Unlimited |

### Workspaces

Workspaces are isolated environments within your account. Use them to separate departments, projects, or clients.

- Starter: up to 3 workspaces
- Growth: up to 10 workspaces
- Business / Enterprise: Unlimited

To create: Dashboard → New Workspace → Name → Set permissions

### Transferring Account Ownership

Settings → Account → Transfer Ownership. Both parties confirm via email. This action is irreversible without contacting support.

---

## 2. Password & Security

### Resetting Your Password (Logged Out)

1. Go to `app.syncflow.io/login`
2. Click "Forgot Password"
3. Enter your email address
4. Check your inbox for the reset link (valid for 60 minutes)
5. Create a new password: minimum 12 characters, must include at least one uppercase letter, one number, and one symbol

**Note:** Password reset terminates all active sessions. You'll need to log in again on all devices.

### Changing Your Password (Logged In)

Settings → Security → Change Password → Enter current password → Enter new password → Save

### Two-Factor Authentication (2FA)

**To enable:**
1. Settings → Security → Two-Factor Authentication
2. Choose: Authenticator App (recommended) or SMS
3. Scan the QR code with your authenticator app
4. Enter the 6-digit confirmation code
5. Save your backup codes securely

**Supported apps:** Google Authenticator, Authy, 1Password, Microsoft Authenticator

**To disable:** Settings → Security → Two-Factor Authentication → Disable → Confirm with password

### Session Management

View and revoke active sessions at Settings → Security → Active Sessions.
Each session displays device type, approximate location, and last active time.

### Single Sign-On (SSO)

Available on Business and Enterprise plans.

**Supported providers:** Okta, Azure AD, Google Workspace, OneLogin

SSO requires Admin access and SAML 2.0 configuration. Contact your IT administrator. See the SSO Setup Guide for full instructions.

**Common SSO issues:**
- "SSO not configured" error → Check Settings → Security → SSO is enabled
- Email domain mismatch → Confirm your email matches the configured domain
- Redirect loop → Clear cookies and try incognito mode

---

## 3. Billing & Subscriptions

### Understanding Your Invoice

Invoices are generated on the 1st of each month and available at Settings → Billing → Invoice History.

Each invoice includes:
- Base plan charge
- Per-seat charges (if applicable)
- Automation overage fees (if monthly limit exceeded)
- Add-on charges (premium integrations, extra storage)

### Upgrading Your Plan

- Settings → Billing → Change Plan → Select new plan → Confirm
- Upgrade takes effect immediately
- You are charged a prorated amount for the remainder of the billing cycle

### Downgrading Your Plan

- Settings → Billing → Change Plan → Select lower plan → Confirm
- Downgrade takes effect at the start of the next billing cycle
- Current plan features remain active until then
- Ensure your usage falls within the lower plan's limits before downgrading

### Payment Methods

- Settings → Billing → Payment Methods
- Supported: Visa, Mastercard, American Express, PayPal, ACH bank transfer (US, Enterprise only)
- Primary method is charged automatically; backup method is charged if primary fails

### Refund Policy

| Plan Type | Refund Eligibility |
|-----------|-------------------|
| Annual    | Pro-rated refund within 30 days of renewal |
| Monthly   | No refund for current period; cancellation stops future charges |
| Free trial | No charge; cancel anytime |

For refund requests: `billing@novasynctechnologies.com`

**Note:** Refunds cannot be processed by the AI agent. Customers must be connected to the billing team.

### Cancelling Your Account

Settings → Billing → Cancel Subscription

Upon cancellation:
- Access continues until end of the paid period
- Data is retained for 90 days then permanently deleted
- Export your data before cancellation via Settings → Data → Export

---

## 4. API Usage

### Getting Your API Key

1. Settings → Developer → API Keys
2. Click "Generate New Key"
3. Name your key (e.g., "Production", "Staging")
4. Copy and store it securely — it is shown only once

**Security:** Never share your API key or commit it to version control. If compromised, revoke immediately and generate a new key.

### API Rate Limits

| Plan       | Requests/Minute | Requests/Day |
|------------|-----------------|--------------|
| Starter    | 60              | 10,000       |
| Growth     | 300             | 100,000      |
| Business   | 1,000           | 1,000,000    |
| Enterprise | Custom          | Custom       |

Rate limit headers included in every response:
```
X-RateLimit-Limit: 300
X-RateLimit-Remaining: 247
X-RateLimit-Reset: 1711234567
```

When the rate limit is exceeded, you receive a `429 Too Many Requests` response. Wait until the reset time shown in `X-RateLimit-Reset`.

### Common API Error Codes

| Code | Meaning                      | Resolution                               |
|------|------------------------------|------------------------------------------|
| 400  | Bad Request                  | Check request body format and fields     |
| 401  | Unauthorized                 | Invalid or expired API key — regenerate  |
| 403  | Forbidden                    | Check API key scope / permissions        |
| 404  | Not Found                    | Verify the resource ID                   |
| 429  | Rate Limited                 | Wait for reset or upgrade your plan      |
| 500  | Internal Server Error        | Contact support with request ID          |
| 503  | Service Unavailable          | Check status.syncflow.io                 |

### Webhooks

Webhooks deliver real-time event data to your endpoint.

**Setup:**
1. Settings → Developer → Webhooks → Add Endpoint
2. Enter your HTTPS endpoint URL
3. Select event types to subscribe to
4. Save — SyncFlow sends a test payload immediately

**Signature Verification:** Validate payloads using the `X-SyncFlow-Signature` header with your webhook secret.

**Retry Logic:** Failed webhooks are retried 5 times with exponential backoff: 1m, 5m, 30m, 2h, 12h.

---

## 5. Integrations

### Available Integrations (Selected)

| Category           | Apps                                               |
|--------------------|----------------------------------------------------|
| CRM                | Salesforce, HubSpot, Pipedrive                    |
| Communication      | Slack, Microsoft Teams, Gmail, Outlook             |
| Project Management | Jira, Asana, Monday.com, Trello, Linear            |
| Cloud Storage      | Google Drive, Dropbox, Box, OneDrive               |
| E-commerce         | Shopify, WooCommerce, BigCommerce                  |
| Data / Databases   | Google Sheets, Airtable, Notion, PostgreSQL        |
| Marketing          | Mailchimp, Klaviyo, ActiveCampaign                 |
| Payments           | Stripe, PayPal, Chargebee                          |
| Developer          | GitHub, GitLab, Bitbucket, PagerDuty              |

### Connecting an Integration

1. Dashboard → Integrations → Browse
2. Search for the app
3. Click Connect → Authorize via OAuth or enter API credentials
4. Configure settings (sync frequency, field mapping)
5. Test the connection before using in workflows

### Disconnecting an Integration

Integrations → Connected Apps → Select app → Disconnect

**Warning:** Disconnecting pauses all workflows using that integration. Re-connecting restores them.

### OAuth Token Expiry

Some integrations use OAuth tokens that expire periodically. When this happens:
- A "Reconnect Required" banner appears on the integration
- Affected workflows fail and generate error logs
- Re-authenticate by clicking "Reconnect" and re-authorizing with the external service

### Troubleshooting Failed Integrations

1. Check the integration error log: Integrations → [App] → Error Log
2. Verify your credentials for the external service are still valid
3. Check if the external service is experiencing an outage
4. Try disconnecting and reconnecting the integration
5. If the error persists after reconnection, contact support with the error log

---

## 6. Workflows & Automations

### Creating a Workflow

1. Dashboard → Workflows → New Workflow
2. Choose a trigger (webhook, schedule, app event, or manual)
3. Add actions — drag and drop from the action panel
4. Configure each action's settings and field mappings
5. Test with a sample payload
6. Activate

### Workflow Limits by Plan

| Plan       | Active Workflows | Runs/Month |
|------------|------------------|------------|
| Starter    | 10               | 500        |
| Growth     | 50               | 5,000      |
| Business   | Unlimited        | Unlimited  |
| Enterprise | Unlimited        | Unlimited  |

### Error Handling

Failed workflow runs appear in Workflows → [Workflow Name] → Run History → Failed.

You can:
- View the exact step and error message
- Manually retry failed runs
- Set up email/Slack notifications for failures in Workflow Settings → Notifications

### Workflow Templates

SyncFlow provides 50+ pre-built workflow templates for common use cases accessible at Dashboard → Templates. Templates are fully customizable after import.

---

## 7. Troubleshooting

### Login Issues

**"Invalid credentials" error:**
- Double-check the email address (case-sensitive)
- Try password reset if unsure of your password
- Check if your account has been deactivated by an Admin

**"Account locked" error:**
- Triggered after 10 consecutive failed login attempts
- Auto-unlocks after 30 minutes
- Contact support to unlock immediately

**SSO not working:**
- Confirm SSO is configured in Settings → Security
- Check your email domain matches the SSO configuration
- Ask your IT administrator to verify the SAML configuration

### Data Not Syncing

1. Check workflow run history for errors
2. Verify the integration connection is active (no "Reconnect Required" banner)
3. Confirm the trigger event actually fired in the source app
4. Review field mappings — source field names may have changed
5. Check your plan's automation run limit has not been reached

### Workflow Not Triggering

- Confirm the workflow status is Active (not Paused or Draft)
- Verify the trigger conditions are correctly configured
- Check if the source app's webhook is still registered and valid
- For scheduled triggers, confirm the timezone setting is correct

### Performance Issues (Slow / Unresponsive)

1. Check `status.syncflow.io` for known incidents
2. Clear browser cache and cookies; try a different browser
3. Try the SyncFlow mobile app (iOS / Android)
4. Report persistent issues with your Account ID and the approximate time of the issue

---

## 8. Data & Privacy

### Data Retention

- Active accounts: Data retained indefinitely while subscription is active
- Cancelled accounts: Data retained for 90 days, then permanently deleted
- Audit logs: 12 months (Enterprise: 5 years)

### Exporting Your Data

Settings → Data → Export Account Data

Exports include: workflows, run history, team configuration, integration configs, and custom fields. Processing time: up to 2 hours for large accounts.

### GDPR Compliance

NovaSync is fully GDPR compliant. For data subject access, deletion, or portability requests:

- Email: `privacy@novasynctechnologies.com`
- Response within 30 calendar days as required by regulation

### SOC 2 Type II

NovaSync holds SOC 2 Type II certification. The full report is available under NDA to Business and Enterprise customers. Request via your Customer Success Manager.

### Data Residency

Enterprise customers may choose data residency in US, EU, or APAC regions. Configure during onboarding or contact your Customer Success Manager to initiate a migration.
