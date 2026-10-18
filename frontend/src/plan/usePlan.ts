import { useQuery } from "@tanstack/react-query";

import { type ApiError, type PlanRequest, type PlanResponse, planTrip } from "../api/client";

const PLAN_STALE_MS = 10 * 60 * 1000;

/** The plan for `request`, cached per exact request and never retried on its own (ui D5). */
export function usePlan(request: PlanRequest | null) {
  return useQuery<PlanResponse, ApiError>({
    queryKey: ["plan", request],
    queryFn: ({ signal }) => planTrip(request as PlanRequest, signal),
    enabled: request !== null,
    staleTime: PLAN_STALE_MS,
    gcTime: PLAN_STALE_MS,
    retry: false,
  });
}
