import { ScrollView, Text, View, StyleSheet, TouchableOpacity } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { colors, spacing } from "../src/theme";

export default function RefundScreen() {
  const router = useRouter();
  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <View style={styles.topBar}>
        <TouchableOpacity onPress={() => router.back()} testID="refund-back-btn">
          <Ionicons name="chevron-back" size={26} color={colors.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.topTitle}>REFUND POLICY</Text>
        <View style={{ width: 26 }} />
      </View>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.lastUpdated}>Last updated: June 2026</Text>

        <Section title="Overview">
          SurfCoach23 is a digital subscription service sold through
          LemonSqueezy. The following refund terms apply to all paid
          subscriptions (LEARN, ADVANCED, PRO).
        </Section>

        <Section title="7-Day Money-Back Guarantee">
          We offer a 7-day money-back guarantee for first-time subscribers.
          If you are not satisfied with SurfCoach23 within 7 days of your
          first payment, email us and we will refund that payment in full —
          no questions asked.
          {"\n\n"}
          The guarantee applies to your first subscription payment only.
          Renewal payments are not covered by the 7-day guarantee but you
          can cancel future renewals anytime (see "Cancellations" below).
        </Section>

        <Section title="How to request a refund">
          Email <Text style={styles.link}>surfcoach23@gmail.com</Text> within
          7 days of your first charge with:
          {"\n"}• The email used to subscribe
          {"\n"}• The order/invoice number from LemonSqueezy
          {"\n"}• A brief reason (optional, helps us improve)
          {"\n\n"}
          We respond within 2 business days. Approved refunds are processed
          by LemonSqueezy and reach your card/bank within 5–10 business days.
        </Section>

        <Section title="Cancellations (stop future renewals)">
          You can cancel auto-renewal anytime from the in-app{" "}
          <Text style={styles.bold}>Manage Plan</Text> screen. Your paid
          access continues until the end of the current billing period —
          no further charges will be made.
        </Section>

        <Section title="When refunds are NOT available">
          Outside the 7-day window, subscription fees are non-refundable
          except where required by law. This includes:
          {"\n"}• Forgetting to cancel before the next renewal
          {"\n"}• Partial-month usage
          {"\n"}• Not using the service after subscribing
          {"\n\n"}
          We still encourage you to contact us — we review every request
          individually and may make exceptions in clear cases of error.
        </Section>

        <Section title="Disputes & chargebacks">
          Please contact us before initiating a chargeback with your bank.
          We will almost always resolve the issue faster directly. Chargebacks
          may result in account suspension while disputed.
        </Section>

        <Section title="Contact">
          Email: <Text style={styles.link}>surfcoach23@gmail.com</Text>
          {"\n"}Payment processor: LemonSqueezy (Merchant of Record)
        </Section>

        <View style={{ height: spacing.xxl }} />
      </ScrollView>
    </SafeAreaView>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      <Text style={styles.body}>{children}</Text>
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
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  topTitle: {
    color: colors.textPrimary,
    letterSpacing: 2,
    fontSize: 12,
    fontWeight: "800",
  },
  content: { padding: spacing.lg },
  lastUpdated: {
    color: colors.textMuted,
    fontSize: 11,
    marginBottom: spacing.lg,
    textTransform: "uppercase",
    letterSpacing: 1,
  },
  section: { marginBottom: spacing.lg },
  sectionTitle: {
    color: colors.primary,
    fontSize: 14,
    fontWeight: "800",
    letterSpacing: 1,
    marginBottom: 8,
    textTransform: "uppercase",
  },
  body: { color: colors.textPrimary, fontSize: 14, lineHeight: 22 },
  link: { color: colors.primary, fontWeight: "700" },
  bold: { color: colors.textPrimary, fontWeight: "800" },
});
