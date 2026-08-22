import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { I18nProvider } from "../src/i18n";
import ErrorBoundary from "../src/components/ErrorBoundary";

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: "#0A0A0A" }}>
      <ErrorBoundary>
      <SafeAreaProvider>
        <I18nProvider>
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
          <Stack.Screen
            name="compare/[id]"
            options={{ animation: "slide_from_right" }}
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
        </I18nProvider>
      </SafeAreaProvider>
      </ErrorBoundary>
    </GestureHandlerRootView>
  );
}
