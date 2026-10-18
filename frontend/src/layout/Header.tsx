import LocalShippingOutlined from "@mui/icons-material/LocalShippingOutlined";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

export function Header() {
  return (
    <Stack direction="row" spacing={1.5} sx={{ alignItems: "center", mb: 2.5 }}>
      <Box
        sx={{
          display: "grid",
          placeItems: "center",
          width: 40,
          height: 40,
          borderRadius: 2,
          bgcolor: "primary.main",
          color: "primary.contrastText",
          flexShrink: 0,
        }}
      >
        <LocalShippingOutlined />
      </Box>
      <Box>
        <Typography component="h1" variant="subtitle1" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
          Weather-Aware Truck Routing
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Three routes, ranked by the forecast at the truck's ETA
        </Typography>
      </Box>
    </Stack>
  );
}
