# Troubleshooting runbook

Three failures that really happen in Kubernetes deployments, each with a broken manifest, the fix, and how to get from one to the other. They run in their own namespace, `shelfwise-lab`, because Argo CD would undo any break in `shelfwise` within a minute.

```bash
kubectl apply -f troubleshooting/namespace.yaml
kubectl apply -f troubleshooting/01-image-pull/broken.yaml     # one scenario at a time, or all three
...
kubectl delete namespace shelfwise-lab                          # clean up afterwards
```

## First five minutes of any incident

Start broad and narrow down. Each command answers one question.

| Question | Command |
|---|---|
| Which pods are unhappy? | `kubectl get pods -n <ns>` (look at READY, STATUS and RESTARTS) |
| What does Kubernetes say happened? | `kubectl get events -n <ns> --sort-by=.lastTimestamp` |
| Why is this pod stuck? | `kubectl describe pod <pod> -n <ns>` (read the Events at the bottom) |
| What did the app say? | `kubectl logs <pod> -n <ns>` (add `--previous` after a crash) |
| Does the Service reach any pod? | `kubectl get endpointslices -n <ns> -l kubernetes.io/service-name=<svc>` |
| Do labels match selectors? | `kubectl get pods -n <ns> --show-labels` vs. `kubectl get svc <svc> -o yaml` |

STATUS tells you which layer to look at:

| What you see | Layer | Usual causes |
|---|---|---|
| `Pending` | Scheduling | Not enough CPU/memory, unbound PVC, node selector/taint |
| `ErrImagePull` / `ImagePullBackOff` | Image | Wrong name or tag, private registry without credentials |
| `CrashLoopBackOff` | Process | App exits on start: bad config, missing env, failing migration |
| `Running` but `0/1` READY | Readiness | App up but a dependency (database, API) is unreachable |
| `Running 1/1` but no traffic | Networking | Service selector or port mismatch, NetworkPolicy, Ingress rule |

---

## 1. ImagePullBackOff: the tag does not exist

**Break it:** `kubectl apply -f troubleshooting/01-image-pull/broken.yaml`

**Symptom**

```text
NAME                             READY   STATUS             RESTARTS
catalogue-api-854c7c5655-8jfhj   0/1     ImagePullBackOff   0
```

**Investigate**

```bash
kubectl describe pod -n shelfwise-lab -l app=catalogue-api | grep -A3 "Failed"
#  Failed to pull image "ghcr.io/aanviiii/shelfwise-backend:sha-0000000": ... not found
```

The kubelet reached the registry and the repository exists, but this tag doesn't. `BackOff` means it keeps retrying with growing delays, so nothing fixes itself.

**Root cause:** `sha-0000000` was never built. In this project every image is tagged with the commit it came from, so the tag must match a commit whose pipeline pushed images (see the Actions run summary or GHCR).

**Fix:** `kubectl apply -f troubleshooting/01-image-pull/fixed.yaml`, which points at a tag CI actually pushed. The Deployment rolls new pods and the old ones go away.

**Prevent it:** The real app is never deployed by hand-typing tags. Argo CD Image Updater only picks tags matching `^sha-[0-9a-f]{7}$` that exist in GHCR, and rollouts use `maxUnavailable: 0`, so a bad image can't take the running version down.

---

## 2. Service with no endpoints: selector typo

**Break it:** `kubectl apply -f troubleshooting/02-service-selector/broken.yaml`

**Symptom:** The pods are `Running 1/1`, yet anything calling `library-web` times out.

```bash
kubectl get endpointslices -n shelfwise-lab -l kubernetes.io/service-name=library-web
# ENDPOINTS: <unset>          (no pod addresses behind the Service)
```

**Investigate:** Compare what the Service selects with what the pods carry.

```bash
kubectl get svc library-web -n shelfwise-lab -o jsonpath='{.spec.selector}'
# {"app":"libary-web"}
kubectl get pods -n shelfwise-lab --show-labels | grep library-web
# ... app=library-web
```

**Root cause:** A Service finds pods by label, not by name. `libary-web` matches nothing, so the Service has no endpoints, and nothing errors or warns about it.

**Fix:** `kubectl apply -f troubleshooting/02-service-selector/fixed.yaml`. The endpoints appear immediately, with no pod restart, because only the Service changed.

**Prevent it:** The Helm chart builds every selector and pod label from one helper (`shelfwise.selector`), so they can't drift apart, and CI renders the chart and validates it with kubeconform.

---

## 3. Running but never Ready: the database rejects the app

**Break it:** `kubectl apply -f troubleshooting/03-readiness/broken.yaml`

**Symptom**

```text
NAME                           READY   STATUS    RESTARTS
lab-backend-7487b6b665-wmtb4   0/1     Running   0
```

No restarts, so the process is healthy, but it never joins the Service.

**Investigate**

```bash
kubectl describe pod -n shelfwise-lab -l app=lab-backend | grep Readiness
#  Readiness probe failed: HTTP probe failed with statuscode: 503
kubectl exec -n shelfwise-lab deploy/lab-backend -- python -c \
  "import urllib.request as u; print(u.urlopen('http://localhost:8000/health').read())"
#  b'{"status":"UP"}'        (liveness is fine, so this is not a crash)
```

`/health` (liveness) answers, while `/ready` (readiness) returns 503 `{"database": "unreachable"}`. That split is deliberate: a database problem shouldn't make Kubernetes restart healthy app pods in a loop, but it should stop sending them traffic.

**Root cause:** The `database-url` in the Secret has the wrong password. Postgres is fine; it refuses the login.

**Fix**

```bash
kubectl apply -f troubleshooting/03-readiness/fixed.yaml
kubectl rollout restart deployment/lab-backend -n shelfwise-lab
```

The restart is needed because environment variables from a Secret are only read when a container starts.

**Prevent it:** In the real chart, the pod template carries a checksum of the Secret, so changing credentials rolls the pods automatically. On EKS the password is generated by `eks-up.ps1` and never typed by hand.

---

## Clean up

```bash
kubectl delete namespace shelfwise-lab
```
