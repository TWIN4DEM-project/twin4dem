
import { redactionPlugin } from "@loglayer/plugin-redaction";
import type { LogLevelType } from "loglayer";
import { ConsoleTransport, LogLayer } from "loglayer";
import type { ILogger, LogMetadata } from "./logger.interface";

const LOG_LEVELS = [
  "trace",
  "debug",
  "info",
  "warn",
  "error",
  "fatal",
] as const;

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

export class LogLayerAdapter implements ILogger {
  private readonly instance: LogLayer;

  constructor() {
    this.instance = new LogLayer({
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
  }

  trace(message: string, metadata?: LogMetadata): void {
    this.write("trace", message, metadata);
  }

  debug(message: string, metadata?: LogMetadata): void {
    this.write("debug", message, metadata);
  }

  info(message: string, metadata?: LogMetadata): void {
    this.write("info", message, metadata);
  }

  warn(message: string, metadata?: LogMetadata): void {
    this.write("warn", message, metadata);
  }

  error(message: string, metadata?: LogMetadata): void {
    this.write("error", message, metadata);
  }

  fatal(message: string, metadata?: LogMetadata): void {
    this.write("fatal", message, metadata);
  }

  private write(
    level: keyof ILogger,
    message: string,
    metadata?: LogMetadata,
  ): void {
    const target = metadata
      ? this.instance.withMetadata(metadata)
      : this.instance;

    target[level](message);
  }
}
