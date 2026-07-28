import React, { useEffect, useState } from "react";
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
import { useEvent } from "expo";
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
import {
  colors,
  radii,
  scoreColor,
  severityColor,
  spacing,
  SCORE_CATEGORIES,
} from "../../src/theme";
import { useI18n } from "../../src/i18n";
import { haptic } from "../../src/haptics";
import ScoreRing from "../../src/components/ScoreRing";
import GlassCard from "../../src/components/GlassCard";

const SPEEDS = [1, 0.5, 0.25];

function tsToSeconds(ts: string): number | null {
  const m = /^(\d{1,2}):(\d{2})$/.exec((ts || "").trim());
  if (!m) return null;
  return parseInt(m[1], 10) * 60 + parseInt(m[2], 10);
}

export default function AnalysisDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { t } = useI18n();
  const [data, setData] = useState<Analysis | null>(null);
  const [me, setMe] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [comments, setComments] = useState<AnalysisComment[]>([]);
  const [draft, setDraft] = useState("");
  const [posting, setPosting] = useState(false);
  const [speedIdx, setSpeedIdx] = useState(0);

  useEffect(() => {
    (async () => {
      try {
        if (!id) return;
        const [d, tok, u] = await Promise.all([
          getAnalysis(id),
          getToken(),
          fetchMe(),
        ]);
        setData(d);
        setMe(u);
        if (tok) setVideoUrl(getVideoStreamUrl(d.analysis_id, tok));
        try {
          setComments(await listComments(id));
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
        if (d.status !== "processing") setData(d);
      } catch {}
    }, 5000);
    return () => clearInterval(timer);
  }, [id, data]);

  const player = useVideoPlayer(videoUrl || null, (p) => {
    p.loop = true;
  });
  const { isPlaying } = useEvent(player, "playingChange", {
    isPlaying: player.playing,
  });

  const togglePlay = () => {
    haptic.tap();
    try {
      if (player.playing) player.pause();
      else player.play();
    } catch {}
  };

  const cycleSpeed = () => {
    haptic.medium();
    const next = (speedIdx + 1) % SPEEDS.length;
    setSpeedIdx(next);
    try {
      player.playbackRate = SPEEDS[next];
    } catch {}
  };

  const stepFrame = (dir: 1 | -1) => {
    haptic.tap();
    try {
      player.pause();
      player.seekBy(dir * (1 / 30));
    } catch {}
  };

  const jumpTo = (ts: string) => {
    const sec = tsToSeconds(ts);
    if (sec === null) return;
    haptic.light();
    try {
      player.currentTime = sec;
      player.play();
    } catch {}
  };

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
          <Text style={styles.backBtnText}>←</Text>
        </TouchableOpacity>
      </SafeAreaView>
    );
  }

  const orderedScores = (data.scores || [])
    .slice()
    .sort(
      (a, b) =>
        (SCORE_CATEGORIES as readonly string[]).indexOf(a.key) -
        (SCORE_CATEGORIES as readonly string[]).indexOf(b.key)
    );
  const mm = data.main_mistake;
  const isOwner = me && data.user_id === me.user_id;

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
          <Text style={styles.topBarLabel}>{t("analysis").toUpperCase()}</Text>
          <View style={{ width: 32 }} />
        </View>

        {/* Video + custom replay controls */}
        <View style={styles.videoWrap}>
          {videoUrl ? (
            <VideoView
              player={player}
              style={styles.video}
              contentFit="cover"
              nativeControls={false}
              testID="analysis-video"
            />
          ) : (
            <View style={[styles.video, styles.center]}>
              <Ionicons name="film-outline" size={42} color={colors.textMuted} />
            </View>
          )}
          {videoUrl && (
            <View style={styles.controlsBar}>
              <TouchableOpacity
                style={styles.ctrlBtn}
                onPress={() => stepFrame(-1)}
                testID="frame-back-btn"
              >
                <Ionicons name="play-skip-back" size={16} color={colors.textPrimary} />
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.ctrlBtn, styles.playBtn]}
                onPress={togglePlay}
                testID="play-pause-btn"
              >
                <Ionicons
                  name={isPlaying ? "pause" : "play"}
                  size={20}
                  color="#000"
                />
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.ctrlBtn}
                onPress={() => stepFrame(1)}
                testID="frame-fwd-btn"
              >
                <Ionicons name="play-skip-forward" size={16} color={colors.textPrimary} />
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.speedBtn, speedIdx > 0 && styles.speedBtnActive]}
                onPress={cycleSpeed}
                testID="speed-btn"
              >
                <Text
                  style={[
                    styles.speedText,
                    speedIdx > 0 && { color: "#000" },
                  ]}
                >
                  {SPEEDS[speedIdx]}x
                </Text>
              </TouchableOpacity>
            </View>
          )}
        </View>

        {/* Key moments — clickable, jump the video */}
        {data.status === "ready" && (data.key_moments?.length || 0) > 0 && (
          <View testID="key-moments-section">
            <Text style={[styles.sectionTitle, { paddingHorizontal: spacing.lg }]}>
              {t("key_moments").toUpperCase()}
            </Text>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={{
                paddingHorizontal: spacing.lg,
                gap: 8,
                paddingBottom: spacing.md,
              }}
            >
              {data.key_moments!.map((km, i) => {
                const c =
                  km.type === "good"
                    ? colors.success
                    : km.type === "bad"
                    ? colors.error
                    : colors.primary;
                return (
                  <TouchableOpacity
                    key={i}
                    style={[styles.momentChip, { borderColor: `${c}55` }]}
                    onPress={() => jumpTo(km.timestamp)}
                    testID={`key-moment-${i}`}
                  >
                    <Text style={[styles.momentTime, { color: c }]}>
                      {km.timestamp}
                    </Text>
                    <Text style={styles.momentLabel} numberOfLines={1}>
                      {km.label}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
          </View>
        )}

        {/* Status banners */}
        {data.status === "processing" && (
          <View style={styles.statusBanner} testID="processing-banner">
            <ActivityIndicator size="small" color={colors.primary} />
            <View style={{ flex: 1 }}>
              <Text style={styles.statusTitle}>
                {t("analysing_title").toUpperCase()}
              </Text>
              <Text style={styles.statusSub}>{t("analysing_sub")}</Text>
            </View>
          </View>
        )}

        {data.status === "failed" && (
          <View
            style={[styles.statusBanner, styles.statusBannerError]}
            testID="failed-banner"
          >
            <Ionicons name="alert-circle" size={22} color={colors.error} />
            <View style={{ flex: 1 }}>
              <Text style={[styles.statusTitle, { color: colors.error }]}>
                {t("failed_title").toUpperCase()}
              </Text>
              <Text style={styles.statusSub}>{t("failed_sub")}</Text>
              <TouchableOpacity
                style={styles.retryBtn}
                onPress={() => router.replace("/(tabs)/upload")}
                testID="retry-upload-btn"
              >
                <Text style={styles.retryText}>
                  {t("upload_again").toUpperCase()}
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        )}

        {/* Overall score hero */}
        <View style={styles.headerBox}>
          <View style={{ flex: 1 }}>
            <Text style={styles.subtitleSmall}>
              {(data.overall_rating || "—").toUpperCase()}
            </Text>
            <Text style={styles.title} numberOfLines={2}>
              {data.status === "failed" ? t("failed_title") : data.title}
            </Text>
            <Text style={styles.summary}>{data.summary}</Text>
          </View>
          {data.status === "ready" && (
            <View testID="analysis-score">
              <ScoreRing value={data.score} size={96} thickness={8} valueSize={30} />
              <Text style={styles.overallLabel}>{t("overall_score")}</Text>
            </View>
          )}
        </View>

        {/* Sub-scores grid */}
        {data.status === "ready" && orderedScores.length > 0 && (
          <View style={styles.section} testID="scores-grid">
            <Text style={styles.sectionTitle}>
              {t("your_results").toUpperCase()}
            </Text>
            <View style={styles.scoreGrid}>
              {orderedScores.map((s) => (
                <GlassCard key={s.key} style={styles.scoreCard}>
                  <ScoreRing value={s.value} size={52} thickness={5} valueSize={15} />
                  <Text style={styles.scoreName} numberOfLines={1}>
                    {t(`score_${s.key}`)}
                  </Text>
                  {s.note ? (
                    <Text style={styles.scoreNote} numberOfLines={2}>
                      {s.note}
                    </Text>
                  ) : null}
                </GlassCard>
              ))}
            </View>
          </View>
        )}

        {/* Strengths */}
        {data.strengths?.length > 0 && (
          <View style={styles.section} testID="strengths-section">
            <GlassCard accent={colors.success}>
              <View style={styles.cardHead}>
                <Ionicons name="checkmark-circle" size={16} color={colors.success} />
                <Text style={[styles.cardHeadText, { color: colors.success }]}>
                  {t("what_you_did_well").toUpperCase()}
                </Text>
              </View>
              {data.strengths.map((s, i) => (
                <View key={i} style={styles.bulletRow}>
                  <View style={[styles.bulletDot, { backgroundColor: colors.success }]} />
                  <Text style={styles.bulletText}>{s}</Text>
                </View>
              ))}
            </GlassCard>
          </View>
        )}

        {/* Main mistake */}
        {data.status === "ready" && mm?.title ? (
          <View style={styles.section} testID="main-mistake-section">
            <GlassCard accent={colors.error} style={styles.mainMistakeCard}>
              <View style={styles.cardHead}>
                <Ionicons name="warning" size={16} color={colors.error} />
                <Text style={[styles.cardHeadText, { color: colors.error }]}>
                  {t("main_mistake").toUpperCase()}
                </Text>
                {mm.timestamp ? (
                  <TouchableOpacity
                    style={styles.mmTs}
                    onPress={() => jumpTo(mm.timestamp!)}
                  >
                    <Ionicons name="play" size={10} color={colors.error} />
                    <Text style={styles.mmTsText}>{mm.timestamp}</Text>
                  </TouchableOpacity>
                ) : null}
              </View>
              <Text style={styles.mmTitle}>{mm.title}</Text>
              {mm.why ? (
                <MistakeBlock label={t("why_it_matters")} text={mm.why} />
              ) : null}
              {mm.cause ? (
                <MistakeBlock label={t("what_caused_it")} text={mm.cause} />
              ) : null}
              {mm.performance_lost ? (
                <MistakeBlock label={t("performance_lost")} text={mm.performance_lost} />
              ) : null}
              {mm.fix ? (
                <MistakeBlock
                  label={t("how_to_fix")}
                  text={mm.fix}
                  color={colors.success}
                />
              ) : null}
            </GlassCard>
          </View>
        ) : null}

        {/* Top 5 corrections */}
        {data.corrections?.length > 0 && (
          <View style={styles.section} testID="corrections-section">
            <Text style={styles.sectionTitle}>
              {t("top_corrections").toUpperCase()}
            </Text>
            {data.corrections.slice(0, 5).map((c, i) => (
              <View key={i} style={styles.correctionRow}>
                <View style={styles.correctionNum}>
                  <Text style={styles.correctionNumText}>{i + 1}</Text>
                </View>
                <Text style={styles.correctionText}>{c}</Text>
              </View>
            ))}
          </View>
        )}

        {/* Other mistakes */}
        {data.mistakes?.length > 0 && (
          <View style={styles.section} testID="mistakes-section">
            <Text style={styles.sectionTitle}>
              {t("mistakes_detected").toUpperCase()}
            </Text>
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
                  <TouchableOpacity onPress={() => jumpTo(m.timestamp!)}>
                    <Text style={styles.timestamp}>▶ {m.timestamp}</Text>
                  </TouchableOpacity>
                ) : null}
                <Text style={styles.mistakeDetail}>{m.detail}</Text>
              </View>
            ))}
          </View>
        )}

        {/* Tips */}
        {data.tips?.length > 0 && (
          <View style={styles.section} testID="tips-section">
            <Text style={styles.sectionTitle}>
              {t("coaching_tips").toUpperCase()}
            </Text>
            {data.tips.map((tip, i) => (
              <View key={i} style={styles.bulletRow}>
                <Ionicons
                  name="bulb-outline"
                  size={16}
                  color={colors.warning}
                  style={{ marginTop: 2, marginRight: 10 }}
                />
                <Text style={styles.bulletText}>{tip}</Text>
              </View>
            ))}
          </View>
        )}

        {/* Drills */}
        {data.drills?.length > 0 && (
          <View style={styles.section} testID="drills-section">
            <Text style={styles.sectionTitle}>
              {t("practice_drills").toUpperCase()}
            </Text>
            {data.drills.map((d, i) => (
              <View key={i} style={styles.bulletRow}>
                <Ionicons
                  name="fitness-outline"
                  size={16}
                  color="#A78BFA"
                  style={{ marginTop: 2, marginRight: 10 }}
                />
                <Text style={styles.bulletText}>{d}</Text>
              </View>
            ))}
          </View>
        )}

        <View
          style={{
            paddingHorizontal: spacing.lg,
            marginTop: spacing.lg,
            gap: spacing.sm,
          }}
        >
          {isOwner ? (
            <TouchableOpacity
              style={styles.secondaryBtn}
              onPress={() =>
                router.push(`/coaches?share_analysis_id=${data.analysis_id}` as any)
              }
              testID="share-with-coach-btn"
            >
              <Ionicons
                name="share-social-outline"
                size={16}
                color={colors.primary}
              />
              <Text style={styles.secondaryBtnText}>
                {data.shared_with_coach_id
                  ? t("share_with_another")
                  : t("share_with_coach")}
              </Text>
            </TouchableOpacity>
          ) : null}

          <TouchableOpacity
            style={styles.primaryBtn}
            onPress={() => router.replace("/(tabs)/upload")}
            testID="analyse-another-btn"
          >
            <Ionicons name="refresh" size={16} color="#000" />
            <Text style={styles.primaryBtnText}>{t("analyse_another")}</Text>
          </TouchableOpacity>
        </View>

        {/* Comments */}
        <View style={styles.section} testID="comments-section">
          <Text style={styles.sectionTitle}>{t("comments").toUpperCase()}</Text>
          {comments.length === 0 ? (
            <Text style={styles.emptyComments}>{t("no_comments")}</Text>
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
                    <Ionicons name="person" size={14} color={colors.textSecondary} />
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

          {data &&
          me &&
          (data.user_id === me.user_id ||
            data.shared_with_coach_id === me.user_id) ? (
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
                style={[
                  styles.commentSend,
                  (!draft.trim() || posting) && { opacity: 0.4 },
                ]}
                disabled={!draft.trim() || posting}
                onPress={async () => {
                  if (!data || !draft.trim()) return;
                  setPosting(true);
                  try {
                    const c = await addComment(data.analysis_id, draft.trim());
                    setComments((prev) => [...prev, c]);
                    setDraft("");
                    haptic.success();
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

function MistakeBlock({
  label,
  text,
  color,
}: {
  label: string;
  text: string;
  color?: string;
}) {
  return (
    <View style={{ marginTop: 10 }}>
      <Text style={[styles.mmBlockLabel, color ? { color } : null]}>
        {label.toUpperCase()}
      </Text>
      <Text style={styles.mmBlockText}>{text}</Text>
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
  errorText: { color: colors.error, marginBottom: 12 },
  backBtn: {
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: radii.md,
  },
  backBtnText: { color: colors.textPrimary, fontSize: 16 },
  videoWrap: {
    marginHorizontal: spacing.lg,
    borderRadius: radii.lg,
    overflow: "hidden",
    backgroundColor: colors.surface,
    marginBottom: spacing.md,
  },
  video: { width: "100%", height: 230 },
  controlsBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 14,
    paddingVertical: 10,
    backgroundColor: "rgba(255,255,255,0.04)",
    borderTopWidth: 1,
    borderTopColor: colors.glassBorder,
  },
  ctrlBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255,255,255,0.08)",
  },
  playBtn: { backgroundColor: colors.primary, width: 46, height: 46, borderRadius: 23 },
  speedBtn: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    paddingHorizontal: 12,
    paddingVertical: 8,
    minWidth: 52,
    alignItems: "center",
  },
  speedBtnActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  speedText: { color: colors.textPrimary, fontSize: 12, fontWeight: "800" },
  momentChip: {
    borderWidth: 1,
    borderRadius: radii.md,
    backgroundColor: colors.glass,
    paddingHorizontal: 12,
    paddingVertical: 8,
    maxWidth: 170,
  },
  momentTime: { fontSize: 11, fontWeight: "900", letterSpacing: 0.5 },
  momentLabel: { color: colors.textSecondary, fontSize: 11, marginTop: 2 },
  statusBanner: {
    flexDirection: "row",
    gap: 12,
    alignItems: "flex-start",
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    padding: spacing.md,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: `${colors.primary}44`,
    backgroundColor: "rgba(0,229,255,0.05)",
  },
  statusBannerError: {
    borderColor: `${colors.error}55`,
    backgroundColor: "rgba(255,51,102,0.06)",
  },
  statusTitle: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 1.5,
    marginBottom: 4,
  },
  statusSub: { color: colors.textSecondary, fontSize: 12, lineHeight: 17 },
  retryBtn: {
    marginTop: 10,
    alignSelf: "flex-start",
    backgroundColor: colors.error,
    borderRadius: radii.sm,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  retryText: { color: "#fff", fontSize: 11, fontWeight: "800", letterSpacing: 1 },
  headerBox: {
    flexDirection: "row",
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
    alignItems: "center",
  },
  subtitleSmall: {
    color: colors.primary,
    fontSize: 10,
    letterSpacing: 3,
    fontWeight: "800",
    marginBottom: 4,
  },
  title: {
    color: colors.textPrimary,
    fontSize: 24,
    fontWeight: "900",
    letterSpacing: -0.5,
    marginBottom: 6,
  },
  summary: { color: colors.textSecondary, fontSize: 13, lineHeight: 19 },
  overallLabel: {
    color: colors.textMuted,
    fontSize: 8,
    letterSpacing: 1,
    textAlign: "center",
    marginTop: 4,
    textTransform: "uppercase",
  },
  section: {
    paddingHorizontal: spacing.lg,
    marginTop: spacing.md,
  },
  sectionTitle: {
    color: colors.textMuted,
    fontSize: 11,
    letterSpacing: 2.5,
    fontWeight: "800",
    marginBottom: spacing.sm,
  },
  scoreGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  scoreCard: {
    width: "31.5%",
    alignItems: "center",
    paddingVertical: 12,
    paddingHorizontal: 6,
  },
  scoreName: {
    color: colors.textPrimary,
    fontSize: 10,
    fontWeight: "800",
    marginTop: 8,
    textAlign: "center",
  },
  scoreNote: {
    color: colors.textMuted,
    fontSize: 9,
    lineHeight: 12,
    marginTop: 3,
    textAlign: "center",
  },
  cardHead: { flexDirection: "row", alignItems: "center", gap: 7, marginBottom: 10 },
  cardHeadText: { fontSize: 11, letterSpacing: 2, fontWeight: "800", flex: 1 },
  bulletRow: { flexDirection: "row", alignItems: "flex-start", marginBottom: 9 },
  bulletDot: {
    width: 5,
    height: 5,
    borderRadius: 3,
    marginTop: 7,
    marginRight: 10,
  },
  bulletText: { flex: 1, color: colors.textSecondary, fontSize: 13, lineHeight: 19 },
  mainMistakeCard: { backgroundColor: "rgba(255,51,102,0.05)" },
  mmTs: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    borderWidth: 1,
    borderColor: `${colors.error}55`,
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  mmTsText: { color: colors.error, fontSize: 10, fontWeight: "800" },
  mmTitle: {
    color: colors.textPrimary,
    fontSize: 17,
    fontWeight: "800",
    letterSpacing: -0.3,
  },
  mmBlockLabel: {
    color: colors.textMuted,
    fontSize: 9,
    letterSpacing: 2,
    fontWeight: "800",
    marginBottom: 3,
  },
  mmBlockText: { color: colors.textSecondary, fontSize: 13, lineHeight: 19 },
  correctionRow: {
    flexDirection: "row",
    gap: 12,
    alignItems: "flex-start",
    backgroundColor: colors.glass,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    borderRadius: radii.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  correctionNum: {
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  correctionNumText: { color: "#000", fontSize: 13, fontWeight: "900" },
  correctionText: { flex: 1, color: colors.textPrimary, fontSize: 13, lineHeight: 19 },
  mistakeCard: {
    backgroundColor: colors.glass,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    borderLeftWidth: 3,
    borderRadius: radii.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  mistakeHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
  },
  mistakeTitle: {
    flex: 1,
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: "800",
  },
  severityBadge: {
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  severityText: { fontSize: 9, fontWeight: "800", letterSpacing: 1 },
  timestamp: {
    color: colors.primary,
    fontSize: 11,
    fontWeight: "800",
    marginTop: 6,
  },
  mistakeDetail: {
    color: colors.textSecondary,
    fontSize: 12,
    lineHeight: 18,
    marginTop: 6,
  },
  secondaryBtn: {
    borderWidth: 1,
    borderColor: `${colors.primary}66`,
    borderRadius: radii.md,
    paddingVertical: 13,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  secondaryBtnText: { color: colors.primary, fontSize: 13, fontWeight: "800" },
  primaryBtn: {
    backgroundColor: colors.primary,
    borderRadius: radii.md,
    paddingVertical: 14,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  primaryBtnText: {
    color: "#000",
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 0.5,
  },
  emptyComments: { color: colors.textMuted, fontSize: 12, lineHeight: 18 },
  commentRow: { flexDirection: "row", gap: 10, marginBottom: spacing.md },
  commentAvatar: { width: 30, height: 30, borderRadius: 15 },
  commentAvatarFallback: {
    backgroundColor: colors.surfaceElevated,
    alignItems: "center",
    justifyContent: "center",
  },
  commentHead: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 2 },
  commentName: { color: colors.textPrimary, fontSize: 12, fontWeight: "800" },
  coachPill: {
    backgroundColor: colors.primary,
    borderRadius: 999,
    paddingHorizontal: 6,
    paddingVertical: 1,
  },
  coachPillText: { color: "#000", fontSize: 8, fontWeight: "900", letterSpacing: 1 },
  commentText: { color: colors.textSecondary, fontSize: 13, lineHeight: 18 },
  commentInputRow: {
    flexDirection: "row",
    gap: 8,
    alignItems: "flex-end",
    marginTop: spacing.sm,
  },
  commentInput: {
    flex: 1,
    minHeight: 42,
    maxHeight: 110,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    color: colors.textPrimary,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 13,
    backgroundColor: colors.glass,
  },
  commentSend: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
});
