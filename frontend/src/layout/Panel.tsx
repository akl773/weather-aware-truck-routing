import Paper from "@mui/material/Paper";
import type { ReactNode } from "react";

/** The share of a narrow screen's height the panel may cover, leaving the rest to the map. */
export const NARROW_PANEL_SHARE = 0.5;

/** The floating panel beside the map; full width at the top on narrow screens (ui D1). */
export function Panel({ children }: { children: ReactNode }) {
  return (
    <Paper
      component="aside"
      aria-label="Trip planner"
      elevation={0}
      sx={{
        position: "absolute",
        zIndex: 2,
        top: { xs: 0, md: 16 },
        left: { xs: 0, md: 16 },
        right: { xs: 0, md: "auto" },
        width: { md: 400 },
        maxHeight: { xs: `${NARROW_PANEL_SHARE * 100}vh`, md: "calc(100% - 32px)" },
        overflowY: "auto",
        p: 2.5,
        borderRadius: { xs: 0, md: 3 },
        border: 1,
        borderColor: "divider",
        boxShadow: "0 8px 32px rgba(15, 23, 42, 0.12)",
      }}
    >
      {children}
    </Paper>
  );
}
