import { useEffect, useRef, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  Platform,
} from "react-native";
import { useRouter } from "expo-router";
import { exchangeSessionId } from "../src/api";
import { colors } from "../src/theme";

export default function AuthCallback() {
  const router = useRouter();
  const processed = useRef(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;
    (async () => {
      try {
        let sessionId: string | null = null;
        if (Platform.OS === "web" && typeof window !== "undefined") {
          const src = (window.location.hash || "") + (window.location.search || "");
          const m = src.match(/session_id=([^&#]+)/);
          if (m && m[1]) sessionId = decodeURIComponent(m[1]);
        }
        if (!sessionId) {
          setError("Missing session id");
          setTimeout(() => router.replace("/"), 1500);
          return;
        }
        await exchangeSessionId(sessionId);
        // Clean the URL only AFTER the exchange succeeded.
        if (Platform.OS === "web" && typeof window !== "undefined") {
          window.history.replaceState(
            window.history.state,
            "",
            window.location.pathname
          );
        }
        // Send new sign-ins to plans first; X closes to dashboard.
        router.replace("/paywall");
      } catch (e: any) {
        setError(e?.message || "Auth failed");
        setTimeout(() => router.replace("/"), 1800);
      }
    })();
  }, [router]);

  return (
    <View style={styles.container} testID="auth-callback">
      <ActivityIndicator size="large" color={colors.primary} />
      <Text style={styles.text}>
        {error ? error : "Securing your session..."}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: "center",
    justifyContent: "center",
    gap: 14,
  },
  text: {
    color: colors.textSecondary,
    fontSize: 13,
    letterSpacing: 1,
  },
});
