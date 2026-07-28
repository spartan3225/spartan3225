import { useCallback, useMemo, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ImageBackground,
  Modal,
  Image,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useFocusEffect, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { Analysis, getAnalysis, listAnalyses } from "../../src/api";
import { colors, radii, spacing } from "../../src/theme";
import { useI18n } from "../../src/i18n";
import { haptic } from "../../src/haptics";
import GlassCard from "../../src/components/GlassCard";
import YouTubeEmbed from "../../src/components/YouTubeEmbed";
import { DRILLS, DrillCategory, TUTORIALS } from "../../src/trainLibrary";

const CATEGORIES: { key: DrillCategory | "all"; labelKey: string }[] = [
  { key: "all", labelKey: "cat_all" },
  { key: "surf", labelKey: "cat_surf" },
  { key: "land", labelKey: "cat_land" },
  { key: "balance", labelKey: "cat_balance" },
  { key: "mobility", labelKey: "cat_mobility" },
  { key: "strength", labelKey: "cat_strength" },
];

export default function TrainScreen() {
  const router = useRouter();
  const { t } = useI18n();
  const [cat, setCat] = useState<DrillCategory | "all">("all");
  const [latest, setLatest] = useState<Analysis | null>(null);
  const [tutorial, setTutorial] = useState<(typeof TUTORIALS)[number] | null>(
    null
  );

  const load = useCallback(async () => {
    try {
      const list = await listAnalyses();
      const ready = list.find((i) => i.status === "ready");
      if (ready) setLatest(await getAnalysis(ready.analysis_id));
      else setLatest(null);
    } catch {}
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  // Personalized: weakest 3 skill categories from the latest analysis
  const recommended = useMemo(() => {
    if (!latest?.scores?.length) return [];
    const weakest = latest.scores
      .slice()
      .sort((a, b) => a.value - b.value)
      .slice(0, 3)
      .map((s) => s.key);
    const matches = DRILLS.filter((d) =>
      d.improves.some((k) => weakest.includes(k))
    );
    return matches.slice(0, 4);
  }, [latest]);

  const filtered = cat === "all" ? DRILLS : DRILLS.filter((d) => d.category === cat);

  return (
    <SafeAreaView style={styles.container} edges={["top"]} testID="train-screen">
      <ScrollView contentContainerStyle={{ paddingBottom: 120 }}>
        <View style={styles.header}>
          <Text style={styles.title}>{t("train_title")}</Text>
          <Text style={styles.sub}>{t("train_sub")}</Text>
        </View>

        {/* Personalized plan */}
        <GlassCard
          style={styles.planCard}
          accent={colors.primary}
          testID="personalized-plan"
        >
          <View style={styles.planHead}>
            <Ionicons name="sparkles" size={14} color={colors.primary} />
            <Text style={styles.planLabel}>
              {t("personalized_plan").toUpperCase()}
            </Text>
          </View>
          {latest ? (
            <>
              <Text style={styles.planSub}>{t("from_last_analysis")}</Text>
              {(latest.drills || []).slice(0, 3).map((d, i) => (
                <View key={i} style={styles.planRow}>
                  <View style={styles.planNum}>
                    <Text style={styles.planNumText}>{i + 1}</Text>
                  </View>
                  <Text style={styles.planText}>{d}</Text>
                </View>
              ))}
              {recommended.length > 0 && (
                <View style={styles.recRow}>
                  {recommended.map((d) => (
                    <View key={d.id} style={styles.recChip}>
                      <Ionicons name={d.icon as any} size={12} color={colors.primary} />
                      <Text style={styles.recChipText}>{t(d.titleKey)}</Text>
                    </View>
                  ))}
                </View>
              )}
            </>
          ) : (
            <TouchableOpacity
              style={styles.planEmpty}
              onPress={() => {
                haptic.tap();
                router.push("/(tabs)/upload" as any);
              }}
            >
              <Text style={styles.planEmptyText}>{t("no_plan_yet")}</Text>
              <Ionicons name="arrow-forward" size={14} color={colors.primary} />
            </TouchableOpacity>
          )}
        </GlassCard>

        {/* Video tutorials */}
        <Text style={styles.tutLabel}>{t("video_tutorials").toUpperCase()}</Text>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={{ marginBottom: spacing.md }}
          contentContainerStyle={{ paddingHorizontal: spacing.lg, gap: 10 }}
          testID="tutorials-row"
        >
          {TUTORIALS.map((tu) => (
            <TouchableOpacity
              key={tu.id}
              style={styles.tutCard}
              activeOpacity={0.85}
              onPress={() => {
                haptic.tap();
                setTutorial(tu);
              }}
              testID={`tutorial-${tu.id}`}
            >
              <Image
                source={{
                  uri: `https://img.youtube.com/vi/${tu.youtubeId}/hqdefault.jpg`,
                }}
                style={styles.tutThumb}
              />
              <View style={styles.tutPlay}>
                <Ionicons name="play" size={16} color="#000" />
              </View>
              <Text style={styles.tutTitle} numberOfLines={2}>
                {tu.title}
              </Text>
              <Text style={styles.tutCat}>{t(`cat_${tu.category}`)}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Category filter */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={{ marginBottom: spacing.md }}
          contentContainerStyle={{ paddingHorizontal: spacing.lg, gap: 8 }}
        >
          {CATEGORIES.map((c) => (
            <TouchableOpacity
              key={c.key}
              style={[styles.chip, cat === c.key && styles.chipActive]}
              onPress={() => {
                haptic.tap();
                setCat(c.key);
              }}
              testID={`cat-${c.key}`}
            >
              <Text style={[styles.chipText, cat === c.key && styles.chipTextActive]}>
                {t(c.labelKey)}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Drill grid */}
        <View style={styles.grid}>
          {filtered.map((d) => (
            <View key={d.id} style={styles.drillCard} testID={`drill-${d.id}`}>
              <ImageBackground
                source={{ uri: d.image }}
                style={styles.drillImage}
                imageStyle={{ borderTopLeftRadius: radii.md, borderTopRightRadius: radii.md }}
              >
                <LinearGradient
                  colors={["transparent", "rgba(10,10,10,0.9)"]}
                  style={StyleSheet.absoluteFill}
                />
                <View style={styles.drillIcon}>
                  <Ionicons name={d.icon as any} size={16} color={colors.primary} />
                </View>
              </ImageBackground>
              <View style={styles.drillBody}>
                <Text style={styles.drillTitle} numberOfLines={1}>
                  {t(d.titleKey)}
                </Text>
                <Text style={styles.drillDesc} numberOfLines={3}>
                  {t(d.descKey)}
                </Text>
                <View style={styles.goalRow}>
                  <Ionicons name="flag-outline" size={11} color={colors.success} />
                  <Text style={styles.goalText} numberOfLines={1}>
                    {t(d.goalKey)}
                  </Text>
                </View>
              </View>
            </View>
          ))}
        </View>
      </ScrollView>

      {/* Tutorial player modal */}
      <Modal
        visible={!!tutorial}
        transparent
        animationType="slide"
        onRequestClose={() => setTutorial(null)}
      >
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard} testID="tutorial-modal">
            <View style={styles.modalHead}>
              <Text style={styles.modalTitle} numberOfLines={2}>
                {tutorial?.title}
              </Text>
              <TouchableOpacity
                onPress={() => setTutorial(null)}
                style={styles.modalClose}
                testID="tutorial-close"
              >
                <Ionicons name="close" size={20} color={colors.textPrimary} />
              </TouchableOpacity>
            </View>
            {tutorial && <YouTubeEmbed videoId={tutorial.youtubeId} />}
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, marginBottom: spacing.md },
  title: { color: colors.textPrimary, fontSize: 32, fontWeight: "900", letterSpacing: -1 },
  sub: { color: colors.textSecondary, fontSize: 13, marginTop: 4 },
  planCard: { marginHorizontal: spacing.lg, marginBottom: spacing.md },
  planHead: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 4 },
  planLabel: { color: colors.primary, fontSize: 10, letterSpacing: 2.5, fontWeight: "800" },
  planSub: { color: colors.textMuted, fontSize: 11, marginBottom: 10 },
  planRow: { flexDirection: "row", gap: 10, marginBottom: 8, alignItems: "flex-start" },
  planNum: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: "rgba(0,229,255,0.14)",
    alignItems: "center",
    justifyContent: "center",
    marginTop: 1,
  },
  planNumText: { color: colors.primary, fontSize: 11, fontWeight: "800" },
  planText: { flex: 1, color: colors.textSecondary, fontSize: 13, lineHeight: 18 },
  recRow: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 6 },
  recChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    backgroundColor: "rgba(0,229,255,0.08)",
    borderWidth: 1,
    borderColor: "rgba(0,229,255,0.25)",
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  recChipText: { color: colors.primary, fontSize: 11, fontWeight: "700" },
  planEmpty: { flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 6 },
  planEmptyText: { color: colors.textSecondary, fontSize: 13, flex: 1 },
  chip: {
    borderWidth: 1,
    borderColor: colors.glassBorder,
    backgroundColor: colors.glass,
    borderRadius: 999,
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { color: colors.textSecondary, fontSize: 12, fontWeight: "700" },
  chipTextActive: { color: "#000" },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
  },
  drillCard: {
    width: "48.5%",
    backgroundColor: colors.glass,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    borderRadius: radii.md,
    overflow: "hidden",
  },
  drillImage: { height: 92, justifyContent: "flex-end" },
  drillIcon: {
    position: "absolute",
    top: 8,
    right: 8,
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: "rgba(10,10,10,0.75)",
    alignItems: "center",
    justifyContent: "center",
  },
  drillBody: { padding: 12 },
  drillTitle: { color: colors.textPrimary, fontSize: 13, fontWeight: "800", marginBottom: 4 },
  drillDesc: { color: colors.textSecondary, fontSize: 11, lineHeight: 15, marginBottom: 8 },
  goalRow: { flexDirection: "row", alignItems: "center", gap: 5 },
  goalText: { color: colors.success, fontSize: 10, fontWeight: "700", flex: 1 },
  tutLabel: {
    color: colors.textMuted,
    fontSize: 11,
    letterSpacing: 2.5,
    fontWeight: "800",
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
  },
  tutCard: { width: 180 },
  tutThumb: {
    width: 180,
    height: 100,
    borderRadius: radii.md,
    backgroundColor: colors.surface,
  },
  tutPlay: {
    position: "absolute",
    top: 34,
    left: 74,
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  tutTitle: {
    color: colors.textPrimary,
    fontSize: 12,
    fontWeight: "700",
    marginTop: 6,
    lineHeight: 16,
  },
  tutCat: { color: colors.primary, fontSize: 10, fontWeight: "700", marginTop: 2 },
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.85)",
    justifyContent: "center",
    padding: spacing.lg,
  },
  modalCard: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    padding: spacing.md,
  },
  modalHead: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginBottom: spacing.sm,
  },
  modalTitle: { flex: 1, color: colors.textPrimary, fontSize: 15, fontWeight: "800" },
  modalClose: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: "rgba(255,255,255,0.08)",
    alignItems: "center",
    justifyContent: "center",
  },
});
