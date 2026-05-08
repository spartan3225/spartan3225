import { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  Platform,
  ScrollView,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import * as ImagePicker from "expo-image-picker";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { VideoView, useVideoPlayer } from "expo-video";
import { uploadVideo } from "../../src/api";
import { colors, spacing } from "../../src/theme";

type PickedAsset = {
  uri: string;
  fileName?: string | null;
  mimeType?: string | null;
  fileSize?: number | null;
};

export default function UploadScreen() {
  const router = useRouter();
  const [asset, setAsset] = useState<PickedAsset | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const player = useVideoPlayer(asset?.uri || null, (p) => {
    p.loop = true;
    p.muted = true;
  });

  const showError = (m: string) => {
    setError(m);
    if (Platform.OS !== "web") Alert.alert("Error", m);
  };

  const pickFromGallery = async () => {
    setError(null);
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      showError("Gallery permission denied");
      return;
    }
    const r = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Videos,
      videoMaxDuration: 60,
      quality: 0.8,
    });
    if (!r.canceled && r.assets[0]) {
      const a = r.assets[0];
      setAsset({
        uri: a.uri,
        fileName: a.fileName,
        mimeType: a.mimeType || "video/mp4",
        fileSize: a.fileSize,
      });
    }
  };

  const recordWithCamera = async () => {
    setError(null);
    const cam = await ImagePicker.requestCameraPermissionsAsync();
    if (!cam.granted) {
      showError("Camera permission denied");
      return;
    }
    const r = await ImagePicker.launchCameraAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Videos,
      videoMaxDuration: 60,
      quality: 0.8,
    });
    if (!r.canceled && r.assets[0]) {
      const a = r.assets[0];
      setAsset({
        uri: a.uri,
        fileName: a.fileName,
        mimeType: a.mimeType || "video/mp4",
        fileSize: a.fileSize,
      });
    }
  };

  const submit = async () => {
    if (!asset) return;
    setSubmitting(true);
    setError(null);
    try {
      const name =
        asset.fileName ||
        `clip_${Date.now()}.${(asset.mimeType?.split("/")?.[1] || "mp4")}`;
      const result = await uploadVideo(
        asset.uri,
        name,
        asset.mimeType || "video/mp4"
      );
      router.replace(`/analysis/${result.analysis_id}` as any);
    } catch (e: any) {
      showError(e?.message || "Upload failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={["top"]} testID="upload-screen">
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <View style={styles.brandRow}>
            <View style={styles.brandDot} />
            <Text style={styles.brandLabel}>NEW · ANALYSIS</Text>
          </View>
          <Text style={styles.heading}>DROP{"\n"}YOUR CLIP.</Text>
          <Text style={styles.subheading}>
            10–60 second wave clip works best. Front-on, side-on or follow cams
            all welcome.
          </Text>
        </View>

        {/* Preview */}
        <View style={styles.previewWrap}>
          {asset ? (
            <VideoView
              player={player}
              style={styles.video}
              contentFit="cover"
              allowsFullscreen
              nativeControls
              testID="video-preview"
            />
          ) : (
            <View style={styles.previewPlaceholder}>
              <Ionicons
                name="cloud-upload-outline"
                size={42}
                color={colors.primary}
              />
              <Text style={styles.previewText}>No clip selected</Text>
            </View>
          )}
          {submitting && (
            <View style={styles.loadingOverlay} testID="analysis-loading">
              <ActivityIndicator size="large" color={colors.primary} />
              <Text style={styles.loadingText}>AI COACH ANALYSING...</Text>
              <Text style={styles.loadingSub}>
                Reading every frame. This usually takes 20–60 seconds.
              </Text>
            </View>
          )}
        </View>

        {/* Action buttons */}
        <View style={styles.row}>
          <TouchableOpacity
            style={[styles.optionBtn, { marginRight: spacing.sm }]}
            onPress={pickFromGallery}
            disabled={submitting}
            testID="pick-gallery-btn"
          >
            <Ionicons name="images-outline" size={20} color={colors.primary} />
            <Text style={styles.optionText}>Gallery</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.optionBtn}
            onPress={recordWithCamera}
            disabled={submitting}
            testID="record-camera-btn"
          >
            <Ionicons
              name="videocam-outline"
              size={20}
              color={colors.primary}
            />
            <Text style={styles.optionText}>Record</Text>
          </TouchableOpacity>
        </View>

        {error ? (
          <Text style={styles.error} testID="upload-error">
            {error}
          </Text>
        ) : null}

        <TouchableOpacity
          style={[
            styles.submitBtn,
            (!asset || submitting) && styles.submitDisabled,
          ]}
          disabled={!asset || submitting}
          onPress={submit}
          testID="start-analysis-btn"
        >
          {submitting ? (
            <ActivityIndicator color="#000" />
          ) : (
            <>
              <Ionicons name="sparkles" size={16} color="#000" />
              <Text style={styles.submitText}>Analyse Surf Technique</Text>
            </>
          )}
        </TouchableOpacity>

        <View style={styles.tipsBox}>
          <Text style={styles.tipsLabel}>FOR BEST RESULTS</Text>
          <Text style={styles.tip}>• Steady camera, ideally tripod or rail</Text>
          <Text style={styles.tip}>• Surfer fills 30%+ of frame</Text>
          <Text style={styles.tip}>• Capture pop-up to top-turn</Text>
          <Text style={styles.tip}>• Keep clip under 60 seconds</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, paddingBottom: 64 },
  header: { marginBottom: spacing.lg },
  brandRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: spacing.md,
  },
  brandDot: { width: 8, height: 8, backgroundColor: colors.primary },
  brandLabel: {
    color: colors.primary,
    fontSize: 11,
    letterSpacing: 4,
    fontWeight: "800",
  },
  heading: {
    color: colors.textPrimary,
    fontSize: 40,
    fontWeight: "900",
    letterSpacing: -2,
    lineHeight: 42,
    textTransform: "uppercase",
    marginBottom: spacing.sm,
  },
  subheading: {
    color: colors.textSecondary,
    fontSize: 14,
    lineHeight: 20,
  },
  previewWrap: {
    height: 240,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    overflow: "hidden",
    marginBottom: spacing.md,
    position: "relative",
  },
  previewPlaceholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
  },
  previewText: {
    color: colors.textMuted,
    fontSize: 12,
    letterSpacing: 2,
    textTransform: "uppercase",
  },
  video: { width: "100%", height: "100%" },
  loadingOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(10,10,10,0.92)",
    alignItems: "center",
    justifyContent: "center",
    gap: 14,
    paddingHorizontal: spacing.lg,
    borderWidth: 1,
    borderColor: colors.primary,
  },
  loadingText: {
    color: colors.primary,
    fontSize: 13,
    letterSpacing: 3,
    fontWeight: "800",
  },
  loadingSub: {
    color: colors.textSecondary,
    fontSize: 12,
    textAlign: "center",
    lineHeight: 18,
  },
  row: { flexDirection: "row", marginBottom: spacing.md },
  optionBtn: {
    flex: 1,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    paddingVertical: 16,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  optionText: {
    color: colors.textPrimary,
    fontSize: 13,
    letterSpacing: 1.5,
    textTransform: "uppercase",
    fontWeight: "700",
  },
  submitBtn: {
    backgroundColor: colors.primary,
    paddingVertical: 16,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    marginBottom: spacing.lg,
  },
  submitDisabled: { opacity: 0.4 },
  submitText: {
    color: "#000",
    fontSize: 14,
    fontWeight: "800",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  tipsBox: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing.md,
  },
  tipsLabel: {
    color: colors.textMuted,
    fontSize: 11,
    letterSpacing: 2.5,
    fontWeight: "800",
    marginBottom: 8,
  },
  tip: {
    color: colors.textSecondary,
    fontSize: 13,
    marginBottom: 4,
    lineHeight: 18,
  },
  error: {
    color: colors.error,
    fontSize: 13,
    marginBottom: spacing.sm,
  },
});
