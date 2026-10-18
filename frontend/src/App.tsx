import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { type PlanRequest, fetchHealth } from "./api/client";
import { Header } from "./layout/Header";
import { Panel } from "./layout/Panel";
import { MapView } from "./map/MapView";
import { usePlan } from "./plan/usePlan";
import { TripForm } from "./trip/TripForm";

export function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: () => fetchHealth() });
  const [request, setRequest] = useState<PlanRequest | null>(null);
  const plan = usePlan(request);

  return (
    <Box sx={{ position: "fixed", inset: 0 }}>
      <Panel>
        <Header />
        <TripForm
          onSubmit={(next) => {
            // Asking again for a plan that failed or has gone stale fetches it; the query would not.
            const same = JSON.stringify(next) === JSON.stringify(request);
            if (same && (plan.isError || plan.isStale)) plan.refetch();
            setRequest(next);
          }}
          pending={plan.isFetching}
          error={plan.error?.message ?? null}
        />
        {plan.data ? (
          <Typography variant="body2" sx={{ mt: 2 }} role="status">
            {plan.data.routes.length} routes. Route {plan.data.recommendation.route_id} is
            recommended: {plan.data.recommendation.reason}
          </Typography>
        ) : null}
      </Panel>
      {/* After the panel, so keyboard users reach the form before the map. */}
      <MapView />
      <Typography
        component="footer"
        variant="caption"
        color="text.secondary"
        sx={{ position: "absolute", left: 8, bottom: 4, pointerEvents: "none" }}
      >
        {health.data ? `build ${health.data.version}` : "API unreachable"}
      </Typography>
    </Box>
  );
}
