import SwapVert from "@mui/icons-material/SwapVert";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import FormControl from "@mui/material/FormControl";
import FormLabel from "@mui/material/FormLabel";
import IconButton from "@mui/material/IconButton";
import InputAdornment from "@mui/material/InputAdornment";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Tooltip from "@mui/material/Tooltip";
import { type FormEvent, useRef, useState } from "react";

import type { PlanRequest } from "../api/client";
import { zoneName } from "../format";
import { PlaceField } from "./PlaceField";
import {
  DEPARTURE_AHEAD_MS,
  DEPARTURE_PAST_MS,
  FIELD_ORDER,
  INTERVALS_MI,
  type TripDraft,
  type TripField,
  defaultDraft,
  toLocalInput,
  validateTrip,
} from "./draft";

interface TripFormProps {
  onSubmit: (request: PlanRequest) => void;
  pending: boolean;
  error: string | null;
}

export function TripForm({ onSubmit, pending, error }: TripFormProps) {
  const [draft, setDraft] = useState<TripDraft>(() => defaultDraft(new Date()));
  const [attempted, setAttempted] = useState(false);
  const originRef = useRef<HTMLInputElement>(null);
  const destinationRef = useRef<HTMLInputElement>(null);
  const departureRef = useRef<HTMLInputElement>(null);
  const loadRef = useRef<HTMLInputElement>(null);

  const now = new Date();
  const { errors } = validateTrip(draft, now);
  const shown = attempted ? errors : {};
  const update = (changes: Partial<TripDraft>) => setDraft((d) => ({ ...d, ...changes }));

  function submit(event: FormEvent) {
    event.preventDefault();
    setAttempted(true);
    const result = validateTrip(draft, new Date());
    if (result.request) {
      onSubmit(result.request);
      return;
    }
    // Keyboard users land on the first thing to fix (ui D4).
    const first = FIELD_ORDER.find((field) => result.errors[field]);
    const refs: Record<TripField, typeof originRef> = {
      origin: originRef,
      destination: destinationRef,
      departure: departureRef,
      loadLb: loadRef,
    };
    if (first) refs[first].current?.focus();
  }

  return (
    <Box component="form" noValidate onSubmit={submit} aria-label="Plan a trip">
      <Stack spacing={2}>
        <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
          <Stack spacing={1.5} sx={{ flex: 1, minWidth: 0 }}>
            <PlaceField
              id="origin"
              label="From"
              value={draft.origin}
              onChange={(origin) => update({ origin })}
              error={shown.origin}
              inputRef={originRef}
            />
            <PlaceField
              id="destination"
              label="To"
              value={draft.destination}
              onChange={(destination) => update({ destination })}
              error={shown.destination}
              inputRef={destinationRef}
            />
          </Stack>
          <Tooltip title="Swap start and destination">
            <span>
              <IconButton
                aria-label="Swap start and destination"
                size="small"
                disabled={!draft.origin || !draft.destination}
                onClick={() => update({ origin: draft.destination, destination: draft.origin })}
              >
                <SwapVert fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
        </Stack>

        <Stack direction="row" spacing={1.5}>
          <TextField
            label="Departure"
            type="datetime-local"
            value={draft.departure}
            onChange={(e) => update({ departure: e.target.value })}
            error={Boolean(shown.departure)}
            helperText={shown.departure ?? `Times in ${zoneName(now)}`}
            inputRef={departureRef}
            sx={{ flex: 1.4 }}
            slotProps={{
              inputLabel: { shrink: true },
              htmlInput: {
                min: toLocalInput(new Date(now.getTime() - DEPARTURE_PAST_MS)),
                max: toLocalInput(new Date(now.getTime() + DEPARTURE_AHEAD_MS)),
              },
            }}
          />
          <TextField
            label="Load"
            value={draft.loadLb}
            onChange={(e) => update({ loadLb: e.target.value })}
            error={Boolean(shown.loadLb)}
            helperText={shown.loadLb ?? "0 to 80,000"}
            placeholder="30,000"
            inputRef={loadRef}
            sx={{ flex: 1 }}
            slotProps={{
              htmlInput: { inputMode: "numeric", autoComplete: "off" },
              input: { endAdornment: <InputAdornment position="end">lb</InputAdornment> },
            }}
          />
        </Stack>

        <FormControl>
          <FormLabel id="interval-label" sx={{ typography: "body2", mb: 0.75 }}>
            Check the weather every
          </FormLabel>
          <ToggleButtonGroup
            aria-labelledby="interval-label"
            exclusive
            fullWidth
            size="small"
            value={draft.intervalMi}
            onChange={(_, intervalMi) => intervalMi && update({ intervalMi })}
          >
            {INTERVALS_MI.map((miles) => (
              <ToggleButton key={miles} value={miles}>
                {miles} mi
              </ToggleButton>
            ))}
          </ToggleButtonGroup>
        </FormControl>

        {error ? (
          <Alert severity="error" role="alert">
            {error}
          </Alert>
        ) : null}

        <Button
          type="submit"
          variant="contained"
          size="large"
          disabled={pending}
          startIcon={pending ? <CircularProgress size={18} color="inherit" /> : null}
        >
          {pending ? "Planning routes…" : "Plan routes"}
        </Button>
      </Stack>
    </Box>
  );
}
