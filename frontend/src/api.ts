import AsyncStorage from "@react-native-async-storage/async-storage";

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;
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
  duration_seconds?: number | null;
  status: string;
  created_at: string;
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
  try {
    await apiFetch("/auth/logout", { method: "POST" });
  } catch {
    // ignore
  }
  await clearToken();
}

export async function uploadVideo(uri: string, name: string, mimeType: string) {
  const token = await getToken();
  const form = new FormData();
  // RN: file as { uri, name, type }
  // @ts-ignore
  form.append("file", { uri, name, type: mimeType });
  const res = await fetch(`${API_URL}/analyses`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form as any,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Upload failed: ${res.status} ${text}`);
  }
  return (await res.json()) as Analysis;
}

export function getVideoStreamUrl(analysisId: string, token: string) {
  return `${API_URL}/analyses/${analysisId}/video?token=${encodeURIComponent(
    token
  )}`;
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
  return apiFetch<{ url: string; session_id: string }>(
    "/payments/checkout",
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
  }>(`/payments/status/${sessionId}`);
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

export async function listCoaches(): Promise<CoachListItem[]> {
  const res = await fetch(`${API_URL}/coaches`);
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

// ---- Sharing & Comments ----
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
