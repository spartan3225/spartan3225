import { ScrollView, Text, View, StyleSheet, TouchableOpacity } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { colors, spacing } from "../src/theme";

export default function PrivacyScreen() {
  const router = useRouter();
  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <View style={styles.topBar}>
        <TouchableOpacity onPress={() => router.back()} testID="privacy-back-btn">
          <Ionicons name="chevron-back" size={26} color={colors.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.topTitle}>PRIVACY POLICY</Text>
        <View style={{ width: 26 }} />
      </View>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.lastUpdated}>Last updated: June 2025</Text>

        <Section title="What we collect">
          • Account info: name, email, Google profile picture (via Google
          Sign-In).{"\n"}
          • Subscription info: tier, status, renewal date (from LemonSqueezy).{"\n"}
          • Content you upload: surfing video clips and their AI analyses.{"\n"}
          • Usage data: app version, login times, error logs — basic, anonymised.
        </Section>

        <Section title="What we do NOT collect">
          • We do not collect your location.{"\n"}
          • We do not access your camera roll, contacts, or photos without
          your explicit action (file picker).{"\n"}
          • We do not collect payment card details — those are handled by
          LemonSqueezy and never reach our servers.
        </Section>

        <Section title="How we use it">
          • To run AI video analysis (your clips are sent securely to Google
          Gemini and Anthropic Claude solely to produce your analysis result;
          providers do not use them for model training under enterprise terms).{"\n"}
          • To manage your subscription and quota.{"\n"}
          • To deliver in-app notifications (e.g. analysis ready, coach
          message).{"\n"}
          • To improve the app (anonymised aggregate metrics).
        </Section>

        <Section title="Sharing">
          We share data only with the third-party processors necessary to run
          the service:
          {"\n"}• <Text style={styles.bold}>LemonSqueezy</Text> — payment processing
          {"\n"}• <Text style={styles.bold}>Google Cloud (Gemini)</Text> — video AI
          {"\n"}• <Text style={styles.bold}>Anthropic (Claude)</Text> — text AI
          {"\n"}• <Text style={styles.bold}>MongoDB Atlas</Text> — secure database hosting
          {"\n\n"}
          We never sell your data.
        </Section>

        <Section title="Coach sharing">
          When you tap "Share with coach", that specific video and analysis
          become visible to the coach you choose, including any comments they
          add. You can revoke sharing anytime from the analysis screen.
        </Section>

        <Section title="Your rights">
          You can request a copy of your data, correction of inaccuracies, or
          deletion of your account & data at any time by emailing
          {" "}<Text style={styles.link}>surfcoach23@gmail.com</Text>.
          We respond within 30 days.
        </Section>

        <Section title="Children">
          The service is not directed to children under 13 (or 16 in the EU).
          We do not knowingly collect data from children.
        </Section>

        <Section title="Security">
          Connections use HTTPS/TLS. Session tokens are stored securely on
          device. Database access is restricted to authenticated services.
        </Section>

        <Section title="Retention">
          Videos and analyses are stored as long as your account exists. If
          you delete your account, we erase all your data within 30 days.
        </Section>

        <Section title="Updates">
          We may update this policy and will notify you in-app of material
          changes. The "Last updated" date above is your reference.
        </Section>

        <Section title="Contact">
          Email: <Text style={styles.link}>surfcoach23@gmail.com</Text>
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
