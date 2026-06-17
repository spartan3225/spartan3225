import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Image,
  Platform,
} from "react-native";
import { useRouter } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import * as Linking from "expo-linking";
import { Ionicons } from "@expo/vector-icons";
import { colors, spacing } from "../src/theme";
import { fetchMe, exchangeSessionId } from "../src/api";

// Hero: dramatic full-body action surfing photograph
const HERO_IMAGE =
  "https://images.unsplash.com/photo-1530870110042-98b2cb110834?w=1400&q=85&auto=format&fit=crop";

export default function LoginScreen() {
  const router = useRouter();
  const [checking, setChecking] = useState(true);
  const [loggingIn, setLoggingIn] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    <View style={styles.container} testID="login-screen">
      <Image source={{ uri: HERO_IMAGE }} style={styles.hero} />
      <View style={styles.overlay} />

      <View style={styles.content}>
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

        <Text style={styles.legal}>
          Your video clips stay private to your account.
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { alignItems: "center", justifyContent: "center" },
  hero: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: "65%",
    resizeMode: "cover",
    opacity: 0.85,
  },
  overlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(10,10,10,0.55)",
  },
  content: {
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
  brandDot: {
    width: 10,
    height: 10,
    backgroundColor: colors.primary,
  },
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
  statDivider: {
    width: 1,
    height: 28,
    backgroundColor: colors.border,
  },
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
  legal: {
    color: colors.textMuted,
    fontSize: 11,
    textAlign: "center",
    marginTop: spacing.md,
  },
  heroFootRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: -4,
    marginBottom: spacing.md,
  },
  heroFootLabel: {
    color: colors.textMuted,
    fontSize: 9,
    letterSpacing: 2,
    fontWeight: "800",
  },
  heroFootName: {
    color: colors.primary,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "800",
  },
  error: {
    color: colors.error,
    marginBottom: spacing.sm,
    fontSize: 13,
  },
});
