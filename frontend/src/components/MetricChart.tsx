import { View, Text, StyleSheet } from "react-native";
import Svg, { Line, Path } from "react-native-svg";
import { MetricPoint } from "../api";
import { colors } from "../theme";

const W = 300;
const H = 90;

/**
 * Heat-colored performance graph: segments are green where the metric is in
 * its best range, red where it drops into its worst range, cyan in between.
 */
export default function MetricChart({
  points,
  higherIsBetter = true,
}: {
  points: MetricPoint[];
  higherIsBetter?: boolean;
}) {
  if (!points || points.length < 2) return null;

  const vals = points.map((p) => p.v);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const range = max - min || 1;
  const sorted = vals.slice().sort((a, b) => a - b);
  const p40 = sorted[Math.floor(sorted.length * 0.4)];
  const p60 = sorted[Math.floor(sorted.length * 0.6)];

  const t0 = points[0].t;
  const t1 = points[points.length - 1].t;
  const tr = t1 - t0 || 1;
  const px = (p: MetricPoint) => ((p.t - t0) / tr) * W;
  const py = (p: MetricPoint) => H - ((p.v - min) / range) * (H - 10) - 5;

  const colorFor = (v: number) => {
    const good = higherIsBetter ? v >= p60 : v <= p40;
    const bad = higherIsBetter ? v <= p40 : v >= p60;
    if (good) return colors.success;
    if (bad) return colors.error;
    return colors.primary;
  };

  const segs = [];
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i];
    const b = points[i + 1];
    segs.push(
      <Path
        key={i}
        d={`M ${px(a).toFixed(1)} ${py(a).toFixed(1)} L ${px(b).toFixed(1)} ${py(b).toFixed(1)}`}
        stroke={colorFor((a.v + b.v) / 2)}
        strokeWidth={2.6}
        strokeLinecap="round"
        fill="none"
      />
    );
  }

  return (
    <View style={{ alignItems: "center" }}>
      <Svg width={W} height={H}>
        {[0.25, 0.5, 0.75].map((g) => (
          <Line
            key={g}
            x1={0}
            y1={H * g}
            x2={W}
            y2={H * g}
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={1}
          />
        ))}
        {segs}
      </Svg>
      <View style={styles.axisRow}>
        <Text style={styles.axisText}>{Math.round(t0)}s</Text>
        <Text style={styles.axisText}>{Math.round(t1)}s</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  axisRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    width: W,
    marginTop: 2,
  },
  axisText: { color: colors.textMuted, fontSize: 9 },
});
