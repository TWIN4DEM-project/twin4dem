import { redactionPlugin } from "@loglayer/plugin-redaction";
import type { LogLevelType } from "loglayer";
import { ConsoleTransport, LogLayer } from "loglayer";

const LOG_LEVELS = ["trace", "debug", "info", "warn", "error", "fatal"] as const;

function getLogLevel(): LogLevelType {
  const configuredLevel = import.meta.env.VITE_LOG_LEVEL;
  const defaultLevel = import.meta.env.PROD ? "error" : "trace";

  if (
    typeof configuredLevel === "string" &&
    LOG_LEVELS.some((level) => level === configuredLevel)
  ) {
    return configuredLevel as LogLevelType;
  }

  return defaultLevel;
}

export const logger = new LogLayer({
  transport: new ConsoleTransport({
    logger: console,
    level: getLogLevel(),
  }),
  plugins: [
    redactionPlugin({
      paths: [
        "password",
        "token",
        "accessToken",
        "refreshToken",
        "apiKey",
        "secret",
        "authorization",
        "cookie",
        "headers.authorization",
        "headers.cookie",
        "*.password",
        "*.token",
        "*.accessToken",
        "*.refreshToken",
        "*.apiKey",
        "*.secret",
        "*.authorization",
        "*.cookie",
        "*.headers.authorization",
        "*.headers.cookie",
      ],
      censor: "[REDACTED]",
    }),
  ],
});