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
