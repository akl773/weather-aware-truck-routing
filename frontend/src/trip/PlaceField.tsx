import PlaceOutlined from "@mui/icons-material/PlaceOutlined";
import Autocomplete from "@mui/material/Autocomplete";
import CircularProgress from "@mui/material/CircularProgress";
import InputAdornment from "@mui/material/InputAdornment";
import TextField from "@mui/material/TextField";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { type Ref, useState } from "react";

import { type ApiError, type Place, searchPlaces } from "../api/client";
import { useDebounced } from "../hooks/useDebounced";

const MIN_QUERY = 2;
const DEBOUNCE_MS = 250;
const SUGGESTIONS_STALE_MS = 5 * 60 * 1000;

interface PlaceFieldProps {
  id: string;
  label: string;
  value: Place | null;
  onChange: (place: Place | null) => void;
  error?: string;
  inputRef?: Ref<HTMLInputElement>;
}

/** Holds a place only once one is picked from the suggestions (ui D2). */
export function PlaceField({ id, label, value, onChange, error, inputRef }: PlaceFieldProps) {
  const [text, setText] = useState(value?.label ?? "");
  // A place set from outside (the swap button) replaces whatever was typed.
  const [shown, setShown] = useState(value);
  if (value !== shown) {
    setShown(value);
    if (value) setText(value.label);
  }
  const query = useDebounced(text.trim(), DEBOUNCE_MS);
  const searching = query.length >= MIN_QUERY && query !== value?.label;
  const suggestions = useQuery<Place[], ApiError>({
    queryKey: ["places", query],
    queryFn: ({ signal }) => searchPlaces(query, signal),
    enabled: searching,
    staleTime: SUGGESTIONS_STALE_MS,
    placeholderData: keepPreviousData,
    retry: false,
  });

  const noOptionsText =
    text.trim().length < MIN_QUERY
      ? "Type at least two letters"
      : suggestions.isError
        ? suggestions.error.message
        : suggestions.isFetching
          ? "Searching…"
          : "No matching places";

  return (
    <Autocomplete
      id={id}
      value={value}
      inputValue={text}
      options={searching ? (suggestions.data ?? []) : value ? [value] : []}
      // The API already ranks matches; filtering again would hide good ones.
      filterOptions={(options) => options}
      getOptionLabel={(place) => place.label}
      getOptionKey={(place) => `${place.label}@${place.lat},${place.lon}`}
      isOptionEqualToValue={(a, b) => a.lat === b.lat && a.lon === b.lon && a.label === b.label}
      onInputChange={(_, next, reason) => {
        setText(next);
        // Typing over a picked place un-picks it, so a label never pairs with stale coordinates.
        if (reason === "input" && value && next !== value.label) onChange(null);
      }}
      onChange={(_, place) => onChange(place)}
      loading={suggestions.isFetching}
      noOptionsText={noOptionsText}
      autoHighlight
      handleHomeEndKeys
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          error={Boolean(error)}
          helperText={error}
          inputRef={inputRef}
          slotProps={{
            ...params.slotProps,
            input: {
              ...params.slotProps.input,
              startAdornment: (
                <InputAdornment position="start">
                  <PlaceOutlined fontSize="small" color={value ? "primary" : "action"} />
                </InputAdornment>
              ),
              endAdornment: (
                <>
                  {suggestions.isFetching ? <CircularProgress color="inherit" size={18} /> : null}
                  {params.slotProps.input.endAdornment}
                </>
              ),
            },
          }}
        />
      )}
    />
  );
}
