import { useCallback, useEffect, useRef } from "react";
import type { Action } from "@/types/action.ts";

type Options = {
  reconnectDelayMs?: number;
};

export function useWebSocketStream<T>(url: string | null, options: Options = {}) {
  const { reconnectDelayMs = 1000 } = options;

  const socketRef = useRef<WebSocket | null>(null);
  const queueRef = useRef<T[]>([]);
  const resolversRef = useRef<((value: IteratorResult<T>) => void)[]>([]);
  const reconnectTimerRef = useRef<number | null>(null);
  const closedRef = useRef(false);

  const connect = useCallback(() => {
    if (!url || closedRef.current) return;

    const ws = new WebSocket(url);
    socketRef.current = ws;

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data) as T;

      const resolver = resolversRef.current.shift();
      if (resolver) {
        resolver({ value: data, done: false });
      } else {
        queueRef.current.push(data);
      }
    };

    ws.onclose = () => {
      if (closedRef.current) return;

      reconnectTimerRef.current = window.setTimeout(connect, reconnectDelayMs);
    };
  }, [url, reconnectDelayMs]);

  useEffect(() => {
    closedRef.current = false;
    connect();

    return () => {
      closedRef.current = true;
      if (socketRef.current !== null) {
        if (!(socketRef.current.readyState in [WebSocket.CLOSED, WebSocket.CLOSING])) {
          socketRef.current?.close();
        }
        socketRef.current = null;
      }

      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }

      // terminate async iterators
      resolversRef.current.forEach((r) => {
        r({ value: undefined as never, done: true });
      });
      resolversRef.current = [];
      queueRef.current = [];
    };
  }, [connect]);

  const send = useCallback((action: Action) => {
    socketRef.current?.send(JSON.stringify(action));
  }, []);

  const stream = {
    async *[Symbol.asyncIterator](): AsyncIterator<T> {
      while (true) {
        if (queueRef.current.length > 0) {
          const value = queueRef.current.shift();
          if (value !== null && typeof value !== "undefined") {
            yield value;
          }
          continue;
        }

        const value = await new Promise<IteratorResult<T>>((resolve) => {
          resolversRef.current.push(resolve);
        });

        if (value.done) return;
        yield value.value;
      }
    },
  };

  return { send, stream };
}
