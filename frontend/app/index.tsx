import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Image,
  Platform,
  ScrollView,
  Dimensions,
  TextInput,
} from "react-native";
import { useRouter } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import * as Linking from "expo-linking";
import * as AppleAuthentication from "expo-apple-authentication";
import { Ionicons } from "@expo/vector-icons";
import { colors, spacing } from "../src/theme";
import {
  fetchMe,
  exchangeSessionId,
  emailLogin,
  emailRegister,
  appleLogin,
} from "../src/api";

// Hero: dramatic full-body action surfing photograph
const HERO_IMAGE =
  "https://images.unsplash.com/photo-1530870110042-98b2cb110834?w=1400&q=85&auto=format&fit=crop";

const SCREEN_H = Dimensions.get("window").height;

export default function LoginScreen() {
  const router = useRouter();
  const [checking, setChecking] = useState(true);
  const [loggingIn, setLoggingIn] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showEmailForm, setShowEmailForm] = useState(false);
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [emailBusy, setEmailBusy] = useState(false);
  const [appleAvailable, setAppleAvailable] = useState(false);

  useEffect(() => {
    if (Platform.OS === "ios") {
      AppleAuthentication.isAvailableAsync()
        .then(setAppleAvailable)
        .catch(() => setAppleAvailable(false));
    }
  }, []);

  const onEmailSubmit = async () => {
    if (!email.trim() || !password) {
      setError("Please enter your email and password.");
      return;
    }
    setError(null);
    setEmailBusy(true);
    try {
      if (isRegister) {
        await emailRegister(email.trim(), password);
      } else {
        await emailLogin(email.trim(), password);
      }
      router.replace("/(tabs)");
    } catch (e: any) {
      setError(e?.message || "Login failed. Please try again.");
    } finally {
      setEmailBusy(false);
    }
  };

  const onAppleSignIn = async () => {
    setError(null);
    try {
      const credential = await AppleAuthentication.signInAsync({
        requestedScopes: [
          AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
          AppleAuthentication.AppleAuthenticationScope.EMAIL,
        ],
      });
      if (!credential.identityToken) throw new Error("No identity token");
      const fullName = [
        credential.fullName?.givenName,
        credential.fullName?.familyName,
      ]
        .filter(Boolean)
        .join(" ");
      await appleLogin(credential.identityToken, fullName || null, credential.email);
      router.replace("/(tabs)");
    } catch (e: any) {
      if (e?.code === "ERR_REQUEST_CANCELED") return; // user cancelled
      setError(e?.message || "Apple sign-in failed. Please try again.");
    }
  };

  useEffect(() => {
    (async () => {
      // If returning from OAuth callback (web), let the callback page handle it
      if (
        Platform.OS === "web" &&
        typeof window !== "undefined" &&
        window.location.hash &&
        window.location.hash.includes("session_id=")
      ) {
        router.replace("/auth-callback");
        return;
      }
      const me = await fetchMe();
      if (me) {
        router.replace("/(tabs)");
      } else {
        setChecking(false);
      }
    })();
  }, [router]);

  const onSignIn = async () => {
    setError(null);
    setLoggingIn(true);
    try {
      // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
      if (Platform.OS === "web") {
        const redirectUrl = window.location.origin + "/auth-callback";
        window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(
          redirectUrl
        )}`;
        return;
      }
      // Native flow — use Expo Linking to build a dynamic deep-link URL
      // that works across preview, production, and any custom domain.
      const redirectUrl = Linking.createURL("/auth-callback");
      const authUrl = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(
        redirectUrl
      )}`;
      const result = await WebBrowser.openAuthSessionAsync(
        authUrl,
        redirectUrl
      );
      if (result.type === "success" && result.url) {
        const m = result.url.match(/session_id=([^&#]+)/);
        if (m && m[1]) {
          await exchangeSessionId(decodeURIComponent(m[1]));
          router.replace("/(tabs)");
          return;
        }
      }
      setError("Sign-in cancelled");
    } catch (e: any) {
      setError(e?.message || "Sign-in failed");
    } finally {
      setLoggingIn(false);
    }
  };

  if (checking) {
    return (
      <View style={[styles.container, styles.center]}>
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={{ paddingBottom: 0 }}
      testID="login-screen"
      showsVerticalScrollIndicator={false}
    >
      {/* ===== HERO ===== */}
      <View style={styles.hero}>
        <Image source={{ uri: HERO_IMAGE }} style={styles.heroImg} />
        <View style={styles.heroOverlay} />

        <View style={styles.heroContent}>
          <View style={styles.brandRow}>
            <View style={styles.brandDot} />
            <Text style={styles.brandLabel}>SURFCOACH · 23</Text>
          </View>

          <Text style={styles.title} testID="login-title">
            MASTER{"\n"}EVERY{"\n"}WAVE.
          </Text>
          <Text style={styles.subtitle}>
            Upload a clip. Get instant pro-tour technique analysis — score,
            mistakes, corrections and drills, frame by frame.
          </Text>

          <View style={styles.statsRow}>
            <View style={styles.statBox}>
              <Text style={styles.statValue}>AI</Text>
              <Text style={styles.statLabel}>Coach</Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.statBox}>
              <Text style={styles.statValue}>4K</Text>
              <Text style={styles.statLabel}>Video</Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.statBox}>
              <Text style={styles.statValue}>30s</Text>
              <Text style={styles.statLabel}>Insights</Text>
            </View>
          </View>

          {error ? (
            <Text style={styles.error} testID="login-error">
              {error}
            </Text>
          ) : null}

          <TouchableOpacity
            style={styles.signInBtn}
            onPress={onSignIn}
            activeOpacity={0.85}
            disabled={loggingIn}
            testID="login-google-btn"
          >
            {loggingIn ? (
              <ActivityIndicator color="#000" />
            ) : (
              <>
                <Ionicons
                  name="logo-google"
                  size={18}
                  color="#000"
                  style={{ marginRight: 10 }}
                />
                <Text style={styles.signInText}>Continue with Google</Text>
              </>
            )}
          </TouchableOpacity>

          {appleAvailable && (
            <AppleAuthentication.AppleAuthenticationButton
              buttonType={
                AppleAuthentication.AppleAuthenticationButtonType.SIGN_IN
              }
              buttonStyle={
                AppleAuthentication.AppleAuthenticationButtonStyle.WHITE
              }
              cornerRadius={10}
              style={styles.appleBtn}
              onPress={onAppleSignIn}
            />
          )}

          {!showEmailForm ? (
            <TouchableOpacity
              style={styles.emailToggleBtn}
              onPress={() => setShowEmailForm(true)}
              testID="show-email-login-btn"
            >
              <Ionicons
                name="mail-outline"
                size={16}
                color={colors.textMuted}
                style={{ marginRight: 8 }}
              />
              <Text style={styles.emailToggleText}>
                Continue with Email
              </Text>
            </TouchableOpacity>
          ) : (
            <View style={styles.emailForm}>
              <TextInput
                style={styles.input}
                placeholder="Email"
                placeholderTextColor={colors.textMuted}
                keyboardType="email-address"
                autoCapitalize="none"
                autoCorrect={false}
                value={email}
                onChangeText={setEmail}
                testID="email-input"
              />
              <TextInput
                style={styles.input}
                placeholder="Password (min 8 characters)"
                placeholderTextColor={colors.textMuted}
                secureTextEntry
                value={password}
                onChangeText={setPassword}
                testID="password-input"
              />
              <TouchableOpacity
                style={styles.emailSubmitBtn}
                onPress={onEmailSubmit}
                disabled={emailBusy}
                testID="email-submit-btn"
              >
                {emailBusy ? (
                  <ActivityIndicator color="#000" />
                ) : (
                  <Text style={styles.signInText}>
                    {isRegister ? "Create Account" : "Log In"}
                  </Text>
                )}
              </TouchableOpacity>
              <TouchableOpacity
                onPress={() => setIsRegister(!isRegister)}
                testID="toggle-register-btn"
              >
                <Text style={styles.emailToggleText}>
                  {isRegister
                    ? "Already have an account? Log in"
                    : "New here? Create an account"}
                </Text>
              </TouchableOpacity>
            </View>
          )}

          <Text style={styles.legal}>
            Your video clips stay private to your account.
          </Text>
        </View>
      </View>

      {/* ===== HOW IT WORKS ===== */}
      <View style={styles.section}>
        <Text style={styles.sectionKicker}>HOW IT WORKS</Text>
        <Text style={styles.sectionTitle}>Three steps to better surfing.</Text>

        <View style={styles.stepCard}>
          <View style={styles.stepNumBox}>
            <Text style={styles.stepNum}>01</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.stepTitle}>Upload your clip</Text>
            <Text style={styles.stepDesc}>
              From your phone gallery — any wave, any angle. We auto-convert
              iPhone .MOV to .MP4 in the cloud.
            </Text>
          </View>
        </View>

        <View style={styles.stepCard}>
          <View style={styles.stepNumBox}>
            <Text style={styles.stepNum}>02</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.stepTitle}>AI breaks it down</Text>
            <Text style={styles.stepDesc}>
              Google Gemini analyses motion frame-by-frame. Claude Sonnet
              rewrites the result in clean pro-coach language.
            </Text>
          </View>
        </View>

        <View style={styles.stepCard}>
          <View style={styles.stepNumBox}>
            <Text style={styles.stepNum}>03</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.stepTitle}>Get score, fixes & drills</Text>
            <Text style={styles.stepDesc}>
              Technical score, top mistakes, frame-specific corrections, and
              dry-land drills you can do today.
            </Text>
          </View>
        </View>
      </View>

      {/* ===== PRICING ===== */}
      <View style={[styles.section, styles.sectionAlt]}>
        <Text style={styles.sectionKicker}>PRICING</Text>
        <Text style={styles.sectionTitle}>Pick the plan that fits.</Text>
        <Text style={styles.sectionSubtitle}>
          Prices in US Dollars (USD). Cancel anytime. Billed monthly.
        </Text>

        <View style={styles.priceCard}>
          <View style={styles.priceHeader}>
            <Text style={styles.priceTier}>FREE</Text>
            <View>
              <Text style={styles.priceAmount}>$0</Text>
            </View>
          </View>
          <Text style={styles.priceBullet}>• 1 lifetime AI analysis</Text>
          <Text style={styles.priceBullet}>• Standard quality</Text>
          <Text style={styles.priceBullet}>• Try before you buy</Text>
        </View>

        <View style={styles.priceCard}>
          <View style={styles.priceHeader}>
            <Text style={styles.priceTier}>LEARN</Text>
            <View>
              <Text style={styles.priceAmount}>$15</Text>
              <Text style={styles.pricePeriod}>/ month</Text>
            </View>
          </View>
          <Text style={styles.priceBullet}>• 3 AI analyses / day</Text>
          <Text style={styles.priceBullet}>• Full coach-language feedback</Text>
          <Text style={styles.priceBullet}>• Drill recommendations</Text>
        </View>

        <View style={[styles.priceCard, styles.priceCardFeatured]}>
          <View style={styles.featuredBadge}>
            <Text style={styles.featuredBadgeText}>POPULAR</Text>
          </View>
          <View style={styles.priceHeader}>
            <Text style={styles.priceTier}>ADVANCED</Text>
            <View>
              <Text style={styles.priceAmount}>$25</Text>
              <Text style={styles.pricePeriod}>/ month</Text>
            </View>
          </View>
          <Text style={styles.priceBullet}>• 7 AI analyses / day</Text>
          <Text style={styles.priceBullet}>• Frame-by-frame breakdown</Text>
          <Text style={styles.priceBullet}>• Share with a coach</Text>
          <Text style={styles.priceBullet}>• Priority processing</Text>
        </View>

        <View style={styles.priceCard}>
          <View style={styles.priceHeader}>
            <Text style={styles.priceTier}>PRO</Text>
            <View>
              <Text style={styles.priceAmount}>$35</Text>
              <Text style={styles.pricePeriod}>/ month</Text>
            </View>
          </View>
          <Text style={styles.priceBullet}>• 15 AI analyses / day</Text>
          <Text style={styles.priceBullet}>• Unlimited coach shares</Text>
          <Text style={styles.priceBullet}>• Highest quality model</Text>
          <Text style={styles.priceBullet}>• Early access to new features</Text>
        </View>

        <Text style={styles.refundLine}>
          7-day money-back guarantee on your first subscription —{" "}
          <Text
            style={styles.refundLink}
            onPress={() => router.push("/refund" as any)}
          >
            see refund policy
          </Text>
          .
        </Text>
      </View>

      {/* ===== FAQ ===== */}
      <View style={styles.section}>
        <Text style={styles.sectionKicker}>FAQ</Text>
        <Text style={styles.sectionTitle}>Quick answers.</Text>

        <FaqItem
          q="Who is SurfCoach23 for?"
          a="Surfers of all levels who want honest, technical feedback on their riding without waiting for a human coach."
        />
        <FaqItem
          q="What videos work best?"
          a="A clear 5–60 second clip filmed from the beach or a chase camera. Side-on angles work best. Up to 200 MB per upload."
        />
        <FaqItem
          q="Will my videos stay private?"
          a="Yes. Your clips are visible only to you, unless you explicitly tap 'Share with coach'. We never sell your data. See our Privacy Policy."
        />
        <FaqItem
          q="Can I cancel anytime?"
          a="Yes. Open Manage Plan in the app and tap Cancel renewal. Your access stays active until the end of the period you already paid for."
        />
        <FaqItem
          q="Do you offer refunds?"
          a="Yes — a 7-day money-back guarantee on your first subscription. After that, see our Refund Policy for details."
        />
      </View>

      {/* ===== CONTACT ===== */}
      <View style={[styles.section, styles.sectionAlt]}>
        <Text style={styles.sectionKicker}>CONTACT</Text>
        <Text style={styles.sectionTitle}>Talk to a human.</Text>
        <Text style={styles.sectionSubtitle}>
          Support, refunds, business questions — we read every email and reply
          within 2 business days.
        </Text>

        <View style={styles.contactCard}>
          <Ionicons name="mail-outline" size={20} color={colors.primary} />
          <View style={{ marginLeft: 12, flex: 1 }}>
            <Text style={styles.contactLabel}>EMAIL</Text>
            <Text style={styles.contactValue}>surfcoach23@gmail.com</Text>
          </View>
        </View>

        <View style={styles.contactCard}>
          <Ionicons name="location-outline" size={20} color={colors.primary} />
          <View style={{ marginLeft: 12, flex: 1 }}>
            <Text style={styles.contactLabel}>BASED IN</Text>
            <Text style={styles.contactValue}>Saudi Arabia</Text>
          </View>
        </View>

        <View style={styles.contactCard}>
          <Ionicons name="card-outline" size={20} color={colors.primary} />
          <View style={{ marginLeft: 12, flex: 1 }}>
            <Text style={styles.contactLabel}>PAYMENT PROCESSOR</Text>
            <Text style={styles.contactValue}>
              LemonSqueezy (Merchant of Record)
            </Text>
          </View>
        </View>
      </View>

      {/* ===== FINAL CTA ===== */}
      <View style={styles.ctaSection}>
        <Text style={styles.ctaTitle}>Ready to level up?</Text>
        <Text style={styles.ctaSubtitle}>
          Start with one free AI analysis. No card needed.
        </Text>
        <TouchableOpacity
          style={styles.ctaBtn}
          onPress={onSignIn}
          activeOpacity={0.85}
          disabled={loggingIn}
          testID="cta-google-btn"
        >
          {loggingIn ? (
            <ActivityIndicator color="#000" />
          ) : (
            <>
              <Ionicons
                name="logo-google"
                size={18}
                color="#000"
                style={{ marginRight: 10 }}
              />
              <Text style={styles.signInText}>Continue with Google</Text>
            </>
          )}
        </TouchableOpacity>
      </View>

      {/* ===== FOOTER ===== */}
      <View style={styles.footer}>
        <Text style={styles.footerBrand}>SURFCOACH · 23</Text>
        <View style={styles.footerLinksRow}>
          <TouchableOpacity
            onPress={() => router.push("/terms" as any)}
            testID="footer-terms-link"
          >
            <Text style={styles.footerLink}>Terms</Text>
          </TouchableOpacity>
          <Text style={styles.footerDot}>·</Text>
          <TouchableOpacity
            onPress={() => router.push("/privacy" as any)}
            testID="footer-privacy-link"
          >
            <Text style={styles.footerLink}>Privacy</Text>
          </TouchableOpacity>
          <Text style={styles.footerDot}>·</Text>
          <TouchableOpacity
            onPress={() => router.push("/refund" as any)}
            testID="footer-refund-link"
          >
            <Text style={styles.footerLink}>Refunds</Text>
          </TouchableOpacity>
        </View>
        <Text style={styles.footerCopy}>
          © 2026 SurfCoach23 · All rights reserved
        </Text>
      </View>
    </ScrollView>
  );
}

function FaqItem({ q, a }: { q: string; a: string }) {
  return (
    <View style={styles.faqItem}>
      <Text style={styles.faqQ}>{q}</Text>
      <Text style={styles.faqA}>{a}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { alignItems: "center", justifyContent: "center" },

  // ===== HERO =====
  hero: {
    minHeight: SCREEN_H > 700 ? SCREEN_H : 700,
    backgroundColor: colors.background,
  },
  heroImg: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: "70%",
    resizeMode: "cover",
    opacity: 0.85,
  },
  heroOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(10,10,10,0.55)",
  },
  heroContent: {
    flex: 1,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.xxl + spacing.lg,
    paddingBottom: spacing.xl,
    justifyContent: "flex-end",
  },
  brandRow: {
    position: "absolute",
    top: spacing.xxl + spacing.md,
    left: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  brandDot: { width: 10, height: 10, backgroundColor: colors.primary },
  brandLabel: {
    color: colors.primary,
    letterSpacing: 4,
    fontSize: 12,
    fontWeight: "800",
  },
  title: {
    color: colors.textPrimary,
    fontSize: 56,
    lineHeight: 56,
    fontWeight: "900",
    letterSpacing: -2,
    textTransform: "uppercase",
    marginBottom: spacing.md,
  },
  subtitle: {
    color: colors.textSecondary,
    fontSize: 15,
    lineHeight: 22,
    marginBottom: spacing.lg,
    maxWidth: 360,
  },
  statsRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.md,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.lg,
  },
  statBox: { flex: 1, alignItems: "flex-start" },
  statDivider: { width: 1, height: 28, backgroundColor: colors.border },
  statValue: {
    color: colors.textPrimary,
    fontSize: 22,
    fontWeight: "900",
    letterSpacing: -1,
  },
  statLabel: {
    color: colors.textMuted,
    fontSize: 10,
    letterSpacing: 2,
    textTransform: "uppercase",
    marginTop: 2,
  },
  signInBtn: {
    backgroundColor: colors.primary,
    paddingVertical: 16,
    borderRadius: 4,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
  },
  signInText: {
    color: "#000",
    fontSize: 15,
    fontWeight: "800",
    letterSpacing: 0.5,
  },
  appleBtn: {
    height: 50,
    marginTop: spacing.sm,
  },
  emailToggleBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 14,
    marginTop: spacing.sm,
    minHeight: 44,
  },
  emailToggleText: {
    color: colors.textMuted,
    fontSize: 13,
    textAlign: "center",
    paddingVertical: 8,
  },
  emailForm: {
    marginTop: spacing.sm,
  },
  input: {
    backgroundColor: "rgba(255,255,255,0.06)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.12)",
    borderRadius: 4,
    color: "#fff",
    paddingHorizontal: 14,
    paddingVertical: 14,
    fontSize: 15,
    marginBottom: spacing.sm,
  },
  emailSubmitBtn: {
    backgroundColor: colors.primary,
    paddingVertical: 15,
    borderRadius: 4,
    alignItems: "center",
    justifyContent: "center",
  },
  legal: {
    color: colors.textMuted,
    fontSize: 11,
    textAlign: "center",
    marginTop: spacing.md,
  },
  error: { color: colors.error, marginBottom: spacing.sm, fontSize: 13 },

  // ===== SECTIONS =====
  section: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xl + spacing.md,
  },
  sectionAlt: { backgroundColor: colors.surface },
  sectionKicker: {
    color: colors.primary,
    fontSize: 11,
    letterSpacing: 3,
    fontWeight: "800",
    marginBottom: 8,
  },
  sectionTitle: {
    color: colors.textPrimary,
    fontSize: 30,
    lineHeight: 34,
    fontWeight: "900",
    letterSpacing: -1,
    marginBottom: 6,
  },
  sectionSubtitle: {
    color: colors.textSecondary,
    fontSize: 14,
    lineHeight: 20,
    marginBottom: spacing.lg,
    maxWidth: 480,
  },

  // ===== STEPS =====
  stepCard: {
    flexDirection: "row",
    gap: spacing.md,
    paddingVertical: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  stepNumBox: {
    width: 44,
    height: 44,
    borderWidth: 1,
    borderColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  stepNum: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: "900",
    letterSpacing: 1,
  },
  stepTitle: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: "800",
    marginBottom: 4,
  },
  stepDesc: { color: colors.textSecondary, fontSize: 14, lineHeight: 20 },

  // ===== PRICING =====
  priceCard: {
    backgroundColor: colors.surfaceElevated,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
    marginBottom: spacing.md,
    borderRadius: 4,
  },
  priceCardFeatured: {
    borderColor: colors.primary,
    backgroundColor: colors.surface,
  },
  featuredBadge: {
    position: "absolute",
    top: -10,
    right: spacing.md,
    backgroundColor: colors.primary,
    paddingVertical: 4,
    paddingHorizontal: 10,
  },
  featuredBadgeText: {
    color: "#000",
    fontSize: 10,
    fontWeight: "900",
    letterSpacing: 1,
  },
  priceHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-end",
    marginBottom: spacing.md,
  },
  priceTier: {
    color: colors.textPrimary,
    fontSize: 18,
    fontWeight: "900",
    letterSpacing: 2,
  },
  priceAmount: {
    color: colors.textPrimary,
    fontSize: 28,
    fontWeight: "900",
    letterSpacing: -1,
    textAlign: "right",
  },
  pricePeriod: {
    color: colors.textMuted,
    fontSize: 11,
    textAlign: "right",
    marginTop: -2,
  },
  priceBullet: {
    color: colors.textSecondary,
    fontSize: 14,
    lineHeight: 22,
  },
  refundLine: {
    color: colors.textMuted,
    fontSize: 12,
    textAlign: "center",
    marginTop: spacing.md,
    lineHeight: 18,
  },
  refundLink: {
    color: colors.primary,
    textDecorationLine: "underline",
    fontWeight: "700",
  },

  // ===== FAQ =====
  faqItem: {
    paddingVertical: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  faqQ: {
    color: colors.textPrimary,
    fontSize: 15,
    fontWeight: "800",
    marginBottom: 6,
  },
  faqA: { color: colors.textSecondary, fontSize: 14, lineHeight: 20 },

  // ===== CONTACT =====
  contactCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surfaceElevated,
    padding: spacing.md,
    marginBottom: spacing.sm,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: colors.border,
  },
  contactLabel: {
    color: colors.textMuted,
    fontSize: 10,
    letterSpacing: 2,
    fontWeight: "800",
    marginBottom: 2,
  },
  contactValue: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: "600",
  },

  // ===== CTA =====
  ctaSection: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xxl,
    alignItems: "center",
    backgroundColor: colors.background,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  ctaTitle: {
    color: colors.textPrimary,
    fontSize: 28,
    fontWeight: "900",
    letterSpacing: -1,
    textAlign: "center",
    marginBottom: 8,
  },
  ctaSubtitle: {
    color: colors.textSecondary,
    fontSize: 14,
    textAlign: "center",
    marginBottom: spacing.lg,
  },
  ctaBtn: {
    backgroundColor: colors.primary,
    paddingVertical: 16,
    paddingHorizontal: spacing.xl,
    borderRadius: 4,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    minWidth: 280,
  },

  // ===== FOOTER =====
  footer: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xl,
    alignItems: "center",
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  footerBrand: {
    color: colors.primary,
    fontSize: 12,
    letterSpacing: 4,
    fontWeight: "800",
    marginBottom: spacing.md,
  },
  footerLinksRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginBottom: spacing.md,
  },
  footerLink: {
    color: colors.textPrimary,
    fontSize: 12,
    textDecorationLine: "underline",
    opacity: 0.85,
  },
  footerDot: { color: colors.textMuted, fontSize: 12 },
  footerCopy: { color: colors.textMuted, fontSize: 11 },
});
