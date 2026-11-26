export type LogMetadata = Record<string, unknown>;

export interface ILogger {
  trace(message: string, metadata?: LogMetadata): void;
  debug(message: string, metadata?: LogMetadata): void;
  info(message: string, metadata?: LogMetadata): void;
  warn(message: string, metadata?: LogMetadata): void;
  error(message: string, metadata?: LogMetadata): void;
  fatal(message: string, metadata?: LogMetadata): void;
}
