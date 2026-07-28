export type DrillCategory = "surf" | "land" | "balance" | "mobility" | "strength";

export type Drill = {
  id: string;
  category: DrillCategory;
  icon: string; // Ionicons name
  titleKey: string;
  descKey: string;
  goalKey: string;
  image?: string;
  // score category keys this drill improves — used for personalization
  improves: string[];
};

export const TUTORIALS: {
  id: string;
  youtubeId: string;
  title: string;
  category: DrillCategory;
}[] = [
  { id: "t1", youtubeId: "2XOIFuBhz2U", title: "Perfect Pop-Up Technique", category: "surf" },
  { id: "t2", youtubeId: "VImJbHuZQnI", title: "Beginner Pop-Up Made Easy", category: "surf" },
  { id: "t3", youtubeId: "dfHdY6SliKI", title: "Bottom Turn & Top Turn Basics", category: "surf" },
  { id: "t4", youtubeId: "i510zQPYPUI", title: "Surfskate Bottom Turn Training", category: "land" },
  { id: "t5", youtubeId: "7vH-fs_iBkU", title: "Set the Rail: Lean & Hold", category: "land" },
  { id: "t6", youtubeId: "j9JjdMf9szM", title: "Dry-Land Pop-Up Drills", category: "mobility" },
];

const IMG = {
  surf: "https://images.unsplash.com/photo-1645499683497-22662a9b1704?crop=entropy&cs=srgb&fm=jpg&q=80&w=600",
  mobility:
    "https://images.unsplash.com/photo-1701826510609-b8d07deca0d4?crop=entropy&cs=srgb&fm=jpg&q=80&w=600",
  balance:
    "https://images.unsplash.com/photo-1518611012118-696072aa579a?crop=entropy&cs=srgb&fm=jpg&q=80&w=600",
  strength:
    "https://images.unsplash.com/photo-1517836357463-d25dfeac3438?crop=entropy&cs=srgb&fm=jpg&q=80&w=600",
  skate:
    "https://images.unsplash.com/photo-1547447134-cd3f5c716030?crop=entropy&cs=srgb&fm=jpg&q=80&w=600",
  ocean:
    "https://images.unsplash.com/photo-1493225255756-d9584f8606e9?crop=entropy&cs=srgb&fm=jpg&q=80&w=600",
};

export const DRILLS: Drill[] = [
  { id: "d1", category: "surf", icon: "flash-outline", titleKey: "drill_1_t", descKey: "drill_1_d", goalKey: "drill_1_g", image: IMG.surf, improves: ["take_off", "timing"] },
  { id: "d2", category: "surf", icon: "eye-outline", titleKey: "drill_2_t", descKey: "drill_2_d", goalKey: "drill_2_g", image: IMG.ocean, improves: ["wave_reading", "timing"] },
  { id: "d3", category: "land", icon: "trending-up-outline", titleKey: "drill_3_t", descKey: "drill_3_d", goalKey: "drill_3_g", image: IMG.skate, improves: ["rail_control", "surf_flow", "speed_generation"] },
  { id: "d4", category: "land", icon: "body-outline", titleKey: "drill_4_t", descKey: "drill_4_d", goalKey: "drill_4_g", image: IMG.mobility, improves: ["bottom_turn", "top_turn", "style"] },
  { id: "d5", category: "balance", icon: "scale-outline", titleKey: "drill_5_t", descKey: "drill_5_d", goalKey: "drill_5_g", image: IMG.balance, improves: ["compression", "balance", "body_position"] },
  { id: "d6", category: "balance", icon: "walk-outline", titleKey: "drill_6_t", descKey: "drill_6_d", goalKey: "drill_6_g", image: IMG.balance, improves: ["balance", "recovery"] },
  { id: "d7", category: "mobility", icon: "accessibility-outline", titleKey: "drill_7_t", descKey: "drill_7_d", goalKey: "drill_7_g", image: IMG.mobility, improves: ["compression", "body_position"] },
  { id: "d8", category: "mobility", icon: "sync-outline", titleKey: "drill_8_t", descKey: "drill_8_d", goalKey: "drill_8_g", image: IMG.mobility, improves: ["top_turn", "style"] },
  { id: "d9", category: "strength", icon: "barbell-outline", titleKey: "drill_9_t", descKey: "drill_9_d", goalKey: "drill_9_g", image: IMG.strength, improves: ["power", "speed_generation"] },
  { id: "d10", category: "strength", icon: "fitness-outline", titleKey: "drill_10_t", descKey: "drill_10_d", goalKey: "drill_10_g", image: IMG.strength, improves: ["power", "take_off"] },
];
