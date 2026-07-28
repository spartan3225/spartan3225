import { View } from "react-native";
import Svg, { Polygon, Line, Text as SvgText } from "react-native-svg";
import { colors } from "../theme";

export type RadarAxis = { label: string; value: number; compare?: number };

/**
 * Spider/radar chart. `value` (cyan) is the user; optional `compare`
 * (green outline) is a second series (e.g. a pro benchmark).
 */
export default function RadarChart({
  axes,
  size = 280,
}: {
  axes: RadarAxis[];
  size?: number;
}) {
  const n = axes.length;
  if (n < 3) return null;
  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2 - 34;

  const pt = (i: number, v: number) => {
    const ang = (Math.PI * 2 * i) / n - Math.PI / 2;
    const rad = (v / 100) * r;
    return [cx + Math.cos(ang) * rad, cy + Math.sin(ang) * rad];
  };
  const poly = (vals: number[]) =>
    vals.map((v, i) => pt(i, v).map((c) => c.toFixed(1)).join(",")).join(" ");

  return (
    <View style={{ alignItems: "center" }}>
      <Svg width={size} height={size}>
        {/* Grid rings */}
        {[25, 50, 75, 100].map((g) => (
          <Polygon
            key={g}
            points={poly(axes.map(() => g))}
            fill="none"
            stroke="rgba(255,255,255,0.08)"
            strokeWidth={1}
          />
        ))}
        {/* Spokes */}
        {axes.map((_, i) => {
          const [x, y] = pt(i, 100);
          return (
            <Line
              key={i}
              x1={cx}
              y1={cy}
              x2={x}
              y2={y}
              stroke="rgba(255,255,255,0.08)"
              strokeWidth={1}
            />
          );
        })}
        {/* Compare series (pro benchmark) */}
        {axes.some((a) => a.compare !== undefined) && (
          <Polygon
            points={poly(axes.map((a) => a.compare ?? 0))}
            fill="rgba(0,255,136,0.08)"
            stroke={colors.success}
            strokeWidth={1.5}
            strokeDasharray="4,4"
          />
        )}
        {/* User series */}
        <Polygon
          points={poly(axes.map((a) => a.value))}
          fill="rgba(0,229,255,0.18)"
          stroke={colors.primary}
          strokeWidth={2}
        />
        {/* Labels */}
        {axes.map((a, i) => {
          const [x, y] = pt(i, 122);
          return (
            <SvgText
              key={i}
              x={x}
              y={y}
              fill={colors.textSecondary}
              fontSize={9.5}
              fontWeight="700"
              textAnchor="middle"
            >
              {a.label}
            </SvgText>
          );
        })}
      </Svg>
    </View>
  );
}
