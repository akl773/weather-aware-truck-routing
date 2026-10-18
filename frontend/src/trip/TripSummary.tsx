import EditOutlined from "@mui/icons-material/EditOutlined";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

import type { PlanRequest } from "../api/client";
import { formatTime } from "../format";

/** The planned trip in one glance, with the way back to the form. */
export function TripSummary({ request, onEdit }: { request: PlanRequest; onEdit: () => void }) {
  const short = (label: string) => label.replace(/, USA$/, "");
  return (
    <Stack direction="row" spacing={1} sx={{ alignItems: "flex-start" }}>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }} noWrap>
          {short(request.origin.label)} → {short(request.destination.label)}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Leaves {formatTime(request.departure)} · {request.load_lb.toLocaleString("en-US")} lb ·
          every {request.interval_mi} mi
        </Typography>
      </Box>
      <Button size="small" startIcon={<EditOutlined />} onClick={onEdit}>
        Edit
      </Button>
    </Stack>
  );
}
