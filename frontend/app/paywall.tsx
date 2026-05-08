import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Platform,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import * as WebBrowser from "expo-web-browser";
import { createCheckout, getPlans, Plan } from "../src/api";
import { colors, spacing } from "../src/theme";

export default function PaywallScreen() {
  const router = useRouter();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await getPlans();
        setPlans(r.plans);
      } catch (e: any) {
        setError(e?.message || "Failed to load plans");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const upgrade = async (planId: "plus" | "coach") => {
    setError(null);
    setSubmitting(true);
    try {
      let originUrl = "";
      if (Platform.OS === "web" && typeof window !== "undefined") {
        originUrl = window.location.origin;
      } else {
        originUrl = (process.env.EXPO_PUBLIC_BACKEND_URL as string) || "";
      }
      const { url } = await createCheckout(planId, originUrl);
      if (Platform.OS === "web") {
        window.location.href = url;
      } else {
        const result = await WebBrowser.openAuthSessionAsync(
          url,
          `${originUrl}/payment-success`
        );
        if (result.type === "success" && result.url) {
          const m = result.url.match(/session_id=([^&#]+)/);
          if (m && m[1]) {
            router.replace(`/payment-success?session_id=${m[1]}` as any);
            return;
          }
        }
        router.replace("/payment-cancel" as any);
      }
    } catch (e: any) {
      setError(e?.message || "Could not start checkout");
      setSubmitting(false);
    }
  };

  const coach = plans.find((p) => p.plan_id === "coach");
  const plus = plans.find((p) => p.plan_id === "plus");
  const free = plans.find((p) => p.plan_id === "free");

  return (
    <SafeAreaView style={styles.container} edges={["top"]} testID="paywall-screen">
      <ScrollView contentContainerStyle={{ paddingBottom: 64 }}>
        <View style={styles.topBar}>
          <TouchableOpacity
            onPress={() => router.replace("/(tabs)")}
            testID="paywall-close-btn"
          >
            <Ionicons name="close" size={24} color={colors.textPrimary} />
          </TouchableOpacity>
          <Text style={styles.topTitle}>UPGRADE</Text>
          <TouchableOpacity
            onPress={() => router.replace("/(tabs)")}
            testID="paywall-skip-btn"
          >
            <Text style={styles.skipText}>Skip</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.hero}>
          <View style={styles.brandRow}>
            <View style={styles.brandDot} />
            <Text style={styles.brandLabel}>SURFCOACH · 23</Text>
          </View>
          <Text style={styles.heading}>GO{"\n"}UNLIMITED.</Text>
          <Text style={styles.sub}>
            One free analysis per day not enough? Unlock pro-grade depth and
            join the global coach network.
          </Text>
        </View>

        {loading ? (
          <ActivityIndicator
            color={colors.primary}
            style={{ marginTop: 40 }}
          />
        ) : (
          <>
            {free && <PlanCard plan={free} testID="plan-free" />}

            {plus && (
              <View style={{ marginTop: spacing.sm }}>
                <PlanCard plan={plus} testID="plan-plus" accent />
                <TouchableOpacity
                  style={[styles.plusBtn, submitting && { opacity: 0.5 }]}
                  onPress={() => upgrade("plus")}
                  disabled={submitting}
                  testID="upgrade-plus-btn"
                >
                  {submitting ? (
                    <ActivityIndicator color={colors.primary} />
                  ) : (
                    <>
                      <Ionicons
                        name="flash"
                        size={14}
                        color={colors.primary}
                      />
                      <Text style={styles.plusText}>
                        Get Plus – ${plus.amount}/mo
                      </Text>
                    </>
                  )}
                </TouchableOpacity>
              </View>
            )}

            {coach && (
              <View style={styles.coachWrap}>
                <PlanCard plan={coach} highlight testID="plan-coach" />
                {error ? (
                  <Text style={styles.error} testID="paywall-error">
                    {error}
                  </Text>
                ) : null}
                <TouchableOpacity
                  style={[styles.upgradeBtn, submitting && { opacity: 0.5 }]}
                  onPress={() => upgrade("coach")}
                  disabled={submitting}
                  testID="upgrade-coach-btn"
                >
                  {submitting ? (
                    <ActivityIndicator color="#000" />
                  ) : (
                    <>
                      <Ionicons name="rocket" size={16} color="#000" />
                      <Text style={styles.upgradeText}>
                        Upgrade to Coach – ${coach.amount}/mo
                      </Text>
                    </>
                  )}
                </TouchableOpacity>
                <Text style={styles.legal}>
                  Secure checkout via Stripe. Cancel renewal anytime.
                </Text>
              </View>
            )}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function PlanCard({
  plan,
  highlight,
  active,
  accent,
  testID,
}: {
  plan: Plan;
  highlight?: boolean;
  active?: boolean;
  accent?: boolean;
  testID?: string;
}) {
  return (
    <View
      style={[
        styles.card,
        highlight && styles.cardHighlight,
        accent && styles.cardAccent,
      ]}
      testID={testID}
    >
      <View style={styles.cardHead}>
        <Text style={[styles.planName, highlight && { color: colors.primary }]}>
          {plan.name.toUpperCase()}
        </Text>
        {active && (
          <View style={styles.activeBadge}>
            <Text style={styles.activeText}>CURRENT</Text>
          </View>
        )}
      </View>
      <Text style={styles.priceRow}>
        <Text style={[styles.price, highlight && { color: colors.primary }]}>
          {plan.amount === 0 ? "$0" : `$${plan.amount}`}
        </Text>
        <Text style={styles.priceUnit}>
          {plan.amount === 0 ? "  forever" : `  /${plan.interval || "month"}`}
        </Text>
      </Text>
      {plan.features.map((f, i) => (
        <View key={i} style={styles.featureRow}>
          <Ionicons
            name="checkmark"
            size={14}
            color={highlight ? colors.primary : colors.success}
            style={{ marginRight: 8 }}
          />
          <Text style={styles.featureText}>{f}</Text>
        </View>
      ))}
    </View>
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
  skipText: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  hero: { padding: spacing.lg },
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
  heading: {
    color: colors.textPrimary,
    fontSize: 44,
    fontWeight: "900",
    letterSpacing: -2,
    lineHeight: 46,
    textTransform: "uppercase",
    marginBottom: spacing.sm,
  },
  sub: { color: colors.textSecondary, fontSize: 14, lineHeight: 20 },
  card: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    padding: spacing.lg,
  },
  cardHighlight: { borderColor: colors.primary, borderWidth: 2 },
  cardAccent: { borderColor: colors.borderStrong },
  plusBtn: {
    marginHorizontal: spacing.lg,
    borderWidth: 1,
    borderColor: colors.primary,
    paddingVertical: 14,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    marginTop: spacing.sm,
  },
  plusText: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  cardHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 6,
  },
  planName: {
    color: colors.textPrimary,
    fontSize: 16,
    letterSpacing: 2,
    fontWeight: "800",
  },
  activeBadge: {
    backgroundColor: colors.success,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  activeText: { color: "#000", fontSize: 9, fontWeight: "900", letterSpacing: 1.5 },
  priceRow: { marginBottom: spacing.md },
  price: {
    color: colors.textPrimary,
    fontSize: 36,
    fontWeight: "900",
    letterSpacing: -2,
  },
  priceUnit: { color: colors.textMuted, fontSize: 13 },
  featureRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 5,
  },
  featureText: { color: colors.textPrimary, fontSize: 13, flex: 1 },
  coachWrap: { marginTop: spacing.sm },
  upgradeBtn: {
    marginHorizontal: spacing.lg,
    backgroundColor: colors.primary,
    paddingVertical: 16,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    marginTop: spacing.md,
  },
  upgradeText: {
    color: "#000",
    fontSize: 14,
    fontWeight: "900",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  legal: {
    color: colors.textMuted,
    fontSize: 11,
    textAlign: "center",
    marginTop: spacing.sm,
  },
  error: {
    color: colors.error,
    fontSize: 13,
    paddingHorizontal: spacing.lg,
    marginTop: spacing.sm,
  },
});
