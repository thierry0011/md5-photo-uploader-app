# Photo Gallery — Application

Django photo gallery: upload an image + a short description, see everything
in a grid. Images are stored in S3 and served through CloudFront; metadata
(the description) is stored in PostgreSQL. No authentication — the gallery is
public by design (per the assignment spec).

Infrastructure (VPC, ECS, RDS, CloudFront, the CI/CD pipeline) lives in the
separate **photo-uploader-infra** repo. This repo owns:

- The Django app (`config/`, `gallery/`)
- `Dockerfile` / `docker-entrypoint.sh`
- `.github/workflows/build-and-push.yml` — builds the image and pushes it to
  ECR on every push to `main`, authenticating to AWS via **OIDC** (no stored
  AWS keys)
- `ecs/taskdef.json` + `ecs/appspec.yaml` — the CodeDeploy blue/green deploy
  files that `photo-gallery-dev-pipeline` (in the infra repo) pulls from this
  repo on every deployment

## Local development

```bash
cp .env.example .env
docker compose up --build
# http://localhost:8000
```

Without AWS credentials configured, uploaded images fall back to local disk
storage automatically (see `config/settings.py`) so you can develop the UI
without touching S3.

Running tests / lint directly:

```bash
pip install -r requirements-dev.txt
DJANGO_TESTING=true DJANGO_SECRET_KEY=local pytest -v
flake8 .
```

## Wiring this repo to the deployed infrastructure

These values only exist once the infra repo's stacks are deployed. Fill them
in once, commit, and the pipeline is fully automatic from then on.

1. **`.github/workflows/build-and-push.yml`**: set `AWS_ROLE_ARN` to the
   `GitHubActionsRoleArn` output of the infra repo's `06-github-oidc.yaml`
   stack, and `AWS_REGION` to match wherever you deployed.

   ```bash
   aws cloudformation list-exports \
     --query "Exports[?Name=='photo-gallery-dev-GitHubActionsRoleArn'].Value" --output text
   ```

2. **`ecs/taskdef.json`**: replace the `<PLACEHOLDER>` values using the
   corresponding infra stack outputs:

   | Placeholder | Source export name |
   |---|---|
   | `<AWS_ACCOUNT_ID>` | your account ID (`aws sts get-caller-identity`) |
   | `<AWS_REGION>` | the region you deployed to |
   | `<IMAGES_BUCKET_NAME>` | `photo-gallery-dev-ImagesBucketName` |
   | `<CLOUDFRONT_DOMAIN_NAME>` | `photo-gallery-dev-CloudFrontDomainName` |
   | `<DB_ENDPOINT_ADDRESS>` | `photo-gallery-dev-DBEndpointAddress` |
   | `<DB_CREDENTIALS_SECRET_ARN>` | `photo-gallery-dev-DBCredentialsSecretArn` |
   | `<DJANGO_SECRET_KEY_SECRET_ARN>` | the ARN of the `photo-gallery-dev-django-secret-key` secret (Secrets Manager console/CLI) |

   `<IMAGE1_NAME>` is **not** a placeholder to fill in — CodePipeline
   substitutes it automatically with the freshly-pushed image URI on every
   deployment. Leave it exactly as-is.

3. Push both files to `main`. The pipeline will pick up `ecs/taskdef.json`
   and `ecs/appspec.yaml` on its next run.

## How a deploy happens

```
git push origin main
  -> GitHub Actions (OIDC, no long-lived keys)
     -> test (flake8 + pytest)
     -> docker build -> push to ECR (tags: <git-sha>, latest)
        -> EventBridge rule (in infra repo) fires on the "latest" push
           -> CodePipeline starts
              -> pulls ecs/taskdef.json + ecs/appspec.yaml from this repo
              -> CodeDeploy registers a new task definition revision
                 with the new image, then blue/green-shifts ALB traffic
                 from the old task set to the new one
```

## Project layout

```
config/          Django project settings, URLs, WSGI entrypoint
gallery/          The app: model, form, views, templates, tests
ecs/              CodeDeploy blue/green deploy files (taskdef.json, appspec.yaml)
.github/workflows/  CI: test -> build -> push to ECR (OIDC)
Dockerfile        Multi-stage build, non-root user, baked-in static assets
docker-compose.yml  Local dev: Django + Postgres
```
