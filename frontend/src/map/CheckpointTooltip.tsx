import Paper from "@mui/material/Paper";

import { CheckpointDetails } from "../plan/CheckpointDetails";
import type { CheckpointPick } from "./planLayers";

const OFFSET = 14;

/** Details for the checkpoint under the pointer, kept inside the window. */
export function CheckpointTooltip({ pick, x, y }: { pick: CheckpointPick; x: number; y: number }) {
  const flipX = x > window.innerWidth - 280;
  const flipY = y > window.innerHeight - 200;
  return (
    <Paper
      role="tooltip"
      elevation={6}
      sx={{
        position: "absolute",
        zIndex: 3,
        pointerEvents: "none",
        p: 1.5,
        borderRadius: 2,
        left: flipX ? undefined : x + OFFSET,
        right: flipX ? window.innerWidth - x + OFFSET : undefined,
        top: flipY ? undefined : y + OFFSET,
        bottom: flipY ? window.innerHeight - y + OFFSET : undefined,
      }}
    >
      <CheckpointDetails routeId={pick.routeId} checkpoint={pick.checkpoint} />
    </Paper>
  );
}
