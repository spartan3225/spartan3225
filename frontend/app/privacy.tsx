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
        <Text style={styles.lastUpdated}>Last updated: June 2026</Text>

        <Section title="Who we are">
          SurfCoach23 (&quot;we&quot;, &quot;us&quot;) provides AI-powered surf video analysis via
          our website and mobile apps. This policy explains what data we
          collect, why, and your rights. It applies to the SurfCoach23 web app
          and the iOS / Android apps.
        </Section>

        <Section title="What we collect">
          • Account info: name and email address — provided when you sign in
          with Google, Sign in with Apple, or create an email & password
          account. With Google we also receive your profile picture. With
          Apple you may hide your email (we then receive Apple&apos;s private
          relay address).{"\n"}
          • Login credentials: if you use email sign-up, we store your
          password only as a secure one-way hash (argon2) — we can never read
          it.{"\n"}
          • Subscription info: plan tier, status, renewal date (from our
          payment provider LemonSqueezy).{"\n"}
          • Content you upload: surfing video clips and the AI analyses
          generated from them.{"\n"}
          • Usage data: app version, login times, error logs — basic and
          anonymised.
        </Section>

        <Section title="What we do NOT collect">
          • We do not track you across other companies&apos; apps or websites, and
          we do not use advertising identifiers (no IDFA).{"\n"}
          • We do not collect your location.{"\n"}
          • We do not access your camera, microphone, or photo library without
          your explicit action and permission (recording or picking a clip).{"\n"}
          • We do not collect payment card details — those are handled by
          LemonSqueezy and never reach our servers.{"\n"}
          • We do not sell your personal data, and we do not show third-party
          ads.
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
          {"\n"}• <Text style={styles.bold}>LemonSqueezy</Text> — payment &
          subscription processing (merchant of record)
          {"\n"}• <Text style={styles.bold}>Google (Gemini AI)</Text> — video analysis
          {"\n"}• <Text style={styles.bold}>Anthropic (Claude AI)</Text> — coaching text
          {"\n"}• <Text style={styles.bold}>Google Sign-In / Apple Sign-In</Text> —
          authentication, only if you choose them
          {"\n"}• <Text style={styles.bold}>MongoDB Atlas</Text> — secure database hosting
          {"\n\n"}
          Each processor receives only the minimum data required. We never
          sell your data. Your data may be processed on servers outside your
          country; we use providers with industry-standard safeguards
          (encryption in transit and at rest).
        </Section>

        <Section title="Coach sharing">
          When you tap &quot;Share with coach&quot;, that specific video and analysis
          become visible to the coach you choose, including any comments they
          add. You can revoke sharing anytime from the analysis screen.
        </Section>

        <Section title="Your rights & account deletion">
          • <Text style={styles.bold}>Delete your account in the app:</Text>{" "}
          Profile → Delete account. This permanently erases your account,
          videos, analyses, comments and sessions from our systems.{"\n"}
          • You can also request a copy of your data, correction of
          inaccuracies, or deletion by emailing{" "}
          <Text style={styles.link}>surfcoach23@gmail.com</Text> — we respond
          within 30 days.{"\n"}
          • Depending on where you live (e.g. EU/EEA GDPR, California CCPA),
          you may have additional rights such as data portability and the
          right to object; contact us to exercise them.
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
          Videos and analyses are stored for as long as your account exists.
          When you delete your account (in-app or by email), your personal
          data, videos and analyses are erased from our production systems
          immediately, and from encrypted backups within 30 days. Payment
          records may be retained by LemonSqueezy as required by tax law.
        </Section>

        <Section title="Updates">
          We may update this policy and will notify you in-app of material
          changes. The &quot;Last updated&quot; date above is your reference.
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
