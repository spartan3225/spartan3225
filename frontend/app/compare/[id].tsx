import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  ImageBackground,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { VideoView, useVideoPlayer } from "expo-video";
import {
  Analysis,
  getAnalysis,
  getToken,
  getVideoStreamUrl,
  getProVideoUrl,
  getProPose,
  PoseData,
} from "../../src/api";
import { colors, radii, scoreColor, spacing, SCORE_CATEGORIES } from "../../src/theme";
import { useI18n } from "../../src/i18n";
import { haptic } from "../../src/haptics";
import GlassCard from "../../src/components/GlassCard";
import RadarChart from "../../src/components/RadarChart";
import PoseOverlay from "../../src/components/PoseOverlay";
import { PRO_BENCHMARKS } from "../../src/proBenchmarks";

const RADAR_KEYS = [
  "surf_flow",
  "take_off",
  "bottom_turn",
  "speed_generation",
  "balance",
  "wave_reading",
];

export default function CompareScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { t } = useI18n();
  const [data, setData] = useState<Analysis | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [proId, setProId] = useState("bottom_turn");
  const [proPose, setProPose] = useState<PoseData | null>(null);
  const [proTime, setProTime] = useState(0);
  const [proLayout, setProLayout] = useState({ w: 0, h: 0 });

  const pro =
    PRO_BENCHMARKS.find((p) => p.id === proId) || PRO_BENCHMARKS[0];
  const proVideoUrl = getProVideoUrl(pro.clipId);

  useEffect(() => {
    (async () => {
      try {
        if (!id) return;
        const [d, tok] = await Promise.all([getAnalysis(id), getToken()]);
        setData(d);
        if (tok) setVideoUrl(getVideoStreamUrl(d.analysis_id, tok));
      } catch {}
      setLoading(false);
    })();
  }, [id]);

  // Load the pro reference skeleton whenever the selected maneuver changes.
  useEffect(() => {
    let cancelled = false;
    setProPose(null);
    (async () => {
      try {
        const res = await getProPose(pro.clipId);
        if (!cancelled && res.status === "ready") setProPose(res.data);
      } catch {}
    })();
    return () => {
      cancelled = true;
    };
  }, [pro.clipId]);

  const player = useVideoPlayer(videoUrl || null, (p) => {
    p.loop = true;
    p.muted = true;
  });

  const proPlayer = useVideoPlayer(proVideoUrl || null, (p) => {
    p.loop = true;
    p.muted = true;
    p.play();
  });

  // Ticker to sync the skeleton overlay to the reference video time.
  useEffect(() => {
    const t = setInterval(() => {
      try {
        setProTime(proPlayer.currentTime || 0);
      } catch {}
    }, 100);
    return () => clearInterval(t);
  }, [proPlayer]);

  if (loading) {
    return (
      <SafeAreaView style={[styles.container, styles.center]}>
        <ActivityIndicator color={colors.primary} size="large" />
      </SafeAreaView>
    );
  }

  const pro2 = pro;
  const userScores: Record<string, number> = {};
  (data?.scores || []).forEach((s) => {
    userScores[s.key] = s.value;
  });
  const cats = (SCORE_CATEGORIES as readonly string[]).filter(
    (k) => userScores[k] !== undefined
  );
  const radarAxes = RADAR_KEYS.filter((k) => userScores[k] !== undefined).map(
    (k) => ({
      label: t(`score_${k}`),
      value: userScores[k],
      compare: pro2.scores[k],
    })
  );

  return (
    <SafeAreaView style={styles.container} edges={["top"]} testID="compare-screen">
      <ScrollView contentContainerStyle={{ paddingBottom: 64 }}>
        <View style={styles.topBar}>
          <TouchableOpacity
            onPress={() => router.back()}
            style={styles.iconBtn}
            testID="compare-back-btn"
          >
            <Ionicons name="chevron-back" size={22} color={colors.textPrimary} />
          </TouchableOpacity>
          <Text style={styles.topBarLabel}>
            {t("compare_title").toUpperCase()}
          </Text>
          <View style={{ width: 32 }} />
        </View>

        {/* Pro selector */}
        <Text style={styles.sectionTitle}>
          {t("pro_reference").toUpperCase()}
        </Text>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={{
            paddingHorizontal: spacing.lg,
            gap: 8,
            paddingBottom: spacing.md,
          }}
        >
          {PRO_BENCHMARKS.map((p) => (
            <TouchableOpacity
              key={p.id}
              disabled={!p.available}
              style={[
                styles.proChip,
                proId === p.id && styles.proChipActive,
                !p.available && { opacity: 0.45 },
              ]}
              onPress={() => {
                haptic.tap();
                setProId(p.id);
              }}
              testID={`pro-${p.id}`}
            >
              <Text
                style={[styles.proChipText, proId === p.id && { color: "#000" }]}
              >
                {p.country} {t(p.name)}
              </Text>
              {!p.available && (
                <Text style={styles.soonText}>{t("coming_soon")}</Text>
              )}
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Split screen: you vs pro */}
        <View style={styles.splitWrap} testID="split-screen">
          <View style={styles.splitCell}>
            <View style={styles.splitTag}>
              <Text style={styles.splitTagText}>{t("you").toUpperCase()}</Text>
            </View>
            {videoUrl ? (
              <VideoView
                player={player}
                style={styles.splitVideo}
                contentFit="cover"
                nativeControls={false}
              />
            ) : (
              <View style={[styles.splitVideo, styles.center]}>
                <Ionicons name="film-outline" size={30} color={colors.textMuted} />
              </View>
            )}
          </View>
          <View style={styles.splitCell}>
            <View style={[styles.splitTag, { backgroundColor: colors.success }]}>
              <Text style={styles.splitTagText}>{t(pro.name).toUpperCase()}</Text>
            </View>
            <View
              style={styles.splitVideo}
              onLayout={(e) =>
                setProLayout({
                  w: e.nativeEvent.layout.width,
                  h: e.nativeEvent.layout.height,
                })
              }
            >
              <VideoView
                player={proPlayer}
                style={StyleSheet.absoluteFill}
                contentFit="cover"
                nativeControls={false}
              />
              {proPose && proLayout.w > 0 && (
                <View style={StyleSheet.absoluteFill} pointerEvents="none">
                  <PoseOverlay
                    data={proPose}
                    time={proTime}
                    width={proLayout.w}
                    height={proLayout.h}
                  />
                </View>
              )}
            </View>
          </View>
        </View>
        <Text style={styles.footnote}>{t("ref_footage_note")}</Text>

        {/* Radar: you vs pro */}
        {radarAxes.length >= 3 && (
          <GlassCard style={styles.card} testID="compare-radar">
            <View style={styles.legendRow}>
              <View style={styles.legendItem}>
                <View style={[styles.legendDot, { backgroundColor: colors.primary }]} />
                <Text style={styles.legendText}>{t("you")}</Text>
              </View>
              <View style={styles.legendItem}>
                <View style={[styles.legendDot, { backgroundColor: colors.success }]} />
                <Text style={styles.legendText}>{t(pro.name)}</Text>
              </View>
            </View>
            <RadarChart axes={radarAxes} />
          </GlassCard>
        )}

        {/* Metric bars: you vs pro */}
        {cats.length > 0 && (
          <GlassCard style={styles.card} testID="compare-bars">
            {cats.map((k) => {
              const u = userScores[k];
              const p = pro.scores[k] ?? 95;
              return (
                <View key={k} style={styles.metricBlock}>
                  <View style={styles.metricHead}>
                    <Text style={styles.metricName}>{t(`score_${k}`)}</Text>
                    <Text style={styles.metricDelta}>
                      {u - p > 0 ? "+" : ""}
                      {u - p}
                    </Text>
                  </View>
                  <View style={styles.barTrack}>
                    <View
                      style={[
                        styles.barFill,
                        { width: `${u}%`, backgroundColor: scoreColor(u) },
                      ]}
                    />
                  </View>
                  <View style={[styles.barTrack, { marginTop: 3 }]}>
                    <View
                      style={[
                        styles.barFill,
                        { width: `${p}%`, backgroundColor: colors.success, opacity: 0.55 },
                      ]}
                    />
                  </View>
                </View>
              );
            })}
          </GlassCard>
        )}

      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { alignItems: "center", justifyContent: "center" },
  topBar: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  topBarLabel: {
    color: colors.textMuted,
    letterSpacing: 3,
    fontSize: 11,
    fontWeight: "800",
  },
  iconBtn: { width: 32, height: 32, alignItems: "center", justifyContent: "center" },
  sectionTitle: {
    color: colors.textMuted,
    fontSize: 11,
    letterSpacing: 2.5,
    fontWeight: "800",
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    marginTop: spacing.sm,
  },
  proChip: {
    borderWidth: 1,
    borderColor: colors.glassBorder,
    backgroundColor: colors.glass,
    borderRadius: radii.md,
    paddingHorizontal: 14,
    paddingVertical: 10,
    alignItems: "center",
  },
  proChipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  proChipText: { color: colors.textPrimary, fontSize: 12, fontWeight: "800" },
  soonText: { color: colors.textMuted, fontSize: 9, marginTop: 2 },
  splitWrap: {
    flexDirection: "row",
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
  },
  splitCell: {
    flex: 1,
    borderRadius: radii.md,
    overflow: "hidden",
    backgroundColor: colors.surface,
  },
  splitTag: {
    position: "absolute",
    top: 8,
    left: 8,
    zIndex: 2,
    backgroundColor: colors.primary,
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  splitTagText: { color: "#000", fontSize: 8, fontWeight: "900", letterSpacing: 1 },
  splitVideo: { width: "100%", height: 150 },
  soonBig: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 1,
    marginTop: 6,
    textTransform: "uppercase",
  },
  footnote: {
    color: colors.textMuted,
    fontSize: 10,
    lineHeight: 14,
    paddingHorizontal: spacing.lg,
    marginTop: 8,
    marginBottom: spacing.sm,
  },
  card: { marginHorizontal: spacing.lg, marginBottom: spacing.md },
  legendRow: { flexDirection: "row", gap: 16, justifyContent: "center", marginBottom: 4 },
  legendItem: { flexDirection: "row", alignItems: "center", gap: 6 },
  legendDot: { width: 8, height: 8, borderRadius: 4 },
  legendText: { color: colors.textSecondary, fontSize: 11, fontWeight: "700" },
  metricBlock: { marginBottom: 12 },
  metricHead: { flexDirection: "row", justifyContent: "space-between", marginBottom: 4 },
  metricName: { color: colors.textSecondary, fontSize: 12, fontWeight: "700" },
  metricDelta: { color: colors.textMuted, fontSize: 11, fontWeight: "800" },
  barTrack: {
    height: 5,
    borderRadius: 3,
    backgroundColor: "rgba(255,255,255,0.08)",
    overflow: "hidden",
  },
  barFill: { height: 5, borderRadius: 3 },
});
