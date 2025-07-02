# Electron Desktop App - System Architecture

## Architecture Overview

The Electron desktop application follows a **multi-process, microservices-inspired architecture** that separates concerns while maintaining the **MASTER RULESET** principles of type safety, performance, and maintainability.

## High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    ELECTRON DESKTOP APPLICATION                  │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐    ┌──────────────┐ │
│  │   Main Process  │    │ Renderer Process│    │   Preload    │ │
│  │   (Node.js)     │◄──►│   (Chromium)    │◄──►│   Scripts    │ │
│  │                 │    │                 │    │              │ │
│  │ • Window Mgmt   │    │ • Next.js App   │    │ • IPC Bridge │ │
│  │ • System Tray   │    │ • React UI      │    │ • Security   │ │
│  │ • Auto Updates  │    │ • State Mgmt    │    │ • Context    │ │
│  │ • Python Mgmt   │    │ • API Calls     │    │   Isolation  │ │
│  └─────────────────┘    └─────────────────┘    └──────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                         EMBEDDED BACKEND                         │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                 Python FastAPI Process                      │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │ │
│  │  │   FastAPI   │  │  Business   │  │     Database        │ │ │
│  │  │   Routes    │  │   Logic     │  │   (SQLite/PgSQL)    │ │ │
│  │  │             │  │             │  │                     │ │ │
│  │  │ • REST API  │  │ • Pydantic  │  │ • SQLAlchemy        │ │ │
│  │  │ • Auth      │  │ • Services  │  │ • Alembic           │ │ │
│  │  │ • Validation│  │ • Utils     │  │ • Connection Pool   │ │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                        LOCAL STORAGE                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   SQLite    │  │    Cache    │  │      File System        │  │
│  │  Database   │  │  (Redis/    │  │                         │  │
│  │             │  │  Memory)    │  │ • Config Files          │  │
│  │ • WAL Mode  │  │             │  │ • Logs                  │  │
│  │ • Encrypted │  │ • Session   │  │ • Backups               │  │
│  │ • Indexed   │  │ • Query     │  │ • User Data             │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Process Architecture

### 1. Main Process (Electron Core)

**Responsibilities:**

- Application lifecycle management
- Window creation and management
- System-level integrations
- Python subprocess management
- Auto-update orchestration
- Security enforcement

```javascript
// Main Process Architecture
class MainApplication {
  constructor() {
    this.windows = new Map();
    this.pythonManager = new PythonBackendManager();
    this.updateManager = new AutoUpdateManager();
    this.securityManager = new SecurityManager();
  }

  async initialize() {
    await this.pythonManager.start();
    await this.createMainWindow();
    this.setupGlobalShortcuts();
    this.setupSystemTray();
  }
}
```

### 2. Renderer Process (UI Layer)

**Responsibilities:**

- UI rendering via Chromium
- React/Next.js application hosting
- User interaction handling
- State management
- API communication (via IPC)

```typescript
// Renderer Process Architecture
interface RendererServices {
  api: ApiService; // Backend communication
  state: StateManager; // Application state
  storage: LocalStorage; // Browser storage
  notifications: NotificationService;
}

class RendererApplication {
  private services: RendererServices;

  async initialize() {
    this.services = await this.setupServices();
    await this.loadApplicationState();
    this.startApplication();
  }
}
```

### 3. Preload Scripts (Security Bridge)

**Responsibilities:**

- Secure IPC communication
- Context isolation enforcement
- API surface limitation
- Security policy enforcement

```typescript
// Preload Script Architecture
const electronAPI = {
  // Backend communication
  backend: {
    invoke: (channel: string, data?: any) => ipcRenderer.invoke(`backend:${channel}`, data),
    on: (channel: string, callback: Function) => ipcRenderer.on(`backend:${channel}`, callback),
  },

  // System operations
  system: {
    showOpenDialog: () => ipcRenderer.invoke("system:show-open-dialog"),
    showSaveDialog: () => ipcRenderer.invoke("system:show-save-dialog"),
    showNotification: (options: NotificationOptions) =>
      ipcRenderer.invoke("system:show-notification", options),
  },
};

contextBridge.exposeInMainWorld("electronAPI", electronAPI);
```

## Backend Architecture (Embedded Python)

### Service Layer Design

```python
# Service Architecture Following MASTER RULESET
from abc import ABC, abstractmethod
from beartype import beartype
from pydantic import BaseModel

class ServiceInterface(ABC):
    """Base interface for all services."""

    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def cleanup(self) -> None: ...

@beartype
class PolicyService(ServiceInterface):
    """Policy management service with defensive programming."""

    def __init__(self, db: DatabaseManager, cache: CacheManager):
        self._db = db
        self._cache = cache
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize service with proper error handling."""
        if self._initialized:
            return

        try:
            await self._db.initialize()
            await self._cache.initialize()
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize PolicyService: {e}")
            raise

    @beartype
    async def create_policy(self, policy_data: PolicyCreateRequest) -> Result[Policy, str]:
        """Create policy with comprehensive validation."""
        if not self._initialized:
            return Result.err("Service not initialized")

        try:
            # Validate business rules
            validation_result = await self._validate_policy_rules(policy_data)
            if validation_result.is_err():
                return validation_result

            # Create policy
            policy = await self._db.create_policy(policy_data)

            # Update cache
            await self._cache.set_policy(policy.id, policy)

            return Result.ok(policy)

        except Exception as e:
            logger.error(f"Failed to create policy: {e}")
            return Result.err(f"Policy creation failed: {str(e)}")
```

### Database Layer Architecture

```python
# Database Architecture with Defensive Programming
class DatabaseManager:
    """SQLite database manager with connection pooling and error recovery."""

    def __init__(self, config: DatabaseConfig):
        self._config = config
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker] = None

    async def initialize(self) -> None:
        """Initialize database with proper configuration."""
        try:
            # Create engine with optimized settings
            self._engine = create_async_engine(
                self._config.url,
                echo=self._config.debug,
                pool_pre_ping=True,
                pool_recycle=3600,
                connect_args={
                    "check_same_thread": False if "sqlite" in self._config.url else {},
                }
            )

            # Create session factory
            self._session_factory = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False
            )

            # Run migrations
            await self._run_migrations()

        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session with proper error handling."""
        if not self._session_factory:
            raise RuntimeError("Database not initialized")

        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Database session error: {e}")
                raise
            finally:
                await session.close()
```

## Data Flow Architecture

### Request Processing Flow

```
┌─────────────┐    IPC     ┌─────────────┐    HTTP    ┌─────────────┐
│  Frontend   │◄──────────►│    Main     │◄──────────►│   Python    │
│  (Renderer) │            │   Process   │            │   Backend   │
└─────────────┘            └─────────────┘            └─────────────┘
       │                          │                          │
       │                          │                          ▼
       │                          │                   ┌─────────────┐
       │                          │                   │  Database   │
       │                          │                   │  (SQLite)   │
       │                          │                   └─────────────┘
       │                          │                          │
       │                          │                          ▼
       │                          │                   ┌─────────────┐
       │                          │                   │    Cache    │
       │                          │                   │ (Redis/Mem) │
       │                          │                   └─────────────┘
       ▼                          ▼
┌─────────────┐            ┌─────────────┐
│ Local State │            │ File System │
│  (Zustand)  │            │ (Config/Log)│
└─────────────┘            └─────────────┘
```

### Data Processing Pipeline

```python
# Data Processing Architecture
@beartype
async def process_policy_request(
    request: PolicyRequest,
    context: RequestContext
) -> Result[PolicyResponse, ProcessingError]:
    """
    Process policy request through validation pipeline.

    Pipeline stages:
    1. Input validation
    2. Business rule validation
    3. Data processing
    4. Response formatting
    5. Audit logging
    """
    pipeline = ProcessingPipeline([
        InputValidationStage(),
        BusinessRuleValidationStage(),
        DataProcessingStage(),
        ResponseFormattingStage(),
        AuditLoggingStage()
    ])

    return await pipeline.execute(request, context)
```

## Security Architecture

### Security Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    SECURITY LAYERS                           │
├─────────────────────────────────────────────────────────────┤
│ 1. Application Security                                     │
│    • Context Isolation  • CSP  • Node Integration Disabled │
├─────────────────────────────────────────────────────────────┤
│ 2. Communication Security                                   │
│    • IPC Whitelisting  • Message Validation  • Encryption  │
├─────────────────────────────────────────────────────────────┤
│ 3. Data Security                                           │
│    • AES-256 Encryption  • OS Keychain  • Audit Logging   │
├─────────────────────────────────────────────────────────────┤
│ 4. System Security                                         │
│    • Process Isolation  • Sandboxing  • Resource Limits   │
└─────────────────────────────────────────────────────────────┘
```

### Security Implementation

```typescript
// Security Architecture Implementation
class SecurityManager {
  private encryptionKey: Buffer;
  private auditLogger: AuditLogger;

  constructor(config: SecurityConfig) {
    this.encryptionKey = this.deriveEncryptionKey(config);
    this.auditLogger = new AuditLogger(config.auditPath);
  }

  async encryptSensitiveData(data: string): Promise<string> {
    // AES-256-GCM encryption
    const cipher = createCipher("aes-256-gcm", this.encryptionKey);
    let encrypted = cipher.update(data, "utf8", "hex");
    encrypted += cipher.final("hex");

    const authTag = cipher.getAuthTag().toString("hex");
    return `${encrypted}:${authTag}`;
  }

  async validateRequest(request: IpcRequest): Promise<boolean> {
    // Request validation and audit logging
    const isValid =
      this.validateRequestStructure(request) && this.validateRequestPermissions(request);

    await this.auditLogger.logRequest(request, isValid);
    return isValid;
  }
}
```

## Performance Architecture

### Performance Optimization Layers

```python
# Performance Architecture with Caching Strategy
class PerformanceManager:
    """Multi-layer caching and performance optimization."""

    def __init__(self):
        self.memory_cache = LRUCache(maxsize=1000)
        self.disk_cache = DiskCache()
        self.db_connection_pool = ConnectionPool()

    @beartype
    async def get_cached_data(
        self,
        key: str,
        fetch_fn: Callable[[], Awaitable[Any]]
    ) -> Any:
        """Multi-layer cache lookup with fallback."""

        # L1: Memory cache (fastest)
        if key in self.memory_cache:
            return self.memory_cache[key]

        # L2: Disk cache (fast)
        disk_data = await self.disk_cache.get(key)
        if disk_data:
            self.memory_cache[key] = disk_data
            return disk_data

        # L3: Database/computation (slowest)
        fresh_data = await fetch_fn()

        # Populate caches
        self.memory_cache[key] = fresh_data
        await self.disk_cache.set(key, fresh_data)

        return fresh_data
```

### Resource Management

```javascript
// Resource Management Architecture
class ResourceManager {
  constructor() {
    this.pythonProcess = null;
    this.memoryMonitor = new MemoryMonitor();
    this.performanceMetrics = new PerformanceMetrics();
  }

  async monitorResources() {
    setInterval(async () => {
      const metrics = await this.gatherMetrics();

      if (metrics.memoryUsage > MEMORY_THRESHOLD) {
        await this.optimizeMemoryUsage();
      }

      if (metrics.cpuUsage > CPU_THRESHOLD) {
        await this.throttleCpuIntensiveTasks();
      }
    }, MONITORING_INTERVAL);
  }

  async optimizeMemoryUsage() {
    // Force garbage collection
    if (global.gc) {
      global.gc();
    }

    // Clear non-essential caches
    await this.clearNonEssentialCaches();

    // Log memory optimization
    logger.info("Memory optimization performed");
  }
}
```

## Deployment Architecture

### Application Packaging Structure

```
policy-decision-desktop/
├── app/
│   ├── main.js                 # Electron main process
│   ├── preload.js             # Security bridge
│   ├── frontend/              # Next.js static export
│   │   ├── _next/
│   │   ├── static/
│   │   └── index.html
│   └── backend/               # Python application
│       ├── main.py
│       ├── requirements.txt
│       └── modules/
├── python-runtime/            # Embedded Python
│   ├── python.exe            # (Windows)
│   ├── lib/
│   └── site-packages/
├── resources/
│   ├── app.ico
│   ├── app.icns
│   └── config/
└── package.json
```

### Cross-Platform Considerations

```yaml
# Platform-specific configurations
platforms:
  windows:
    installer: MSI
    auto_update: true
    context_menu: true
    file_associations: [".policy", ".claim"]

  macos:
    installer: DMG
    notarization: required
    app_store: optional
    universal_binary: true

  linux:
    installers: [AppImage, DEB, RPM]
    desktop_integration: true
    mime_types: ["application/x-policy"]
```

## Error Handling & Recovery

### Resilience Architecture

```python
# Error Handling Architecture
class ResilienceManager:
    """Comprehensive error handling and recovery system."""

    def __init__(self):
        self.circuit_breakers = {}
        self.retry_policies = {}
        self.fallback_strategies = {}

    @beartype
    async def execute_with_resilience(
        self,
        operation: Callable[[], Awaitable[T]],
        operation_id: str
    ) -> Result[T, str]:
        """Execute operation with circuit breaker and retry logic."""

        circuit_breaker = self.get_circuit_breaker(operation_id)

        if circuit_breaker.is_open():
            return Result.err("Circuit breaker is open")

        for attempt in range(MAX_RETRIES):
            try:
                result = await operation()
                circuit_breaker.record_success()
                return Result.ok(result)

            except Exception as e:
                circuit_breaker.record_failure()

                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (2 ** attempt))  # Exponential backoff
                    continue

                # Final attempt failed, try fallback
                fallback_result = await self.try_fallback(operation_id, e)
                return fallback_result
```

This architecture maintains **MASTER RULESET** compliance while providing a robust, scalable foundation for the desktop application conversion. The design emphasizes type safety, performance, security, and maintainability throughout all layers.
