import { useCallback, useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  RefreshControl,
  TouchableOpacity,
  ActivityIndicator,
  Image,
  ScrollView,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useFocusEffect, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import {
  AnalysisListItem,
  fetchMe,
  listAnalyses,
  User,
} from "../../src/api";
import { colors, scoreColor, spacing } from "../../src/theme";
import { PRO_INSPIRATIONS } from "../../src/proInspirations";

export default function DashboardScreen() {
  const router = useRouter();
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
      // Best-effort push registration on first load (no-op on web)
      try {
        const { registerForPushNotificationsAsync } = await import(
          "../../src/push"
        );
        registerForPushNotificationsAsync();
      } catch {}
    } catch (e) {
      console.warn("load failed", e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [router]);

  useEffect(() => {
    load();
  }, [load]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const onRefresh = () => {
    setRefreshing(true);
    load();
  };

  const stats = {
    total: items.length,
    avgScore:
      items.length > 0
        ? Math.round(
            items.reduce((s, i) => s + (i.score || 0), 0) / items.length
          )
        : 0,
    best: items.length > 0 ? Math.max(...items.map((i) => i.score || 0)) : 0,
  };

  const renderItem = ({ item }: { item: AnalysisListItem }) => {
    const date = new Date(item.created_at);
    const dateStr = date.toLocaleDateString(undefined, {
      month: "short",
      day: "2-digit",
      year: "numeric",
    });
    return (
      <TouchableOpacity
        style={styles.card}
        activeOpacity={0.85}
        onPress={() => router.push(`/analysis/${item.analysis_id}` as any)}
        testID={`analysis-card-${item.analysis_id}`}
      >
        <View style={styles.cardLeft}>
          <Text style={styles.cardDate}>{dateStr.toUpperCase()}</Text>
          <Text style={styles.cardTitle} numberOfLines={1}>
            {item.title || "Surf Session"}
          </Text>
          <Text style={styles.cardSummary} numberOfLines={2}>
            {item.summary || item.overall_rating}
          </Text>
          <View style={styles.cardTags}>
            <View style={styles.tag}>
              <Text style={styles.tagText}>
                {(item.overall_rating || "—").toUpperCase()}
              </Text>
            </View>
            <View
              style={[
                styles.tag,
                {
                  borderColor:
                    item.status === "ready"
                      ? colors.success
                      : colors.warning,
                },
              ]}
            >
              <Text
                style={[
                  styles.tagText,
                  {
                    color:
                      item.status === "ready"
                        ? colors.success
                        : colors.warning,
                  },
                ]}
              >
                {item.status.toUpperCase()}
              </Text>
            </View>
          </View>
        </View>
        <View style={styles.cardRight}>
          <Text
            style={[styles.scoreText, { color: scoreColor(item.score || 0) }]}
          >
            {item.score || 0}
          </Text>
          <Text style={styles.scoreLabel}>SCORE</Text>
          <Ionicons
            name="chevron-forward"
            size={18}
            color={colors.textMuted}
            style={{ marginTop: 6 }}
          />
        </View>
      </TouchableOpacity>
    );
  };

  if (loading) {
    return (
      <SafeAreaView style={[styles.container, styles.center]}>
        <ActivityIndicator color={colors.primary} size="large" />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={["top"]} testID="dashboard-screen">
      <FlatList
        data={items}
        keyExtractor={(i) => i.analysis_id}
        renderItem={renderItem}
        contentContainerStyle={{ paddingBottom: 32 }}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={colors.primary}
          />
        }
        ListHeaderComponent={
          <View style={styles.header}>
            <View style={styles.brandRow}>
              <View style={styles.brandDot} />
              <Text style={styles.brandLabel}>SURFCOACH · 23</Text>
            </View>
            <Text style={styles.greeting}>
              Hey, {user?.name?.split(" ")[0] || "Surfer"}
            </Text>
            <Text style={styles.heading}>YOUR{"\n"}SESSIONS.</Text>

            <View style={styles.statsGrid}>
              <View style={styles.statCard}>
                <Text style={styles.statValue}>{stats.total}</Text>
                <Text style={styles.statLabel}>Sessions</Text>
              </View>
              <View style={styles.statCard}>
                <Text
                  style={[
                    styles.statValue,
                    { color: scoreColor(stats.avgScore) },
                  ]}
                >
                  {stats.avgScore}
                </Text>
                <Text style={styles.statLabel}>Avg Score</Text>
              </View>
              <View style={styles.statCard}>
                <Text
                  style={[styles.statValue, { color: scoreColor(stats.best) }]}
                >
                  {stats.best}
                </Text>
                <Text style={styles.statLabel}>Best</Text>
              </View>
            </View>

            <TouchableOpacity
              style={styles.ctaBtn}
              onPress={() => router.push("/(tabs)/upload")}
              testID="dashboard-new-analysis-btn"
            >
              <Ionicons name="add" size={18} color="#000" />
              <Text style={styles.ctaText}>New Analysis</Text>
            </TouchableOpacity>

            {/* Pro Inspirations carousel */}
            <Text style={styles.sectionLabel}>Trained on the Pros</Text>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              style={{ marginHorizontal: -spacing.lg, marginBottom: spacing.lg }}
              contentContainerStyle={{ paddingHorizontal: spacing.lg, gap: 10 }}
              testID="pro-inspirations"
            >
              {PRO_INSPIRATIONS.map((p) => (
                <View
                  key={p.name}
                  style={styles.proCard}
                  testID={`pro-${p.name.replace(/\s+/g, "-").toLowerCase()}`}
                >
                  <Image source={{ uri: p.image }} style={styles.proImage} />
                  <View style={styles.proOverlay} />
                  <View style={styles.proLabels}>
                    <Text style={styles.proTag}>{p.tag}</Text>
                    <Text style={styles.proName}>
                      {p.name.toUpperCase()}
                    </Text>
                  </View>
                </View>
              ))}
            </ScrollView>

            <Text style={styles.sectionLabel}>Past Analyses</Text>
          </View>
        }
        ListEmptyComponent={
          <View style={styles.empty} testID="empty-state">
            <Ionicons
              name="film-outline"
              size={48}
              color={colors.textMuted}
            />
            <Text style={styles.emptyTitle}>No clips yet</Text>
            <Text style={styles.emptySub}>
              Upload your first surfing video to get a full AI breakdown.
            </Text>
          </View>
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { alignItems: "center", justifyContent: "center" },
  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  brandRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: spacing.lg,
  },
  brandDot: { width: 8, height: 8, backgroundColor: colors.primary },
  brandLabel: {
    color: colors.primary,
    fontSize: 11,
    letterSpacing: 4,
    fontWeight: "800",
  },
  greeting: {
    color: colors.textSecondary,
    fontSize: 14,
    letterSpacing: 1.2,
  },
  heading: {
    color: colors.textPrimary,
    fontSize: 44,
    fontWeight: "900",
    letterSpacing: -2,
    lineHeight: 44,
    textTransform: "uppercase",
    marginTop: 6,
    marginBottom: spacing.lg,
  },
  statsGrid: {
    flexDirection: "row",
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  statCard: {
    flex: 1,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    borderRadius: 4,
  },
  statValue: {
    color: colors.textPrimary,
    fontSize: 28,
    fontWeight: "900",
    letterSpacing: -1,
  },
  statLabel: {
    color: colors.textMuted,
    fontSize: 10,
    letterSpacing: 2,
    textTransform: "uppercase",
    marginTop: 4,
  },
  ctaBtn: {
    backgroundColor: colors.primary,
    paddingVertical: 14,
    borderRadius: 4,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    marginBottom: spacing.lg,
  },
  ctaText: {
    color: "#000",
    fontWeight: "800",
    letterSpacing: 1,
    textTransform: "uppercase",
    fontSize: 13,
  },
  sectionLabel: {
    color: colors.textMuted,
    fontSize: 11,
    letterSpacing: 2.5,
    textTransform: "uppercase",
    fontWeight: "800",
    marginBottom: spacing.sm,
  },
  card: {
    flexDirection: "row",
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 4,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    padding: spacing.md,
  },
  cardLeft: { flex: 1, paddingRight: spacing.md },
  cardDate: {
    color: colors.textMuted,
    fontSize: 10,
    letterSpacing: 2,
    fontWeight: "700",
    marginBottom: 4,
  },
  cardTitle: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: "800",
    letterSpacing: -0.4,
    marginBottom: 4,
  },
  cardSummary: {
    color: colors.textSecondary,
    fontSize: 12,
    lineHeight: 17,
    marginBottom: 8,
  },
  cardTags: { flexDirection: "row", gap: 6 },
  tag: {
    borderWidth: 1,
    borderColor: colors.borderStrong,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  tagText: {
    color: colors.textSecondary,
    fontSize: 9,
    letterSpacing: 1.5,
    fontWeight: "800",
  },
  cardRight: {
    minWidth: 80,
    alignItems: "center",
    justifyContent: "center",
    borderLeftWidth: 1,
    borderLeftColor: colors.border,
    paddingLeft: spacing.md,
  },
  scoreText: { fontSize: 36, fontWeight: "900", letterSpacing: -2 },
  scoreLabel: {
    color: colors.textMuted,
    fontSize: 9,
    letterSpacing: 2,
    fontWeight: "700",
  },
  empty: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 60,
    paddingHorizontal: spacing.lg,
    gap: 10,
  },
  emptyTitle: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: "800",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  emptySub: {
    color: colors.textMuted,
    textAlign: "center",
    fontSize: 13,
    lineHeight: 19,
    maxWidth: 280,
  },
  proCard: {
    width: 200,
    height: 110,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  proImage: { width: "100%", height: "100%", resizeMode: "cover" },
  proOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(10,10,10,0.45)",
  },
  proLabels: {
    position: "absolute",
    left: 12,
    bottom: 10,
    right: 12,
  },
  proTag: {
    color: colors.primary,
    fontSize: 9,
    letterSpacing: 1.8,
    fontWeight: "800",
    marginBottom: 2,
  },
  proName: {
    color: colors.textPrimary,
    fontSize: 13,
    letterSpacing: 0.5,
    fontWeight: "900",
  },
});
