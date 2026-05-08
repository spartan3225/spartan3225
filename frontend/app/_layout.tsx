import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { useEffect } from "react";
import { setNotificationHandler } from "../src/push";

export default function RootLayout() {
  useEffect(() => {
    try {
      setNotificationHandler();
    } catch {}
  }, []);
  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: "#0A0A0A" }}>
      <SafeAreaProvider>
        <StatusBar style="light" />
        <Stack
          screenOptions={{
            headerShown: false,
            contentStyle: { backgroundColor: "#0A0A0A" },
            animation: "fade",
          }}
        >
          <Stack.Screen name="index" />
          <Stack.Screen name="auth-callback" />
          <Stack.Screen name="(tabs)" />
          <Stack.Screen
            name="analysis/[id]"
            options={{ animation: "slide_from_bottom" }}
          />
          <Stack.Screen name="paywall" options={{ animation: "slide_from_bottom" }} />
          <Stack.Screen name="payment-success" />
          <Stack.Screen name="payment-cancel" />
          <Stack.Screen name="coaches" />
          <Stack.Screen name="coach/[id]" />
          <Stack.Screen name="coach-edit" />
          <Stack.Screen name="coach-inbox" />
          <Stack.Screen name="manage-plan" />
        </Stack>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
