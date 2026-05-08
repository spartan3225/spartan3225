import { useEffect, useMemo, useState } from "react";
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
import { createCheckout, getPlans, fetchMe, Plan, User } from "../src/api";
import { colors, spacing } from "../src/theme";

// Tier ordering for display.
const TIER_ORDER = [
  "free",
  "beginner",
  "plus",
  "intermediate",
  "advanced",
  "pro",
  "coach",
];

const HIGHLIGHTED_TIERS = new Set(["plus", "coach"]);

type PaidPlanId =
  | "beginner"
  | "plus"
  | "intermediate"
  | "advanced"
  | "pro"
  | "coach";

export default function PaywallScreen() {
  const router = useRouter();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [me, setMe] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [plansRes, user] = await Promise.all([getPlans(), fetchMe()]);
        setPlans(plansRes.plans);
        setMe(user);
      } catch (e: any) {
        setError(e?.message || "Failed to load plans");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const sortedPlans = useMemo(() => {
    const byId = new Map(plans.map((p) => [p.plan_id, p]));
    return TIER_ORDER.map((id) => byId.get(id)).filter(Boolean) as Plan[];
  }, [plans]);

  const upgrade = async (planId: PaidPlanId) => {
    setError(null);
    setSubmitting(planId);
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
    } finally {
      setSubmitting(null);
    }
  };

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
          <Text style={styles.heading}>RIDE{"\n"}MORE WAVES.</Text>
          <Text style={styles.sub}>
            Free plan gives you one analysis on us. Pick your level — from
            Beginner to Coach Elite — to keep dialing in your technique.
          </Text>
        </View>

        {loading ? (
          <ActivityIndicator
            color={colors.primary}
            style={{ marginTop: 40 }}
          />
        ) : (
          <>
            {error ? (
              <Text style={styles.error} testID="paywall-error">
                {error}
              </Text>
            ) : null}

            {sortedPlans.map((plan) => {
              const isFree = plan.plan_id === "free";
              const isCurrent = me?.tier === plan.plan_id;
              const isHighlight = HIGHLIGHTED_TIERS.has(plan.plan_id);
              const isCoach = plan.plan_id === "coach";
              return (
                <View
                  key={plan.plan_id}
                  style={{ marginBottom: spacing.sm }}
                >
                  <PlanCard
                    plan={plan}
                    highlight={isCoach}
                    accent={isHighlight && !isCoach}
                    active={isCurrent}
                    testID={`plan-${plan.plan_id}`}
                  />
                  {!isFree && (
                    <TouchableOpacity
                      style={[
                        isCoach ? styles.coachCta : styles.planCta,
                        submitting === plan.plan_id && { opacity: 0.5 },
                      ]}
                      onPress={() => upgrade(plan.plan_id as PaidPlanId)}
                      disabled={submitting !== null}
                      testID={`upgrade-${plan.plan_id}-btn`}
                    >
                      {submitting === plan.plan_id ? (
                        <ActivityIndicator
                          color={isCoach ? "#000" : colors.primary}
                        />
                      ) : (
                        <>
                          <Ionicons
                            name={
                              isCurrent
                                ? "refresh"
                                : isCoach
                                ? "rocket"
                                : "flash"
                            }
                            size={isCoach ? 16 : 14}
                            color={isCoach ? "#000" : colors.primary}
                          />
                          <Text
                            style={
                              isCoach ? styles.coachCtaText : styles.planCtaText
                            }
                          >
                            {isCurrent
                              ? `Renew ${plan.name} – $${plan.amount}/mo`
                              : isCoach
                              ? `Upgrade to ${plan.name} – $${plan.amount}/mo`
                              : `Choose ${plan.name} – $${plan.amount}/mo`}
                          </Text>
                        </>
                      )}
                    </TouchableOpacity>
                  )}
                  {isCurrent && !isFree ? (
                    <View style={styles.currentRow}>
                      <Ionicons
                        name="checkmark-circle"
                        size={14}
                        color={colors.success}
                      />
                      <Text style={styles.currentText}>
                        You're on this plan
                      </Text>
                    </View>
                  ) : null}
                </View>
              );
            })}

            <Text style={styles.legal}>
              Secure checkout via Stripe. Cancel renewal anytime from your
              profile.
            </Text>
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
        <Text
          style={[styles.planName, highlight && { color: colors.primary }]}
        >
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
    marginBottom: 0,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    padding: spacing.lg,
  },
  cardHighlight: { borderColor: colors.primary, borderWidth: 2 },
  cardAccent: { borderColor: colors.borderStrong },
  planCta: {
    marginHorizontal: spacing.lg,
    borderWidth: 1,
    borderColor: colors.primary,
    paddingVertical: 14,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    marginTop: spacing.xs,
  },
  planCtaText: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  coachCta: {
    marginHorizontal: spacing.lg,
    backgroundColor: colors.primary,
    paddingVertical: 16,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    marginTop: spacing.xs,
  },
  coachCtaText: {
    color: "#000",
    fontSize: 14,
    fontWeight: "900",
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
  activeText: {
    color: "#000",
    fontSize: 9,
    fontWeight: "900",
    letterSpacing: 1.5,
  },
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
  currentRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    marginTop: spacing.xs,
  },
  currentText: {
    color: colors.success,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  legal: {
    color: colors.textMuted,
    fontSize: 11,
    textAlign: "center",
    marginTop: spacing.md,
    paddingHorizontal: spacing.lg,
  },
  error: {
    color: colors.error,
    fontSize: 13,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
  },
});
