# ==============================================================================
# Vaidya AI - AWS Deployment Script (EC2 + Elastic IP)
# ==============================================================================
# Prerequisites:
#   - AWS CLI installed and configured (aws configure)
#   - Docker Desktop installed and running
#   - Node.js / npm installed (for frontend build)
#   - (Optional) An EC2 Key Pair created in ap-south-1 for SSH access
#
# Usage:
#   .\deploy.ps1                              # Full deploy (stack + backend + frontend)
#   .\deploy.ps1 -SkipStack                   # Skip CloudFormation, deploy code only
#   .\deploy.ps1 -BackendOnly                 # Deploy only backend
#   .\deploy.ps1 -FrontendOnly               # Deploy only frontend
#   .\deploy.ps1 -KeyPairName "my-key"       # Specify EC2 key pair for SSH
# ==============================================================================

param(
    [switch]$SkipStack,
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [string]$KeyPairName = ""
)

$ErrorActionPreference = "Stop"

# --- Configuration ---
$STACK_NAME = "vaidya-ai"
$AWS_REGION = "ap-south-1"
$IMAGE_TAG = "latest"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Vaidya AI - AWS Deployment" -ForegroundColor Cyan
Write-Host "  (EC2 + Elastic IP)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get AWS Account ID
$AWS_ACCOUNT_ID = aws sts get-caller-identity --query "Account" --output text
if (-not $AWS_ACCOUNT_ID) {
    Write-Host "ERROR: Unable to get AWS Account ID. Run 'aws configure' first." -ForegroundColor Red
    exit 1
}
Write-Host "AWS Account: $AWS_ACCOUNT_ID" -ForegroundColor Green
Write-Host "Region: $AWS_REGION" -ForegroundColor Green
Write-Host ""

# ==============================================================================
# STEP 1: Deploy CloudFormation Stack
# ==============================================================================
if (-not $SkipStack -and -not $BackendOnly -and -not $FrontendOnly) {
    Write-Host "[1/4] Deploying CloudFormation stack..." -ForegroundColor Yellow

    $paramOverrides = "AppName=$STACK_NAME AwsRegion=$AWS_REGION"
    if ($KeyPairName) {
        $paramOverrides += " KeyPairName=$KeyPairName"
    }

    aws cloudformation deploy `
        --template-file "$PSScriptRoot\cloudformation.yaml" `
        --stack-name $STACK_NAME `
        --parameter-overrides $paramOverrides `
        --capabilities CAPABILITY_NAMED_IAM `
        --region $AWS_REGION `
        --no-fail-on-empty-changeset

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: CloudFormation deployment failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "CloudFormation stack deployed!" -ForegroundColor Green
    Write-Host ""
}

# Get stack outputs
Write-Host "Fetching stack outputs..." -ForegroundColor Yellow

$ECR_URI = aws cloudformation describe-stacks `
    --stack-name $STACK_NAME `
    --query "Stacks[0].Outputs[?OutputKey=='ECRRepositoryUri'].OutputValue" `
    --output text --region $AWS_REGION

$BACKEND_IP = aws cloudformation describe-stacks `
    --stack-name $STACK_NAME `
    --query "Stacks[0].Outputs[?OutputKey=='BackendIP'].OutputValue" `
    --output text --region $AWS_REGION

$BACKEND_URL = aws cloudformation describe-stacks `
    --stack-name $STACK_NAME `
    --query "Stacks[0].Outputs[?OutputKey=='BackendURL'].OutputValue" `
    --output text --region $AWS_REGION

$FRONTEND_BUCKET = aws cloudformation describe-stacks `
    --stack-name $STACK_NAME `
    --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" `
    --output text --region $AWS_REGION

$CLOUDFRONT_ID = aws cloudformation describe-stacks `
    --stack-name $STACK_NAME `
    --query "Stacks[0].Outputs[?OutputKey=='CloudFrontDistributionId'].OutputValue" `
    --output text --region $AWS_REGION

$FRONTEND_URL = aws cloudformation describe-stacks `
    --stack-name $STACK_NAME `
    --query "Stacks[0].Outputs[?OutputKey=='FrontendURL'].OutputValue" `
    --output text --region $AWS_REGION

Write-Host "ECR:          $ECR_URI" -ForegroundColor Gray
Write-Host "Backend IP:   $BACKEND_IP (Elastic IP - stable)" -ForegroundColor Gray
Write-Host "Backend URL:  $BACKEND_URL" -ForegroundColor Gray
Write-Host "S3 Bucket:    $FRONTEND_BUCKET" -ForegroundColor Gray
Write-Host "Frontend URL: $FRONTEND_URL" -ForegroundColor Gray
Write-Host ""

# ==============================================================================
# STEP 2: Build and Push Backend Docker Image
# ==============================================================================
if (-not $FrontendOnly) {
    Write-Host "[2/4] Building and pushing backend Docker image..." -ForegroundColor Yellow

    # Login to ECR
    $ECR_PASSWORD = aws ecr get-login-password --region $AWS_REGION
    $ECR_PASSWORD | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

    # Build Docker image
    $BackendPath = Join-Path $PSScriptRoot "..\backend"
    docker build -t "${ECR_URI}:${IMAGE_TAG}" $BackendPath

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Docker build failed!" -ForegroundColor Red
        exit 1
    }

    # Push to ECR
    docker push "${ECR_URI}:${IMAGE_TAG}"

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Docker push failed!" -ForegroundColor Red
        exit 1
    }

    Write-Host "Backend image pushed to ECR!" -ForegroundColor Green
    Write-Host ""

    # Deploy to EC2 via SSH (or SSM)
    Write-Host "[3/4] Deploying to EC2..." -ForegroundColor Yellow

    # Use AWS SSM to run the deploy script on the instance (no SSH key needed)
    $INSTANCE_ID = aws cloudformation describe-stacks `
        --stack-name $STACK_NAME `
        --query "Stacks[0].Outputs[?OutputKey=='EC2InstanceId'].OutputValue" `
        --output text --region $AWS_REGION

    # Try SSM first (doesn't require SSH key)
    $SSM_COMMAND = "#!/bin/bash`naws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com`ndocker pull ${ECR_URI}:${IMAGE_TAG}`ndocker stop vaidya-backend 2>/dev/null || true`ndocker rm vaidya-backend 2>/dev/null || true`ndocker run -d --name vaidya-backend --restart unless-stopped -p 8000:8000 -e APP_ENV=production -e AWS_REGION=$AWS_REGION -e BEDROCK_MODEL_ID=global.anthropic.claude-haiku-4-5-20251001-v1:0 -e CORS_ORIGINS=* ${ECR_URI}:${IMAGE_TAG}`ndocker image prune -f"

    # Send command via SSM
    $CMD_ID = aws ssm send-command `
        --instance-ids $INSTANCE_ID `
        --document-name "AWS-RunShellScript" `
        --parameters "commands=['$SSM_COMMAND']" `
        --region $AWS_REGION `
        --query "Command.CommandId" `
        --output text 2>$null

    if ($CMD_ID) {
        Write-Host "SSM command sent (ID: $CMD_ID). Waiting..." -ForegroundColor Gray
        Start-Sleep -Seconds 10

        $CMD_STATUS = aws ssm get-command-invocation `
            --command-id $CMD_ID `
            --instance-id $INSTANCE_ID `
            --query "Status" `
            --output text --region $AWS_REGION 2>$null

        if ($CMD_STATUS -eq "Success") {
            Write-Host "Backend deployed on EC2 via SSM!" -ForegroundColor Green
        } else {
            Write-Host "SSM command status: $CMD_STATUS" -ForegroundColor Yellow
            Write-Host "If SSM failed, SSH into the instance and run: ./deploy.sh" -ForegroundColor Yellow
            Write-Host "  ssh -i <key.pem> ec2-user@$BACKEND_IP" -ForegroundColor Gray
        }
    } else {
        Write-Host "SSM not available. Deploy manually via SSH:" -ForegroundColor Yellow
        Write-Host "  ssh -i <key.pem> ec2-user@$BACKEND_IP" -ForegroundColor Gray
        Write-Host "  ./deploy.sh" -ForegroundColor Gray
    }
    Write-Host ""
}

# ==============================================================================
# STEP 3: Build and Deploy Frontend
# ==============================================================================
if (-not $BackendOnly) {
    Write-Host "[4/4] Building and deploying frontend..." -ForegroundColor Yellow
    Write-Host "Using API URL: $BACKEND_URL/api/v1" -ForegroundColor Gray

    $FrontendPath = Join-Path $PSScriptRoot "..\frontend"

    # Set the API base URL for the production build
    $env:VITE_API_BASE = "$BACKEND_URL/api/v1"

    # Install dependencies and build
    Push-Location $FrontendPath
    npm install
    npm run build
    Pop-Location

    # Find build output directory
    $BuildDir = $null
    $PossibleDirs = @(
        (Join-Path $FrontendPath "dist"),
        (Join-Path $FrontendPath ".output\public"),
        (Join-Path $FrontendPath "build"),
        (Join-Path $FrontendPath "dist\client")
    )
    foreach ($dir in $PossibleDirs) {
        if (Test-Path $dir) {
            $BuildDir = $dir
            break
        }
    }

    if (-not $BuildDir) {
        Write-Host "WARNING: Could not find build output directory." -ForegroundColor Red
        Write-Host "Tried: dist, .output/public, build, dist/client" -ForegroundColor Red
        Write-Host "Upload manually: aws s3 sync <build-dir> s3://$FRONTEND_BUCKET --delete" -ForegroundColor Gray
    } else {
        Write-Host "Uploading from: $BuildDir" -ForegroundColor Gray
        aws s3 sync $BuildDir "s3://$FRONTEND_BUCKET" --delete --region $AWS_REGION

        # Invalidate CloudFront cache
        aws cloudfront create-invalidation `
            --distribution-id $CLOUDFRONT_ID `
            --paths "/*" `
            --region $AWS_REGION | Out-Null

        Write-Host "Frontend deployed to S3 + CloudFront cache invalidated!" -ForegroundColor Green
    }

    Remove-Item Env:\VITE_API_BASE -ErrorAction SilentlyContinue
    Write-Host ""
}

# ==============================================================================
# Done!
# ==============================================================================
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Deployment Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Backend API:  $BACKEND_URL (Elastic IP - stable)" -ForegroundColor Green
Write-Host "Frontend:     $FRONTEND_URL" -ForegroundColor Green
Write-Host ""
Write-Host "API Docs:     $BACKEND_URL/docs" -ForegroundColor Gray
Write-Host "Health Check: $BACKEND_URL/health" -ForegroundColor Gray
Write-Host "SSH:          ssh -i <key.pem> ec2-user@$BACKEND_IP" -ForegroundColor Gray
