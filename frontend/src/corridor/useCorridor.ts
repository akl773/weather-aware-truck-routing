import { useQuery } from "@tanstack/react-query";

import {
  type ApiError,
  type CorridorResponse,
  type PlanRequest,
  type PlanResponse,
  fetchCorridor,
} from "../api/client";

const CORRIDOR_STALE_MS = 10 * 60 * 1000;

/** The corridor's 48 hours for a plan, fetched once it arrives (corridor-heatmap D5). */
export function useCorridor(
  plan: PlanResponse | undefined,
  request: PlanRequest | null,
  /** When the plan was fetched, so a refetched plan gets a fresh corridor. */
  planFetchedAt: number,
) {
  return useQuery<CorridorResponse, ApiError>({
    queryKey: ["corridor", request, planFetchedAt],
    queryFn: ({ signal }) =>
      fetchCorridor(
        {
          paths: (plan as PlanResponse).routes.map((route) => route.path),
          departure: (request as PlanRequest).departure,
          load_lb: (request as PlanRequest).load_lb,
        },
        signal,
      ),
    enabled: Boolean(plan && request),
    staleTime: CORRIDOR_STALE_MS,
    gcTime: CORRIDOR_STALE_MS,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}
