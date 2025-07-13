# MVP Policy Decision Backend – Comprehensive Upgrade Path

> **Audience:** DevOps / Platform Engineers responsible for rolling upgrades of the `pd_prime_demo` FastAPI backend across environments (local → staging → production).
> 
> **Scope:** Covers application code, database schema, container images, CI/CD pipelines, security artefacts and observability. References:
> - `/migrations` SQL scripts & `alembic/versions/*`
> - `.coveragerc`
> - `.secrets.baseline`
> - `.trufflehogignore`
> - `alembic.ini`
> - `Dockerfile`
> - `Makefile`
> - `pyproject.toml`
> - `alembic/**`

---

## 1. Pre-Upgrade Checklist ✅

1. **Freeze current state**
   - Tag current Git SHA (`git tag pre-upgrade-$(date +%F)`).
   - Export DB schema & data (`pg_dump --schema-only`, `pg_dump --data-only`).
   - Capture current secrets baseline (`detect-secrets scan > pre_upgrade.baseline`).
2. **Smoke Test** – run `make test-cov` to ensure green baseline.
3. **Verify Coverage Budget** – `.coveragerc` mandates ≥ **80 %**; block if below.
4. **Security Gate** – run `make security`; ensure no new Bandit/BOM findings.
5. **Rehearse Migration** on a disposable DB clone.

---

## 2. Upgrade Sequence 🛠️

| # | Component | Action | Reference |
|---|-----------|--------|-----------|
| 1 | Python deps | `uv sync --frozen` (uses `pyproject.toml` & `uv.lock`) | `pyproject.toml` |
| 2 | Database   | Apply Alembic migrations **in order**:<br/>`001` → `002` → `003` → `004` → `005` → `006` → `007` → `008` → `009` | `alembic/versions/*` |
| 3 | Secrets    | Re-scan repo (`detect-secrets scan`) & update `.secrets.baseline` **only if new false-positives appear**. | `.secrets.baseline` |
| 4 | TruffleHog | Confirm ignore patterns still exclude docs/tests. Amend `.trufflehogignore` if paths changed. | `.trufflehogignore` |
| 5 | Coverage   | Adjust omit/include paths if new modules introduced. | `.coveragerc` |
| 6 | Docker     | Rebuild multi-stage image:<br/>`docker build -t pd_prime_demo:$(git rev-parse --short HEAD) .` | `Dockerfile` |
| 7 | Makefile   | Run `make validate` → gate on Pydantic, perf & master ruleset. Amend tasks if new scripts added. | `Makefile` |
| 8 | CI/CD      | Push tag/branch – GitHub Actions will:<br/>`pytest`, `ruff`, `mypy --strict`, build image, push to registry, run smoke deploy. | `.github/workflows/*` (implicit) |

---

## 3. Database Migration Details 📜

1. **Alembic configuration** (`alembic.ini`, `alembic/env.py`) now derives the connection string from `pd_prime_demo.core.config.get_settings()`.
2. **Offline vs Online**
   - **Offline:** `alembic upgrade head --sql > upgrade.sql` (review & run manually).
   - **Online (async):** `alembic upgrade head` (default in `start.sh`).
3. **Revision Map**
   1. `001_initial_schema.py` – customers → policies → claims
   2. `002_add_users_and_quote_system_tables.py`
   3. `003_add_rating_engine_tables.py`
   4. `004_add_security_compliance_tables.py`
   5. `005_add_real_time_analytics_tables.py`
   6. `006_add_admin_system_tables.py`
   7. `007_add_sso_integration_tables.py`
   8. `008_add_websocket_performance_tables.py`
   9. `009_add_missing_oauth2_tables.py` *(placeholder – implement before prod)*

> **Tip:** For each revision, ensure `update_updated_at_column()` trigger exists before dependent triggers run.

---

## 4. Runtime Upgrade (Container) 🚢

1. **Blue/Green Strategy** – deploy new pod set under `/v2` path, warm it up with health probes.
2. **Health Check** – relies on `GET /api/v1/health/live` exposed in `Dockerfile` `HEALTHCHECK`.
3. **Migration Hook** – `start.sh` auto-runs `alembic upgrade head` when `DATABASE_URL` is set.
4. **Rollback** – re-deploy previous image tag & `alembic downgrade -1` if schema breakage detected.

---

## 5. Post-Upgrade Validation 🔍

1. **End-to-End Tests** – `pytest -m integration`.
2. **Performance Budgets** – `make benchmark`; fail if > 5 % regression.
3. **Observability**
   - Check WebSocket metrics tables (`websocket_system_metrics`) for anomalies.
   - Verify `audit_logs` partitions created (monthly).
4. **Security Regression** – rerun Bandit, Semgrep, Safety, pip-audit.
5. **Data Retention** – confirm `data_retention_policies` meet compliance.

---

## 6. Rollback Plan 🔄

1. **Code** – re-deploy previous container tag.
2. **DB Schema** – `alembic downgrade <prev_revision>` *(ensure no irreversible DDL)*.
3. **Data Restore** – if needed, `pg_restore` from backup.
4. **Secrets** – revert baseline if mistakenly updated.

---

## 7. Troubleshooting 🆘

| Symptom | Likely Cause | Remedy |
|---------|--------------|--------|
| `alembic.util.exc.CommandError: Can't locate revision` | Skipped migration | `alembic history`, then `alembic upgrade <missing>` |
| `ModuleNotFoundError` at start-up | New dependency not in lockfile | `uv sync --frozen` in builder stage, rebuild image |
| Health check fails after deploy | DB migrations error | `kubectl logs`, inspect `start.sh` migration output |
| Coverage job fails (<80 %) | New code paths untested | Add unit tests, adjust `.coveragerc` only if deliberate |

---

## 8. Next Steps ➡️

1. Implement **`009_add_missing_oauth2_tables.py`** before production freeze.
2. Automate monthly partition creation for `audit_logs` via cron or pg_cron.
3. Schedule quarterly secret scans & baseline refresh.

Happy shipping! 🎉 

---

## 9. Enterprise-Grade Hardening Roadmap (Goal ≥ 90/100) 🧱

The checklist below closes every gap spotted in the 78 → 90+ reassessment.
Each item should be tackled in **sprints (S)** of ±2 weeks; dependencies noted.

| # | Theme | Deliverable | Tools / Tech | Sprint | Blockers |
|---|-------|-------------|--------------|--------|----------|
| 1 | **Infrastructure-as-Code** | Terraform / Pulumi modules for:<br/>• Railway service<br/>• Postgres (AWS RDS-MultiAZ) <br/>• Redis Cluster<br/>Commit under `infra/` with CI `terraform plan` gate | Terraform 1.8, CloudPosse modules, tfsec | S1-S2 | Finalize cloud vendor budget |
| 2 | **Container Security** | Add image scanning job (Trivy & Grype) to `security-monitoring.yml`; break build on `CRITICAL` vulns | Trivy, Grype | S1 | — |
| 3 | **Blue/Green & Canary** | Migrate deploy workflows to progressive rollout:<br/>1. Build image + push<br/>2. Deploy *green* replica set (`pd–v2`)<br/>3. 10 % traffic shift via Railway gradual routes<br/>4. Auto-promote on success; auto-rollback on 5xx spike | Railway Phased Deploy API or Argo Rollouts | S2-S3 | IaC foundation (row #1) |
| 4 | **Automated DB Migrations** | Separate GitHub Action step: `alembic upgrade head` via one-shot job before pod rollout; capture artefact `migrations.log` | Alembic, Railway Jobs | S3 | Blue/green infra |
| 5 | **High Availability** | • Postgres read-replica + `pgbouncer`<br/>• Redis Sentinel setup<br/>• Health probes + automatic fail-over runbook | AWS RDS, Redis 6.x Sentinel | S3-S4 | IaC foundation |
| 6 | **Disaster Recovery** | Automate PITR backups (`pgbackrest`), daily S3 snapshots, restore drills each quarter; document in `runbooks/` | pgBackRest, S3 Lifecycle | S4 | HA foundation |
| 7 | **Observability & Alerting** | Wire Prometheus exporters + Grafana dashboards; route alerts via PagerDuty (or OpsGenie) for:<br/>• p95 latency<br/>• error_rate>1 %<br/>• db_connections >85 %<br/>CI budgets already measured via Locust. | Prometheus Operator, Alertmanager, Grafana Cloud | S2-S3 | IaC foundation |
| 8 | **DAST & SCA** | Nightly OWASP ZAP spider + active scan against staging; push HTML report artefact; gate prod if `High` finding. | OWASP ZAP CLI | S4 | Staging endpoint stability |
| 9 | **Policy-as-Code** | Enforce runtime guardrails via OPA / Conftest: <br/>• Terraform plans must tag resources<br/>• Container images must be scanned<br/>Add `master-ruleset-enforcement.yml` step. | Open Policy Agent | S4 | IaC foundation |
| 10 | **Runbooks & Training** | Create `runbooks/` for:<br/>• On-call cheat-sheet<br/>• DB fail-over<br/>• Redis sentinel recovery<br/>• Rolling back bad migration<br/>Schedule quarterly game-days. | Markdown, Fire-Drill sessions | S5 | Completion of HA & DR items |

> ⚠️  **Scoring Model**: Each completed row roughly adds 2-4 points on the readiness index. Finishing rows #1-#6 pushes the system to ~92-95/100, while rows #7-#10 cement the score near 98.

### Suggested Execution Order

```
S1  ──► IaC foundation  &  Container scanning
S2  ──► Blue/Green rollout + Observability baseline
S3  ──► Automated migrations  &  HA database/redis
S4  ──► DR automation  &  DAST  &  Policy-as-Code
S5  ──► Runbooks, Chaos game-day, final audit
```

**Definition of Done for 90+**

1. All pipelines block on Trivy/Grype `CRITICAL` findings.
2. Terraform plan passes OPA policies and tfsec with 0 High issues.
3. Blue deployment receives 10 % traffic for ≥10 min with <0.1 % error rate.
4. Automated rollback tested (blue→green reversion + `alembic downgrade -1`).
5. Prometheus shows replication lag ≤5 s; fail-over drill <30 s API blip.
6. Quarterly ZAP scan report has 0 High, ≤2 Medium accepted with mitigation.

Once these KPIs hold for two consecutive releases, bump the readiness score and update this document header. 

---

## 10. Phase-Based Wave Plan (Extending Beyond Wave 3) 🚀

> These phases assume **the React/Vercel front-end is shipped first**. They reuse SAGE’s wave/agent orchestration rules (see `MASTER_INSTRUCTION_SET.md`) and the documentation pipeline (`00_SOURCE_DOCS_INSTRUCTION_SET.md`).  
> Each phase contains one or more **waves**.   *Wave N.x ⇒ 3-5 agents in parallel*.
>
> **Target scores after completion**
>
> | Dimension | Goal |
> |-----------|------|
> | Core Business Features | 100 |
> | Performance | 95-98 |
> | Security | 98-100 |
> | SOC 2 Compliance | 100 |
> | Observability & Monitoring (PostHog analytics) | 100 |
> | Scalability & HA | 95-100 |
> | Testing & Coverage | ≥ 90 |
> | CI/CD & Automation | 100 |
> | Documentation & Knowledge Base | ≥ 90 |
>
> Phases build **left-to-right** in the dependency graph below; arrows mark strict prerequisites.

```mermaid
flowchart LR
    subgraph Phase-4 "Feature Hardening"
        W4_1((4.1)) --> W4_2((4.2))
    end
    subgraph Phase-5 "Performance + Observability"
        W5_1((5.1)) --> W5_2((5.2))
    end
    subgraph Phase-6 "Security + SOC2"
        W6_1((6.1)) --> W6_2((6.2))
    end
    subgraph Phase-7 "Scalability + HA"
        W7_1((7.1)) --> W7_2((7.2))
    end
    subgraph Phase-8 "Docs + Knowledge"
        W8_1((8.1))
    end

    W4_2 --> W5_1
    W5_2 --> W6_1
    W6_2 --> W7_1
    W7_2 --> W8_1
```

### Phase 4 – Feature Hardening & Analytics

| Wave | Parallel Agents (3-5) | Key Files / Folders | Outcome |
|------|-----------------------|---------------------|---------|
| **4.1** | 1️⃣ **API Versioning Agent** → `src/pd_prime_demo/api/v2/*`  <br>2️⃣ **GraphQL Gateway Agent** → `src/pd_prime_demo/graphql/**`  <br>3️⃣ **Analytics Instrumentation Agent** → PostHog SDK hooks in middleware  <br>4️⃣ **Contract-Test Agent** → `tests/contracts/`  | ‑ V2 REST + GraphQL endpoints  <br>- Middleware emits PostHog events  <br>- Tavern/Pytest contract tests | Core Dimension = 90→95  <br>Observability seed  |
| **4.2** | 1️⃣ **Advanced Rating-ML Agent** → Rust model protos + Python FFI stub  <br>2️⃣ **Underwriting Rules Agent** → `services/underwriting/**`  <br>3️⃣ **Admin UI API Extensions Agent** → new endpoints in `/api/v1/admin/*`  <br>4️⃣ **Load-Gen Scenario Agent** → Locust scripts in `load_tests/`  <br>5️⃣ **Benchmark Harness Agent** → extend `pytest-benchmark` config | Rating engine vNext stub, underwriting logic, perf scenarios | Core Features 100  |

### Phase 5 – Performance & Observability

| Wave | Agents | Artifacts | Goal |
|------|--------|-----------|------|
| **5.1** | 1️⃣ **Rust Service Scaffold Agent** → `rust/services/quote_core/`  <br>2️⃣ **gRPC Gateway Agent** → `src/pd_prime_demo/grpc_gateway.py`  <br>3️⃣ **Prometheus Exporter Agent** → `/observability/exporters/**`  <br>4️⃣ **Grafana Dashboards Agent** → `observability/dashboards/*.json`  <br>5️⃣ **Perf-Budget Agent** → extend `performance-budget.yml` | First Rust microservice + telemetry | Perf 90→95, Observability 85→95 |
| **5.2** | 1️⃣ **DB Partitioning Agent** → migrations 010-012  <br>2️⃣ **PgBouncer/Pooler Agent** → Helm chart or Railway config  <br>3️⃣ **Query-Plan Optimizer Agent** → `core/admin_query_optimizer.py` refactor  <br>4️⃣ **Async-IO Profiler Agent** → `core/performance_monitor.py`  <br>5️⃣ **Chaos-Latency Test Agent** → k6 + tox suite | Sub-50 ms p95, p99 dashboards | Perf 95-98 |

### Phase 6 – Security & SOC 2

| Wave | Agents | Deliverables | Goal |
|------|--------|--------------|------|
| **6.1** | 1️⃣ **Rate-Limiter/WAF Agent** → `core/rate_limiter.py`, `infra/cloudflare_rules.yaml`  <br>2️⃣ **OPA Policy Agent** → `policy/opa/*.rego`  <br>3️⃣ **Secrets Rotation Agent** → Doppler script + CI hook  <br>4️⃣ **API Threat Model Agent** → `docs/SECURITY_THREAT_MODEL.md`  | Runtime protection, policies | Security 90→96 |
| **6.2** | 1️⃣ **DAST Pipeline Agent** → ZAP job in `security-monitoring.yml`  <br>2️⃣ **SOC2 Evidence Store Agent** → S3 bucket infra + `compliance/evidence_store.py`  <br>3️⃣ **Continuous Controls Agent** → cron job executing control framework  <br>4️⃣ **PKI Automation Agent** → ACME scripts for client certs  | Evidence automation, DAST gating | Security 98-100, SOC2 100 |

### Phase 7 – Scalability & High-Availability

| Wave | Agents | Output | Goal |
|------|--------|--------|------|
| **7.1** | 1️⃣ **Terraform Core-Infra Agent** → `infra/terraform/{network,db,redis}`  <br>2️⃣ **Kubernetes Helm-Chart Agent** → `deploy/helm/pd-prime-demo`  <br>3️⃣ **Argo Rollouts Agent** → canary YAMLs  <br>4️⃣ **Read-Replica Agent** → Terraform RDS replica, read router  | Infra codified, canary infra | Scalability 85→93 |
| **7.2** | 1️⃣ **Multi-Region Failover Agent** → Route53 / GLB config  <br>2️⃣ **Disaster-Recovery Automation Agent** → `runbooks/dr_restore.md` & scripts  <br>3️⃣ **Load-Test 10K->1M Agent** → locust-k8s manifest  <br>4️⃣ **Cost-Optimizer Agent** → Infracost diff job  <br>5️⃣ **Redis Sentinel Agent** → k8s stateful set  | RTO<30 s drills, 1 M QPS proof | Scalability/HA 95-100 |

### Phase 8 – Documentation & Knowledge Base

| Wave | Agents | Files | Goal |
|------|--------|-------|------|
| **8.1** | 1️⃣ **Runbook Author Agent** → `runbooks/*.md`  <br>2️⃣ **ADR Curator Agent** → `docs/architecture/adr/*.md`  <br>3️⃣ **Living Docs Sync Agent** → docs CI job (Serenity BDD, OpenAPI)  <br>4️⃣ **Pattern Library Agent** → `.sage/learned_patterns.json` enrichment  | Docs, KB, ADRs reach 90 + | Documentation 90 +

> After Phase 8 completion, all target scores are expected to meet or exceed goals.  The Rust migration of performance-critical paths can proceed as an independent track using the same SAGE wave protocol. 