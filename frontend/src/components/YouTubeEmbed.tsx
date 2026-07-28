import React from "react";
import { Platform, View, StyleSheet } from "react-native";
import { WebView } from "react-native-webview";
import { radii } from "../theme";

/** Cross-platform YouTube embed (iframe on web, WebView on native). */
export default function YouTubeEmbed({
  videoId,
  height = 210,
}: {
  videoId: string;
  height?: number;
}) {
  const src = `https://www.youtube.com/embed/${videoId}?rel=0&playsinline=1`;

  if (Platform.OS === "web") {
    return (
      <View style={[styles.wrap, { height }]}>
        {React.createElement("iframe", {
          src,
          style: {
            width: "100%",
            height: "100%",
            border: 0,
            borderRadius: 14,
          },
          allow:
            "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture",
          allowFullScreen: true,
        })}
      </View>
    );
  }

  return (
    <View style={[styles.wrap, { height }]}>
      <WebView
        source={{ uri: src }}
        style={{ flex: 1, backgroundColor: "#000" }}
        allowsFullscreenVideo
        allowsInlineMediaPlayback
        mediaPlaybackRequiresUserAction={false}
        javaScriptEnabled
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    borderRadius: radii.md,
    overflow: "hidden",
    backgroundColor: "#000",
  },
});
