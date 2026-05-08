import * as Notifications from "expo-notifications";
import * as Device from "expo-device";
import { Platform } from "react-native";
import { savePushToken } from "./api";

let registered = false;

export async function registerForPushNotificationsAsync(): Promise<string | null> {
  if (registered) return null;
  registered = true;

  // Web does not support Expo push notifications
  if (Platform.OS === "web") return null;
  if (!Device.isDevice) return null;

  try {
    const { status: existingStatus } = await Notifications.getPermissionsAsync();
    let finalStatus = existingStatus;
    if (existingStatus !== "granted") {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
    }
    if (finalStatus !== "granted") return null;

    if (Platform.OS === "android") {
      await Notifications.setNotificationChannelAsync("default", {
        name: "default",
        importance: Notifications.AndroidImportance.HIGH,
        vibrationPattern: [0, 250, 250, 250],
        lightColor: "#00E5FF",
      });
    }

    const tokenObj = await Notifications.getExpoPushTokenAsync();
    const token = tokenObj.data;
    if (token) {
      try {
        await savePushToken(token);
      } catch {
        // ignore
      }
      return token;
    }
  } catch (e) {
    console.warn("push registration failed", e);
  }
  return null;
}

export function setNotificationHandler() {
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowAlert: true,
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: true,
      shouldSetBadge: false,
    }),
  });
}
