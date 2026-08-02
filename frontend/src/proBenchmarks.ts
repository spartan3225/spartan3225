// Pro Reference benchmarks for Comparison Mode.
//
// LEGAL NOTE: To stay 100% compliant for commercial App/Play Store use, these
// are GENERIC "world-tour level" reference archetypes — NOT named professional
// athletes. Using a real pro's name/likeness/footage requires that athlete's
// personal licensing agreement, which stock libraries do NOT grant. Each entry
// represents a *style* of elite surfing so users can benchmark their technique.
//
// When you obtain a properly licensed elite-surfer clip (Pond5 / Shutterstock /
// iStock — commercial license), just set `footage` to the video URL and
// `available: true`. Adding a new reference = adding one object here.

export type ProBenchmark = {
  id: string;
  name: string; // localization key -> resolved in the Compare screen
  stance: string;
  country: string;
  available: boolean;
  image: string;
  scores: Record<string, number>;
  footage?: string | null; // video URL once licensed footage is added
};

const base = (overrides: Record<string, number> = {}): Record<string, number> => ({
  surf_flow: 95,
  take_off: 96,
  bottom_turn: 95,
  top_turn: 95,
  compression: 94,
  recovery: 93,
  rail_control: 95,
  speed_generation: 96,
  power: 94,
  timing: 95,
  balance: 96,
  style: 95,
  body_position: 94,
  wave_reading: 96,
  ...overrides,
});

// `name` values are i18n keys (see i18n.tsx pro_ref_* entries).
export const PRO_BENCHMARKS: ProBenchmark[] = [
  {
    id: "power",
    name: "pro_ref_power",
    stance: "Regular",
    country: "🌊",
    available: true,
    image:
      "https://images.unsplash.com/photo-1502933691298-84fc14542831?crop=entropy&cs=srgb&fm=jpg&q=85&w=1000",
    scores: base({ power: 98, rail_control: 98, bottom_turn: 97 }),
    footage: null,
  },
  {
    id: "progressive",
    name: "pro_ref_progressive",
    stance: "Goofy",
    country: "🏄",
    available: false,
    image:
      "https://images.unsplash.com/photo-1455729552865-3658a5d39692?crop=entropy&cs=srgb&fm=jpg&q=85&w=1000",
    scores: base({ take_off: 98, top_turn: 98, style: 97 }),
    footage: null,
  },
  {
    id: "flow",
    name: "pro_ref_flow",
    stance: "Regular",
    country: "🌀",
    available: false,
    image:
      "https://images.unsplash.com/photo-1531722569936-825d3dd91b15?crop=entropy&cs=srgb&fm=jpg&q=85&w=1000",
    scores: base({ surf_flow: 98, style: 98, timing: 97 }),
    footage: null,
  },
  {
    id: "technical",
    name: "pro_ref_technical",
    stance: "Goofy",
    country: "🎯",
    available: false,
    image:
      "https://images.unsplash.com/photo-1544551763-46a013bb70d5?crop=entropy&cs=srgb&fm=jpg&q=85&w=1000",
    scores: base({ compression: 98, body_position: 98, balance: 98 }),
    footage: null,
  },
];
