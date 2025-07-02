# DEMO_OVERALL_TECH_STACK - Technology Stack

## P&C Insurance Platform Demo

### Stack Overview

```yaml
philosophy: "Modern, Fast, Impressive"
timeline: "4 weeks to demo"
principle: "Use the best tools for rapid development"
future_ready: "Easy to evolve to Rust/production scale"
```

### Core Technology Choices

#### Programming Languages

```yaml
backend:
  primary:
    language: Python
    version: "3.11.7"
    why: "Fastest path to working demo, huge ecosystem"
    future: "Can add Rust extensions later via PyO3"

frontend:
  primary:
    language: TypeScript
    version: "5.3.3"
    why: "Type safety without slowing development"

  markup:
    language: "TSX/JSX"
    why: "React ecosystem, component reusability"

styling:
  primary: "Tailwind CSS"
  version: "3.4.0"
  why: "Rapid UI development, looks modern instantly"

infrastructure:
  primary: "Terraform"
  version: "1.6.6"
  why: "IaC for repeatable deployments"
```

### Backend Stack

#### Web Framework

```yaml
framework:
  name: "FastAPI"
  version: "0.109.0"
  why:
    - "Automatic API documentation"
    - "Native async support"
    - "Pydantic integration"
    - "Fastest Python framework"

  key_features_for_demo:
    - "Swagger UI impresses technical audience"
    - "WebSocket support for real-time updates"
    - "Background tasks for async operations"
```

#### Backend Dependencies

```toml
# pyproject.toml
[tool.poetry]
name = "pd-prime-demo"
version = "0.1.0"
description = "P&C Insurance Platform Demo"
authors = ["Your Name <you@example.com>"]
python = "^3.11"

[tool.poetry.dependencies]
# Core Framework
fastapi = "^0.109.0"
uvicorn = {extras = ["standard"], version = "^0.25.0"}
pydantic = "^2.5.3"
pydantic-settings = "^2.1.0"

# Database
sqlalchemy = "^2.0.25"
asyncpg = "^0.29.0"
alembic = "^1.13.1"

# Redis for caching
redis = "^5.0.1"

# Authentication (simple for demo)
python-jose = {extras = ["cryptography"], version = "^3.3.0"}
passlib = {extras = ["bcrypt"], version = "^1.7.4"}
python-multipart = "^0.0.6"

# AI Integration
openai = "^1.8.0"
langchain = "^0.1.0"

# Document Generation
reportlab = "^4.0.8"
python-docx = "^1.1.0"

# Background Tasks
celery = "^5.3.4"

# Utilities
httpx = "^0.26.0"
python-dateutil = "^2.8.2"
faker = "^22.0.0"  # Demo data generation

# Development
pytest = "^7.4.4"
pytest-asyncio = "^0.23.3"
black = "^23.12.1"
ruff = "^0.1.11"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

#### Database Stack

```yaml
primary_database:
  name: "PostgreSQL"
  version: "15"
  hosting: "Railway (managed)"
  why:
    - "JSONB for flexible demo schemas"
    - "Excellent async support with asyncpg"
    - "Railway auto-provisions with one click"

  extensions:
    - "uuid-ossp" # UUID generation
    - "pg_trgm" # Fuzzy text search
    - "btree_gin" # Better JSONB indexing

cache:
  name: "Redis"
  version: "7"
  hosting: "Railway (managed)"
  use_cases:
    - "API response caching"
    - "Session storage"
    - "Real-time metrics"
    - "WebSocket pub/sub"
```

### Frontend Stack

#### Core Framework

```yaml
framework:
  name: "Next.js"
  version: "14.0.4"
  features_used:
    - "App Router"
    - "Server Components"
    - "Server Actions"
    - "Middleware"
    - "API Routes"
  why:
    - "Vercel's own framework = perfect deployment"
    - "React Server Components = impressive performance"
    - "Built-in optimizations"
```

#### Frontend Dependencies

```json
// package.json
{
  "name": "pd-prime-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    // Core
    "next": "14.0.4",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",

    // Routing & State
    "@tanstack/react-query": "^5.17.9",
    "@trpc/client": "^10.45.0",
    "@trpc/react-query": "^10.45.0",
    "@trpc/server": "^10.45.0",
    "zustand": "^4.4.7",

    // UI Components
    "@radix-ui/react-accordion": "^1.1.2",
    "@radix-ui/react-alert-dialog": "^1.0.5",
    "@radix-ui/react-dialog": "^1.0.5",
    "@radix-ui/react-dropdown-menu": "^2.0.6",
    "@radix-ui/react-select": "^2.0.0",
    "@radix-ui/react-tabs": "^1.0.4",
    "@radix-ui/react-toast": "^1.1.5",

    // Forms & Validation
    "react-hook-form": "^7.48.2",
    "@hookform/resolvers": "^3.3.4",
    "zod": "^3.22.4",

    // Tables & Data
    "@tanstack/react-table": "^8.11.2",

    // Charts for Demo Analytics
    "recharts": "^2.10.4",

    // Utilities
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.2.0",
    "date-fns": "^3.2.0",
    "lucide-react": "^0.309.0",

    // Auth
    "next-auth": "^4.24.5"
  },
  "devDependencies": {
    "@types/node": "^20.11.0",
    "@types/react": "^18.2.47",
    "@types/react-dom": "^18.2.18",
    "autoprefixer": "^10.4.16",
    "eslint": "^8.56.0",
    "eslint-config-next": "14.0.4",
    "postcss": "^8.4.33",
    "tailwindcss": "^3.4.1",
    "typescript": "^5.3.3"
  }
}
```

#### UI Component Library

```yaml
component_library:
  name: "shadcn/ui"
  why:
    - "Beautiful components out of the box"
    - "Tailwind-based = consistent styling"
    - "Copy-paste = full control"
    - "Radix UI primitives = accessibility"

  components_used:
    - Button, Card, Dialog
    - Form components
    - Data tables
    - Toast notifications
    - Command palette (for AI search demo)
```

### AI/ML Stack

```yaml
ai_services:
  primary:
    name: "OpenAI API"
    models:
      - "GPT-4" # Document analysis
      - "GPT-3.5-turbo" # Quick completions
    use_cases:
      - "Risk analysis from documents"
      - "Underwriting recommendations"
      - "Natural language search"
      - "Auto-complete for forms"

  framework:
    name: "LangChain"
    why: "Quick AI prototype development"

  vector_database:
    name: "In-memory for demo"
    future: "Pinecone/Weaviate for production"
```

### DevOps & Deployment

#### Hosting Platforms

```yaml
backend_hosting:
  platform: "Railway"
  why:
    - "Git push = deploy"
    - "Auto-provisions databases"
    - "Built-in monitoring"
    - "WebSocket support"
    - "Fair pricing for demos"

  services:
    - "FastAPI app"
    - "PostgreSQL database"
    - "Redis cache"
    - "Background workers"

frontend_hosting:
  platform: "Vercel"
  why:
    - "Next.js creators"
    - "Edge network = fast globally"
    - "Preview deployments"
    - "Analytics included"
    - "Generous free tier"
```

#### Infrastructure as Code

```hcl
# terraform/demo-stack.tf
terraform {
  required_providers {
    railway = {
      source = "terraform-providers/railway"
    }
    vercel = {
      source = "vercel/vercel"
    }
  }
}

variable "github_repo_backend" {
  default = "your-org/pd-prime-backend"
}

variable "github_repo_frontend" {
  default = "your-org/pd-prime-frontend"
}

resource "railway_project" "demo" {
  name = "pd-prime-demo"
}

resource "railway_service" "api" {
  name       = "api"
  project_id = railway_project.demo.id

  github_repo = var.github_repo_backend
  branch      = "main"

  deploy_on_push = true
}

resource "vercel_project" "frontend" {
  name = "pd-prime-demo"

  git_repository = {
    type = "github"
    repo = var.github_repo_frontend
  }
}
```

### Development Tools

#### IDE & Extensions

```yaml
primary_ide:
  name: "Cursor"
  why: "AI-powered development acceleration"

  key_features:
    - "AI code completion"
    - "Natural language to code"
    - "Automatic refactoring"
    - "Bug detection"

vscode_extensions:
  - "Python"
  - "Pylance"
  - "Black Formatter"
  - "ESLint"
  - "Prettier"
  - "Tailwind CSS IntelliSense"
  - "Thunder Client" # API testing
  - "GitLens"
```

#### Version Control

```yaml
git_workflow:
  platform: "GitHub"
  branching:
    - main # Production demo
    - develop # Active development
    - feature/* # Feature branches

  automation:
    - "GitHub Actions for CI/CD"
    - "Automatic deployment on merge"
    - "PR preview deployments"
```

### Testing Stack (Minimal for Demo)

```yaml
backend_testing:
  framework: "pytest"
  coverage_target: "60%" # Lower for demo
  key_tests:
    - "API endpoint smoke tests"
    - "Critical path validation"
    - "Demo scenario tests"

frontend_testing:
  framework: "Jest + React Testing Library"
  e2e: "Playwright"
  coverage_target: "40%" # Focus on demo flow
```

### Monitoring & Analytics

```yaml
monitoring:
  backend:
    platform: "Railway built-in"
    metrics:
      - "Request/response times"
      - "Error rates"
      - "Resource usage"

  frontend:
    platform: "Vercel Analytics"
    metrics:
      - "Web vitals"
      - "User interactions"
      - "Error tracking"

  error_tracking:
    service: "Sentry"
    tier: "Free/Developer"
    why: "Catch demo bugs quickly"
```

### Demo-Specific Tools

```yaml
demo_utilities:
  data_generation:
    tool: "Faker"
    why: "Realistic demo data"

  api_documentation:
    tool: "Swagger UI (via FastAPI)"
    why: "Interactive API demo"

  database_gui:
    tool: "Railway's built-in data browser"
    why: "Show data transparency"

  load_testing:
    tool: "locust"
    why: "Demo performance under load"
```

### Security (Demo Level)

```yaml
security_measures:
  authentication:
    method: "JWT tokens"
    library: "python-jose"
    complexity: "Simple for demo"

  api_security:
    - "CORS properly configured"
    - "Rate limiting (basic)"
    - "Input validation (Pydantic)"

  secrets_management:
    dev: ".env files"
    demo: "Railway/Vercel env vars"

  https:
    backend: "Railway provides"
    frontend: "Vercel provides"
```

### Performance Optimizations

```yaml
backend_performance:
  - "Redis caching for all expensive operations"
  - "Database connection pooling"
  - "Async everywhere"
  - "Pagination on all lists"

frontend_performance:
  - "React Server Components"
  - "Image optimization (Next.js)"
  - "Code splitting"
  - "Edge caching (Vercel)"
```

### Migration Path to Production

```yaml
future_evolution:
  backend:
    phase_1: "Current Python stack"
    phase_2: "Add Rust modules for hot paths"
    phase_3: "Full Rust rewrite if needed"

  frontend:
    stable: "Next.js scales to production"

  infrastructure:
    phase_1: "Railway/Vercel"
    phase_2: "Add CDN, better monitoring"
    phase_3: "AWS/GCP for enterprise features"

  database:
    phase_1: "PostgreSQL with JSONB"
    phase_2: "Add read replicas"
    phase_3: "Proper schema, partitioning"
```

### Cost Analysis (Demo Phase)

```yaml
monthly_costs:
  railway:
    tier: "Hobby"
    cost: "$5/month"
    includes:
      - "App hosting"
      - "PostgreSQL"
      - "Redis"

  vercel:
    tier: "Hobby"
    cost: "$0/month"
    includes:
      - "Hosting"
      - "Analytics"
      - "Edge network"

  openai:
    budget: "$20/month"
    usage: "Demo AI features"

  total: "~$25/month for demo"
```

---

**Tech Stack Philosophy**: "Start Modern, Stay Flexible, Ship Fast"
