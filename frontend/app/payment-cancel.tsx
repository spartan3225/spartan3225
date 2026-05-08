import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { colors, spacing } from "../src/theme";

export default function PaymentCancel() {
  const router = useRouter();
  return (
    <SafeAreaView style={styles.container} testID="payment-cancel-screen">
      <View style={styles.body}>
        <Ionicons name="close-circle-outline" size={72} color={colors.error} />
        <Text style={styles.title}>Payment Cancelled</Text>
        <Text style={styles.sub}>No charges were made. You can try again any time.</Text>
        <TouchableOpacity
          style={styles.btn}
          onPress={() => router.replace("/paywall")}
          testID="payment-cancel-retry"
        >
          <Text style={styles.btnText}>View Plans</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={() => router.replace("/(tabs)/profile")}>
          <Text style={styles.link}>Back to profile</Text>
        </TouchableOpacity>
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
    fontSize: 22,
    fontWeight: "900",
    letterSpacing: -0.5,
  },
  sub: { color: colors.textSecondary, fontSize: 14, textAlign: "center" },
  btn: {
    marginTop: spacing.md,
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
  link: {
    color: colors.textMuted,
    fontSize: 13,
    marginTop: spacing.sm,
    textDecorationLine: "underline",
  },
});
