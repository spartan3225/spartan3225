import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  Image,
  ActivityIndicator,
  Alert,
  Platform,
  TextInput,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import {
  CoachListItem,
  listCoaches,
  shareWithCoach,
} from "../src/api";
import { colors, spacing } from "../src/theme";

export default function CoachesDirectory() {
  const router = useRouter();
  const { share_analysis_id } = useLocalSearchParams<{
    share_analysis_id?: string;
  }>();
  const [coaches, setCoaches] = useState<CoachListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [location, setLocation] = useState("");
  const [specialty, setSpecialty] = useState("");

  const fetchData = async () => {
    setLoading(true);
    try {
      const list = await listCoaches({
        q: q.trim() || undefined,
        location: location.trim() || undefined,
        specialty: specialty.trim() || undefined,
      });
      setCoaches(list);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onPick = async (c: CoachListItem) => {
    if (!share_analysis_id) return;
    setBusy(c.user_id);
    try {
      await shareWithCoach(share_analysis_id, c.user_id);
      const msg = `Shared with ${c.name}. They'll see it in their inbox.`;
      if (Platform.OS === "web") {
        if (typeof window !== "undefined") window.alert(msg);
      } else {
        Alert.alert("Shared!", msg);
      }
      router.back();
    } catch (e: any) {
      const msg = e?.message || "Failed to share";
      if (Platform.OS === "web") {
        if (typeof window !== "undefined") window.alert(msg);
      } else {
        Alert.alert("Error", msg);
      }
    } finally {
      setBusy(null);
    }
  };

  return (
    <SafeAreaView
      style={styles.container}
      edges={["top"]}
      testID="coaches-screen"
    >
      <View style={styles.topBar}>
        <TouchableOpacity onPress={() => router.back()} testID="coaches-back-btn">
          <Ionicons name="chevron-back" size={22} color={colors.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.topTitle}>
          {share_analysis_id ? "PICK A COACH" : "COACHES"}
        </Text>
        <View style={{ width: 22 }} />
      </View>

      <View style={styles.header}>
        <Text style={styles.heading}>
          {share_analysis_id ? "SHARE WITH" : "MEET THE"}{"\n"}COACHES.
        </Text>
        <Text style={styles.sub}>
          {share_analysis_id
            ? "Send your clip to a coach and get personalised feedback."
            : "Browse our certified surf coaches. Tap one to view their profile."}
        </Text>
      </View>

      <View style={styles.filterBox}>
        <View style={styles.searchRow}>
          <Ionicons name="search" size={16} color={colors.textMuted} />
          <TextInput
            value={q}
            onChangeText={setQ}
            placeholder="Search name, bio…"
            placeholderTextColor={colors.textMuted}
            style={styles.searchInput}
            returnKeyType="search"
            onSubmitEditing={fetchData}
            testID="coaches-search-input"
          />
        </View>
        <View style={styles.filterRow}>
          <TextInput
            value={specialty}
            onChangeText={setSpecialty}
            placeholder="Specialty"
            placeholderTextColor={colors.textMuted}
            style={[styles.filterInput, { marginRight: spacing.sm }]}
            returnKeyType="search"
            onSubmitEditing={fetchData}
            testID="coaches-specialty-filter"
          />
          <TextInput
            value={location}
            onChangeText={setLocation}
            placeholder="Location"
            placeholderTextColor={colors.textMuted}
            style={styles.filterInput}
            returnKeyType="search"
            onSubmitEditing={fetchData}
            testID="coaches-location-filter"
          />
        </View>
        <TouchableOpacity
          style={styles.applyBtn}
          onPress={fetchData}
          testID="coaches-apply-filters-btn"
        >
          <Text style={styles.applyText}>Apply filters</Text>
        </TouchableOpacity>
      </View>

      {loading ? (
        <ActivityIndicator color={colors.primary} style={{ marginTop: 40 }} />
      ) : (
        <FlatList
          data={coaches}
          keyExtractor={(c) => c.user_id}
          contentContainerStyle={{ paddingBottom: 40 }}
          ListEmptyComponent={
            <View style={styles.empty}>
              <Ionicons name="people-outline" size={42} color={colors.textMuted} />
              <Text style={styles.emptyText}>No coaches yet.</Text>
              <Text style={styles.emptySub}>
                Be the first — upgrade to Coach and make your profile public.
              </Text>
            </View>
          }
          renderItem={({ item }) => (
            <TouchableOpacity
              style={styles.card}
              onPress={() => {
                if (share_analysis_id) {
                  onPick(item);
                } else {
                  router.push(`/coach/${item.user_id}` as any);
                }
              }}
              activeOpacity={0.85}
              disabled={busy === item.user_id}
              testID={`coach-card-${item.user_id}`}
            >
              {item.picture ? (
                <Image source={{ uri: item.picture }} style={styles.avatar} />
              ) : (
                <View style={[styles.avatar, styles.avatarFallback]}>
                  <Ionicons
                    name="person"
                    size={26}
                    color={colors.textSecondary}
                  />
                </View>
              )}
              <View style={{ flex: 1 }}>
                <Text style={styles.name} numberOfLines={1}>
                  {item.name}
                </Text>
                <Text style={styles.specialty} numberOfLines={1}>
                  {item.coach_specialty || "Surf Coach"}
                </Text>
                <Text style={styles.location} numberOfLines={1}>
                  {item.coach_location || ""}
                </Text>
              </View>
              {busy === item.user_id ? (
                <ActivityIndicator color={colors.primary} />
              ) : (
                <Ionicons
                  name={share_analysis_id ? "send" : "chevron-forward"}
                  size={18}
                  color={colors.primary}
                />
              )}
            </TouchableOpacity>
          )}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
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
  header: { padding: spacing.lg, paddingTop: spacing.sm },
  heading: {
    color: colors.textPrimary,
    fontSize: 36,
    fontWeight: "900",
    letterSpacing: -1.5,
    lineHeight: 38,
    textTransform: "uppercase",
    marginBottom: 6,
  },
  sub: { color: colors.textSecondary, fontSize: 13, lineHeight: 19 },
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    padding: spacing.md,
  },
  avatar: { width: 56, height: 56, borderRadius: 4 },
  avatarFallback: {
    backgroundColor: colors.surfaceElevated,
    alignItems: "center",
    justifyContent: "center",
  },
  name: {
    color: colors.textPrimary,
    fontSize: 15,
    fontWeight: "800",
    letterSpacing: -0.3,
  },
  specialty: {
    color: colors.primary,
    fontSize: 11,
    letterSpacing: 1.5,
    fontWeight: "700",
    textTransform: "uppercase",
    marginTop: 2,
  },
  location: { color: colors.textMuted, fontSize: 12, marginTop: 2 },
  empty: {
    alignItems: "center",
    justifyContent: "center",
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
  filterBox: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    marginBottom: spacing.sm,
  },
  searchRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.md,
    marginBottom: spacing.sm,
  },
  searchInput: {
    flex: 1,
    color: colors.textPrimary,
    paddingVertical: 10,
    fontSize: 14,
  },
  filterRow: { flexDirection: "row", marginBottom: spacing.sm },
  filterInput: {
    flex: 1,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    color: colors.textPrimary,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    fontSize: 13,
  },
  applyBtn: {
    backgroundColor: colors.primary,
    paddingVertical: 12,
    alignItems: "center",
  },
  applyText: {
    color: "#000",
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 1.5,
    textTransform: "uppercase",
  },
});
