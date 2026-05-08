export const colors = {
  background: "#0A0A0A",
  surface: "#121214",
  surfaceElevated: "#1A1A1E",
  primary: "#00E5FF",
  secondary: "#2A2A2E",
  textPrimary: "#FFFFFF",
  textSecondary: "#A1A1AA",
  textMuted: "#6B6B72",
  error: "#FF3B30",
  warning: "#FF8A1F",
  success: "#39FF14",
  border: "#27272A",
  borderStrong: "#3F3F46",
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

export const radii = {
  sm: 4,
  md: 8,
  lg: 12,
  pill: 999,
};

export const fonts = {
  // System fallback as Oswald/Manrope aren't loaded
  heading: undefined as undefined,
  body: undefined as undefined,
};

export const severityColor = (severity: string) => {
  const s = (severity || "").toLowerCase();
  if (s === "high") return colors.error;
  if (s === "medium") return colors.warning;
  return "#FACC15";
};

export const scoreColor = (score: number) => {
  if (score >= 80) return colors.success;
  if (score >= 50) return colors.primary;
  return colors.warning;
};
