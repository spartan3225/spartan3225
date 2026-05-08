import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  Platform,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import {
  cancelRenewal,
  fetchMe,
  resumeRenewal,
  User,
} from "../src/api";
import { colors, spacing } from "../src/theme";

export default function ManagePlan() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    const me = await fetchMe();
    if (!me) {
      router.replace("/");
      return;
    }
    setUser(me);
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, []);

  const notify = (title: string, msg: string) => {
    if (Platform.OS === "web") {
      if (typeof window !== "undefined") window.alert(msg);
    } else {
      Alert.alert(title, msg);
    }
  };

  const onCancel = async () => {
    if (!user) return;
    setSaving(true);
    try {
      const r = await cancelRenewal();
      notify(
        "Renewal cancelled",
        `Your Coach access stays active until ${
          r.subscription_expires_at
            ? new Date(r.subscription_expires_at).toLocaleDateString()
            : "your period end"
        }. After that you'll move to Free.`
      );
      await load();
    } catch (e: any) {
      notify("Error", e?.message || "Could not cancel renewal");
    } finally {
      setSaving(false);
    }
  };

  const onResume = async () => {
    setSaving(true);
    try {
      await resumeRenewal();
      notify("Renewal resumed", "We'll keep your Coach plan active.");
      await load();
    } catch (e: any) {
      notify("Error", e?.message || "Could not resume renewal");
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

  const PAID_TIERS = ["beginner", "plus", "intermediate", "advanced", "pro", "coach"];
  const isPaid = PAID_TIERS.includes(user.tier || "free");
  const isCoach = user.tier === "coach";
  const tierDisplay = (user.tier || "free").toUpperCase();
  const expDate = user.subscription_expires_at
    ? new Date(user.subscription_expires_at)
    : null;
  const cancelled = !!user.cancel_at_period_end;

  return (
    <SafeAreaView style={styles.container} testID="manage-plan-screen">
      <View style={styles.topBar}>
        <TouchableOpacity onPress={() => router.back()} testID="manage-back-btn">
          <Ionicons name="chevron-back" size={22} color={colors.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.topTitle}>MANAGE PLAN</Text>
        <View style={{ width: 22 }} />
      </View>

      <View style={styles.body}>
        <Text style={styles.heading}>YOUR{"\n"}SUBSCRIPTION.</Text>

        <View style={styles.card}>
          <Text style={styles.label}>CURRENT PLAN</Text>
          <Text style={styles.planName}>
            {tierDisplay}
          </Text>
          {isPaid && expDate ? (
            <Text style={styles.exp}>
              {cancelled ? "Ends on " : "Renews on "}
              {expDate.toLocaleDateString(undefined, {
                month: "short",
                day: "2-digit",
                year: "numeric",
              })}
            </Text>
          ) : null}
          {cancelled && (
            <View style={styles.warningPill} testID="cancelled-pill">
              <Ionicons
                name="alert-circle"
                size={12}
                color={colors.warning}
              />
              <Text style={styles.warningText}>RENEWAL CANCELLED</Text>
            </View>
          )}
        </View>

        {isPaid ? (
          <>
            <TouchableOpacity
              style={styles.outlineBtn}
              onPress={() => router.push("/paywall" as any)}
              testID="extend-plan-btn"
            >
              <Ionicons name="add-circle-outline" size={16} color={colors.primary} />
              <Text style={styles.outlineBtnText}>
                {isCoach ? "Extend +1 month" : "Change plan"}
              </Text>
            </TouchableOpacity>

            {cancelled ? (
              <TouchableOpacity
                style={[styles.primaryBtn, saving && { opacity: 0.5 }]}
                onPress={onResume}
                disabled={saving}
                testID="resume-renewal-btn"
              >
                {saving ? (
                  <ActivityIndicator color="#000" />
                ) : (
                  <>
                    <Ionicons name="play" size={14} color="#000" />
                    <Text style={styles.primaryBtnText}>Resume Renewal</Text>
                  </>
                )}
              </TouchableOpacity>
            ) : (
              <TouchableOpacity
                style={[styles.dangerBtn, saving && { opacity: 0.5 }]}
                onPress={onCancel}
                disabled={saving}
                testID="cancel-renewal-btn"
              >
                {saving ? (
                  <ActivityIndicator color={colors.error} />
                ) : (
                  <>
                    <Ionicons name="close" size={14} color={colors.error} />
                    <Text style={styles.dangerBtnText}>Cancel Renewal</Text>
                  </>
                )}
              </TouchableOpacity>
            )}
            <Text style={styles.legal}>
              Cancelling stops auto-renewal at the period end. You keep your
              current plan access until then.
            </Text>
          </>
        ) : (
          <TouchableOpacity
            style={styles.primaryBtn}
            onPress={() => router.replace("/paywall" as any)}
            testID="upgrade-from-manage-btn"
          >
            <Ionicons name="rocket" size={14} color="#000" />
            <Text style={styles.primaryBtnText}>See Plans</Text>
          </TouchableOpacity>
        )}
      </View>
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
  body: { padding: spacing.lg },
  heading: {
    color: colors.textPrimary,
    fontSize: 36,
    fontWeight: "900",
    letterSpacing: -1.5,
    lineHeight: 38,
    textTransform: "uppercase",
    marginBottom: spacing.lg,
  },
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
    marginBottom: spacing.lg,
  },
  label: {
    color: colors.textMuted,
    fontSize: 11,
    letterSpacing: 2.5,
    fontWeight: "800",
    marginBottom: 6,
  },
  planName: {
    color: colors.textPrimary,
    fontSize: 36,
    fontWeight: "900",
    letterSpacing: -1.5,
    marginBottom: 4,
  },
  exp: { color: colors.textSecondary, fontSize: 13 },
  warningPill: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    gap: 4,
    backgroundColor: "rgba(255,138,31,0.12)",
    borderColor: colors.warning,
    borderWidth: 1,
    paddingHorizontal: 8,
    paddingVertical: 3,
    marginTop: spacing.sm,
  },
  warningText: {
    color: colors.warning,
    fontSize: 10,
    fontWeight: "900",
    letterSpacing: 1.5,
  },
  outlineBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingVertical: 14,
    borderWidth: 1,
    borderColor: colors.primary,
    marginBottom: spacing.sm,
  },
  outlineBtnText: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  primaryBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingVertical: 14,
    backgroundColor: colors.primary,
  },
  primaryBtnText: {
    color: "#000",
    fontSize: 13,
    fontWeight: "900",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  dangerBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingVertical: 14,
    borderWidth: 1,
    borderColor: colors.error,
  },
  dangerBtnText: {
    color: colors.error,
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  legal: {
    color: colors.textMuted,
    fontSize: 11,
    textAlign: "center",
    marginTop: spacing.md,
    lineHeight: 16,
  },
});
