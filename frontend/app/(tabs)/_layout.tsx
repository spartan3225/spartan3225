import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { View, StyleSheet } from "react-native";
import { colors } from "../../src/theme";

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
          borderTopWidth: 1,
          height: 70,
          paddingTop: 8,
          paddingBottom: 12,
        },
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textMuted,
        tabBarLabelStyle: {
          fontSize: 10,
          letterSpacing: 1.5,
          textTransform: "uppercase",
          fontWeight: "700",
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Sessions",
          tabBarIcon: ({ color, focused }) => (
            <View style={styles.iconWrap}>
              {focused && <View style={styles.activeBar} />}
              <Ionicons name="albums-outline" size={22} color={color} />
            </View>
          ),
        }}
      />
      <Tabs.Screen
        name="upload"
        options={{
          title: "Analyse",
          tabBarIcon: ({ color, focused }) => (
            <View style={styles.iconWrap}>
              {focused && <View style={styles.activeBar} />}
              <Ionicons name="sparkles-outline" size={22} color={color} />
            </View>
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "Profile",
          tabBarIcon: ({ color, focused }) => (
            <View style={styles.iconWrap}>
              {focused && <View style={styles.activeBar} />}
              <Ionicons name="person-outline" size={22} color={color} />
            </View>
          ),
        }}
      />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  iconWrap: {
    alignItems: "center",
    justifyContent: "center",
    paddingTop: 4,
  },
  activeBar: {
    position: "absolute",
    top: -10,
    height: 2,
    width: 30,
    backgroundColor: colors.primary,
  },
});
