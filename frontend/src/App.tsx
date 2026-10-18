import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { useQuery } from "@tanstack/react-query";

import { fetchHealth } from "./api/client";
import { MapView } from "./map/MapView";

export function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: () => fetchHealth() });

  return (
    <Box sx={{ position: "fixed", inset: 0 }}>
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
