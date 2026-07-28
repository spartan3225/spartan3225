import { useCallback, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  RefreshControl,
  TouchableOpacity,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useFocusEffect, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { AnalysisListItem, listAnalyses } from "../../src/api";
import { colors, radii, spacing } from "../../src/theme";
import { useI18n } from "../../src/i18n";
import { haptic } from "../../src/haptics";
import ScoreRing from "../../src/components/ScoreRing";
import Skeleton from "../../src/components/Skeleton";

export default function ReviewScreen() {
  const router = useRouter();
  const { t } = useI18n();
  const [items, setItems] = useState<AnalysisListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [band, setBand] = useState<"all" | "high" | "mid" | "low">("all");
  const [sort, setSort] = useState<"recent" | "best">("recent");

  const load = useCallback(async () => {
    try {
      setItems(await listAnalyses());
    } catch (e) {
      console.warn("load failed", e);
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

  const renderItem = ({ item }: { item: AnalysisListItem }) => {
    const statusColor =
      item.status === "ready"
        ? colors.success
        : item.status === "failed"
        ? colors.error
        : colors.warning;
    return (
      <TouchableOpacity
        style={styles.card}
        activeOpacity={0.85}
        onPress={() => {
          haptic.tap();
          router.push(`/analysis/${item.analysis_id}` as any);
        }}
        testID={`analysis-card-${item.analysis_id}`}
      >
        <ScoreRing value={item.score} size={56} thickness={5} valueSize={16} />
        <View style={{ flex: 1 }}>
          <Text style={styles.cardTitle} numberOfLines={1}>
            {item.title || "Surf Session"}
          </Text>
          <Text style={styles.cardSummary} numberOfLines={2}>
            {item.summary || item.overall_rating}
          </Text>
          <View style={styles.metaRow}>
            <Text style={styles.cardDate}>
              {new Date(item.created_at).toLocaleDateString(undefined, {
                month: "short",
                day: "2-digit",
                year: "numeric",
              })}
            </Text>
            <View style={[styles.statusPill, { borderColor: `${statusColor}55` }]}>
              <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
              <Text style={[styles.statusText, { color: statusColor }]}>
                {t(
                  item.status === "ready"
                    ? "ready"
                    : item.status === "failed"
                    ? "failed"
                    : "processing"
                )}
              </Text>
            </View>
          </View>
        </View>
        <Ionicons name="chevron-forward" size={16} color={colors.textMuted} />
      </TouchableOpacity>
    );
  };

  const shown = items
    .filter((i) => {
      if (band === "all") return true;
      const s = i.score || 0;
      if (band === "high") return s >= 80;
      if (band === "mid") return s >= 50 && s < 80;
      return s < 50;
    })
    .slice()
    .sort((a, b) =>
      sort === "best"
        ? (b.score || 0) - (a.score || 0)
        : Date.parse(b.created_at) - Date.parse(a.created_at)
    );

  return (
    <SafeAreaView style={styles.container} edges={["top"]} testID="review-screen">
      <FlatList
        data={shown}
        keyExtractor={(i) => i.analysis_id}
        renderItem={renderItem}
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
        ListHeaderComponent={
          <View style={styles.header}>
            <Text style={styles.title}>{t("review_title")}</Text>
            <Text style={styles.sub}>{t("review_sub")}</Text>
            <TouchableOpacity
              style={styles.ctaBtn}
              onPress={() => {
                haptic.light();
                router.push("/(tabs)/upload" as any);
              }}
              testID="review-new-analysis-btn"
            >
              <Ionicons name="add-circle" size={18} color="#000" />
              <Text style={styles.ctaText}>{t("new_analysis")}</Text>
            </TouchableOpacity>
            {items.length > 0 && (
              <>
                <Text style={styles.sectionLabel}>
                  {t("past_sessions").toUpperCase()}
                </Text>
                <View style={styles.filterRow} testID="review-filters">
                  {(
                    [
                      ["all", t("cat_all")],
                      ["high", "80+"],
                      ["mid", "50–79"],
                      ["low", "<50"],
                    ] as const
                  ).map(([key, label]) => (
                    <TouchableOpacity
                      key={key}
                      style={[styles.filterChip, band === key && styles.filterChipActive]}
                      onPress={() => {
                        haptic.tap();
                        setBand(key);
                      }}
                      testID={`filter-${key}`}
                    >
                      <Text
                        style={[styles.filterText, band === key && { color: "#000" }]}
                      >
                        {label}
                      </Text>
                    </TouchableOpacity>
                  ))}
                  <View style={{ flex: 1 }} />
                  <TouchableOpacity
                    style={styles.sortBtn}
                    onPress={() => {
                      haptic.tap();
                      setSort((s) => (s === "recent" ? "best" : "recent"));
                    }}
                    testID="sort-toggle"
                  >
                    <Ionicons
                      name={sort === "recent" ? "time-outline" : "podium-outline"}
                      size={13}
                      color={colors.primary}
                    />
                    <Text style={styles.sortText}>
                      {sort === "recent" ? t("sort_recent") : t("sort_best")}
                    </Text>
                  </TouchableOpacity>
                </View>
              </>
            )}
          </View>
        }
        ListEmptyComponent={
          loading ? (
            <View style={{ paddingHorizontal: spacing.lg, gap: 10 }}>
              <Skeleton height={86} radius={radii.md} />
              <Skeleton height={86} radius={radii.md} />
              <Skeleton height={86} radius={radii.md} />
            </View>
          ) : (
            <View style={styles.empty} testID="empty-state">
              <Ionicons name="film-outline" size={46} color={colors.textMuted} />
              <Text style={styles.emptyTitle}>{t("no_sessions_title")}</Text>
              <Text style={styles.emptySub}>{t("no_sessions_sub")}</Text>
            </View>
          )
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: { paddingHorizontal: spacing.lg, paddingTop: spacing.md },
  title: {
    color: colors.textPrimary,
    fontSize: 32,
    fontWeight: "900",
    letterSpacing: -1,
  },
  sub: { color: colors.textSecondary, fontSize: 13, marginTop: 4, marginBottom: spacing.md },
  ctaBtn: {
    backgroundColor: colors.primary,
    borderRadius: radii.md,
    paddingVertical: 15,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    marginBottom: spacing.lg,
  },
  ctaText: {
    color: "#000",
    fontWeight: "800",
    fontSize: 13,
    letterSpacing: 0.8,
    textTransform: "uppercase",
  },
  sectionLabel: {
    color: colors.textMuted,
    fontSize: 11,
    letterSpacing: 2.5,
    fontWeight: "800",
    marginBottom: spacing.sm,
  },
  filterRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: spacing.sm,
  },
  filterChip: {
    borderWidth: 1,
    borderColor: colors.glassBorder,
    backgroundColor: colors.glass,
    borderRadius: 999,
    paddingHorizontal: 11,
    paddingVertical: 6,
  },
  filterChipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  filterText: { color: colors.textSecondary, fontSize: 11, fontWeight: "700" },
  sortBtn: { flexDirection: "row", alignItems: "center", gap: 4 },
  sortText: { color: colors.primary, fontSize: 11, fontWeight: "700" },
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.glass,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    borderRadius: radii.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    padding: spacing.md,
  },
  cardTitle: { color: colors.textPrimary, fontSize: 15, fontWeight: "800", letterSpacing: -0.3 },
  cardSummary: { color: colors.textSecondary, fontSize: 12, lineHeight: 16, marginTop: 3 },
  metaRow: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 6 },
  cardDate: { color: colors.textMuted, fontSize: 10, letterSpacing: 1, fontWeight: "700" },
  statusPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  statusDot: { width: 5, height: 5, borderRadius: 3 },
  statusText: { fontSize: 9, fontWeight: "800", letterSpacing: 1, textTransform: "uppercase" },
  empty: { alignItems: "center", paddingVertical: 50, paddingHorizontal: spacing.lg, gap: 10 },
  emptyTitle: { color: colors.textPrimary, fontSize: 16, fontWeight: "800" },
  emptySub: { color: colors.textMuted, textAlign: "center", fontSize: 13, lineHeight: 19, maxWidth: 280 },
});
