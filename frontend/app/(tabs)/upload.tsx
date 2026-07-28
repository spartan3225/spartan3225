import { useCallback, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  Platform,
  ScrollView,
  Linking,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import * as ImagePicker from "expo-image-picker";
import { useFocusEffect, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { VideoView, useVideoPlayer } from "expo-video";
import {
  uploadVideo,
  uploadChunksForFile,
  finalizeMultiUpload,
  createCheckout,
  fetchMe,
  ChunkedUploadRef,
} from "../../src/api";
import { colors, spacing } from "../../src/theme";
import { useI18n } from "../../src/i18n";
import { haptic } from "../../src/haptics";

type PickedAsset = {
  uri: string;
  fileName?: string | null;
  mimeType?: string | null;
  fileSize?: number | null;
};

export default function UploadScreen() {
  const router = useRouter();
  const { t } = useI18n();
  const [asset, setAsset] = useState<PickedAsset | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"single" | "multi">("single");
  const [multiAssets, setMultiAssets] = useState<PickedAsset[]>([]);
  const [credits, setCredits] = useState(0);
  const [buying, setBuying] = useState(false);

  useFocusEffect(
    useCallback(() => {
      fetchMe()
        .then((me) => setCredits(me?.multi_credits || 0))
        .catch(() => {});
    }, [])
  );

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
      const picked: PickedAsset = {
        uri: a.uri,
        fileName: a.fileName,
        mimeType: a.mimeType || "video/mp4",
        fileSize: a.fileSize,
      };
      if (mode === "multi") {
        setMultiAssets((prev) => (prev.length >= 3 ? prev : [...prev, picked]));
      } else {
        setAsset(picked);
      }
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
      const picked: PickedAsset = {
        uri: a.uri,
        fileName: a.fileName,
        mimeType: a.mimeType || "video/mp4",
        fileSize: a.fileSize,
      };
      if (mode === "multi") {
        setMultiAssets((prev) => (prev.length >= 3 ? prev : [...prev, picked]));
      } else {
        setAsset(picked);
      }
    }
  };

  const buyCredit = async () => {
    setBuying(true);
    setError(null);
    try {
      const origin =
        Platform.OS === "web" && typeof window !== "undefined"
          ? window.location.origin
          : "https://surfcoach23.com";
      const { url } = await createCheckout("multi", origin);
      if (Platform.OS === "web" && typeof window !== "undefined") {
        window.location.href = url;
      } else {
        await Linking.openURL(url);
      }
    } catch (e: any) {
      showError(e?.message || "Could not start checkout");
    } finally {
      setBuying(false);
    }
  };

  const submitMulti = async () => {
    if (multiAssets.length < 2) return;
    setSubmitting(true);
    setProgress(0);
    setError(null);
    try {
      const refs: ChunkedUploadRef[] = [];
      for (let i = 0; i < multiAssets.length; i++) {
        const a = multiAssets[i];
        const name =
          a.fileName ||
          `clip_${Date.now()}_${i}.${a.mimeType?.split("/")?.[1] || "mp4"}`;
        const ref = await uploadChunksForFile(
          a.uri,
          name,
          a.mimeType || "video/mp4",
          (pct) =>
            setProgress(
              Math.round(((i + pct / 100) / multiAssets.length) * 95)
            )
        );
        refs.push(ref);
      }
      const result = await finalizeMultiUpload(refs);
      haptic.success();
      setMultiAssets([]);
      setCredits((c) => Math.max(0, c - 1));
      router.replace(`/analysis/${result.analysis_id}` as any);
    } catch (e: any) {
      const m = String(e?.message || "");
      if (m.includes("402") || m.toLowerCase().includes("credit")) {
        showError(t("credit_needed_note"));
      } else {
        showError(e?.message || "Upload failed");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const submit = async () => {
    if (!asset) return;
    setSubmitting(true);
    setProgress(0);
    setError(null);
    try {
      const name =
        asset.fileName ||
        `clip_${Date.now()}.${(asset.mimeType?.split("/")?.[1] || "mp4")}`;
      const result = await uploadVideo(
        asset.uri,
        name,
        asset.mimeType || "video/mp4",
        (pct) => setProgress(pct)
      );
      haptic.success();
      router.replace(`/analysis/${result.analysis_id}` as any);
    } catch (e: any) {
      const m = String(e?.message || "");
      if (m.includes("402")) {
        showError("Free plan limit reached. Upgrade to Coach for unlimited analyses.");
        router.push("/paywall" as any);
        return;
      }
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
          <Text style={styles.heading}>{t("upload_title").toUpperCase()}</Text>
          <Text style={styles.subheading}>
            {mode === "multi" ? t("multi_sub") : t("upload_sub")}
          </Text>
        </View>

        {/* Mode toggle */}
        <View style={styles.modeRow} testID="mode-toggle">
          {(
            [
              ["single", t("single_mode")],
              ["multi", t("multi_mode")],
            ] as const
          ).map(([key, label]) => (
            <TouchableOpacity
              key={key}
              style={[styles.modeBtn, mode === key && styles.modeBtnActive]}
              onPress={() => {
                haptic.tap();
                setMode(key);
                setError(null);
              }}
              disabled={submitting}
              testID={`mode-${key}`}
            >
              <Text style={[styles.modeText, mode === key && { color: "#000" }]}>
                {label}
              </Text>
            </TouchableOpacity>
          ))}
          {mode === "multi" && (
            <View style={styles.creditsPill} testID="credits-pill">
              <Ionicons name="ticket-outline" size={13} color={colors.primary} />
              <Text style={styles.creditsText}>
                {t("credits")}: {credits}
              </Text>
            </View>
          )}
        </View>

        {mode === "multi" && (
          <View style={styles.multiBox}>
            {multiAssets.map((a, i) => (
              <View key={i} style={styles.multiRow} testID={`multi-clip-${i}`}>
                <Ionicons name="film-outline" size={16} color={colors.primary} />
                <Text style={styles.multiName} numberOfLines={1}>
                  {t("clip")} {i + 1} — {a.fileName || a.uri.split("/").pop()}
                </Text>
                <TouchableOpacity
                  onPress={() =>
                    setMultiAssets((prev) => prev.filter((_, j) => j !== i))
                  }
                  disabled={submitting}
                  testID={`multi-remove-${i}`}
                >
                  <Ionicons name="close-circle" size={18} color={colors.error} />
                </TouchableOpacity>
              </View>
            ))}
            {multiAssets.length < 3 && (
              <TouchableOpacity
                style={styles.addClipBtn}
                onPress={pickFromGallery}
                disabled={submitting}
                testID="add-clip-btn"
              >
                <Ionicons name="add" size={16} color={colors.primary} />
                <Text style={styles.addClipText}>
                  {t("add_clip")} ({multiAssets.length}/3)
                </Text>
              </TouchableOpacity>
            )}
            <Text style={styles.creditNote}>{t("credit_needed_note")}</Text>
            {credits === 0 &&
              (Platform.OS === "ios" ? (
                <Text style={styles.iosNote} testID="ios-purchase-note">
                  {t("ios_purchase_note")}
                </Text>
              ) : (
                <TouchableOpacity
                  style={styles.buyBtn}
                  onPress={buyCredit}
                  disabled={buying || submitting}
                  testID="buy-credit-btn"
                >
                  {buying ? (
                    <ActivityIndicator color={colors.primary} size="small" />
                  ) : (
                    <>
                      <Ionicons name="cart-outline" size={15} color={colors.primary} />
                      <Text style={styles.buyText}>{t("buy_credit")}</Text>
                    </>
                  )}
                </TouchableOpacity>
              ))}
          </View>
        )}

        {/* Preview */}
        {mode === "single" && (
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
              <Text style={styles.previewText}>{t("no_clip")}</Text>
            </View>
          )}
          {submitting && (
            <View style={styles.loadingOverlay} testID="analysis-loading">
              <ActivityIndicator size="large" color={colors.primary} />
              <Text style={styles.loadingText}>
                {progress < 100
                  ? `${t("uploading").toUpperCase()}... ${progress}%`
                  : t("ai_analysing").toUpperCase()}
              </Text>
              <Text style={styles.loadingSub}>
                {progress < 100
                  ? "Sending your clip in small pieces — keep the app open."
                  : "Reading every frame. This usually takes 20–60 seconds."}
              </Text>
            </View>
          )}
        </View>
        )}

        {/* Action buttons */}
        {mode === "single" && (
        <View style={styles.row}>
          <TouchableOpacity
            style={[styles.optionBtn, { marginRight: spacing.sm }]}
            onPress={pickFromGallery}
            disabled={submitting}
            testID="pick-gallery-btn"
          >
            <Ionicons name="images-outline" size={20} color={colors.primary} />
            <Text style={styles.optionText}>{t("gallery")}</Text>
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
            <Text style={styles.optionText}>{t("record")}</Text>
          </TouchableOpacity>
        </View>
        )}

        {error ? (
          <Text style={styles.error} testID="upload-error">
            {error}
          </Text>
        ) : null}

        <TouchableOpacity
          style={[
            styles.submitBtn,
            (mode === "single"
              ? !asset || submitting
              : multiAssets.length < 2 || submitting || credits === 0) &&
              styles.submitDisabled,
          ]}
          disabled={
            mode === "single"
              ? !asset || submitting
              : multiAssets.length < 2 || submitting || credits === 0
          }
          onPress={mode === "single" ? submit : submitMulti}
          testID="start-analysis-btn"
        >
          {submitting ? (
            <>
              <ActivityIndicator color="#000" />
              {mode === "multi" && (
                <Text style={styles.submitText}>{progress}%</Text>
              )}
            </>
          ) : (
            <>
              <Ionicons name="sparkles" size={16} color="#000" />
              <Text style={styles.submitText}>
                {mode === "single" ? t("analyse_btn") : t("analyse_multi_btn")}
              </Text>
            </>
          )}
        </TouchableOpacity>
        {mode === "multi" && multiAssets.length < 2 && !submitting ? (
          <Text style={styles.creditNote}>{t("need_two")}</Text>
        ) : null}

        <View style={styles.tipsBox}>
          <Text style={styles.tipsLabel}>{t("best_results").toUpperCase()}</Text>
          <Text style={styles.tip}>• {t("tip1")}</Text>
          <Text style={styles.tip}>• {t("tip2")}</Text>
          <Text style={styles.tip}>• {t("tip3")}</Text>
          <Text style={styles.tip}>• {t("tip4")}</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, paddingBottom: 120 },
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
  modeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: spacing.md,
  },
  modeBtn: {
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    borderRadius: 999,
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  modeBtnActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  modeText: {
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0.5,
  },
  creditsPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    marginLeft: "auto",
    borderWidth: 1,
    borderColor: `${colors.primary}55`,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  creditsText: { color: colors.primary, fontSize: 11, fontWeight: "800" },
  multiBox: {
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    padding: spacing.md,
    marginBottom: spacing.md,
    gap: 10,
  },
  multiRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  multiName: { flex: 1, color: colors.textPrimary, fontSize: 12, fontWeight: "600" },
  addClipBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    borderWidth: 1,
    borderColor: `${colors.primary}55`,
    borderStyle: "dashed",
    paddingVertical: 12,
  },
  addClipText: { color: colors.primary, fontSize: 12, fontWeight: "800" },
  creditNote: { color: colors.textMuted, fontSize: 11, lineHeight: 15 },
  iosNote: {
    color: colors.warning,
    fontSize: 12,
    lineHeight: 17,
    fontWeight: "600",
  },
  buyBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 7,
    borderWidth: 1,
    borderColor: colors.primary,
    paddingVertical: 12,
  },
  buyText: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
});
