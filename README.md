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
   `GitHubActionsRoleArn` output of the infra repo's root stack, and
   `AWS_REGION` to match wherever you deployed.

   ```bash
   aws cloudformation describe-stacks --stack-name photo-gallery-dev-root \
     --query "Stacks[0].Outputs[?OutputKey=='GitHubActionsRoleArn'].OutputValue" --output text
   ```

2. **`ecs/taskdef.json` is generated — never edit it by hand.** The source
   of truth is `ecs/taskdef.template.json`, which the `build-and-push.yml`
   workflow renders into `ecs/taskdef.json` on every run (via `envsubst`)
   and commits back before pushing the image, so CodePipeline's git-sourced
   deploy input is always current. Deterministic values (account ID,
   region, the images bucket name, both ECS role ARNs — none of these carry
   an AWS-generated random suffix) are hardcoded as plain `env:` values at
   the top of the workflow file already. The four that *do* carry a random
   suffix, and so change if their resource is ever recreated, must be set
   as **repository secrets** (Settings → Secrets and variables → Actions)
   instead of committed literally:

   | Secret | Source |
   |---|---|
   | `CLOUDFRONT_DOMAIN_NAME` | infra root stack output `CloudFrontDomainName` |
   | `DB_ENDPOINT_ADDRESS` | `DatabaseStack` nested-stack output `DBInstanceEndpointAddress` (query that nested stack directly - not surfaced at the root level) |
   | `DB_CREDENTIALS_SECRET_ARN` | Secrets Manager console/CLI: ARN of the `photo-gallery-dev-db-credentials` secret |
   | `DJANGO_SECRET_KEY_SECRET_ARN` | Secrets Manager console/CLI: ARN of the `photo-gallery-dev-django-secret-key` secret |

   ```bash
   aws cloudformation describe-stacks --stack-name photo-gallery-dev-root \
     --query "Stacks[0].Outputs[?OutputKey=='CloudFrontDomainName'].OutputValue" --output text
   ```

   Update these secrets whenever the underlying resource is recreated (e.g.
   after an RDS replacement) — the next workflow run re-renders
   `ecs/taskdef.json` from the current secret values automatically, no
   manual file editing required.

   `<IMAGE1_NAME>` in the template (and `<TASK_DEFINITION>` in
   `appspec.yaml`) are **not** placeholders to fill in — `envsubst` only
   touches `$VAR`/`${VAR}` syntax, so these angle-bracket tokens pass
   through untouched for CodeDeploy to substitute itself at deploy time.
   Leave them exactly as-is.

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
