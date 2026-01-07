# App Center Setup Guide for SAVO iOS

This guide walks through setting up App Center integration in Codemagic to automatically distribute .ipa files after successful builds.

## Overview

The `ios_ipa` workflow in `codemagic.yaml` is now configured to:
1. ✅ Build signed iOS .ipa files
2. ✅ Upload to App Store Connect/TestFlight
3. ✅ Upload to App Center for broader distribution

## Prerequisites

- App Center account (https://appcenter.ms)
- Access to Codemagic Team settings
- iOS app already created in App Center

---

## Step 1: Create App in App Center (5 minutes)

### 1.1 Sign in to App Center
1. Go to https://appcenter.ms
2. Sign in with your account (Microsoft, GitHub, or email)

### 1.2 Create iOS App
1. Click **"Add new"** → **"Add new app"**
2. Fill in details:
   - **App name**: `SAVO-iOS` (must match `APP_CENTER_IOS_APP` in codemagic.yaml)
   - **Icon**: Upload SAVO logo (optional)
   - **OS**: iOS
   - **Platform**: Objective-C / Swift
   - **Release type**: Beta (for testing) or Production

3. Click **"Add new app"**

### 1.3 Note Your Organization/Owner Name
- After creating the app, the URL will be: `https://appcenter.ms/orgs/{owner}/apps/SAVO-iOS`
- **Copy the `{owner}` value** (e.g., `john-doe-org` or your username)
- This is your `APP_CENTER_OWNER` value

---

## Step 2: Generate App Center API Token (5 minutes)

### 2.1 Create API Token
1. In App Center, click your profile icon (top right)
2. Go to **Account Settings** → **API Tokens**
3. Click **"New API token"**

### 2.2 Configure Token
- **Description**: `Codemagic CI/CD Integration`
- **Access**: **Full Access** (required for uploading builds)
- Click **"Add new API token"**

### 2.3 Copy Token
- ⚠️ **CRITICAL**: Copy the token immediately (shown only once)
- Store it securely (you'll add it to Codemagic next)

**Example token format**: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0`

---

## Step 3: Add App Center Integration to Codemagic (5 minutes)

### 3.1 Go to Codemagic Integrations
1. Sign in to https://codemagic.io
2. Navigate to **Teams** (left sidebar)
3. Click your team name
4. Go to **Integrations** tab

### 3.2 Add App Center Integration
1. Scroll to **"App Center"** section
2. Click **"Connect"**
3. Fill in:
   - **Integration name**: `SAVO_AppCenter` (must match `app_center:` in codemagic.yaml)
   - **API Token**: Paste the token from Step 2.3
4. Click **"Save"**

### 3.3 Verify Integration
- You should see `SAVO_AppCenter` listed under App Center integrations
- Status should show as "Connected"

---

## Step 4: Update Codemagic Environment Variables (2 minutes)

### 4.1 Set App Center Variables
1. In Codemagic, go to your **SAVO app** → **Settings** → **Environment variables**
2. Add these variables:

| Variable Name | Value | Secure? |
|--------------|-------|---------|
| `APP_CENTER_OWNER` | Your organization/username from Step 1.3 | No |
| `APP_CENTER_IOS_APP` | `SAVO-iOS` (must match app name) | No |

3. Click **"Save changes"**

**Example values:**
```bash
APP_CENTER_OWNER=savo-team
APP_CENTER_IOS_APP=SAVO-iOS
```

---

## Step 5: Create Distribution Groups (Optional, 5 minutes)

By default, builds go to the **"Collaborators"** group. You can create custom groups:

### 5.1 Create Tester Group
1. In App Center, open your **SAVO-iOS** app
2. Go to **Distribute** → **Groups**
3. Click **"New group"**
4. Enter group name (e.g., `Internal-QA`, `Beta-Testers`)
5. Add tester email addresses
6. Click **"Create group"**

### 5.2 Update codemagic.yaml (if using custom group)
In `codemagic.yaml`, update the `distribution_group` field:

```yaml
publishing:
  app_center:
    auth: integration
    owner: $APP_CENTER_OWNER
    app_name: $APP_CENTER_IOS_APP
    notify_testers: true
    distribution_group: Internal-QA  # ← Change from "Collaborators"
```

---

## Step 6: Trigger Build and Verify (10 minutes)

### 6.1 Start Build
1. In Codemagic, go to **Builds** tab
2. Click **"Start new build"**
3. Select:
   - **Workflow**: `ios_ipa`
   - **Branch**: `main`
4. Click **"Start new build"**

### 6.2 Monitor Build Progress
The build will:
1. ✅ Fetch dependencies (`flutter pub get`)
2. ✅ Apply code signing
3. ✅ Build .ipa file
4. ✅ Verify IPA structure
5. ✅ Upload to App Store Connect
6. ✅ Upload to App Center ← **Look for this step**

### 6.3 Check App Center Upload
1. In Codemagic build logs, look for:
   ```
   Publishing to App Center...
   ✓ Successfully uploaded to App Center
   ```

2. In App Center dashboard:
   - Go to **Distribute** → **Releases**
   - You should see the new build listed
   - Status: **Available**
   - Testers will receive email notifications (if enabled)

---

## Troubleshooting

### Issue 1: "Integration 'SAVO_AppCenter' not found"
**Solution**: Ensure the integration name in Codemagic exactly matches `app_center: SAVO_AppCenter` in codemagic.yaml.

### Issue 2: "App not found in App Center"
**Solution**: Verify:
- `APP_CENTER_OWNER` matches your organization/username
- `APP_CENTER_IOS_APP` matches the app name in App Center
- App is created under the correct organization

### Issue 3: "401 Unauthorized"
**Solution**: 
- API token may have expired
- Regenerate token in App Center → Account Settings → API Tokens
- Update token in Codemagic integrations

### Issue 4: "Distribution group 'Collaborators' not found"
**Solution**: 
- Create the distribution group in App Center first
- Or change `distribution_group` in codemagic.yaml to an existing group

### Issue 5: Testers not receiving emails
**Solution**:
- Verify `notify_testers: true` in codemagic.yaml
- Check testers are added to the distribution group
- Testers should check spam folders

---

## App Center Features

### Automatic Updates
- When testers install the app from App Center, they'll get automatic update notifications
- No need to manually send new builds

### Crash Reporting
App Center includes free crash analytics:
1. Go to **Diagnostics** → **Crashes**
2. Install App Center SDK in Flutter (optional):
   ```bash
   flutter pub add appcenter_crashes
   ```

### Distribution Analytics
- Track install rates
- Monitor active devices
- See which versions are in use

### Device Testing (Optional)
- Test on real devices in the cloud
- Go to **Test** → **Device sets**

---

## Testing Distribution Flow

### 1. Add Yourself as Tester
1. In App Center, go to **Distribute** → **Groups** → **Collaborators**
2. Add your email address
3. Click **"Add users"**

### 2. Trigger Build in Codemagic
1. Push a commit to trigger the workflow
2. Wait for build to complete (~10-15 minutes)

### 3. Check Email
- You'll receive: **"A new release is available for SAVO-iOS"**
- Click **"Install"** in the email

### 4. Install on Device
1. Opens App Center in browser
2. Tap **"Install"** button
3. Follow iOS prompts to install
4. App appears on home screen

---

## Build Artifacts

After each successful build, you'll have:

### App Store Connect/TestFlight
- **Purpose**: Internal/external testing before production release
- **Access**: TestFlight app on iOS devices
- **Distribution**: Limited to 10,000 testers
- **Review**: External testing requires beta review

### App Center
- **Purpose**: Rapid distribution to stakeholders/QA
- **Access**: Web browser or App Center mobile app
- **Distribution**: Unlimited testers
- **Review**: No review required

---

## Best Practices

### 1. Version Bumping
Update `pubspec.yaml` before each build:
```yaml
version: 1.0.0+1  # 1.0.0 = version, +1 = build number
```

Increment the build number (+2, +3, etc.) for each new build.

### 2. Release Notes
The current setup auto-generates release notes from:
- Build number
- Git commit hash
- Branch name
- Custom feature highlights

Customize in `codemagic.yaml` → `publishing` → `app_center` → `release_notes`.

### 3. Multiple Environments
Create separate workflows for:
- `ios_ipa_dev` → App Center (development builds)
- `ios_ipa_prod` → App Store Connect (production builds)

### 4. Automated Builds
Enable **automatic builds** in Codemagic:
1. Go to **Settings** → **Build triggers**
2. Enable **"Trigger on push"**
3. Select branch: `main`
4. Select workflow: `ios_ipa`

Now every push to `main` auto-builds and distributes!

---

## Summary Checklist

- [ ] App Center account created
- [ ] SAVO-iOS app created in App Center
- [ ] API token generated and copied
- [ ] App Center integration added to Codemagic
- [ ] Environment variables set (`APP_CENTER_OWNER`, `APP_CENTER_IOS_APP`)
- [ ] Distribution group created (or using default "Collaborators")
- [ ] Test build triggered
- [ ] Build succeeded and uploaded to App Center
- [ ] Test installation on iOS device
- [ ] Testers added and notified

---

## Next Steps

1. **Test the workflow**:
   ```bash
   git add codemagic.yaml APP_CENTER_SETUP_GUIDE.md
   git commit -m "Add App Center publishing to ios_ipa workflow"
   git push
   ```

2. **Monitor first build**:
   - Watch Codemagic build logs
   - Verify App Center upload step succeeds

3. **Test on physical device**:
   - Check email for App Center notification
   - Install .ipa from App Center
   - Test continuous scanning feature

4. **Iterate**:
   - Adjust distribution groups
   - Customize release notes
   - Enable automatic builds

---

## Support Resources

- **App Center Docs**: https://docs.microsoft.com/en-us/appcenter
- **Codemagic App Center Integration**: https://docs.codemagic.io/yaml-publishing/app-center
- **SAVO Continuous Scanning Guide**: See `CONTINUOUS_SCANNING_COMPLETE.md`

---

**Last Updated**: January 2026  
**Author**: GitHub Copilot (Claude Sonnet 4.5)  
**Status**: Ready for implementation
