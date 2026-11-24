# Deploying Ghost to Amazon ECS Express Mode

Status: **deployed and smoke-tested** in us-east-1 (create, update path, healthz, haunted-sample flow, report downloads). (AWS App Runner is closed to new customers, so Express Mode replaces it.)

Express Mode creates a Fargate service, an Application Load Balancer, security groups and autoscaling from one command, and serves it at `https://<service-name>.ecs.<region>.on.aws`.

## Prerequisites

1. **Docker** (Docker Desktop on macOS works). The script builds `linux/amd64`.
2. **AWS CLI v2** with the `ecs create-express-gateway-service` command (update the CLI if it is missing), and `openssl`.
3. **Log in** with `aws login`, `aws configure sso`, or `aws configure`. Confirm with `aws sts get-caller-identity`.
4. **A default VPC with public subnets** in the region. The script runs `aws ec2 describe-vpcs --filters Name=is-default,Values=true` and stops with a message if none exists.
5. **IAM permissions** for the deploying identity:
   - ECS: `ecs:CreateExpressGatewayService`, `ecs:UpdateExpressGatewayService`, `ecs:DescribeExpressGatewayService`, `ecs:DeleteExpressGatewayService` (and `ecs:MonitorExpressGatewayService` if your CLI version needs it)
   - ECR: `ecr:GetAuthorizationToken`, `ecr:CreateRepository`, `ecr:DescribeRepositories`, `ecr:DescribeImages`, `ecr:BatchCheckLayerAvailability`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload`, `ecr:PutImage`
   - IAM: `iam:GetRole`, `iam:CreateRole`, `iam:AttachRolePolicy`, `iam:PassRole` on both roles below
   - EC2: `ec2:DescribeVpcs`, `ec2:DescribeSubnets`, `ec2:DescribeSecurityGroups`
   - Load balancing: `elasticloadbalancing:Describe*`, plus `iam:CreateServiceLinkedRole` for the ECS and Elastic Load Balancing service-linked roles on first use in an account

   The infrastructure role (below) performs the actual ALB and security-group creation. Your own identity needs enough to call ECS and pass the roles. If a call is denied, the error names the missing action.

## Roles

The script creates both once and reuses them afterwards:

| Role | Trusted by | Managed policy |
|---|---|---|
| `GhostEcsTaskExecutionRole` | `ecs-tasks.amazonaws.com` | `arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy` |
| `GhostEcsInfrastructureRole` | `ecs.amazonaws.com` | `arn:aws:iam::aws:policy/service-role/AmazonECSInfrastructureRoleforExpressGatewayServices` |

New roles can take about a minute to propagate. The script waits 20 s and retries the ECS call up to 6 times (15 s apart) on assume-role errors.

## Run

Preview first. This prints every command and calls no AWS API:

```bash
./scripts/deploy_ecs_express.sh --dry-run
```

Deploy:

```bash
./scripts/deploy_ecs_express.sh
```

Flags:

- `--dry-run`: print commands, call nothing with credentials.
- `--skip-build`: reuse the image already in ECR (fails if the tag is missing).
- `--delete`: delete the service, then print the commands to remove the roles and the ECR repository.

Defaults: `AWS_REGION=us-east-1`, `SERVICE_NAME=ghost-in-the-macro`, `ECR_REPO=ghost-in-the-macro`, `IMAGE_TAG=latest`. Override by exporting the variable.

`GHOST_SESSION_SECRET` is read from the environment (letters, digits, `.`, `_`, `~`, `-` only). If unset on first create, the script generates one with `openssl rand -hex 32` and prints it **once**. It is never written to the repo. The container JSON that holds it goes to a `chmod 600` temp file that is removed on exit, and command logs never show it.

The script then:

1. checks the default VPC, creates the ECR repository if missing, logs in, builds and pushes;
2. creates the two roles if missing;
3. creates the service with 1 vCPU (`--cpu 1024`), 2 GB (`--memory 2048`), port 8080, health check `/healthz`, scaling pinned to **exactly one task** (`minTaskCount=1`, `maxTaskCount=1`), and `GHOST_MAX_JOBS=2`, `GHOST_COOKIE_SECURE=1`, `GHOST_SESSION_SECRET`, `GHOST_SOFFICE=/usr/bin/soffice`. If the service exists, it updates it with the new image instead;
4. prints the URL.

The single-task pin is required: the web app keeps sessions and job state in memory, so a second task would lose them.

Monitor or inspect:

```bash
aws ecs monitor-express-gateway-service --region us-east-1 --service-arn <service-arn>
aws ecs describe-express-gateway-service --region us-east-1 --service-arn <service-arn>
```

Confirmed against a live account: CPU and memory are given in CPU units and MiB (`1024` / `2048`); `--cpu 1 --memory 2` was rejected with "Invalid CPU/Memory combination". The service ARN has the shape `arn:aws:ecs:us-east-1:<acct>:service/default/<name>`, and the update path works with it. Not verified: the exact describe query used to read the endpoint. If it fails, the URL falls back to `https://<service-name>.ecs.<region>.on.aws`.

Web uploads never run macros. Nothing in the deployment changes that.

## Cost

This is an estimate, not a quote: Fargate at 1 vCPU / 2 GB running 24x7 plus an Application Load Balancer comes to roughly **US$40 per month** if left running, plus small ECR and log charges. See [Fargate pricing](https://aws.amazon.com/fargate/pricing/) and [ELB pricing](https://aws.amazon.com/elasticloadbalancing/pricing/).

**Delete after judging:**

```bash
./scripts/deploy_ecs_express.sh --delete
```

That runs `aws ecs delete-express-gateway-service --service-arn <arn>` and prints the commands to remove the roles and ECR repository.

## Rotate the session secret

Rotating invalidates existing session cookies, so active users start new sessions. Export a new value and rerun; with the variable set, an existing service gets its environment replaced:

```bash
export GHOST_SESSION_SECRET="$(openssl rand -hex 32)"   # keep it in your shell or password manager
./scripts/deploy_ecs_express.sh --skip-build
```

This calls `aws ecs update-express-gateway-service --service-arn <arn> --primary-container file://<temp>`. Check `aws ecs update-express-gateway-service help` if your CLI version differs. With the variable unset, an update changes only the image.

For stronger handling, move the secret to AWS Secrets Manager and reference it from the container definition.

## Post-deploy smoke checklist

- [ ] `curl -i https://<url>/healthz` returns `200` with `"status": "ok"` and the Referee reported as available.
- [ ] The home page loads over HTTPS and shows the privacy note.
- [ ] Load the **haunted** sample. The autopsy shows finding F-001.
- [ ] Run verification in Faithful mode: zero mismatches.
- [ ] Record Decision D-001 ("bulk means 50 or more") and run verification in Intended mode: one expected difference, counterexample quantity=50.
- [ ] Download the HTML report, the JSON report and the generated module.
- [ ] Upload a file over 5 MB (or a non-workbook): it is rejected with a clear message.
- [ ] Rerun `./scripts/deploy_ecs_express.sh --skip-build` and confirm it updates the existing service.

## Record the URL

Add the printed URL near the top of `README.md`:

```markdown
**Live demo:** https://<service-name>.ecs.<region>.on.aws
```

Commit only the URL. Never commit the session secret or AWS credentials.
