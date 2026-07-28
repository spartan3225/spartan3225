import { View, Text, StyleSheet } from "react-native";
import Svg, { Circle } from "react-native-svg";
import { colors, scoreColor } from "../theme";

type Props = {
  value: number;
  size?: number;
  thickness?: number;
  color?: string;
  showValue?: boolean;
  valueSize?: number;
  suffix?: string;
};

export default function ScoreRing({
  value,
  size = 64,
  thickness = 5,
  color,
  showValue = true,
  valueSize,
  suffix,
}: Props) {
  const v = Math.max(0, Math.min(100, Math.round(value || 0)));
  const c = color || scoreColor(v);
  const r = (size - thickness) / 2;
  const circumference = 2 * Math.PI * r;
  const offset = circumference * (1 - v / 100);

  return (
    <View style={{ width: size, height: size }}>
      <Svg width={size} height={size}>
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke="rgba(255,255,255,0.09)"
          strokeWidth={thickness}
          fill="none"
        />
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={c}
          strokeWidth={thickness}
          strokeLinecap="round"
          fill="none"
          strokeDasharray={`${circumference}`}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </Svg>
      {showValue && (
        <View style={styles.center}>
          <Text
            style={[
              styles.value,
              { fontSize: valueSize || size * 0.3, color: colors.textPrimary },
            ]}
          >
            {v}
            {suffix ? <Text style={styles.suffix}>{suffix}</Text> : null}
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  center: {
    ...StyleSheet.absoluteFillObject,
    alignItems: "center",
    justifyContent: "center",
  },
  value: { fontWeight: "900", letterSpacing: -1 },
  suffix: { fontSize: 10, color: colors.textMuted, fontWeight: "700" },
});
