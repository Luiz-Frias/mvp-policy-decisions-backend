# Electron Desktop App - Technical Stack Overview

## Technology Architecture Overview

The Electron desktop application follows a **multi-process architecture** combining modern web technologies with embedded Python backend, maintaining the existing **MASTER RULESET** standards while adapting for desktop deployment.

## Core Technology Stack

### 🖥️ Desktop Application Framework

#### Electron (Latest LTS - v22+)

- **Main Process**: Application lifecycle, window management, system integration
- **Renderer Process**: UI rendering using Chromium engine
- **IPC (Inter-Process Communication)**: Secure communication between main/renderer
- **Native Modules**: Platform-specific integrations (notifications, file system)

```javascript
// Electron Architecture Example
const { app, BrowserWindow, ipcMain } = require("electron");

class ApplicationManager {
  constructor() {
    this.mainWindow = null;
    this.pythonProcess = null;
  }

  async initialize() {
    await this.startPythonBackend();
    this.createMainWindow();
    this.setupIPC();
  }
}
```

### 🎨 Frontend Technology Stack

#### Next.js 13+ (Adapted for Electron)

- **App Router**: Modern routing with layout support
- **Server Components**: Adapted for Electron renderer process
- **Static Export**: Pre-built static assets for offline operation
- **TypeScript**: Full type safety with strict mode

#### UI Components & Styling

- **Tailwind CSS 3.x**: Utility-first CSS framework
- **Headless UI**: Accessible component primitives
- **Lucide Icons**: Lightweight icon library
- **CSS Modules**: Scoped styling for component isolation

#### State Management

- **Zustand**: Lightweight state management
- **React Query/TanStack Query**: Server state management (adapted for local backend)
- **React Hook Form**: Form handling with validation

```typescript
// Frontend Architecture Example
interface ElectronBridge {
  backend: {
    invoke: (channel: string, data?: any) => Promise<any>;
    on: (channel: string, callback: Function) => void;
  };
}

declare global {
  interface Window {
    electronAPI: ElectronBridge;
  }
}
```

### 🐍 Backend Technology Stack

#### Python 3.11+ (Embedded Runtime)

- **FastAPI**: High-performance async web framework
- **Uvicorn**: ASGI server for development/embedded mode
- **Pydantic v2**: Data validation with Rust core
- **Beartype**: Runtime type checking

#### Database Layer

- **Primary**: SQLite 3.35+ with WAL mode
- **Enterprise**: PostgreSQL 13+ (optional embedded)
- **ORM**: SQLAlchemy 2.0+ with async support
- **Migrations**: Alembic for schema management

```python
# Backend Architecture Example
from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database, cache
    await init_local_database()
    await init_local_cache()
    yield
    # Shutdown: Cleanup resources
    await cleanup_resources()

app = FastAPI(
    title="Policy Decision Desktop API",
    lifespan=lifespan,
    docs_url=None,  # Disable in embedded mode
    redoc_url=None
)
```

#### Caching & Performance

- **Local Redis**: Embedded Redis for caching (optional)
- **In-Memory Cache**: Python `cachetools` for simple caching
- **File System Cache**: Persistent cache using local storage
- **Background Tasks**: `asyncio` with proper resource management

### 💾 Data Storage Architecture

#### Local Database Configuration

```sql
-- SQLite Configuration for Desktop App
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = 10000;
PRAGMA foreign_keys = ON;
PRAGMA temp_store = MEMORY;
```

#### Database Schema Management

- **Schema Versioning**: Alembic migrations with desktop-specific handling
- **Data Encryption**: SQLCipher for enterprise deployments
- **Backup Strategy**: Automated local backups with rotation
- **Data Import/Export**: Custom utilities for data portability

### 🔧 Development & Build Tools

#### Package Management

- **Frontend**: `npm` with `package-lock.json`
- **Backend**: `uv` with `uv.lock` (maintaining existing setup)
- **Electron**: `electron-builder` for packaging

#### Build Pipeline

- **Frontend Build**: Next.js static export for Electron
- **Backend Packaging**: Python bundling with PyInstaller/cx_Freeze
- **Asset Bundling**: Webpack for optimal resource packaging
- **Code Signing**: Platform-specific signing for distribution

```json
{
  "build": {
    "appId": "com.company.policy-decision-desktop",
    "productName": "Policy Decision Desktop",
    "directories": {
      "output": "dist",
      "buildResources": "build"
    },
    "files": ["electron/**/*", "frontend/out/**/*", "backend/dist/**/*"],
    "extraResources": [
      {
        "from": "python-runtime",
        "to": "python-runtime"
      }
    ]
  }
}
```

### 🔒 Security & Compliance Stack

#### Application Security

- **Content Security Policy**: Strict CSP for renderer processes
- **Context Isolation**: Isolated renderer contexts
- **Node Integration**: Disabled in renderer, controlled via preload scripts
- **Remote Module**: Disabled for security

#### Data Security

- **Encryption at Rest**: AES-256 for sensitive data
- **Key Management**: OS keychain integration (Windows Credential Manager, macOS Keychain, Linux Secret Service)
- **Certificate Handling**: Local certificate store management
- **Audit Logging**: Structured logging with rotation

```typescript
// Security Configuration Example
const securityConfig = {
  csp: "default-src 'self'; script-src 'self' 'unsafe-inline';",
  nodeIntegration: false,
  contextIsolation: true,
  enableRemoteModule: false,
  allowRunningInsecureContent: false,
};
```

### 🧪 Testing & Quality Assurance

#### Testing Framework Stack

- **Unit Testing**: Jest + React Testing Library (frontend), pytest (backend)
- **Integration Testing**: Electron-specific testing with Spectron successor
- **E2E Testing**: Playwright for cross-platform testing
- **Performance Testing**: Existing pytest-benchmark + desktop-specific metrics

#### Code Quality Tools

- **Linting**: ESLint (frontend), Ruff (backend)
- **Formatting**: Prettier (frontend), Black (backend)
- **Type Checking**: TypeScript strict mode, MyPy strict mode
- **Security Scanning**: Electron-specific security audits

### 📦 Distribution & Deployment

#### Platform-Specific Packaging

- **Windows**: MSI installer with auto-update support
- **macOS**: DMG with notarization, App Store distribution optional
- **Linux**: AppImage, DEB, RPM packages

#### Auto-Update System

- **Update Server**: Simple HTTP-based update server
- **Differential Updates**: Binary diff updates for efficiency
- **Rollback Mechanism**: Automatic rollback on update failures
- **Enterprise Control**: Group policy controls for update management

### 🔧 Development Environment

#### Required Development Tools

```bash
# Node.js and npm
node --version  # v18+
npm --version   # v9+

# Python and uv (existing setup)
python --version  # 3.11+
uv --version      # latest

# Platform-specific tools
# Windows: Visual Studio Build Tools
# macOS: Xcode Command Line Tools
# Linux: build-essential
```

#### Development Workflow

1. **Local Development**: Hot reload for both frontend and backend
2. **Testing**: Automated test suites for all components
3. **Building**: Cross-platform builds in CI/CD
4. **Distribution**: Automated release pipeline

### 🚀 Performance Optimization

#### Application Performance

- **Bundle Splitting**: Lazy loading for non-critical components
- **Memory Management**: Proper cleanup of Python/Node.js resources
- **Process Isolation**: Separate processes for CPU-intensive tasks
- **Caching Strategy**: Multi-layer caching (memory, disk, database)

#### Resource Usage Targets

- **Memory**: < 512MB baseline, < 1GB under load
- **CPU**: < 10% idle, < 50% normal operation
- **Disk I/O**: Efficient SQLite usage, minimal file system operations
- **Startup Time**: < 5 seconds cold start

### 🔄 Migration Strategy

#### Data Migration Pipeline

```python
class DataMigrator:
    """Handles migration from cloud to local storage."""

    async def migrate_from_railway(self, connection_config: dict):
        """Migrate data from Railway PostgreSQL to local SQLite."""
        # Implementation handles:
        # - Schema mapping
        # - Data transformation
        # - Progress tracking
        # - Error recovery
        pass
```

#### Configuration Migration

- **Environment Variables**: Convert to local config files
- **Secrets**: Migrate Doppler secrets to local encrypted storage
- **Database URLs**: Update connection strings for local databases
- **API Endpoints**: Adapt for localhost backend communication

## Technology Decision Matrix

| Component              | Web App              | Desktop App                | Rationale                             |
| ---------------------- | -------------------- | -------------------------- | ------------------------------------- |
| **Frontend Framework** | Next.js              | Next.js (adapted)          | Maintain existing expertise           |
| **Backend Framework**  | FastAPI              | FastAPI (embedded)         | Zero rewrite, proven performance      |
| **Database**           | PostgreSQL (Railway) | SQLite + PostgreSQL option | Offline-first, enterprise flexibility |
| **Caching**            | Redis (Railway)      | Local Redis/Memory         | Performance + offline capability      |
| **Deployment**         | Cloud hosting        | Desktop installers         | User requirement for offline          |
| **Updates**            | Continuous           | Versioned releases         | Desktop app lifecycle                 |
| **Security**           | HTTPS/Transport      | Full-stack encryption      | Enhanced local security               |

## Integration Points

### Electron ↔ Frontend Communication

```typescript
// Preload script (secure bridge)
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  backend: {
    invoke: (channel, data) => ipcRenderer.invoke(channel, data),
    on: (channel, callback) => ipcRenderer.on(channel, callback),
  },
});
```

### Electron ↔ Python Backend Communication

```javascript
// Main process manages Python subprocess
class PythonManager {
  async start() {
    this.process = spawn("python", ["-m", "uvicorn", "main:app", "--port", "8001"]);
    await this.waitForReady();
  }

  async invoke(endpoint, data) {
    return fetch(`http://localhost:8001${endpoint}`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }
}
```

This technical stack maintains the **MASTER RULESET** principles while adapting to desktop deployment requirements, ensuring type safety, performance, and maintainability standards are preserved throughout the conversion process.
