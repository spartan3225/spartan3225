import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  ImageBackground,
  Platform,
  ScrollView,
  Dimensions,
  TextInput,
  Alert,
} from "react-native";
import { useRouter } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import * as Linking from "expo-linking";
import * as AppleAuthentication from "expo-apple-authentication";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { colors, spacing } from "../src/theme";
import {
  fetchMe,
  exchangeSessionId,
  emailLogin,
  emailRegister,
  appleLogin,
} from "../src/api";

// Hero: cinematic surfer at dusk
const HERO_IMAGE = require("../assets/surf-login.png");

const SCREEN_H = Dimensions.get("window").height;

// Required for the OAuth browser session to close correctly on native.
WebBrowser.maybeCompleteAuthSession();

// Guard: the same session_id can surface from multiple sources on Android
// (auth session result + deep-link listener + initial URL). Exchange once.
const usedSessionIds = new Set<string>();

function extractSessionId(url: string | null | undefined): string | null {
  if (!url) return null;
  const m = url.match(/[?#&]session_id=([^&#]+)/);
  return m && m[1] ? decodeURIComponent(m[1]) : null;
}

export default function LoginScreen() {
  const router = useRouter();
  const [checking, setChecking] = useState(true);
  const [loggingIn, setLoggingIn] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [emailBusy, setEmailBusy] = useState(false);
  const [appleAvailable, setAppleAvailable] = useState(false);

  const onForgotPassword = () => {
    Alert.alert(
      "Reset password",
      "Email us at surfcoach23@gmail.com from your account address and we'll help you reset your password right away.",
      [{ text: "OK" }]
    );
  };

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
      // Cold start (native): app may have been killed and relaunched via the
      // OAuth deep link — the session_id arrives in the initial URL.
      if (Platform.OS !== "web") {
        try {
          const initialUrl = await Linking.getInitialURL();
          const sid = extractSessionId(initialUrl);
          if (sid && !usedSessionIds.has(sid)) {
            usedSessionIds.add(sid);
            await exchangeSessionId(sid);
            router.replace("/(tabs)");
            return;
          }
        } catch {}
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

      // On Android, openAuthSessionAsync often returns "dismiss" with no URL
      // even when login SUCCEEDED (the deep link is delivered separately).
      // Capture it with a listener registered BEFORE opening the browser.
      let listenerUrl: string | null = null;
      const sub = Linking.addEventListener("url", (e) => {
        if (e?.url && e.url.includes("session_id=")) listenerUrl = e.url;
      });
      let result: WebBrowser.WebBrowserAuthSessionResult;
      try {
        result = await WebBrowser.openAuthSessionAsync(authUrl, redirectUrl);
      } finally {
        // Give a hot deep link a beat to arrive before removing the listener.
        setTimeout(() => sub.remove(), 3000);
      }

      let sessionId =
        extractSessionId(result.type === "success" ? result.url : null) ||
        extractSessionId(listenerUrl);
      if (!sessionId) {
        // Last resort: app may have been relaunched via the deep link.
        sessionId = extractSessionId(await Linking.getInitialURL());
      }

      if (sessionId && !usedSessionIds.has(sessionId)) {
        usedSessionIds.add(sessionId);
        await exchangeSessionId(sessionId);
        router.replace("/(tabs)");
        return;
      }
      if (!sessionId) setError("Sign-in cancelled");
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
      {/* ===== HERO / LOGIN ===== */}
      <ImageBackground source={HERO_IMAGE} style={styles.hero} resizeMode="cover">
        <LinearGradient
          colors={[
            "rgba(6,12,20,0.72)",
            "rgba(6,12,20,0.35)",
            "rgba(6,12,20,0.55)",
            "#060C14",
          ]}
          locations={[0, 0.28, 0.6, 1]}
          style={StyleSheet.absoluteFill}
        />

        <View style={styles.heroContent}>
          {/* Brand */}
          <View style={styles.brandRow}>
            <Text style={styles.brandName}>
              SURF<Text style={{ color: colors.primary }}>COACH</Text>23
            </Text>
            <Text style={styles.brandTag}>THE AI SURF COACH</Text>
          </View>

          {/* Greeting */}
          <Text style={styles.greeting} testID="login-title">
            Aloha 🤙
          </Text>
          <Text style={styles.greetingSub}>
            Ready for the next{" "}
            <Text style={{ color: colors.primary, fontStyle: "italic" }}>wave?</Text>
          </Text>

          {error ? (
            <Text style={styles.error} testID="login-error">
              {error}
            </Text>
          ) : null}

          {/* Glass login card */}
          <View style={styles.card}>
            <View style={styles.inputRow}>
              <Ionicons name="mail-outline" size={18} color={colors.textMuted} />
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
            </View>

            <View style={styles.inputRow}>
              <Ionicons name="lock-closed-outline" size={18} color={colors.textMuted} />
              <TextInput
                style={styles.input}
                placeholder="Password"
                placeholderTextColor={colors.textMuted}
                secureTextEntry={!showPassword}
                value={password}
                onChangeText={setPassword}
                testID="password-input"
              />
              <TouchableOpacity
                onPress={() => setShowPassword((s) => !s)}
                hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
              >
                <Ionicons
                  name={showPassword ? "eye-off-outline" : "eye-outline"}
                  size={18}
                  color={colors.textMuted}
                />
              </TouchableOpacity>
            </View>

            {!isRegister && (
              <TouchableOpacity onPress={onForgotPassword} style={styles.forgotBtn}>
                <Text style={styles.forgotText}>Forgot password?</Text>
              </TouchableOpacity>
            )}

            <TouchableOpacity
              activeOpacity={0.9}
              onPress={onEmailSubmit}
              disabled={emailBusy}
              testID="email-submit-btn"
              style={{ marginTop: isRegister ? spacing.md : 4 }}
            >
              <LinearGradient
                colors={["#4FE3F0", "#0091AD"]}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 0 }}
                style={styles.continueBtn}
              >
                {emailBusy ? (
                  <ActivityIndicator color="#00131a" />
                ) : (
                  <Text style={styles.continueText}>
                    {isRegister ? "Create Account" : "Continue"}
                  </Text>
                )}
              </LinearGradient>
            </TouchableOpacity>

            {/* Divider */}
            <View style={styles.orRow}>
              <View style={styles.orLine} />
              <Text style={styles.orText}>OR</Text>
              <View style={styles.orLine} />
            </View>

            <TouchableOpacity
              style={styles.socialBtn}
              onPress={onSignIn}
              activeOpacity={0.85}
              disabled={loggingIn}
              testID="login-google-btn"
            >
              {loggingIn ? (
                <ActivityIndicator color="#000" />
              ) : (
                <>
                  <Ionicons name="logo-google" size={18} color="#000" style={{ marginRight: 10 }} />
                  <Text style={styles.socialText}>Continue with Google</Text>
                </>
              )}
            </TouchableOpacity>

            {appleAvailable && (
              <AppleAuthentication.AppleAuthenticationButton
                buttonType={AppleAuthentication.AppleAuthenticationButtonType.SIGN_IN}
                buttonStyle={AppleAuthentication.AppleAuthenticationButtonStyle.WHITE}
                cornerRadius={14}
                style={styles.appleBtn}
                onPress={onAppleSignIn}
              />
            )}
          </View>

          {/* Feature icons */}
          <View style={styles.featuresRow}>
            <Feature icon="hardware-chip-outline" title="AI Analysis" sub="Advanced tech" />
            <Feature icon="trending-up-outline" title="Real Progress" sub="Improve every session" />
            <Feature icon="shield-checkmark-outline" title="Private & Safe" sub="Your data is secure" />
          </View>

          <TouchableOpacity
            onPress={() => setIsRegister((r) => !r)}
            style={styles.registerRow}
            testID="toggle-register-btn"
          >
            <Text style={styles.registerText}>
              {isRegister ? "Already have an account? " : "Don't have an account? "}
              <Text style={{ color: colors.primary, fontWeight: "800" }}>
                {isRegister ? "Log in" : "Register"}
              </Text>
            </Text>
          </TouchableOpacity>
        </View>
      </ImageBackground>

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

      {/* ===== PRICING (web only — Apple 3.1.1 forbids external purchase
          pricing inside the iOS app) ===== */}
      {Platform.OS === "web" && (
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
      )}

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
              <Text style={styles.socialText}>Continue with Google</Text>
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
          <TouchableOpacity
            onPress={() => router.push("/support" as any)}
            testID="footer-support-link"
          >
            <Text style={styles.footerLink}>Support</Text>
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

function Feature({
  icon,
  title,
  sub,
}: {
  icon: any;
  title: string;
  sub: string;
}) {
  return (
    <View style={styles.feature}>
      <View style={styles.featureIcon}>
        <Ionicons name={icon} size={22} color={colors.primary} />
      </View>
      <Text style={styles.featureTitle}>{title}</Text>
      <Text style={styles.featureSub}>{sub}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { alignItems: "center", justifyContent: "center" },

  // ===== HERO / LOGIN =====
  hero: {
    minHeight: SCREEN_H > 700 ? SCREEN_H : 760,
    backgroundColor: "#060C14",
    justifyContent: "center",
  },
  heroContent: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.xxl + spacing.lg,
    paddingBottom: spacing.xl,
  },
  brandRow: { alignItems: "center", marginBottom: spacing.xl },
  brandName: {
    color: colors.textPrimary,
    fontSize: 32,
    fontWeight: "900",
    letterSpacing: 2,
  },
  brandTag: {
    color: colors.textSecondary,
    fontSize: 9,
    letterSpacing: 4,
    fontWeight: "800",
    marginTop: 2,
  },
  greeting: {
    color: colors.textPrimary,
    fontSize: 46,
    fontWeight: "900",
    letterSpacing: -1.5,
  },
  greetingSub: {
    color: colors.textSecondary,
    fontSize: 18,
    fontStyle: "italic",
    marginTop: 2,
    marginBottom: spacing.lg,
  },
  card: {
    backgroundColor: "rgba(10,18,28,0.72)",
    borderWidth: 1,
    borderColor: "rgba(120,190,220,0.18)",
    borderRadius: 24,
    padding: spacing.lg,
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: "rgba(255,255,255,0.06)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.10)",
    borderRadius: 16,
    paddingHorizontal: 16,
    marginBottom: spacing.sm,
  },
  input: {
    flex: 1,
    color: "#fff",
    paddingVertical: 16,
    fontSize: 16,
  },
  forgotBtn: { alignSelf: "flex-end", paddingVertical: 8, marginBottom: 2 },
  forgotText: { color: colors.primary, fontSize: 14, fontWeight: "700" },
  continueBtn: {
    paddingVertical: 17,
    borderRadius: 999,
    alignItems: "center",
    justifyContent: "center",
  },
  continueText: {
    color: "#00131a",
    fontSize: 17,
    fontWeight: "900",
    letterSpacing: 0.3,
  },
  orRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    marginVertical: spacing.md,
  },
  orLine: { flex: 1, height: StyleSheet.hairlineWidth, backgroundColor: "rgba(255,255,255,0.18)" },
  orText: { color: colors.textMuted, fontSize: 11, fontWeight: "700", letterSpacing: 1 },
  socialBtn: {
    backgroundColor: "#fff",
    paddingVertical: 15,
    borderRadius: 999,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
  },
  socialText: { color: "#000", fontSize: 15, fontWeight: "800" },
  appleBtn: { height: 50, marginTop: spacing.sm },
  featuresRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: spacing.xl,
  },
  feature: { flex: 1, alignItems: "center", paddingHorizontal: 4 },
  featureIcon: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: "rgba(79,227,240,0.10)",
    borderWidth: 1,
    borderColor: "rgba(79,227,240,0.25)",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 8,
  },
  featureTitle: {
    color: colors.textPrimary,
    fontSize: 13,
    fontWeight: "800",
    textAlign: "center",
  },
  featureSub: {
    color: colors.textMuted,
    fontSize: 11,
    textAlign: "center",
    marginTop: 2,
  },
  registerRow: { alignItems: "center", marginTop: spacing.xl },
  registerText: { color: colors.textSecondary, fontSize: 15 },
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
