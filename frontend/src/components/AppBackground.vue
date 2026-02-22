<template>
  <div class="app-background" aria-hidden="true">
    <motion.div
      v-for="shape in shapes"
      :key="shape.id"
      class="paper-shape"
      :class="shape.variant"
      :style="shapeStyle(shape)"
      :initial="shapeInitial(shape)"
      :animate="reducedMotion ? shapeStatic(shape) : shapeAnimate(shape)"
      :transition="shapeTransition(shape)"
    />
    <div class="paper-vignette"></div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { motion, useReducedMotion } from "motion-v";

type ShapeVariant = "paper-circle" | "paper-rounded" | "paper-pebble";

interface FloatingShape {
  id: string;
  variant: ShapeVariant;
  colorIndex: 1 | 2 | 3 | 4 | 5 | 6;
  width: number;
  height: number;
  left: string;
  top: string;
  opacity: number;
  yRange: number[];
  rotateRange: number[];
  xRange: number[];
  duration: number;
  delay: number;
}

const prefersReducedMotion = useReducedMotion();
const motionMode = ref<"auto" | "on" | "off">("auto");
const reducedMotion = computed(() => {
  if (motionMode.value === "on") {
    return false;
  }
  if (motionMode.value === "off") {
    return true;
  }
  return Boolean(prefersReducedMotion.value);
});

const shapes: FloatingShape[] = [
  {
    id: "paper-1",
    variant: "paper-rounded",
    colorIndex: 1,
    width: 270,
    height: 190,
    left: "4%",
    top: "10%",
    opacity: 0.5,
    yRange: [-24, 18, -22],
    rotateRange: [-9, 7, -8],
    xRange: [-20, 16, -18],
    duration: 14,
    delay: 0
  },
  {
    id: "paper-2",
    variant: "paper-circle",
    colorIndex: 2,
    width: 190,
    height: 190,
    left: "80%",
    top: "8%",
    opacity: 0.44,
    yRange: [-18, 20, -18],
    rotateRange: [-8, 6, -7],
    xRange: [16, -20, 16],
    duration: 13.5,
    delay: 0.4
  },
  {
    id: "paper-3",
    variant: "paper-pebble",
    colorIndex: 3,
    width: 250,
    height: 170,
    left: "68%",
    top: "68%",
    opacity: 0.42,
    yRange: [-20, 16, -19],
    rotateRange: [8, -7, 7],
    xRange: [15, -18, 15],
    duration: 16,
    delay: 0.6
  },
  {
    id: "paper-4",
    variant: "paper-rounded",
    colorIndex: 4,
    width: 220,
    height: 160,
    left: "15%",
    top: "72%",
    opacity: 0.38,
    yRange: [-19, 15, -18],
    rotateRange: [7, -6, 7],
    xRange: [-17, 14, -16],
    duration: 15,
    delay: 0.3
  },
  {
    id: "paper-5",
    variant: "paper-circle",
    colorIndex: 5,
    width: 130,
    height: 130,
    left: "45%",
    top: "16%",
    opacity: 0.32,
    yRange: [-14, 14, -14],
    rotateRange: [-6, 5, -6],
    xRange: [12, -12, 12],
    duration: 12.5,
    delay: 0.8
  },
  {
    id: "paper-6",
    variant: "paper-pebble",
    colorIndex: 6,
    width: 170,
    height: 120,
    left: "36%",
    top: "78%",
    opacity: 0.31,
    yRange: [-15, 12, -15],
    rotateRange: [6, -5, 6],
    xRange: [-11, 11, -11],
    duration: 11.5,
    delay: 0.1
  }
];

function shapeStyle(shape: FloatingShape): Record<string, string | number> {
  return {
    "--shape-color": `var(--paper-shape-${shape.colorIndex})`,
    width: `${shape.width}px`,
    height: `${shape.height}px`,
    left: shape.left,
    top: shape.top,
    opacity: shape.opacity
  };
}

function shapeInitial(shape: FloatingShape): Record<string, number> {
  return {
    x: shape.xRange[0],
    y: shape.yRange[0],
    rotate: shape.rotateRange[0],
    scale: 1
  };
}

function shapeStatic(shape: FloatingShape): Record<string, number> {
  return {
    x: shape.xRange[0],
    y: shape.yRange[0],
    rotate: shape.rotateRange[0],
    scale: 1
  };
}

function shapeAnimate(shape: FloatingShape): Record<string, number[]> {
  return {
    x: shape.xRange,
    y: shape.yRange,
    rotate: shape.rotateRange,
    scale: [1, 1.03, 1]
  };
}

function shapeTransition(shape: FloatingShape): Record<string, string | number> {
  return {
    duration: shape.duration,
    repeat: Infinity,
    ease: "easeInOut",
    delay: shape.delay
  };
}

onMounted(() => {
  const motionParam = new URLSearchParams(window.location.search).get("motion")?.toLowerCase();
  if (motionParam === "on" || motionParam === "off") {
    motionMode.value = motionParam;
  }
});
</script>
