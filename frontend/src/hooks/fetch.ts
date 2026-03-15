import axios, { type AxiosRequestConfig, type Method } from "axios";
import { useEffect, useState } from "react";
import type { z } from "zod";

type UseFetchOptions<T> = {
  url: string | null;
  method: Method;
  schema: z.ZodSchema<T>;
  config?: AxiosRequestConfig;
  initialValue?: T;
  deps?: unknown[];
};

export function useFetch<T>({
  url,
  schema,
  config,
  initialValue,
  method = "GET",
  deps = [],
}: UseFetchOptions<T>) {
  const [data, setData] = useState<T | undefined>(initialValue);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [nonce, setNonce] = useState(0);

  function refetch() {
    setNonce((n) => n + 1);
  }

  // biome-ignore lint/correctness/useExhaustiveDependencies: setting nonce retriggers the effect => refetch
  useEffect(() => {
    if (!url) return;

    (async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await axios.request({
          url,
          method,
          ...config,
        });
        const parsed = schema.parse(res.data);

        setData(parsed);
      } catch (e) {
        setError(e);
      } finally {
        setLoading(false);
      }
    })();
  }, [url, nonce, ...deps]);

  return { data, setData, loading, error, refetch };
}
