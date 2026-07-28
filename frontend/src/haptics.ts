import { Platform } from "react-native";
import * as Haptics from "expo-haptics";

const native = Platform.OS === "ios" || Platform.OS === "android";

export const haptic = {
  tap: () => {
    if (native) Haptics.selectionAsync().catch(() => {});
  },
  light: () => {
    if (native) Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
  },
  medium: () => {
    if (native) Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
  },
  success: () => {
    if (native)
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
  },
};
