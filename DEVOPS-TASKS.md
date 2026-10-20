# Your DevOps Tasks

The app is done. Everything below is for you to build **by hand**. Each level has a goal, a "done when" check, and hints, but no solutions. Write every file yourself.

Rule: **do it manually once before you automate it.** Keep a `docs/LEARNINGS.md` with every error you hit and how you fixed it.

---

## Level 0: Git

- [ ] `git init`, first commit, push to a new GitHub repo
- [ ] Branches: `main` (protected), `dev`, `feature/*`
- [ ] Protect `main`: PR required, status checks must pass (once CI exists)
- [ ] Conventional commits (`feat:`, `fix:`, `ci:`, `chore:`), tag `v0.1.0`
- [ ] Practice: create a merge conflict on purpose and resolve it. Try `rebase -i`, `cherry-pick`, `revert`, `stash`.

**Done when:** every later change in this list arrives on `main` through a PR.

---

## Level 1: Docker

- [ ] `Dockerfile` for the app. **One image** runs both the API and the worker, with a different command for each.
- [ ] Multi-stage build, slim base, non-root user, `.dockerignore`
- [ ] A `HEALTHCHECK` that uses `/health`
- [ ] Run Postgres and Redis containers by hand with `docker run` and a user-defined network, then run the API and worker containers against them

**Hints**
- Run with `LLM_PROVIDER=extractive` first so a missing key can't confuse your debugging; add the Groq key once everything is up
- uvicorn must listen on `0.0.0.0` inside a container, not `127.0.0.1`
- Plain `postgres` has no pgvector. Look at `pgvector/pgvector:pg16`.
- Containers talk to each other by container name on a user-defined network, not via `localhost`
- Pass config with `-e` / `--env-file`. Never `COPY .env` into the image.

**Done when:** you can upload `samples/kubernetes-basics.md` in the browser and get an answer. Bonus: the image is under 300 MB (`docker images`).

---

## Level 2: Docker Compose

- [ ] `docker-compose.yml` with `api`, `worker`, `postgres`, `redis`
- [ ] Named volume for Postgres data, `depends_on` with `condition: service_healthy`
- [ ] Healthchecks on every service
- [ ] Push the image to Docker Hub, tagged with **both** the version and the git short SHA

**Done when:** `docker compose up -d`, then `docker compose down`, then `up` again, and your documents are still there.

---

## Level 3: CI (GitHub Actions)

- [ ] On every PR: `ruff check`, `ruff format --check`, `pytest`
- [ ] Build the Docker image (no push) on PRs, and scan it with Trivy
- [ ] On merge to `main`: build and push, with the tag = git SHA, passing `APP_VERSION=<sha>` into the image
- [ ] Use Docker layer caching to speed up builds
- [ ] Make these checks **required** in branch protection

**Done when:** a PR with a lint error is blocked, and merging produces a new image tag in the registry.

---

## Level 4: Kubernetes, local (kind or minikube)

Write raw YAML first. **No Helm yet.**

- [ ] `Namespace`
- [ ] `ConfigMap` (non-secret settings, including `GROQ_MODEL`) and `Secret` (`DATABASE_URL`, `GROQ_API_KEY`)
- [ ] Postgres as a `StatefulSet` + `PersistentVolumeClaim` + headless `Service`
- [ ] Redis `Deployment` + `Service`
- [ ] API `Deployment` (2 replicas) + `Service`
- [ ] Worker `Deployment`: same image, different command, **no Service** (think about why)
- [ ] `livenessProbe` on `/health`, `readinessProbe` on `/ready`
- [ ] Resource `requests` and `limits` on every container
- [ ] `Ingress` with ingress-nginx
- [ ] `HorizontalPodAutoscaler` for the API (needs metrics-server)

**Break it on purpose and debug each failure with `kubectl describe / logs / get events / exec`:**
- [ ] Wrong image tag (`ImagePullBackOff`)
- [ ] Wrong `DATABASE_URL` (what happens to readiness? to liveness?)
- [ ] Kill Redis. Watch the API pods drop out of the Service while they stay running.
- [ ] Set a tiny memory limit (`OOMKilled`)
- [ ] Delete the Postgres pod. Does your data survive?
- [ ] `kubectl rollout undo` after a bad deploy

**Then:** turn your YAML into a **Helm chart** with a separate `values-dev.yaml` and `values-prod.yaml`.

**Done when:** `helm install` gives you a working app at your Ingress host, and `helm upgrade` with a new image tag does a zero-downtime rolling update.

---

## Level 5: AWS (console first, then CLI, then Terraform)

- [ ] **Day 1: set a billing alarm** (e.g., $10). Create an IAM user for yourself and stop using root.
- [ ] VPC with public and private subnets across 2 AZs
- [ ] ECR repository; push your image there
- [ ] RDS PostgreSQL 16 in the private subnets (it supports the `vector` extension)
- [ ] ElastiCache Redis, or keep Redis in-cluster to save money
- [ ] Store `DATABASE_URL` and `GROQ_API_KEY` in Secrets Manager or SSM Parameter Store
- [ ] Cluster: **EKS** (the industry standard, but the control plane costs money every hour, so tear it down after each session) **or k3s on one EC2 instance** (cheap, still real Kubernetes)
- [ ] AWS Load Balancer Controller for the Ingress, or a NodePort + security group on k3s
- [ ] Optional: Route 53 domain + ACM certificate for HTTPS

**Hints**
- Pods pull from ECR using IAM (node role or IRSA / Pod Identity), not stored passwords
- RDS security group: allow 5432 **only** from the cluster's security group

**Done when:** the app works on a public URL, backed by RDS, and you can explain every security group rule.

**Then:** rebuild the whole thing with **Terraform** and an S3 state backend. `terraform destroy` should leave nothing billable behind.

---

## Level 6: CD

Pick one, then try the other:
- [ ] **Push-based:** GitHub Actions authenticates to AWS with **OIDC** (no access keys in GitHub secrets), then runs `helm upgrade --set image.tag=$SHA`
- [ ] **GitOps:** install **ArgoCD**. CI only updates the image tag in a `deploy/` folder or repo, and ArgoCD syncs the cluster.

- [ ] Separate `dev` and `prod` environments, with a manual approval step before prod (GitHub Environments)

**Done when:** merging a PR changes what `/health` reports in the cluster (it shows the new SHA) without you running any command.

---

## Level 7: Bonus

- [ ] Prometheus + Grafana (kube-prometheus-stack) scraping `/metrics`; dashboard of request rate, p95 latency, errors
- [ ] Autoscale the **worker** on Redis queue length with KEDA
- [ ] Database migrations with Alembic as a Kubernetes `Job` / Helm pre-upgrade hook (instead of `create_all` on startup)
- [ ] Sync `GROQ_API_KEY` from AWS Secrets Manager with External Secrets Operator, then rotate it with zero downtime
- [ ] Change `GROQ_MODEL` through the ConfigMap only (no image rebuild) and roll the pods
- [ ] Turn on LangSmith tracing in one environment only, via config
- [ ] Add an `/api/ask` rate limit at the Ingress so nobody burns your Groq quota
- [ ] Store uploaded files in S3 instead of the DB, and access it with an IAM role, not keys
- [ ] Canary or blue-green deploys with Argo Rollouts
- [ ] Image signing with cosign; SBOM generation

---

## Resume line, once done

> Built and deployed **DocMind**, a agentic RAG service (LangGraph, Groq LLM, FastAPI, pgvector, Redis/RQ workers) on **AWS EKS** with **Helm**, **GitHub Actions CI** (lint, tests, Trivy scan), **OIDC-based CD / ArgoCD GitOps**, RDS, HPA autoscaling and Prometheus/Grafana monitoring; infrastructure provisioned with **Terraform**.

Only claim the parts you actually built.
