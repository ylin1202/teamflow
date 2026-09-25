# Teamflow

This project is a full-stack, multi-tenant team collaboration and project management SaaS platform. It uses a modern distributed microservices architecture — a Next.js (App Router) + NextAuth frontend, and a backend built on Django REST Framework, RabbitMQ + Celery for asynchronous task queues, Redis for distributed caching/locking, and MySQL as the relational database. It natively implements UUIDv7 index optimization, row-level multi-tenant isolation, a simulated Stripe one-time-purchase and quota control system, and a webhook service backed by Redis distributed anti-concurrency locks with database-level idempotency checks.

## Highlights

* **Multi-Tenant Architecture**: Complete row-level tenant data isolation and automatic routing based on the `X-Organization-ID` header.
* **High-Performance UUIDv7 Keys**: All tables use time-ordered UUIDv7 primary keys, balancing B-Tree index write performance with non-enumerable security.
* **Stripe Billing & Quota Engine**: Integrates Stripe Checkout one-time purchase plans (test environment), dynamically validating project and member quota limits per plan.
* **Distributed Webhook Resilience**: Combines Redis distributed locks with a `StripeEventLog` database table for dual-layer idempotency protection, preventing payment race conditions.
* **Asynchronous Queue**: Uses RabbitMQ as the message broker driving Celery workers to asynchronously process team invitation emails and subscription upgrade notifications, with exponential backoff retry.
* **Granular RBAC Security**: OWNER / ADMIN / MEMBER role hierarchy protecting team assets.
* **Decoupled Markdown Specs & Kanban**: Modular task board and a real-time technical spec document rendering/editing module.
* **Dockerized Microservices**: Fully containerized orchestration of MySQL, Redis, RabbitMQ, Celery Worker, Django, and Next.js.

## Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | Next.js · TypeScript · Tailwind CSS · Lucide React | User dashboard, Kanban board, and multi-tenant state management |
| **State & Auth** | Zustand · NextAuth (Google OAuth) · Axios Interceptor | Tenant context switching, OAuth route guarding, and automatic header injection |
| **Backend API** | Django · Django REST Framework · django-allauth | Core RESTful API, RBAC permission checks, and tenant-scoped viewsets |
| **Message Broker** | RabbitMQ 3 (Management) | Message broker relay (AMQP protocol) |
| **Task & Worker** | Celery | Asynchronous email delivery, task retry, and scheduling |
| **Cache & Lock** | Redis 7 (Alpine) | Distributed webhook lock (`lock:stripe_event:*`) and caching |
| **Database** | MySQL | Relational database, UUIDv7, indexing, and transactional consistency |
| **Payment Gateway** | Stripe API (Checkout & Webhooks) | One-time plan purchases, checkout sessions, and payment auditing |
| **Deployment** | Docker · Docker Compose | Multi-container service orchestration and environment isolation |

## System Architecture

```
                               +------------------------------------------+
                               |         Client Browser (Next.js)         |
                               |------------------------------------------|
                               | • NextAuth Google OAuth & Middleware     |
                               | • Zustand Multi-Tenant Workspace Store   |
                               | • KanbanBoard & MarkdownSpecs Modules    |
                               +--------------------+---------------------+
                                                    |
                                            X-Organization-ID
                                                    |
                                                    v
+-----------------------+      +------------------------------------------+      +-----------------------+
|  Stripe Billing API   |<---->|         Django Backend (DRF API)         |<---->|         MySQL         |
|-----------------------|      |------------------------------------------|      |-----------------------|
| • Checkout Sessions   |      | • TenantBaseViewSet (Row Isolation)      |      | • saas_organization   |
| • Webhook Dispatcher  |      | • StripeWebhookService (Idempotency)     |      | • saas_project / task |
+-----------------------+      | • Signal: Auto Workspace Provisioning    |      | • UUIDv7 PK Indices   |
                               +---------+----------------------+---------+      +-----------------------+
                                         |                      |
                            Redis Lock   |                      | AMQP Tasks
                                         v                      v
                        +----------------------+      +----------------------+
                        |        Redis         |      | RabbitMQ Message Bus |
                        |----------------------|      |----------------------|
                        | • Distributed Lock   |      | • AMQP Broker (5672) |
                        |   (lock:stripe_event)|      | • Management (15672) |
                        +----------------------+      +----------+-----------+
                                                                 |
                                                                 v
                                                      +----------------------+
                                                      |    Celery Worker     |
                                                      |----------------------|
                                                      | • send_invitation    |
                                                      | • send_subscription  |
                                                      +----------------------+
```

## Data Flow: Webhook Idempotency

Checkout sessions can only be created by an organization Owner. After payment completes, the backend verifies the signature via the Stripe webhook secret, then uses a Redis distributed lock combined with the `StripeEventLog` table to guarantee event idempotency, preventing duplicate plan upgrades or task dispatches. Notifications are finally sent asynchronously via Celery.

```
         Stripe Event Trigger (e.g. checkout.session.completed)
                                │
                                ▼
                   Stripe Signature Verification
                       (stripe.Webhook.construct_event)
                                │
                                ▼
                  Redis Distributed Lock Acquisition
                        (lock:stripe_event:<id>)
                                │
                                ▼
                 Event Idempotency & Replay Check
                     (StripeEventLog exists?)
                                │
                                ▼
                 MySQL 8.0 Subscription Update
                  (Update Plan, Quota & Status)
                                │
                                ▼
                     RabbitMQ (AMQP Protocol)
                                │
                                ▼
                     Celery Background Worker
                                │
                                ▼
                     Asynchronous Welcome Email
```

## Performance Benchmark & Async Decoupling

For high-latency third-party I/O (such as SMTP handshakes and email delivery), the system decouples this work from the synchronous HTTP request-response cycle by offloading it to Celery workers.

Benchmarked with k6 in the same Docker environment (simulating 30 concurrent virtual users continuously hitting `/api/invitations/` for 20 seconds):

| **Metric** | **Before: Synchronous Blocking I/O** | **After: Celery + RabbitMQ Async Decoupling** | **Improvement** |
|-----------------------|-------------------------------------------:|----------------------------------------:|------------------|
| **Average Latency** | 836.73 ms | 73.20 ms | **91.3% reduction** |
| **P95 Tail Latency** | 856.99 ms | 111.20 ms | **87.0% reduction** |
| **Throughput** | 33.06 req/s | 242.43 req/s | **7.33x increase (+633%)** |
| **Total Requests Processed** | 690 | 4,868 | **7.05x increase** |
| **Success Rate** | 100% | 100% | **Zero errors maintained** |

### Distributed Concurrency Protection & Idempotency Validation (Stripe Webhook Concurrency Guard)

To defend against race conditions caused by payment gateway retries and transient network failures, the system combines a **Redis distributed lock (60s TTL)** with a **`StripeEventLog`** database status check:

* **Stress & Boundary Testing**: Used 50 concurrent threads to send Stripe webhook events with the same `event_id` within the same millisecond.
* **Results**:
  * **Redis Lock Interception**: Of 50 concurrent requests, **49 were precisely blocked by the Redis lock**, with only **1** acquiring the lock and proceeding to the database update.
  * **Database Consistency**: The final `StripeEventLog` count was strictly maintained at `count = 1`, with no duplicate plan upgrades or redundant task dispatches.
  * **Reliability Guarantee**: Achieved **100% idempotency (zero duplicate processing)** and atomic state transitions.

## Core Engineering Highlights

### Distributed Payment Protection & Idempotency Design
* **Redis Distributed Lock**: A 60-second expiring lock prevents race conditions triggered by short-interval Stripe retries.
* **Dual-Layer Idempotency Audit**: Before writing data, a `StripeEventLog` status check is performed; if already processed (`PROCESSED`), the event is safely skipped.
* **Transactional Safety**: `transaction.atomic()` and `transaction.on_commit()` ensure consistency between tenant plan upgrades and Celery welcome-email dispatch.

### UUIDv7 Time-Ordered Primary Key Architecture
* All models inherit from `BaseModel`, using `uuid6.uuid7()` as the default primary key — retaining the non-enumerable, distributed-safety benefits of traditional UUIDs while significantly reducing B-Tree index page splits thanks to time-ordering.

### Multi-Tenant Isolation Base
* Automatically parses the `X-Organization-ID` request header and enforces organization boundaries in `get_queryset()` and `perform_create()`, ensuring zero cross-tenant data leakage.

### Quota Limits & Tiered Plan Management
* Free Tier: up to 5 projects, 3 team members.
* Pro Plan: up to 25 projects, unlimited members.
* Enterprise Plan: up to 150 projects, unlimited members.
* Quota limits are automatically enforced when creating projects and sending invitations.

## Repository Structure

```
├── backend/                              # Django core backend
│   ├── config/                           # Project configuration module
│   │   ├── __init__.py
│   │   ├── asgi.py                       # ASGI entry point
│   │   ├── celery.py                     # Celery app init & task discovery
│   │   ├── settings.py                   # Global settings
│   │   ├── urls.py                       # Root URL routing
│   │   └── wsgi.py                       # WSGI entry point
│   ├── core/                             # SaaS core business logic
│   │   ├── migrations/                   # Database migrations
│   │   ├── services/                     # Domain service layer
│   │   │   ├── __init__.py
│   │   │   └── stripe_service.py         # Stripe distributed lock & payment logic
│   │   ├── views/                        # API view layer
│   │   │   ├── __init__.py               # View exports
│   │   │   ├── auth.py                   # Google OAuth endpoints
│   │   │   ├── base.py                   # TenantBaseViewSet abstract base
│   │   │   ├── billing.py                # Stripe webhook, checkout & quota views
│   │   │   ├── organization.py           # Organization, member & invitation views
│   │   │   └── workspace.py              # Project, task & Markdown doc views
│   │   ├── __init__.py
│   │   ├── admin.py                      # Django Admin configuration
│   │   ├── apps.py                       # Core app config
│   │   ├── decorators.py                 # Custom decorators
│   │   ├── models.py                     # UUIDv7 tables, RBAC, StripeLog, etc.
│   │   ├── permissions.py                # Tenant & role permission gatekeepers
│   │   ├── serializers.py                # DRF serializers
│   │   ├── signals.py                    # Auto team creation signal on registration
│   │   ├── tasks.py                      # Invitation & welcome email Celery tasks
│   │   └── tests.py                      # Backend test module
│   ├── .dockerignore                     # Backend Docker ignore file
│   ├── .env                              # Backend environment variables
│   ├── db.sqlite3                        # Local SQLite dev database
│   ├── Dockerfile                        # Backend Docker build file
│   ├── manage.py                         # Django management script
│   └── requirements.txt                  # Python dependencies
├── frontend/                             # Next.js frontend application
│   ├── public/                           # Static assets
│   ├── src/
│   │   ├── app/                          # Next.js App Router
│   │   │   ├── api/auth/[...nextauth]/   # NextAuth OAuth route
│   │   │   │   └── route.ts              # NextAuth handler
│   │   │   ├── dashboard/                # Dashboard entry point
│   │   │   │   ├── billing/              # Plan & billing management page
│   │   │   │   │   └── page.tsx
│   │   │   │   ├── projects/             # Project Kanban & docs page
│   │   │   │   │   └── page.tsx
│   │   │   │   ├── team/                 # Team members & invitations page
│   │   │   │   │   └── page.tsx
│   │   │   │   ├── layout.tsx            # Shared dashboard layout
│   │   │   │   └── page.tsx              # Dashboard homepage
│   │   │   ├── invite/accept/            # Invitation acceptance page
│   │   │   │   └── page.tsx
│   │   │   ├── login/                    # Login page
│   │   │   │   └── page.tsx
│   │   │   ├── globals.css               # Global stylesheet
│   │   │   ├── layout.tsx                # Root layout
│   │   │   └── page.tsx                  # Root path redirect page
│   │   ├── components/                   # Shared React components
│   │   │   ├── Header.tsx                # Top navigation bar
│   │   │   ├── OrgProvider.tsx           # Organization context provider
│   │   │   ├── OrgSwitcher.tsx           # Live workspace switcher
│   │   │   ├── Providers.tsx             # Global session & state provider
│   │   │   └── Sidebar.tsx               # Sidebar navigation
│   │   ├── lib/
│   │   │   └── api.ts                    # Axios interceptors (injects X-Organization-ID)
│   │   ├── store/
│   │   │   └── useOrgStore.ts            # Zustand tenant state store
│   │   ├── types/                        # TypeScript type declarations
│   │   │   ├── next-auth.d.ts            # NextAuth session extension types
│   │   │   └── react-markdown.d.ts       # Markdown module types
│   │   └── middleware.ts                 # Route guard middleware
│   ├── .dockerignore                     # Frontend Docker ignore file
│   ├── .env.local                        # Frontend environment variables
│   ├── .gitignore                        # Frontend Git ignore list
│   ├── Dockerfile                        # Frontend Docker build file
│   ├── eslint.config.mjs                 # ESLint configuration
│   ├── next-env.d.ts                     # Next.js type declarations
│   ├── next.config.ts                    # Next.js build configuration
│   ├── package-lock.json                 # npm dependency lockfile
│   ├── package.json                      # Frontend dependencies
│   ├── postcss.config.mjs                # PostCSS / Tailwind config
│   ├── README.md                         # Frontend module notes
│   └── tsconfig.json                     # TypeScript configuration
├── docker-compose.yml                    # Container service orchestration
├── .env                                  # Root global environment variables
└── .gitignore                            # Root Git ignore list
```

## Services & Port Mappings

| Service | Container | Internal/External Port | Description |
|--------------------|----------------------|---------------|------|
| **frontend** | `saas_frontend` | `3000:3000` | Next.js 15 frontend web app |
| **web** | `saas_django` | `8000:8000` | Django REST Framework core API |
| **celery_worker** | `saas_celery` | (internal network) | Persistent async email delivery & background task worker |
| **rabbitmq** | `saas_rabbitmq` | `5672:5672` / `15672:15672` | RabbitMQ AMQP broker & web management console |
| **redis** | `saas_redis` | `6379:6379` | Redis cache & Stripe distributed anti-concurrency lock |
| **db** | `saas_mysql` | `3306:3306` | MySQL 8.0 relational database (with health checks) |

## Quickstart

**Configure environment variables**

```
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

**Start all microservice containers**
```
docker compose up -d --build
```

**Run database migrations**
```
docker compose exec web python manage.py migrate
```

**Access service endpoints**

* Frontend web app: 3000
* Backend API server: 8000
* Django admin panel: 8000/admin
* RabbitMQ console: 15672

## RBAC Permissions

| Feature / Action | Owner | Admin | Member |
| :--- | :---: | :---: | :---: |
| **Purchase / checkout billing plans** | ✅ | ❌ | ❌ |
| **View subscription status & project quota usage** | ✅ | ✅ | ✅ |
| **Send team invitations** | ✅ | ✅ | ❌ |
| **Revoke unaccepted invitations** | ✅ | ✅ | ❌ |
| **Remove team members** | ✅ | ✅ | ❌ |
| **Create new project** | ✅ | ✅ | ✅ |
| **View project list & details** | ✅ | ✅ | ✅ |
| **Edit project name & description** | ✅ | ✅ | ❌ |
| **Delete project** | ✅ | ✅ | ❌ |
| **Create Kanban task** | ✅ | ✅ | ✅ |
| **Edit task / drag to change status** | ✅ | ✅ | ✅ |
| **Delete Kanban task** | ✅ | ✅ | ❌ |
| **Create Markdown spec document** | ✅ | ✅ | ✅ |
| **Edit Markdown spec document** | ✅ | ✅ | ✅ |
| **Delete Markdown spec document** | ✅ | ✅ | ❌ |

## Protocols & API Reference

### Auth & Organization

| Method | Endpoint | Description |
|--------|----------|------|
| `POST` | `/api/auth/google/` | Google OAuth login, returns a DRF token. |
| `GET` | `/api/organizations/me/` | Get all workspaces the current user belongs to. |
| `GET` | `/api/org-members/` | Get current workspace member list (requires `X-Organization-ID` header). |
| `DELETE` | `/api/org-members/{id}/` | Remove an organization member (Owner/Admin only). |
| `GET` | `/api/invitations/` | Get pending invitations for the current workspace. |
| `POST` | `/api/invitations/` | Send a workspace email invitation (auto-validates member quota). |
| `DELETE` | `/api/invitations/{id}/` | Revoke an unaccepted invitation. |
| `POST` | `/api/accept-invitation/` | Accept an invitation via token to join an organization. |

---

### Workspace (Projects & Collaboration Specs)

| Method | Endpoint | Description |
|---------|--------------|----------|
| `GET` | `/api/projects/` | Get organization project list (requires `X-Organization-ID` header). |
| `POST` | `/api/projects/` | Create a new project (auto-validates plan project quota). |
| `GET` | `/api/projects/{id}/` | Get a single project's details. |
| `PUT / PATCH` | `/api/projects/{id}/` | Edit project name & description (Owner/Admin only). |
| `DELETE` | `/api/projects/{id}/` | Delete a project (Owner/Admin only). |
| `GET` | `/api/tasks/?project_id=...` | Get the Kanban task list for a project. |
| `POST` | `/api/tasks/` | Create a Kanban task. |
| `PUT / PATCH` | `/api/tasks/{id}/` | Edit task title, description, status (`TODO` / `IN_PROGRESS` / `DONE`), or assignee. |
| `DELETE` | `/api/tasks/{id}/` | Delete a Kanban task (Owner/Admin only). |
| `GET` | `/api/documents/?project_id=...` | Get a project's Markdown spec document list. |
| `POST` | `/api/documents/` | Create a project Markdown spec document. |
| `GET` | `/api/documents/{id}/` | Get a single Markdown spec document's details. |
| `PUT / PATCH` | `/api/documents/{id}/` | Edit a Markdown spec document's title & content. |
| `DELETE` | `/api/documents/{id}/` | Delete a Markdown spec document (Owner/Admin only). |

---

### Billing & Stripe

| Method | Endpoint | Description |
|--------|----------|------|
| `POST` | `/api/billing/checkout/` | Create a Stripe one-time-purchase checkout session. |
| `GET` | `/api/billing/subscription/` | Get the current organization's plan tier (`FREE` / `PRO` / `ENTERPRISE`) and subscription status. |
| `GET` | `/api/billing/project-usage/` | Get the current organization's project quota and usage. |
| `POST` | `/webhooks/stripe/` | Receive Stripe webhook events (supports Redis distributed anti-concurrency lock and DB idempotency auditing). |

---

### API Documentation (OpenAPI / Swagger)

| Method | Endpoint | Description |
|--------|----------|------|
| `GET` | `/api/docs/swagger/` | Swagger UI interactive API documentation. |
| `GET` | `/api/docs/redoc/` | ReDoc API specification documentation. |
| `GET` | `/api/schema/` | OpenAPI 3.0 YAML / JSON schema file. |
