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

1. Add one **repository secret** (Settings → Secrets and variables → Actions
   → *Secrets*): `AWS_ROLE_ARN` ← the infra repo's `ecr.yaml` stack's
   `GitHubActionsRoleArn` output.

   ```bash
   aws cloudformation describe-stacks --stack-name photo-gallery-dev-ecr \
     --query "Stacks[0].Outputs[?OutputKey=='GitHubActionsRoleArn'].OutputValue" --output text
   ```

2. Add these as **repository variables** instead (same Settings page →
   *Variables*): `AWS_REGION`, `ECR_REPOSITORY` (`photo-gallery-dev-app`),
   `ARTIFACT_KEY` (`source/appspec-taskdef.zip`), `ARTIFACT_BUCKET`.

3. **`ecs/taskdef.json` is a real, committed file — edit it directly when
   infra changes.** Every ARN in it (execution/task role, DB credentials
   secret, the SSM parameters for the CloudFront domain / DB endpoint /
   Django secret key) follows this account's deterministic
   `photo-gallery-dev-*` naming convention, so it never needs templating -
   see `templates/bootstrap.yaml`'s Description and the SSM parameters in
   `03-storage-cdn.yaml`/`04-database.yaml` in the infra repo for where each
   value comes from. `build-and-push.yml` only patches the `image` field
   (via `jq`) with the digest it just pushed, since that's the one thing
   that legitimately changes on every build; everything else resolves from
   Parameter Store/Secrets Manager at container launch, straight off the
   ARNs already in the file.

   If the infra is ever torn down and respun into a **different** AWS
   account or region, update the literal ARNs in `ecs/taskdef.json` to
   match - they won't re-resolve themselves.

4. Push to `main`. The workflow will build (running flake8/pytest as a
   Dockerfile build stage), push, patch, and deploy on its own from here.

## How a deploy happens

```
git push origin main
  -> GitHub Actions (OIDC, no long-lived keys)
     -> docker build (flake8 + pytest run as a build stage - fails the
                       build, and the push, if either fails)
        -> push to ECR (tags: <git-sha>, latest)
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
