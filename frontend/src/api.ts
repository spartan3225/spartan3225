import AsyncStorage from "@react-native-async-storage/async-storage";
import { Platform } from "react-native";
import * as FileSystem from "expo-file-system/legacy";

// On web, always call the API on the same domain the site is served from
// (works on preview AND on the deployed .emergent.host domain).
// On native (iOS/Android), use the configured backend URL.
const BACKEND_URL =
  Platform.OS === "web" && typeof window !== "undefined"
    ? window.location.origin
    : process.env.EXPO_PUBLIC_BACKEND_URL;
export const API_URL = `${BACKEND_URL}/api`;

const TOKEN_KEY = "session_token";

export async function getToken(): Promise<string | null> {
  try {
    return await AsyncStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export async function setToken(token: string): Promise<void> {
  await AsyncStorage.setItem(TOKEN_KEY, token);
}

export async function clearToken(): Promise<void> {
  await AsyncStorage.removeItem(TOKEN_KEY);
}

export async function apiFetch<T = any>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = await getToken();
  const headers: Record<string, string> = {
    ...((options.headers as Record<string, string>) || {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (
    options.body &&
    !(options.body instanceof FormData) &&
    !headers["Content-Type"]
  ) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
  }
  if (res.status === 204) return undefined as unknown as T;
  return (await res.json()) as T;
}

export type User = {
  user_id: string;
  email: string;
  name: string;
  picture?: string | null;
  created_at: string;
  tier?: "free" | "coach" | string;
  subscription_status?: string | null;
  subscription_expires_at?: string | null;
  coach_bio?: string | null;
  coach_specialty?: string | null;
  coach_location?: string | null;
  coach_public?: boolean;
  preferred_language?: string;
  multi_credits?: number;
};

export type AnalysisListItem = {
  analysis_id: string;
  title: string;
  score: number;
  overall_rating: string;
  summary: string;
  status: string;
  created_at: string;
};

export type Mistake = {
  title: string;
  detail: string;
  severity: "low" | "medium" | "high" | string;
  timestamp?: string | null;
};

export type ScoreItem = { key: string; value: number; note?: string };
export type MainMistake = {
  title?: string;
  why?: string;
  cause?: string;
  performance_lost?: string;
  fix?: string;
  timestamp?: string | null;
};
export type KeyMoment = {
  timestamp: string;
  label: string;
  type: "good" | "bad" | "neutral" | string;
};

export type Analysis = {
  analysis_id: string;
  user_id: string;
  title: string;
  score: number;
  overall_rating: string;
  summary: string;
  strengths: string[];
  mistakes: Mistake[];
  corrections: string[];
  tips: string[];
  drills: string[];
  scores?: ScoreItem[] | null;
  main_mistake?: MainMistake | null;
  key_moments?: KeyMoment[] | null;
  duration_seconds?: number | null;
  status: string;
  created_at: string;
  shared_with_coach_id?: string | null;
};

export async function exchangeSessionId(sessionId: string) {
  const res = await fetch(`${API_URL}/auth/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (!res.ok) throw new Error(`Auth failed: ${res.status}`);
  const data = await res.json();
  await setToken(data.session_token);
  return data.user as User;
}

async function authPost(path: string, body: object): Promise<User> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `Error ${res.status}`;
    try {
      detail = (await res.json()).detail || detail;
    } catch {}
    throw new Error(detail);
  }
  const data = await res.json();
  await setToken(data.session_token);
  return data.user as User;
}

export async function emailRegister(email: string, password: string, name?: string) {
  return authPost("/auth/register", { email, password, name });
}

export async function emailLogin(email: string, password: string) {
  return authPost("/auth/login", { email, password });
}

export async function appleLogin(
  identityToken: string,
  name?: string | null,
  email?: string | null
) {
  return authPost("/auth/apple", {
    identity_token: identityToken,
    name: name || undefined,
    email: email || undefined,
  });
}

export async function fetchMe(): Promise<User | null> {
  try {
    return await apiFetch<User>("/auth/me");
  } catch {
    return null;
  }
}

export async function listAnalyses(): Promise<AnalysisListItem[]> {
  return apiFetch<AnalysisListItem[]>("/analyses");
}

export async function getAnalysis(id: string): Promise<Analysis> {
  return apiFetch<Analysis>(`/analyses/${id}`);
}

export async function logout(): Promise<void> {
  // Clear the local token FIRST so the user is logged out even if the
  // network call fails or the device is offline.
  const token = await getToken();
  await clearToken();
  if (token) {
    try {
      await fetch(`${API_URL}/auth/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch {
      // ignore
    }
  }
}

const CHUNK_SIZE = 3 * 1024 * 1024; // 3MB — safely under proxy body limits

function makeUploadId(): string {
  return (
    Date.now().toString(16) +
    Math.random().toString(16).slice(2) +
    Math.random().toString(16).slice(2)
  ).slice(0, 32);
}

async function postFormWithRetry(
  url: string,
  buildForm: () => FormData,
  headers: Record<string, string>,
  attempts = 3
): Promise<Response> {
  let lastErr: any = null;
  for (let i = 0; i < attempts; i++) {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers,
        body: buildForm() as any,
      });
      if (res.ok) return res;
      // Don't retry on client errors (auth/quota/etc.)
      if (res.status < 500 && res.status !== 429) return res;
      lastErr = new Error(`HTTP ${res.status}`);
    } catch (e) {
      lastErr = e;
    }
    await new Promise((r) => setTimeout(r, 1000 * (i + 1)));
  }
  throw lastErr || new Error("Chunk upload failed");
}

async function finalizeChunkedUpload(
  uploadId: string,
  name: string,
  mimeType: string,
  totalChunks: number,
  token: string | null
): Promise<Analysis> {
  let lastErr: any = null;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const res = await fetch(`${API_URL}/analyses/finalize`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          upload_id: uploadId,
          filename: name,
          mime_type: mimeType,
          total_chunks: totalChunks,
        }),
      });
      if (res.ok) return (await res.json()) as Analysis;
      const text = await res.text().catch(() => "");
      // Don't retry client errors (quota/auth/bad-request) — surface them.
      if (res.status < 500 && res.status !== 429) {
        throw new Error(`Upload failed: ${res.status} ${text}`);
      }
      lastErr = new Error(`Upload failed: ${res.status} ${text}`);
    } catch (e) {
      lastErr = e;
    }
    await new Promise((r) => setTimeout(r, 1000 * (attempt + 1)));
  }
  throw lastErr || new Error("Upload failed");
}

export async function uploadVideo(
  uri: string,
  name: string,
  mimeType: string,
  onProgress?: (pct: number) => void
) {
  const token = await getToken();
  const authHeaders: Record<string, string> = token
    ? { Authorization: `Bearer ${token}` }
    : {};

  if (Platform.OS === "web") {
    // On web, FormData needs a real File/Blob. Fetch the picked URI and convert.
    let blob: Blob;
    try {
      const blobRes = await fetch(uri);
      blob = await blobRes.blob();
    } catch (e) {
      throw new Error(
        `Could not read selected video on web. Please try again or use the mobile app. (${
          (e as Error).message
        })`
      );
    }
    const finalType = blob.type || mimeType || "video/mp4";

    // Small clip: single request (fast path)
    if (blob.size <= CHUNK_SIZE) {
      const fileObj =
        typeof File !== "undefined"
          ? new File([blob], name, { type: finalType })
          : blob;
      onProgress?.(10);
      const res = await postFormWithRetry(
        `${API_URL}/analyses`,
        () => {
          const form = new FormData();
          form.append("file", fileObj as any, name);
          return form;
        },
        authHeaders
      );
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(`Upload failed: ${res.status} ${text}`);
      }
      onProgress?.(100);
      return (await res.json()) as Analysis;
    }

    // Big clip: upload in chunks to bypass proxy limits
    const uploadId = makeUploadId();
    const total = Math.ceil(blob.size / CHUNK_SIZE);
    for (let i = 0; i < total; i++) {
      const part = blob.slice(
        i * CHUNK_SIZE,
        Math.min((i + 1) * CHUNK_SIZE, blob.size),
        finalType
      );
      const res = await postFormWithRetry(
        `${API_URL}/uploads/chunk`,
        () => {
          const form = new FormData();
          form.append("upload_id", uploadId);
          form.append("chunk_index", String(i));
          form.append("total_chunks", String(total));
          form.append("file", part as any, `${name}.part${i}`);
          return form;
        },
        authHeaders
      );
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(`Upload failed: ${res.status} ${text}`);
      }
      onProgress?.(Math.round(((i + 1) / total) * 95));
    }
    const result = await finalizeChunkedUpload(
      uploadId,
      name,
      finalType,
      total,
      token
    );
    onProgress?.(100);
    return result;
  }

  // ---- Native (iOS/Android) ----
  let size = 0;
  try {
    const info = await FileSystem.getInfoAsync(uri, { size: true } as any);
    size = (info as any)?.size || 0;
  } catch {
    size = 0;
  }

  // Small clip (or unknown size): single multipart request
  if (!size || size <= CHUNK_SIZE) {
    onProgress?.(10);
    const res = await postFormWithRetry(
      `${API_URL}/analyses`,
      () => {
        const form = new FormData();
        // @ts-ignore - React Native FormData accepts this shape natively
        form.append("file", { uri, name, type: mimeType });
        return form;
      },
      authHeaders
    );
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`Upload failed: ${res.status} ${text}`);
    }
    onProgress?.(100);
    return (await res.json()) as Analysis;
  }

  // Big clip: read base64 chunks from disk and upload sequentially
  const uploadId = makeUploadId();
  const total = Math.ceil(size / CHUNK_SIZE);
  for (let i = 0; i < total; i++) {
    const b64 = await FileSystem.readAsStringAsync(uri, {
      encoding: FileSystem.EncodingType.Base64,
      position: i * CHUNK_SIZE,
      length: Math.min(CHUNK_SIZE, size - i * CHUNK_SIZE),
    });
    const res = await postFormWithRetry(
      `${API_URL}/uploads/chunk`,
      () => {
        const form = new FormData();
        form.append("upload_id", uploadId);
        form.append("chunk_index", String(i));
        form.append("total_chunks", String(total));
        form.append("chunk_b64", b64);
        return form;
      },
      authHeaders
    );
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`Upload failed: ${res.status} ${text}`);
    }
    onProgress?.(Math.round(((i + 1) / total) * 95));
  }
  const result = await finalizeChunkedUpload(
    uploadId,
    name,
    mimeType || "video/mp4",
    total,
    token
  );
  onProgress?.(100);
  return result;
}

export function getVideoStreamUrl(analysisId: string, token: string) {
  return `${API_URL}/analyses/${analysisId}/video?token=${encodeURIComponent(
    token
  )}`;
}

// ---- Multi-video (paid add-on) ----
export type ChunkedUploadRef = {
  upload_id: string;
  filename: string;
  mime_type: string;
  total_chunks: number;
};

/** Chunk-upload a single file WITHOUT finalizing (used by multi-video mode). */
export async function uploadChunksForFile(
  uri: string,
  name: string,
  mimeType: string,
  onProgress?: (pct: number) => void
): Promise<ChunkedUploadRef> {
  const token = await getToken();
  const authHeaders: Record<string, string> = token
    ? { Authorization: `Bearer ${token}` }
    : {};
  const uploadId = makeUploadId();

  if (Platform.OS === "web") {
    const blobRes = await fetch(uri);
    const blob = await blobRes.blob();
    const finalType = blob.type || mimeType || "video/mp4";
    const total = Math.max(1, Math.ceil(blob.size / CHUNK_SIZE));
    for (let i = 0; i < total; i++) {
      const part = blob.slice(
        i * CHUNK_SIZE,
        Math.min((i + 1) * CHUNK_SIZE, blob.size),
        finalType
      );
      const res = await postFormWithRetry(
        `${API_URL}/uploads/chunk`,
        () => {
          const form = new FormData();
          form.append("upload_id", uploadId);
          form.append("chunk_index", String(i));
          form.append("total_chunks", String(total));
          form.append("file", part as any, `${name}.part${i}`);
          return form;
        },
        authHeaders
      );
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(`Upload failed: ${res.status} ${text}`);
      }
      onProgress?.(Math.round(((i + 1) / total) * 100));
    }
    return {
      upload_id: uploadId,
      filename: name,
      mime_type: finalType,
      total_chunks: total,
    };
  }

  // Native
  let size = 0;
  try {
    const info = await FileSystem.getInfoAsync(uri, { size: true } as any);
    size = (info as any)?.size || 0;
  } catch {
    size = 0;
  }
  if (!size) throw new Error("Could not read the selected video");
  const total = Math.max(1, Math.ceil(size / CHUNK_SIZE));
  for (let i = 0; i < total; i++) {
    const b64 = await FileSystem.readAsStringAsync(uri, {
      encoding: FileSystem.EncodingType.Base64,
      position: i * CHUNK_SIZE,
      length: Math.min(CHUNK_SIZE, size - i * CHUNK_SIZE),
    });
    const res = await postFormWithRetry(
      `${API_URL}/uploads/chunk`,
      () => {
        const form = new FormData();
        form.append("upload_id", uploadId);
        form.append("chunk_index", String(i));
        form.append("total_chunks", String(total));
        form.append("chunk_b64", b64);
        return form;
      },
      authHeaders
    );
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`Upload failed: ${res.status} ${text}`);
    }
    onProgress?.(Math.round(((i + 1) / total) * 100));
  }
  return {
    upload_id: uploadId,
    filename: name,
    mime_type: mimeType || "video/mp4",
    total_chunks: total,
  };
}

export async function finalizeMultiUpload(
  uploads: ChunkedUploadRef[]
): Promise<Analysis> {
  return apiFetch<Analysis>("/analyses/finalize-multi", {
    method: "POST",
    body: JSON.stringify({ uploads }),
  });
}

// ---- Skeleton tracking (pose) ----
export type PoseFrame = { t: number; kp: number[][] }; // 33 x [x, y, visibility]
export type MetricPoint = { t: number; v: number };
export type PoseData = {
  version: number;
  width: number;
  height: number;
  sample_fps: number;
  frames: PoseFrame[];
  metrics: { speed: MetricPoint[]; compression: MetricPoint[] };
};

export async function getPoseData(
  analysisId: string
): Promise<{ status: string; data: PoseData | null }> {
  return apiFetch(`/analyses/${analysisId}/pose`);
}

// ---- Pro reference clips (royalty-free, skeleton-tracked) ----
export function getProVideoUrl(clipId: string) {
  return `${API_URL}/pro/${clipId}/video`;
}

export async function getProPose(
  clipId: string
): Promise<{ status: string; data: PoseData | null }> {
  return apiFetch(`/pro/${clipId}/pose`);
}

// ---- Quotas, plans, payments ----
export type Quota = {
  tier: string;
  remaining: number;
  limit: number;
  used_today: number;
};

export async function getQuota(): Promise<Quota> {
  return apiFetch<Quota>("/analyses/quota");
}

export type Plan = {
  plan_id: string;
  name: string;
  amount: number;
  currency: string;
  features: string[];
  interval?: string;
};

export async function getPlans(): Promise<{
  plans: Plan[];
  free_daily_limit: number;
}> {
  const res = await fetch(`${API_URL}/plans`);
  return res.json();
}

export async function createCheckout(planId: string, originUrl: string) {
  // LemonSqueezy hosted checkout (replaces Stripe).
  return apiFetch<{ url: string; session_id: string }>(
    "/payments/lemonsqueezy/checkout",
    {
      method: "POST",
      body: JSON.stringify({ plan_id: planId, origin_url: originUrl }),
    }
  );
}

export async function getPaymentStatus(sessionId: string) {
  return apiFetch<{
    session_id: string;
    status: string;
    payment_status: string;
    plan_id?: string;
    tier?: string | null;
  }>(`/payments/lemonsqueezy/status/${sessionId}`);
}

// ---- Coaches ----
export type CoachListItem = {
  user_id: string;
  name: string;
  picture?: string | null;
  coach_bio?: string | null;
  coach_specialty?: string | null;
  coach_location?: string | null;
};

export async function listCoaches(filters?: {
  q?: string;
  location?: string;
  specialty?: string;
}): Promise<CoachListItem[]> {
  const qs = new URLSearchParams();
  if (filters?.q) qs.append("q", filters.q);
  if (filters?.location) qs.append("location", filters.location);
  if (filters?.specialty) qs.append("specialty", filters.specialty);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  const res = await fetch(`${API_URL}/coaches${suffix}`);
  return res.json();
}

export async function updateCoachProfile(payload: {
  bio?: string;
  specialty?: string;
  location?: string;
  public?: boolean;
}) {
  return apiFetch<User>("/coach/profile", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function coachInbox(): Promise<AnalysisListItem[]> {
  return apiFetch<AnalysisListItem[]>("/coach/inbox");
}

// ---- Account + plan management ----
export async function updatePreferences(language: string) {
  return apiFetch<User>("/users/preferences", {
    method: "PUT",
    body: JSON.stringify({ language }),
  });
}

export async function deleteAccount() {
  return apiFetch<{ ok: boolean }>("/auth/account", { method: "DELETE" });
}

export async function cancelRenewal() {
  return apiFetch<{
    cancel_at_period_end: boolean;
    subscription_expires_at?: string | null;
  }>("/payments/cancel-renewal", { method: "POST" });
}

export async function resumeRenewal() {
  return apiFetch<{
    cancel_at_period_end: boolean;
    subscription_expires_at?: string | null;
  }>("/payments/resume-renewal", { method: "POST" });
}
export async function shareWithCoach(analysisId: string, coachUserId: string) {
  return apiFetch(`/analyses/${analysisId}/share`, {
    method: "POST",
    body: JSON.stringify({ coach_user_id: coachUserId }),
  });
}

export type AnalysisComment = {
  comment_id: string;
  analysis_id: string;
  author_id: string;
  author_name: string;
  author_picture?: string | null;
  is_coach: boolean;
  text: string;
  created_at: string;
};

export async function listComments(
  analysisId: string
): Promise<AnalysisComment[]> {
  return apiFetch<AnalysisComment[]>(`/analyses/${analysisId}/comments`);
}

export async function addComment(analysisId: string, text: string) {
  return apiFetch<AnalysisComment>(`/analyses/${analysisId}/comments`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}
