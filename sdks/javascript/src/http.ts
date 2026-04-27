// ===============================================
// Veritera Forge Verify SDK — HTTP Client
// ===============================================
// Enterprise-grade HTTP layer with retry, backoff, circuit breaker,
// and idempotency support. Zero external dependencies.

import { ForgeError, RateLimitError } from "./types.js";

export interface HttpConfig {
  baseUrl: string;
  apiKey: string;
  timeout: number;
  maxRetries: number;
  debug: boolean;
}

interface RequestOptions {
  method: "GET" | "POST" | "PUT" | "DELETE";
  path: string;
  body?: unknown;
  headers?: Record<string, string>;
  idempotencyKey?: string;
}

// Circuit breaker state
let consecutiveFailures = 0;
let circuitOpenUntil = 0;
const CIRCUIT_BREAKER_THRESHOLD = 5;
const CIRCUIT_BREAKER_RESET_MS = 30_000;

function isCircuitOpen(): boolean {
  if (consecutiveFailures < CIRCUIT_BREAKER_THRESHOLD) return false;
  if (Date.now() > circuitOpenUntil) {
    // Half-open: allow one request through
    consecutiveFailures = CIRCUIT_BREAKER_THRESHOLD - 1;
    return false;
  }
  return true;
}

function recordSuccess(): void {
  consecutiveFailures = 0;
}

function recordFailure(): void {
  consecutiveFailures++;
  if (consecutiveFailures >= CIRCUIT_BREAKER_THRESHOLD) {
    circuitOpenUntil = Date.now() + CIRCUIT_BREAKER_RESET_MS;
  }
}

/** Calculate exponential backoff with jitter */
function backoffMs(attempt: number): number {
  const base = Math.min(1000 * Math.pow(2, attempt), 10_000);
  const jitter = Math.random() * base * 0.3;
  return base + jitter;
}

export async function httpRequest<T>(config: HttpConfig, options: RequestOptions): Promise<T> {
  if (isCircuitOpen()) {
    throw new ForgeError(
      "Forge API circuit breaker is open — too many consecutive failures. Will retry automatically.",
      "circuit_open",
      503,
    );
  }

  const url = `${config.baseUrl}${options.path}`;
  const sdkVersion = "1.2.0";
  const environment = typeof process !== "undefined" ? (process.env.NODE_ENV ?? "production") : "browser";
  const headers: Record<string, string> = {
    "Authorization": `Bearer ${config.apiKey}`,
    "Content-Type": "application/json",
    "User-Agent": `forge-verify-js/${sdkVersion}`,
    "X-Forge-SDK-Version": sdkVersion,
    "X-Forge-Environment": environment,
    "X-Forge-Timestamp": new Date().toISOString(),
    ...options.headers,
  };

  if (options.idempotencyKey) {
    headers["Idempotency-Key"] = options.idempotencyKey;
  }

  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= config.maxRetries; attempt++) {
    if (attempt > 0) {
      const delay = backoffMs(attempt - 1);
      if (config.debug) {
        console.log(`[Forge Verify] Retry ${attempt}/${config.maxRetries} after ${Math.round(delay)}ms`);
      }
      await new Promise(resolve => setTimeout(resolve, delay));
    }

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), config.timeout);

      const response = await fetch(url, {
        method: options.method,
        headers,
        body: options.body ? JSON.stringify(options.body) : undefined,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      // Rate limit — don't retry
      if (response.status === 429) {
        recordFailure();
        const retryAfter = parseInt(response.headers.get("Retry-After") ?? "60", 10) * 1000;
        throw new RateLimitError("Rate limit exceeded", retryAfter);
      }

      // Client errors (4xx except 429) — don't retry
      if (response.status >= 400 && response.status < 500) {
        recordSuccess(); // server is responding, just rejecting our request
        const errorBody = await response.json().catch(() => ({}));
        throw new ForgeError(
          (errorBody as any)?.message ?? `Request failed with status ${response.status}`,
          (errorBody as any)?.error ?? "client_error",
          response.status,
          errorBody,
        );
      }

      // Server errors (5xx) — retry
      if (response.status >= 500) {
        recordFailure();
        lastError = new ForgeError(
          `Server error: ${response.status}`,
          "server_error",
          response.status,
        );
        continue; // retry
      }

      // Success
      recordSuccess();
      const data = await response.json();
      return data as T;

    } catch (err) {
      if (err instanceof ForgeError) {
        // Don't retry client errors or rate limits
        if (err.status >= 400 && err.status < 500) throw err;
        lastError = err;
        continue;
      }
      if (err instanceof Error && err.name === "AbortError") {
        recordFailure();
        lastError = new ForgeError("Request timed out", "timeout", 408);
        continue;
      }
      recordFailure();
      lastError = err instanceof Error ? err : new Error(String(err));
      continue;
    }
  }

  throw lastError ?? new ForgeError("Request failed after retries", "max_retries", 503);
}
