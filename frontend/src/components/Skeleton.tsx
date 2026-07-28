import { useEffect, useRef } from "react";
import { Animated, StyleProp, ViewStyle } from "react-native";
import { radii } from "../theme";

export default function Skeleton({
  width,
  height,
  style,
  radius = radii.md,
}: {
  width?: number | `${number}%`;
  height: number;
  style?: StyleProp<ViewStyle>;
  radius?: number;
}) {
  const pulse = useRef(new Animated.Value(0.35)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 0.75, duration: 700, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0.35, duration: 700, useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [pulse]);

  return (
    <Animated.View
      style={[
        {
          width: width ?? "100%",
          height,
          borderRadius: radius,
          backgroundColor: "#1E1E22",
          opacity: pulse,
        },
        style,
      ]}
    />
  );
}
