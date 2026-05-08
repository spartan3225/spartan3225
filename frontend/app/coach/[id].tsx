import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Image,
  ActivityIndicator,
  TouchableOpacity,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { API_URL, CoachListItem } from "../../src/api";
import { colors, spacing } from "../../src/theme";

export default function CoachProfile() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [coach, setCoach] = useState<CoachListItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API_URL}/coaches/${id}`);
        if (!r.ok) throw new Error("Coach not found");
        setCoach(await r.json());
      } catch (e: any) {
        setError(e?.message || "Not found");
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  if (loading) {
    return (
      <SafeAreaView style={[styles.container, styles.center]}>
        <ActivityIndicator color={colors.primary} size="large" />
      </SafeAreaView>
    );
  }
  if (!coach) {
    return (
      <SafeAreaView style={[styles.container, styles.center]}>
        <Text style={{ color: colors.error }}>{error}</Text>
        <TouchableOpacity
          onPress={() => router.back()}
          style={styles.btn}
        >
          <Text style={styles.btnText}>Back</Text>
        </TouchableOpacity>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} testID="coach-profile-screen">
      <View style={styles.topBar}>
        <TouchableOpacity onPress={() => router.back()} testID="coach-back-btn">
          <Ionicons name="chevron-back" size={22} color={colors.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.topTitle}>COACH</Text>
        <View style={{ width: 22 }} />
      </View>

      <View style={styles.body}>
        {coach.picture ? (
          <Image source={{ uri: coach.picture }} style={styles.avatar} />
        ) : (
          <View style={[styles.avatar, styles.avatarFallback]}>
            <Ionicons name="person" size={48} color={colors.textSecondary} />
          </View>
        )}
        <Text style={styles.name}>{coach.name}</Text>
        {coach.coach_specialty ? (
          <Text style={styles.specialty}>{coach.coach_specialty}</Text>
        ) : null}
        {coach.coach_location ? (
          <Text style={styles.location}>
            <Ionicons name="location-outline" size={12} /> {coach.coach_location}
          </Text>
        ) : null}

        {coach.coach_bio ? (
          <View style={styles.bioBox}>
            <Text style={styles.bioLabel}>About</Text>
            <Text style={styles.bio}>{coach.coach_bio}</Text>
          </View>
        ) : null}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { alignItems: "center", justifyContent: "center", gap: 12 },
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
  body: { padding: spacing.lg, alignItems: "center" },
  avatar: {
    width: 130,
    height: 130,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: colors.primary,
  },
  avatarFallback: {
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  name: {
    color: colors.textPrimary,
    fontSize: 26,
    fontWeight: "900",
    letterSpacing: -1,
    marginTop: spacing.md,
  },
  specialty: {
    color: colors.primary,
    fontSize: 12,
    letterSpacing: 2.5,
    fontWeight: "800",
    textTransform: "uppercase",
    marginTop: 6,
  },
  location: { color: colors.textMuted, fontSize: 12, marginTop: 4 },
  bioBox: {
    width: "100%",
    marginTop: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    padding: spacing.md,
  },
  bioLabel: {
    color: colors.textMuted,
    fontSize: 11,
    letterSpacing: 2.5,
    fontWeight: "800",
    marginBottom: 6,
  },
  bio: { color: colors.textPrimary, fontSize: 14, lineHeight: 22 },
  btn: {
    paddingVertical: 10,
    paddingHorizontal: 24,
    borderWidth: 1,
    borderColor: colors.border,
  },
  btnText: { color: colors.textPrimary },
});
