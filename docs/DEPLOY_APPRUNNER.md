# Deploying Ghost to AWS App Runner

Status: **not yet deployed.** This guide and `scripts/deploy_apprunner.sh` are prepared; nobody has run them against an AWS account.

## Prerequisites

1. **Docker** with `buildx` (Docker Desktop on macOS is fine). The script builds `linux/amd64`.
2. **AWS CLI v2**: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
3. **Credentials**: run `aws configure` (or `aws configure sso`) and confirm with `aws sts get-caller-identity`.
4. **IAM permissions** for the deploying user or role:
   - ECR: `ecr:CreateRepository`, `ecr:DescribeRepositories`, `ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload`, `ecr:PutImage`
   - App Runner: `apprunner:CreateService`, `apprunner:UpdateService`, `apprunner:ListServices`, `apprunner:DescribeService`
   - `iam:PassRole` on the ECR access role below
   - `sts:GetCallerIdentity`
5. **ECR access role for App Runner** (one time). It lets App Runner pull the private image:

   ```bash
   cat > trust.json <<'EOF'
   {"Version":"2012-10-17","Statement":[{"Effect":"Allow",
     "Principal":{"Service":"build.apprunner.amazonaws.com"},"Action":"sts:AssumeRole"}]}
   EOF
   aws iam create-role --role-name GhostAppRunnerEcrAccess --assume-role-policy-document file://trust.json
   aws iam attach-role-policy --role-name GhostAppRunnerEcrAccess \
     --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess
   aws iam get-role --role-name GhostAppRunnerEcrAccess --query Role.Arn --output text
   ```

   The last command prints the ARN to use as `ECR_ACCESS_ROLE_ARN`.

## Deploy

```bash
export AWS_REGION=us-east-1
export ECR_ACCESS_ROLE_ARN=arn:aws:iam::<account-id>:role/GhostAppRunnerEcrAccess
export GHOST_SESSION_SECRET="$(openssl rand -hex 32)"   # keep it; reuse on redeploys
./scripts/deploy_apprunner.sh
```

The script creates the ECR repository if missing, logs in, builds and pushes the image, then creates the service (or updates it if it already exists). It configures 1 vCPU / 2 GB, port 8080, health check `GET /healthz`, and the environment `GHOST_MAX_JOBS=2`, `GHOST_COOKIE_SECURE=1`, `GHOST_SESSION_SECRET`. It waits for `RUNNING` and prints the URL.

Notes:
- Keep the same `GHOST_SESSION_SECRET` across redeploys, or existing session cookies become invalid.
- App Runner stores runtime environment variables in the service config. To keep the secret out of it, move it to AWS Secrets Manager and use `RuntimeEnvironmentSecrets` (needs an instance role with `secretsmanager:GetSecretValue`).
- The first LibreOffice start is slow. If the service fails its health check at first, check logs in CloudWatch (`/aws/apprunner/<service>/.../application`). The Referee check in `/healthz` is cached for 60 seconds.
- Web uploads never run macros, and nothing here changes that.

## Cost note

App Runner bills for provisioned memory while the service is idle, plus vCPU and memory while active. At 1 vCPU / 2 GB, expect roughly US$10 to 15 per month idle and more under load, plus a small ECR storage charge. Check current pricing at https://aws.amazon.com/apprunner/pricing/. To stop charges, pause the service (`aws apprunner pause-service --service-arn ...`) or delete it, and delete the ECR repository.

## Record the URL

After the script prints `https://<id>.<region>.awsapprunner.com`, add it to `README.md`, for example under the title:

```markdown
**Live demo:** https://<id>.<region>.awsapprunner.com
```

Commit only the URL. Never commit the session secret or AWS account credentials.

## Post-deploy smoke checklist

- [ ] `curl -i https://<url>/healthz` returns `200` and the JSON shows `"status": "ok"` with the Referee `available: true`.
- [ ] The home page loads over HTTPS and shows the privacy note.
- [ ] Choose the **haunted** sample ("Try a sample"). The autopsy shows finding F-001.
- [ ] Confirm inputs and outputs, then run verification. Progress updates appear and the run finishes.
- [ ] Faithful mode reports zero mismatches.
- [ ] Record Decision D-001 and rerun in Intended mode. One expected difference appears with counterexample quantity=50.
- [ ] Download the HTML report, JSON report and generated module.
- [ ] Upload a file over 5 MB (or a non-workbook): it is rejected with a clear message.
- [ ] Redeploy check: rerun `./scripts/deploy_apprunner.sh` with the same variables and confirm it updates the existing service.
