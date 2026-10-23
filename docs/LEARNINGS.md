# DocMind DevOps Learnings

## Phase 0: Local setup on macOS (Apple Silicon)

### Problem: pip could not find langchain-core>=1.0
- Cause: venv used macOS built-in Python 3.9 (pip 21.2.4). LangChain 1.x needs Python 3.10+.
- Fix: `conda create -n docmind python=3.12 -y` then `conda activate docmind`
- Check: `python --version` shows 3.12.x

### Problem: tests ran from /opt/anaconda3 instead of my env
- Cause: Anaconda (base) was active, not the project env.
- Fix: `conda activate docmind`, run `python -m pytest -q`

### Problem: `python: command not found` after `conda deactivate`
- Cause: macOS only has `python3`. No env active.
- Fix: `conda activate docmind`

### Problem: `conda: error: invalid choice: 'conda'`
- Cause: typed `conda` twice on one line.
- Fix: run exactly `conda activate docmind`

### Problem: terminal stuck at `quote>`
- Cause: zsh does not treat `#` as a comment when pasting; an apostrophe opened a quote.
- Fix: Ctrl+C, paste without comments.
- Permanent: `echo 'setopt interactivecomments' >> ~/.zshrc && source ~/.zshrc`

### Problem: `brew: command not found` after install
- Cause: install was still downloading or stopped early.
- Fix: rerun installer, wait for "Installation successful!" (or .pkg from github.com/Homebrew/brew/releases)
- Then: `eval "$(/opt/homebrew/bin/brew shellenv)"`
- /opt/homebrew = Apple Silicon (arm64) -> for AWS build with `--platform linux/amd64`

### Problem: brew cask docker "App already exists"
- Docker Desktop was already installed. Just `open -a Docker`.

### Problem: `failed to connect to the docker API ... docker.sock`
- Cause: Docker Desktop not running.
- Fix: `open -a Docker`, wait for whale icon, check `docker ps`

### Problem: API "Could not connect to the database"
- Cause: Postgres container not running (Docker was off). App retries 60s then exits.
- Fix: start Docker + pg container, `docker exec pg pg_isready -U docmind` before uvicorn
- Debug: `docker ps -a`, `docker logs pg`

### Not a problem: `GET /favicon.ico 404`
- Browser asks for a tab icon; app has none. Harmless.

### Problem: hidden files (.env, .gitignore) lost after moving folder
- Cause: `ls` and `mv *` skip dot-files.
- Fix: recreated them. Use `ls -a`; copy with `rsync -a src/ dest/`

### Problem: `echo "x" >> .gitignore` created a new one-line .gitignore
- `>>` creates the file if missing. Always `cat .gitignore` and confirm `.env` is listed BEFORE `git add .`

### Other notes
- No spaces in project paths -> moved to ~/projects/docmind
- A moved venv breaks; recreate it
- dump.rdb = Redis data file; never commit (in .gitignore)
- macOS RQ worker objc fork crash -> `export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES`

## Phase 1: Git + GitHub

### Setup
- `git config --global user.name / user.email / init.defaultBranch main`
- `brew install gh` + `gh auth login`
- `gh repo create docmind --public --source=. --remote=origin --push`

### Branch strategy
- main = protected, releases only (PR required)
- dev = integration
- feature/* = one branch per change -> PR into dev
- release = PR dev -> main, then annotated tag

### Daily loop
1. `git checkout dev && git pull`
2. `git checkout -b feature/<name>`
3. edit -> `git add` -> `git commit -m "type: msg"`
4. `git push -u origin feature/<name>`
5. `gh pr create --base dev --title "..." --body "..."`
6. `gh pr merge --merge --delete-branch`
7. `git checkout dev && git pull`

### Concepts
- Conventional commits: feat / fix / docs / ci / chore / test / refactor
- Fast-forward merge = no merge commit; merge commit = joins two histories
- Conflict: edit file, remove `<<<<<<<` `=======` `>>>>>>>`, then `git add` + `git commit`
- `git branch -d` "not found" = already deleted by `--delete-branch`
- `git fetch --prune` removes refs to branches deleted on GitHub
- Annotated tag: `git tag -a v0.1.0 -m "..."` + `git push origin v0.1.0`
- `gh release create v0.1.0 --title "v0.1.0" --notes "..."`
- `git reset --hard origin/main` discards local commits (dangerous)
- `git log --oneline --graph --decorate -10`

## Phase 2: Docker

### Files
- `Dockerfile` and `.dockerignore` live in the project root (next to requirements.txt)
- "the Dockerfile cannot be empty" = file not saved. Check with `wc -c Dockerfile`

### Dockerfile decisions
- Multi-stage: builder installs deps, final stage copies only /install -> smaller image
- COPY requirements.txt BEFORE app code -> pip layer is cached, rebuilds are fast
- python:3.12-slim base, non-root `appuser` (uid 10001)
- PYTHONUNBUFFERED=1 -> logs show immediately in `docker logs`
- uvicorn --host 0.0.0.0 (127.0.0.1 is unreachable from outside the container)
- HEALTHCHECK calls /health -> `docker ps` shows (healthy)
- ARG/ENV APP_VERSION -> CI will inject the git SHA
- .dockerignore excludes .env -> secrets never baked into the image

### Commands
- Build: `docker build -t docmind:dev .`
- Run all 4 on a network: `docker network create docmind-net`, then `--network docmind-net` on every run
- Containers reach each other by NAME (postgres, redis), not localhost
- Postgres/Redis need no `-p` (internal only); only the api gets `-p 8000:8000`
- `--env-file .env` loads secrets at runtime; `-e` overrides individual values
- Worker = same image + different command: `docmind:dev python -m app.worker`
- Volume for data: `-v pgdata:/var/lib/postgresql/data`

### Debugging
- `docker ps -a` (includes stopped), `docker logs -f <name>`
- `docker exec -it <name> sh` -> shell inside; type `exit` ALONE to leave ($ prompt = inside container)
- `docker inspect <name> --format '{{.State.Health.Status}}'`
- `docker stats --no-stream`
- `docker exec -it postgres psql -U docmind -c "select ..."`
- `docker exec -it redis redis-cli keys "*"`
- "container name already in use" -> `docker rm -f <name>`
- pg_isready "no response" right after start = still initializing, wait 5-10s

### Break-it results
- DB stopped: /ready = 503, /health = 200 -> K8s stops traffic, does not restart
- Deleted postgres container: data survived because of the volume
- DATABASE_URL with localhost: connection refused (localhost = the container itself)
- No GROQ_API_KEY: app starts, warns, /api/ask fails clearly
- Worker stopped: uploads stay "queued" in Redis, processed when worker returns

### Interview answers (write in my own words)
- Why requirements.txt first?
- Why multi-stage?
- Why 0.0.0.0?
- Why does the worker reuse the API image?
- Why pass the key at runtime?
- Container vs volume?

## Phase 3: Docker Compose + Docker Hub

### docker-compose.yml (project root)
- 4 services: postgres, redis, api, worker
- Compose creates the network automatically (docmind_default); services reach each other by service name
- Named volume `pgdata` -> actual name `docmind_pgdata` (project name prefix)
- `env_file: .env` loads secrets; `environment:` overrides individual values (DATABASE_URL, REDIS_URL point to service names)
- `depends_on: condition: service_healthy` waits for postgres/redis healthchecks before starting api/worker
- YAML anchor `x-app: &app` + `<<: *app` = shared config for api and worker, no copy-paste
- `restart: unless-stopped` = auto-restart on crash

### Commands
- `docker compose config` validate + show merged config (prints secrets, never share output)
- `docker compose up -d --build` build + start all
- `docker compose ps` / `logs -f [service]` / `exec <service> sh`
- `docker compose restart api` / `stop` / `start`
- `docker compose up -d --build api` redeploy only the api after code change
- `docker compose up -d --scale worker=3` scale workers (api cannot scale this way: port 8000 conflict)
- `docker compose down` removes containers + network, KEEPS volumes
- `docker compose down -v` ALSO DELETES VOLUMES = database wiped

### Lessons
- restart policy restarts CRASHED containers, not ones I stopped/killed manually
- "service is not running" on exec -> `docker compose up -d <service>` first
- Data survives `down` / `up` because of the named volume
- Separate worker service = can scale background jobs independently

### Docker Hub
- Login with a Personal Access Token, not the password: `docker login -u chetansatkar45`
- Mac is arm64, cloud is usually amd64 -> multi-arch build:
  `docker buildx build --platform linux/amd64,linux/arm64 --build-arg APP_VERSION=$SHA -t chetansatkar45/docmind:$SHA -t chetansatkar45/docmind:latest --push .`
- Verify: `docker buildx imagetools inspect chetansatkar45/docmind:$SHA`
- Tag with git SHA = know exactly which code is running + easy rollback. `latest` alone is ambiguous.

## Phase 4: CI with GitHub Actions

### File: .github/workflows/ci.yml
- Triggers: pull_request + push on dev/main, workflow_dispatch = manual button
- Jobs chained with `needs:` -> lint-and-test -> build-and-scan -> push (main only)
- `permissions: contents: read` = least privilege
- `concurrency` cancels outdated runs on the same branch
- pip cache + Docker layer cache (type=gha) = fast reruns
- `services:` gives the job real Postgres/Redis containers (like compose)
- Smoke test runs the BUILT IMAGE: upload doc, wait for ready, ask a question (LLM_PROVIDER=extractive, no key needed)
- `if: failure()` step prints container logs only when something broke
- Trivy scan fails on CRITICAL fixable CVEs (exit-code 1); "0" = report only
- push job only on main: multi-arch (QEMU + buildx), tags = full git SHA + latest

### Secrets
- `gh secret set NAME` stores encrypted secrets; values never shown again
- Used as ${{ secrets.NAME }}, masked as *** in logs
- PRs never push images, and CI needs no Groq key

### Commands
- `gh pr checks --watch` watch a PR's checks
- `gh run list` / `gh run watch` / `gh run view --log-failed`
- `actionlint` validates workflow YAML locally

### Branch protection
- Require status checks lint-and-test + build-and-scan on main AND dev
- Checks appear in the settings list only after they ran once

### Break-it results
- Unused import -> lint fails -> build skipped -> merge blocked
- Broken test -> pytest fails
- Dockerfile on wrong port -> lint/tests pass but smoke test fails (test the image, not just the code)

### Supply-chain security
- March 2026: attackers force-pushed 76/77 trivy-action tags to credential-stealing code
- Tags are mutable, SHAs are not -> pin third-party actions to full commit SHA with a version comment
- Dependabot (.github/dependabot.yml) proposes updates for actions and pip weekly

### Interview answers (write in my own words)
- CI vs CD?
- Why run a smoke test on the image if unit tests pass?
- Why does only main push images?
- How do secrets reach a workflow without being in the code?
- Why pin actions to a SHA?

## Phase 5: Kubernetes (kind) + Gateway API + HPA + Helm

### Cluster basics
- kind = k8s nodes as Docker containers: `kind create cluster --config k8s/kind-config.yaml`
- Docker Desktop needs >= 6 GB RAM
- `kubectl config set-context --current --namespace=X` = default namespace

### Errors I hit and fixes
- "namespaces X not found" -> create the Namespace first
- Secret created without -n landed in `default` -> pods only read Secrets in their own namespace
- `@` in password broke DATABASE_URL ("failed to resolve host '12345@postgres'") -> URL-encode (%40) or `openssl rand -hex 16`
- POSTGRES_PASSWORD only applies the first time the volume is initialized
- CreateContainerConfigError "non-numeric user (appuser)" -> runAsUser: 10001 + Dockerfile `USER 10001:10001`
- CrashLoopBackOff "redis Name or service not known" -> redis never deployed; `kubectl logs --previous`
- api `0/1 Running` = readiness failing -> out of the Service, not restarted
- k8s has no depends_on -> first-start "Connection refused" race; fix: restarts / retries / initContainer
- Groq AuthenticationError -> bad key in Secret; check prefix + length, test with curl, `kubectl patch secret ... stringData`, rollout restart
- Forgotten break-it (bad liveness path) = 73 restarts, 8h down unnoticed -> need monitoring + alerts
- curl `000` = nothing listening (port-forward dead / stopped with Ctrl+C / wrong tab)
- port-forward blocks its tab; it dies when the Mac sleeps or its pod is replaced
- psql pager `(END)` -> q or `-P pager=off`
- Helm "no template configmap.yaml associated" -> a template file was missing; check `ls -la templates/`
- Helm lint "mapping values are not allowed" -> `image: repo:` with empty tag; quote template output, lint with --set image.tag

### Concepts
- Deployment (stateless) vs StatefulSet (stable name + own PVC) for databases
- Headless Service (clusterIP: None) -> DNS straight to the pod
- envFrom ConfigMap + Secret; env read only at pod start
- Secrets are base64, NOT encrypted; never commit them
- startupProbe (slow start) / livenessProbe (restart when dead) / readinessProbe (remove from traffic)
- requests = scheduler reservation; over memory limit = OOMKilled (137); impossible request = Pending
- maxUnavailable 0 + maxSurge 1 = zero-downtime rollout; a bad image keeps old pods serving
- `rollout status / history / undo`; EndpointSlices = ready pods behind a Service
- ingress-nginx retired March 2026 -> Gateway API: GatewayClass -> Gateway -> HTTPRoute (Envoy Gateway)
- Gateway PROGRAMMED False on kind = no LoadBalancer; proxy works via port-forward
- HPA needs metrics-server (kind: --kubelet-insecure-tls); target % is of the CPU request

### Helm
- Chart = templates + values; values.yaml < values-<env>.yaml < --set
- `required` for image.tag (always the git SHA); Secrets stay outside the chart (existingSecret)
- `{{- if not autoscaling.enabled }} replicas` -> no fight with the HPA
- `checksum/config` annotation -> config change rolls pods automatically
- `helm lint` (with real values), `helm template`, `install / upgrade / history / rollback / get values / list -A`
- Rollback creates a NEW revision
- `helm diff upgrade` before every prod upgrade
- Helm can't adopt kubectl-created resources -> fresh namespaces
- Same chart -> docmind-dev (1 replica, DEBUG) and docmind-prod (HPA, INFO)
- Test zero downtime through the Gateway, not a port-forward to one pod

### Recreate after a new cluster (no secret values in git)
1. kind create cluster --config k8s/kind-config.yaml
2. helm install eg oci://docker.io/envoyproxy/gateway-helm --version v1.9.2 -n envoy-gateway-system --create-namespace
3. kubectl apply GatewayClass `eg` (from k8s/06-gateway.yaml)
4. helm install metrics-server ... --set "args={--kubelet-insecure-tls}"
5. kubectl create ns + secret docmind-secrets (POSTGRES_PASSWORD, DATABASE_URL, GROQ_API_KEY)
6. helm install docmind helm/docmind -n <ns> -f values-<env>.yaml --set image.tag=<sha>

## Phase 6: AWS (Free plan credits)

### Account safety
- Free plan: $100 + up to $100 credits for activities, 6 months, no charges
- Root = MFA only, never access keys; daily work as IAM user chetan-admin (group admins, MFA)
- Zero-spend budget alert on day 1 (also earned $20 credit)
- Region ap-south-1 (Mumbai); billing pages always show us-east-1 (global)
- CLI keys in ~/.aws/credentials (never in repo); describe access keys; rotate ~90 days
- IAM group names: letters/numbers/+=,.@_- only; paste can add invisible chars -> type by hand

### What I built
- ECR repo docmind (scan on push); copied the multi-arch image with `docker buildx imagetools create`
- EC2 (free-tier-eligible type) running k3s, Ubuntu 24.04 AMI from SSM Parameter Store
- Security group: 22 from my IP /32 only, 80 from anywhere, 6443 NEVER open -> SSH tunnel
- Elastic IP 43.204.223.233 (fixed address; costs a little; release at teardown)
- Node IAM role: ECR read-only + SSM managed instance (instance profile, IMDSv2 required)
- RDS Postgres 16 db.t4g.micro, private, SG source = k3s SG (not IP), sslmode=require, pgvector works
- Helm: same chart, values-aws.yaml (postgres.enabled=false, imagePullSecrets ecr-pull, HPA)
- Envoy Gateway on k3s: ServiceLB gives the Gateway the node IP -> PROGRAMMED True
- Public URL via nip.io: http://43.204.223.233.nip.io

### Keyless CD
- GitHub OIDC provider + role github-docmind-deploy
- Trust condition sub = repo:chetan1428/docmind:environment:aws (only that repo + environment)
- Permissions: push to one ECR repo, SendCommand to one instance (least privilege)
- GitHub environment `aws`: required reviewer (me) + only main branch; vars AWS_ROLE_ARN, APP_URL
- Job: configure-aws-credentials (1h creds) -> copy image to ECR -> SSM Run Command runs deploy/aws-deploy.sh -> verify /health shows the SHA
- deploy script: set -euo pipefail, IMDSv2 public IP, refresh ECR pull secret with node role, helm upgrade --install --wait

### Errors I hit and fixes
- SSH timed out -> instance stopped (new IP) or my home IP changed (SG rule)
- Same SSH fingerprint on new IP = same server (safe); different fingerprint = stop
- 127.0.0.1:6443 refused -> tunnel not running; use -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes
- `ubuntu@$IP]` stray bracket; PASTE_IP / <placeholders> typed literally
- RDS start error "not in stopped state" -> it was already starting
- SSM exit 127 "deploy/aws-deploy.sh: No such file" -> script was not committed+pushed; check `git ls-tree -r --name-only origin/<branch>`
- GitHub env variables 404 -> environment didn't exist yet (gh api -X PUT .../environments/aws)
- JMESPath: backticks = JSON literal (number), single quotes = string
- `<<'EOF'` literal vs `<<EOF` expands $VARS
- YAML pasted into zsh -> "command not found: uses:" (YAML goes in files)

### Cost habits
- End of session: helm uninstall (public app offline), stop EC2, stop RDS
- Stopped RDS auto-starts after 7 days
- Elastic IP costs even when the instance is stopped
- Check Billing -> Credits weekly
