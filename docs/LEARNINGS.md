# Learnings

- Docker Desktop must be running, else: cannot connect to docker.sock
- macOS system python is 3.9; LangChain 1.x needs 3.10+ (used conda env with 3.12)
- zsh does not treat # as a comment when pasting; apostrophes open a quote> prompt
- Homebrew install must finish fully; then run brew shellenv
<<<<<<< HEAD
- Note from branch A
=======
- Note from branch B
>>>>>>> feature/b

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
