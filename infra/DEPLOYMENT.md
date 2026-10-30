# Vaidya AI — AWS Deployment Guide (EC2 + Elastic IP)

Simplified POC deployment with a stable backend IP. No ALB needed.

---

## Architecture

```
User Browser
     │
     ▼
CloudFront (HTTPS) ──► S3 Bucket (Frontend static files)
     │
     │ API calls (/api/v1/*)
     ▼
EC2 Instance (t3.micro) + Elastic IP ──► Docker Container (port 8000)
     │
     ▼
AWS Bedrock (Claude Haiku 4.5)
```

**Estimated monthly cost:** ~$8-15/month
- EC2 t3.micro: ~$8/mo (or free tier if eligible)
- Elastic IP (attached): Free (only charged if NOT attached)
- S3 + CloudFront: ~$1-2
- ECR: ~$0.50
- Bedrock: Pay per token

---

## Prerequisites

1. **AWS CLI** installed and configured
   ```powershell
   aws configure
   # Access Key, Secret Key, Region: ap-south-1, Output: json
   ```

2. **Docker Desktop** installed and running

3. **Node.js** (v18+) and npm installed

4. **AWS Bedrock model access** enabled
   - AWS Console → Bedrock → Model access → Enable `Anthropic Claude Haiku 4.5` in `ap-south-1`

5. **(Optional) EC2 Key Pair** for SSH access
   - AWS Console → EC2 → Key Pairs → Create key pair
   - Save the `.pem` file securely

---

## Quick Deploy (First Time)

```powershell
cd infra
.\deploy.ps1 -KeyPairName "your-key-pair-name"
```

Without SSH key (you can still use AWS SSM to access the instance):
```powershell
cd infra
.\deploy.ps1
```

First deploy takes ~5-8 minutes. The script will:
1. Create the CloudFormation stack (VPC, EC2, Elastic IP, ECR, S3, CloudFront)
2. Build the backend Docker image and push to ECR
3. Deploy the container on EC2 via AWS SSM
4. Build the frontend with the stable backend URL
5. Upload frontend to S3 and invalidate CloudFront

---

## Elastic IP — How It Works

The Elastic IP is **automatically created and attached** to the EC2 instance by CloudFormation. You don't need to do anything manually.

- The IP is allocated when the stack is created
- It's associated with the EC2 instance automatically
- It **never changes** — even if you stop/start the instance
- The backend URL will always be `http://<ELASTIC_IP>:8000`
- The frontend is built with this stable URL baked in

If you delete the stack, the Elastic IP is released. If you need to keep the IP across stack recreations, allocate it manually in the console first and import it.

---

## Deploy Script Options

```powershell
.\deploy.ps1                              # Full deploy (stack + backend + frontend)
.\deploy.ps1 -SkipStack                   # Skip CloudFormation, deploy code only
.\deploy.ps1 -BackendOnly                 # Backend only
.\deploy.ps1 -FrontendOnly               # Frontend only
.\deploy.ps1 -KeyPairName "my-key"       # Specify SSH key pair
```

---

## CI/CD with GitHub Actions

After the initial deployment, CI/CD handles subsequent deployments automatically.

### Setup (One Time)

1. Push your code to GitHub

2. Add these **GitHub Secrets** (Settings → Secrets and variables → Actions):

   | Secret | Value | Where to find it |
   |--------|-------|------------------|
   | `AWS_ACCESS_KEY_ID` | IAM user access key | AWS Console → IAM |
   | `AWS_SECRET_ACCESS_KEY` | IAM user secret key | AWS Console → IAM |
   | `EC2_HOST` | Elastic IP address | Stack output `BackendIP` |
   | `EC2_SSH_KEY` | Full content of your `.pem` file | The key pair you downloaded |
   | `BACKEND_URL` | `http://<ELASTIC_IP>:8000` | Stack output `BackendURL` |
   | `S3_BUCKET` | Frontend S3 bucket name | Stack output `FrontendBucketName` |
   | `CLOUDFRONT_DISTRIBUTION_ID` | CloudFront dist ID | Stack output `CloudFrontDistributionId` |

3. Get stack outputs:
   ```powershell
   aws cloudformation describe-stacks --stack-name vaidya-ai --region ap-south-1 --query "Stacks[0].Outputs" --output table
   ```

### How CI/CD Works

```
Push to main (backend/ files changed)
     │
     ▼
GitHub Actions: deploy-backend.yml
     ├── Build Docker image
     ├── Push to ECR
     └── SSH into EC2 → pull image → restart container

Push to main (frontend/ files changed)
     │
     ▼
GitHub Actions: deploy-frontend.yml
     ├── npm install + build (with VITE_API_BASE)
     ├── Upload to S3
     └── Invalidate CloudFront cache
```

- **Backend deploys** trigger when files in `backend/` change
- **Frontend deploys** trigger when files in `frontend/` change
- Both can also be triggered manually via GitHub Actions → "Run workflow"

---

## Manual Deployment Steps

### 1. Deploy CloudFormation Stack

```powershell
aws cloudformation deploy `
    --template-file infra\cloudformation.yaml `
    --stack-name vaidya-ai `
    --parameter-overrides AppName=vaidya-ai AwsRegion=ap-south-1 KeyPairName=your-key `
    --capabilities CAPABILITY_NAMED_IAM `
    --region ap-south-1
```

### 2. Build and Push Backend Image

```powershell
$ECR_URI = aws cloudformation describe-stacks --stack-name vaidya-ai `
    --query "Stacks[0].Outputs[?OutputKey=='ECRRepositoryUri'].OutputValue" `
    --output text --region ap-south-1

aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin ($ECR_URI.Split('/')[0])

cd backend
docker build -t "${ECR_URI}:latest" .
docker push "${ECR_URI}:latest"
```

### 3. Deploy on EC2

SSH into the instance and run the deploy script:
```powershell
$IP = aws cloudformation describe-stacks --stack-name vaidya-ai `
    --query "Stacks[0].Outputs[?OutputKey=='BackendIP'].OutputValue" `
    --output text --region ap-south-1

ssh -i "your-key.pem" ec2-user@$IP "./deploy.sh"
```

### 4. Build and Deploy Frontend

```powershell
$BACKEND_URL = aws cloudformation describe-stacks --stack-name vaidya-ai `
    --query "Stacks[0].Outputs[?OutputKey=='BackendURL'].OutputValue" `
    --output text --region ap-south-1

$env:VITE_API_BASE = "$BACKEND_URL/api/v1"

cd frontend
npm install
npm run build

$BUCKET = aws cloudformation describe-stacks --stack-name vaidya-ai `
    --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" `
    --output text --region ap-south-1

aws s3 sync dist "s3://$BUCKET" --delete --region ap-south-1
```

---

## Verifying

```powershell
# Health check (use your Elastic IP)
curl http://<ELASTIC_IP>:8000/health
# Expected: {"status":"ok","version":"0.2.0","env":"production"}
```

- Frontend: `https://<cloudfront-id>.cloudfront.net`
- API Docs: `http://<elastic-ip>:8000/docs`
- SSH: `ssh -i <key.pem> ec2-user@<elastic-ip>`

---

## Troubleshooting

### Backend not responding
```bash
# SSH into instance
ssh -i key.pem ec2-user@<ELASTIC_IP>

# Check if container is running
docker ps

# Check container logs
docker logs vaidya-backend

# Restart manually
./deploy.sh
```

### Docker not installed (first boot)
UserData runs on first boot. If the instance just launched, wait 2-3 minutes for Docker to install.
```bash
# Check cloud-init status
sudo cloud-init status
```

### Bedrock permission denied
- Verify the model is enabled in Bedrock console for `ap-south-1`
- The EC2 IAM role has `bedrock:InvokeModel` — check it in IAM console

### Frontend shows connection error
- Verify `VITE_API_BASE` was set correctly during build
- Check that security group allows port 8000 from `0.0.0.0/0`
- Test: `curl http://<ELASTIC_IP>:8000/health`

---

## Cleanup (Delete Everything)

```powershell
# Empty S3 bucket first
$BUCKET = aws cloudformation describe-stacks --stack-name vaidya-ai `
    --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" `
    --output text --region ap-south-1
aws s3 rm "s3://$BUCKET" --recursive --region ap-south-1

# Delete ECR images
aws ecr delete-repository --repository-name vaidya-ai-backend --force --region ap-south-1

# Delete stack
aws cloudformation delete-stack --stack-name vaidya-ai --region ap-south-1
aws cloudformation wait stack-delete-complete --stack-name vaidya-ai --region ap-south-1
```

This removes: VPC, EC2 instance, Elastic IP, ECR, S3, CloudFront, IAM roles, logs.

---

## File Structure

```
Vaidya-AI/
├── .github/workflows/
│   ├── deploy-backend.yml       ← CI/CD: build Docker → push ECR → SSH deploy
│   └── deploy-frontend.yml      ← CI/CD: build → S3 → invalidate CloudFront
├── backend/
│   ├── Dockerfile
│   ├── .dockerignore
│   └── app/ (config.py updated for IAM roles, main.py for CORS)
├── frontend/
│   └── src/lib/chat-data.ts (reads VITE_API_BASE)
└── infra/
    ├── cloudformation.yaml      ← EC2 + Elastic IP + ECR + S3 + CloudFront
    ├── deploy.ps1               ← One-command local deploy script
    └── DEPLOYMENT.md            ← This file
```
