
<div align="center">

<img width="150" height="150" alt="image" src="https://github.com/user-attachments/assets/f7a7e8dd-6cc7-4384-8c4d-eb746f4f7331" />



# Telegram Downloader Bot (`tg-downloader-bot`)

![CI/CD Pipeline](https://img.shields.io/github/actions/workflow/status/k5sha/tg-downloader-bot/ci.yaml?style=for-the-badge&logo=githubactions&logoColor=white&label=CI%2FCD)
[![Python Version](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://docs.aiogram.dev/)
[![Kubernetes](https://img.shields.io/badge/Orchestration-K3s-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white)](https://k3s.io/)
[![Traefik](https://img.shields.io/badge/Ingress-Traefik-24A1DE?style=for-the-badge&logo=traefik&logoColor=white)](https://traefik.io/)
[![Cloudflare WAF](https://img.shields.io/badge/Protection-Cloudflare_WAF-F38020?style=for-the-badge&logo=cloudflare&logoColor=white)](https://www.cloudflare.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)
</div>

## The bot 🤖

A lightweight, high-performance Telegram bot designed for asynchronous media downloading and webhook processing. Built with **Python 3.11+**, **aiogram 3.x**, and **aiohttp**, and engineered for cloud-native deployment on **Kubernetes / K3s** using **Traefik Ingress** and **Cloudflare Edge Security**.

## Features ⚙️

* **Asynchronous Core:** Non-blocking request handling powered by `aiogram` and `aiohttp`.
* **Cloud-Native Design:** Containerized for Kubernetes environments with native `livenessProbe` and `readinessProbe` support via `/healthz`.
* **Hardened Security Context:** Operates in unprivileged mode with `readOnlyRootFilesystem`, dropped capabilities, and dedicated non-root UID `1001`.
* **Edge-First Security:** Protection against scanners and unauthorized payloads using Cloudflare WAF IP filtering and Telegram `WEBHOOK_SECRET` header verification.

## Architecture Overview 🎯

```text
  [ Telegram API ]
         │ (HTTPS)
         ▼
[ Cloudflare WAF ] ──(Blocks non-Telegram IPs)
         │
         ▼
 [ Traefik Ingress ] ──(Routes /tg-bot/webhook)
         │
         ▼
   [ K3s Service ]
         │
         ▼
 [ tg-bot Container ] ──(Validates X-Telegram-Bot-Api-Secret-Token)

```

1. **Telegram API** sends updates via HTTPS to `[https://api.k5sha.com/tg-bot/webhook](https://api.k5sha.com/tg-bot/webhook)`.
2. **Cloudflare WAF** validates the incoming IP address against official Telegram CIDR ranges (`149.154.160.0/20`, `91.108.4.0/22`), dropping all other traffic at the network edge.
3. **Traefik Ingress Controller** terminates TLS and routes traffic inside the K3s cluster.
4. **aiogram Webhook Handler** verifies the secret token header (`X-Telegram-Bot-Api-Secret-Token`) and executes downloading tasks asynchronously using `/tmp` ephemeral storage.

## Environment Variables

| Variable | Description | Example / Default |
| --- | --- | --- |
| `WEB_SERVER_HOST` | Bind address for the internal HTTP server | `0.0.0.0` |
| `WEB_SERVER_PORT` | Port for the internal HTTP server | `8080` |
| `BASE_WEBHOOK_URL` | Public domain exposed to Telegram | `https://api.k5sha.com` |
| `WEBHOOK_PATH` | Path endpoint for update delivery | `/tg-bot/webhook` |
| `BOT_TOKEN` | API Token retrieved from `@BotFather` | `123456789:ABC...` |
| `WEBHOOK_SECRET` | Secret key used to verify Telegram origin | Mounted from K8s Secret |


## Security Model 🔐

Security is enforced through a two-layer defense strategy:

### 1. Cloudflare WAF (Edge Protection)

Because the ingress sits behind Cloudflare Proxy (Orange Cloud), enforcing IP whitelisting at the Traefik level can result in proxy IP mismatches. Filtering traffic at the Cloudflare Edge prevents unauthorized requests from ever reaching the cluster.

Create a **Custom Rule** in **Cloudflare Dashboard -> Security -> WAF -> Custom rules**:

* **Rule Name:** `Allow Telegram Webhook Only`
* **Expression:**
```text
(starts_with(http.request.uri.path, "/tg-bot/webhook") and not ip.src in {149.154.160.0/20 91.108.4.0/22})

```


* **Action:** `Block`

### 2. Secret Token Verification (Application Layer)

The bot application validates every incoming request against `WEBHOOK_SECRET`. Unauthenticated requests matching the route are immediately rejected with `401 Unauthorized` by `aiogram`.

 
## Deployment Configuration ([Full source](https://github.com/k5sha/k5sha-gitops/tree/main/manifests/tg-bot)) ⚙️

Example Kubernetes manifest (`deployment.yaml`):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tg-bot
  namespace: tg-bot
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: tg-bot
  template:
    metadata:
      labels:
        app: tg-bot
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1001
        fsGroup: 1001
      containers:
      - name: bot
        image: ghcr.io/k5sha/tg-downloader-bot:latest
        securityContext:
          readOnlyRootFilesystem: true
          allowPrivilegeEscalation: false
          capabilities:
            drop:
              - ALL
        ports:
        - name: http
          containerPort: 8080
        env:
        - name: WEB_SERVER_HOST
          value: "0.0.0.0"
        - name: WEB_SERVER_PORT
          value: "8080"
        - name: BASE_WEBHOOK_URL
          value: "https://api.k5sha.com"
        - name: WEBHOOK_PATH
          value: "/tg-bot/webhook"
        - name: BOT_TOKEN
          valueFrom:
            secretKeyRef:
              name: tg-bot-secrets
              key: bot_token
        - name: WEBHOOK_SECRET
          valueFrom:
            secretKeyRef:
              name: tg-bot-secrets
              key: webhook_secret
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 15
        readinessProbe:
          httpGet:
            path: /healthz
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        volumeMounts:
        - name: tmp
          mountPath: /tmp
      volumes:
      - name: tmp
        emptyDir: {}

```


## Health Checks & Diagnostics 🧑‍⚕️

### 1. Inspect Webhook Status via Telegram API

Query the official Telegram API endpoint to verify delivery status and queue backlogs:

```bash
curl -s "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo" | jq .
```

**Key Response Diagnostics:**

* **`pending_update_count`**: Number of queued updates. Values greater than `0` indicate processing timeouts or server errors.
* **`last_error_message`**:
* `403 Forbidden`: Cloudflare WAF or Traefik is blocking Telegram IP ranges.
* `Wrong response from webhook`: Application runtime errors or unhandled exceptions.
* `Connection timed out`: Media downloading task blocked the event loop for longer than 5 seconds.



### 2. Verify Container Health Privately

Test the application instance inside the cluster (bypassing external routing and WAF):

```bash
kubectl port-forward -n tg-bot svc/tg-bot 8080:80
```

In another terminal window:

```bash
curl -i http://127.0.0.1:8080/healthz
# Expected output: HTTP/1.1 200 OK
```
