import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  Switch,
  TouchableOpacity,
  ActivityIndicator,
  Platform,
  Alert,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { fetchMe, updateCoachProfile, User } from "../src/api";
import { colors, spacing } from "../src/theme";

export default function CoachEdit() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [bio, setBio] = useState("");
  const [specialty, setSpecialty] = useState("");
  const [location, setLocation] = useState("");
  const [isPublic, setIsPublic] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      const me = await fetchMe();
      if (!me) {
        router.replace("/");
        return;
      }
      if (me.tier !== "coach") {
        router.replace("/paywall");
        return;
      }
      setUser(me);
      setBio(me.coach_bio || "");
      setSpecialty(me.coach_specialty || "");
      setLocation(me.coach_location || "");
      setIsPublic(!!me.coach_public);
      setLoading(false);
    })();
  }, [router]);

  const save = async () => {
    setSaving(true);
    try {
      await updateCoachProfile({
        bio,
        specialty,
        location,
        public: isPublic,
      });
      const msg = "Coach profile saved.";
      if (Platform.OS === "web") {
        if (typeof window !== "undefined") window.alert(msg);
      } else {
        Alert.alert("Saved", msg);
      }
      router.back();
    } catch (e: any) {
      const msg = e?.message || "Save failed";
      if (Platform.OS === "web") {
        if (typeof window !== "undefined") window.alert(msg);
      } else {
        Alert.alert("Error", msg);
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading || !user) {
    return (
      <SafeAreaView style={[styles.container, styles.center]}>
        <ActivityIndicator color={colors.primary} size="large" />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} testID="coach-edit-screen">
      <View style={styles.topBar}>
        <TouchableOpacity onPress={() => router.back()} testID="coach-edit-back-btn">
          <Ionicons name="chevron-back" size={22} color={colors.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.topTitle}>COACH PROFILE</Text>
        <View style={{ width: 22 }} />
      </View>

      <ScrollView contentContainerStyle={styles.body}>
        <Text style={styles.heading}>YOUR{"\n"}COACH PAGE.</Text>
        <Text style={styles.sub}>
          Set your specialty and bio. Toggle public to appear in the directory.
        </Text>

        <Field label="Specialty">
          <TextInput
            value={specialty}
            onChangeText={setSpecialty}
            placeholder="e.g. Pop-up & beginners"
            placeholderTextColor={colors.textMuted}
            style={styles.input}
            maxLength={120}
            testID="coach-specialty-input"
          />
        </Field>
        <Field label="Location">
          <TextInput
            value={location}
            onChangeText={setLocation}
            placeholder="e.g. Ericeira, PT"
            placeholderTextColor={colors.textMuted}
            style={styles.input}
            maxLength={120}
            testID="coach-location-input"
          />
        </Field>
        <Field label="Bio">
          <TextInput
            value={bio}
            onChangeText={setBio}
            placeholder="Tell surfers about your style and credentials..."
            placeholderTextColor={colors.textMuted}
            style={[styles.input, styles.textarea]}
            multiline
            maxLength={600}
            testID="coach-bio-input"
          />
          <Text style={styles.counter}>{bio.length}/600</Text>
        </Field>

        <View style={styles.toggleRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.toggleLabel}>Public profile</Text>
            <Text style={styles.toggleSub}>
              Listed in the coaches directory.
            </Text>
          </View>
          <Switch
            value={isPublic}
            onValueChange={setIsPublic}
            trackColor={{ false: colors.border, true: colors.primary }}
            thumbColor={isPublic ? "#000" : colors.textSecondary}
            testID="coach-public-switch"
          />
        </View>

        <TouchableOpacity
          style={[styles.saveBtn, saving && { opacity: 0.5 }]}
          onPress={save}
          disabled={saving}
          testID="coach-save-btn"
        >
          {saving ? (
            <ActivityIndicator color="#000" />
          ) : (
            <Text style={styles.saveText}>Save Profile</Text>
          )}
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <View style={{ marginBottom: spacing.md }}>
      <Text style={styles.label}>{label.toUpperCase()}</Text>
      {children}
    </View>
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
  body: { padding: spacing.lg, paddingBottom: 64 },
  heading: {
    color: colors.textPrimary,
    fontSize: 36,
    fontWeight: "900",
    letterSpacing: -1.5,
    lineHeight: 38,
    textTransform: "uppercase",
    marginBottom: 6,
  },
  sub: {
    color: colors.textSecondary,
    fontSize: 13,
    lineHeight: 19,
    marginBottom: spacing.lg,
  },
  label: {
    color: colors.textMuted,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "800",
    marginBottom: 6,
  },
  input: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    color: colors.textPrimary,
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
    fontSize: 14,
  },
  textarea: { minHeight: 120, textAlignVertical: "top" },
  counter: {
    color: colors.textMuted,
    fontSize: 11,
    textAlign: "right",
    marginTop: 4,
  },
  toggleRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.md,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.lg,
  },
  toggleLabel: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: "800",
  },
  toggleSub: { color: colors.textMuted, fontSize: 12, marginTop: 2 },
  saveBtn: {
    backgroundColor: colors.primary,
    paddingVertical: 16,
    alignItems: "center",
    justifyContent: "center",
  },
  saveText: {
    color: "#000",
    fontSize: 14,
    fontWeight: "900",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
});
