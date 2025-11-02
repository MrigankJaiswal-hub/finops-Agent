

# 🧠 FinOps AI Agent
> Smart, Automated Financial Operations Insights powered by **AWS Bedrock + FastAPI**

---

## 🌟 About the Project

**FinOps AI Agent** is an intelligent cloud-native assistant that helps organizations **analyze, optimize, and automate financial operations (FinOps)**.

It combines the power of **AWS Bedrock**, **FastAPI**, and **React** to deliver real-time cost insights, AI-driven recommendations, and automated execution workflows — empowering IT, finance, and operations teams to make smarter, data-driven decisions with minimal manual effort.

Developed as part of advanced AI and cloud hackathons, the project demonstrates how **agentic AI** can transform traditional FinOps into an **autonomous decision-making system**.

---

## ⚙️ Key Features

| Category | Description |
|-----------|--------------|
| 🔍 **Analyze** | Ingest and parse cloud billing CSV data from S3 to identify cost anomalies and waste. |
| 💡 **Recommend** | Generate contextual AI-driven recommendations for optimization using Bedrock (Claude 3 Sonnet). |
| ⚙️ **Execute** | Trigger automation actions like instance right-sizing, budget alerts, and forecast updates. |
| 📈 **Track** | Monitor and visualize KPIs such as monthly trends, spend per service, and budget adherence. |
| 🔐 **Secure Auth** | Integrated AWS Cognito authentication with OIDC and JWT token verification. |
| ☁️ **Cloud-Native** | Fully serverless backend with API Gateway, Lambda, S3, and DynamoDB. |
| 📜 **History Log** | Persist historical FinOps insights and user-triggered actions in DynamoDB. |

---

## 🧩 Architecture Overview

```

[Frontend: React + OIDC]
|
↓
[API Gateway + Lambda (FastAPI via Mangum)]
|
↓
[Bedrock (Claude 3 Sonnet) + DynamoDB + S3]

````

---

## 🧠 Tech Stack

| Layer | Technologies |
|-------|---------------|
| **Frontend** | React (Vite) + TailwindCSS + react-oidc-context |
| **Backend** | FastAPI + Mangum + SQLAlchemy |
| **AI Integration** | AWS Bedrock (Anthropic Claude 3 Sonnet) |
| **Storage** | S3 (billing data) + DynamoDB (history & logs) |
| **Auth** | AWS Cognito OIDC |
| **Infra & CI/CD** | AWS SAM + GitHub Actions |
| **Deployment** | API Gateway + Lambda + CloudFront |

---

## 🚀 Getting Started

### 🧱 Prerequisites
- **Node.js** ≥ 18  
- **Python** ≥ 3.12  
- **AWS CLI** configured with SSO or IAM profile  
- **AWS SAM CLI** installed  

---

### 🔧 Setup Instructions

#### Clone the Repository
```bash
git clone https://github.com/MrigankJaiswal-hub/finops-Agent.git
cd finops-agent
````

#### Backend Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # (for Windows)
pip install -r requirements.txt
uvicorn app:app --reload
```

#### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Visit **[http://localhost:5173](http://localhost:5173)**

---

## ☁️ AWS Deployment via SAM

```bash
cd sam-deploy/finops-backend
sam build
sam deploy --guided \
  --profile 390503781686_AdministratorAccess \
  --region us-east-1 \
  --parameter-overrides \
    S3DataBucket=finops-demo-bucket3905 \
    ExistingActionsTableName=FinOpsActions
```

After deployment, note the **API URL** and **Lambda function name** displayed in the outputs.

---

## 🗂️ Repository Structure

```
finops-agent/
│
├── frontend/               # React + OIDC user interface
├── backend/                # FastAPI app + AI logic + S3 & DynamoDB utils
├── sam-deploy/             # AWS SAM templates for Lambda + API Gateway
├── .gitignore
├── README.md
└── requirements.txt
```

---

## 🧾 Release Notes

### 🔸 **v1.0.0 – Initial Public Release**

**Date:** November 2025
**Highlights:**

* Core FinOps analysis & AI insights pipeline
* Bedrock (Claude 3 Sonnet) integration
* DynamoDB historical tracking
* Secure Cognito authentication (OIDC)
* Full stack AWS-native deployment

---

### 🔹 **v1.1.0 – Upcoming**

**Planned Features:**

* Multi-tenant organization support
* Enhanced FinOps forecasting with RAG pipeline
* PDF-based executive summary generation
* Multi-region Bedrock agent orchestration
* Interactive FinOps dashboard & insights viewer

---

## 👩‍💻 Contributing

We welcome community contributions to make **FinOps AI Agent** even better!

1. Fork the repository
2. Create a new branch:

   ```bash
   git checkout -b feature/new-feature
   ```
3. Commit your changes:

   ```bash
   git commit -m "Add new feature"
   ```
4. Push and open a Pull Request

All contributions should follow:

* **PEP8** (Python backend)
* **ESLint + Prettier** (frontend)
* Include meaningful commit messages and documentation updates.

---

## 📧 Contact

**Author:** Mrigank Jaiswal


---

## 🛡️ License

**MIT License © 2025** — FinOps AI Agent
Built for the **SuperOps | AWS | Google Cloud | AI Hackathons**

---

````


