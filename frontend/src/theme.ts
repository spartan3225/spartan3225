export const colors = {
  background: "#0A0A0A",
  surface: "#141416",
  surfaceElevated: "#1C1C20",
  glass: "rgba(255,255,255,0.06)",
  glassBorder: "rgba(255,255,255,0.10)",
  primary: "#00E5FF",
  primaryDim: "#0D2224",
  secondary: "#2A2A2E",
  textPrimary: "#FFFFFF",
  textSecondary: "#A1A1AA",
  textMuted: "#6B6B72",
  error: "#FF3366",
  warning: "#FFD600",
  success: "#00FF88",
  border: "#222226",
  borderStrong: "#37373E",
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
  sm: 8,
  md: 14,
  lg: 22,
  pill: 999,
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

// Canonical order of the 14 AI sub-score categories.
export const SCORE_CATEGORIES = [
  "surf_flow",
  "take_off",
  "bottom_turn",
  "top_turn",
  "compression",
  "recovery",
  "rail_control",
  "speed_generation",
  "power",
  "timing",
  "balance",
  "style",
  "body_position",
  "wave_reading",
] as const;

export const IMAGES = {
  heroSurfer:
    "https://images.unsplash.com/photo-1493225255756-d9584f8606e9?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200",
  darkOcean:
    "https://images.unsplash.com/photo-1710438399422-2fca27686bcd?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200",
  trainMobility:
    "https://images.unsplash.com/photo-1701826510609-b8d07deca0d4?crop=entropy&cs=srgb&fm=jpg&q=80&w=600",
  trainSurf:
    "https://images.unsplash.com/photo-1645499683497-22662a9b1704?crop=entropy&cs=srgb&fm=jpg&q=80&w=600",
};
