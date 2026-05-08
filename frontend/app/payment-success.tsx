import { useEffect, useRef, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
  Platform,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { getPaymentStatus } from "../src/api";
import { colors, spacing } from "../src/theme";

export default function PaymentSuccess() {
  const router = useRouter();
  const params = useLocalSearchParams<{ session_id?: string }>();
  const [statusText, setStatusText] = useState("Confirming payment...");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const attemptsRef = useRef(0);

  // On web, get session_id from URL query string (works alongside expo-router)
  let sessionId = params.session_id as string | undefined;
  if (
    !sessionId &&
    Platform.OS === "web" &&
    typeof window !== "undefined"
  ) {
    const url = new URL(window.location.href);
    sessionId = url.searchParams.get("session_id") || undefined;
  }

  useEffect(() => {
    if (!sessionId) {
      setError("Missing session_id");
      setDone(true);
      return;
    }
    let cancelled = false;
    const poll = async () => {
      attemptsRef.current += 1;
      try {
        const r = await getPaymentStatus(sessionId!);
        if (cancelled) return;
        if (r.payment_status === "paid") {
          setStatusText("Payment confirmed. Welcome, Coach!");
          setDone(true);
          return;
        }
        if (r.status === "expired") {
          setStatusText("Payment session expired.");
          setError("Expired");
          setDone(true);
          return;
        }
        if (attemptsRef.current >= 8) {
          setStatusText(
            "Still processing — check Profile in a moment, or contact support."
          );
          setDone(true);
          return;
        }
        setStatusText(`Verifying payment...`);
        setTimeout(poll, 2000);
      } catch (e: any) {
        if (cancelled) return;
        setError(e?.message || "Status check failed");
        setDone(true);
      }
    };
    poll();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  return (
    <SafeAreaView style={styles.container} testID="payment-success-screen">
      <View style={styles.body}>
        {!done ? (
          <>
            <ActivityIndicator size="large" color={colors.primary} />
            <Text style={styles.title}>{statusText}</Text>
          </>
        ) : (
          <>
            <Ionicons
              name={error ? "alert-circle" : "checkmark-circle"}
              size={72}
              color={error ? colors.error : colors.success}
            />
            <Text style={styles.title}>{statusText}</Text>
            {error ? (
              <Text style={styles.errorText} testID="payment-error">
                {error}
              </Text>
            ) : null}
            <TouchableOpacity
              style={styles.btn}
              onPress={() => router.replace("/(tabs)/profile")}
              testID="payment-success-continue"
            >
              <Text style={styles.btnText}>Back to Profile</Text>
            </TouchableOpacity>
          </>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  body: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.lg,
    gap: spacing.md,
  },
  title: {
    color: colors.textPrimary,
    fontSize: 18,
    fontWeight: "800",
    letterSpacing: 0.5,
    textAlign: "center",
  },
  errorText: { color: colors.error, fontSize: 13, textAlign: "center" },
  btn: {
    marginTop: spacing.lg,
    backgroundColor: colors.primary,
    paddingVertical: 14,
    paddingHorizontal: 32,
  },
  btnText: {
    color: "#000",
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
});
