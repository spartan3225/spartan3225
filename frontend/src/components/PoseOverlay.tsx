import React, { useMemo } from "react";
import { View, StyleSheet } from "react-native";
import Svg, { Line, Circle, Polyline, Text as SvgText } from "react-native-svg";
import { PoseData } from "../api";
import { colors } from "../theme";

// MediaPipe Pose skeleton connections (subset for a clean overlay)
const CONNECTIONS: [number, number][] = [
  [11, 12], // shoulders
  [11, 13], [13, 15], // left arm
  [12, 14], [14, 16], // right arm
  [11, 23], [12, 24], // torso
  [23, 24], // hips
  [23, 25], [25, 27], [27, 31], // left leg + foot
  [24, 26], [26, 28], [28, 32], // right leg + foot
  [0, 11], [0, 12], // head to shoulders
];

const JOINTS = [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28, 31, 32];

function angle(a: number[], b: number[], c: number[]): number {
  const v1 = [a[0] - b[0], a[1] - b[1]];
  const v2 = [c[0] - b[0], c[1] - b[1]];
  const n1 = Math.hypot(v1[0], v1[1]) || 1e-6;
  const n2 = Math.hypot(v2[0], v2[1]) || 1e-6;
  const cos = Math.max(-1, Math.min(1, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)));
  return (Math.acos(cos) * 180) / Math.PI;
}

type Props = {
  data: PoseData;
  time: number; // current video time in seconds
  width: number; // displayed video rect width (px)
  height: number; // displayed video rect height (px)
};

export default function PoseOverlay({ data, time, width, height }: Props) {
  const frames = data.frames;

  const idx = useMemo(() => {
    if (!frames.length) return -1;
    // nearest frame to `time`
    let lo = 0;
    let hi = frames.length - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (frames[mid].t < time) lo = mid + 1;
      else hi = mid;
    }
    if (lo > 0 && Math.abs(frames[lo - 1].t - time) < Math.abs(frames[lo].t - time))
      lo -= 1;
    return lo;
  }, [frames, time]);

  if (idx < 0 || width <= 0 || height <= 0) return null;
  const frame = frames[idx];
  // hide overlay if the nearest tracked frame is too far from playhead
  if (Math.abs(frame.t - time) > 0.6) return null;

  const kp = frame.kp;
  const X = (i: number) => kp[i][0] * width;
  const Y = (i: number) => kp[i][1] * height;
  const vis = (i: number) => kp[i][2] > 0.4;

  // Center of gravity = hip midpoint
  const hipOk = vis(23) || vis(24);
  const cgx = (X(23) + X(24)) / 2;
  const cgy = (Y(23) + Y(24)) / 2;

  // Motion trail: hip centres of the previous ~8 frames
  const trail: string[] = [];
  for (let i = Math.max(0, idx - 8); i <= idx; i++) {
    const k = frames[i].kp;
    trail.push(
      `${(((k[23][0] + k[24][0]) / 2) * width).toFixed(1)},${(
        ((k[23][1] + k[24][1]) / 2) *
        height
      ).toFixed(1)}`
    );
  }

  // Velocity arrow (direction of travel)
  let arrow: { x2: number; y2: number } | null = null;
  if (idx > 0) {
    const pk = frames[idx - 1].kp;
    const px = (((pk[23][0] + pk[24][0]) / 2) * width);
    const py = (((pk[23][1] + pk[24][1]) / 2) * height);
    const dx = cgx - px;
    const dy = cgy - py;
    const mag = Math.hypot(dx, dy);
    if (mag > 1) {
      const scale = Math.min(46, mag * 5) / mag;
      arrow = { x2: cgx + dx * scale, y2: cgy + dy * scale };
    }
  }

  // Knee angle (best visible leg)
  let kneeAngle: number | null = null;
  let kneePos: [number, number] | null = null;
  for (const [h, k, a] of [
    [23, 25, 27],
    [24, 26, 28],
  ] as [number, number, number][]) {
    if (vis(k) && kp[h][2] > 0.3 && kp[a][2] > 0.3) {
      kneeAngle = angle(kp[h], kp[k], kp[a]);
      kneePos = [X(k), Y(k)];
      break;
    }
  }

  // Back angle vs vertical (shoulder-mid to hip-mid)
  let backAngle: number | null = null;
  if ((vis(11) || vis(12)) && hipOk) {
    const sx = (X(11) + X(12)) / 2;
    const sy = (Y(11) + Y(12)) / 2;
    backAngle = angle([sx, sy], [cgx, cgy], [cgx, cgy - 50]);
  }

  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none">
      <Svg width={width} height={height}>
        {/* Motion trail */}
        {trail.length > 2 && (
          <Polyline
            points={trail.join(" ")}
            fill="none"
            stroke="rgba(0,229,255,0.45)"
            strokeWidth={2}
            strokeDasharray="3,4"
          />
        )}
        {/* Bones */}
        {CONNECTIONS.map(([a, b], i) =>
          vis(a) && vis(b) ? (
            <Line
              key={i}
              x1={X(a)}
              y1={Y(a)}
              x2={X(b)}
              y2={Y(b)}
              stroke={colors.primary}
              strokeWidth={2.4}
              strokeLinecap="round"
              opacity={0.95}
            />
          ) : null
        )}
        {/* Joints */}
        {JOINTS.map((j) =>
          vis(j) ? (
            <Circle
              key={j}
              cx={X(j)}
              cy={Y(j)}
              r={3.4}
              fill="#fff"
              stroke={colors.primary}
              strokeWidth={1.4}
            />
          ) : null
        )}
        {/* Center of gravity */}
        {hipOk && (
          <>
            <Circle cx={cgx} cy={cgy} r={7} fill="rgba(0,255,136,0.25)" />
            <Circle cx={cgx} cy={cgy} r={3.4} fill={colors.success} />
          </>
        )}
        {/* Velocity arrow */}
        {arrow && hipOk && (
          <>
            <Line
              x1={cgx}
              y1={cgy}
              x2={arrow.x2}
              y2={arrow.y2}
              stroke={colors.warning}
              strokeWidth={2.6}
              strokeLinecap="round"
            />
            <Circle cx={arrow.x2} cy={arrow.y2} r={3.4} fill={colors.warning} />
          </>
        )}
        {/* Angle labels */}
        {kneeAngle !== null && kneePos && (
          <SvgText
            x={kneePos[0] + 9}
            y={kneePos[1] + 4}
            fill="#fff"
            fontSize={11}
            fontWeight="bold"
            stroke="rgba(0,0,0,0.7)"
            strokeWidth={0.6}
          >
            {Math.round(kneeAngle)}°
          </SvgText>
        )}
        {backAngle !== null && hipOk && (
          <SvgText
            x={cgx + 11}
            y={cgy - 10}
            fill={colors.success}
            fontSize={11}
            fontWeight="bold"
            stroke="rgba(0,0,0,0.7)"
            strokeWidth={0.6}
          >
            {Math.round(backAngle)}°
          </SvgText>
        )}
      </Svg>
    </View>
  );
}
