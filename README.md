
# FinOps+ Agent

AI-assisted FinOps for MSPs/IT: analyze billing, benchmark waste, recommend cost actions, and log decisions.  
**Stack:** FastAPI on AWS Lambda (SAM), API Gateway (HTTP API), DynamoDB (action logs), S3 (uploads), Bedrock (Claude 3 Sonnet), Cognito (OIDC).  
**Frontend:** Vite + React, CloudFront + S3 (static site), OIDC login (react-oidc-context).

---

## ✨ Features

- **Upload & Analyze**: Parse CSV (S3/local), compute revenue/cost/profit, per-client license waste.
- **Benchmarks**: Compare against industry waste % (mock or API).
- **AI Insights**: Bedrock (Claude Sonnet) generates savings recommendations.
- **Actions**: One-click “Reduce waste 10%”, “Reprice low-margin”, etc. Stored as immutable **Action Logs**.
- **History**: Shows uploads, actions, and latest key.
- **Secure**: Cognito OIDC login; token → API Gateway auth; CORS locked to your CloudFront domain.


---

## 📁 Monorepo layout



finops-Agent/
├─ frontend/                      # Vite + React app
│  ├─ src/
│  │  ├─ utils/api.js            # API client (injects OIDC token)
│  │  └─ utils/authDebug.js      # OIDC token helpers
│  ├─ public/
│  │  └─ finops-logo.png
│  └─ .env.example
└─ sam-deploy/
└─ finops-backend/
├─ api/
│  ├─ app.py
│  ├─ lambda_handler.py
│  ├─ routers/
│  │  ├─ actions_routes.py
│  │  └─ history_routes.py
│  ├─ models.py, db.py, utils/
│  └─ requirements.txt
└─ template.yml            # SAM template (HTTP API + Lambda)



---

## 🔧 Prereqs

- Node.js 18+ (or 20+), PNPM/NPM/Yarn
- Python 3.12
- AWS CLI v2 + SAM CLI
- AWS account with permissions (CloudFront, S3, API Gateway, Lambda, Cognito, DynamoDB)
- (Optional) Elastic IP allowlist/Proxy, if corporate network restricts `github.com`

---

## 🔐 Cognito (OIDC)

1. Create **User Pool** and **App Client** (no secret).
2. App client callback URLs:  
   - `https://<your-cf-domain>/` (prod)  
   - `http://localhost:5173/` (dev)
3. Allowed logout URLs: same as above.
4. **Scopes**: `openid email profile`.
5. Note these for envs:
   - **REGION**: e.g. `us-east-2`
   - **USER_POOL_ID**: e.g. `us-east-2_XXXX`
   - **CLIENT_ID**: e.g. `aaaa...`
   - **COGNITO_DOMAIN** (Hosted UI domain, optional if using discovery via `authority`).

### Frontend `.env` (copy to `frontend/.env`)
```env
# API gateway base (no trailing slash)
VITE_API_BASE=https://<your-api-id>.execute-api.us-east-1.amazonaws.com

# Cognito OIDC (react-oidc-context via authority/metadata)
VITE_COGNITO_REGION=us-east-2
VITE_USER_POOL_ID=us-east-2_XXXX
VITE_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
VITE_REDIRECT_URI=https://<your-cf-domain>/
````

---

## 🚀 Backend Deploy (SAM)

From `sam-deploy/finops-backend`:

```powershell
# Build
sam build --profile <aws-profile> --region us-east-1

# Deploy (reuses an existing DynamoDB table "FinOpsActions")
sam deploy `
  --no-confirm-changeset `
  --parameter-overrides S3DataBucket=<your-data-bucket> ExistingActionsTableName=FinOpsActions `
  --capabilities CAPABILITY_IAM `
  --profile <aws-profile> `
  --region us-east-1
```

**Outputs** will show `ApiUrl` like:

```
https://<api-id>.execute-api.us-east-1.amazonaws.com/
```

### Environment (SAM `template.yml`)

* CORS already allows:

  * `https://<your CloudFront domain>`
  * `http://localhost:5173`
* Make sure your **DynamoDB** table `FinOpsActions` exists (PK: `id` as number, `time` as ISO is fine).
* If you don’t want DynamoDB: switch to the provided **SQLite-to-Dynamo adapter** or stub persistence.

---

## 🌐 Frontend Deploy (S3 + CloudFront)

```powershell
# Build Vite app
cd frontend
npm install
npm run build

# Create S3 bucket (us-east-1 special case – no LocationConstraint)
aws s3api create-bucket --bucket <your-frontend-bucket> --region us-east-1 --profile <aws-profile>

# Upload /dist
aws s3 sync dist/ s3://<your-frontend-bucket>/ --delete --profile <aws-profile>

# Create CloudFront distribution with OAC (recommended)
# (Use your working OAC/Distribution from earlier. Ensure bucket policy allows CF distribution ARN.)
# Then invalidate:
aws cloudfront create-invalidation `
  --distribution-id <DIST_ID> `
  --paths "/*" `
  --profile <aws-profile>
```

**Tip:** Your S3 bucket policy should allow only your CloudFront distribution via `AWS:SourceArn`.

---

## 🧪 Local Dev

**Backend (local)**
You can run the FastAPI app locally too (if you have a local variant):

```powershell
# example if you have a local FastAPI runner
uvicorn app:app --reload --port 8000
```

**Frontend (local)**

```powershell
cd frontend
npm install
npm run dev
# open http://localhost:5173
```

Set `VITE_API_BASE=http://localhost:8000` in `frontend/.env` for local API.

---

## 🔗 Key Endpoints

* `GET /health` → `{ status: "ok" }`
* `GET /analyze?source=auto|local`
* `GET /benchmarks?industry=msp`
* `GET /history` / `GET /history/recent`
* `POST /history/add` → `{ message, kind, key? }`
* `POST /actions/execute` → `{ action: { title, targets[], est_impact_usd? }, preview_only? }`

> All endpoints expect an **Authorization: Bearer <id_token>** from Cognito.

---

## ⚠️ Troubleshooting

* **CORS errors**: Confirm your **CloudFront domain** is listed in SAM `HttpApi.CorsConfiguration.AllowOrigins`, then `sam deploy` again.
* **401/403**: Check the browser has an OIDC `id_token` (react-oidc-context). Make sure your **audience** and **claims** are correct in API auth if you added authorizer.
* **500 on `/actions/execute`**: Ensure the database persistence is writable. In Lambda, prefer **DynamoDB** (the included `template.yml` uses `FinOpsActions`).
* **CloudFront 403 / XML AccessDenied**: S3 bucket policy must trust your distribution (`AWS:SourceArn` with `arn:aws:cloudfront::<acct>:distribution/<DIST_ID>`).
* **VITE_COGNITO_* missing**: Check `frontend/.env` is present **before** `npm run build`. Re-deploy after fixing.

---

## 🧾 Scripts

**Frontend**

```bash
npm run dev
npm run build
npm run preview
```

**Backend (SAM)**

```bash
sam build
sam deploy --guided
```

---

## 📜 License

MIT — use freely with attribution.

---

## 🙌 Credits

Built by Mrigank with AWS + Bedrock + React. If this helps your hackathon, star the repo ⭐!

```
`

