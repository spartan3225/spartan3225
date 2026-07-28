import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { Platform, StyleSheet, View } from "react-native";
import { BlurView } from "expo-blur";
import { colors } from "../../src/theme";
import { useI18n } from "../../src/i18n";
import { haptic } from "../../src/haptics";

function TabIcon({
  focused,
  color,
  name,
  nameActive,
}: {
  focused: boolean;
  color: string;
  name: any;
  nameActive: any;
}) {
  return (
    <View style={styles.iconWrap}>
      {focused && <View style={styles.glow} />}
      <Ionicons name={focused ? nameActive : name} size={23} color={color} />
    </View>
  );
}

export default function TabsLayout() {
  const { t } = useI18n();

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textMuted,
        tabBarStyle: {
          position: "absolute",
          backgroundColor:
            Platform.OS === "ios" ? "transparent" : "rgba(10,10,10,0.96)",
          borderTopColor: "rgba(255,255,255,0.08)",
          borderTopWidth: StyleSheet.hairlineWidth,
          height: Platform.OS === "ios" ? 84 : 68,
          paddingTop: 8,
          elevation: 0,
        },
        tabBarBackground: () =>
          Platform.OS === "ios" ? (
            <BlurView
              tint="dark"
              intensity={80}
              style={StyleSheet.absoluteFill}
            />
          ) : null,
        tabBarLabelStyle: {
          fontSize: 10,
          fontWeight: "700",
          letterSpacing: 0.4,
        },
      }}
      screenListeners={{
        tabPress: () => haptic.tap(),
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: t("tab_home"),
          tabBarIcon: (p) => (
            <TabIcon {...p} name="home-outline" nameActive="home" />
          ),
        }}
      />
      <Tabs.Screen
        name="review"
        options={{
          title: t("tab_review"),
          tabBarIcon: (p) => (
            <TabIcon {...p} name="sparkles-outline" nameActive="sparkles" />
          ),
        }}
      />
      <Tabs.Screen
        name="progress"
        options={{
          title: t("tab_progress"),
          tabBarIcon: (p) => (
            <TabIcon {...p} name="trending-up-outline" nameActive="trending-up" />
          ),
        }}
      />
      <Tabs.Screen
        name="train"
        options={{
          title: t("tab_train"),
          tabBarIcon: (p) => (
            <TabIcon {...p} name="barbell-outline" nameActive="barbell" />
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: t("tab_profile"),
          tabBarIcon: (p) => (
            <TabIcon {...p} name="person-outline" nameActive="person" />
          ),
        }}
      />
      {/* Upload lives inside tabs (existing flows navigate here) but is not a tab */}
      <Tabs.Screen name="upload" options={{ href: null }} />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  iconWrap: { alignItems: "center", justifyContent: "center", paddingTop: 2 },
  glow: {
    position: "absolute",
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: "rgba(0,229,255,0.12)",
  },
});
