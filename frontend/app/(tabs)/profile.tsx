import { useCallback, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Image,
  ImageBackground,
  ScrollView,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useFocusEffect, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import {
  fetchMe,
  listAnalyses,
  logout,
  User,
  getQuota,
  Quota,
} from "../../src/api";
import { colors, scoreColor, spacing } from "../../src/theme";

const BG =
  "https://images.unsplash.com/photo-1618502396341-5c680e7d7233?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMzl8MHwxfHNlYXJjaHwxfHxkYXJrJTIwb2NlYW4lMjB3YXZlJTIwdGV4dHVyZXxlbnwwfHx8fDE3NzgyMzYwOTd8MA&ixlib=rb-4.1.0&q=85";

export default function ProfileScreen() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [stats, setStats] = useState({ total: 0, avg: 0, best: 0, latest: "—" });
  const [quota, setQuota] = useState<Quota | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const me = await fetchMe();
    if (!me) {
      router.replace("/");
      return;
    }
    setUser(me);
    try {
      const [list, q] = await Promise.all([listAnalyses(), getQuota()]);
      const total = list.length;
      const avg =
        total > 0
          ? Math.round(list.reduce((s, i) => s + (i.score || 0), 0) / total)
          : 0;
      const best = total > 0 ? Math.max(...list.map((i) => i.score || 0)) : 0;
      const latest = list[0]
        ? new Date(list[0].created_at).toLocaleDateString()
        : "—";
      setStats({ total, avg, best, latest });
      setQuota(q);
    } catch {}
    setLoading(false);
  }, [router]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const onLogout = async () => {
    await logout();
    router.replace("/");
  };

  if (loading || !user) {
    return (
      <SafeAreaView style={[styles.container, styles.center]}>
        <ActivityIndicator color={colors.primary} size="large" />
      </SafeAreaView>
    );
  }

  const isCoach = user.tier === "coach";
  const expDate = user.subscription_expires_at
    ? new Date(user.subscription_expires_at).toLocaleDateString()
    : null;

  return (
    <SafeAreaView style={styles.container} edges={["top"]} testID="profile-screen">
      <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>
        <ImageBackground source={{ uri: BG }} style={styles.headerBg}>
          <View style={styles.headerOverlay} />
          <View style={styles.headerContent}>
            <View style={styles.brandRow}>
              <View style={styles.brandDot} />
              <Text style={styles.brandLabel}>SURFER · PROFILE</Text>
            </View>
            <View style={styles.userRow}>
              {user.picture ? (
                <Image source={{ uri: user.picture }} style={styles.avatar} />
              ) : (
                <View style={[styles.avatar, styles.avatarPlaceholder]}>
                  <Ionicons name="person" size={28} color={colors.textSecondary} />
                </View>
              )}
              <View style={{ flex: 1 }}>
                <Text style={styles.name} numberOfLines={1}>
                  {user.name}
                </Text>
                <Text style={styles.email} numberOfLines={1}>
                  {user.email}
                </Text>
                <View style={styles.tierBadgeRow}>
                  <View
                    style={[
                      styles.tierBadge,
                      isCoach && styles.tierBadgeCoach,
                    ]}
                    testID="tier-badge"
                  >
                    <Ionicons
                      name={isCoach ? "ribbon" : "person"}
                      size={11}
                      color={isCoach ? "#000" : colors.textPrimary}
                      style={{ marginRight: 4 }}
                    />
                    <Text
                      style={[
                        styles.tierText,
                        isCoach && { color: "#000" },
                      ]}
                    >
                      {isCoach ? "COACH PLAN" : "FREE PLAN"}
                    </Text>
                  </View>
                </View>
              </View>
            </View>
          </View>
        </ImageBackground>

        <View style={styles.body}>
          {/* Quota / Plan card */}
          <View style={styles.quotaCard} testID="quota-card">
            <View style={{ flex: 1 }}>
              <Text style={styles.quotaLabel}>
                {isCoach ? "ANALYSES TODAY" : "FREE QUOTA TODAY"}
              </Text>
              <Text style={styles.quotaValue}>
                {isCoach
                  ? "Unlimited"
                  : `${(quota?.used_today ?? 0)} / ${(quota?.limit ?? 1)}`}
              </Text>
              {isCoach && expDate ? (
                <Text style={styles.quotaSub}>Renews {expDate}</Text>
              ) : null}
              {!isCoach ? (
                <Text style={styles.quotaSub}>
                  {quota && quota.remaining > 0
                    ? `${quota.remaining} left today`
                    : "Daily limit reached. Upgrade for unlimited."}
                </Text>
              ) : null}
            </View>
            <TouchableOpacity
              style={[styles.upgradeBtn, isCoach && styles.manageBtn]}
              onPress={() => router.push("/paywall" as any)}
              testID={isCoach ? "manage-plan-btn" : "upgrade-btn"}
            >
              <Ionicons
                name={isCoach ? "settings-outline" : "rocket"}
                size={14}
                color={isCoach ? colors.textPrimary : "#000"}
                style={{ marginRight: 6 }}
              />
              <Text
                style={[
                  styles.upgradeBtnText,
                  isCoach && { color: colors.textPrimary },
                ]}
              >
                {isCoach ? "Plans" : "Upgrade"}
              </Text>
            </TouchableOpacity>
          </View>

          {/* Coach quick actions */}
          {isCoach && (
            <View style={styles.actionGrid}>
              <TouchableOpacity
                style={styles.actionCard}
                onPress={() => router.push("/coach-inbox" as any)}
                testID="goto-inbox-btn"
              >
                <Ionicons
                  name="mail-outline"
                  size={22}
                  color={colors.primary}
                />
                <Text style={styles.actionTitle}>Inbox</Text>
                <Text style={styles.actionSub}>Shared clips</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.actionCard}
                onPress={() => router.push("/coach-edit" as any)}
                testID="goto-coach-edit-btn"
              >
                <Ionicons
                  name="create-outline"
                  size={22}
                  color={colors.primary}
                />
                <Text style={styles.actionTitle}>Coach Page</Text>
                <Text style={styles.actionSub}>Edit your profile</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* Manage Plan link (visible when user has any subscription state) */}
          {isCoach && (
            <TouchableOpacity
              style={styles.linkRow}
              onPress={() => router.push("/manage-plan" as any)}
              testID="manage-plan-link"
            >
              <Ionicons
                name="card-outline"
                size={20}
                color={colors.primary}
              />
              <Text style={styles.linkText}>Manage Subscription</Text>
              <Ionicons
                name="chevron-forward"
                size={18}
                color={colors.textMuted}
              />
            </TouchableOpacity>
          )}

          {/* Browse coaches (everyone) */}
          <TouchableOpacity
            style={styles.linkRow}
            onPress={() => router.push("/coaches" as any)}
            testID="browse-coaches-btn"
          >
            <Ionicons
              name="people-outline"
              size={20}
              color={colors.primary}
            />
            <Text style={styles.linkText}>Browse Coaches</Text>
            <Ionicons
              name="chevron-forward"
              size={18}
              color={colors.textMuted}
            />
          </TouchableOpacity>

          <Text style={styles.sectionLabel}>Performance</Text>
          <View style={styles.bento}>
            <View style={[styles.bentoCard, styles.bentoBig]}>
              <Text style={styles.bentoLabel}>Avg Score</Text>
              <Text
                style={[styles.bentoValue, { color: scoreColor(stats.avg) }]}
              >
                {stats.avg}
              </Text>
              <Text style={styles.bentoFoot}>
                across {stats.total} sessions
              </Text>
            </View>
            <View style={styles.bentoCol}>
              <View style={styles.bentoCard}>
                <Text style={styles.bentoLabel}>Best</Text>
                <Text
                  style={[
                    styles.bentoValueSm,
                    { color: scoreColor(stats.best) },
                  ]}
                >
                  {stats.best}
                </Text>
              </View>
              <View style={styles.bentoCard}>
                <Text style={styles.bentoLabel}>Sessions</Text>
                <Text style={styles.bentoValueSm}>{stats.total}</Text>
              </View>
            </View>
          </View>

          <TouchableOpacity
            style={styles.logoutBtn}
            onPress={onLogout}
            testID="logout-btn"
          >
            <Ionicons name="log-out-outline" size={18} color={colors.error} />
            <Text style={styles.logoutText}>Log out</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { alignItems: "center", justifyContent: "center" },
  headerBg: { height: 240 },
  headerOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(10,10,10,0.65)",
  },
  headerContent: {
    flex: 1,
    padding: spacing.lg,
    justifyContent: "flex-end",
  },
  brandRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: spacing.md,
  },
  brandDot: { width: 8, height: 8, backgroundColor: colors.primary },
  brandLabel: {
    color: colors.primary,
    fontSize: 11,
    letterSpacing: 4,
    fontWeight: "800",
  },
  userRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  avatar: {
    width: 64,
    height: 64,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: colors.primary,
  },
  avatarPlaceholder: {
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  name: {
    color: colors.textPrimary,
    fontSize: 22,
    fontWeight: "900",
    letterSpacing: -0.5,
  },
  email: { color: colors.textSecondary, fontSize: 13, marginTop: 2 },
  tierBadgeRow: { marginTop: 6, flexDirection: "row" },
  tierBadge: {
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  tierBadgeCoach: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  tierText: {
    color: colors.textPrimary,
    fontSize: 9,
    letterSpacing: 1.5,
    fontWeight: "900",
  },
  body: { padding: spacing.lg },
  quotaCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  quotaLabel: {
    color: colors.textMuted,
    fontSize: 10,
    letterSpacing: 2,
    fontWeight: "800",
  },
  quotaValue: {
    color: colors.textPrimary,
    fontSize: 22,
    fontWeight: "900",
    marginTop: 2,
    letterSpacing: -0.5,
  },
  quotaSub: { color: colors.textMuted, fontSize: 12, marginTop: 4 },
  upgradeBtn: {
    backgroundColor: colors.primary,
    paddingHorizontal: 14,
    paddingVertical: 10,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
  },
  manageBtn: {
    backgroundColor: "transparent",
    borderWidth: 1,
    borderColor: colors.border,
  },
  upgradeBtnText: {
    color: "#000",
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  actionGrid: {
    flexDirection: "row",
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  actionCard: {
    flex: 1,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
  },
  actionTitle: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: "800",
    marginTop: 6,
  },
  actionSub: {
    color: colors.textMuted,
    fontSize: 11,
    marginTop: 2,
  },
  linkRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    paddingVertical: 14,
    paddingHorizontal: spacing.md,
    marginBottom: spacing.lg,
  },
  linkText: {
    flex: 1,
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: "700",
    letterSpacing: 0.5,
  },
  sectionLabel: {
    color: colors.textMuted,
    fontSize: 11,
    letterSpacing: 2.5,
    textTransform: "uppercase",
    fontWeight: "800",
    marginBottom: spacing.md,
  },
  bento: { flexDirection: "row", gap: spacing.sm },
  bentoCard: {
    flex: 1,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    minHeight: 90,
  },
  bentoBig: { minHeight: 140 },
  bentoCol: { flex: 1, gap: spacing.sm },
  bentoLabel: {
    color: colors.textMuted,
    fontSize: 10,
    letterSpacing: 2,
    fontWeight: "700",
    textTransform: "uppercase",
    marginBottom: 6,
  },
  bentoValue: {
    color: colors.textPrimary,
    fontSize: 56,
    fontWeight: "900",
    letterSpacing: -3,
  },
  bentoValueSm: {
    color: colors.textPrimary,
    fontSize: 24,
    fontWeight: "900",
    letterSpacing: -1,
  },
  bentoFoot: { color: colors.textMuted, fontSize: 11, marginTop: 4 },
  logoutBtn: {
    marginTop: spacing.xl,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 14,
    borderWidth: 1,
    borderColor: colors.error,
    gap: 8,
  },
  logoutText: {
    color: colors.error,
    fontSize: 13,
    letterSpacing: 1.5,
    fontWeight: "800",
    textTransform: "uppercase",
  },
});
