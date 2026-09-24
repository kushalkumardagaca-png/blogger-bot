# STEP-BY-STEP SETUP GUIDE: AUTONOMOUS BLOGGER PUBLISHING BOT
### For "Finance by CA Kushal" (Blog ID: 8911514070006792465)

This guide is designed for a helper, family member, or friend with a computer. It takes **under 7 minutes total**, requires **zero coding knowledge**, and only needs to be performed **once**. After these steps, the system runs 100% autonomously in the cloud 5 times every day for the entire 6 months.

---

## OVERVIEW OF WHAT WE ARE DOING
1. **Part 1 (3 minutes):** Tell Google Cloud that our bot is allowed to post to Blogger and get 3 authorization keys.
2. **Part 2 (2 minutes):** Put the bot code onto a free, private GitHub repository.
3. **Part 3 (2 minutes):** Paste the 3 keys into GitHub Secrets and click "Run".

---

## PART 1: GET GOOGLE BLOGGER API KEYS (In Your Web Browser)

### Step 1.1: Log into Google Cloud Console
1. Open your web browser and go to: **[https://console.cloud.google.com/](https://console.cloud.google.com/)**
2. Make sure you are signed in with the Google Account that owns the blog (**`kushalkumardaga.ca@gmail.com`**).
3. At the top left, click the project dropdown (next to "Google Cloud") and click **"NEW PROJECT"**.
   - Project Name: `Blogger Cloud Bot`
   - Click **CREATE**.
   - Wait 5 seconds, then make sure `Blogger Cloud Bot` is selected in the top dropdown.

### Step 1.2: Enable Blogger API v3
1. In the top search bar, type: **`Blogger API v3`** and press Enter.
2. Click on **Blogger API v3** from the results.
3. Click the blue **ENABLE** button.

### Step 1.3: Configure the Consent Screen
1. On the left navigation menu, click **APIs & Services** > **OAuth consent screen**.
2. Select **External**, then click **CREATE**.
3. Fill in these 3 required fields (leave the rest blank):
   - **App name:** `Finance Bot`
   - **User support email:** (select Kushal's email from the dropdown)
   - **Developer contact information:** (type Kushal's email)
4. Click **SAVE AND CONTINUE**.
5. On the **Scopes** page, click **SAVE AND CONTINUE** (default is fine).
6. On the **Test users** page (*Crucial Step!*):
   - Click **+ ADD USERS**.
   - Enter Kushal's email: `kushalkumardaga.ca@gmail.com`.
   - Click **ADD**.
   - Click **SAVE AND CONTINUE**.
7. Click **BACK TO DASHBOARD**.

### Step 1.4: Create OAuth Credentials
1. On the left menu, click **Credentials**.
2. At the top, click **+ CREATE CREDENTIALS** > **OAuth client ID**.
3. Under **Application type**, choose: **Web application**.
4. Name: `Blogger Web Client`.
5. Under **Authorized redirect URIs**, click **+ ADD URI** and paste this exact address:
   ```
   https://developers.google.com/oauthplayground
   ```
6. Click the blue **CREATE** button.
7. A pop-up box will appear showing:
   - **Client ID** (looks like: `xxxxxx.apps.googleusercontent.com`)
   - **Client Secret** (looks like: `GOCSPX-xxxxxx`)
8. Copy and paste both into a temporary notepad.

### Step 1.5: Get the Refresh Token (Takes 60 seconds)
1. In a new browser tab, go to: **[https://developers.google.com/oauthplayground](https://developers.google.com/oauthplayground)**
2. In the top-right corner, click the **⚙️ (Gear Icon / Settings)**.
3. Check the box: **`[x] Use your own OAuth credentials`**.
4. Paste the **OAuth Client ID** and **OAuth Client Secret** you copied in Step 1.4.
5. Close the gear settings panel (click the gear icon again).
6. On the left column, scroll down and click **Blogger API v3**, then check the box:
   `https://www.googleapis.com/auth/blogger`
7. Click the blue button: **Authorize APIs**.
8. A Google sign-in window will open. Choose Kushal's Google Account.
   - If Google shows *"Google hasn't verified this app"*, click **Advanced** (at the bottom) and click **"Go to Finance Bot (unsafe)"**.
   - Click **Continue** / **Allow** to grant permission.
9. You will be redirected back to OAuth Playground at **Step 2 (Exchange authorization code for tokens)**.
10. Click the blue button: **Exchange authorization code for tokens**.
11. Look at the box on the right. You will see:
    ```
    Refresh token: 1//0xxxxxxxxxxxxxxxxxxxxxxxxxxxx
    ```
12. Copy that entire **Refresh token** value!

**You now have all 3 keys:**
- `BLOGGER_CLIENT_ID`
- `BLOGGER_CLIENT_SECRET`
- `BLOGGER_REFRESH_TOKEN`

---

## PART 2: CREATE THE PRIVATE GITHUB REPOSITORY (2 Minutes)

1. Open **[https://github.com](https://github.com)** (sign in or create a free account).
2. Click the **+** icon in the top right > **New repository**.
3. Name it: **`blogger-auto-bot`**.
4. Choose **Private** (so your keys and code stay private).
5. Check **Add a README file**.
6. Click **Create repository**.
7. In the new repository, click **Add file** > **Upload files**.
8. Upload the files from the provided `blogger_cloud_bot.zip`:
   - `.github/workflows/daily_blogger_poster.yml`
   - `auto_blogger_publisher.py`
   - `published_tracker.json`
   - `500_topics_evenly_mixed.csv`
9. Click **Commit changes**.

---

## PART 3: ADD THE KEYS TO GITHUB SECRETS (2 Minutes)

1. In your GitHub repository, click on the **Settings** tab at the top.
2. In the left sidebar, click **Secrets and variables** > **Actions**.
3. Click the green button: **New repository secret**.
4. Add these 4 secrets one by one:

| Secret Name | Secret Value |
| :--- | :--- |
| `BLOGGER_BLOG_ID` | `8911514070006792465` |
| `BLOGGER_CLIENT_ID` | *(Paste Client ID from Part 1)* |
| `BLOGGER_CLIENT_SECRET` | *(Paste Client Secret from Part 1)* |
| `BLOGGER_REFRESH_TOKEN` | *(Paste Refresh Token from Part 1)* |

---

## PART 4: TEST RUN & VERIFICATION (30 Seconds)

1. In the GitHub repository, click on the **Actions** tab at the top.
2. In the left column, click **Autonomous Blogger Daily Publishing Engine (5x Daily)**.
3. On the right side, click **Run workflow** > green **Run workflow** button.
4. Refresh after 20-30 seconds. A green checkmark (`✔`) will appear.
5. Open **[https://dailyyield.blogspot.com/](https://dailyyield.blogspot.com/)**.
6. You will see Topic #11 published live, complete with all SEO tags, schema, styling, and categories!

---

## FROM THIS MOMENT FORWARD:
The bot runs **completely autonomously 5 times every day** at:
- **08:00 AM IST**
- **11:30 AM IST**
- **02:30 PM IST**
- **05:45 PM IST**
- **08:30 PM IST**

You never need to touch Blogger, write, format, or upload another post for the entire 6 months of bedrest.
