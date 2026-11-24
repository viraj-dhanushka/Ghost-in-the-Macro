#!/usr/bin/env bash
# Build, push and deploy Ghost to Amazon ECS Express Mode (Fargate behind an ALB).
# Usage: scripts/deploy_ecs_express.sh [--dry-run] [--skip-build] [--delete]
#   --dry-run     print every command; run nothing that needs credentials
#   --skip-build  reuse the image already in ECR (no docker build/push)
#   --delete      delete the service and print the commands to remove roles/ECR
# See docs/DEPLOY_ECS_EXPRESS.md. No secrets are stored in this file.
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
SERVICE_NAME="${SERVICE_NAME:-ghost-in-the-macro}"
ECR_REPO="${ECR_REPO:-ghost-in-the-macro}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
EXEC_ROLE_NAME="${EXEC_ROLE_NAME:-GhostEcsTaskExecutionRole}"
INFRA_ROLE_NAME="${INFRA_ROLE_NAME:-GhostEcsInfrastructureRole}"
CPU="${CPU:-1024}"          # CPU units (1024 = 1 vCPU)
MEMORY="${MEMORY:-2048}"   # MiB
PORT=8080
HEALTH_PATH=/healthz
EXEC_POLICY_ARN="arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
INFRA_POLICY_ARN="arn:aws:iam::aws:policy/service-role/AmazonECSInfrastructureRoleforExpressGatewayServices"

DRY_RUN=0
SKIP_BUILD=0
DELETE=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --skip-build) SKIP_BUILD=1 ;;
    --delete) DELETE=1 ;;
    -h|--help) sed -n '2,7p' "$0"; exit 0 ;;
    *) echo "error: unknown argument: $arg" >&2; exit 2 ;;
  esac
done

# run: print the command; execute it unless --dry-run.
run() {
  if [ "$DRY_RUN" = 1 ]; then
    echo "[dry-run] $*"
  else
    "$@"
  fi
}

cd "$(dirname "$0")/.."

for tool in aws docker openssl; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    if [ "$DRY_RUN" = 1 ]; then echo "[dry-run] warning: $tool not found on PATH"
    elif [ "$tool" = docker ] && { [ "$SKIP_BUILD" = 1 ] || [ "$DELETE" = 1 ]; }; then :
    else echo "error: $tool not found on PATH" >&2; exit 1; fi
  fi
done

if [ "$DRY_RUN" = 1 ]; then
  ACCOUNT_ID="<account-id>"
  echo "[dry-run] aws sts get-caller-identity   (skipped, no credentials used)"
else
  aws sts get-caller-identity >/dev/null 2>&1 \
    || { echo "error: aws sts get-caller-identity failed; log in first (aws login / aws configure sso / aws configure)" >&2; exit 1; }
  ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
fi
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
IMAGE_URI="${REGISTRY}/${ECR_REPO}:${IMAGE_TAG}"
EXEC_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${EXEC_ROLE_NAME}"
INFRA_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${INFRA_ROLE_NAME}"
# Express services live in the "default" cluster. If this ARN shape is wrong for
# your account, the existence check below fails and the script tries to create.
SERVICE_ARN="arn:aws:ecs:${AWS_REGION}:${ACCOUNT_ID}:service/default/${SERVICE_NAME}"
echo "==> Account ${ACCOUNT_ID}, region ${AWS_REGION}, service ${SERVICE_NAME}"

service_exists() {
  [ "$DRY_RUN" = 0 ] && aws ecs describe-express-gateway-service --region "$AWS_REGION" \
    --service-arn "$SERVICE_ARN" >/dev/null 2>&1
}

# ---------------------------------------------------------------- delete
if [ "$DELETE" = 1 ]; then
  echo "==> Deleting service ${SERVICE_NAME}"
  run aws ecs delete-express-gateway-service --region "$AWS_REGION" --service-arn "$SERVICE_ARN"
  cat <<EOF

The service is being deleted (this also removes the ALB it created).
Roles and the ECR repository are kept. To remove them too, run:

  aws iam detach-role-policy --role-name ${EXEC_ROLE_NAME} --policy-arn ${EXEC_POLICY_ARN}
  aws iam delete-role --role-name ${EXEC_ROLE_NAME}
  aws iam detach-role-policy --role-name ${INFRA_ROLE_NAME} --policy-arn ${INFRA_POLICY_ARN}
  aws iam delete-role --role-name ${INFRA_ROLE_NAME}
  aws ecr delete-repository --region ${AWS_REGION} --repository-name ${ECR_REPO} --force
EOF
  [ "$DRY_RUN" = 1 ] && echo "No deploy or delete was performed (dry run)."
  exit 0
fi

# ---------------------------------------------------------------- default VPC
echo "==> Checking for a default VPC (Express Mode needs it, with public subnets)"
if [ "$DRY_RUN" = 1 ]; then
  echo "[dry-run] aws ec2 describe-vpcs --region ${AWS_REGION} --filters Name=is-default,Values=true"
else
  VPC_ID="$(aws ec2 describe-vpcs --region "$AWS_REGION" --filters Name=is-default,Values=true \
    --query 'Vpcs[0].VpcId' --output text 2>/dev/null || true)"
  if [ -z "$VPC_ID" ] || [ "$VPC_ID" = "None" ]; then
    echo "error: no default VPC in ${AWS_REGION}. Create one with 'aws ec2 create-default-vpc --region ${AWS_REGION}'" >&2
    echo "       or choose another region (AWS_REGION=...). Stopping before creating anything." >&2
    exit 1
  fi
  echo "    default VPC: ${VPC_ID}"
fi

# ---------------------------------------------------------------- ECR + image
echo "==> Ensuring ECR repository ${ECR_REPO}"
if [ "$DRY_RUN" = 1 ] || ! aws ecr describe-repositories --region "$AWS_REGION" --repository-names "$ECR_REPO" >/dev/null 2>&1; then
  run aws ecr create-repository --region "$AWS_REGION" --repository-name "$ECR_REPO"
fi

if [ "$SKIP_BUILD" = 1 ]; then
  echo "==> --skip-build: reusing ${IMAGE_URI}"
  if [ "$DRY_RUN" = 0 ]; then
    aws ecr describe-images --region "$AWS_REGION" --repository-name "$ECR_REPO" \
      --image-ids imageTag="$IMAGE_TAG" >/dev/null 2>&1 \
      || { echo "error: ${ECR_REPO}:${IMAGE_TAG} not found in ECR; run without --skip-build" >&2; exit 1; }
  else
    echo "[dry-run] aws ecr describe-images --repository-name ${ECR_REPO} --image-ids imageTag=${IMAGE_TAG}"
  fi
else
  echo "==> Logging in to ${REGISTRY}"
  if [ "$DRY_RUN" = 1 ]; then
    echo "[dry-run] aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${REGISTRY}"
  else
    aws ecr get-login-password --region "$AWS_REGION" \
      | docker login --username AWS --password-stdin "$REGISTRY"
  fi
  echo "==> Building and pushing"
  run docker build --platform linux/amd64 -t "$IMAGE_URI" .
  run docker push "$IMAGE_URI"
fi

# ---------------------------------------------------------------- IAM roles
# ensure_role <name> <trust-service> <policy-arn>
ensure_role() {
  local name="$1" svc="$2" policy="$3" trust
  echo "==> Ensuring IAM role ${name} (trusted by ${svc})"
  if [ "$DRY_RUN" = 1 ] || ! aws iam get-role --role-name "$name" >/dev/null 2>&1; then
    trust="{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Principal\":{\"Service\":\"${svc}\"},\"Action\":\"sts:AssumeRole\"}]}"
    run aws iam create-role --role-name "$name" --assume-role-policy-document "$trust"
    run aws iam attach-role-policy --role-name "$name" --policy-arn "$policy"
    NEW_ROLES=1
  fi
}
NEW_ROLES=0
ensure_role "$EXEC_ROLE_NAME" ecs-tasks.amazonaws.com "$EXEC_POLICY_ARN"
ensure_role "$INFRA_ROLE_NAME" ecs.amazonaws.com "$INFRA_POLICY_ARN"
if [ "$NEW_ROLES" = 1 ] && [ "$DRY_RUN" = 0 ]; then
  echo "    waiting 20 s for new roles to propagate"
  sleep 20
fi

# ---------------------------------------------------------------- container JSON
# The JSON may hold the secret, so it goes to a private temp file removed on exit.
CONTAINER_FILE=""
cleanup() { [ -n "$CONTAINER_FILE" ] && rm -f "$CONTAINER_FILE"; return 0; }
trap cleanup EXIT

# write_container_json <with-env: 1|0> <secret>
write_container_json() {
  local with_env="$1" secret="$2"
  CONTAINER_FILE="$(umask 077; mktemp)"
  chmod 600 "$CONTAINER_FILE"
  if [ "$with_env" = 1 ]; then
    cat >"$CONTAINER_FILE" <<EOF
{"image":"${IMAGE_URI}","containerPort":${PORT},"environment":[{"name":"GHOST_MAX_JOBS","value":"2"},{"name":"GHOST_COOKIE_SECURE","value":"1"},{"name":"GHOST_SESSION_SECRET","value":"${secret}"},{"name":"GHOST_SOFFICE","value":"/usr/bin/soffice"}]}
EOF
  else
    cat >"$CONTAINER_FILE" <<EOF
{"image":"${IMAGE_URI}","containerPort":${PORT}}
EOF
  fi
}

# Retry on IAM propagation errors (newly created roles).
# retry_aws <description> <command...>  (stderr is filtered, never the JSON file)
retry_aws() {
  local what="$1"; shift
  local out attempt
  for attempt in 1 2 3 4 5 6; do
    if out="$("$@" 2>&1)"; then
      printf '%s\n' "$out"
      return 0
    fi
    if printf '%s' "$out" | grep -qiE 'assume|not authorized to perform: sts|role.*(not|cannot)|invalid.*role|propagat'; then
      echo "    ${what}: role not ready yet (attempt ${attempt}/6), retrying in 15 s" >&2
      sleep 15
    else
      printf '%s\n' "$out" >&2
      return 1
    fi
  done
  printf '%s\n' "$out" >&2
  return 1
}

# ---------------------------------------------------------------- create / update
if service_exists; then
  echo "==> Service exists: updating to the current image"
  if [ -n "${GHOST_SESSION_SECRET:-}" ]; then
    echo "    GHOST_SESSION_SECRET is set: environment will be replaced (secret rotation)."
    write_container_json 1 "$GHOST_SESSION_SECRET"
  else
    echo "    GHOST_SESSION_SECRET not set: image only, environment left as is."
    write_container_json 0 ""
  fi
  retry_aws update aws ecs update-express-gateway-service --region "$AWS_REGION" \
    --service-arn "$SERVICE_ARN" --primary-container "file://${CONTAINER_FILE}" >/dev/null
else
  SECRET_GENERATED=0
  if [ "$DRY_RUN" = 1 ]; then
    SECRET="<redacted>"
    echo "[dry-run] GHOST_SESSION_SECRET: would use \$GHOST_SESSION_SECRET or 'openssl rand -hex 32'"
  elif [ -n "${GHOST_SESSION_SECRET:-}" ]; then
    SECRET="$GHOST_SESSION_SECRET"
    case "$SECRET" in
      *[!A-Za-z0-9._~-]*) echo "error: GHOST_SESSION_SECRET may only contain A-Z a-z 0-9 . _ ~ -" >&2; exit 1 ;;
    esac
  else
    SECRET="$(openssl rand -hex 32)"
    SECRET_GENERATED=1
  fi
  write_container_json 1 "$SECRET"
  echo "==> Creating Express Mode service ${SERVICE_NAME}"
  if [ "$DRY_RUN" = 1 ]; then
    echo "[dry-run] aws ecs create-express-gateway-service --region ${AWS_REGION} --service-name ${SERVICE_NAME} \\"
    echo "            --execution-role-arn ${EXEC_ROLE_ARN} --infrastructure-role-arn ${INFRA_ROLE_ARN} \\"
    echo "            --cpu ${CPU} --memory ${MEMORY} --health-check-path ${HEALTH_PATH} \\"
    echo "            --scaling-target '{\"minTaskCount\":1,\"maxTaskCount\":1}' --monitor-resources \\"
    echo "            --primary-container file://<temp-file, mode 600>"
    echo "[dry-run] primary-container (secret redacted):"
    cat "$CONTAINER_FILE"
  else
    if [ "$SECRET_GENERATED" = 1 ]; then
      echo "    Generated GHOST_SESSION_SECRET (shown once, not saved anywhere):"
      echo "    ${SECRET}"
    fi
    # Pinned to exactly one task: sessions and job state live in memory.
    retry_aws create aws ecs create-express-gateway-service --region "$AWS_REGION" \
      --service-name "$SERVICE_NAME" \
      --execution-role-arn "$EXEC_ROLE_ARN" --infrastructure-role-arn "$INFRA_ROLE_ARN" \
      --primary-container "file://${CONTAINER_FILE}" \
      --cpu "$CPU" --memory "$MEMORY" --health-check-path "$HEALTH_PATH" \
      --scaling-target '{"minTaskCount":1,"maxTaskCount":1}' \
      --monitor-resources
  fi
fi

# ---------------------------------------------------------------- URL
if [ "$DRY_RUN" = 1 ]; then
  echo "[dry-run] aws ecs describe-express-gateway-service --service-arn ${SERVICE_ARN}   (poll until active)"
  echo "[dry-run] final URL: https://${SERVICE_NAME}.ecs.${AWS_REGION}.on.aws"
  echo "No deploy was performed (dry run)."
  exit 0
fi

echo "==> Reading the service endpoint"
ENDPOINT="$(aws ecs describe-express-gateway-service --region "$AWS_REGION" --service-arn "$SERVICE_ARN" \
  --query 'service.activeConfigurations[0].ingressPaths[0].endpoint' --output text 2>/dev/null || true)"
case "$ENDPOINT" in
  ""|None) URL="https://${SERVICE_NAME}.ecs.${AWS_REGION}.on.aws" ;;
  http*) URL="$ENDPOINT" ;;
  *) URL="https://${ENDPOINT}" ;;
esac
echo "==> Deployed: ${URL}"
echo "    Health:   ${URL}${HEALTH_PATH}"
echo "    Status:   aws ecs describe-express-gateway-service --region ${AWS_REGION} --service-arn ${SERVICE_ARN}"
echo "    Next: run the smoke checklist in docs/DEPLOY_ECS_EXPRESS.md, add the URL to README.md,"
echo "          and delete with '$0 --delete' after judging (the ALB bills while it runs)."
