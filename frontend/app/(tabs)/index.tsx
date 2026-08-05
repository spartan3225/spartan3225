import { useCallback, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
  ImageBackground,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useFocusEffect, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { AnalysisListItem, fetchMe, listAnalyses, User } from "../../src/api";
import { colors, radii, scoreColor, spacing, IMAGES } from "../../src/theme";
import { useI18n } from "../../src/i18n";
import { haptic } from "../../src/haptics";
import ScoreRing from "../../src/components/ScoreRing";
import GlassCard from "../../src/components/GlassCard";
import Skeleton from "../../src/components/Skeleton";

export default function HomeScreen() {
  const router = useRouter();
  const { t } = useI18n();
  const [items, setItems] = useState<AnalysisListItem[]>([]);
  const [user, setUser] = useState<User | null>(null);
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
  const latest = ready[0];
  const stats = {
    total: items.length,
    avg: ready.length
      ? Math.round(ready.reduce((s, i) => s + (i.score || 0), 0) / ready.length)
      : 0,
    best: ready.length ? Math.max(...ready.map((i) => i.score || 0)) : 0,
  };

  const go = (path: string) => {
    haptic.tap();
    router.push(path as any);
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={["top"]}>
        <View style={{ padding: spacing.lg, gap: 14 }}>
          <Skeleton height={26} width={180} />
          <Skeleton height={190} radius={radii.lg} />
          <Skeleton height={90} radius={radii.lg} />
          <Skeleton height={70} radius={radii.lg} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={["top"]} testID="dashboard-screen">
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
          <View style={styles.brandRow}>
            <View style={styles.brandDot} />
            <Text style={styles.brandLabel}>SURFCOACH · 23</Text>
          </View>
          <Text style={styles.greeting}>
            {t("greeting")}, {user?.name?.split(" ")[0] || "Surfer"}
          </Text>
          <Text style={styles.headline}>{t("home_headline")}</Text>
        </View>

        {/* Hero — latest session */}
        <View style={styles.heroWrap}>
          <ImageBackground
            source={{ uri: IMAGES.darkOcean }}
            style={styles.hero}
            imageStyle={{ borderRadius: radii.lg }}
          >
            <LinearGradient
              colors={["rgba(10,10,10,0.25)", "rgba(10,10,10,0.92)"]}
              style={[StyleSheet.absoluteFill, { borderRadius: radii.lg }]}
            />
            {latest ? (
              <TouchableOpacity
                style={styles.heroInner}
                activeOpacity={0.9}
                onPress={() => go(`/analysis/${latest.analysis_id}`)}
                testID="latest-session-card"
              >
                <View style={{ flex: 1 }}>
                  <Text style={styles.heroLabel}>
                    {t("latest_session").toUpperCase()}
                  </Text>
                  <Text style={styles.heroTitle} numberOfLines={2}>
                    {latest.title}
                  </Text>
                  <Text style={styles.heroSub} numberOfLines={2}>
                    {latest.summary}
                  </Text>
                  <View style={styles.heroCta}>
                    <Text style={styles.heroCtaText}>
                      {t("review_title").toUpperCase()}
                    </Text>
                    <Ionicons name="arrow-forward" size={14} color={colors.primary} />
                  </View>
                </View>
                <ScoreRing value={latest.score} size={92} thickness={7} />
              </TouchableOpacity>
            ) : (
              <TouchableOpacity
                style={[styles.heroInner, { alignItems: "center" }]}
                activeOpacity={0.9}
                onPress={() => go("/(tabs)/upload")}
                testID="hero-upload-cta"
              >
                <View style={{ flex: 1 }}>
                  <Text style={styles.heroTitle}>{t("no_sessions_title")}</Text>
                  <Text style={styles.heroSub}>{t("no_sessions_sub")}</Text>
                </View>
                <View style={styles.heroPlus}>
                  <Ionicons name="add" size={28} color="#000" />
                </View>
              </TouchableOpacity>
            )}
          </ImageBackground>
        </View>

        {/* Quick actions */}
        <View style={styles.actionsRow}>
          <QuickAction
            icon="sparkles"
            label={t("analyze_now")}
            primary
            onPress={() => go("/(tabs)/upload")}
            testID="dashboard-new-analysis-btn"
          />
          <QuickAction
            icon="trending-up"
            label={t("view_progress")}
            onPress={() => go("/(tabs)/progress")}
          />
          <QuickAction
            icon="barbell"
            label={t("start_training")}
            onPress={() => go("/(tabs)/train")}
          />
        </View>

        {/* Stats */}
        <View style={styles.statsRow}>
          <GlassCard style={styles.statCard}>
            <Text style={styles.statValue}>{stats.total}</Text>
            <Text style={styles.statLabel}>{t("sessions")}</Text>
          </GlassCard>
          <GlassCard style={styles.statCard}>
            <Text style={[styles.statValue, { color: scoreColor(stats.avg) }]}>
              {stats.avg}
            </Text>
            <Text style={styles.statLabel}>{t("avg_score")}</Text>
          </GlassCard>
          <GlassCard style={styles.statCard}>
            <Text style={[styles.statValue, { color: scoreColor(stats.best) }]}>
              {stats.best}
            </Text>
            <Text style={styles.statLabel}>{t("best")}</Text>
          </GlassCard>
        </View>

        {/* AI insight */}
        {latest?.summary ? (
          <GlassCard style={styles.insightCard} accent={colors.primary}>
            <View style={styles.insightHead}>
              <Ionicons name="sparkles" size={14} color={colors.primary} />
              <Text style={styles.insightLabel}>
                {t("ai_insight").toUpperCase()}
              </Text>
            </View>
            <Text style={styles.insightText} numberOfLines={4}>
              {latest.summary}
            </Text>
          </GlassCard>
        ) : null}

        {/* Recent sessions */}
        {items.length > 0 && (
          <View style={{ paddingHorizontal: spacing.lg }}>
            <View style={styles.sectionHead}>
              <Text style={styles.sectionLabel}>
                {t("recent_sessions").toUpperCase()}
              </Text>
              <TouchableOpacity onPress={() => go("/(tabs)/review")}>
                <Text style={styles.viewAll}>{t("view_all")}</Text>
              </TouchableOpacity>
            </View>
            {items.slice(0, 4).map((item) => (
              <TouchableOpacity
                key={item.analysis_id}
                style={styles.sessionRow}
                activeOpacity={0.85}
                onPress={() => go(`/analysis/${item.analysis_id}`)}
                testID={`analysis-card-${item.analysis_id}`}
              >
                <ScoreRing
                  value={item.score}
                  size={44}
                  thickness={4}
                  valueSize={13}
                />
                <View style={{ flex: 1 }}>
                  <Text style={styles.sessionTitle} numberOfLines={1}>
                    {item.title || "Surf Session"}
                  </Text>
                  <Text style={styles.sessionDate}>
                    {new Date(item.created_at).toLocaleDateString(undefined, {
                      month: "short",
                      day: "2-digit",
                    })}
                    {"  ·  "}
                    <Text
                      style={{
                        color:
                          item.status === "ready"
                            ? colors.success
                            : item.status === "failed"
                            ? colors.error
                            : colors.warning,
                      }}
                    >
                      {t(item.status === "ready" ? "ready" : item.status === "failed" ? "failed" : "processing")}
                    </Text>
                  </Text>
                </View>
                <Ionicons name="chevron-forward" size={16} color={colors.textMuted} />
              </TouchableOpacity>
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function QuickAction({
  icon,
  label,
  onPress,
  primary,
  testID,
}: {
  icon: any;
  label: string;
  onPress: () => void;
  primary?: boolean;
  testID?: string;
}) {
  return (
    <TouchableOpacity
      style={[styles.actionCard, primary && styles.actionPrimary]}
      onPress={onPress}
      activeOpacity={0.85}
      testID={testID}
    >
      <Ionicons name={icon} size={20} color={primary ? "#000" : colors.primary} />
      <Text
        style={[styles.actionLabel, primary && { color: "#000" }]}
        numberOfLines={2}
      >
        {label}
      </Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: { paddingHorizontal: spacing.lg, paddingTop: spacing.md },
  brandRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: spacing.md,
  },
  brandDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.primary },
  brandLabel: { color: colors.primary, fontSize: 11, letterSpacing: 4, fontWeight: "800" },
  greeting: { color: colors.textSecondary, fontSize: 14, letterSpacing: 0.4 },
  headline: {
    color: colors.textPrimary,
    fontSize: 34,
    fontWeight: "900",
    letterSpacing: -1.2,
    lineHeight: 38,
    marginTop: 4,
    marginBottom: spacing.md,
  },
  heroWrap: { paddingHorizontal: spacing.lg, marginBottom: spacing.md },
  hero: { borderRadius: radii.lg, overflow: "hidden" },
  heroInner: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.lg,
    minHeight: 170,
  },
  heroLabel: {
    color: colors.primary,
    fontSize: 10,
    letterSpacing: 3,
    fontWeight: "800",
    marginBottom: 6,
  },
  heroTitle: {
    color: colors.textPrimary,
    fontSize: 22,
    fontWeight: "800",
    letterSpacing: -0.5,
    marginBottom: 6,
  },
  heroSub: { color: colors.textSecondary, fontSize: 13, lineHeight: 18 },
  heroCta: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 12 },
  heroCtaText: { color: colors.primary, fontSize: 11, fontWeight: "800", letterSpacing: 2 },
  heroPlus: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  actionsRow: {
    flexDirection: "row",
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  actionCard: {
    flex: 1,
    backgroundColor: colors.glass,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    borderRadius: radii.md,
    paddingVertical: 14,
    paddingHorizontal: 10,
    alignItems: "center",
    gap: 8,
    minHeight: 78,
    justifyContent: "center",
  },
  actionPrimary: { backgroundColor: colors.primary, borderColor: colors.primary },
  actionLabel: {
    color: colors.textPrimary,
    fontSize: 11,
    fontWeight: "700",
    textAlign: "center",
    lineHeight: 14,
  },
  statsRow: {
    flexDirection: "row",
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  statCard: { flex: 1, alignItems: "center", paddingVertical: 14 },
  statValue: { color: colors.textPrimary, fontSize: 24, fontWeight: "900", letterSpacing: -1 },
  statLabel: { color: colors.textMuted, fontSize: 10, letterSpacing: 1, marginTop: 2, textTransform: "uppercase" },
  insightCard: { marginHorizontal: spacing.lg, marginBottom: spacing.lg },
  insightHead: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 8 },
  insightLabel: { color: colors.primary, fontSize: 10, letterSpacing: 2.5, fontWeight: "800" },
  insightText: { color: colors.textSecondary, fontSize: 13, lineHeight: 20 },
  sectionHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.sm,
  },
  sectionLabel: { color: colors.textMuted, fontSize: 11, letterSpacing: 2.5, fontWeight: "800" },
  viewAll: { color: colors.primary, fontSize: 12, fontWeight: "700" },
  sessionRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.glass,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    borderRadius: radii.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  sessionTitle: { color: colors.textPrimary, fontSize: 14, fontWeight: "700" },
  sessionDate: { color: colors.textMuted, fontSize: 11, marginTop: 2 },
});
