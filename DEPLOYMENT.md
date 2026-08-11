# Deployment Next Steps

How to take this demo from a local Docker image to a hosted environment **anywhere**, using containers plus IaC (**Terraform** and/or **Rancher/Kubernetes**), or the **$0 Hugging Face Space** path.

Current artifacts already in the repo:

| Artifact | Purpose |
|---|---|
| [`gradio_app.py`](gradio_app.py) | HF Space Gradio entry (ChatInterface + scoped agent) |
| [`requirements-space.txt`](requirements-space.txt) | Slim deps for Gradio/HF (Spaces also install [`requirements.txt`](requirements.txt)) |
| [`Dockerfile`](Dockerfile) | Production-shaped image (seed SQLite → Uvicorn `:8000`) |
| [`docker-compose.yml`](docker-compose.yml) | Local / single-host demo |
| [`scripts/entrypoint.sh`](scripts/entrypoint.sh) | Seeds DB if missing; **1 worker** (required for in-memory chat) |
| App health | `GET /health` (`database_ready`, `chat_ready`) |
| Demo UI | FastAPI `GET /` or Gradio Space |

---

## $0 public URL — Hugging Face Space + Inference Providers

**Recommended cheapest shareable demo.** Free CPU Space runs Gradio only; the LLM runs on HF Inference Providers (separate free monthly credit).

```text
Browser → Gradio on free CPU Space → scoped tool loop + SQLite
                                   → HF Inference Providers (Qwen2.5-7B-Instruct)
```

### Deploy checklist

1. Create a **public Gradio Space** (hardware: CPU basic — no credit card).
2. **Settings → Secrets** → add `HF_TOKEN` (HF access token with permission to call Inference Providers).
3. **Settings → Variables** (optional):
   - `LLM_PROVIDER=hf` (also the default in `gradio_app.py`)
   - `HF_MODEL=Qwen/Qwen2.5-7B-Instruct`
   - `HF_PROVIDER=auto`
4. Push this git repo to the Space remote (README YAML sets `sdk: gradio`, `app_file: gradio_app.py`).
5. Wait for the build; open `https://huggingface.co/spaces/<user>/<space>`.
6. Smoke test:
   - Directory question (e.g. cardiologist in Cluj who speaks English)
   - Follow-up turn (multi-turn history via Gradio)
   - Out-of-scope refusal (e.g. weather / medical advice)

### Local Gradio before push

```bash
pip install -r requirements-space.txt
export LLM_PROVIDER=hf
export HF_TOKEN=hf_xxx
python scripts/seed_db.py
python gradio_app.py
```

### Notes

- SQLite is seeded on first Space boot from `healthcare_data.json` (~3MB in repo).
- Do **not** load the model onto the Space CPU — inference is remote via `huggingface_hub.InferenceClient`.
- Free Inference credit is small; fine for demos. Upgrade to PRO or pay-as-you-go if you hit limits.
- Entry file is `gradio_app.py` (not `app.py`) so it does not collide with the Python package directory `app/`.
- FastAPI/Docker path remains available with `LLM_PROVIDER=openai`.

---

## Constraints that drive every deploy

1. **Single replica / single worker** — conversation history is in-process memory. Do not set Uvicorn `--workers > 1` or run multiple replicas behind a load balancer unless you add sticky sessions or external session store.
2. **Secrets** — `OPENAI_API_KEY` must come from a secret store (never bake into the image). Optional: `OPENAI_MODEL`, `OPENAI_BASE_URL` (only if using a compatible gateway; leave unset otherwise).
3. **SQLite** — fine for demo. Prefer a **persistent volume** at `/app/data` so restarts do not re-seed unnecessarily. For HA/multi-node, migrate off SQLite later.
4. **Outbound HTTPS** — the container must reach the OpenAI-compatible API.
5. **No auth in app** — put the demo behind a private network, VPN, IP allowlist, or edge basic-auth / SSO.

---

## Phase 0 — Prove the image (any host)

```bash
# 1. Build
docker build -t healthcare-agent:demo .

# 2. Run locally
docker run --rm -p 8000:8000 \
  -e OPENAI_API_KEY \
  -e OPENAI_MODEL=gpt-4o-mini \
  healthcare-agent:demo

# 3. Smoke
curl -fsS http://127.0.0.1:8000/health
open http://127.0.0.1:8000
```

Pass criteria: `database_ready: true`, `chat_ready: true`, multi-turn chat works in the UI.

---

## Phase 1 — Publish the container (required for IaC)

Pick a registry (GHCR, ECR, GCR/Artifact Registry, Docker Hub, Harbor on Rancher).

```bash
export REGISTRY=ghcr.io/<org>          # or account.dkr.ecr.<region>.amazonaws.com
export IMAGE=$REGISTRY/healthcare-agent
export TAG=$(git rev-parse --short HEAD)

docker build -t "$IMAGE:$TAG" -t "$IMAGE:latest" .
docker push "$IMAGE:$TAG"
docker push "$IMAGE:latest"
```

**Next step in-repo:** add CI (GitHub Actions) that builds/pushes on `main` and prints the digest for Terraform/Rancher to pin.

Suggested workflow responsibilities:

- build + scan image
- push `$IMAGE:$GIT_SHA` and optionally `:latest`
- (optional) open a PR that bumps the image tag in Terraform/Helm values

---

## Phase 2A — Terraform path (cloud VM or managed container)

Use Terraform when you want cloud resources declared as code without operating a full cluster.

### Recommended first Terraform target (simplest “anywhere”)

**Single VM + Docker** (AWS EC2 / Azure VM / GCP Compute Engine):

| Resource | Purpose |
|---|---|
| VPC / security group | Allow `80/443` in; egress HTTPS out |
| VM | Runs Docker Engine |
| cloud-init / user-data | `docker pull` + `docker run` with env from secret |
| DNS + TLS | Route53/Cloud DNS + Caddy/nginx or cloud LB cert |
| Secret | SSM Parameter Store / Secrets Manager / Key Vault |

**Why this first:** matches the current single-container, single-worker model with almost no app changes.

### Alternative Terraform targets (same image)

| Target | When to choose |
|---|---|
| **AWS ECS Fargate** + ALB | Want managed containers, no SSH |
| **Google Cloud Run** | Want scale-to-zero public demo (keep `max instances = 1` for session affinity) |
| **Azure Container Apps** | Same as Cloud Run on Azure |
| **Kubernetes via Terraform** (`kubernetes` / `helm` providers) | You already have a cluster (see Phase 2B) |

### Terraform layout to add next

```text
infra/terraform/
  versions.tf
  providers.tf
  variables.tf
  main.tf            # network + compute/service
  secrets.tf         # reference to OPENAI_API_KEY (not the value)
  outputs.tf         # public_url, image_uri
  environments/
    demo.tfvars
```

### Terraform checklist

1. Create `infra/terraform/` with provider for your cloud.
2. Parameterize `image_uri`, `openai_model`, `desired_count = 1`.
3. Inject `OPENAI_API_KEY` from the cloud secret store at runtime.
4. Mount or attach durable storage for `/app/data` (EBS, Azure Disk, GCS fuse only if needed — a local disk/volume is enough for demo).
5. Health check path: `/health` on port `8000` (or via reverse proxy on `443`).
6. `terraform plan` → `terraform apply` → smoke `/` and `/chat`.
7. Lock state in remote backend (S3+DynamoDB, Terraform Cloud, azurerm storage, GCS).

### Minimal runtime contract for Terraform modules

```hcl
# Conceptual — values every module must honor
desired_count        = 1
container_port       = 8000
healthcheck_path     = "/health"
env = {
  OPENAI_MODEL = "gpt-4o-mini"
  DATABASE_URL = "sqlite:////app/data/healthcare.db"
}
# OPENAI_API_KEY from secret ARN / Key Vault reference — never tfvars plaintext in git
```

---

## Phase 2B — Rancher path (Kubernetes)

Use Rancher when you already run (or want) Kubernetes: RKE2, K3s, EKS/AKS/GKE imported into Rancher.

### Workload shape

| K8s object | Setting |
|---|---|
| `Deployment` | `replicas: 1` |
| Container port | `8000` |
| Probes | HTTP `GET /health` |
| `Secret` | `OPENAI_API_KEY` |
| `PersistentVolumeClaim` | Mount at `/app/data` |
| `Service` | ClusterIP `8000` |
| `Ingress` | TLS hostname → Service (nginx / Traefik / Rancher Istio) |

### Manifest / Helm layout to add next

```text
infra/k8s/
  namespace.yaml
  secret.example.yaml      # template only — real secret via Rancher/External Secrets
  pvc.yaml
  deployment.yaml          # replicas: 1, image: $IMAGE:$TAG
  service.yaml
  ingress.yaml
  kustomization.yaml       # or chart under infra/helm/healthcare-agent/
```

### Rancher UI / GitOps checklist

1. Import or provision cluster in Rancher.
2. Create project/namespace `healthcare-demo`.
3. Create Secret `healthcare-agent-openai` with key `OPENAI_API_KEY`.
4. Deploy from:
   - Rancher **App** (Helm chart), or
   - **Continuous Delivery (Fleet)** pointing at `infra/k8s` / Helm chart, or
   - `kubectl apply -k infra/k8s`.
5. Configure Ingress hostname + cert-manager / Rancher-generated cert.
6. Verify: Ingress URL loads demo UI; `/health` shows `chat_ready: true`.
7. Pin image digest/tag in Git; promote by PR (do not rely on mutable `:latest` in prod-like demos).

### Deployment snippet (reference)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: healthcare-agent
spec:
  replicas: 1
  strategy:
    type: Recreate   # avoid two pods sharing one SQLite PVC
  template:
    spec:
      containers:
        - name: api
          image: REGISTRY/healthcare-agent:TAG
          ports:
            - containerPort: 8000
          env:
            - name: OPENAI_API_KEY
              valueFrom:
                secretKeyRef:
                  name: healthcare-agent-openai
                  key: OPENAI_API_KEY
            - name: OPENAI_MODEL
              value: gpt-4o-mini
            - name: DATABASE_URL
              value: sqlite:////app/data/healthcare.db
          volumeMounts:
            - name: data
              mountPath: /app/data
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: healthcare-agent-data
```

`Recreate` strategy matters: SQLite + a single PVC must not be mounted by two writers.

---

## Phase 3 — Hardening before a wider audience

Do these after the first public URL works:

| Priority | Item |
|---|---|
| P0 | OpenAI billing/credits working; monitor 429s |
| P0 | Edge TLS + restrict who can hit the demo |
| P1 | Image scanning in CI; pin digests in Terraform/Helm |
| P1 | Structured logs + request IDs; uptime check on `/health` |
| P2 | Replace in-memory conversations (Redis) if you need multi-replica |
| P2 | Replace SQLite with Postgres if you need multi-node writes |
| P2 | Rate limits on `/chat` to control LLM spend |
| P3 | Auth (SSO / magic link) if the demo leaves a private network |

---

## Choosing Terraform vs Rancher

| Choose **Terraform (VM / ECS / Cloud Run)** when… | Choose **Rancher / K8s** when… |
|---|---|
| You want the fastest path to one demo URL | You already operate Kubernetes |
| Ops team prefers cloud services over clusters | You need GitOps (Fleet), shared ingress, many apps |
| Single container is enough | You expect to grow into more services on the same cluster |

**Practical recommendation for this repo today:**  
1) publish image → 2) Terraform **single VM + Docker** *or* Cloud Run/ECS with `max/desired = 1` → 3) graduate to Rancher/K8s only if the org standard is Kubernetes.

---

## Ordered backlog (do in this order)

### Path A — $0 HF Space + Vercel MCP client

1. [x] HF Space: https://huggingface.co/spaces/robcr/clinician-directory-agent
2. [x] MCP Streamable HTTP: `https://robcr-clinician-directory-agent.hf.space/gradio_api/mcp/`
3. [x] Vercel TS client in [`web/`](web/) — deploy with Root Directory `web`
4. [ ] Optional: rename the Vercel project and set custom domain

### Path B — Docker + cloud IaC

1. [ ] Confirm local `docker compose up` demo with a funded `OPENAI_API_KEY`
2. [ ] Create container registry + push `$IMAGE:$GIT_SHA`
3. [ ] Add CI build/push workflow
4. [ ] **Either** scaffold `infra/terraform/` for chosen cloud **or** scaffold `infra/k8s/` (or Helm) for Rancher
5. [ ] Store `OPENAI_API_KEY` in cloud/Rancher secrets (rotate any key that was shared in chat)
6. [ ] Apply IaC / deploy; attach PVC or disk at `/app/data`
7. [ ] Point DNS + TLS at the service
8. [ ] Smoke: `/health`, UI multi-turn, out-of-scope refusal
9. [ ] Add uptime monitor + budget alerts on LLM usage
10. [ ] (Optional) Redis sessions + Postgres when you outgrow single-replica SQLite

---

## Related docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — runtime architecture and demo constraints
- [README.md](README.md) — local runbook
