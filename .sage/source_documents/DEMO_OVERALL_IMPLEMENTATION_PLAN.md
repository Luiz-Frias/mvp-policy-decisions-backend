# DEMO_OVERALL_IMPLEMENTATION_PLAN - Detailed Implementation Guide

## P&C Insurance Platform Demo

### Implementation Overview

This guide provides copy-paste ready code and exact commands to build the demo in 4 weeks. Follow sequentially for best results.

### Day 1: Project Initialization

#### Backend Setup

```bash
# Create project structure
mkdir pd-prime-demo && cd pd-prime-demo
mkdir backend frontend

# Initialize backend
cd backend
poetry new pd-prime-backend
cd pd-prime-backend

# Install dependencies
poetry add fastapi uvicorn[standard] sqlalchemy asyncpg alembic \
  pydantic pydantic-settings redis python-jose[cryptography] \
  passlib python-multipart httpx openai python-docx reportlab \
  faker python-dateutil

poetry add --group dev pytest pytest-asyncio black ruff

# Create project structure
mkdir -p app/{api,core,models,schemas,services,db}
touch app/__init__.py
touch app/{api,core,models,schemas,services,db}/__init__.py
```

#### Initial FastAPI App

```python
# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncpg
from redis import asyncio as aioredis

from app.core.config import settings
from app.api import quotes, policies, rates, auth

# Lifespan manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.db_pool = await asyncpg.create_pool(
        settings.DATABASE_URL,
        min_size=5,
        max_size=20
    )
    app.state.redis = await aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True
    )

    yield

    # Shutdown
    await app.state.db_pool.close()
    await app.state.redis.close()

# Create FastAPI app
app = FastAPI(
    title="PD Prime Insurance Demo API",
    description="Modern P&C Insurance Platform Demo",
    version="0.1.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT
    }

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(quotes.router, prefix="/api/v1/quotes", tags=["quotes"])
app.include_router(policies.router, prefix="/api/v1/policies", tags=["policies"])
app.include_router(rates.router, prefix="/api/v1/rates", tags=["rates"])
```

#### Configuration

```python
# app/core/config.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

    # OpenAI
    OPENAI_API_KEY: Optional[str] = None

    # Demo settings
    DEMO_MODE: bool = True
    DEMO_RESET_ENABLED: bool = True

    class Config:
        env_file = ".env"

settings = Settings()
```

#### Database Models

```python
# app/models/base.py
from sqlalchemy import Column, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import uuid

Base = declarative_base()

class BaseModel(Base):
    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

```python
# app/models/quote.py
from sqlalchemy import Column, String, Numeric, JSON, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel

class QuoteStatus(str, enum.Enum):
    DRAFT = "draft"
    QUOTED = "quoted"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"

class Quote(BaseModel):
    __tablename__ = "quotes"

    quote_number = Column(String(50), unique=True, nullable=False, index=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"))
    status = Column(Enum(QuoteStatus), default=QuoteStatus.DRAFT)

    # Flexible quote data for demo
    quote_data = Column(JSON, nullable=False)

    # Calculated premium
    premium = Column(Numeric(10, 2))
    monthly_premium = Column(Numeric(10, 2))

    # Relationships
    customer = relationship("Customer", back_populates="quotes")
    policy = relationship("Policy", back_populates="quote", uselist=False)
```

### Day 2: Frontend Setup

```bash
# Frontend initialization
cd ../../frontend
npx create-next-app@latest pd-prime-frontend --typescript --tailwind --app

cd pd-prime-frontend

# Install dependencies
npm install @radix-ui/react-accordion @radix-ui/react-alert-dialog \
  @radix-ui/react-dialog @radix-ui/react-dropdown-menu @radix-ui/react-select \
  @radix-ui/react-tabs @radix-ui/react-toast @tanstack/react-query \
  @tanstack/react-table react-hook-form @hookform/resolvers zod \
  clsx tailwind-merge date-fns lucide-react recharts \
  next-auth axios

# Install dev dependencies
npm install -D @types/node

# Setup shadcn/ui
npx shadcn-ui@latest init
# Choose: TypeScript, yes to CSS variables, default for everything else

# Add components
npx shadcn-ui@latest add button card dialog form input label \
  select table tabs toast alert badge
```

#### App Layout

```tsx
// app/layout.tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";
import { Toaster } from "@/components/ui/toaster";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "PD Prime - Modern Insurance Platform",
  description: "Next-generation P&C insurance management",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <Providers>
          {children}
          <Toaster />
        </Providers>
      </body>
    </html>
  );
}
```

```tsx
// components/providers.tsx
"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SessionProvider } from "next-auth/react";
import { ThemeProvider } from "next-themes";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return (
    <SessionProvider>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          {children}
        </ThemeProvider>
      </QueryClientProvider>
    </SessionProvider>
  );
}
```

### Day 3: Database Setup & Auth

#### Database Migrations

```python
# alembic.ini setup (in backend)
# Update sqlalchemy.url with your DATABASE_URL

# Create first migration
alembic init alembic
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

```sql
-- SQL Schema (generated by Alembic)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    state VARCHAR(2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE quotes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quote_number VARCHAR(50) UNIQUE NOT NULL,
    customer_id UUID REFERENCES customers(id),
    status VARCHAR(20) DEFAULT 'draft',
    quote_data JSONB NOT NULL,
    premium NUMERIC(10, 2),
    monthly_premium NUMERIC(10, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE policies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    policy_number VARCHAR(50) UNIQUE NOT NULL,
    quote_id UUID REFERENCES quotes(id),
    customer_id UUID REFERENCES customers(id),
    policy_data JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    effective_date DATE NOT NULL,
    expiration_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE rate_tables (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) UNIQUE NOT NULL,
    version VARCHAR(20) NOT NULL,
    table_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100)
);

-- Indexes
CREATE INDEX idx_quotes_customer ON quotes(customer_id);
CREATE INDEX idx_quotes_status ON quotes(status);
CREATE INDEX idx_policies_customer ON policies(customer_id);
CREATE INDEX idx_quotes_data ON quotes USING GIN (quote_data);
```

#### Authentication Implementation

```python
# app/core/auth.py
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# Demo users (in production, these would be in database)
DEMO_USERS = {
    "agent@demo.com": {
        "username": "agent@demo.com",
        "hashed_password": pwd_context.hash("demo123"),
        "role": "agent",
        "full_name": "Demo Agent"
    },
    "underwriter@demo.com": {
        "username": "underwriter@demo.com",
        "hashed_password": pwd_context.hash("demo123"),
        "role": "underwriter",
        "full_name": "Demo Underwriter"
    },
    "admin@demo.com": {
        "username": "admin@demo.com",
        "hashed_password": pwd_context.hash("demo123"),
        "role": "admin",
        "full_name": "Demo Admin"
    }
}

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = DEMO_USERS.get(username)
    if user is None:
        raise credentials_exception
    return user
```

### Day 4: Core API Implementation

#### Quote API

```python
# app/api/quotes.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from uuid import UUID
import asyncpg
from datetime import datetime, timedelta

from app.core.auth import get_current_user
from app.schemas.quote import QuoteCreate, QuoteResponse, QuoteUpdate
from app.services.rating_engine import RatingEngine
from app.core.deps import get_db_pool, get_redis

router = APIRouter()

@router.post("/", response_model=QuoteResponse)
async def create_quote(
    quote_data: QuoteCreate,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_db_pool),
    redis = Depends(get_redis)
):
    """Create a new insurance quote"""
    async with db_pool.acquire() as conn:
        # Generate quote number
        quote_number = f"Q-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Calculate premium using rating engine
        rating_engine = RatingEngine(db_pool, redis)
        premium_calc = await rating_engine.calculate_premium(quote_data.dict())

        # Insert quote
        quote_id = await conn.fetchval(
            """
            INSERT INTO quotes (quote_number, customer_id, status, quote_data, premium, monthly_premium, expires_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            quote_number,
            quote_data.customer_id,
            'quoted',
            quote_data.dict(),
            premium_calc.total_premium,
            premium_calc.total_premium / 12,
            datetime.now() + timedelta(days=30)
        )

        # Fetch and return created quote
        quote = await conn.fetchrow(
            "SELECT * FROM quotes WHERE id = $1",
            quote_id
        )

        return QuoteResponse(
            **dict(quote),
            premium_breakdown=premium_calc.breakdown
        )

@router.get("/{quote_id}", response_model=QuoteResponse)
async def get_quote(
    quote_id: UUID,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_db_pool)
):
    """Get quote details"""
    async with db_pool.acquire() as conn:
        quote = await conn.fetchrow(
            "SELECT * FROM quotes WHERE id = $1",
            quote_id
        )

        if not quote:
            raise HTTPException(status_code=404, detail="Quote not found")

        return QuoteResponse(**dict(quote))

@router.get("/", response_model=List[QuoteResponse])
async def list_quotes(
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_db_pool)
):
    """List quotes with filtering"""
    async with db_pool.acquire() as conn:
        query = "SELECT * FROM quotes"
        params = []

        if status:
            query += " WHERE status = $1"
            params.append(status)

        query += f" ORDER BY created_at DESC LIMIT ${len(params)+1} OFFSET ${len(params)+2}"
        params.extend([limit, skip])

        quotes = await conn.fetch(query, *params)

        return [QuoteResponse(**dict(quote)) for quote in quotes]
```

#### Rating Engine Service

```python
# app/services/rating_engine.py
from typing import Dict, Any, List
from decimal import Decimal
import json
from dataclasses import dataclass

@dataclass
class PremiumCalculation:
    base_premium: float
    factors: Dict[str, float]
    total_premium: float
    breakdown: Dict[str, float]

class RatingEngine:
    """Demo rating engine with realistic calculations"""

    def __init__(self, db_pool, redis):
        self.db_pool = db_pool
        self.redis = redis

    async def calculate_premium(self, quote_data: Dict[str, Any]) -> PremiumCalculation:
        """Calculate insurance premium based on various factors"""

        # Base rates by coverage type
        base_rates = {
            "auto": 1200,
            "home": 1500,
            "commercial": 2500
        }

        base_premium = base_rates.get(quote_data.get("policy_type"), 1000)

        # Calculate factors
        factors = {}

        # Territory factor
        territory_factor = await self._get_territory_factor(
            quote_data.get("state"),
            quote_data.get("zip_code")
        )
        factors["territory"] = territory_factor

        # Vehicle/Property specific factors
        if quote_data.get("policy_type") == "auto":
            vehicle_factor = self._calculate_vehicle_factor(quote_data.get("vehicle", {}))
            factors["vehicle"] = vehicle_factor

            driver_factor = self._calculate_driver_factor(quote_data.get("driver", {}))
            factors["driver"] = driver_factor

        # Coverage level factor
        coverage_factor = self._get_coverage_factor(quote_data.get("coverage_level", "standard"))
        factors["coverage"] = coverage_factor

        # AI risk score (mock for demo)
        risk_score = await self._get_ai_risk_score(quote_data)
        factors["ai_risk"] = 1.0 + (risk_score * 0.1)

        # Calculate total
        total_factor = 1.0
        for factor_value in factors.values():
            total_factor *= factor_value

        total_premium = base_premium * total_factor

        # Create breakdown
        breakdown = {
            "base_premium": base_premium,
            "territory_adjustment": base_premium * (factors["territory"] - 1),
            "risk_adjustment": base_premium * (factors.get("ai_risk", 1) - 1),
            "total_premium": total_premium
        }

        if "vehicle" in factors:
            breakdown["vehicle_adjustment"] = base_premium * (factors["vehicle"] - 1)
        if "driver" in factors:
            breakdown["driver_adjustment"] = base_premium * (factors["driver"] - 1)

        return PremiumCalculation(
            base_premium=base_premium,
            factors=factors,
            total_premium=round(total_premium, 2),
            breakdown={k: round(v, 2) for k, v in breakdown.items()}
        )

    async def _get_territory_factor(self, state: str, zip_code: str) -> float:
        """Get territory-based rating factor"""
        # Check cache first
        cache_key = f"territory:{state}:{zip_code}"
        cached = await self.redis.get(cache_key)
        if cached:
            return float(cached)

        # Mock territory factors for demo
        state_factors = {
            "CA": 1.2,
            "NY": 1.3,
            "TX": 1.1,
            "FL": 1.4,
            "IL": 1.15
        }

        factor = state_factors.get(state, 1.0)

        # Cache for 1 hour
        await self.redis.setex(cache_key, 3600, str(factor))

        return factor

    def _calculate_vehicle_factor(self, vehicle: Dict) -> float:
        """Calculate vehicle-based factor"""
        factors = 1.0

        # Vehicle type
        vehicle_type_factors = {
            "sedan": 1.0,
            "suv": 1.2,
            "truck": 1.15,
            "sports": 1.5,
            "luxury": 1.4
        }
        factors *= vehicle_type_factors.get(vehicle.get("type"), 1.0)

        # Vehicle age
        age = 2024 - vehicle.get("year", 2020)
        if age < 1:
            factors *= 1.1  # New car
        elif age > 10:
            factors *= 0.9  # Older car discount

        return factors

    def _calculate_driver_factor(self, driver: Dict) -> float:
        """Calculate driver-based factor"""
        factors = 1.0

        # Age factor
        age = driver.get("age", 30)
        if age < 25:
            factors *= 1.5
        elif age > 60:
            factors *= 1.1

        # Driving record
        violations = driver.get("violations", 0)
        factors *= (1.0 + violations * 0.2)

        return factors

    def _get_coverage_factor(self, coverage_level: str) -> float:
        """Get coverage level factor"""
        coverage_factors = {
            "basic": 0.8,
            "standard": 1.0,
            "premium": 1.3,
            "comprehensive": 1.5
        }
        return coverage_factors.get(coverage_level, 1.0)

    async def _get_ai_risk_score(self, quote_data: Dict) -> float:
        """Mock AI risk scoring"""
        # In real implementation, this would call an ML model
        # For demo, return a realistic but random score
        import random
        return random.uniform(-0.2, 0.3)  # -20% to +30% adjustment
```

### Day 5: Frontend Quote Flow

#### Quote Creation Wizard

```tsx
// app/(dashboard)/quotes/new/page.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/use-toast";
import { Loader2 } from "lucide-react";

// Form schemas
const customerSchema = z.object({
  name: z.string().min(2, "Name is required"),
  email: z.string().email("Invalid email"),
  phone: z.string().min(10, "Valid phone required"),
  state: z.string().length(2, "Select a state"),
});

const autoQuoteSchema = z.object({
  vehicle_year: z.number().min(1900).max(2025),
  vehicle_make: z.string().min(1),
  vehicle_model: z.string().min(1),
  vehicle_type: z.enum(["sedan", "suv", "truck", "sports", "luxury"]),
  coverage_level: z.enum(["basic", "standard", "premium", "comprehensive"]),
});

export default function NewQuotePage() {
  const router = useRouter();
  const { toast } = useToast();
  const [step, setStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [customerData, setCustomerData] = useState({});

  const customerForm = useForm({
    resolver: zodResolver(customerSchema),
    defaultValues: {
      name: "",
      email: "",
      phone: "",
      state: "",
    },
  });

  const quoteForm = useForm({
    resolver: zodResolver(autoQuoteSchema),
    defaultValues: {
      vehicle_year: 2022,
      vehicle_make: "",
      vehicle_model: "",
      vehicle_type: "sedan",
      coverage_level: "standard",
    },
  });

  const onCustomerSubmit = (data: any) => {
    setCustomerData(data);
    setStep(2);
  };

  const onQuoteSubmit = async (data: any) => {
    setIsSubmitting(true);

    try {
      const quoteData = {
        ...customerData,
        policy_type: "auto",
        vehicle: {
          year: data.vehicle_year,
          make: data.vehicle_make,
          model: data.vehicle_model,
          type: data.vehicle_type,
        },
        coverage_level: data.coverage_level,
      };

      const response = await fetch("/api/quotes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(quoteData),
      });

      if (!response.ok) throw new Error("Failed to create quote");

      const quote = await response.json();

      toast({
        title: "Quote Created!",
        description: `Quote ${quote.quote_number} has been created successfully.`,
      });

      router.push(`/quotes/${quote.id}`);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to create quote. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="container max-w-2xl py-8">
      <Card>
        <CardHeader>
          <CardTitle>Create New Quote</CardTitle>
          <CardDescription>
            Step {step} of 2: {step === 1 ? "Customer Information" : "Vehicle & Coverage"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {step === 1 ? (
            <Form {...customerForm}>
              <form onSubmit={customerForm.handleSubmit(onCustomerSubmit)} className="space-y-4">
                <FormField
                  control={customerForm.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Full Name</FormLabel>
                      <FormControl>
                        <Input placeholder="John Doe" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={customerForm.control}
                  name="email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Email</FormLabel>
                      <FormControl>
                        <Input type="email" placeholder="john@example.com" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={customerForm.control}
                  name="phone"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Phone</FormLabel>
                      <FormControl>
                        <Input placeholder="(555) 123-4567" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={customerForm.control}
                  name="state"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>State</FormLabel>
                      <Select onValueChange={field.onChange} defaultValue={field.value}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Select a state" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="CA">California</SelectItem>
                          <SelectItem value="NY">New York</SelectItem>
                          <SelectItem value="TX">Texas</SelectItem>
                          <SelectItem value="FL">Florida</SelectItem>
                          <SelectItem value="IL">Illinois</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <Button type="submit" className="w-full">
                  Continue to Vehicle Details
                </Button>
              </form>
            </Form>
          ) : (
            <Form {...quoteForm}>
              <form onSubmit={quoteForm.handleSubmit(onQuoteSubmit)} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <FormField
                    control={quoteForm.control}
                    name="vehicle_year"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Year</FormLabel>
                        <FormControl>
                          <Input
                            type="number"
                            {...field}
                            onChange={(e) => field.onChange(parseInt(e.target.value))}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={quoteForm.control}
                    name="vehicle_make"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Make</FormLabel>
                        <FormControl>
                          <Input placeholder="Tesla" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                <FormField
                  control={quoteForm.control}
                  name="vehicle_model"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Model</FormLabel>
                      <FormControl>
                        <Input placeholder="Model 3" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={quoteForm.control}
                  name="vehicle_type"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Vehicle Type</FormLabel>
                      <Select onValueChange={field.onChange} defaultValue={field.value}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="sedan">Sedan</SelectItem>
                          <SelectItem value="suv">SUV</SelectItem>
                          <SelectItem value="truck">Truck</SelectItem>
                          <SelectItem value="sports">Sports Car</SelectItem>
                          <SelectItem value="luxury">Luxury</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={quoteForm.control}
                  name="coverage_level"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Coverage Level</FormLabel>
                      <Select onValueChange={field.onChange} defaultValue={field.value}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="basic">Basic</SelectItem>
                          <SelectItem value="standard">Standard</SelectItem>
                          <SelectItem value="premium">Premium</SelectItem>
                          <SelectItem value="comprehensive">Comprehensive</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <div className="flex gap-4">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setStep(1)}
                    className="w-full"
                  >
                    Back
                  </Button>
                  <Button type="submit" className="w-full" disabled={isSubmitting}>
                    {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    Generate Quote
                  </Button>
                </div>
              </form>
            </Form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

### Railway Deployment (Day 5)

```toml
# railway.toml (in backend directory)
[build]
builder = "NIXPACKS"
buildCommand = "poetry install"

[deploy]
startCommand = "poetry run uvicorn app.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

```bash
# Deploy to Railway
cd backend/pd-prime-backend
railway login
railway link  # Select your project or create new
railway up

# Set environment variables in Railway dashboard:
# - DATABASE_URL (auto-set if using Railway Postgres)
# - REDIS_URL (auto-set if using Railway Redis)
# - SECRET_KEY (generate a secure key)
# - FRONTEND_URL (your Vercel URL once deployed)
```

### Vercel Deployment (Day 5)

```bash
# Deploy frontend to Vercel
cd frontend/pd-prime-frontend
vercel

# Follow prompts:
# - Link to existing project or create new
# - Set environment variables:
#   - NEXT_PUBLIC_API_URL: Your Railway backend URL
#   - NEXTAUTH_SECRET: Generate secure secret
#   - NEXTAUTH_URL: Your Vercel app URL
```

## Week 2-4 Implementation Highlights

Due to space constraints, here are the key patterns for the remaining features:

### AI Integration (Week 3)

```python
# app/services/ai_service.py
from openai import OpenAI
import json

class AIService:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    async def analyze_document(self, document_text: str):
        """Extract key information from documents"""
        prompt = f"""
        Extract the following from this insurance document:
        1. Driver name and license number
        2. Vehicle information
        3. Driving violations
        4. Previous claims

        Document: {document_text}

        Return as JSON.
        """

        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": prompt}],
            response_format={"type": "json_object"}
        )

        return json.loads(response.choices[0].message.content)
```

### Real-time Dashboard (Week 3)

```tsx
// components/dashboard/metrics.tsx
"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export function DashboardMetrics() {
  const [metrics, setMetrics] = useState({
    quotesToday: 0,
    conversionRate: 0,
    avgPremium: 0,
  });

  useEffect(() => {
    // WebSocket connection for real-time updates
    const ws = new WebSocket(`${process.env.NEXT_PUBLIC_WS_URL}/ws/metrics`);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setMetrics(data);
    };

    return () => ws.close();
  }, []);

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardHeader>
          <CardTitle>Quotes Today</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{metrics.quotesToday}</div>
        </CardContent>
      </Card>
      {/* More metric cards... */}
    </div>
  );
}
```

### Demo Data Seeder

```python
# scripts/seed_demo_data.py
from faker import Faker
import asyncio
import asyncpg
from datetime import datetime, timedelta
import random

fake = Faker()

async def seed_demo_data():
    conn = await asyncpg.connect(DATABASE_URL)

    # Create customers
    customers = []
    for _ in range(100):
        customer_id = await conn.fetchval(
            """
            INSERT INTO customers (email, name, phone, state)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            fake.email(),
            fake.name(),
            fake.phone_number(),
            random.choice(['CA', 'NY', 'TX', 'FL', 'IL'])
        )
        customers.append(customer_id)

    # Create quotes
    for _ in range(200):
        quote_data = {
            "policy_type": "auto",
            "vehicle": {
                "year": random.randint(2015, 2024),
                "make": random.choice(["Tesla", "Toyota", "Ford", "BMW"]),
                "model": fake.word(),
                "type": random.choice(["sedan", "suv", "truck"])
            },
            "coverage_level": random.choice(["basic", "standard", "premium"])
        }

        await conn.execute(
            """
            INSERT INTO quotes (quote_number, customer_id, status, quote_data, premium)
            VALUES ($1, $2, $3, $4, $5)
            """,
            f"Q-{fake.random_number(digits=8)}",
            random.choice(customers),
            random.choice(['draft', 'quoted', 'accepted', 'expired']),
            quote_data,
            random.uniform(800, 3000)
        )

    await conn.close()
    print("Demo data seeded successfully!")

if __name__ == "__main__":
    asyncio.run(seed_demo_data())
```

## Final Demo Checklist

### Technical Readiness

- [ ] All APIs return <2s response time
- [ ] Frontend loads in <3s
- [ ] Authentication works smoothly
- [ ] No console errors in browser
- [ ] Mobile responsive design works
- [ ] Demo data looks realistic
- [ ] AI features have fallbacks

### Demo Flow

- [ ] Can create account (or use demo login)
- [ ] Can create quote in <1 minute
- [ ] Premium calculation impresses
- [ ] Can bind policy instantly
- [ ] Dashboard shows live metrics
- [ ] AI document analysis wows
- [ ] Rate management looks powerful

### Backup Plans

- [ ] Local environment ready
- [ ] Backup deployment on Render
- [ ] Screenshots/video prepared
- [ ] Offline demo possible
- [ ] Key talking points memorized

---

**Implementation Motto**: "Make it work, make it right, make it fast"

**Remember**: The goal is a compelling demo, not production code. Focus on what will impress your audience!
