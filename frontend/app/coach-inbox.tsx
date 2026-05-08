import { useCallback, useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import {
  AnalysisListItem,
  coachInbox,
  fetchMe,
} from "../src/api";
import { colors, scoreColor, spacing } from "../src/theme";

export default function CoachInbox() {
  const router = useRouter();
  const [items, setItems] = useState<AnalysisListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const me = await fetchMe();
      if (!me) {
        router.replace("/");
        return;
      }
      if (me.tier !== "coach") {
        router.replace("/paywall");
        return;
      }
      const list = await coachInbox();
      setItems(list);
    } catch (e) {
      console.warn(e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [router]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <SafeAreaView style={[styles.container, styles.center]}>
        <ActivityIndicator color={colors.primary} size="large" />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} testID="coach-inbox-screen">
      <View style={styles.topBar}>
        <TouchableOpacity onPress={() => router.back()} testID="inbox-back-btn">
          <Ionicons name="chevron-back" size={22} color={colors.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.topTitle}>COACH INBOX</Text>
        <View style={{ width: 22 }} />
      </View>

      <FlatList
        data={items}
        keyExtractor={(i) => i.analysis_id}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: 40 }}
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
          <View style={{ marginBottom: spacing.md }}>
            <Text style={styles.heading}>SHARED{"\n"}WITH YOU.</Text>
            <Text style={styles.sub}>
              Clips students sent for your review.
            </Text>
          </View>
        }
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons
              name="mail-outline"
              size={42}
              color={colors.textMuted}
            />
            <Text style={styles.emptyText}>No clips yet</Text>
            <Text style={styles.emptySub}>
              Students will see you in the directory once your profile is
              public. Their shared clips appear here.
            </Text>
          </View>
        }
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.card}
            onPress={() =>
              router.push(`/analysis/${item.analysis_id}` as any)
            }
            testID={`inbox-card-${item.analysis_id}`}
          >
            <View style={{ flex: 1 }}>
              <Text style={styles.cardDate}>
                {new Date(item.created_at).toLocaleDateString().toUpperCase()}
              </Text>
              <Text style={styles.cardTitle} numberOfLines={1}>
                {item.title}
              </Text>
              <Text style={styles.cardSummary} numberOfLines={2}>
                {item.summary}
              </Text>
            </View>
            <View style={styles.scoreBox}>
              <Text
                style={[styles.scoreText, { color: scoreColor(item.score) }]}
              >
                {item.score}
              </Text>
              <Text style={styles.scoreLbl}>SCORE</Text>
            </View>
          </TouchableOpacity>
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { alignItems: "center", justifyContent: "center" },
  topBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  topTitle: {
    color: colors.textMuted,
    letterSpacing: 3,
    fontSize: 11,
    fontWeight: "800",
  },
  heading: {
    color: colors.textPrimary,
    fontSize: 36,
    fontWeight: "900",
    letterSpacing: -1.5,
    lineHeight: 38,
    textTransform: "uppercase",
  },
  sub: { color: colors.textSecondary, fontSize: 13, marginTop: 4 },
  card: {
    flexDirection: "row",
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.sm,
    gap: spacing.md,
    alignItems: "center",
  },
  cardDate: {
    color: colors.textMuted,
    fontSize: 10,
    letterSpacing: 2,
    fontWeight: "700",
    marginBottom: 4,
  },
  cardTitle: {
    color: colors.textPrimary,
    fontSize: 15,
    fontWeight: "800",
    marginBottom: 4,
  },
  cardSummary: {
    color: colors.textSecondary,
    fontSize: 12,
    lineHeight: 17,
  },
  scoreBox: {
    minWidth: 72,
    alignItems: "center",
    paddingLeft: spacing.md,
    borderLeftWidth: 1,
    borderLeftColor: colors.border,
  },
  scoreText: { fontSize: 30, fontWeight: "900", letterSpacing: -1 },
  scoreLbl: {
    color: colors.textMuted,
    fontSize: 9,
    letterSpacing: 2,
    fontWeight: "800",
  },
  empty: {
    alignItems: "center",
    paddingVertical: 40,
    gap: 8,
  },
  emptyText: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: "800",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  emptySub: {
    color: colors.textMuted,
    fontSize: 13,
    textAlign: "center",
    paddingHorizontal: spacing.lg,
  },
});
