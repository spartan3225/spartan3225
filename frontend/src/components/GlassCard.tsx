import { View, StyleSheet, ViewStyle, StyleProp } from "react-native";
import { colors, radii, spacing } from "../theme";

export default function GlassCard({
  children,
  style,
  accent,
  testID,
}: {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  accent?: string; // optional left accent / tinted border colour
  testID?: string;
}) {
  return (
    <View
      testID={testID}
      style={[
        styles.card,
        accent ? { borderColor: `${accent}44` } : null,
        style,
      ]}
    >
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.glass,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    borderRadius: radii.lg,
    padding: spacing.md,
    overflow: "hidden",
  },
});
