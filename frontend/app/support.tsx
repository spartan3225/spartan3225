import { ScrollView, Text, View, StyleSheet, TouchableOpacity, Platform, Linking } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { colors, spacing } from "../src/theme";

const SUPPORT_EMAIL = "surfcoach23@gmail.com";

export default function SupportScreen() {
  const router = useRouter();

  const emailUs = (subject: string) => {
    const url = `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(subject)}`;
    Linking.openURL(url).catch(() => {});
  };

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <View style={styles.topBar}>
        <TouchableOpacity onPress={() => router.back()} testID="support-back-btn">
          <Ionicons name="chevron-back" size={26} color={colors.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.topTitle}>SUPPORT</Text>
        <View style={{ width: 26 }} />
      </View>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.heroTitle}>How can we help?</Text>
        <Text style={styles.heroSub}>
          SurfCoach23 support — we read every email and reply within 24–48
          hours.
        </Text>

        <TouchableOpacity
          style={styles.emailCard}
          onPress={() => emailUs("SurfCoach23 Support Request")}
          testID="support-email-btn"
        >
          <Ionicons name="mail" size={22} color={colors.primary} />
          <View style={{ flex: 1 }}>
            <Text style={styles.emailLabel}>Email us anytime</Text>
            <Text style={styles.emailValue}>{SUPPORT_EMAIL}</Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={colors.textMuted} />
        </TouchableOpacity>

        <Section title="Common questions">
          <Item
            icon="videocam-outline"
            q="My video won't upload or analysis failed"
            a="Use a clear 5–60 second clip (MP4 or MOV, up to 200 MB). Check your internet connection and try again — failed analyses never use up your quota. Still stuck? Email us the approximate time it happened."
          />
          <Item
            icon="key-outline"
            q="I can't log in"
            a="You can sign in with Google, Apple, or your email & password. If you forgot your password, email us from your account email and we'll help you reset it."
          />
          <Item
            icon="card-outline"
            q="Subscriptions, billing & refunds"
            a="Subscriptions are managed from your SurfCoach23 account on the web. You can cancel renewal anytime from your Profile — access stays until the end of the paid period. First subscription comes with a 7-day money-back guarantee (see our Refund Policy)."
          />
          <Item
            icon="trash-outline"
            q="Delete my account & data"
            a="Open Profile → Delete account (two taps to confirm). This permanently removes your account, videos and analyses. You can also request deletion by email."
          />
        </Section>

        <Section title="When you email us, include">
          <Text style={styles.body}>
            • The email address of your SurfCoach23 account{"\n"}
            • What you were doing when the problem happened{"\n"}
            • A screenshot if possible{"\n"}
            {"\n"}
            We reply within 24–48 hours, usually much faster.
          </Text>
        </Section>

        <Section title="Legal">
          <View style={styles.linkRow}>
            <TouchableOpacity onPress={() => router.push("/terms" as any)} testID="support-terms-link">
              <Text style={styles.link}>Terms of Service</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => router.push("/privacy" as any)} testID="support-privacy-link">
              <Text style={styles.link}>Privacy Policy</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => router.push("/refund" as any)} testID="support-refund-link">
              <Text style={styles.link}>Refund Policy</Text>
            </TouchableOpacity>
          </View>
        </Section>

        <Text style={styles.footer}>
          SurfCoach23 — AI surf coaching.{" "}
          {Platform.OS === "web" ? "Available on iOS, Android and the web." : ""}
        </Text>

        <View style={{ height: spacing.xxl }} />
      </ScrollView>
    </SafeAreaView>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {children}
    </View>
  );
}

function Item({ icon, q, a }: { icon: any; q: string; a: string }) {
  return (
    <View style={styles.item}>
      <View style={styles.itemHead}>
        <Ionicons name={icon} size={16} color={colors.primary} />
        <Text style={styles.itemQ}>{q}</Text>
      </View>
      <Text style={styles.itemA}>{a}</Text>
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
  content: { padding: spacing.lg, maxWidth: 760, width: "100%", alignSelf: "center" },
  heroTitle: {
    color: colors.textPrimary,
    fontSize: 26,
    fontWeight: "900",
    marginBottom: 6,
  },
  heroSub: { color: colors.textMuted, fontSize: 14, marginBottom: spacing.lg },
  emailCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    borderWidth: 1,
    borderColor: colors.primary,
    borderRadius: 8,
    padding: spacing.md,
    marginBottom: spacing.xl,
    minHeight: 44,
  },
  emailLabel: { color: colors.textMuted, fontSize: 11, textTransform: "uppercase", letterSpacing: 1 },
  emailValue: { color: colors.textPrimary, fontSize: 15, fontWeight: "800" },
  section: { marginBottom: spacing.xl },
  sectionTitle: {
    color: colors.primary,
    fontSize: 14,
    fontWeight: "800",
    letterSpacing: 1,
    marginBottom: spacing.md,
    textTransform: "uppercase",
  },
  item: { marginBottom: spacing.md },
  itemHead: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 4 },
  itemQ: { color: colors.textPrimary, fontSize: 14, fontWeight: "800", flex: 1 },
  itemA: { color: colors.textMuted, fontSize: 13, lineHeight: 20, paddingLeft: 24 },
  body: { color: colors.textPrimary, fontSize: 14, lineHeight: 22 },
  linkRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.lg },
  link: { color: colors.primary, fontWeight: "700", fontSize: 13, paddingVertical: 8 },
  footer: { color: colors.textMuted, fontSize: 12, textAlign: "center", marginTop: spacing.lg },
});
