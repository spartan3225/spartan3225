import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Image,
  ImageBackground,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { fetchMe, listAnalyses, logout, User } from "../../src/api";
import { colors, scoreColor, spacing } from "../../src/theme";

const BG =
  "https://images.unsplash.com/photo-1618502396341-5c680e7d7233?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMzl8MHwxfHNlYXJjaHwxfHxkYXJrJTIwb2NlYW4lMjB3YXZlJTIwdGV4dHVyZXxlbnwwfHx8fDE3NzgyMzYwOTd8MA&ixlib=rb-4.1.0&q=85";

export default function ProfileScreen() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [stats, setStats] = useState({ total: 0, avg: 0, best: 0, latest: "—" });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const me = await fetchMe();
      if (!me) {
        router.replace("/");
        return;
      }
      setUser(me);
      try {
        const list = await listAnalyses();
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
      } catch {}
      setLoading(false);
    })();
  }, [router]);

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

  return (
    <SafeAreaView style={styles.container} edges={["top"]} testID="profile-screen">
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
                <Ionicons
                  name="person"
                  size={28}
                  color={colors.textSecondary}
                />
              </View>
            )}
            <View style={{ flex: 1 }}>
              <Text style={styles.name} numberOfLines={1}>
                {user.name}
              </Text>
              <Text style={styles.email} numberOfLines={1}>
                {user.email}
              </Text>
            </View>
          </View>
        </View>
      </ImageBackground>

      <View style={styles.body}>
        <Text style={styles.sectionLabel}>Performance</Text>

        <View style={styles.bento}>
          <View style={[styles.bentoCard, styles.bentoBig]}>
            <Text style={styles.bentoLabel}>Avg Score</Text>
            <Text
              style={[styles.bentoValue, { color: scoreColor(stats.avg) }]}
            >
              {stats.avg}
            </Text>
            <Text style={styles.bentoFoot}>across {stats.total} sessions</Text>
          </View>
          <View style={styles.bentoCol}>
            <View style={styles.bentoCard}>
              <Text style={styles.bentoLabel}>Best</Text>
              <Text
                style={[styles.bentoValueSm, { color: scoreColor(stats.best) }]}
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

        <View style={[styles.bentoCard, { marginTop: spacing.sm }]}>
          <Text style={styles.bentoLabel}>Latest Session</Text>
          <Text style={[styles.bentoValueSm, { fontSize: 18 }]}>
            {stats.latest}
          </Text>
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
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { alignItems: "center", justifyContent: "center" },
  headerBg: {
    height: 220,
  },
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
  email: {
    color: colors.textSecondary,
    fontSize: 13,
    marginTop: 2,
  },
  body: { flex: 1, padding: spacing.lg },
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
  bentoBig: {
    minHeight: 140,
  },
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
  bentoFoot: {
    color: colors.textMuted,
    fontSize: 11,
    marginTop: 4,
  },
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
