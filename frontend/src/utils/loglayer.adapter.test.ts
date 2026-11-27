import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ILogger } from "./logger.interface";

const consoleMethods = ["log", "debug", "info", "warn", "error", "trace"] as const;

function captureLogs() {
  const spies = consoleMethods.map((method) =>
    vi.spyOn(console, method).mockImplementation(() => {}),
  );

  return () =>
    spies
      .flatMap((spy) => spy.mock.calls)
      .map((args) =>
        args
          .map((arg) => {
            if (typeof arg === "string") {
              return arg;
            }

            try {
              return JSON.stringify(arg);
            } catch {
              return "[Unserializable object]";
            }
          })
          .join(" "),
      )
      .join("\n");
}

async function createLogger(): Promise<ILogger> {
  const { LogLayerAdapter } = await import("./loglayer.adapter");
  return new LogLayerAdapter();
}

describe("LogLayerAdapter", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  });

  it("logs all levels in development", async () => {
    vi.stubEnv("PROD", false);
    vi.stubEnv("VITE_LOG_LEVEL", undefined);

    const getOutput = captureLogs();
    const logger = await createLogger();

    logger.trace("Trace test");
    logger.debug("Debug test");
    logger.info("Info test");
    logger.warn("Warning test");
    logger.error("Error test");

    const output = getOutput();

    expect(output).toContain("Trace test");
    expect(output).toContain("Debug test");
    expect(output).toContain("Info test");
    expect(output).toContain("Warning test");
    expect(output).toContain("Error test");
  });

  it("logs only errors and above in production", async () => {
    vi.stubEnv("PROD", true);
    vi.stubEnv("VITE_LOG_LEVEL", undefined);

    const getOutput = captureLogs();
    const logger = await createLogger();

    logger.trace("Hidden trace");
    logger.debug("Hidden debug");
    logger.info("Hidden info");
    logger.warn("Hidden warning");
    logger.error("Visible error");

    const output = getOutput();

    expect(output).not.toContain("Hidden trace");
    expect(output).not.toContain("Hidden debug");
    expect(output).not.toContain("Hidden info");
    expect(output).not.toContain("Hidden warning");
    expect(output).toContain("Visible error");
  });

  it("allows configuring the minimum log level at build time", async () => {
    vi.stubEnv("PROD", false);
    vi.stubEnv("VITE_LOG_LEVEL", "warn");

    const getOutput = captureLogs();
    const logger = await createLogger();

    logger.debug("Hidden debug");
    logger.info("Hidden info");
    logger.warn("Visible warning");
    logger.error("Visible error");

    const output = getOutput();

    expect(output).not.toContain("Hidden debug");
    expect(output).not.toContain("Hidden info");
    expect(output).toContain("Visible warning");
    expect(output).toContain("Visible error");
  });

  it("redacts passwords and tokens", async () => {
    vi.stubEnv("PROD", false);
    vi.stubEnv("VITE_LOG_LEVEL", undefined);

    const getOutput = captureLogs();
    const logger = await createLogger();

    logger.info("Authentication event", {
      username: "test-user",
      password: "secret123",
      token: "abc123",
    });

    const output = getOutput();

    expect(output).toContain("test-user");
    expect(output).toContain("[REDACTED]");
    expect(output).not.toContain("secret123");
    expect(output).not.toContain("abc123");
  });

  it("supports structured metadata", async () => {
    vi.stubEnv("PROD", false);
    vi.stubEnv("VITE_LOG_LEVEL", undefined);

    const getOutput = captureLogs();
    const logger = await createLogger();

    logger.error("Simulation failed", {
      simulationId: 42,
      errorType: "NetworkError",
    });

    const output = getOutput();

    expect(output).toContain("Simulation failed");
    expect(output).toContain("42");
    expect(output).toContain("NetworkError");
  });
});
