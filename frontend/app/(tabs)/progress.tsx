import { useCallback, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import Svg, { Polyline, Line, Circle } from "react-native-svg";
import {
  Analysis,
  AnalysisListItem,
  getAnalysis,
  listAnalyses,
} from "../../src/api";
import {
  colors,
  radii,
  scoreColor,
  spacing,
  SCORE_CATEGORIES,
} from "../../src/theme";
import { useI18n } from "../../src/i18n";
import ScoreRing from "../../src/components/ScoreRing";
import GlassCard from "../../src/components/GlassCard";
import Skeleton from "../../src/components/Skeleton";
import RadarChart from "../../src/components/RadarChart";

const RADAR_KEYS = [
  "surf_flow",
  "take_off",
  "bottom_turn",
  "speed_generation",
  "balance",
  "wave_reading",
];

function computeStreaks(dates: string[]): { current: number; longest: number } {
  // dates = ISO created_at strings
  const days = Array.from(
    new Set(dates.map((d) => new Date(d).toISOString().slice(0, 10)))
  ).sort();
  if (!days.length) return { current: 0, longest: 0 };
  const DAY = 86400000;
  let longest = 1;
  let run = 1;
  for (let i = 1; i < days.length; i++) {
    const diff = (Date.parse(days[i]) - Date.parse(days[i - 1])) / DAY;
    run = diff === 1 ? run + 1 : 1;
    if (run > longest) longest = run;
  }
  // current streak must end today or yesterday
  const today = new Date().toISOString().slice(0, 10);
  const last = days[days.length - 1];
  const gap = (Date.parse(today) - Date.parse(last)) / DAY;
  let current = 0;
  if (gap <= 1) {
    current = 1;
    for (let i = days.length - 1; i > 0; i--) {
      const diff = (Date.parse(days[i]) - Date.parse(days[i - 1])) / DAY;
      if (diff === 1) current++;
      else break;
    }
  }
  return { current, longest };
}

const CHART_W = 320;
const CHART_H = 120;

export default function ProgressScreen() {
  const { t } = useI18n();
  const [items, setItems] = useState<AnalysisListItem[]>([]);
  const [latest, setLatest] = useState<Analysis | null>(null);
  const [previous, setPrevious] = useState<Analysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const list = await listAnalyses();
      setItems(list);
      const ready = list.filter((i) => i.status === "ready");
      if (ready.length > 0) {
        const detailPromises = [getAnalysis(ready[0].analysis_id)];
        if (ready.length > 1) detailPromises.push(getAnalysis(ready[1].analysis_id));
        const details = await Promise.all(detailPromises);
        setLatest(details[0]);
        setPrevious(details[1] || null);
      }
    } catch (e) {
      console.warn("progress load failed", e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const ready = items
    .filter((i) => i.status === "ready")
    .slice()
    .reverse(); // chronological
  const scores = ready.map((i) => i.score || 0);
  const current = scores.length ? scores[scores.length - 1] : 0;
  const best = scores.length ? Math.max(...scores) : 0;
  const avg = scores.length
    ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)
    : 0;
  const delta =
    scores.length >= 2 ? current - scores[scores.length - 2] : 0;

  const prevScoreMap: Record<string, number> = {};
  (previous?.scores || []).forEach((s) => {
    prevScoreMap[s.key] = s.value;
  });
  const latestScores = (latest?.scores || []).filter((s) =>
    (SCORE_CATEGORIES as readonly string[]).includes(s.key)
  );
  const scoreMap: Record<string, number> = {};
  latestScores.forEach((s) => {
    scoreMap[s.key] = s.value;
  });
  const radarAxes = RADAR_KEYS.filter((k) => scoreMap[k] !== undefined).map(
    (k) => ({ label: t(`score_${k}`), value: scoreMap[k] })
  );
  const streaks = computeStreaks(
    items.filter((i) => i.status === "ready").map((i) => i.created_at)
  );
  const bestItem = ready.length
    ? ready.reduce((a, b) => ((b.score || 0) > (a.score || 0) ? b : a))
    : null;

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={["top"]}>
        <View style={{ padding: spacing.lg, gap: 14 }}>
          <Skeleton height={30} width={160} />
          <Skeleton height={150} radius={radii.lg} />
          <Skeleton height={160} radius={radii.lg} />
          <Skeleton height={200} radius={radii.lg} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={["top"]} testID="progress-screen">
      <ScrollView
        contentContainerStyle={{ paddingBottom: 120 }}
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
        <View style={styles.header}>
          <Text style={styles.title}>{t("progress_title")}</Text>
          <Text style={styles.sub}>{t("progress_sub")}</Text>
        </View>

        {scores.length === 0 ? (
          <View style={styles.empty} testID="progress-empty">
            <Ionicons name="analytics-outline" size={46} color={colors.textMuted} />
            <Text style={styles.emptyTitle}>{t("no_data_title")}</Text>
            <Text style={styles.emptySub}>{t("no_data_sub")}</Text>
          </View>
        ) : (
          <>
            {/* Headline metric */}
            <GlassCard style={styles.headCard} testID="progress-headline">
              <ScoreRing value={current} size={110} thickness={9} valueSize={34} />
              <View style={{ flex: 1, gap: 6 }}>
                <Text style={styles.headLabel}>{t("current").toUpperCase()}</Text>
                {delta !== 0 && (
                  <View
                    style={[
                      styles.deltaPill,
                      {
                        backgroundColor:
                          delta > 0 ? "rgba(0,255,136,0.12)" : "rgba(255,51,102,0.12)",
                      },
                    ]}
                  >
                    <Ionicons
                      name={delta > 0 ? "trending-up" : "trending-down"}
                      size={13}
                      color={delta > 0 ? colors.success : colors.error}
                    />
                    <Text
                      style={[
                        styles.deltaText,
                        { color: delta > 0 ? colors.success : colors.error },
                      ]}
                    >
                      {delta > 0 ? "+" : ""}
                      {delta} {t("vs_previous")}
                    </Text>
                  </View>
                )}
                <View style={styles.miniStatsRow}>
                  <MiniStat label={t("best_ever")} value={best} />
                  <MiniStat label={t("average")} value={avg} />
                  <MiniStat label={t("sessions")} value={scores.length} plain />
                </View>
              </View>
            </GlassCard>

            {/* Trend chart */}
            <GlassCard style={styles.chartCard} testID="score-trend-chart">
              <Text style={styles.sectionLabel}>
                {t("score_trend").toUpperCase()}
              </Text>
              <TrendChart data={scores.slice(-10)} />
              <Text style={styles.chartFoot}>
                {Math.min(scores.length, 10)} {t("last_sessions")}
              </Text>
            </GlassCard>

            {/* Skill radar */}
            {radarAxes.length >= 3 && (
              <GlassCard style={styles.chartCard} testID="skill-radar">
                <Text style={styles.sectionLabel}>
                  {t("skill_radar").toUpperCase()}
                </Text>
                <RadarChart axes={radarAxes} />
              </GlassCard>
            )}

            {/* Streaks + best wave */}
            <View style={styles.streakRow} testID="streaks-row">
              <GlassCard style={styles.streakCard}>
                <Ionicons name="flame" size={18} color={colors.warning} />
                <Text style={styles.streakValue}>{streaks.current}</Text>
                <Text style={styles.streakLabel}>{t("current_streak")}</Text>
              </GlassCard>
              <GlassCard style={styles.streakCard}>
                <Ionicons name="trophy" size={18} color={colors.primary} />
                <Text style={styles.streakValue}>{streaks.longest}</Text>
                <Text style={styles.streakLabel}>{t("longest_streak")}</Text>
              </GlassCard>
              <GlassCard style={styles.streakCard}>
                <Ionicons name="star" size={18} color={colors.success} />
                <Text style={[styles.streakValue, { color: scoreColor(bestItem?.score || 0) }]}>
                  {bestItem?.score ?? 0}
                </Text>
                <Text style={styles.streakLabel} numberOfLines={2}>
                  {t("best_wave")}
                </Text>
              </GlassCard>
            </View>

            {/* Skill evolution */}
            {latestScores.length > 0 && (
              <GlassCard style={styles.chartCard} testID="skill-evolution">
                <Text style={styles.sectionLabel}>
                  {t("skill_evolution").toUpperCase()}
                </Text>
                {latestScores.map((s) => {
                  const prev = prevScoreMap[s.key];
                  const d = prev !== undefined ? s.value - prev : null;
                  return (
                    <View key={s.key} style={styles.skillRow}>
                      <Text style={styles.skillName}>{t(`score_${s.key}`)}</Text>
                      <View style={styles.skillBarTrack}>
                        <View
                          style={[
                            styles.skillBarFill,
                            {
                              width: `${s.value}%`,
                              backgroundColor: scoreColor(s.value),
                            },
                          ]}
                        />
                      </View>
                      <Text style={[styles.skillValue, { color: scoreColor(s.value) }]}>
                        {s.value}
                      </Text>
                      {d !== null && d !== 0 ? (
                        <Text
                          style={[
                            styles.skillDelta,
                            { color: d > 0 ? colors.success : colors.error },
                          ]}
                        >
                          {d > 0 ? "+" : ""}
                          {d}
                        </Text>
                      ) : (
                        <Text style={styles.skillDelta}> </Text>
                      )}
                    </View>
                  );
                })}
              </GlassCard>
            )}

            {/* AI summary */}
            {latest?.summary ? (
              <GlassCard style={styles.chartCard} accent={colors.primary}>
                <View style={styles.aiHead}>
                  <Ionicons name="sparkles" size={14} color={colors.primary} />
                  <Text style={[styles.sectionLabel, { marginBottom: 0 }]}>
                    {t("ai_insight").toUpperCase()}
                  </Text>
                </View>
                <Text style={styles.aiText}>{latest.summary}</Text>
              </GlassCard>
            ) : null}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function MiniStat({
  label,
  value,
  plain,
}: {
  label: string;
  value: number;
  plain?: boolean;
}) {
  return (
    <View style={{ flex: 1 }}>
      <Text
        style={[
          styles.miniValue,
          !plain && { color: scoreColor(value) },
        ]}
      >
        {value}
      </Text>
      <Text style={styles.miniLabel} numberOfLines={1}>
        {label}
      </Text>
    </View>
  );
}

function TrendChart({ data }: { data: number[] }) {
  const pts = data.length === 1 ? [data[0], data[0]] : data;
  const stepX = CHART_W / (pts.length - 1);
  const toY = (v: number) => CHART_H - (v / 100) * CHART_H;
  const points = pts.map((v, i) => `${i * stepX},${toY(v)}`).join(" ");
  return (
    <View style={{ alignItems: "center" }}>
      <Svg width={CHART_W} height={CHART_H + 10}>
        {[25, 50, 75].map((g) => (
          <Line
            key={g}
            x1={0}
            y1={toY(g)}
            x2={CHART_W}
            y2={toY(g)}
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={1}
          />
        ))}
        <Polyline
          points={points}
          fill="none"
          stroke={colors.primary}
          strokeWidth={2.5}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {pts.map((v, i) => (
          <Circle
            key={i}
            cx={i * stepX}
            cy={toY(v)}
            r={3.5}
            fill={colors.background}
            stroke={colors.primary}
            strokeWidth={2}
          />
        ))}
      </Svg>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, marginBottom: spacing.md },
  title: { color: colors.textPrimary, fontSize: 32, fontWeight: "900", letterSpacing: -1 },
  sub: { color: colors.textSecondary, fontSize: 13, marginTop: 4 },
  empty: { alignItems: "center", paddingVertical: 60, paddingHorizontal: spacing.lg, gap: 10 },
  emptyTitle: { color: colors.textPrimary, fontSize: 16, fontWeight: "800" },
  emptySub: { color: colors.textMuted, textAlign: "center", fontSize: 13, lineHeight: 19, maxWidth: 280 },
  headCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.lg,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    padding: spacing.lg,
  },
  headLabel: { color: colors.textMuted, fontSize: 10, letterSpacing: 2.5, fontWeight: "800" },
  deltaPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    alignSelf: "flex-start",
    borderRadius: 999,
    paddingHorizontal: 9,
    paddingVertical: 4,
  },
  deltaText: { fontSize: 11, fontWeight: "800" },
  miniStatsRow: { flexDirection: "row", gap: 8, marginTop: 6 },
  miniValue: { color: colors.textPrimary, fontSize: 18, fontWeight: "900" },
  miniLabel: { color: colors.textMuted, fontSize: 9, letterSpacing: 0.5, textTransform: "uppercase", marginTop: 1 },
  chartCard: { marginHorizontal: spacing.lg, marginBottom: spacing.md },
  streakRow: {
    flexDirection: "row",
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  streakCard: { flex: 1, alignItems: "center", paddingVertical: 14, gap: 4 },
  streakValue: { color: colors.textPrimary, fontSize: 20, fontWeight: "900" },
  streakLabel: {
    color: colors.textMuted,
    fontSize: 9,
    letterSpacing: 0.5,
    textAlign: "center",
    textTransform: "uppercase",
  },
  sectionLabel: { color: colors.textMuted, fontSize: 11, letterSpacing: 2.5, fontWeight: "800", marginBottom: spacing.md },
  chartFoot: { color: colors.textMuted, fontSize: 10, textAlign: "center", marginTop: 6 },
  skillRow: { flexDirection: "row", alignItems: "center", gap: 10, marginBottom: 12 },
  skillName: { color: colors.textSecondary, fontSize: 12, fontWeight: "600", width: 108 },
  skillBarTrack: {
    flex: 1,
    height: 6,
    borderRadius: 3,
    backgroundColor: "rgba(255,255,255,0.08)",
    overflow: "hidden",
  },
  skillBarFill: { height: 6, borderRadius: 3 },
  skillValue: { fontSize: 12, fontWeight: "800", width: 26, textAlign: "right" },
  skillDelta: { fontSize: 10, fontWeight: "800", width: 26 },
  aiHead: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 10 },
  aiText: { color: colors.textSecondary, fontSize: 13, lineHeight: 20 },
});
