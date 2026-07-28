import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  TouchableOpacity,
  TextInput,
  Image,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { VideoView, useVideoPlayer } from "expo-video";
import {
  Analysis,
  AnalysisComment,
  addComment,
  fetchMe,
  getAnalysis,
  getToken,
  getVideoStreamUrl,
  listComments,
  User,
} from "../../src/api";
import { colors, scoreColor, severityColor, spacing } from "../../src/theme";

export default function AnalysisDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [data, setData] = useState<Analysis | null>(null);
  const [me, setMe] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [comments, setComments] = useState<AnalysisComment[]>([]);
  const [draft, setDraft] = useState("");
  const [posting, setPosting] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        if (!id) return;
        const [d, t, u] = await Promise.all([
          getAnalysis(id),
          getToken(),
          fetchMe(),
        ]);
        setData(d);
        setMe(u);
        if (t) setVideoUrl(getVideoStreamUrl(d.analysis_id, t));
        try {
          const c = await listComments(id);
          setComments(c);
        } catch {}
      } catch (e: any) {
        setError(e?.message || "Failed to load");
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  // Poll while the AI is still working so the page updates itself the
  // moment the analysis is ready (or failed) — no manual refresh needed.
  useEffect(() => {
    if (!id || !data || data.status !== "processing") return;
    const timer = setInterval(async () => {
      try {
        const d = await getAnalysis(id);
        if (d.status !== "processing") {
          setData(d);
        }
      } catch {}
    }, 5000);
    return () => clearInterval(timer);
  }, [id, data]);

  const player = useVideoPlayer(videoUrl || null, (p) => {
    p.loop = true;
  });

  if (loading) {
    return (
      <SafeAreaView style={[styles.container, styles.center]}>
        <ActivityIndicator color={colors.primary} size="large" />
      </SafeAreaView>
    );
  }

  if (!data) {
    return (
      <SafeAreaView style={[styles.container, styles.center]}>
        <Text style={styles.errorText}>{error || "Not found"}</Text>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Text style={styles.backBtnText}>Go back</Text>
        </TouchableOpacity>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView
      style={styles.container}
      edges={["top"]}
      testID="analysis-detail-screen"
    >
      <ScrollView contentContainerStyle={{ paddingBottom: 64 }}>
        <View style={styles.topBar}>
          <TouchableOpacity
            onPress={() => router.back()}
            testID="back-btn"
            style={styles.iconBtn}
          >
            <Ionicons name="chevron-back" size={22} color={colors.textPrimary} />
          </TouchableOpacity>
          <Text style={styles.topBarLabel}>ANALYSIS</Text>
          <View style={{ width: 32 }} />
        </View>

        {/* Video */}
        <View style={styles.videoWrap}>
          {videoUrl ? (
            <VideoView
              player={player}
              style={styles.video}
              contentFit="cover"
              nativeControls
              testID="analysis-video"
            />
          ) : (
            <View style={[styles.video, styles.center]}>
              <Ionicons name="film-outline" size={42} color={colors.textMuted} />
            </View>
          )}
        </View>

        {/* Title + Score */}
        {data.status === "processing" && (
          <View style={styles.statusBanner} testID="processing-banner">
            <ActivityIndicator size="small" color={colors.primary} />
            <View style={{ flex: 1 }}>
              <Text style={styles.statusTitle}>AI COACH IS ANALYSING…</Text>
              <Text style={styles.statusSub}>
                Usually takes 1–3 minutes. This page updates automatically —
                you can also come back later, your result will be saved.
              </Text>
            </View>
          </View>
        )}

        {data.status === "failed" && (
          <View style={[styles.statusBanner, styles.statusBannerError]} testID="failed-banner">
            <Ionicons name="alert-circle" size={22} color={colors.error} />
            <View style={{ flex: 1 }}>
              <Text style={[styles.statusTitle, { color: colors.error }]}>
                ANALYSIS FAILED
              </Text>
              <Text style={styles.statusSub}>
                Something went wrong while analysing this clip. Your quota was
                NOT used — please upload the clip again. If it keeps failing,
                try a shorter clip (5–60s) or email surfcoach23@gmail.com.
              </Text>
              <TouchableOpacity
                style={styles.retryBtn}
                onPress={() => router.replace("/(tabs)/upload")}
                testID="retry-upload-btn"
              >
                <Text style={styles.retryText}>UPLOAD AGAIN</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}

        <View style={styles.headerBox}>
          <View style={{ flex: 1 }}>
            <Text style={styles.subtitleSmall}>
              {(data.overall_rating || "—").toUpperCase()}
            </Text>
            <Text style={styles.title} numberOfLines={2}>
              {data.status === "failed" ? "Analysis failed" : data.title}
            </Text>
            <Text style={styles.summary}>{data.summary}</Text>
          </View>
          {data.status === "ready" && (
            <View style={styles.scorePill}>
              <Text
                style={[styles.scoreNum, { color: scoreColor(data.score) }]}
                testID="analysis-score"
              >
                {data.score}
              </Text>
              <Text style={styles.scoreLabel}>SCORE</Text>
            </View>
          )}
        </View>

        {/* Strengths */}
        {data.strengths?.length > 0 && (
          <Section title="Strengths" testID="strengths-section">
            {data.strengths.map((s, i) => (
              <BulletRow
                key={i}
                color={colors.success}
                icon="checkmark-circle"
                text={s}
              />
            ))}
          </Section>
        )}

        {/* Mistakes */}
        {data.mistakes?.length > 0 && (
          <Section title="Mistakes Detected" testID="mistakes-section">
            {data.mistakes.map((m, i) => (
              <View
                key={i}
                style={[
                  styles.mistakeCard,
                  { borderLeftColor: severityColor(m.severity) },
                ]}
                testID={`mistake-${i}`}
              >
                <View style={styles.mistakeHead}>
                  <Text style={styles.mistakeTitle}>{m.title}</Text>
                  <View
                    style={[
                      styles.severityBadge,
                      { borderColor: severityColor(m.severity) },
                    ]}
                  >
                    <Text
                      style={[
                        styles.severityText,
                        { color: severityColor(m.severity) },
                      ]}
                    >
                      {(m.severity || "low").toUpperCase()}
                    </Text>
                  </View>
                </View>
                {m.timestamp ? (
                  <Text style={styles.timestamp}>@ {m.timestamp}</Text>
                ) : null}
                <Text style={styles.mistakeDetail}>{m.detail}</Text>
              </View>
            ))}
          </Section>
        )}

        {/* Corrections */}
        {data.corrections?.length > 0 && (
          <Section title="How to Fix" testID="corrections-section">
            {data.corrections.map((c, i) => (
              <BulletRow
                key={i}
                color={colors.primary}
                icon="arrow-forward-circle"
                text={c}
              />
            ))}
          </Section>
        )}

        {/* Tips */}
        {data.tips?.length > 0 && (
          <Section title="Coaching Tips" testID="tips-section">
            {data.tips.map((t, i) => (
              <BulletRow
                key={i}
                color={colors.warning}
                icon="bulb-outline"
                text={t}
              />
            ))}
          </Section>
        )}

        {/* Drills */}
        {data.drills?.length > 0 && (
          <Section title="Practice Drills" testID="drills-section">
            {data.drills.map((d, i) => (
              <BulletRow
                key={i}
                color="#A78BFA"
                icon="fitness-outline"
                text={d}
              />
            ))}
          </Section>
        )}

        <View style={{ paddingHorizontal: spacing.lg, marginTop: spacing.lg, gap: spacing.sm }}>
          {data && me && data.user_id === me.user_id ? (
            <TouchableOpacity
              style={styles.secondaryBtn}
              onPress={() =>
                router.push(`/coaches?share_analysis_id=${data.analysis_id}` as any)
              }
              testID="share-with-coach-btn"
            >
              <Ionicons name="share-social-outline" size={16} color={colors.primary} />
              <Text style={styles.secondaryBtnText}>
                {data.shared_with_coach_id
                  ? "Share with Another Coach"
                  : "Share with a Coach"}
              </Text>
            </TouchableOpacity>
          ) : null}

          <TouchableOpacity
            style={styles.primaryBtn}
            onPress={() => router.replace("/(tabs)/upload")}
            testID="analyse-another-btn"
          >
            <Ionicons name="refresh" size={16} color="#000" />
            <Text style={styles.primaryBtnText}>Analyse Another Clip</Text>
          </TouchableOpacity>
        </View>

        {/* Comments */}
        <View style={styles.section} testID="comments-section">
          <Text style={styles.sectionTitle}>COMMENTS</Text>
          {comments.length === 0 ? (
            <Text style={styles.emptyComments}>
              No comments yet. {me?.tier === "coach" ? "Leave the first one." : "Share with a coach to get feedback."}
            </Text>
          ) : (
            comments.map((c) => (
              <View key={c.comment_id} style={styles.commentRow}>
                {c.author_picture ? (
                  <Image
                    source={{ uri: c.author_picture }}
                    style={styles.commentAvatar}
                  />
                ) : (
                  <View
                    style={[styles.commentAvatar, styles.commentAvatarFallback]}
                  >
                    <Ionicons
                      name="person"
                      size={14}
                      color={colors.textSecondary}
                    />
                  </View>
                )}
                <View style={{ flex: 1 }}>
                  <View style={styles.commentHead}>
                    <Text style={styles.commentName}>{c.author_name}</Text>
                    {c.is_coach && (
                      <View style={styles.coachPill}>
                        <Text style={styles.coachPillText}>COACH</Text>
                      </View>
                    )}
                  </View>
                  <Text style={styles.commentText}>{c.text}</Text>
                </View>
              </View>
            ))
          )}

          {data && me && (data.user_id === me.user_id || data.shared_with_coach_id === me.user_id) ? (
            <View style={styles.commentInputRow}>
              <TextInput
                value={draft}
                onChangeText={setDraft}
                placeholder={
                  me.tier === "coach"
                    ? "Leave coaching feedback..."
                    : "Reply to your coach..."
                }
                placeholderTextColor={colors.textMuted}
                style={styles.commentInput}
                multiline
                maxLength={600}
                testID="comment-input"
              />
              <TouchableOpacity
                style={[styles.commentSend, (!draft.trim() || posting) && { opacity: 0.4 }]}
                disabled={!draft.trim() || posting}
                onPress={async () => {
                  if (!data || !draft.trim()) return;
                  setPosting(true);
                  try {
                    const c = await addComment(data.analysis_id, draft.trim());
                    setComments((prev) => [...prev, c]);
                    setDraft("");
                  } catch {}
                  setPosting(false);
                }}
                testID="comment-send-btn"
              >
                {posting ? (
                  <ActivityIndicator color="#000" />
                ) : (
                  <Ionicons name="send" size={16} color="#000" />
                )}
              </TouchableOpacity>
            </View>
          ) : null}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function Section({
  title,
  children,
  testID,
}: {
  title: string;
  children: React.ReactNode;
  testID?: string;
}) {
  return (
    <View style={styles.section} testID={testID}>
      <Text style={styles.sectionTitle}>{title.toUpperCase()}</Text>
      {children}
    </View>
  );
}

function BulletRow({
  color,
  icon,
  text,
}: {
  color: string;
  icon: any;
  text: string;
}) {
  return (
    <View style={styles.bulletRow}>
      <Ionicons
        name={icon}
        size={18}
        color={color}
        style={{ marginTop: 1, marginRight: 10 }}
      />
      <Text style={styles.bulletText}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { alignItems: "center", justifyContent: "center" },
  topBar: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  topBarLabel: {
    color: colors.textMuted,
    letterSpacing: 3,
    fontSize: 11,
    fontWeight: "800",
  },
  iconBtn: {
    width: 32,
    height: 32,
    alignItems: "center",
    justifyContent: "center",
  },
  videoWrap: {
    height: 240,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: colors.border,
  },
  video: { width: "100%", height: "100%" },
  statusBanner: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
    margin: spacing.lg,
    marginBottom: 0,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.primary,
    borderRadius: 8,
  },
  statusBannerError: {
    borderColor: colors.error,
  },
  statusTitle: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 1,
    marginBottom: 4,
  },
  statusSub: {
    color: colors.textMuted,
    fontSize: 12,
    lineHeight: 18,
  },
  retryBtn: {
    marginTop: 10,
    alignSelf: "flex-start",
    borderWidth: 1,
    borderColor: colors.error,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 4,
    minHeight: 40,
    justifyContent: "center",
  },
  retryText: {
    color: colors.error,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 1,
  },
  headerBox: {
    flexDirection: "row",
    padding: spacing.lg,
    gap: spacing.md,
    alignItems: "center",
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  subtitleSmall: {
    color: colors.primary,
    fontSize: 11,
    letterSpacing: 3,
    fontWeight: "800",
    marginBottom: 4,
  },
  title: {
    color: colors.textPrimary,
    fontSize: 24,
    fontWeight: "900",
    letterSpacing: -1,
    lineHeight: 28,
    marginBottom: 6,
  },
  summary: {
    color: colors.textSecondary,
    fontSize: 13,
    lineHeight: 19,
  },
  scorePill: {
    minWidth: 90,
    alignItems: "center",
    justifyContent: "center",
    borderLeftWidth: 1,
    borderLeftColor: colors.border,
    paddingLeft: spacing.md,
  },
  scoreNum: { fontSize: 48, fontWeight: "900", letterSpacing: -2 },
  scoreLabel: {
    color: colors.textMuted,
    fontSize: 9,
    letterSpacing: 2,
    fontWeight: "800",
  },
  section: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
  },
  sectionTitle: {
    color: colors.textMuted,
    fontSize: 11,
    letterSpacing: 2.5,
    fontWeight: "800",
    marginBottom: spacing.sm,
  },
  bulletRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  bulletText: {
    color: colors.textPrimary,
    flex: 1,
    fontSize: 14,
    lineHeight: 20,
  },
  mistakeCard: {
    backgroundColor: colors.surface,
    borderLeftWidth: 3,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    marginBottom: spacing.sm,
    borderTopWidth: 1,
    borderRightWidth: 1,
    borderBottomWidth: 1,
    borderTopColor: colors.border,
    borderRightColor: colors.border,
    borderBottomColor: colors.border,
  },
  mistakeHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 4,
  },
  mistakeTitle: {
    color: colors.textPrimary,
    fontSize: 15,
    fontWeight: "800",
    flex: 1,
    paddingRight: 8,
  },
  severityBadge: {
    borderWidth: 1,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  severityText: { fontSize: 9, letterSpacing: 1.5, fontWeight: "800" },
  timestamp: {
    color: colors.primary,
    fontSize: 11,
    letterSpacing: 1.5,
    fontWeight: "700",
    marginBottom: 4,
  },
  mistakeDetail: {
    color: colors.textSecondary,
    fontSize: 13,
    lineHeight: 19,
  },
  primaryBtn: {
    backgroundColor: colors.primary,
    paddingVertical: 14,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  primaryBtnText: {
    color: "#000",
    fontSize: 14,
    fontWeight: "800",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  secondaryBtn: {
    borderWidth: 1,
    borderColor: colors.primary,
    paddingVertical: 14,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  secondaryBtnText: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  emptyComments: {
    color: colors.textMuted,
    fontSize: 13,
    paddingVertical: spacing.sm,
  },
  commentRow: {
    flexDirection: "row",
    gap: spacing.sm,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  commentAvatar: { width: 32, height: 32, borderRadius: 4 },
  commentAvatarFallback: {
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  commentHead: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: 2,
  },
  commentName: {
    color: colors.textPrimary,
    fontSize: 13,
    fontWeight: "800",
  },
  coachPill: {
    backgroundColor: colors.primary,
    paddingHorizontal: 5,
    paddingVertical: 1,
  },
  coachPillText: {
    color: "#000",
    fontSize: 8,
    fontWeight: "900",
    letterSpacing: 1,
  },
  commentText: {
    color: colors.textPrimary,
    fontSize: 13,
    lineHeight: 18,
  },
  commentInputRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  commentInput: {
    flex: 1,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    color: colors.textPrimary,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    fontSize: 13,
    minHeight: 44,
    maxHeight: 120,
  },
  commentSend: {
    backgroundColor: colors.primary,
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  errorText: {
    color: colors.error,
    fontSize: 14,
    marginBottom: spacing.md,
  },
  backBtn: {
    paddingVertical: 10,
    paddingHorizontal: 24,
    borderWidth: 1,
    borderColor: colors.border,
  },
  backBtnText: { color: colors.textPrimary },
});
