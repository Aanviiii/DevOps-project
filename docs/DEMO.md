# Live demo script (about 12 minutes)

Follows the order the course asks for: application → Git → CI → image → scan → registry → Terraform → Kubernetes → Helm → Ingress → autoscaling → monitoring → troubleshooting.

## Before the session (10 minutes, not on camera)

```powershell
# Docker Desktop running, then:
./scripts/up-local.ps1                      # cluster, Argo CD, monitoring, app
minikube tunnel                             # in a separate *Administrator* terminal, leave it open
```

Open these tabs:

| Tab | URL |
|---|---|
| App | http://shelfwise.local |
| Argo CD | http://argocd.shelfwise.local (admin / password printed by `up-local.ps1`) |
| Grafana | http://grafana.shelfwise.local, dashboard *Shelfwise · Library service* |
| Prometheus | http://prometheus.shelfwise.local/targets |
| GitHub | the repository's Actions tab, and Packages |

To read the logins again:

```powershell
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | % { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_)) }
kubectl -n monitoring get secret monitoring-grafana -o jsonpath="{.data.admin-password}" | % { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_)) }
```

## 1. The application (2 min)

1. **Catalogue**: search "data", filter by a genre, point at "2 of 3 on shelf" and "All out · 2 holds".
2. **Circulation desk**: lend a book to a member. Then try to lend a book that is all out: the toast explains `No copies are available. Place a hold…` (a lending rule, HTTP 409).
3. **Holds**: show the FIFO queue and the "collect by" deadline.
4. **Members**: open an account and show the tier policy, books out, fines and *Record payment*.
5. **Insights**: KPIs and the 14-day chart (hover a column).
6. API docs: `kubectl port-forward -n shelfwise svc/shelfwise-backend 8000:8000`, then http://localhost:8000/docs → try `GET /api/stats`.
7. Database: `kubectl exec -n shelfwise shelfwise-postgres-0 -- psql -U shelfwise -c "\dt"` and `-c "select count(*) from loans"`.

## 2. Commit → pipeline → deployment, live (4 min)

Make a visible change. For example, in `frontend/src/components/Layout.jsx` change

```jsx
            <small>Library desk</small>
```

to

```jsx
            <small>Library desk · open till 8 pm</small>
```

```powershell
git add frontend/src/components/Layout.jsx
git commit -m "Show the library's closing time under the logo"
git push
```

While it runs, narrate the stages in the Actions tab:
- **Quality gates in parallel:** lint + 111 tests (≥90% coverage), frontend build, Helm lint + kubeconform, Terraform validate, gitleaks.
- **Images:** build → **Trivy gate** (open the step: the table shows 0 HIGH/CRITICAL) → push `sha-xxxxxxx` to GHCR.
- **GitHub Packages:** the new tag next to the older ones, never `latest`.

Then in Argo CD (about 1 minute after the push finishes): the Application's `image.tag` parameter changes, and pods roll one by one (`maxUnavailable: 0`, so the app never goes down).

```powershell
kubectl get pods -n shelfwise -w            # old pods terminate as new ones become Ready
```

Refresh the app: the new text shows, and the sidebar footer reads `Frontend sha-xxxxxxx` with the commit you just pushed.

## 3. Infrastructure as code (1.5 min)

- Walk through `terraform/`: `network.tf` (VPC, two public subnets, no NAT and why), `cluster.tf`, `nodes.tf` (Spot), `budget.tf`.
- Show the screenshots of `terraform plan`, the AWS console (VPC + EKS) and `terraform destroy` in [SUBMISSION.md](SUBMISSION.md#m7--terraform-aws-infrastructure-as-code). The cluster is only up during a dedicated session, to keep costs near zero.

## 4. Kubernetes, Helm, Ingress (1.5 min)

```powershell
kubectl get pods,svc,ingress,hpa -n shelfwise
helm list -A                                # monitoring, argocd, image updater
helm test shelfwise -n shelfwise --logs     # only if the chart was installed with Helm directly (EKS)
```

Point out two replicas per tier, ClusterIP Services, and the Ingress routing `/` and `/api`. Mention that pods run non-root with read-only filesystems and that the namespace enforces the *restricted* Pod Security profile.

## 5. Autoscaling (1.5 min)

```powershell
kubectl apply -f scripts/load-test.yaml
kubectl get hpa -n shelfwise -w             # CPU climbs past 60%, replicas 2 → 4+
```

In Grafana, the "Backend pods: HPA current vs desired" and "CPU per pod" panels move. Clean up with `kubectl delete -f scripts/load-test.yaml`; it scales back after a minute.

## 6. Monitoring (1 min)

- Prometheus **Targets**: `shelfwise-backend` endpoints are UP. **Alerts**: the five Shelfwise rules.
- Grafana dashboard: requests per route, p95 latency, error ratio, circulation activity, refusals by reason (`NOT_AVAILABLE`, `LOAN_LIMIT`, …), library gauges.
- `curl http://localhost:8000/metrics | findstr shelfwise_` (with the port-forward from step 1).

## 7. Troubleshooting (1 min)

```powershell
kubectl apply -f troubleshooting/namespace.yaml
kubectl apply -f troubleshooting/02-service-selector/broken.yaml
kubectl get pods -n shelfwise-lab                         # Running 1/1…
kubectl get endpointslices -n shelfwise-lab               # …but no endpoints
kubectl get svc library-web -n shelfwise-lab -o jsonpath="{.spec.selector}"
kubectl apply -f troubleshooting/02-service-selector/fixed.yaml
kubectl delete namespace shelfwise-lab
```

Mention the other two scenarios in [RUNBOOK.md](../troubleshooting/RUNBOOK.md).

## After the session

```powershell
./scripts/down-local.ps1          # stop minikube (or -Delete)
```

If EKS was used: `./scripts/eks-down.ps1`, then confirm in the AWS console that nothing tagged `Project = shelfwise` remains.
