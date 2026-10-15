# Submission: rubric → evidence

Every criterion from the course's GRADING.md, where it is implemented, and the screenshot that proves it. All screenshots are real captures of the running system: browser windows show the address bar, and terminal windows show the exact command that was run.

**Repository:** https://github.com/Aanviiii/DevOps-project · **Author:** Aanvi Solanki (every commit authored and committed by `Aanviiii`)

---

## M1 · Application: Frontend + Backend + Database (10)

| Criterion | Where | Evidence |
|---|---|---|
| FastAPI backend starts and answers `/health` | [`backend/app/routers/system.py`](../backend/app/routers/system.py) | [m4-compose-up.png](evidence/m4-compose-up.png), [m1-swagger.png](evidence/m1-swagger.png) |
| ≥4 REST endpoints (GET, POST, PUT, DELETE) | 25 operations: [`routers/`](../backend/app/routers/) (books, members, loans, holds, stats) | [m1-swagger.png](evidence/m1-swagger.png) |
| PostgreSQL with tables managed by Alembic | [`alembic/versions/0001_initial.py`](../backend/alembic/versions/0001_initial.py), [`0002_fines_and_open_loan_index.py`](../backend/alembic/versions/0002_fines_and_open_loan_index.py) | [m1-postgres-tables.png](evidence/m1-postgres-tables.png) (4 tables, revision 0002) |
| React frontend renders and calls the API | [`frontend/src/`](../frontend/src/) | [m1-app-catalogue.png](evidence/m1-app-catalogue.png), [m1-app-desk.png](evidence/m1-app-desk.png), [m1-app-holds.png](evidence/m1-app-holds.png), [m1-app-member-account.png](evidence/m1-app-member-account.png), [m1-app-insights.png](evidence/m1-app-insights.png) |
| Responsive, usable UI | [`styles/`](../frontend/src/styles/) | [m1-app-mobile.png](evidence/m1-app-mobile.png), [m1-app-insights-dark.png](evidence/m1-app-insights-dark.png) |

## M2 · Testing (10)

| Criterion | Where | Evidence |
|---|---|---|
| `pytest` runs without errors | [`backend/tests/`](../backend/tests/) | [m2-pytest.png](evidence/m2-pytest.png): **111 passed, 98% coverage** |
| ≥5 tests over ≥3 endpoints | 111 tests across every endpoint, plus pure-rule, migration and seed tests | same |
| Test database, not production | [`tests/conftest.py`](../backend/tests/conftest.py): in-memory SQLite set before import, fresh schema per test, frozen clock | same |
| `pytest.ini` / `conftest.py` | [`backend/pytest.ini`](../backend/pytest.ini), [`backend/tests/conftest.py`](../backend/tests/conftest.py) | n/a |

## M3 · Git and GitHub (5)

| Criterion | Where | Evidence |
|---|---|---|
| Public repository | https://github.com/Aanviiii/DevOps-project | n/a |
| Meaningful commit messages | One commit per task, each with a body explaining *why*. The feature in PR #1 went test-first. | [m3-commit-history.png](evidence/m3-commit-history.png), [m3-pull-request.png](evidence/m3-pull-request.png) |
| `.gitignore` covers `.env`, `__pycache__`, `node_modules`, `.venv` | [`.gitignore`](../.gitignore) (also Terraform state, `*.tfvars`, keys) | n/a |

## M4 · Docker (10)

| Criterion | Where | Evidence |
|---|---|---|
| Backend Dockerfile builds | [`backend/Dockerfile`](../backend/Dockerfile) (multi-stage, Alpine, no pip at runtime) | [m4-compose-up.png](evidence/m4-compose-up.png) |
| Frontend multi-stage (Node → nginx) | [`frontend/Dockerfile`](../frontend/Dockerfile) | same |
| Non-root images | UIDs 10001 (backend), 101 (nginx), 10002 (activity) | [m4-non-root.png](evidence/m4-non-root.png) |
| `docker compose up --build` starts all three | [`docker-compose.yml`](../docker-compose.yml) (healthcheck-ordered, read-only containers) | [m4-compose-up.png](evidence/m4-compose-up.png), [m4-compose-browser.png](evidence/m4-compose-browser.png) |

## M5 · CI/CD (15)

| Criterion | Where | Evidence |
|---|---|---|
| Workflow present | [`.github/workflows/pipeline.yml`](../.github/workflows/pipeline.yml) | [m5-pipeline-green.png](evidence/m5-pipeline-green.png) |
| Triggers on push to `main` | `on: push: branches: [main]` (and PRs) | same |
| pytest runs and fails the build | `backend` job; `images` needs it | [m5-pipeline-gate-failed.png](evidence/m5-pipeline-gate-failed.png): failing tests skip every image job |
| Frontend built in the pipeline | `frontend` job | [m5-pipeline-green.png](evidence/m5-pipeline-green.png) |
| Images built for frontend and backend | `images` matrix (backend, frontend, activity) | same |
| Pushed to GHCR | `docker/build-push-action`, with SBOM and provenance | [m5-ghcr-packages.png](evidence/m5-ghcr-packages.png) |
| SHA tags, not `latest` | `sha-<7>` and the full SHA | [m5-ghcr-backend-tags.png](evidence/m5-ghcr-backend-tags.png) |

Extra gates in the same pipeline: ruff lint and format (with bandit rules), a 90% coverage floor, `helm lint` + kubeconform against Kubernetes 1.35, `terraform fmt` + `validate`, and gitleaks over the full Git history. **Delivery** is GitOps: Argo CD Image Updater picks up each new SHA tag and Argo CD rolls it out (see M10).

## M6 · DevSecOps: Trivy (5)

| Criterion | Where | Evidence |
|---|---|---|
| Trivy scans backend and frontend in CI | "Trivy gate" step in the `images` job, for all three images | [m6-trivy-pipeline-log.png](evidence/m6-trivy-pipeline-log.png) |
| Fails on HIGH/CRITICAL | `severity: HIGH,CRITICAL`, `exit-code: "1"`, before any push | same |
| Explanation | below | n/a |

**What Trivy scanned and what the result means.** On every build, Trivy inspects each image in two layers: the OS packages of the Alpine 3.24 base (29 apk packages for the backend) and every installed language library (each Python package in the backend's virtualenv). It also looks for secrets baked into the layers. The result is **0 HIGH or CRITICAL vulnerabilities**. That isn't luck: the runtime images are deliberately minimal (multi-stage builds, no compiler, no pip or Node, no package caches), so there is very little attack surface for CVEs to land on. A clean scan means no *known* fixable high-severity issue at build time, not that the image is "secure". That's why the pipeline re-scans on every commit, Dependabot proposes base-image and dependency updates weekly, and findings from MEDIUM up are uploaded to the GitHub Security tab for review.

## M7 · Terraform on AWS (15)

Provisioned for real on **AWS account 419701112200** (Free plan, paid from its credits), then destroyed the same day. The Free plan shaped three choices, recorded honestly here:
- **Region.** The account is limited to **Sydney (`ap-southeast-2`)**; every other region is denied by AWS's service control policy ([m7-account-blocked.png](evidence/m7-account-blocked.png) shows the Mumbai attempt). The region is a single Terraform variable, so the same code targets any region.
- **No Spot.** Spot launches are denied on the Free plan, so `node_capacity_type = "ON_DEMAND"`.
- **Free Tier instance types only.** A first apply with `t3.medium` nodes stalled: AWS refused the launches with *"not eligible for Free Tier"*. The node group was removed and re-created on **`m7i-flex.large`** (2 vCPU, 8 GiB, Free Tier eligible). That is why the apply screenshot shows the final 5 resources: the other 19 were created by the first run.

| Criterion | Where | Evidence |
|---|---|---|
| Valid HCL in `terraform/` | [`terraform/`](../terraform/): plain resources, no modules | CI job "Terraform · fmt and validate" in [m5-pipeline-green.png](evidence/m5-pipeline-green.png) |
| `terraform init` succeeds | n/a | [m7-terraform-plan.png](evidence/m7-terraform-plan.png) |
| `terraform plan` non-empty, no errors | n/a | [m7-terraform-plan.png](evidence/m7-terraform-plan.png): **24 to add** in `ap-southeast-2` |
| VPC with ≥2 public subnets | [`network.tf`](../terraform/network.tf) | [m7-aws-console-vpc.png](evidence/m7-aws-console-vpc.png) (`shelfwise-vpc`, 10.42.0.0/16), [m7-terraform-apply.png](evidence/m7-terraform-apply.png) (VPC id and subnet outputs) |
| EKS with a worker node group | [`cluster.tf`](../terraform/cluster.tf), [`nodes.tf`](../terraform/nodes.tf) | [m7-aws-console-eks.png](evidence/m7-aws-console-eks.png) (Active, 1.35), [m7-eks-kubectl.png](evidence/m7-eks-kubectl.png) (2 Ready nodes, app running) |
| `terraform destroy` clean | [`scripts/eks-down.ps1`](../scripts/eks-down.ps1) | [m7-terraform-destroy.png](evidence/m7-terraform-destroy.png) |
| `terraform.tfvars.example`, no credentials | [`terraform.tfvars.example`](../terraform/terraform.tfvars.example); gitleaks in CI | n/a |

The app was also deployed onto this cluster with [`scripts/eks-up.ps1`](../scripts/eks-up.ps1) (ingress-nginx behind an AWS load balancer, a random database password, the Helm chart, and `helm test` passing). See [m8-eks-ingress-browser.png](evidence/m8-eks-ingress-browser.png).

Cost-conscious design (no NAT gateway, standard-support pin, budget alert) is explained in [terraform/README.md](../terraform/README.md).

## M8 · Kubernetes + Helm (15)

| Criterion | Where | Evidence |
|---|---|---|
| `k8s/namespace.yaml` applies | [`k8s/namespace.yaml`](../k8s/namespace.yaml) (restricted Pod Security) | [m8-kubectl-get.png](evidence/m8-kubectl-get.png) |
| Helm chart with Chart, values, templates | [`helm/shelfwise/`](../helm/shelfwise/) | n/a |
| `helm upgrade --install` deploys | n/a | [m8-helm-upgrade-install.png](evidence/m8-helm-upgrade-install.png) (with `helm test` passing) |
| Backend and frontend ≥2 replicas | HPA `minReplicas: 2` | [m8-kubectl-get.png](evidence/m8-kubectl-get.png) |
| ClusterIP Services | [`backend.yaml`](../helm/shelfwise/templates/backend.yaml), [`frontend.yaml`](../helm/shelfwise/templates/frontend.yaml) | [m8-kubectl-get.png](evidence/m8-kubectl-get.png) |
| Ingress `/` → frontend, `/api` → backend | [`ingress.yaml`](../helm/shelfwise/templates/ingress.yaml) | [m8-kubectl-get.png](evidence/m8-kubectl-get.png); the app through `shelfwise.local` in [m1-app-catalogue.png](evidence/m1-app-catalogue.png), and on **AWS EKS** through its load balancer in [m8-eks-ingress-browser.png](evidence/m8-eks-ingress-browser.png) |
| All pods Running | n/a | [m8-kubectl-get.png](evidence/m8-kubectl-get.png) |
| `helm list` | n/a | [m8-kubectl-get.png](evidence/m8-kubectl-get.png), [m8-helm-upgrade-install.png](evidence/m8-helm-upgrade-install.png) |
| HPA | [`autoscaling.yaml`](../helm/shelfwise/templates/autoscaling.yaml) | [m8-hpa-scaling.png](evidence/m8-hpa-scaling.png): 2 → 6 replicas under k6 load |

## M9 · Observability (10)

| Criterion | Where | Evidence |
|---|---|---|
| `/metrics` in Prometheus format | [`app/metrics.py`](../backend/app/metrics.py) | [m9-metrics-endpoint.png](evidence/m9-metrics-endpoint.png) |
| Prometheus scraping the app | [`monitoring/`](../monitoring/), [`monitoring.yaml`](../helm/shelfwise/templates/monitoring.yaml) | [m9-prometheus-targets.png](evidence/m9-prometheus-targets.png): 2/2 UP |
| Grafana installed and reachable | `grafana.shelfwise.local` | [m9-grafana-dashboard.png](evidence/m9-grafana-dashboard.png) |
| Panel with live metrics | 11 panels (requests, latency, errors, library state, HPA, CPU) | [m9-grafana-dashboard.png](evidence/m9-grafana-dashboard.png), [m9-grafana-hpa-cpu.png](evidence/m9-grafana-hpa-cpu.png) |
| Alerting (beyond the rubric) | 5 PrometheusRules | [m9-prometheus-alerts.png](evidence/m9-prometheus-alerts.png), [m9-prometheus-alerts-under-load.png](evidence/m9-prometheus-alerts-under-load.png) (pending under load) |

## M10 · Presentation + documentation (5)

| Criterion | Where | Evidence |
|---|---|---|
| README explaining the application | [README.md](../README.md), [ARCHITECTURE.md](ARCHITECTURE.md) | n/a |
| Live demo: commit → pipeline → deployment updates | [DEMO.md](DEMO.md) | the recorded sequence below |

The live demo, captured end to end:

1. [m10-1-before.png](evidence/m10-1-before.png): the catalogue header and the running version (`sha-fa06b22`) before the change.
2. [m10-2-commit-and-push.png](evidence/m10-2-commit-and-push.png): a one-line UI change, committed and pushed.
3. [m10-3-pipeline-running.png](evidence/m10-3-pipeline-running.png), then [m10-4-pipeline-green.png](evidence/m10-4-pipeline-green.png): the pipeline for that commit.
4. [m10-5-argocd-rollout.png](evidence/m10-5-argocd-rollout.png): Image Updater moves the Application to the new SHA, and the Deployments roll with no manual step.
5. [m10-6-after.png](evidence/m10-6-after.png): the new text is live, and the sidebar shows the new commit's SHA.
6. [m10-argocd-app-tree.png](evidence/m10-argocd-app-tree.png): Argo CD Synced and Healthy, tracking `main`.

## Troubleshooting lab

[troubleshooting/RUNBOOK.md](../troubleshooting/RUNBOOK.md): each scenario broken and then fixed on the live cluster. [ImagePullBackOff](evidence/troubleshooting-1.png) · [Service without endpoints](evidence/troubleshooting-2.png) · [Running but not Ready](evidence/troubleshooting-3.png)
