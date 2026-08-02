import { useCallback, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
  ImageBackground,
  Dimensions,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useFocusEffect, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import {
  AnalysisListItem,
  Analysis,
  fetchMe,
  listAnalyses,
  getAnalysis,
  User,
} from "../../src/api";
import { colors, radii, scoreColor, spacing } from "../../src/theme";
import { useI18n } from "../../src/i18n";
import { haptic } from "../../src/haptics";
import ScoreRing from "../../src/components/ScoreRing";
import GlassCard from "../../src/components/GlassCard";
import Skeleton from "../../src/components/Skeleton";

const KAI_IMAGE = require("../../assets/kai-coach.png");
const SCREEN_W = Dimensions.get("window").width;

// Technique rows shown on the dashboard, mapped to AI score categories.
const TECH_ROWS: { key: string; color: string }[] = [
  { key: "take_off", color: "#00E5FF" },
  { key: "bottom_turn", color: "#00FF88" },
  { key: "top_turn", color: "#FFD600" },
  { key: "rail_control", color: "#B388FF" },
  { key: "timing", color: "#4DD0E1" },
];

export default function HomeScreen() {
  const router = useRouter();
  const { t } = useI18n();
  const [items, setItems] = useState<AnalysisListItem[]>([]);
  const [user, setUser] = useState<User | null>(null);
  const [latestFull, setLatestFull] = useState<Analysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [me, list] = await Promise.all([fetchMe(), listAnalyses()]);
      if (!me) {
        router.replace("/");
        return;
      }
      setUser(me);
      setItems(list);
      const firstReady = list.find((i) => i.status === "ready");
      if (firstReady) {
        try {
          setLatestFull(await getAnalysis(firstReady.analysis_id));
        } catch {
          setLatestFull(null);
        }
      } else {
        setLatestFull(null);
      }
    } catch (e) {
      console.warn("load failed", e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [router]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const ready = items.filter((i) => i.status === "ready");
  const kaiScore = ready.length
    ? Math.round(ready.reduce((s, i) => s + (i.score || 0), 0) / ready.length)
    : 0;
  const best = ready.length ? Math.max(...ready.map((i) => i.score || 0)) : 0;
  // Improvement = latest ready score minus the oldest ready score.
  const improvement =
    ready.length >= 2
      ? (ready[0].score || 0) - (ready[ready.length - 1].score || 0)
      : 0;

  // Technique values from the most recent full analysis (real per-category
  // scores). Falls back to the overall score if categories are missing.
  const scoreMap: Record<string, number> = {};
  (latestFull?.scores || []).forEach((s) => {
    if (s && s.key) scoreMap[s.key] = Math.round(s.value || 0);
  });
  const techValue = (key: string) =>
    scoreMap[key] != null ? scoreMap[key] : latestFull?.score || 0;

  const takeOff = techValue("take_off");
  const quote = [t("quote_1"), t("quote_2"), t("quote_3")][
    new Date().getDate() % 3
  ];

  const firstName = user?.name?.split(" ")[0] || "Surfer";
  const kaiMsg =
    ready.length === 0
      ? t("kai_msg_start")
      : improvement > 0
      ? t("kai_msg_improving").replace("{n}", String(improvement))
      : t("kai_msg_steady");

  const go = (path: string) => {
    haptic.tap();
    router.push(path as any);
  };

  const achievements = [
    {
      icon: "water" as const,
      color: "#B87333",
      label: t("ach_first"),
      sub: ready.length >= 1 ? t("ach_first_sub") : t("ach_first_locked"),
      unlocked: ready.length >= 1,
    },
    {
      icon: "flame" as const,
      color: "#D4A017",
      label: t("ach_consistency"),
      sub: t("ach_consistency_sub").replace("{n}", String(ready.length)),
      unlocked: ready.length >= 3,
    },
    {
      icon: "rocket" as const,
      color: "#E0A800",
      label: t("ach_popup"),
      sub: t("ach_popup_sub"),
      unlocked: takeOff > 80,
    },
    {
      icon: "trophy" as const,
      color: "#00B4D8",
      label: t("ach_pro"),
      sub: t("ach_pro_sub"),
      unlocked: best > 85,
    },
  ];

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={["top"]}>
        <View style={{ padding: spacing.lg, gap: 14 }}>
          <Skeleton height={260} radius={radii.lg} />
          <Skeleton height={110} radius={radii.lg} />
          <Skeleton height={70} radius={radii.lg} />
          <Skeleton height={160} radius={radii.lg} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <View style={styles.container} testID="dashboard-screen">
      <ScrollView
        contentContainerStyle={{ paddingBottom: 130 }}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => {
              setRefreshing(true);
              load();
            }}
            tintColor={colors.primary}
          />
        }
      >
        {/* ---------- Hero ---------- */}
        <ImageBackground
          source={KAI_IMAGE}
          style={styles.hero}
          imageStyle={styles.heroImg}
        >
          <LinearGradient
            colors={[
              "rgba(10,10,10,0.55)",
              "rgba(10,10,10,0.15)",
              "rgba(10,10,10,0.85)",
              "#0A0A0A",
            ]}
            locations={[0, 0.4, 0.82, 1]}
            style={StyleSheet.absoluteFill}
          />
          <SafeAreaView edges={["top"]} style={styles.heroSafe}>
            <View style={styles.brandRow}>
              <View>
                <Text style={styles.brandName}>KAI</Text>
                <Text style={styles.brandTag}>{t("home_tagline")}</Text>
              </View>
              <TouchableOpacity
                style={styles.bellBtn}
                activeOpacity={0.8}
                onPress={() => go("/(tabs)/review")}
                testID="notifications-btn"
              >
                <Ionicons
                  name="notifications-outline"
                  size={20}
                  color={colors.textPrimary}
                />
              </TouchableOpacity>
            </View>

            <View style={styles.heroBottom}>
              <Text style={styles.greeting}>
                {t("greeting")}, {firstName} 🤙
              </Text>
              <Text style={styles.subGreeting}>{t("home_ready")}</Text>
            </View>
          </SafeAreaView>
        </ImageBackground>

        <View style={styles.body}>
          {/* ---------- Kai message + KAI Score ring ---------- */}
          <View style={styles.msgRow}>
            <GlassCard style={styles.msgCard} accent={colors.primary}>
              <View style={styles.msgHead}>
                <Ionicons name="chatbubble-ellipses" size={14} color={colors.primary} />
                <Text style={styles.msgAuthor}>{t("quote_author")}</Text>
              </View>
              <Text style={styles.msgText} numberOfLines={4}>
                {kaiMsg}
              </Text>
            </GlassCard>
            <View style={styles.ringCol}>
              <ScoreRing
                value={kaiScore}
                size={104}
                thickness={9}
                color={colors.primary}
                valueSize={34}
              />
              <Text style={styles.ringLabel}>{t("kai_score").toUpperCase()}</Text>
            </View>
          </View>

          {/* ---------- Stats ---------- */}
          <View style={styles.statsRow}>
            <View style={styles.statCell}>
              <Text style={styles.statValue}>{ready.length}</Text>
              <Text style={styles.statLabel}>{t("sessions").toUpperCase()}</Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.statCell}>
              <Text style={[styles.statValue, { color: colors.primary }]}>
                {(kaiScore / 10).toFixed(1)}
              </Text>
              <Text style={styles.statLabel}>{t("kai_score").toUpperCase()}</Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.statCell}>
              <Text
                style={[
                  styles.statValue,
                  { color: improvement >= 0 ? colors.success : colors.error },
                ]}
              >
                {improvement >= 0 ? "+" : ""}
                {improvement}
              </Text>
              <Text style={styles.statLabel}>
                {t("improvement").toUpperCase()}
              </Text>
            </View>
          </View>

          {/* ---------- Analyze CTA ---------- */}
          <TouchableOpacity
            activeOpacity={0.9}
            onPress={() => go("/(tabs)/upload")}
            testID="dashboard-new-analysis-btn"
          >
            <LinearGradient
              colors={["#00E5FF", "#0091AD"]}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 1 }}
              style={styles.cta}
            >
              <View style={styles.ctaIcon}>
                <Ionicons name="videocam" size={22} color="#00131a" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.ctaTitle}>
                  {t("analyze_session").toUpperCase()}
                </Text>
                <Text style={styles.ctaSub}>{t("analyze_session_sub")}</Text>
              </View>
              <Ionicons name="chevron-forward" size={22} color="#00131a" />
            </LinearGradient>
          </TouchableOpacity>

          {/* ---------- Recent sessions (horizontal) ---------- */}
          {ready.length > 0 && (
            <View style={styles.section}>
              <View style={styles.sectionHead}>
                <Text style={styles.sectionLabel}>
                  {t("recent_sessions").toUpperCase()}
                </Text>
                <TouchableOpacity onPress={() => go("/(tabs)/review")}>
                  <Text style={styles.viewAll}>{t("view_all")} →</Text>
                </TouchableOpacity>
              </View>
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={{ gap: spacing.sm, paddingRight: spacing.lg }}
              >
                {ready.slice(0, 8).map((item) => (
                  <TouchableOpacity
                    key={item.analysis_id}
                    style={styles.clipCard}
                    activeOpacity={0.85}
                    onPress={() => go(`/analysis/${item.analysis_id}`)}
                    testID={`analysis-card-${item.analysis_id}`}
                  >
                    <View style={styles.clipThumb}>
                      <View style={styles.playCircle}>
                        <Ionicons name="play" size={20} color="#fff" />
                      </View>
                      <View style={styles.clipScorePill}>
                        <Text
                          style={[
                            styles.clipScoreText,
                            { color: scoreColor(item.score) },
                          ]}
                        >
                          {item.score}
                        </Text>
                      </View>
                    </View>
                    <Text style={styles.clipTitle} numberOfLines={1}>
                      {item.title || t("unknown_spot")}
                    </Text>
                    <View style={styles.clipMetaRow}>
                      <Text style={styles.clipDate}>
                        {new Date(item.created_at).toLocaleDateString(undefined, {
                          day: "2-digit",
                          month: "short",
                        })}
                      </Text>
                      <Ionicons name="trending-up" size={13} color={colors.primary} />
                    </View>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>
          )}

          {/* ---------- Technique ---------- */}
          {latestFull && (
            <GlassCard style={styles.panel}>
              <View style={styles.panelHead}>
                <View style={styles.panelTitleRow}>
                  <View style={styles.panelIcon}>
                    <Ionicons name="barbell" size={16} color={colors.primary} />
                  </View>
                  <Text style={styles.panelTitle}>
                    {t("technique").toUpperCase()}
                  </Text>
                </View>
                <TouchableOpacity onPress={() => go("/(tabs)/progress")}>
                  <Text style={styles.viewAll}>{t("details")} →</Text>
                </TouchableOpacity>
              </View>
              {TECH_ROWS.map((row) => {
                const v = techValue(row.key);
                return (
                  <View key={row.key} style={styles.techRow}>
                    <Text style={styles.techLabel} numberOfLines={1}>
                      {t(`score_${row.key}`).toUpperCase()}
                    </Text>
                    <View style={styles.techTrack}>
                      <View
                        style={[
                          styles.techFill,
                          { width: `${Math.max(4, v)}%`, backgroundColor: row.color },
                        ]}
                      />
                    </View>
                    <Text style={[styles.techValue, { color: row.color }]}>{v}</Text>
                  </View>
                );
              })}
            </GlassCard>
          )}

          {/* ---------- Achievements ---------- */}
          <GlassCard style={styles.panel}>
            <View style={styles.panelHead}>
              <View style={styles.panelTitleRow}>
                <View style={styles.panelIcon}>
                  <Ionicons name="trophy" size={16} color={colors.primary} />
                </View>
                <Text style={styles.panelTitle}>
                  {t("achievements").toUpperCase()}
                </Text>
              </View>
              <TouchableOpacity onPress={() => go("/(tabs)/progress")}>
                <Text style={styles.viewAll}>{t("view_all")} →</Text>
              </TouchableOpacity>
            </View>
            <View style={styles.badgeRow}>
              {achievements.map((a, i) => (
                <View key={i} style={styles.badgeCell}>
                  <View
                    style={[
                      styles.badgeHex,
                      {
                        backgroundColor: a.unlocked ? `${a.color}22` : "rgba(255,255,255,0.04)",
                        borderColor: a.unlocked ? a.color : colors.glassBorder,
                      },
                    ]}
                  >
                    <Ionicons
                      name={a.icon}
                      size={22}
                      color={a.unlocked ? a.color : colors.textMuted}
                    />
                  </View>
                  <Text
                    style={[
                      styles.badgeLabel,
                      { color: a.unlocked ? colors.textPrimary : colors.textMuted },
                    ]}
                    numberOfLines={1}
                  >
                    {a.label}
                  </Text>
                  <Text style={styles.badgeSub} numberOfLines={1}>
                    {a.sub}
                  </Text>
                </View>
              ))}
            </View>
          </GlassCard>

          {/* ---------- Quote ---------- */}
          <GlassCard style={styles.quoteCard}>
            <Text style={styles.quoteMark}>“</Text>
            <Text style={styles.quoteText}>{quote}</Text>
            <Text style={styles.quoteAuthor}>— {t("quote_author")}</Text>
          </GlassCard>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  // Hero
  hero: { width: SCREEN_W, height: SCREEN_W * 1.28, justifyContent: "flex-start" },
  heroImg: { resizeMode: "cover" },
  heroSafe: { flex: 1, justifyContent: "space-between" },
  brandRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
  },
  brandName: {
    color: colors.primary,
    fontSize: 34,
    fontWeight: "900",
    letterSpacing: 2,
  },
  brandTag: {
    color: colors.textSecondary,
    fontSize: 9,
    letterSpacing: 3,
    fontWeight: "800",
    marginTop: -2,
  },
  bellBtn: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: "rgba(255,255,255,0.10)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.14)",
    alignItems: "center",
    justifyContent: "center",
  },
  heroBottom: { paddingHorizontal: spacing.lg, paddingBottom: spacing.md },
  greeting: {
    color: colors.textPrimary,
    fontSize: 34,
    fontWeight: "900",
    letterSpacing: -1,
  },
  subGreeting: { color: colors.textSecondary, fontSize: 15, marginTop: 2 },
  // Body
  body: { paddingHorizontal: spacing.lg, marginTop: -spacing.sm },
  // Kai message + ring
  msgRow: { flexDirection: "row", gap: spacing.sm, marginBottom: spacing.md },
  msgCard: { flex: 1, justifyContent: "center" },
  msgHead: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 6 },
  msgAuthor: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0.5,
  },
  msgText: { color: colors.textSecondary, fontSize: 13, lineHeight: 19 },
  ringCol: { alignItems: "center", justifyContent: "center", width: 118 },
  ringLabel: {
    color: colors.textMuted,
    fontSize: 9,
    letterSpacing: 2,
    fontWeight: "800",
    marginTop: 8,
  },
  // Stats
  statsRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.glass,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    borderRadius: radii.lg,
    paddingVertical: spacing.md,
    marginBottom: spacing.md,
  },
  statCell: { flex: 1, alignItems: "center" },
  statDivider: {
    width: StyleSheet.hairlineWidth,
    height: 34,
    backgroundColor: colors.glassBorder,
  },
  statValue: {
    color: colors.textPrimary,
    fontSize: 24,
    fontWeight: "900",
    letterSpacing: -0.5,
  },
  statLabel: {
    color: colors.textMuted,
    fontSize: 9,
    letterSpacing: 1.2,
    fontWeight: "700",
    marginTop: 3,
  },
  // CTA
  cta: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    borderRadius: radii.lg,
    padding: spacing.md,
    marginBottom: spacing.lg,
  },
  ctaIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: "rgba(0,0,0,0.18)",
    alignItems: "center",
    justifyContent: "center",
  },
  ctaTitle: {
    color: "#00131a",
    fontSize: 17,
    fontWeight: "900",
    letterSpacing: 0.5,
  },
  ctaSub: { color: "rgba(0,19,26,0.7)", fontSize: 13, marginTop: 1 },
  // Sections
  section: { marginBottom: spacing.lg },
  sectionHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.sm,
  },
  sectionLabel: {
    color: colors.textMuted,
    fontSize: 11,
    letterSpacing: 2.5,
    fontWeight: "800",
  },
  viewAll: { color: colors.primary, fontSize: 12, fontWeight: "800" },
  // Clip cards
  clipCard: { width: 150 },
  clipThumb: {
    width: 150,
    height: 96,
    borderRadius: radii.md,
    backgroundColor: colors.surfaceElevated,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 8,
    overflow: "hidden",
  },
  playCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "rgba(255,255,255,0.14)",
    alignItems: "center",
    justifyContent: "center",
  },
  clipScorePill: {
    position: "absolute",
    top: 8,
    right: 8,
    backgroundColor: "rgba(0,0,0,0.55)",
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  clipScoreText: { fontSize: 12, fontWeight: "900" },
  clipTitle: { color: colors.textPrimary, fontSize: 14, fontWeight: "700" },
  clipMetaRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 2,
  },
  clipDate: { color: colors.textMuted, fontSize: 11 },
  // Panels
  panel: { marginBottom: spacing.lg, padding: spacing.md },
  panelHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.md,
  },
  panelTitleRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  panelIcon: {
    width: 30,
    height: 30,
    borderRadius: 9,
    backgroundColor: colors.primaryDim,
    alignItems: "center",
    justifyContent: "center",
  },
  panelTitle: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: "800",
    letterSpacing: 1.5,
  },
  // Technique rows
  techRow: { flexDirection: "row", alignItems: "center", marginBottom: 12 },
  techLabel: {
    width: 96,
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.5,
  },
  techTrack: {
    flex: 1,
    height: 8,
    borderRadius: 4,
    backgroundColor: "rgba(255,255,255,0.07)",
    overflow: "hidden",
    marginHorizontal: 10,
  },
  techFill: { height: "100%", borderRadius: 4 },
  techValue: { width: 30, textAlign: "right", fontSize: 15, fontWeight: "900" },
  // Badges
  badgeRow: { flexDirection: "row", justifyContent: "space-between" },
  badgeCell: { alignItems: "center", width: (SCREEN_W - spacing.lg * 2 - 24) / 4 },
  badgeHex: {
    width: 52,
    height: 52,
    borderRadius: 16,
    borderWidth: 1.5,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 8,
  },
  badgeLabel: { fontSize: 11, fontWeight: "800", textAlign: "center" },
  badgeSub: {
    color: colors.primary,
    fontSize: 9,
    fontWeight: "700",
    textAlign: "center",
    marginTop: 2,
  },
  // Quote
  quoteCard: { padding: spacing.lg, marginBottom: spacing.lg },
  quoteMark: {
    color: colors.primary,
    fontSize: 40,
    fontWeight: "900",
    height: 34,
    marginBottom: 4,
  },
  quoteText: {
    color: colors.textPrimary,
    fontSize: 16,
    fontStyle: "italic",
    lineHeight: 24,
  },
  quoteAuthor: {
    color: colors.primary,
    fontSize: 14,
    fontWeight: "700",
    fontStyle: "italic",
    textAlign: "right",
    marginTop: spacing.sm,
  },
});
