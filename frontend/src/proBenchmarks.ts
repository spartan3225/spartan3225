// Pro reference benchmarks for Comparison Mode.
// Benchmark scores approximate world-tour level execution per category and
// are clearly labeled as reference data in the UI. Real pro footage + pose
// data can be attached later via the `footage` / `pose` fields (modular:
// adding a new pro = adding one object here).

export type ProBenchmark = {
  id: string;
  name: string;
  stance: string;
  country: string;
  available: boolean;
  image: string;
  scores: Record<string, number>;
  footage?: string | null; // video URL when licensed footage is added
};

const WORLD_TOUR_SCORES: Record<string, number> = {
  surf_flow: 96,
  take_off: 97,
  bottom_turn: 95,
  top_turn: 96,
  compression: 94,
  recovery: 93,
  rail_control: 95,
  speed_generation: 97,
  power: 94,
  timing: 95,
  balance: 96,
  style: 95,
  body_position: 94,
  wave_reading: 96,
};

export const PRO_BENCHMARKS: ProBenchmark[] = [
  {
    id: "yago_dora",
    name: "Yago Dora",
    stance: "Goofy",
    country: "🇧🇷",
    available: true,
    image:
      "https://images.unsplash.com/photo-1502680390469-be75c86b636f?crop=entropy&cs=srgb&fm=jpg&q=80&w=800",
    scores: WORLD_TOUR_SCORES,
    footage: null,
  },
  {
    id: "gabriel_medina",
    name: "Gabriel Medina",
    stance: "Goofy",
    country: "🇧🇷",
    available: false,
    image: "",
    scores: WORLD_TOUR_SCORES,
  },
  {
    id: "john_john",
    name: "John John Florence",
    stance: "Regular",
    country: "🇺🇸",
    available: false,
    image: "",
    scores: WORLD_TOUR_SCORES,
  },
  {
    id: "italo_ferreira",
    name: "Italo Ferreira",
    stance: "Regular",
    country: "🇧🇷",
    available: false,
    image: "",
    scores: WORLD_TOUR_SCORES,
  },
];
