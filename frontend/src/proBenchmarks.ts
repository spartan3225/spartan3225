// Pro Reference clips for Comparison Mode.
//
// These are REAL surfing clips sourced from Pexels under its Free-to-use /
// commercial license (safe for a paid app — no named-athlete likeness). Each
// clip is skeleton-tracked server-side; the Compare screen plays the clip with
// the pro's skeleton overlay next to the user's wave.
//
// Served by the backend: GET /api/pro/{clipId}/video and /api/pro/{clipId}/pose
// To add / swap footage: drop the mp4 + pose JSON in backend/static_assets/pro
// and register the id in PRO_CLIP_IDS (server.py). Buy maneuver-specific pro
// clips (Pond5/Shutterstock) later and swap the clipId to upgrade any entry.

export type ProBenchmark = {
  id: string; // maneuver id
  clipId: string; // backend reference clip id
  name: string; // i18n key resolved in the Compare screen
  stance: string;
  country: string;
  available: boolean;
  image: string;
  scores: Record<string, number>;
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

const thumb = (id: string) =>
  `https://images.pexels.com/videos/${id}/pexels-photo-${id}.jpeg?auto=compress&cs=tinysrgb&w=600`;

// Six core maneuvers -> real reference clips (skeleton-tracked).
export const PRO_BENCHMARKS: ProBenchmark[] = [
  {
    id: "bottom_turn",
    clipId: "4927323",
    name: "maneuver_bottom_turn",
    stance: "Regular",
    country: "🌊",
    available: true,
    image: thumb("4927323"),
    scores: base({ bottom_turn: 98, rail_control: 98, power: 97 }),
  },
  {
    id: "top_turn",
    clipId: "4929633",
    name: "maneuver_top_turn",
    stance: "Regular",
    country: "🌊",
    available: true,
    image: thumb("4929633"),
    scores: base({ top_turn: 98, compression: 97, style: 97 }),
  },
  {
    id: "snap",
    clipId: "14435086",
    name: "maneuver_snap",
    stance: "Regular",
    country: "🌊",
    available: true,
    image: thumb("14435086"),
    scores: base({ top_turn: 98, timing: 97, power: 97 }),
  },
  {
    id: "cutback",
    clipId: "4929633",
    name: "maneuver_cutback",
    stance: "Regular",
    country: "🌊",
    available: true,
    image: thumb("4929633"),
    scores: base({ surf_flow: 98, rail_control: 97, wave_reading: 97 }),
  },
  {
    id: "roundhouse",
    clipId: "4927323",
    name: "maneuver_roundhouse",
    stance: "Regular",
    country: "🌊",
    available: true,
    image: thumb("4927323"),
    scores: base({ surf_flow: 98, timing: 98, style: 97 }),
  },
  {
    id: "floater",
    clipId: "8775726",
    name: "maneuver_floater",
    stance: "Regular",
    country: "🌊",
    available: true,
    image: thumb("8775726"),
    scores: base({ balance: 98, body_position: 97, recovery: 97 }),
  },
];
