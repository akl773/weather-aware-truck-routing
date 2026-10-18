import { createTheme } from "@mui/material/styles";

export const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: "#1f4e79" },
    background: { default: "#f4f5f7" },
  },
  shape: { borderRadius: 8 },
  typography: {
    fontFamily: '"Inter Variable", Inter, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
    button: { textTransform: "none", fontWeight: 600 },
  },
  components: {
    MuiTextField: { defaultProps: { size: "small" } },
    MuiAutocomplete: { defaultProps: { size: "small" } },
    MuiButton: { defaultProps: { disableElevation: true } },
  },
});
