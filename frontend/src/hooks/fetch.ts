import { useEffect, useState } from "react";
import axios, { type AxiosRequestConfig } from "axios";
import { z } from "zod";

type UseFetchOptions<T> = {
  url: string | null;
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
  deps = [],
}: UseFetchOptions<T>) {
  const [data, setData] = useState<T | undefined>(initialValue);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!url) return;

    (async () => {
      try {
        setLoading(true);
        setError(null);

        const res = await axios.get(url, config);
        const parsed = schema.parse(res.data);

        setData(parsed);
      } catch (e) {
        setError(e);
      } finally {
        setLoading(false);
      }
    })();
  }, [url, ...deps]);

  return { data, loading, error };
}
