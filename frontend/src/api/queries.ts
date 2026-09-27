import { MutationCache, QueryCache, QueryClient, useQuery } from "@tanstack/react-query";

import { ApiError, api } from "./client";
import { isPending, type PaperDocument } from "./types";

export const keys = {
  config: ["config"] as const,
  me: ["me"] as const,
  documents: ["documents"] as const,
  document: (id: string) => ["documents", id] as const,
};

export function createQueryClient(): QueryClient {
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({ onError: (error) => handleUnauthorized(client, error) }),
    mutationCache: new MutationCache({ onError: (error) => handleUnauthorized(client, error) }),
    defaultOptions: {
      queries: {
        refetchOnWindowFocus: true,
        retry: (failures, error) => {
          const clientError = error instanceof ApiError && error.status >= 400 && error.status < 500;
          return !clientError && failures < 2;
        },
      },
    },
  });
  return client;
}

/** A session that expires mid-use sends the user back to the sign-in page instead of showing errors everywhere. */
function handleUnauthorized(client: QueryClient, error: unknown) {
  if (error instanceof ApiError && error.status === 401) client.setQueryData(keys.me, null);
}

export function useConfig() {
  return useQuery({ queryKey: keys.config, queryFn: api.config, staleTime: Infinity });
}

export function useMe() {
  return useQuery({ queryKey: keys.me, queryFn: api.me, staleTime: 5 * 60_000 });
}

export function useDocuments() {
  return useQuery({
    queryKey: keys.documents,
    queryFn: api.listDocuments,
    refetchInterval: (query) => (query.state.data?.some((doc) => isPending(doc.status)) ? 3_000 : false),
  });
}

/** Polls while the document is being processed, backing off gradually up to 10 seconds. */
export function pollDelay(document: PaperDocument | undefined, updates: number): number | false {
  if (!document || !isPending(document.status)) return false;
  return Math.min(Math.round(1_500 * 1.25 ** updates), 10_000);
}

export function useSearch(id: string, query: string) {
  const trimmed = query.trim();
  return useQuery({
    queryKey: [...keys.document(id), "search", trimmed] as const,
    queryFn: () => api.search(id, trimmed),
    enabled: trimmed.length > 1,
    staleTime: 60_000,
    placeholderData: (previous) => previous, // keep old hits visible while the next query runs
  });
}

export function useDocument(id: string) {
  return useQuery({
    queryKey: keys.document(id),
    queryFn: () => api.getDocument(id),
    refetchInterval: (query) => pollDelay(query.state.data, query.state.dataUpdateCount),
  });
}
