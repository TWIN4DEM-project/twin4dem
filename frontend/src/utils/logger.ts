import type { ILogger } from "./logger.interface";
import { LogLayerAdapter } from "./loglayer.adapter";

export const logger: ILogger = new LogLayerAdapter();