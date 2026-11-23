#!/usr/bin/env bash
# Build, push and deploy Ghost to AWS App Runner (ECR image source).
# See docs/DEPLOY_APPRUNNER.md. Nothing secret is stored in this file.
#
# Required (export before running):
#   AWS_REGION               e.g. us-east-1
#   ECR_ACCESS_ROLE_ARN      IAM role App Runner uses to pull from ECR
#                            (trusted by build.apprunner.amazonaws.com,
#                             policy AWSAppRunnerServicePolicyForECRAccess)
#   GHOST_SESSION_SECRET     long random string, e.g. $(openssl rand -hex 32)
# Optional:
#   SERVICE_NAME             default ghost-in-the-macro
#   ECR_REPO                 default ghost-in-the-macro
#   IMAGE_TAG                default git short SHA, else "latest"
#   CPU / MEMORY             default "1 vCPU" / "2 GB"
set -euo pipefail

: "${AWS_REGION:?set AWS_REGION}"
: "${ECR_ACCESS_ROLE_ARN:?set ECR_ACCESS_ROLE_ARN}"
: "${GHOST_SESSION_SECRET:?set GHOST_SESSION_SECRET (e.g. openssl rand -hex 32)}"
SERVICE_NAME="${SERVICE_NAME:-ghost-in-the-macro}"
ECR_REPO="${ECR_REPO:-ghost-in-the-macro}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo latest)}"
CPU="${CPU:-1 vCPU}"
MEMORY="${MEMORY:-2 GB}"
PORT=8080
HEALTH_PATH=/healthz

for tool in aws docker; do
  command -v "$tool" >/dev/null 2>&1 || { echo "error: $tool not found on PATH" >&2; exit 1; }
done
cd "$(dirname "$0")/.."

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
IMAGE_URI="${REGISTRY}/${ECR_REPO}:${IMAGE_TAG}"

echo "==> Ensuring ECR repository ${ECR_REPO}"
aws ecr describe-repositories --region "$AWS_REGION" --repository-names "$ECR_REPO" >/dev/null 2>&1 \
  || aws ecr create-repository --region "$AWS_REGION" --repository-name "$ECR_REPO" >/dev/null

echo "==> Logging in to ${REGISTRY}"
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$REGISTRY"

echo "==> Building ${IMAGE_URI} (linux/amd64)"
docker build --platform linux/amd64 -t "$IMAGE_URI" .

echo "==> Pushing image"
docker push "$IMAGE_URI"

# Build the service config in a temp file (it contains the session secret).
CONFIG="$(mktemp)"
trap 'rm -f "$CONFIG"' EXIT
chmod 600 "$CONFIG"

write_config() {
  # $1 = "create" includes ServiceName and instance config; "update" omits ServiceName.
  local name_line=""
  if [ "$1" = create ]; then name_line="\"ServiceName\": \"${SERVICE_NAME}\","; fi
  cat >"$CONFIG" <<EOF
{
  ${name_line}
  "SourceConfiguration": {
    "AuthenticationConfiguration": { "AccessRoleArn": "${ECR_ACCESS_ROLE_ARN}" },
    "AutoDeploymentsEnabled": false,
    "ImageRepository": {
      "ImageIdentifier": "${IMAGE_URI}",
      "ImageRepositoryType": "ECR",
      "ImageConfiguration": {
        "Port": "${PORT}",
        "RuntimeEnvironmentVariables": {
          "GHOST_MAX_JOBS": "2",
          "GHOST_COOKIE_SECURE": "1",
          "GHOST_SESSION_SECRET": "${GHOST_SESSION_SECRET}"
        }
      }
    }
  },
  "InstanceConfiguration": { "Cpu": "${CPU}", "Memory": "${MEMORY}" },
  "HealthCheckConfiguration": {
    "Protocol": "HTTP",
    "Path": "${HEALTH_PATH}",
    "Interval": 20,
    "Timeout": 10,
    "HealthyThreshold": 1,
    "UnhealthyThreshold": 5
  }
}
EOF
}

SERVICE_ARN="$(aws apprunner list-services --region "$AWS_REGION" \
  --query "ServiceSummaryList[?ServiceName=='${SERVICE_NAME}'].ServiceArn | [0]" --output text)"

if [ -z "$SERVICE_ARN" ] || [ "$SERVICE_ARN" = "None" ]; then
  echo "==> Creating App Runner service ${SERVICE_NAME}"
  write_config create
  SERVICE_ARN="$(aws apprunner create-service --region "$AWS_REGION" \
    --cli-input-json "file://${CONFIG}" --query Service.ServiceArn --output text)"
else
  echo "==> Updating App Runner service ${SERVICE_NAME}"
  write_config update
  pick() { python3 -c 'import json,sys;print(json.dumps(json.load(open(sys.argv[1]))[sys.argv[2]]))' "$CONFIG" "$1"; }
  aws apprunner update-service --region "$AWS_REGION" --service-arn "$SERVICE_ARN" \
    --source-configuration "$(pick SourceConfiguration)" \
    --instance-configuration "$(printf '{"Cpu":"%s","Memory":"%s"}' "$CPU" "$MEMORY")" \
    --health-check-configuration "$(pick HealthCheckConfiguration)" >/dev/null
fi

echo "==> Waiting for service to reach RUNNING (up to ~10 min)"
for _ in $(seq 1 60); do
  STATUS="$(aws apprunner describe-service --region "$AWS_REGION" --service-arn "$SERVICE_ARN" \
    --query Service.Status --output text)"
  echo "    status: ${STATUS}"
  case "$STATUS" in
    RUNNING) break ;;
    CREATE_FAILED|DELETE_FAILED|DELETED) echo "error: deployment failed (${STATUS})" >&2; exit 1 ;;
  esac
  sleep 10
done
[ "$STATUS" = RUNNING ] || { echo "error: timed out waiting for RUNNING" >&2; exit 1; }

URL="$(aws apprunner describe-service --region "$AWS_REGION" --service-arn "$SERVICE_ARN" \
  --query Service.ServiceUrl --output text)"
echo "==> Deployed: https://${URL}"
echo "    Health:   https://${URL}${HEALTH_PATH}"
echo "    Next: run the smoke checklist in docs/DEPLOY_APPRUNNER.md and add the URL to README.md"
